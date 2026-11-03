"""Gemini Live backend (google-genai SDK, ``gemini-3.8-live``; needs Python 3.10+).

Audio in: 16 kHz s16le. Audio out: 24 kHz s16le (the runner resamples to 16 kHz).
Video: JPEG frames as they arrive (the robot streams 2 fps while talking).
The invitation is spoken live: ``send_client_content(turn_complete=True)`` with
the frame and the instruction. Context window compression (no 2-minute cap)
and session resumption (survives the ~10 min connection limit and drops) are on.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Optional

from greeter.backends.base import Backend, ProviderDown
from greeter.backends.spend import is_provider_down
from greeter.dialogue.prompts import SYSTEM_PROMPT

log = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-3.8-live"
OUTPUT_RATE = 24000


def _rate_from_mime(mime: Optional[str], default: int = OUTPUT_RATE) -> int:
    match = re.search(r"rate=(\d+)", mime or "")
    return int(match.group(1)) if match else default


class GeminiBackend(Backend):
    name = "gemini"

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        voice: str = "Puck",
        system_prompt: str = SYSTEM_PROMPT,
        api_key: Optional[str] = None,
        silence_ms: int = 700,
        media_resolution: Optional[str] = None,
        nudge: bool = True,
    ) -> None:
        super().__init__()
        self.model, self.voice, self.system_prompt = model, voice, system_prompt
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        self.silence_ms, self.media_resolution, self.nudge = silence_ms, media_resolution, nudge
        self.name = "gemini:" + model
        self._cm = None
        self._session = None
        self._rx: Optional[asyncio.Task] = None
        self._handle: Optional[str] = None  # session resumption handle
        self.note = ""

    def build_config(self):
        from google.genai import types

        kwargs = {}
        if self.media_resolution:
            kwargs["media_resolution"] = getattr(types.MediaResolution, "MEDIA_RESOLUTION_" + self.media_resolution.upper())
        return types.LiveConnectConfig(
            response_modalities=["AUDIO"],  # the only modality gemini-3.8-live offers
            system_instruction=self.system_prompt,
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=self.voice))
            ),
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
            realtime_input_config=types.RealtimeInputConfig(
                automatic_activity_detection=types.AutomaticActivityDetection(
                    disabled=False,
                    start_of_speech_sensitivity=types.StartSensitivity.START_SENSITIVITY_LOW,  # noisy hall
                    end_of_speech_sensitivity=types.EndSensitivity.END_SENSITIVITY_LOW,
                    prefix_padding_ms=20,
                    silence_duration_ms=self.silence_ms,
                ),
            ),
            context_window_compression=types.ContextWindowCompressionConfig(
                trigger_tokens=25600, sliding_window=types.SlidingWindow(target_tokens=12800)
            ),
            session_resumption=types.SessionResumptionConfig(handle=self._handle),
            **kwargs,
        )

    async def _connect(self) -> None:
        from google import genai

        if not self.api_key:
            raise ProviderDown("GEMINI_API_KEY is not set")
        client = genai.Client(api_key=self.api_key)
        self._cm = client.aio.live.connect(model=self.model, config=self.build_config())
        try:
            self._session = await self._cm.__aenter__()
        except Exception as exc:
            if is_provider_down(None, str(exc)) or "401" in str(exc) or "403" in str(exc) or "429" in str(exc):
                raise ProviderDown(str(exc)) from exc
            raise

    async def open(self, jpeg: Optional[bytes], note: str) -> None:
        self.note = note
        await self._connect()
        self._rx = asyncio.ensure_future(self._receive())
        log.info("gemini session warm (%s, voice %s)", self.model, self.voice)

    async def speak_opener(self) -> None:
        """Speak first: frame + instruction as one user turn, turn_complete=True."""
        from google.genai import types

        if self._opener_request is None or self._session is None:
            return
        jpeg, instruction = self._opener_request
        parts = [types.Part.from_bytes(data=jpeg, mime_type="image/jpeg"), types.Part(text=(self.note + "\n" + instruction).strip())]
        await self._session.send_client_content(turns=types.Content(role="user", parts=parts), turn_complete=True)
        if self.nudge:
            # Gemini 3.x will not start inference on client content until some
            # realtime input arrives (same workaround as pipecat's GeminiLiveLLMService)
            await self._session.send_realtime_input(text=" ")

    async def _receive(self) -> None:
        failures = 0
        while not self._closed:
            try:
                got_any = False
                async for msg in self._session.receive():  # ends after every turn
                    got_any, failures = True, 0
                    self._handle_message(msg)
                if not got_any:
                    raise ConnectionError("Gemini Live connection closed")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if self._closed:
                    return
                log.warning("gemini receive failed: %s", exc)
                failures += 1
                if self._handle and failures <= 3 and await self._resume():
                    continue
                self._emit("error", str(exc))
                return

    def _handle_message(self, msg) -> None:
        if msg.go_away is not None:
            log.info("gemini go_away: %s left; will resume", msg.go_away.time_left)
        update = getattr(msg, "session_resumption_update", None)
        if update is not None and update.resumable and update.new_handle:
            self._handle = update.new_handle
        activity = getattr(msg, "voice_activity", None)
        if activity is not None:
            kind = str(getattr(activity, "voice_activity_type", ""))
            self._emit("user_turn_end" if kind.endswith("ACTIVITY_END") else "user_activity")
        sc = msg.server_content
        if sc is None:
            return
        if sc.interim_input_transcription is not None:
            self._emit("user_activity")
        if sc.interrupted:
            self._emit("interrupted")
        if sc.model_turn and sc.model_turn.parts:
            for part in sc.model_turn.parts:
                blob = part.inline_data
                if blob is not None and blob.data:
                    self._emit("audio", blob.data, _rate_from_mime(blob.mime_type))
        if sc.input_transcription and sc.input_transcription.text:
            self._emit("user_text", sc.input_transcription.text)
        if sc.output_transcription and sc.output_transcription.text:
            self._emit("bot_text", sc.output_transcription.text)
        if sc.turn_complete:
            self._emit("turn_complete")

    async def _resume(self) -> bool:
        try:
            if self._cm is not None:
                try:
                    await self._cm.__aexit__(None, None, None)
                except Exception:
                    pass
            await self._connect()
            log.info("gemini session resumed")
            return True
        except Exception as exc:
            log.warning("gemini resume failed: %s", exc)
            return False

    async def _send(self, **kwargs) -> None:
        if self._session is None or self._closed:
            return
        try:
            await self._session.send_realtime_input(**kwargs)
        except Exception as exc:
            if not self._closed:
                log.warning("gemini send failed: %s", exc)

    async def send_audio(self, pcm: bytes) -> None:
        from google.genai import types

        await self._send(audio=types.Blob(data=pcm, mime_type="audio/pcm;rate=16000"))

    async def send_frame(self, jpeg: bytes) -> None:
        from google.genai import types

        await self._send(video=types.Blob(data=jpeg, mime_type="image/jpeg"))

    async def send_text(self, text: str) -> None:
        await self._send(text=text)

    async def close(self) -> None:
        await super().close()
        if self._rx is not None:
            self._rx.cancel()
        if self._cm is not None:
            try:
                await self._cm.__aexit__(None, None, None)
            except Exception as exc:
                log.debug("closing gemini session: %s", exc)
        self._cm = self._session = None
