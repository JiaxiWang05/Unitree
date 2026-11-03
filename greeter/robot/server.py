"""Optional WebSocket bridge: puts :class:`RobotCore` behind a socket for a laptop.

Not used by the default all-on-Jetson mode. Exactly one laptop is served at a
time; a new connection replaces the old one. Wire format: ``greeter.protocol``.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import threading
from typing import Optional, Union
from urllib.parse import parse_qs, urlparse

from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed

from greeter import protocol
from greeter.robot.core import RobotCore, RobotEvent

log = logging.getLogger(__name__)

Message = Union[str, bytes]


def encode(event: RobotEvent) -> Optional[Message]:
    kind, data = event.kind, event.data
    if kind == "mic":
        return protocol.encode_binary(protocol.TAG_MIC, data)
    if kind == "video":
        return protocol.encode_binary(protocol.TAG_VIDEO, data)
    if kind == "notice":
        fields = {k: v for k, v in data.items() if k != "jpeg"}
        return protocol.encode_event("notice", jpeg_b64=base64.b64encode(data["jpeg"]).decode("ascii"), **fields)
    if kind == "tracks":
        return protocol.encode_event("tracks", **data)
    if kind == "playback":
        return protocol.encode_event("playback", state=data)
    if kind == "status":
        return protocol.encode_event("status", **data)
    if kind == "hello":
        return protocol.encode_event("hello", audio_rate=protocol.AUDIO_RATE, **data)
    return None


class BridgeServer:
    def __init__(
        self,
        core: RobotCore,
        host: str = "0.0.0.0",
        port: int = protocol.DEFAULT_PORT,
        token: Optional[str] = None,
    ) -> None:
        self.core, self.host, self.port, self.token = core, host, port, token
        self.ready = threading.Event()  # set once listening (port known)
        self.client = None
        self._dropped = 0

    def _authorised(self, ws) -> bool:
        if not self.token:
            return True
        query = parse_qs(urlparse(ws.request.path).query)
        return query.get("token", [""])[0] == self.token

    async def _handle_message(self, msg: Message) -> None:
        core = self.core
        if isinstance(msg, bytes):
            tag, payload = protocol.decode_binary(msg)
            if tag == protocol.TAG_PLAY:
                core.play(payload)
            return
        event = protocol.decode_event(msg)
        kind = event["type"]
        if kind == "triggers":
            core.set_triggers(bool(event.get("enabled", True)))
        elif kind == "stream":
            core.set_stream(mic=event.get("mic"), video=event.get("video"))
        elif kind == "release":
            core.release(int(event["track_id"]))
        elif kind == "led":
            core.led(tuple(event["rgb"]))
        elif kind == "audio_stop":
            core.stop_audio()
        else:
            log.warning("unknown message type %r", kind)

    async def _handler(self, ws) -> None:
        if not self._authorised(ws):
            await ws.close(code=4001, reason="bad token")
            return
        if self.client is not None:
            log.info("new laptop connected; closing the previous one")
            await self.client.close(code=4000, reason="replaced")
        self.client = ws
        queue: asyncio.Queue = asyncio.Queue(maxsize=256)

        def sink(event: RobotEvent) -> None:
            msg = encode(event)
            if msg is None:
                return
            try:
                queue.put_nowait(msg)
            except asyncio.QueueFull:  # drop rather than block when the laptop falls behind
                self._dropped += 1
                if self._dropped % 100 == 1:
                    log.warning("laptop is not keeping up; dropped %d messages", self._dropped)

        async def sender() -> None:
            while True:
                await ws.send(await queue.get())

        log.info("laptop connected from %s", ws.remote_address)
        self.core.attach(sink)
        send_task = asyncio.ensure_future(sender())
        try:
            async for msg in ws:
                try:
                    await self._handle_message(msg)
                except (ValueError, KeyError, TypeError) as exc:
                    log.warning("bad message from laptop: %s", exc)
        except ConnectionClosed:
            pass
        finally:
            send_task.cancel()
            self.core.detach(sink)
            if self.client is ws:
                self.client = None
                log.info("laptop disconnected")

    async def run(self, stop: Optional[asyncio.Event] = None) -> None:
        async with serve(
            self._handler,
            self.host,
            self.port,
            max_size=protocol.MAX_MESSAGE_BYTES,
            ping_interval=10,
            ping_timeout=20,
        ) as server:
            self.port = server.sockets[0].getsockname()[1]
            log.info("bridge listening on ws://%s:%d", self.host, self.port)
            self.ready.set()
            await self.core.run(stop)
