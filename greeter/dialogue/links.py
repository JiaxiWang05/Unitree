"""How the dialogue app reaches the robot: in the same process (default) or over the bridge."""

from __future__ import annotations

import asyncio
import base64
import logging
from typing import AsyncIterator, Optional, Tuple

from greeter import protocol
from greeter.robot.core import RobotCore, RobotEvent

log = logging.getLogger(__name__)


class RobotLink:
    """Commands to the robot and a stream of :class:`RobotEvent` from it."""

    name = "robot"

    async def open(self) -> None:
        raise NotImplementedError

    def events(self) -> AsyncIterator[RobotEvent]:
        """Yields until the link drops or is closed."""
        raise NotImplementedError

    async def set_triggers(self, enabled: bool) -> None:
        raise NotImplementedError

    async def set_stream(self, mic: bool, video: bool) -> None:
        raise NotImplementedError

    async def led(self, rgb: Tuple[int, int, int]) -> None:
        raise NotImplementedError

    async def release(self, track_id: int) -> None:
        """The noticed person was never invited: they may be noticed again later."""
        raise NotImplementedError

    async def play(self, pcm: bytes) -> None:
        """16 kHz mono s16le."""
        raise NotImplementedError

    async def stop_audio(self) -> None:
        raise NotImplementedError

    async def close(self) -> None:
        raise NotImplementedError


class InProcessLink(RobotLink):
    """Direct calls into a :class:`RobotCore` running in the same event loop. No sockets."""

    name = "in-process"

    def __init__(self, core: RobotCore, max_queue: int = 1000) -> None:
        self.core = core
        self._max_queue = max_queue
        self._queue: Optional[asyncio.Queue] = None
        self._dropped = 0

    def _put(self, event: RobotEvent) -> None:
        if self._queue is None:
            return
        try:
            self._queue.put_nowait(event)
        except asyncio.QueueFull:
            self._dropped += 1
            if self._dropped % 100 == 1:
                log.warning("dialogue is not keeping up; dropped %d robot events", self._dropped)

    async def open(self) -> None:
        self._queue = asyncio.Queue(maxsize=self._max_queue)
        self.core.attach(self._put)

    async def events(self) -> AsyncIterator[RobotEvent]:
        queue = self._queue
        while queue is not None:
            event = await queue.get()
            if event is None:
                return
            yield event

    async def set_triggers(self, enabled: bool) -> None:
        self.core.set_triggers(enabled)

    async def set_stream(self, mic: bool, video: bool) -> None:
        self.core.set_stream(mic=mic, video=video)

    async def led(self, rgb) -> None:
        self.core.led(tuple(rgb))

    async def release(self, track_id: int) -> None:
        self.core.release(track_id)

    async def play(self, pcm: bytes) -> None:
        self.core.play(pcm)

    async def stop_audio(self) -> None:
        self.core.stop_audio()

    async def close(self) -> None:
        self.core.detach(self._put)
        if self._queue is not None:
            self._queue.put_nowait(None)
            self._queue = None


class WebSocketLink(RobotLink):
    """Talks to ``greeter.robot.server.BridgeServer`` (optional laptop split)."""

    name = "websocket"

    def __init__(self, url: str) -> None:
        self.url = url
        self.ws = None

    async def open(self) -> None:
        from websockets.asyncio.client import connect

        self.ws = await connect(self.url, max_size=protocol.MAX_MESSAGE_BYTES, open_timeout=5, ping_interval=10, ping_timeout=20)
        log.info("connected to robot bridge %s", self.url.split("?")[0])

    async def events(self) -> AsyncIterator[RobotEvent]:
        from websockets.exceptions import ConnectionClosed

        try:
            async for msg in self.ws:
                if isinstance(msg, bytes):
                    tag, payload = protocol.decode_binary(msg)
                    if tag == protocol.TAG_MIC:
                        yield RobotEvent("mic", payload)
                    elif tag == protocol.TAG_VIDEO:
                        yield RobotEvent("video", payload)
                    continue
                event = protocol.decode_event(msg)
                kind = event.pop("type")
                if kind == "notice":
                    event["jpeg"] = base64.b64decode(event.pop("jpeg_b64"))
                    yield RobotEvent("notice", event)
                elif kind == "tracks":
                    yield RobotEvent("tracks", event)
                elif kind == "playback":
                    yield RobotEvent("playback", event.get("state"))
                elif kind == "status":
                    yield RobotEvent("status", event)
                elif kind == "hello":
                    yield RobotEvent("hello", event)
        except ConnectionClosed:
            return

    async def _send(self, message) -> None:
        from websockets.exceptions import ConnectionClosed

        if self.ws is None:
            return
        try:
            await self.ws.send(message)
        except ConnectionClosed:
            pass

    async def set_triggers(self, enabled: bool) -> None:
        await self._send(protocol.encode_event("triggers", enabled=enabled))

    async def set_stream(self, mic: bool, video: bool) -> None:
        await self._send(protocol.encode_event("stream", mic=mic, video=video))

    async def led(self, rgb) -> None:
        await self._send(protocol.encode_event("led", rgb=list(rgb)))

    async def release(self, track_id: int) -> None:
        await self._send(protocol.encode_event("release", track_id=track_id))

    async def play(self, pcm: bytes) -> None:
        await self._send(protocol.encode_binary(protocol.TAG_PLAY, pcm))

    async def stop_audio(self) -> None:
        await self._send(protocol.encode_event("audio_stop"))

    async def close(self) -> None:
        if self.ws is not None:
            await self.ws.close()
            self.ws = None
