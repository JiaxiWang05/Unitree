"""OpenRouter cascade with a fake client: no network."""

import asyncio
import io
import math
import struct
import wave

import pytest

from greeter import cli
from greeter.backends import openrouter as orb


def tone(seconds, amp=8000, rate=16000):
    n = int(seconds * rate)
    return struct.pack("<%dh" % n, *(int(amp * math.sin(2 * math.pi * 440 * i / rate)) for i in range(n)))


def wav(seconds=0.2, rate=24000):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(rate)
        w.writeframes(b"\x01\x00" * int(seconds * rate))
    return buf.getvalue()


class FakeClient:
    def __init__(self, pieces, fail=None, tts_fail=False):
        self.pieces, self.fail, self.tts_fail = pieces, fail, tts_fail
        self.requests, self.spoken = [], []

    def stream_chat(self, model, messages, max_tokens=160):
        self.requests.append(messages)
        if self.fail:
            raise self.fail
        for i, p in enumerate(self.pieces):
            yield p, ({"cost": 0.0012, "total_tokens": 900} if i == len(self.pieces) - 1 else None)

    def speech(self, model, text, voice):
        if self.tts_fail:
            raise RuntimeError("no speech")
        self.spoken.append(text)
        return wav()


async def collect(backend, until=("turn_complete", "error", "provider_down", "opener_ready")):
    out = []
    async for e in backend.events():
        out.append(e)
        if e.kind in until:
            return out


def test_turn_hears_answers_sentence_by_sentence():
    async def run():
        client = FakeClient(["«what do", " you do?» I greet", " visitors. Come and", " say hi!"])
        b = orb.OpenRouterBackend(client=client)
        await b.open(b"\xff\xd8jpeg", "")
        for chunk in [tone(0.1)] * 6 + [b"\x00\x00" * 1600] * 12:  # 0.6 s of speech, then silence
            await b.send_audio(chunk)
        events = await collect(b)
        await b.close()
        return client, events

    client, events = asyncio.run(run())
    kinds = [e.kind for e in events]
    assert kinds[0] == "user_activity" and "user_turn_end" in kinds and kinds[-1] == "turn_complete"
    assert [e.data for e in events if e.kind == "user_text"] == ["what do you do?"]
    assert [e.data.strip() for e in events if e.kind == "bot_text"] == ["I greet visitors.", "Come and say hi!"]
    assert client.spoken == ["I greet visitors.", "Come and say hi!"]
    assert all(e.rate == 24000 for e in events if e.kind == "audio")
    assert [e.data["cost_usd"] for e in events if e.kind == "usage"] == [0.0012]
    sent = client.requests[0][-1]["content"]
    assert [p["type"] for p in sent] == ["input_audio", "image_url", "text"]


def test_opener_out_of_band_and_history():
    async def run():
        client = FakeClient(["Hey, love the green jacket!", " Come and say hi."])
        b = orb.OpenRouterBackend(client=client)
        await b.prepare_opener(b"jpg", "Invite them, naming something they wear.")
        events = await collect(b)
        await b.commit_opener(events[-1].data["text"])
        history = list(b.history)
        await b.close()
        return events, history

    events, history = asyncio.run(run())
    ready = events[-1]
    assert ready.kind == "opener_ready" and ready.data["rate"] == 24000
    assert ready.data["text"] == "Hey, love the green jacket! Come and say hi."
    assert history[-1] == {"role": "assistant", "content": ready.data["text"]}


def test_out_of_credit_switches_provider():
    async def run():
        b = orb.OpenRouterBackend(client=FakeClient([], fail=orb.OpenRouterError(402, "insufficient credits")))
        await b.send_text("hello")
        events = await collect(b)
        await b.close()
        return events

    assert asyncio.run(run())[-1].kind == "provider_down"


def test_speech_falls_back_to_espeak(monkeypatch):
    monkeypatch.setattr(orb, "espeak", lambda text: (b"\x02\x00" * 160, 22050))

    async def run():
        b = orb.OpenRouterBackend(client=FakeClient(["Hello there."], tts_fail=True))
        await b.send_text("greet")
        events = await collect(b)
        await b.close()
        return events

    audio = [e for e in asyncio.run(run()) if e.kind == "audio"]
    assert audio and audio[0].rate == 22050


def test_split_heard():
    assert orb.split_heard("«hi» Hello.") == ("hi", "Hello.", True)
    assert orb.split_heard("  «half") == (None, "", False)
    assert orb.split_heard("Hello.") == (None, "Hello.", True)


def test_cli_openrouter_needs_its_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(SystemExit) as exc:
        cli.providers(cli.parse_args(["--backend", "openrouter", "--env-file", "/nonexistent"]))
    assert "OPENROUTER_API_KEY" in str(exc.value)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    names = [n for n, _ in cli.providers(cli.parse_args(["--backend", "openrouter"]))]
    assert names[0] == "openrouter:qwen/qwen3.8-omni-flash"
