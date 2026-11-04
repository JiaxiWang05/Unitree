"""Common interface for conversation backends (OpenAI Realtime, Gemini Live, local, scripted)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, AsyncIterator, Optional


class ProviderDown(RuntimeError):
    """The provider refused service for the day (spend limit, quota, auth): switch providers."""


@dataclass
class BackendEvent:
    """``kind`` is one of:

    ``audio``          ``data`` = mono s16le speech at ``rate`` Hz (in-conversation reply)
    ``opener_ready``   ``data`` = {"pcm", "rate", "text"}: the pre-generated invitation
    ``bot_text``       ``data`` = (part of) what the robot is saying
    ``user_text``      ``data`` = (part of) what the visitor said
    ``user_activity``  the visitor is speaking
    ``user_turn_end``  the visitor finished a turn (the model is thinking)
    ``turn_complete``  the model finished its turn
    ``interrupted``    the model was interrupted; drop queued speech
    ``usage``          ``data`` = {"model", "cost_usd", "tokens"} for one response
    ``provider_down``  ``data`` = message: this provider should not be used any more today
    ``error``          ``data`` = message; the session is unusable
    """

    kind: str
    data: Any = None
    rate: int = 0


class Backend:
    """One conversation with one visitor (or group). Created per visit, closed afterwards.

    Lifecycle: :meth:`open` (warm session, silent) -> :meth:`prepare_opener`
    -> either the runner plays the ``opener_ready`` audio and calls
    :meth:`commit_opener`, or (backends without out-of-band generation) the
    runner calls :meth:`speak_opener` -> :meth:`begin` -> audio/frames -> :meth:`close`.
    """

    name = "base"
    supports_opener = False  # can generate the invitation out of band, before it is needed

    def __init__(self) -> None:
        self._events: "asyncio.Queue[Optional[BackendEvent]]" = asyncio.Queue()
        self._closed = False
        self._opener_request: Optional[tuple] = None

    def _emit(self, kind: str, data: Any = None, rate: int = 0) -> None:
        if not self._closed:
            self._events.put_nowait(BackendEvent(kind, data, rate))

    async def events(self) -> AsyncIterator[BackendEvent]:
        while True:
            event = await self._events.get()
            if event is None:
                return
            yield event

    async def open(self, jpeg: Optional[bytes], note: str) -> None:
        """Connect; say nothing yet. ``jpeg``/``note`` describe the scene (either may be empty)."""
        raise NotImplementedError

    async def prepare_opener(self, jpeg: bytes, instruction: str) -> None:
        """Generate the invitation now (out of band) or remember it for :meth:`speak_opener`."""
        self._opener_request = (jpeg, instruction)

    async def commit_opener(self, text: str) -> None:
        """The runner played ``text`` (the opener or a canned clip): record it in the conversation."""

    async def speak_opener(self) -> None:
        """Say the invitation now, live (backends without out-of-band generation)."""
        if self._opener_request is not None:
            await self.send_text(self._opener_request[1])

    async def begin(self, instruction: Optional[str]) -> None:
        """The conversation starts. With an instruction the model speaks first."""
        if instruction:
            await self.send_text(instruction)

    async def send_audio(self, pcm: bytes) -> None:
        """Visitor audio: 16 kHz mono s16le."""
        raise NotImplementedError

    async def send_frame(self, jpeg: bytes) -> None:
        raise NotImplementedError

    async def send_text(self, text: str) -> None:
        """An instruction for the next turn (e.g. wrap up)."""
        raise NotImplementedError

    async def cut_in(self, instruction: str) -> None:
        """Speak now, although the visitor hasn't paused (they have talked for a long time)."""
        await self.send_text(instruction)

    async def add_note(self, text: str) -> None:
        """Silent context for the model's next reply (e.g. start wrapping up). Default: ignored."""

    async def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._events.put_nowait(None)
