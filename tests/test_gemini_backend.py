"""GeminiBackend against a fake Live session built from real google-genai message types."""

import asyncio

import pytest

genai = pytest.importorskip("google.genai")
from google.genai import types  # noqa: E402

from greeter.backends.gemini import GeminiBackend  # noqa: E402


def audio_msg(data=b"\x01\x00" * 240, text=None):
    return types.LiveServerMessage(
        server_content=types.LiveServerContent(
            model_turn=types.Content(parts=[types.Part(inline_data=types.Blob(data=data, mime_type="audio/pcm;rate=24000"))]),
            output_transcription=types.Transcription(text=text) if text else None,
        )
    )


def content(**kw):
    return types.LiveServerMessage(server_content=types.LiveServerContent(**kw))


TURNS = [
    [audio_msg(text="Hello! "), audio_msg(text="Love the green."), content(turn_complete=True)],
    [content(input_transcription=types.Transcription(text="hi robot")), content(interrupted=True), content(turn_complete=True)],
]


class FakeSession:
    def __init__(self):
        self.client_content, self.realtime = [], []
        self.turns = list(TURNS)

    async def send_client_content(self, turns, turn_complete):
        self.client_content.append((turns, turn_complete))

    async def send_realtime_input(self, **kw):
        assert len(kw) == 1, "SDK allows exactly one kwarg per call"
        self.realtime.append(kw)

    async def receive(self):
        if not self.turns:
            return  # connection closed: the SDK iterator yields nothing
        for msg in self.turns.pop(0):
            await asyncio.sleep(0)
            yield msg


class FakeConnect:
    def __init__(self, session):
        self.session, self.closed = session, False

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *exc):
        self.closed = True


@pytest.fixture
def fake(monkeypatch):
    session = FakeSession()
    calls = {}

    class Live:
        def connect(self, model, config):
            calls["model"], calls["config"] = model, config
            calls["cm"] = FakeConnect(session)
            return calls["cm"]

    class Client:
        def __init__(self, api_key):
            calls["api_key"] = api_key
            self.aio = type("Aio", (), {"live": Live()})()

    monkeypatch.setattr(genai, "Client", Client)
    return session, calls


async def collect(backend, until_kind, timeout=2.0):
    events = []

    async def run():
        async for ev in backend.events():
            events.append(ev)
            if ev.kind == until_kind:
                return

    await asyncio.wait_for(run(), timeout)
    return events


def test_greeting_and_conversation_flow(fake):
    session, calls = fake

    async def main():
        b = GeminiBackend(api_key="test-key")
        await b.open(b"\xff\xd8jpeg", "")  # warm, silent
        assert session.client_content == []
        await b.prepare_opener(b"\xff\xd8jpeg", "Greet the visitor in green")
        await b.speak_opener()  # Gemini speaks first via client content
        first = await collect(b, "turn_complete")
        await b.send_audio(b"\x00\x00" * 160)
        await b.send_frame(b"\xff\xd8frame")
        await b.send_text("say goodbye")
        rest = await collect(b, "error")
        await b.close()
        return first, rest

    first, rest = asyncio.run(main())
    assert calls["model"] == "gemini-3.8-live" and calls["api_key"] == "test-key"
    assert calls["config"].response_modalities == ["AUDIO"]
    assert calls["config"].context_window_compression is not None  # no 2-minute cap
    assert calls["config"].session_resumption is not None
    # greeting: image + explicit instruction as one user turn, turn_complete=True
    (turn, complete), = session.client_content
    assert complete is True and turn.role == "user"
    assert turn.parts[0].inline_data.mime_type == "image/jpeg"
    assert turn.parts[1].text == "Greet the visitor in green"
    assert session.realtime[0] == {"text": " "}  # Gemini 3.x needs a realtime input to start
    kinds = [e.kind for e in first]
    assert kinds == ["audio", "bot_text", "audio", "bot_text", "turn_complete"]
    assert all(e.rate == 24000 for e in first if e.kind == "audio")
    assert [e.kind for e in rest] == ["user_text", "interrupted", "turn_complete", "error"]
    audio, video, text = session.realtime[1:]
    assert audio["audio"].mime_type == "audio/pcm;rate=16000"
    assert video["video"].mime_type == "image/jpeg"
    assert text == {"text": "say goodbye"}
    assert calls["cm"].closed


def test_missing_api_key_fails_fast(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        asyncio.run(GeminiBackend().open(b"", ""))


def test_session_resumption_after_a_drop(fake, monkeypatch):
    session, calls = fake
    session.turns = [[
        types.LiveServerMessage(session_resumption_update=types.LiveServerSessionResumptionUpdate(new_handle="h1", resumable=True)),
        content(turn_complete=True),
    ]]
    configs = []
    live_connect = calls  # the fixture's Client records the latest connect only; wrap it

    import google.genai as genai_mod

    original = genai_mod.Client

    class Recording(original):
        def __init__(self, api_key):
            super().__init__(api_key)
            connect = self.aio.live.connect

            def wrapped(model, config):
                configs.append(config)
                return connect(model, config)

            self.aio.live.connect = wrapped

    monkeypatch.setattr(genai_mod, "Client", Recording)

    async def main():
        b = GeminiBackend(api_key="k")
        await b.open(None, "")
        events = await collect(b, "error", timeout=5.0)
        await b.close()
        return events

    events = asyncio.run(main())
    assert len(configs) >= 2  # reconnected
    assert configs[1].session_resumption.handle == "h1"  # ... with the resumption handle
    assert events[-1].kind == "error"  # gave up after a few failed resumes
    assert live_connect["model"] == "gemini-3.8-live"
