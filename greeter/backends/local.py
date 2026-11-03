"""Offline fallback: Silero VAD -> Whisper/Parakeet -> Ollama VLM (qwen3.5:4b) -> Kokoro TTS.

Runs entirely on the laptop (tuned for an Apple-silicon Mac, works elsewhere).
Models load once on the first visit and stay in memory; audio, frames and the
text history live only in memory for the current visit.

Optional dependencies (``requirements/local.txt``): silero-vad, faster-whisper
or parakeet-mlx, ollama, kokoro (Python < 3.13, needs espeak-ng).
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import List, Optional

import numpy as np

from greeter.audio import float_to_int16, int16_to_pcm, pcm_to_int16
from greeter.backends.base import Backend
from greeter.dialogue.prompts import SYSTEM_PROMPT

log = logging.getLogger(__name__)

VAD_CHUNK = 512  # Silero VAD at 16 kHz takes exactly 512-sample chunks
KOKORO_RATE = 24000
SENTENCE_END = re.compile(r"(?<=[.!?])\s+")

_models = {}


def _vad_model():
    if "vad" not in _models:
        from silero_vad import load_silero_vad

        _models["vad"] = load_silero_vad()
    return _models["vad"]


class _WhisperASR:
    def __init__(self, model: str) -> None:
        from faster_whisper import WhisperModel

        self.model = WhisperModel(model, device="auto", compute_type="int8")

    def transcribe(self, audio: np.ndarray) -> str:
        segments, _ = self.model.transcribe(audio, language="en", beam_size=1, vad_filter=False)
        return " ".join(s.text.strip() for s in segments).strip()


class _ParakeetASR:
    """parakeet-mlx (Apple silicon). Transcribes from memory: no temporary WAV files."""

    def __init__(self, model: str) -> None:
        from parakeet_mlx import from_pretrained

        self.model = from_pretrained(model)

    def transcribe(self, audio: np.ndarray) -> str:
        import mlx.core as mx
        from parakeet_mlx.audio import get_logmel

        mel = get_logmel(mx.array(audio), self.model.preprocessor_config)
        return self.model.generate(mel)[0].text.strip()


def _asr(kind: str, model: Optional[str]):
    key = ("asr", kind, model)
    if key not in _models:
        if kind == "parakeet":
            _models[key] = _ParakeetASR(model or "mlx-community/parakeet-tdt-0.6b-v3")
        else:
            _models[key] = _WhisperASR(model or "small.en")
    return _models[key]


def _tts(lang_code: str):
    key = ("tts", lang_code)
    if key not in _models:
        from kokoro import KPipeline

        _models[key] = KPipeline(lang_code=lang_code)
    return _models[key]


def _synthesise(text: str, voice: str, lang_code: str) -> bytes:
    pipeline = _tts(lang_code)
    chunks = []
    for _, _, audio in pipeline(text, voice=voice, speed=1.0):
        if audio is None:
            continue
        audio = audio.detach().cpu().numpy() if hasattr(audio, "detach") else np.asarray(audio)
        chunks.append(float_to_int16(audio.astype(np.float32)))
    return int16_to_pcm(np.concatenate(chunks)) if chunks else b""


class LocalBackend(Backend):
    name = "local"

    def __init__(
        self,
        vlm_model: str = "qwen3.5:4b",
        ollama_host: Optional[str] = None,
        asr: str = "whisper",
        asr_model: Optional[str] = None,
        voice: str = "bf_emma",
        lang_code: str = "b",  # Kokoro British English
        system_prompt: str = SYSTEM_PROMPT,
        vad_threshold: float = 0.5,
        min_silence_ms: int = 600,
    ) -> None:
        super().__init__()
        self.vlm_model, self.ollama_host = vlm_model, ollama_host
        self.asr_kind, self.asr_model = asr, asr_model
        self.voice, self.lang_code = voice, lang_code
        self.vad_threshold, self.min_silence_ms = vad_threshold, min_silence_ms
        self.history: List[dict] = [{"role": "system", "content": system_prompt}]
        self.latest_jpeg: Optional[bytes] = None
        self._pending = np.zeros(0, dtype=np.float32)
        self._utterance: List[np.ndarray] = []
        self._preroll: List[np.ndarray] = []
        self._in_speech = False
        self._busy = False
        self._tasks = set()
        self._vad = None
        self._client = None

    def _spawn(self, coro) -> None:
        task = asyncio.ensure_future(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def open(self, jpeg: Optional[bytes], note: str) -> None:
        import ollama
        from silero_vad import VADIterator

        loop = asyncio.get_running_loop()
        # load (or reuse) every model before the invitation so the first reply isn't slow
        await loop.run_in_executor(None, _vad_model)
        await loop.run_in_executor(None, _asr, self.asr_kind, self.asr_model)
        await loop.run_in_executor(None, _tts, self.lang_code)
        self._vad = VADIterator(
            _vad_model(),
            threshold=self.vad_threshold,
            sampling_rate=16000,
            min_silence_duration_ms=self.min_silence_ms,
            speech_pad_ms=100,
        )
        self._client = ollama.AsyncClient(host=self.ollama_host)
        self.latest_jpeg = jpeg
        if note:
            self.history.append({"role": "user", "content": note})

    async def speak_opener(self) -> None:
        if self._opener_request is not None:
            jpeg, instruction = self._opener_request
            self._spawn(self._respond(instruction, jpeg))

    async def begin(self, instruction: Optional[str]) -> None:
        if instruction:
            self._spawn(self._respond(instruction, self.latest_jpeg))

    # --- listening -----------------------------------------------------------
    async def send_audio(self, pcm: bytes) -> None:
        import torch

        samples = pcm_to_int16(pcm).astype(np.float32) / 32768.0
        self._pending = np.concatenate([self._pending, samples])
        while self._pending.size >= VAD_CHUNK:
            chunk, self._pending = self._pending[:VAD_CHUNK], self._pending[VAD_CHUNK:]
            event = self._vad(torch.from_numpy(chunk))
            if self._in_speech:
                self._utterance.append(chunk)
                self._emit("user_activity")
            else:
                self._preroll = (self._preroll + [chunk])[-10:]  # ~0.3 s before the VAD fires
            if event and "start" in event and not self._in_speech:
                self._in_speech = True
                self._utterance = list(self._preroll)
                self._emit("user_activity")
            elif event and "end" in event and self._in_speech:
                self._in_speech = False
                self._emit("user_turn_end")
                audio, self._utterance = np.concatenate(self._utterance), []
                if self._busy:
                    log.info("ignoring speech while the robot is still answering")
                else:
                    self._spawn(self._handle_utterance(audio))

    async def _handle_utterance(self, audio: np.ndarray) -> None:
        loop = asyncio.get_running_loop()
        self._busy = True
        try:
            text = await loop.run_in_executor(None, _asr(self.asr_kind, self.asr_model).transcribe, audio)
        except Exception as exc:
            log.warning("ASR failed: %s", exc)
            self._busy = False
            return
        if not text:
            self._busy = False
            return
        self._emit("user_text", text)
        await self._respond(text, self.latest_jpeg)

    # --- answering -----------------------------------------------------------
    async def _speak(self, sentence: str) -> None:
        sentence = sentence.strip()
        if not sentence:
            return
        loop = asyncio.get_running_loop()
        pcm = await loop.run_in_executor(None, _synthesise, sentence, self.voice, self.lang_code)
        self._emit("bot_text", sentence + " ")
        step = KOKORO_RATE // 5 * 2  # 200 ms chunks
        for i in range(0, len(pcm), step):
            self._emit("audio", pcm[i : i + step], KOKORO_RATE)

    async def _respond(self, user_text: str, jpeg: Optional[bytes]) -> None:
        self._busy = True
        message = {"role": "user", "content": user_text}
        if jpeg:
            message["images"] = [jpeg]  # only the current frame, never kept in history
        reply, pending = "", ""
        try:
            stream = await self._client.chat(
                model=self.vlm_model,
                messages=self.history + [message],
                stream=True,
                think=False,  # qwen3.5 is a thinking model; we want the answer, fast
                options={"num_predict": 120, "temperature": 0.7},
            )
            async for part in stream:
                piece = part.message.content or ""
                reply += piece
                pending += piece
                *sentences, pending = SENTENCE_END.split(pending)
                for sentence in sentences:  # speak sentence by sentence to cut latency
                    await self._speak(sentence)
            await self._speak(pending)
            self.history += [{"role": "user", "content": user_text}, {"role": "assistant", "content": reply}]
            self._emit("turn_complete")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("local cascade failed: %s", exc)
            self._emit("error", str(exc))
        finally:
            self._busy = False

    async def send_frame(self, jpeg: bytes) -> None:
        self.latest_jpeg = jpeg

    async def send_text(self, text: str) -> None:
        self._spawn(self._respond(text, self.latest_jpeg))

    async def close(self) -> None:
        for task in list(self._tasks):
            task.cancel()
        self.history, self.latest_jpeg, self._utterance = [], None, []
        await super().close()
