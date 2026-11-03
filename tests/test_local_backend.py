"""LocalBackend glue (VAD segmentation, ASR, streamed VLM, sentence-wise TTS) with stub models.

The real models (Silero, faster-whisper, Ollama, Kokoro) are replaced by tiny
fakes in ``sys.modules``, so this runs anywhere torch is installed.
"""

import asyncio
import sys
import types

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from greeter.audio import int16_to_pcm  # noqa: E402


class FakeVAD:
    """Starts on the first loud 512-sample chunk, ends after 5 quiet ones."""

    def __init__(self, model, threshold, sampling_rate, min_silence_duration_ms, speech_pad_ms):
        self.speaking, self.quiet, self.n = False, 0, 0

    def __call__(self, chunk):
        self.n += 512
        loud = float(chunk.abs().mean()) > 0.05
        if loud and not self.speaking:
            self.speaking, self.quiet = True, 0
            return {"start": self.n}
        if self.speaking and not loud:
            self.quiet += 1
            if self.quiet >= 5:
                self.speaking = False
                return {"end": self.n}
        return None


class FakeWhisper:
    calls = []

    def __init__(self, model, device, compute_type):
        pass

    def transcribe(self, audio, language, beam_size, vad_filter):
        FakeWhisper.calls.append(audio)
        return [types.SimpleNamespace(text=" hello robot ")], None


class FakeKokoro:
    def __init__(self, lang_code):
        self.lang_code = lang_code

    def __call__(self, text, voice, speed):
        yield None, None, torch.full((2400,), 0.1)  # 0.1 s at 24 kHz per sentence


class FakeOllama:
    requests = []
    reply = ["Hello there", ". I like your", " green top! ", "What brings", " you here?"]

    def __init__(self, host=None):
        pass

    async def chat(self, model, messages, stream, think, options):
        FakeOllama.requests.append({"model": model, "messages": messages, "think": think})

        async def gen():
            for piece in FakeOllama.reply:
                yield types.SimpleNamespace(message=types.SimpleNamespace(content=piece))

        return gen()


@pytest.fixture
def local(monkeypatch):
    monkeypatch.setitem(sys.modules, "silero_vad", types.SimpleNamespace(load_silero_vad=lambda: object(), VADIterator=FakeVAD))
    monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=FakeWhisper))
    monkeypatch.setitem(sys.modules, "kokoro", types.SimpleNamespace(KPipeline=FakeKokoro))
    monkeypatch.setitem(sys.modules, "ollama", types.SimpleNamespace(AsyncClient=FakeOllama))
    from greeter.backends import local as local_mod

    local_mod._models.clear()
    FakeWhisper.calls.clear()
    FakeOllama.requests.clear()
    yield local_mod
    local_mod._models.clear()


async def drain_until(backend, kind, timeout=3.0):
    events = []

    async def collect():
        async for ev in backend.events():
            events.append(ev)
            if ev.kind == kind:
                return

    await asyncio.wait_for(collect(), timeout)
    return events


def test_greeting_streams_sentences_through_tts(local):
    async def main():
        b = local.LocalBackend()
        await b.open(b"frame0", "")
        await b.prepare_opener(b"frame0", "greet them")
        await b.speak_opener()  # no out-of-band generation locally: the invitation is spoken live
        events = await drain_until(b, "turn_complete")
        await b.close()
        return b, events

    b, events = asyncio.run(main())
    said = [e.data.strip() for e in events if e.kind == "bot_text"]
    assert said == ["Hello there.", "I like your green top!", "What brings you here?"]
    audio = [e for e in events if e.kind == "audio"]
    assert audio and all(e.rate == 24000 for e in audio)
    assert sum(len(e.data) for e in audio) == 3 * 2400 * 2
    req = FakeOllama.requests[0]
    assert req["model"] == "qwen3.5:4b" and req["think"] is False
    assert req["messages"][-1] == {"role": "user", "content": "greet them", "images": [b"frame0"]}
    assert req["messages"][0]["role"] == "system"


def test_visitor_utterance_is_transcribed_and_answered(local):
    loud = int16_to_pcm(np.full(512 * 8, 8000, dtype=np.int16))
    quiet = int16_to_pcm(np.zeros(512 * 8, dtype=np.int16))

    async def main():
        b = local.LocalBackend()
        await b.open(b"frame0", "")
        await b.begin("greet them")
        await drain_until(b, "turn_complete")
        await b.send_frame(b"frame1")
        for i in range(0, len(loud), 1000):  # arbitrary chunking, not multiples of 512
            await b.send_audio(loud[i : i + 1000])
        for i in range(0, len(quiet), 1000):
            await b.send_audio(quiet[i : i + 1000])
        events = await drain_until(b, "turn_complete")
        history = list(b.history)
        await b.close()
        return events, history

    events, history = asyncio.run(main())
    kinds = [e.kind for e in events]
    assert "user_activity" in kinds and "user_turn_end" in kinds
    assert ("user_text", "hello robot") in [(e.kind, e.data) for e in events]
    utterance = FakeWhisper.calls[0]
    assert utterance.dtype == np.float32 and 512 * 8 <= utterance.size <= 512 * 16
    # the newest frame goes with the question, and no image is kept in the history
    assert FakeOllama.requests[-1]["messages"][-1]["images"] == [b"frame1"]
    assert all("images" not in m for m in history)
    assert [m["role"] for m in history] == ["system", "user", "assistant", "user", "assistant"]


def test_close_forgets_everything(local):
    async def main():
        b = local.LocalBackend()
        await b.open(b"frame0", "(scene note)")
        await b.begin("greet them")
        await drain_until(b, "turn_complete")
        await b.close()
        return b

    b = asyncio.run(main())
    assert b.history == [] and b.latest_jpeg is None
