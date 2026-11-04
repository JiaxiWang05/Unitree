"""OpenAI Realtime backend (default): ``gpt-realtime-2.1`` over a raw asyncio WebSocket.

No SDK, only ``websockets``, so it runs on the Jetson's system Python. This is
the asyncio rewrite of the voice layer of namanbansal013/unitree-openai-voice
(MIT, (c) 2026 Naman Bansal): same G1 audio plumbing (16 kHz mic -> 24 kHz in,
24 kHz reply -> 16 kHz PlayStream), plus reconnect, truncation on barge-in,
reasoning effort "minimal" and a pre-generated opener.

* warm session at NOTICED; the opener is generated **out of band**
  (``response.create`` with ``conversation: "none"``, the frame as ``input_image``
  and a scene note) so it is ready the moment the visitor is in range;
* once played, the opener is appended to the conversation (append-only: no
  item is ever deleted, so the prompt cache stays warm);
* turn detection: semantic VAD with ``create_response: false``. A fresh frame
  goes in as ``input_image`` when the visitor starts speaking and again at
  commit if the scene changed; then ``response.create``;
* barge-in: ``conversation.item.truncate`` at the audio actually played, both while
  the reply is still being generated and while its audio is still playing;
* a visitor who doesn't pause: commit their turn and answer with a cut-in instruction;
* a dropped connection is re-opened once and re-seeded with the text so far;
* usage from every ``response.done`` goes to the spend meter; spend-limit or
  quota errors raise ``provider_down`` so the runner switches provider.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import os
import platform
import time
from typing import List, Optional, Tuple

import numpy as np

from greeter.audio import StreamResampler
from greeter.backends.base import Backend, ProviderDown
from greeter.backends.spend import METER, is_provider_down, response_cost
from greeter.dialogue.prompts import SYSTEM_PROMPT

log = logging.getLogger(__name__)

DEFAULT_MODEL = "gpt-realtime-2.1"
RATE = 24000  # Realtime PCM in and out
URL = "wss://api.openai.com/v1/realtime?model={model}"


def _image_part(jpeg: bytes, detail: str) -> dict:
    return {
        "type": "input_image",
        "image_url": "data:image/jpeg;base64," + base64.b64encode(jpeg).decode("ascii"),
        "detail": detail,
    }


def _safety_identifier() -> str:
    """Stable, anonymous id for this robot (OpenAI recommends one per end user/app)."""
    return "g1-greeter-" + hashlib.sha256(platform.node().encode()).hexdigest()[:16]


def frames_differ(a: Optional[bytes], b: Optional[bytes], threshold: float = 12.0) -> bool:
    """Coarse scene-change test between two JPEGs (mean abs difference of 32x24 grey)."""
    if a is None or b is None:
        return a is not b
    import cv2

    small = []
    for jpeg in (a, b):
        img = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_GRAYSCALE)
        if img is None:
            return True
        small.append(cv2.resize(img, (32, 24), interpolation=cv2.INTER_AREA).astype(np.float32))
    return float(np.mean(np.abs(small[0] - small[1]))) > threshold


class OpenAIRealtimeBackend(Backend):
    name = "openai"
    supports_opener = True

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        voice: str = "marin",
        system_prompt: str = SYSTEM_PROMPT,
        api_key: Optional[str] = None,
        eagerness: str = "auto",
        reasoning_effort: Optional[str] = "minimal",
        transcription_model: Optional[str] = "gpt-4o-mini-transcribe",
        noise_reduction: Optional[str] = "far_field",
        greet_detail: str = "auto",
        turn_detail: str = "low",
        url: Optional[str] = None,
        reconnect: bool = True,
    ) -> None:
        super().__init__()
        self.model, self.voice, self.system_prompt = model, voice, system_prompt
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.eagerness, self.reasoning_effort = eagerness, reasoning_effort
        self.transcription_model, self.noise_reduction = transcription_model, noise_reduction
        self.greet_detail, self.turn_detail = greet_detail, turn_detail
        self.url = url or URL.format(model=model)
        self.reconnect = reconnect
        self.name = "openai:" + model
        self.ws = None
        self.note = ""
        self.latest_jpeg: Optional[bytes] = None
        self._sent_jpeg: Optional[bytes] = None
        self._rx: Optional[asyncio.Task] = None
        self._heartbeat: Optional[asyncio.Task] = None
        self._upsample = StreamResampler(16000, RATE)
        self._responding = False
        self._user_turn_open = False
        self._pending_instruction: Optional[str] = None  # for the reply to a turn we committed ourselves
        self._history: List[Tuple[str, str]] = []  # (role, text), for re-seeding after a reconnect
        self._said = ""
        # out-of-band opener
        self._opener_id: Optional[str] = None
        self._opener_pcm = bytearray()
        self._opener_text = ""
        # what is playing, for truncation on barge-in
        self._item_id: Optional[str] = None
        self._item_audio_ms = 0.0
        self._item_first_audio = 0.0

    # --- session ---------------------------------------------------------
    def session_config(self) -> dict:
        audio_in = {
            "format": {"type": "audio/pcm", "rate": RATE},
            "turn_detection": {
                "type": "semantic_vad",
                "eagerness": self.eagerness,
                "create_response": False,  # we answer ourselves, after attaching a fresh frame
                "interrupt_response": True,
            },
        }
        if self.transcription_model:
            audio_in["transcription"] = {"model": self.transcription_model, "language": "en"}
        if self.noise_reduction:
            audio_in["noise_reduction"] = {"type": self.noise_reduction}
        session = {
            "type": "realtime",
            "model": self.model,
            "output_modalities": ["audio"],
            "instructions": self.system_prompt,
            "audio": {"input": audio_in, "output": {"format": {"type": "audio/pcm", "rate": RATE}, "voice": self.voice}},
        }
        if self.reasoning_effort:
            session["reasoning"] = {"effort": self.reasoning_effort}
        return session

    async def _send(self, event: dict) -> None:
        if self.ws is None or self._closed:
            return
        try:
            await self.ws.send(json.dumps(event))
        except Exception as exc:
            if not self._closed:
                log.warning("openai send failed: %s", exc)

    async def _wait_for(self, *types_: str, timeout: float = 10.0) -> dict:
        async def wait() -> dict:
            while True:
                event = json.loads(await self.ws.recv())
                if event.get("type") == "error":
                    err = event.get("error") or {}
                    if is_provider_down(err.get("code"), err.get("message")):
                        raise ProviderDown(err.get("message") or str(err))
                    raise RuntimeError("OpenAI Realtime error: %s" % err.get("message", event))
                if event.get("type") in types_:
                    return event

        return await asyncio.wait_for(wait(), timeout)

    async def _connect(self) -> None:
        from websockets.asyncio.client import connect
        from websockets.exceptions import InvalidStatus

        if not self.api_key:
            raise ProviderDown("OPENAI_API_KEY is not set (API key from platform.openai.com, see README)")
        try:
            self.ws = await connect(
                self.url,
                additional_headers={"Authorization": "Bearer " + self.api_key, "OpenAI-Safety-Identifier": _safety_identifier()},
                max_size=16 * 1024 * 1024,
                open_timeout=10,
                ping_interval=20,
                ping_timeout=20,
            )
        except InvalidStatus as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status in (401, 403, 429):
                raise ProviderDown("OpenAI refused the connection (HTTP %s)" % status) from exc
            raise
        await self._wait_for("session.created")
        await self.ws.send(json.dumps({"type": "session.update", "session": self.session_config()}))
        await self._wait_for("session.updated")

    async def open(self, jpeg: Optional[bytes], note: str) -> None:
        self.note = note
        self.latest_jpeg = jpeg
        await self._connect()
        self._rx = asyncio.ensure_future(self._receive())
        self._heartbeat = asyncio.ensure_future(self._keep_alive())
        if note:
            await self._send({"type": "conversation.item.create", "item": _user_item([{"type": "input_text", "text": note}])})
        log.info("openai realtime session warm (%s, voice %s)", self.model, self.voice)

    async def _reopen(self) -> bool:
        """The socket dropped mid-visit: reconnect once and re-seed the conversation as text."""
        try:
            await self._connect()
        except Exception as exc:
            log.warning("openai reconnect failed: %s", exc)
            return False
        items = [_user_item([{"type": "input_text", "text": self.note}])] if self.note else []
        for role, text in self._history:
            if role == "user":
                items.append(_user_item([{"type": "input_text", "text": text}]))
            else:
                items.append({"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": text}]})
        for item in items:
            await self._send({"type": "conversation.item.create", "item": item})
        self._responding = self._user_turn_open = False
        log.info("openai reconnected and re-seeded %d items", len(items))
        return True

    # --- opener ----------------------------------------------------------
    async def prepare_opener(self, jpeg: bytes, instruction: str) -> None:
        self._opener_request = (jpeg, instruction)
        content = [_image_part(jpeg, self.greet_detail)]
        if self.note:
            content.append({"type": "input_text", "text": self.note})
        await self._send(
            {
                "type": "response.create",
                "response": {
                    "conversation": "none",  # out of band: not added to the conversation
                    "metadata": {"purpose": "opener"},
                    "output_modalities": ["audio"],
                    "instructions": self.system_prompt + "\n\n" + instruction,
                    "input": [_user_item(content)],
                },
            }
        )

    async def commit_opener(self, text: str) -> None:
        """Append-only: the frame and what the robot said become part of the conversation."""
        if self._opener_request is not None:
            await self._send({"type": "conversation.item.create", "item": _user_item([_image_part(self._opener_request[0], "low")])})
            self._sent_jpeg = self._opener_request[0]
        await self._send(
            {"type": "conversation.item.create", "item": {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": text}]}}
        )
        self._history.append(("assistant", text))

    async def begin(self, instruction: Optional[str]) -> None:
        if instruction:
            await self._respond(instruction)

    async def _respond(self, instruction: Optional[str] = None) -> None:
        response: dict = {}
        if instruction:
            # per-response instructions replace the session ones, so keep the persona and rules
            response["instructions"] = self.system_prompt + "\n\n" + instruction
        await self._send({"type": "response.create", "response": response})

    # --- events from OpenAI ----------------------------------------------
    async def _receive(self) -> None:
        while not self._closed:
            try:
                async for raw in self.ws:
                    await self._handle(json.loads(raw))
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.warning("openai receive failed: %s", exc)
            if self._closed:
                return
            if not (self.reconnect and await self._reopen()):
                self._emit("error", "OpenAI Realtime connection closed")
                return

    async def _handle(self, event: dict) -> None:
        kind = event.get("type", "")
        response_id = event.get("response_id")
        if kind == "response.output_audio.delta":
            pcm = base64.b64decode(event["delta"])
            if response_id is not None and response_id == self._opener_id:
                self._opener_pcm.extend(pcm)
                return
            if event.get("item_id") != self._item_id:
                self._item_id, self._item_audio_ms, self._item_first_audio = event.get("item_id"), 0.0, time.monotonic()
            self._item_audio_ms += len(pcm) / (RATE * 2) * 1000.0
            self._emit("audio", pcm, RATE)
        elif kind == "response.output_audio_transcript.delta":
            if response_id is not None and response_id == self._opener_id:
                self._opener_text += event.get("delta", "")
            else:
                self._said += event.get("delta", "")
                self._emit("bot_text", event.get("delta", ""))
        elif kind == "response.created":
            response = event.get("response") or {}
            if (response.get("metadata") or {}).get("purpose") == "opener":
                self._opener_id = response.get("id")
            else:
                self._responding = True
                self._user_turn_open = False
        elif kind == "response.done":
            response = event.get("response") or {}
            cost = response_cost(self.model, response.get("usage") or {})
            METER.add(cost)
            if cost is not None:
                self._emit("usage", {"model": self.model, "cost_usd": cost, "tokens": (response.get("usage") or {}).get("total_tokens")})
            details = response.get("status_details") or {}
            error = details.get("error") or {}
            if response.get("status") == "failed" and is_provider_down(error.get("code"), error.get("message")):
                self._emit("provider_down", error.get("message") or error.get("code"))
            if response.get("id") is not None and response.get("id") == self._opener_id:
                self._emit("opener_ready", {"pcm": bytes(self._opener_pcm), "rate": RATE, "text": self._opener_text.strip()})
                self._opener_id = None
                return
            self._responding = False
            if self._said.strip():
                self._history.append(("assistant", self._said.strip()))
            self._said = ""
            self._emit("turn_complete")
        elif kind == "input_audio_buffer.speech_started":
            self._user_turn_open = True
            self._emit("user_activity")
            if self._responding or self._playing():
                await self._truncate()
                self._emit("interrupted")  # the server cancels the reply; drop what is queued
            await self._attach_frame()
        elif kind == "input_audio_buffer.speech_stopped":
            self._emit("user_activity")
        elif kind == "input_audio_buffer.committed":
            self._emit("user_turn_end")
            self._user_turn_open = False
            if frames_differ(self._sent_jpeg, self.latest_jpeg):
                await self._attach_frame()
            instruction, self._pending_instruction = self._pending_instruction, None
            await self._respond(instruction)
        elif kind == "conversation.item.input_audio_transcription.completed":
            text = (event.get("transcript") or "").strip()
            if text:
                self._history.append(("user", text))
                self._emit("user_text", text)
        elif kind == "error":
            err = event.get("error") or {}
            if is_provider_down(err.get("code"), err.get("message")):
                self._emit("provider_down", err.get("message") or err.get("code"))
            else:  # most errors (e.g. a response already in progress) don't end the session
                log.warning("openai error: %s", err.get("message", event))

    async def _attach_frame(self) -> None:
        jpeg = self.latest_jpeg
        if jpeg is None or jpeg is self._sent_jpeg:
            return
        self._sent_jpeg = jpeg
        await self._send({"type": "conversation.item.create", "item": _user_item([_image_part(jpeg, self.turn_detail)])})

    def _playing(self) -> bool:
        """The last reply's audio is still coming out of the speaker (estimated from its length)."""
        return self._item_id is not None and (time.monotonic() - self._item_first_audio) * 1000.0 < self._item_audio_ms

    async def _truncate(self) -> None:
        """Tell the model how much of its reply was actually heard."""
        if self._item_id is None:
            return
        played = min(self._item_audio_ms, (time.monotonic() - self._item_first_audio) * 1000.0)
        await self._send(
            {"type": "conversation.item.truncate", "item_id": self._item_id, "content_index": 0, "audio_end_ms": max(0, int(played))}
        )
        self._item_id = None  # truncated once; later speech in this turn isn't a new interruption

    async def _keep_alive(self) -> None:
        """Semantic VAD can take seconds to decide a turn is over; that is not silence."""
        while not self._closed:
            await asyncio.sleep(1.0)
            if self._user_turn_open:
                self._emit("user_activity")

    # --- inputs ----------------------------------------------------------
    async def send_audio(self, pcm: bytes) -> None:
        pcm24 = self._upsample.process(pcm)
        if pcm24:
            await self._send({"type": "input_audio_buffer.append", "audio": base64.b64encode(pcm24).decode("ascii")})

    async def send_frame(self, jpeg: bytes) -> None:
        self.latest_jpeg = jpeg  # sent at the next speech start / commit

    async def send_text(self, text: str) -> None:
        if self._responding:
            await self._send({"type": "response.cancel"})
        await self._respond(text)

    async def cut_in(self, instruction: str) -> None:
        """The visitor hasn't paused: close their turn now so the reply hears what they said."""
        if self._responding:
            return  # already answering
        if self._user_turn_open:
            self._pending_instruction = instruction
            await self._send({"type": "input_audio_buffer.commit"})
        else:
            await self._respond(instruction)

    async def add_note(self, text: str) -> None:
        await self._send(
            {"type": "conversation.item.create", "item": {"type": "message", "role": "system", "content": [{"type": "input_text", "text": text}]}}
        )

    async def close(self) -> None:
        await super().close()
        for task in (self._rx, self._heartbeat):
            if task is not None:
                task.cancel()
        if self.ws is not None:
            try:
                await self.ws.close()
            except Exception:
                pass
        self.ws = None


def _user_item(content: list) -> dict:
    return {"type": "message", "role": "user", "content": content}
