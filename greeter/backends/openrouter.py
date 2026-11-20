"""OpenRouter cascade: one omni model hears the visitor and sees the camera, then text to speech.

OpenRouter has no realtime voice connection, so each turn is a request:

    visitor stops talking (energy detector, as the canned backend)
    -> the visitor's audio + the latest camera frame go to an omni model (default Qwen3.8 Omni Flash),
       which streams back a text reply
    -> each finished sentence goes to a text-to-speech model on OpenRouter (default Kokoro)
       and is played while the next one is made

No new Python packages (urllib only), so it runs on the Jetson's Python 3.8. If the
speech model fails, sentences are spoken with the robot's espeak-ng instead.

Half duplex: the visitor cannot interrupt a reply. Expect 1.5-3 s from the end of the visitor's
turn to the robot's first word; every turn's timings are logged.

    python -m greeter.backends.openrouter --wav question.wav [--jpeg view.jpg] [--out reply.wav]

runs one turn from a recording and prints the timings (needs OPENROUTER_API_KEY).
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import os
import re
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import wave
from pathlib import Path
from typing import AsyncIterator, Dict, Iterator, List, Optional, Tuple

from greeter.audio import rms_dbfs
from greeter.backends.base import Backend
from greeter.backends.scripted import _EnergyEars
from greeter.dialogue.prompts import SYSTEM_PROMPT

log = logging.getLogger(__name__)

API = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "qwen/qwen3.8-omni-flash"
DEFAULT_TTS = "hexgrad/kokoro-82m"
DEFAULT_VOICE = "bf_emma"
DOWN_STATUS = (401, 402, 403)  # bad key, out of credit, forbidden: no use retrying today
SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
KEEP_AUDIO_TURNS = 3   # earlier visitor turns stay in the history as a short note only
MAX_TURN_S = 30.0      # longest visitor turn sent (the dialogue cuts in long before)
PREROLL_CHUNKS = 10    # audio kept from just before speech was detected
HEARD_OPEN, HEARD_CLOSE = "«", "»"   # the model is asked to put what it heard in << >>

TURN_RULES = (
    "You hear the visitor through the robot's microphone; their latest speech is attached as audio, "
    "with the robot's current camera view. Start every reply with what you heard, in "
    + HEARD_OPEN + "double angle quotes" + HEARD_CLOSE + ", then answer out loud in one or two short "
    "spoken sentences. If you could not make it out, put " + HEARD_OPEN + "?" + HEARD_CLOSE
    + " and ask them to say it again."
)


def wav_bytes(pcm: bytes, rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


def read_wav(data: bytes) -> Tuple[bytes, int]:
    """(mono s16le, rate) from WAV bytes; ValueError if it is not 16-bit PCM WAV."""
    if data[:4] != b"RIFF":
        raise ValueError("not a WAV file")
    with wave.open(io.BytesIO(data), "rb") as w:
        if w.getsampwidth() != 2:
            raise ValueError("not 16-bit PCM")
        rate, channels = w.getframerate(), w.getnchannels()
        frames = w.readframes(w.getnframes())
    if channels > 1:
        import numpy as np

        a = np.frombuffer(frames, dtype="<i2")
        frames = a[: len(a) // channels * channels].reshape(-1, channels).mean(axis=1).astype("<i2").tobytes()
    return frames, rate


def split_heard(text: str) -> Tuple[Optional[str], str, bool]:
    """(heard, reply, complete) from the start of a reply that may begin with <<heard>>.
    ``complete`` is False while the opening quote has come but the closing one hasn't."""
    stripped = text.lstrip()
    if not stripped.startswith(HEARD_OPEN):
        return None, text, True
    end = stripped.find(HEARD_CLOSE)
    if end < 0:
        return None, "", False
    return stripped[1:end].strip(), stripped[end + 1 :].lstrip(), True


class OpenRouterError(RuntimeError):
    def __init__(self, status: int, message: str) -> None:
        super().__init__("OpenRouter HTTP %d: %s" % (status, message))
        self.status = status


class OpenRouterClient:
    """The two HTTP calls, synchronous (run them in an executor)."""

    def __init__(self, key: str, timeout: float = 30.0) -> None:
        self.key, self.timeout = key, timeout

    def _request(self, path: str, body: dict):
        req = urllib.request.Request(
            API + path,
            data=json.dumps(body).encode(),
            headers={"Authorization": "Bearer " + self.key, "Content-Type": "application/json",
                     "X-Title": "G1 open day greeter"},
        )
        try:
            return urllib.request.urlopen(req, timeout=self.timeout)
        except urllib.error.HTTPError as exc:
            detail = exc.read()[:300].decode("utf-8", "replace")
            raise OpenRouterError(exc.code, detail) from None

    def stream_chat(self, model: str, messages: List[dict], max_tokens: int = 160) -> Iterator[Tuple[str, Optional[dict]]]:
        """Yields (text piece, usage or None) as the reply streams in."""
        body = {"model": model, "messages": messages, "stream": True, "max_tokens": max_tokens,
                "temperature": 0.7, "usage": {"include": True}}
        with self._request("/chat/completions", body) as resp:
            for raw in resp:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    return
                try:
                    chunk = json.loads(payload)
                except ValueError:
                    continue
                if "error" in chunk:
                    err = chunk["error"]
                    raise OpenRouterError(int(err.get("code") or 500), str(err.get("message", err)))
                piece = ""
                for choice in chunk.get("choices") or []:
                    piece += (choice.get("delta") or {}).get("content") or ""
                yield piece, chunk.get("usage")

    def speech(self, model: str, text: str, voice: str) -> bytes:
        body = {"model": model, "input": text, "voice": voice, "response_format": "wav"}
        with self._request("/audio/speech", body) as resp:
            return resp.read()


def espeak(text: str) -> Tuple[bytes, int]:
    """Fallback speech on the robot itself (espeak-ng, or say on a Mac)."""
    from greeter.clips import offline_command

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "line.wav"
        cmd = offline_command(text, out)
        if cmd is None:
            raise RuntimeError("no offline speech program (espeak-ng)")
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return read_wav(out.read_bytes())


class OpenRouterBackend(Backend):
    name = "openrouter"
    supports_opener = True

    def __init__(self, key: Optional[str] = None, model: str = DEFAULT_MODEL, tts_model: str = DEFAULT_TTS,
                 voice: str = DEFAULT_VOICE, system_prompt: str = SYSTEM_PROMPT, client=None) -> None:
        super().__init__()
        self.model, self.tts_model, self.voice = model, tts_model, voice
        self.client = client or OpenRouterClient(key or os.environ.get("OPENROUTER_API_KEY", ""))
        self.history: List[dict] = [{"role": "system", "content": system_prompt + "\n\n" + TURN_RULES}]
        self.notes: List[str] = []
        self.latest_jpeg: Optional[bytes] = None
        self._ears = _EnergyEars()
        self._utterance: List[bytes] = []
        self._preroll: List[bytes] = []
        self._collecting = False
        self._busy = False
        self._tts_ok = True
        self._turn_end_at = 0.0
        self._tasks = set()

    # --- plumbing ------------------------------------------------------------
    def _spawn(self, coro) -> None:
        task = asyncio.ensure_future(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _stream(self, messages: List[dict]) -> AsyncIterator[Tuple[str, Optional[dict]]]:
        loop = asyncio.get_running_loop()
        queue: "asyncio.Queue[tuple]" = asyncio.Queue()

        def work() -> None:
            try:
                for piece, usage in self.client.stream_chat(self.model, messages):
                    loop.call_soon_threadsafe(queue.put_nowait, ("piece", piece, usage))
                loop.call_soon_threadsafe(queue.put_nowait, ("end", None, None))
            except Exception as exc:  # handed to the event loop below
                loop.call_soon_threadsafe(queue.put_nowait, ("error", exc, None))

        loop.run_in_executor(None, work)
        while True:
            kind, a, b = await queue.get()
            if kind == "end":
                return
            if kind == "error":
                raise a
            yield a, b

    async def _synth(self, text: str) -> Tuple[bytes, int]:
        loop = asyncio.get_running_loop()
        if self._tts_ok:
            try:
                data = await loop.run_in_executor(None, self.client.speech, self.tts_model, text, self.voice)
                return read_wav(data)
            except Exception as exc:
                log.warning("OpenRouter speech failed (%s): using espeak-ng from now on", exc)
                self._tts_ok = False
        return await loop.run_in_executor(None, espeak, text)

    def _failed(self, exc: Exception) -> None:
        if isinstance(exc, OpenRouterError) and exc.status in DOWN_STATUS:
            self._emit("provider_down", str(exc))
        else:
            self._emit("error", str(exc))

    def _message(self, text: Optional[str], audio: Optional[bytes], jpeg: Optional[bytes]) -> dict:
        content: List[dict] = []
        if audio:
            content.append({"type": "input_audio", "input_audio": {"data": base64.b64encode(wav_bytes(audio)).decode(), "format": "wav"}})
        if jpeg:
            content.append({"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(jpeg).decode()}})
        content.append({"type": "text", "text": text or "(The visitor spoke: audio attached, with the camera view.)"})
        return {"role": "user", "content": content}

    def _request_messages(self, message: dict) -> List[dict]:
        notes = [{"role": "system", "content": n} for n in self.notes]
        self.notes = []
        return self.history + notes + [message]

    def _remember(self, message: dict, reply: str, heard: Optional[str]) -> None:
        """History keeps text only, except the last few visitor turns' audio."""
        self.history += [message, {"role": "assistant", "content": reply}]
        audio_turns = [m for m in self.history if m["role"] == "user" and isinstance(m["content"], list)
                       and any(p.get("type") == "input_audio" for p in m["content"])]
        for old in audio_turns[:-KEEP_AUDIO_TURNS]:
            old["content"] = [{"type": "text", "text": "(The visitor said: %s)" % (heard or "something")}
                              if p.get("type") == "input_audio" else p for p in old["content"] if p.get("type") != "image_url"]
        for m in self.history[:-2]:  # images only ever go with the current turn
            if isinstance(m.get("content"), list):
                m["content"] = [p for p in m["content"] if p.get("type") != "image_url"]

    # --- the conversation ----------------------------------------------------
    async def open(self, jpeg: Optional[bytes], note: str) -> None:
        self.latest_jpeg = jpeg
        if note:
            self.notes.append(note)

    async def prepare_opener(self, jpeg: bytes, instruction: str) -> None:
        self._opener_request = (jpeg, instruction)
        self._spawn(self._make_opener(jpeg, instruction))

    async def _make_opener(self, jpeg: Optional[bytes], instruction: str) -> None:
        text = ""
        try:
            async for piece, usage in self._stream(self._request_messages(self._message(instruction, None, jpeg))):
                text += piece
                if usage:
                    self._emit_usage(usage)
            _, text, _ = split_heard(text)
            text = text.strip()
            pcm, rate = await self._synth(text) if text else (b"", 16000)
            self._emit("opener_ready", {"pcm": pcm, "rate": rate, "text": text})
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("opener failed: %s", exc)
            self._failed(exc)

    async def commit_opener(self, text: str) -> None:
        if text:
            self.history.append({"role": "assistant", "content": text})

    async def begin(self, instruction: Optional[str]) -> None:
        if instruction:
            self._spawn(self._respond(self._message(instruction, None, self.latest_jpeg)))

    async def send_text(self, text: str) -> None:
        self._spawn(self._respond(self._message(text, None, self.latest_jpeg)))

    async def add_note(self, text: str) -> None:
        self.notes.append(text)

    async def send_frame(self, jpeg: bytes) -> None:
        self.latest_jpeg = jpeg

    async def send_audio(self, pcm: bytes) -> None:
        if self._busy:  # half duplex: the robot is answering
            self._collecting, self._utterance = False, []
            return
        loud = rms_dbfs(pcm) > self._ears.speech_dbfs
        if not self._collecting:
            self._preroll = (self._preroll + [pcm])[-PREROLL_CHUNKS:]
            if loud:
                self._collecting, self._utterance = True, list(self._preroll)
        else:
            self._utterance.append(pcm)
        heard = self._ears.feed(pcm)
        if heard == "speaking":
            self._emit("user_activity")
        elif heard == "end" and self._collecting:
            audio = b"".join(self._utterance)[-int(MAX_TURN_S * 32000):]
            self._collecting, self._utterance, self._preroll = False, [], []
            self._turn_end_at = time.monotonic()
            self._emit("user_turn_end")
            self._spawn(self._respond(self._message(None, audio, self.latest_jpeg)))

    async def _respond(self, message: dict) -> None:
        self._busy = True
        start = self._turn_end_at if self._turn_end_at else time.monotonic()
        self._turn_end_at = 0.0
        text, spoken, heard, first_word, first_audio = "", "", None, None, None
        try:
            async for piece, usage in self._stream(self._request_messages(message)):
                if usage:
                    self._emit_usage(usage)
                if piece and first_word is None:
                    first_word = time.monotonic() - start
                text += piece
                h, body, complete = split_heard(text)
                if not complete:
                    continue
                if h is not None and heard is None:
                    heard = h
                    self._emit("user_text", h)
                *sentences, _rest = SENTENCE_END.split(body[len(spoken):])
                for sentence in sentences:
                    first_audio = await self._say(sentence, start, first_audio)
                    spoken += sentence + " "
                    spoken = body[: len(spoken)] if body.startswith(spoken.strip()) else spoken
            _, body, _ = split_heard(text)
            rest = body[len(spoken):].strip() if body.startswith(spoken.strip()) else body.strip()
            if rest:
                first_audio = await self._say(rest, start, first_audio)
            self._remember(message, body.strip(), heard)
            log.info("openrouter turn: first words after %.2f s, first audio after %.2f s",
                     first_word or -1, first_audio or -1)
            self._emit("turn_complete")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("openrouter turn failed: %s", exc)
            self._failed(exc)
        finally:
            self._busy = False

    async def _say(self, sentence: str, start: float, first_audio: Optional[float]) -> Optional[float]:
        sentence = sentence.strip()
        if not sentence:
            return first_audio
        pcm, rate = await self._synth(sentence)
        self._emit("bot_text", sentence + " ")
        self._emit("audio", pcm, rate)
        return first_audio if first_audio is not None else time.monotonic() - start

    def _emit_usage(self, usage: Dict) -> None:
        self._emit("usage", {"model": "openrouter:" + self.model, "cost_usd": float(usage.get("cost") or 0.0),
                             "tokens": int(usage.get("total_tokens") or 0)})

    async def close(self) -> None:
        for task in list(self._tasks):
            task.cancel()
        self.history, self.latest_jpeg, self._utterance = [], None, []
        await super().close()


async def _one_turn(args) -> None:
    pcm, rate = read_wav(Path(args.wav).read_bytes())
    if rate != 16000:
        import audioop

        pcm, _ = audioop.ratecv(pcm, 2, 1, rate, 16000, None)
    jpeg = Path(args.jpeg).read_bytes() if args.jpeg else None
    backend = OpenRouterBackend(model=args.model, tts_model=args.tts, voice=args.voice)
    out = bytearray()
    out_rate = 0
    await backend.open(jpeg, "")
    backend._turn_end_at = time.monotonic()
    t0 = backend._turn_end_at
    task = asyncio.ensure_future(backend._respond(backend._message(None, pcm, jpeg)))
    async for event in backend.events():
        if event.kind == "user_text":
            print("heard:   %s" % event.data)
        elif event.kind == "bot_text":
            print("reply:   %s   (%.2f s)" % (event.data.strip(), time.monotonic() - t0))
        elif event.kind == "audio":
            out += event.data
            out_rate = event.rate
        elif event.kind == "usage":
            print("cost:    $%.5f, %d tokens" % (event.data["cost_usd"], event.data["tokens"]))
        elif event.kind in ("turn_complete", "error", "provider_down"):
            if event.kind != "turn_complete":
                print("%s: %s" % (event.kind, event.data))
            break
    await task
    print("total:   %.2f s" % (time.monotonic() - t0))
    if args.out and out:
        Path(args.out).write_bytes(wav_bytes(bytes(out), out_rate))
        print("saved the spoken reply to %s" % args.out)
    await backend.close()


def main(argv=None) -> None:
    import argparse

    from greeter.envfile import load_env_file

    load_env_file()
    p = argparse.ArgumentParser(prog="python -m greeter.backends.openrouter", description="one OpenRouter turn from a recording, with timings")
    p.add_argument("--wav", required=True, help="the visitor's speech (16-bit WAV)")
    p.add_argument("--jpeg", help="a camera frame to send with it")
    p.add_argument("--out", help="save the robot's spoken reply here")
    p.add_argument("--model", default=os.environ.get("GREETER_OPENROUTER_MODEL", DEFAULT_MODEL))
    p.add_argument("--tts", default=os.environ.get("GREETER_OPENROUTER_TTS", DEFAULT_TTS))
    p.add_argument("--voice", default=os.environ.get("GREETER_OPENROUTER_VOICE", DEFAULT_VOICE))
    args = p.parse_args(argv)
    if not os.environ.get("OPENROUTER_API_KEY"):
        raise SystemExit("OPENROUTER_API_KEY is not set (scripts/set-api-key.sh unitree@<robot> OPENROUTER_API_KEY)")
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    asyncio.run(_one_turn(args))


if __name__ == "__main__":
    main()
