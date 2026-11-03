"""OpenAIRealtimeBackend against a fake GA Realtime server over a real local WebSocket."""

import asyncio
import base64
import json

import cv2
import numpy as np
import pytest
from websockets.asyncio.server import serve

from greeter.audio import int16_to_pcm
from greeter.backends.base import ProviderDown
from greeter.backends.openai_realtime import OpenAIRealtimeBackend, frames_differ
from greeter.backends.spend import SpendMeter, is_provider_down, response_cost
from greeter.dialogue.prompts import BEGIN_INSTRUCTION, SYSTEM_PROMPT, opener_instruction

PCM = int16_to_pcm(np.full(2400, 1000, dtype=np.int16))  # 0.1 s at 24 kHz
USAGE = {
    "total_tokens": 1500,
    "input_tokens": 1000,
    "output_tokens": 500,
    "input_token_details": {"text_tokens": 200, "audio_tokens": 500, "image_tokens": 300, "cached_tokens": 0},
    "output_token_details": {"text_tokens": 100, "audio_tokens": 400},
}


def jpeg(value):
    ok, buf = cv2.imencode(".jpg", np.full((48, 64, 3), value, np.uint8))
    return buf.tobytes()


SCENE_A, SCENE_A2, SCENE_B = jpeg(80), jpeg(81), jpeg(220)


def b64(data):
    return base64.b64encode(data).decode()


class FakeRealtime:
    """Speaks enough of the GA Realtime protocol; can drop the first connection once."""

    def __init__(self, drop_after_commit=False):
        self.connections = []  # list of lists of received events
        self.headers = []
        self.drop_after_commit = drop_after_commit

    async def reply(self, ws, rid, text, purpose=None, item="item_1"):
        meta = {"purpose": purpose} if purpose else None
        await ws.send(json.dumps({"type": "response.created", "response": {"id": rid, "metadata": meta}}))
        await ws.send(json.dumps({"type": "response.output_audio.delta", "response_id": rid, "item_id": item, "delta": b64(PCM)}))
        await ws.send(json.dumps({"type": "response.output_audio_transcript.delta", "response_id": rid, "delta": text}))
        await ws.send(json.dumps({"type": "response.done", "response": {"id": rid, "status": "completed", "usage": USAGE}}))

    async def handler(self, ws):
        received = []
        self.connections.append(received)
        self.headers.append(ws.request.headers)
        await ws.send(json.dumps({"type": "session.created", "session": {}}))
        n = 0
        async for raw in ws:
            event = json.loads(raw)
            received.append(event)
            kind = event["type"]
            if kind == "session.update":
                await ws.send(json.dumps({"type": "session.updated", "session": event["session"]}))
            elif kind == "response.create":
                n += 1
                response = event["response"]
                if response.get("conversation") == "none":
                    await self.reply(ws, "resp_opener", "Hey, green scarf! Come say hi?", purpose="opener", item="op")
                else:
                    await self.reply(ws, "resp_%d" % n, "Hello!" if response.get("instructions") else "Nice.")
            elif kind == "conversation.item.create" and self.drop_after_commit and len(self.connections) == 1:
                content = event["item"]["content"][0]
                if content.get("type") == "output_text":
                    await ws.close()  # network blip right after the opener was committed
                    return


async def collect(backend, until, timeout=3.0):
    seen = []

    async def run():
        async for ev in backend.events():
            seen.append(ev)
            if ev.kind == until:
                return

    await asyncio.wait_for(run(), timeout)
    return seen


async def serve_fake(fake):
    server = await serve(fake.handler, "127.0.0.1", 0).__aenter__()
    return server, "ws://127.0.0.1:%d/v1/realtime" % server.sockets[0].getsockname()[1]


def test_opener_turns_and_frames():
    fake = FakeRealtime()

    async def main():
        server, url = await serve_fake(fake)
        b = OpenAIRealtimeBackend(api_key="test-key", url=url)
        await b.open(SCENE_A, "(scene note)")
        await b.prepare_opener(SCENE_A, opener_instruction(1))
        opener = await collect(b, "opener_ready")
        await b.commit_opener("Hey, green scarf! Come say hi?")
        await b.begin(BEGIN_INSTRUCTION)
        hello = await collect(b, "turn_complete")
        # the visitor talks: frame at speech start, then the scene changes before commit
        await b.send_frame(SCENE_A2)
        await b._handle({"type": "input_audio_buffer.speech_started"})
        await b.send_frame(SCENE_B)
        await b._handle({"type": "input_audio_buffer.committed", "item_id": "u1"})
        turn = await collect(b, "turn_complete")
        await b.close()
        server.close()
        return opener, hello, turn

    opener, hello, turn = asyncio.run(main())
    (sent,) = fake.connections
    headers = fake.headers[0]
    assert headers["Authorization"] == "Bearer test-key" and "OpenAI-Beta" not in headers
    session = sent[0]["session"]
    assert session["model"] == "gpt-realtime-2.1" and session["reasoning"] == {"effort": "minimal"}
    assert session["audio"]["input"]["turn_detection"]["create_response"] is False
    assert session["audio"]["input"]["format"] == {"type": "audio/pcm", "rate": 24000}

    # out-of-band opener: conversation none, the frame as input_image, persona kept
    oob = next(e for e in sent if e["type"] == "response.create" and e["response"].get("conversation") == "none")
    assert oob["response"]["input"][0]["content"][0]["type"] == "input_image"
    assert SYSTEM_PROMPT in oob["response"]["instructions"]
    ready = opener[-1]
    assert ready.kind == "opener_ready" and ready.data["pcm"] == PCM and ready.data["text"].startswith("Hey, green scarf")
    assert not any(e.kind == "audio" for e in opener)  # opener audio is buffered, not streamed

    # append-only commit: frame + what the robot said
    items = [e["item"] for e in sent if e["type"] == "conversation.item.create"]
    assert any(i["role"] == "assistant" and i["content"][0] == {"type": "output_text", "text": "Hey, green scarf! Come say hi?"} for i in items)
    assert not any(e["type"] == "conversation.item.delete" for e in sent)

    # begin -> the model speaks first; audio streamed at 24 kHz; usage costed
    assert [e.kind for e in hello if e.kind in ("audio", "bot_text", "usage", "turn_complete")] == ["audio", "bot_text", "usage", "turn_complete"]
    assert hello[0].rate == 24000

    # visitor turn: one frame at speech start, another at commit because the scene changed
    images = [i["content"][0] for i in items if i["role"] == "user" and i["content"][0]["type"] == "input_image"]
    assert [base64.b64decode(img["image_url"].split(",", 1)[1]) for img in images[-2:]] == [SCENE_A2, SCENE_B]
    assert images[-1]["detail"] == "low"
    assert sent[-1] == {"type": "response.create", "response": {}}
    assert "user_turn_end" in [e.kind for e in turn] and "turn_complete" in [e.kind for e in turn]


def test_unchanged_scene_is_not_sent_twice():
    assert not frames_differ(SCENE_A, SCENE_A2)
    assert frames_differ(SCENE_A, SCENE_B)
    assert frames_differ(None, SCENE_A)


def test_barge_in_truncates_what_was_heard():
    fake = FakeRealtime()

    async def main():
        server, url = await serve_fake(fake)
        b = OpenAIRealtimeBackend(api_key="k", url=url)
        await b.open(None, "")
        await b._handle({"type": "response.created", "response": {"id": "r9"}})
        await b._handle({"type": "response.output_audio.delta", "response_id": "r9", "item_id": "it9", "delta": b64(PCM * 20)})  # 2 s
        await asyncio.sleep(0.3)
        await b._handle({"type": "input_audio_buffer.speech_started"})
        events = []
        while not b._events.empty():
            events.append((await b._events.get()).kind)
        await asyncio.sleep(0.1)
        await b.close()
        server.close()
        return events

    events = asyncio.run(main())
    truncate = next(e for e in fake.connections[0] if e["type"] == "conversation.item.truncate")
    assert truncate["item_id"] == "it9" and 200 <= truncate["audio_end_ms"] <= 1000
    assert "interrupted" in events


def test_reconnects_and_reseeds_the_conversation():
    fake = FakeRealtime(drop_after_commit=True)

    async def main():
        server, url = await serve_fake(fake)
        b = OpenAIRealtimeBackend(api_key="k", url=url)
        await b.open(SCENE_A, "(scene note)")
        await b.commit_opener("Hey, green scarf!")
        for _ in range(50):
            if len(fake.connections) == 2 and any(e["type"] == "conversation.item.create" for e in fake.connections[1]):
                break
            await asyncio.sleep(0.05)
        await b.begin(BEGIN_INSTRUCTION)
        await collect(b, "turn_complete")
        await b.close()
        server.close()

    asyncio.run(main())
    assert len(fake.connections) == 2
    second = fake.connections[1]
    assert second[0]["type"] == "session.update"
    reseeded = [e["item"] for e in second if e["type"] == "conversation.item.create"]
    assert any(i["role"] == "assistant" and i["content"][0]["text"] == "Hey, green scarf!" for i in reseeded)


def test_spend_limit_is_provider_down():
    async def handler(ws):
        await ws.send(json.dumps({"type": "session.created", "session": {}}))
        await ws.recv()
        await ws.send(json.dumps({"type": "error", "error": {"code": "insufficient_quota", "message": "You exceeded your current quota"}}))
        await asyncio.sleep(0.3)

    async def main():
        async with serve(handler, "127.0.0.1", 0) as server:
            b = OpenAIRealtimeBackend(api_key="k", url="ws://127.0.0.1:%d" % server.sockets[0].getsockname()[1])
            with pytest.raises(ProviderDown):
                await b.open(None, "")
            await b.close()

    asyncio.run(main())
    assert is_provider_down("org_spend_limit_exceeded", None)
    assert not is_provider_down("conversation_already_has_active_response", "busy")


def test_missing_key_is_provider_down(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ProviderDown, match="OPENAI_API_KEY"):
        asyncio.run(OpenAIRealtimeBackend().open(None, ""))


def test_response_cost_and_meter():
    cost = response_cost("gpt-realtime-2.1", USAGE)
    expected = (200 * 4 + 500 * 32 + 300 * 5 + 100 * 24 + 400 * 64) / 1e6
    assert cost == pytest.approx(expected)
    assert response_cost("unknown-model", USAGE) is None
    t = [0.0]
    meter = SpendMeter(clock=lambda: t[0])
    meter.add(1.0)
    t[0] = 1800.0
    meter.add(2.0)
    t[0] = 4000.0
    assert meter.total_usd == 3.0 and meter.last_hour_usd() == 2.0


def test_slow_turn_detection_is_not_silence():
    """speech_started ... (semantic VAD still deciding) ... keeps the silence timer from firing."""

    async def main():
        fake = FakeRealtime()
        server, url = await serve_fake(fake)
        b = OpenAIRealtimeBackend(api_key="k", url=url)
        await b.open(None, "")
        await b._handle({"type": "input_audio_buffer.speech_started"})
        await asyncio.sleep(2.6)
        kinds = []
        while not b._events.empty():
            kinds.append((await b._events.get()).kind)
        await b.close()
        server.close()
        return kinds

    assert asyncio.run(main()).count("user_activity") >= 3
