"""Runner: connects the robot (via a link), the interaction ladder and a backend."""

from __future__ import annotations

import asyncio
import logging
import math
import time
from collections import Counter, deque
from typing import Callable, Deque, Dict, List, Optional, Sequence, Tuple

from greeter import clips as clip_lines
from greeter import protocol
from greeter.audio import StreamResampler, pcm_duration, rms_dbfs
from greeter.backends.base import Backend, ProviderDown
from greeter.backends.spend import METER
from greeter.dialogue.links import RobotLink
from greeter.dialogue.machine import (
    SESSION_STATES,
    AddNote,
    Begin,
    CloseSession,
    CutIn,
    Dialogue,
    DialogueConfig,
    EnableTriggers,
    LedMode,
    OpenSession,
    PlayClip,
    PlayOpener,
    PrepareOpener,
    Release,
    SendText,
    State,
    StopAudio,
    Stream,
)
from greeter.recorder import NullRecorder, Recorder
from greeter.robot.core import RobotEvent

log = logging.getLogger(__name__)

Provider = Tuple[str, Callable[[], Backend]]

LED_COLOURS = {
    "noticed": (120, 255, 120),  # light green
    "listening": (0, 255, 0),  # green
    "thinking": (255, 140, 0),  # amber
    "speaking": (0, 200, 60),
}


def led_colour(mode: str, t: float) -> Tuple[int, int, int]:
    if mode in LED_COLOURS:
        return LED_COLOURS[mode]
    level = 0.15 + 0.85 * (0.5 - 0.5 * math.cos(2 * math.pi * t / 4.0))  # idle: white breathing, 4 s
    v = int(255 * level)
    return (v, v, v)


class SpotEars:
    """Talk-spot voice trigger: loudness above an adaptive noise floor for >= 0.3 s.

    The floor starts from the first 0.5 s, then follows quieter sound quickly and
    louder sound slowly (~5 s), so steady hall noise is learned but speech is not.
    """

    def __init__(self, margin_db: float = 12.0, min_dbfs: float = -50.0, min_speech_s: float = 0.3) -> None:
        self.margin_db, self.min_dbfs, self.min_speech_s = margin_db, min_dbfs, min_speech_s
        self.floor = -60.0
        self.speech_s = 0.0
        self._warm: List[float] = []
        self._warm_s = 0.0

    def feed(self, pcm: bytes) -> bool:
        level = rms_dbfs(pcm)
        seconds = pcm_duration(pcm, protocol.AUDIO_RATE)
        if self._warm_s < 0.5:
            self._warm.append(level)
            self._warm_s += seconds
            self.floor = sum(self._warm) / len(self._warm)
            return False
        if level > max(self.floor + self.margin_db, self.min_dbfs):
            self.speech_s += seconds
        else:
            self.speech_s = max(0.0, self.speech_s - seconds)
        rate = min(1.0, (0.2 if level < self.floor else 0.01) * seconds / 0.05)
        self.floor += rate * (level - self.floor)
        if self.speech_s >= self.min_speech_s:
            self.speech_s = 0.0
            return True
        return False


class GreeterApp:
    def __init__(
        self,
        link: RobotLink,
        providers: Sequence[Provider],
        dialogue_cfg: Optional[DialogueConfig] = None,
        transcripts: bool = True,
        recorder: Optional[Recorder] = None,
        clips: Optional[Dict[str, bytes]] = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if callable(providers):  # a bare factory
            providers = [("backend", providers)]
        self.link = link
        self.providers: List[Provider] = list(providers)
        self.provider_index = 0
        self.dialogue = Dialogue(dialogue_cfg)
        self.transcripts = transcripts
        self.recorder = recorder or NullRecorder()
        self.clips = clips or {}
        self.clock = clock
        self.backend: Optional[Backend] = None
        self.backend_ready = False
        self._jobs: Optional[asyncio.Queue] = None
        self._worker: Optional[asyncio.Task] = None
        self._pump_task: Optional[asyncio.Task] = None
        self._opener: Optional[dict] = None
        self._resamplers: Dict[int, StreamResampler] = {}
        self._ring: Deque[Tuple[float, bytes]] = deque()  # recent mic audio, replayed into a new session
        self._ears = SpotEars()
        self._led_mode = "idle"
        self._last_frame_saved = 0.0
        self._said: List[str] = []
        self._heard: List[str] = []
        self._stopping = False
        self.stats: Counter = Counter()

    # --- link lifecycle ------------------------------------------------------
    async def run(self) -> None:
        backoff = 1.0
        led = asyncio.ensure_future(self._led_loop())
        try:
            while not self._stopping:
                try:
                    await self.link.open()
                except Exception as exc:  # OSError, handshake and timeout errors
                    if self._stopping:
                        break
                    log.warning("robot link (%s) unavailable: %s; retrying in %.0f s", self.link.name, exc, backoff)
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2.0, 10.0)
                    continue
                backoff = 1.0
                try:
                    await self._serve()
                finally:
                    await self.link.close()
                if not self._stopping:
                    log.warning("robot link lost; reconnecting")
                    await asyncio.sleep(1.0)
        finally:
            led.cancel()

    async def stop(self) -> None:
        self._stopping = True
        await self._close_backend()
        self.recorder.end_visit()
        await self.link.close()

    async def _serve(self) -> None:
        await self._apply(self.dialogue.start(self.clock()))
        ticker = asyncio.ensure_future(self._ticker())
        try:
            async for event in self.link.events():
                try:
                    await self._on_robot(event)
                except (ValueError, KeyError, TypeError) as exc:
                    log.warning("bad event from robot: %s", exc)
        finally:
            ticker.cancel()
            await self._close_backend()

    async def _ticker(self) -> None:
        while True:
            await asyncio.sleep(0.1)
            await self._apply(self.dialogue.tick(self.clock()))

    async def _led_loop(self) -> None:
        last = None
        while True:
            colour = led_colour(self._led_mode, time.monotonic())
            if colour != last:
                last = colour
                await self.link.led(colour)
            await asyncio.sleep(0.25)  # LedControl must stay >= 200 ms apart

    # --- robot -> dialogue ---------------------------------------------------
    async def _on_robot(self, event: RobotEvent) -> None:
        now = self.clock()
        kind, data = event.kind, event.data
        if kind == "mic":
            self.recorder.mic(data)
            if self.backend_ready and self.backend is not None and self.dialogue.state in SESSION_STATES:
                self.stats["mic_bytes"] += len(data)
                await self.backend.send_audio(data)
                return
            self._ring.append((now, data))
            while self._ring and now - self._ring[0][0] > 2.0:
                self._ring.popleft()
            if self.dialogue.state is State.IDLE and self._ears.feed(data):
                await self._apply(self.dialogue.on_spot_speech(now))
        elif kind == "video":
            if self.backend_ready and self.backend is not None:
                self.stats["frames"] += 1
                await self.backend.send_frame(data)
            if self.recorder.visit is not None and now - self._last_frame_saved >= 2.0:
                self._last_frame_saved = now
                self.recorder.frame(data, "turn")
        elif kind == "notice":
            self.stats["notices"] += 1
            await self._apply(self.dialogue.on_notice(data, data["jpeg"], now))
        elif kind == "tracks":
            self.recorder.trace("tracks", data)
            await self._apply(self.dialogue.on_tracks(data, now))
        elif kind == "playback":
            await self._apply(self.dialogue.on_playback(str(data), now))
        elif kind == "status":
            self.recorder.trace("status", data)
        elif kind == "hello":
            log.info("robot ready (mock=%s, via %s link)", (data or {}).get("mock"), self.link.name)

    # --- actions -------------------------------------------------------------
    def _job(self, fn) -> None:
        """Run ``fn(backend)`` in order, once the session is open."""
        if self._jobs is not None:
            self._jobs.put_nowait(fn)

    async def _apply(self, actions) -> None:
        link = self.link
        for action in actions:
            if isinstance(action, EnableTriggers):
                await link.set_triggers(action.enabled)
            elif isinstance(action, Release):
                await link.release(action.track_id)
            elif isinstance(action, Stream):
                await link.set_stream(action.mic, action.video)
            elif isinstance(action, LedMode):
                self._led_mode = action.mode
            elif isinstance(action, StopAudio):
                self._resamplers.clear()
                await link.stop_audio()
            elif isinstance(action, OpenSession):
                await self._open_session(action)
            elif isinstance(action, PrepareOpener):
                self._job(lambda b, a=action: self._prepare(b, a))
            elif isinstance(action, PlayOpener):
                await self._play_opener()
            elif isinstance(action, PlayClip):
                await self._play_clip(action.name)
            elif isinstance(action, Begin):
                self._job(lambda b, i=action.instruction: b.begin(i))
            elif isinstance(action, SendText):
                self._job(lambda b, t=action.text: b.send_text(t))
            elif isinstance(action, CutIn):
                self._job(lambda b, t=action.instruction: b.cut_in(t))
            elif isinstance(action, AddNote):
                self._job(lambda b, t=action.text: b.add_note(t))
            elif isinstance(action, CloseSession):
                self._flush_transcript()
                self.recorder.end_visit()
                await self._close_backend()

    async def _play(self, pcm16: bytes) -> None:
        if not pcm16:
            return
        self.stats["speech_bytes"] += len(pcm16)
        self.recorder.robot(pcm16)
        await self.link.play(pcm16)
        await self._apply(self.dialogue.on_bot_audio(pcm_duration(pcm16, protocol.AUDIO_RATE), self.clock()))

    def _to16k(self, pcm: bytes, rate: int) -> bytes:
        if not rate or rate == protocol.AUDIO_RATE:
            return pcm
        if rate not in self._resamplers:
            self._resamplers[rate] = StreamResampler(rate, protocol.AUDIO_RATE)
        return self._resamplers[rate].process(pcm)

    async def _prepare(self, backend: Backend, action: PrepareOpener) -> None:
        await backend.prepare_opener(action.jpeg, action.instruction)
        if not backend.supports_opener:  # it will speak live: nothing to wait for
            await self._apply(self.dialogue.on_opener_ready(self.clock()))

    async def _play_opener(self) -> None:
        backend, opener = self.backend, self._opener
        if backend is not None and backend.supports_opener and opener and opener.get("pcm"):
            self._opener = None
            log.info("invitation: %s", opener.get("text"))
            self.recorder.event("robot", opener.get("text"))
            await self._play(StreamResampler(opener["rate"], protocol.AUDIO_RATE).process(opener["pcm"]))
            self._job(lambda b, t=opener.get("text") or "": b.commit_opener(t))
        else:
            self._job(lambda b: b.speak_opener())

    async def _play_clip(self, name: str) -> None:
        pcm = self.clips.get(name)
        text = clip_lines.LINES.get(name, name)
        if pcm:
            log.info("clip %s: %s", name, text)
            self.recorder.event("robot_clip", text)
            await self._play(pcm)
            self._job(lambda b, t=text: b.commit_opener(t))
        elif name in ("hey_green", "hey_there"):
            self._job(lambda b: b.speak_opener())  # no clip rendered: say the invitation live

    # --- backend -------------------------------------------------------------
    def _make_backend(self) -> Backend:
        name, factory = self.providers[self.provider_index]
        backend = factory()
        backend.provider_name = name
        return backend

    def _provider_down(self, why: str) -> None:
        if self.provider_index + 1 < len(self.providers):
            old = self.providers[self.provider_index][0]
            self.provider_index += 1
            log.error("provider %s unavailable (%s): switching to %s", old, why, self.providers[self.provider_index][0])
        else:
            log.error("provider unavailable (%s) and no fallback left", why)

    async def _open_session(self, action: OpenSession) -> None:
        await self._close_backend()
        self.stats["visits"] += 1
        label = "track%s" % self.dialogue.target_id if self.dialogue.target_id is not None else "spot"
        self.recorder.start_visit(label)
        if action.jpeg:
            self.recorder.frame(action.jpeg, "notice")
        backend = self._make_backend()
        self.backend, self.backend_ready, self._opener = backend, False, None
        self._resamplers.clear()
        self._jobs = asyncio.Queue()
        self._worker = asyncio.ensure_future(self._session_worker(backend, action, self._jobs))

    async def _session_worker(self, backend: Backend, action: OpenSession, jobs: asyncio.Queue) -> None:
        t0 = self.clock()
        try:
            await backend.open(action.jpeg, action.note)
        except Exception as exc:
            if isinstance(exc, ProviderDown):
                self._provider_down(str(exc))
            log.error("could not start %s session: %s", backend.name, exc)
            await backend.close()
            if self.backend is backend:
                await self._apply(self.dialogue.on_session_error(self.clock()))
            return
        if self.backend is not backend:
            await backend.close()
            return
        self.backend_ready = True
        log.info("%s session ready in %.1f s", backend.name, self.clock() - t0)
        self._pump_task = asyncio.ensure_future(self._pump(backend))
        now = self.clock()
        if action.jpeg is None:  # started by talk-spot speech: replay what they just said
            for t, pcm in list(self._ring):
                if now - t <= 2.0:
                    await backend.send_audio(pcm)
        self._ring.clear()
        while True:
            job = await jobs.get()
            try:
                await job(backend)
            except Exception as exc:
                log.warning("%s: %s", backend.name, exc)

    async def _pump(self, backend: Backend) -> None:
        async for ev in backend.events():
            if self.backend is not backend:
                break
            now = self.clock()
            kind = ev.kind
            if kind == "audio":
                await self._play(self._to16k(ev.data, ev.rate))
            elif kind == "opener_ready":
                self._opener = ev.data
                await self._apply(self.dialogue.on_opener_ready(now))
            elif kind == "bot_text":
                self._said.append(ev.data)
            elif kind == "user_text":
                self._heard.append(ev.data)
                self.recorder.event("visitor", ev.data)
                await self._apply(self.dialogue.on_user_text(ev.data, now))
            elif kind == "user_activity":
                await self._apply(self.dialogue.on_user_activity(now))
            elif kind == "user_turn_end":
                await self._apply(self.dialogue.on_user_turn_end(now))
            elif kind == "turn_complete":
                said = "".join(self._said)
                self._flush_transcript()
                await self._apply(self.dialogue.on_turn_complete(now, said))
            elif kind == "interrupted":
                self._flush_transcript()
                await self._apply(self.dialogue.on_interrupted(now))
            elif kind == "usage":
                self.recorder.event("usage", ev.data)
                log.debug("spend: $%.3f total, $%.2f in the last hour", METER.total_usd, METER.last_hour_usd())
            elif kind == "provider_down":
                self._provider_down(str(ev.data))
                await self._apply(self.dialogue.on_session_error(now))
            elif kind == "error":
                await self._apply(self.dialogue.on_session_error(now))

    def _flush_transcript(self) -> None:
        heard = " ".join(s.strip() for s in self._heard if s and s.strip())
        said = "".join(self._said).strip()
        if said:
            self.recorder.event("robot", said)
        if self.transcripts:
            if heard:
                print("  visitor: %s" % heard, flush=True)
            if said:
                print("  robot:   %s" % said, flush=True)
        self._heard.clear()
        self._said.clear()

    async def _close_backend(self) -> None:
        backend, self.backend, self.backend_ready = self.backend, None, False
        current = asyncio.current_task()
        for task in (self._worker, self._pump_task):
            if task is not None and not task.done() and task is not current:
                task.cancel()
        self._worker = self._pump_task = None
        self._jobs = None
        self._opener = None
        if backend is not None:
            await backend.close()
