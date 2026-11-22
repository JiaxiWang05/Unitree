"""OpenRouter cascade with a fake client: no network."""

import asyncio
import math
import struct
import time

import pytest

from greeter import cli
from greeter.backends import openrouter as orb


def tone(seconds, amp=8000, rate=16000):
    n = int(seconds * rate)
    return struct.pack("<%dh" % n, *(int(amp * math.sin(2 * math.pi * 440 * i / rate)) for i in range(n)))


SILENCE = b"\x00\x00" * 1600   # 0.1 s


class FakeClient:
    def __init__(self, pieces, fail=None, tts_fail=False, delay=0.0):
        self.pieces, self.fail, self.tts_fail, self.delay = pieces, fail, tts_fail, delay
        self.requests, self.spoken = [], []

    def stream_chat(self, model, messages):
        self.requests.append(messages)
        if self.fail:
            raise self.fail
        for i, p in enumerate(self.pieces):
            time.sleep(self.delay)
            yield p, ({"cost": 0.0012, "total_tokens": 900} if i == len(self.pieces) - 1 else None)

    def speech(self, model, text, voice):
        if self.tts_fail:
            raise RuntimeError("no speech")
        self.spoken.append(text)
        return b"\x01\x00" * 480, 24000


@pytest.fixture(autouse=True)
def reset_failures():
    orb.OpenRouterBackend.consecutive_failures = 0


async def collect(backend, until=("turn_complete", "error", "provider_down", "opener_ready")):
    out = []
    async for e in backend.events():
        out.append(e)
        if e.kind in until:
            return out


async def speak(b, seconds=0.6):
    for chunk in [tone(0.1)] * int(seconds * 10) + [SILENCE] * 12:
        await b.send_audio(chunk)


def test_turn_hears_answers_sentence_by_sentence():
    async def run():
        client = FakeClient(["«what do", " you do?» I greet", " visitors. Come and", " say hi!"])
        b = orb.OpenRouterBackend(client=client)
        await b.open(b"\xff\xd8jpeg", "")
        await speak(b)
        events = await collect(b)
        history = list(b.history)
        await b.close()
        return client, events, history

    client, events, history = asyncio.run(run())
    kinds = [e.kind for e in events]
    assert kinds[0] == "user_activity" and "user_turn_end" in kinds and kinds[-1] == "turn_complete"
    assert [e.data for e in events if e.kind == "user_text"] == ["what do you do?"]
    assert [e.data.strip() for e in events if e.kind == "bot_text"] == ["I greet visitors.", "Come and say hi!"]
    assert client.spoken == ["I greet visitors.", "Come and say hi!"]
    assert all(e.rate == 24000 for e in events if e.kind == "audio")
    assert [e.data["cost_usd"] for e in events if e.kind == "usage"] == [0.0012]
    assert [p["type"] for p in client.requests[0][-1]["content"]] == ["input_audio", "image_url", "text"]
    remembered = history[-2]["content"]   # its own transcript, no image kept
    assert [p["type"] for p in remembered] == ["input_audio", "text"]
    assert remembered[-1]["text"] == "(The visitor said: what do you do?)"


def test_no_quote_and_leading_whitespace_is_spoken_once():
    async def run():
        client = FakeClient(["\n Hello there. ", "How are you?"])
        b = orb.OpenRouterBackend(client=client)
        await b.send_text("greet them")
        events = await collect(b)
        await b.close()
        return client

    assert asyncio.run(run()).spoken == ["Hello there.", "How are you?"]


def test_unclosed_quote_asks_again():
    async def run():
        client = FakeClient(["«what is this robot for"])
        b = orb.OpenRouterBackend(client=client)
        await speak(b)
        events = await collect(b)
        await b.close()
        return client, events

    client, events = asyncio.run(run())
    assert client.spoken == [orb.REASK] and events[-1].kind == "turn_complete"


def test_new_reply_stops_the_one_being_spoken():
    async def run():
        client = FakeClient(["One. ", "Two. ", "Three. ", "Four."], delay=0.05)
        b = orb.OpenRouterBackend(client=client)
        await b.send_text("first")
        await asyncio.sleep(0.02)
        await b.send_text("goodbye")
        events = await collect(b, until=("turn_complete",))
        await b.close()
        return events

    events = asyncio.run(run())
    assert "interrupted" in [e.kind for e in events]
    assert [e.kind for e in events].count("turn_complete") == 1


def test_cut_in_answers_with_the_speech_so_far():
    async def run():
        client = FakeClient(["«so much» Sorry to jump in!"])
        b = orb.OpenRouterBackend(client=client)
        for _ in range(8):
            await b.send_audio(tone(0.1))
        await b.cut_in("Cut in politely.")
        events = await collect(b)
        await b.close()
        return client, events

    client, events = asyncio.run(run())
    assert [p["type"] for p in client.requests[0][-1]["content"]][0] == "input_audio"
    assert "user_turn_end" in [e.kind for e in events]


def test_a_cough_is_not_a_turn():
    async def run():
        client = FakeClient(["Hi."])
        b = orb.OpenRouterBackend(client=client)
        await b.send_audio(tone(0.1))
        for _ in range(15):
            await b.send_audio(SILENCE)
        collecting = b._collecting
        await b.close()
        return client, collecting

    client, collecting = asyncio.run(run())
    assert not collecting and client.requests == []


def test_out_of_credit_switches_provider():
    async def run():
        b = orb.OpenRouterBackend(client=FakeClient([], fail=orb.OpenRouterError(402, "insufficient credits")))
        await b.send_text("hello")
        events = await collect(b)
        await b.close()
        return events

    assert asyncio.run(run())[-1].kind == "provider_down"


def test_repeated_failures_switch_provider():
    async def turn():
        b = orb.OpenRouterBackend(client=FakeClient([], fail=orb.OpenRouterError(502, "model is down")))
        await b.send_text("hello")
        events = await collect(b)
        await b.close()
        return events[-1].kind

    kinds = [asyncio.run(turn()) for _ in range(orb.FAILS_BEFORE_DOWN)]
    assert kinds[:-1] == ["error"] * (orb.FAILS_BEFORE_DOWN - 1) and kinds[-1] == "provider_down"


def test_speech_falls_back_to_espeak(monkeypatch):
    monkeypatch.setattr(orb, "espeak", lambda text: (b"\x02\x00" * 160, 16000))

    async def run():
        b = orb.OpenRouterBackend(client=FakeClient(["Hello there."], tts_fail=True))
        await b.send_text("greet")
        events = await collect(b)
        await b.close()
        return events

    audio = [e for e in asyncio.run(run()) if e.kind == "audio"]
    assert audio and audio[0].rate == 16000


def test_notes_ride_in_the_user_message():
    async def run():
        client = FakeClient(["Hello."])
        b = orb.OpenRouterBackend(client=client)
        await b.open(None, "A group of three is here.")
        await b.send_text("greet them")
        await collect(b)
        await b.close()
        return client

    sent = asyncio.run(run()).requests[0]
    assert [m["role"] for m in sent] == ["system", "user"]
    assert sent[-1]["content"][-1]["text"].startswith("Note for the robot: A group of three is here.")


def test_helpers():
    assert orb.split_heard("«hi» Hello.") == ("hi", "Hello.", True)
    assert orb.split_heard("  «half") == (None, "", False)
    assert orb.split_heard("Hello.") == (None, "Hello.", True)
    assert orb.unclosed_heard("«hi>> Hello.") == ("hi", "Hello.")
    assert orb.pcm_rate("audio/pcm;rate=22050") == 22050 and orb.pcm_rate("audio/pcm") == 24000
    assert orb.reasoning_for("qwen/qwen3.8-omni-flash") == {"enabled": False}
    assert orb.reasoning_for("~google/gemini-flash-latest")["effort"] == "low"
    assert len(orb.to_16k(b"\x01\x00" * 22050, 22050)) // 2 in range(15990, 16010)


def test_cli_openrouter_needs_its_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(SystemExit) as exc:
        cli.providers(cli.parse_args(["--backend", "openrouter", "--env-file", "/nonexistent"]))
    assert "OPENROUTER_API_KEY" in str(exc.value)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    names = [n for n, _ in cli.providers(cli.parse_args(["--backend", "openrouter"]))]
    assert names[0] == "openrouter:qwen/qwen3.8-omni-flash"
