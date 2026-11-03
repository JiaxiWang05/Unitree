"""Interaction ladder (design doc 3.2): IDLE -> NOTICED -> BID -> OPEN -> CONVERSE -> CLOSE -> COOLDOWN.

* IDLE      perception only, LED white breathing.
* NOTICED   someone in green within 5 m who isn't walking past: open a warm session
            and generate the opener in the background (LED light green).
* BID       target at 1.2-2.2 m, facing us >= 0.8 s, no crowd, 8 s since the last
            bid, not invited in the last 30 min: play the opener (<= 15 words,
            names the green item, invites them to the talk spot). Not ready
            within 1 s: play the canned "Hey, you in the green!" clip.
* OPEN      they reply, step onto the talk spot or keep facing 1.5 s: talk.
            Otherwise drop silently (they count as invited).
            Anyone speaking on the talk spot can also start a conversation.
* CONVERSE  until goodbye, nobody in range for 4 s, someone queued 30 s after
            2 min of chat, or the 4 min cap. LED green listening / amber thinking.
* CLOSE     one-line takeaway calling back to the green item (skipped if they left).
* COOLDOWN  close the session, then back to IDLE.

Pure logic with an explicit ``now``: every input returns a list of actions for
the runner (``greeter.dialogue.app``). The robot never moves.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from greeter.dialogue import prompts
from greeter.vision import iou

log = logging.getLogger(__name__)


class State(str, Enum):
    IDLE = "idle"
    NOTICED = "noticed"
    BID = "bid"
    OPEN = "open"
    CONVERSE = "converse"
    CLOSE = "close"
    COOLDOWN = "cooldown"


SESSION_STATES = (State.NOTICED, State.BID, State.OPEN, State.CONVERSE, State.CLOSE)
GOODBYE = re.compile(r"\b(good ?bye|bye|see (you|ya)|got(ta)? to go|have to go|i'?m off|cheers,? bye)\b", re.I)


# --- actions -------------------------------------------------------------------
@dataclass(frozen=True)
class EnableTriggers:
    enabled: bool


@dataclass(frozen=True)
class Release:
    track_id: int


@dataclass(frozen=True)
class Stream:
    mic: bool
    video: bool


@dataclass(frozen=True)
class LedMode:
    mode: str  # idle | noticed | listening | thinking | speaking


@dataclass(frozen=True)
class OpenSession:
    jpeg: Optional[bytes]
    note: str


@dataclass(frozen=True)
class PrepareOpener:
    jpeg: bytes
    instruction: str


@dataclass(frozen=True)
class PlayOpener:
    pass


@dataclass(frozen=True)
class PlayClip:
    name: str


@dataclass(frozen=True)
class Begin:
    instruction: Optional[str]  # None: wait for the visitor to speak


@dataclass(frozen=True)
class SendText:
    text: str


@dataclass(frozen=True)
class StopAudio:
    pass


@dataclass(frozen=True)
class CloseSession:
    pass


Action = Any


@dataclass
class DialogueConfig:
    notice_timeout_s: float = 20.0  # noticed but never came into bid range: let go
    lost_s: float = 3.0  # target unseen this long during NOTICED/BID/OPEN
    bid_min_dist: float = 1.2
    bid_max_dist: float = 2.2
    bid_facing_s: float = 0.8
    opener_wait_s: float = 1.0  # then the canned clip
    open_facing_s: float = 1.5
    open_timeout_s: float = 4.0
    global_cooldown_s: float = 8.0  # between bids
    invited_memory_s: float = 1800.0  # same track not invited again within 30 min
    converse_range: float = 2.5  # "still here" during a conversation
    spot_empty_s: float = 4.0
    queue_s: float = 30.0
    queue_after_s: float = 120.0
    queue_range: float = 3.0
    max_visit_s: float = 240.0
    silence_s: float = 15.0  # safety net: nobody spoke and the robot was quiet (0 = off)
    close_timeout_s: float = 8.0
    cooldown_s: float = 2.0
    reacquire_iou: float = 0.3
    spot_accept_margin_s: float = 0.5  # spot filled from just before the invitation began = they accepted


class Dialogue:
    def __init__(self, cfg: Optional[DialogueConfig] = None) -> None:
        self.cfg = cfg or DialogueConfig()
        self.state = State.IDLE
        self.entered_at = 0.0
        self.transitions: List[Tuple[str, str, str]] = []  # (from, to, reason)
        self.target_id: Optional[int] = None
        self.target_box: Optional[Tuple[float, float, float, float]] = None
        self.target: Dict[str, Any] = {}  # latest Person dict of the target
        self.target_seen = 0.0
        self.group_size = 1
        self.snapshot: Dict[str, Any] = {"people": [], "crowd": False, "spot_occupied": False}
        self.invited: Dict[int, float] = {}
        self.last_bid = -1e9
        self.opener_ready = False
        self.bid_played = False
        self.bid_audio_seen = False
        self.visit_started = 0.0
        self.last_user = 0.0
        self.speech_until = 0.0
        self.robot_playing = False
        self.thinking = False
        self.turn_done = False
        self.in_range_seen = 0.0
        self.spot_listen = False
        self.spot_since: Optional[float] = None  # when the talk spot last became occupied
        self._spot_source = "webcam"
        self.session_ended_at = float("-inf")
        self.end_reason = ""
        self._led = ""

    # --- helpers -------------------------------------------------------------
    def speaking(self, now: float) -> bool:
        return self.robot_playing or self.speech_until > now

    def _people(self) -> List[Dict[str, Any]]:
        return list(self.snapshot.get("people", []))

    def _led_mode(self, mode: str) -> List[Action]:
        if mode == self._led:
            return []
        self._led = mode
        return [LedMode(mode)]

    def _enter(self, state: State, now: float, reason: str = "", **kw) -> List[Action]:
        log.info("state %s -> %s%s", self.state.value, state.value, " (%s)" % reason if reason else "")
        self.transitions.append((self.state.value, state.value, reason))
        self.state, self.entered_at = state, now
        a: List[Action] = []
        if state is State.IDLE:
            self.target_id, self.target, self.thinking = None, {}, False
            self.spot_listen = bool(self.snapshot.get("spot_occupied"))
            a += [Stream(mic=self.spot_listen, video=False), EnableTriggers(True)] + self._led_mode("idle")
        elif state is State.NOTICED:
            self.opener_ready = self.bid_played = False
            self.speech_until, self.turn_done, self.thinking = 0.0, False, False
            note = prompts.scene_note(kw.get("distance"), self.group_size)
            a += [EnableTriggers(False)] + self._led_mode("noticed")
            a += [OpenSession(kw["jpeg"], note), PrepareOpener(kw["jpeg"], prompts.opener_instruction(self.group_size))]
        elif state is State.BID:
            self.last_bid = now
            self.bid_audio_seen = False
            if self.target_id is not None:
                self.invited[self.target_id] = now
            a += self._led_mode("speaking")
            if self.opener_ready:
                self.bid_played = True
                a.append(PlayOpener())
        elif state is State.OPEN:
            a += [Stream(mic=True, video=True)] + self._led_mode("listening")
        elif state is State.CONVERSE:
            self.visit_started = self.last_user = self.in_range_seen = now
            a += [EnableTriggers(False), Stream(mic=True, video=True)] + self._led_mode("listening")
            if "begin" in kw:
                a.append(Begin(kw["begin"]))
        elif state is State.CLOSE:
            self.end_reason = reason
            if not kw.get("spoken", True):
                return a + self._enter(State.COOLDOWN, now, reason)
            self.turn_done = False
            a += [Stream(mic=False, video=False), SendText(prompts.CLOSE_INSTRUCTION)] + self._led_mode("speaking")
        elif state is State.COOLDOWN:
            self.session_ended_at = now
            self.speech_until = now  # StopAudio cuts whatever was still playing
            a += [Stream(mic=False, video=False), StopAudio()]
            if kw.get("clip"):
                a.append(PlayClip(kw["clip"]))  # after StopAudio, or it would be cut off at once
            a += [CloseSession()] + self._led_mode("idle")
        return a

    def _drop(self, now: float, reason: str, release: bool) -> List[Action]:
        """Leave the ladder before a conversation started."""
        a: List[Action] = []
        if release and self.target_id is not None:
            a.append(Release(self.target_id))
        a += [StopAudio(), CloseSession()]
        return a + self._enter(State.IDLE, now, reason)

    def _bid_ready(self, now: float) -> bool:
        cfg, t = self.cfg, self.target
        dist = t.get("distance")
        return (
            dist is not None
            and cfg.bid_min_dist <= dist <= cfg.bid_max_dist
            and (t.get("facing_for") or 0.0) >= cfg.bid_facing_s
            and not self.snapshot.get("crowd")
            and now - self.last_bid >= cfg.global_cooldown_s
        )

    def _queued(self, now: float) -> bool:
        cfg = self.cfg
        mine = {self.target_id, self.target.get("group")}
        for p in self._people():
            if p.get("id") in mine or (p.get("group") is not None and p.get("group") in mine):
                continue
            if (p.get("distance") or 99) <= cfg.queue_range and (p.get("present_for") or 0) >= cfg.queue_s:
                return True
        return False

    def _visitor_in_range(self, match: Optional[Dict[str, Any]]) -> bool:
        """The visitor (or their group, or anyone on the talk spot) is still there."""
        if self.snapshot.get("spot_occupied"):
            return True
        group = self.target.get("group")
        for p in self._people():
            mine = p is match or (group is not None and p.get("group") == group)
            if mine and (p.get("distance") or 99) <= self.cfg.converse_range:
                return True
        return False

    # --- inputs --------------------------------------------------------------
    def start(self, now: float) -> List[Action]:
        """(Re)connected to the robot: always restart from idle."""
        a: List[Action] = []
        if self.state in SESSION_STATES:
            a += [StopAudio(), CloseSession()]
        self._led = ""
        return a + self._enter(State.IDLE, now, "start")

    def on_notice(self, event: Dict[str, Any], jpeg: bytes, now: float) -> List[Action]:
        tid = int(event["track_id"])
        if self.state is not State.IDLE:
            return [Release(tid)]  # busy: let the robot notice them again later
        if now - self.invited.get(tid, -1e9) < self.cfg.invited_memory_s:
            return []
        self.target_id, self.target_box, self.target_seen = tid, tuple(event.get("bbox") or (0, 0, 0, 0)), now
        self.group_size = int(event.get("group_size") or 1)
        self.target = {"id": tid, "distance": event.get("distance"), "facing_for": 0.0}
        return self._enter(State.NOTICED, now, "green at %.1f m" % (event.get("distance") or 0), jpeg=jpeg, distance=event.get("distance"))

    def on_tracks(self, snapshot: Dict[str, Any], now: float) -> List[Action]:
        occupied_now = bool(snapshot.get("spot_occupied"))
        spot = snapshot.get("spot") or {}
        source = "depth" if spot.get("source") == "depth" and not spot.get("stale") else "webcam"
        if not occupied_now:
            self.spot_since = None
        elif source != self._spot_source and self.spot_since is None:
            self.spot_since = -1e9  # a source switch is not someone stepping on: treat as long occupied
        elif not self.snapshot.get("spot_occupied") or self.spot_since is None:
            self.spot_since = now
        self._spot_source = source
        self.snapshot = snapshot
        a: List[Action] = []
        if self.state is State.IDLE:
            occupied = bool(snapshot.get("spot_occupied"))
            if occupied != self.spot_listen:  # listen for talk-spot speech only when someone is there
                self.spot_listen = occupied
                a.append(Stream(mic=occupied, video=False))
            return a
        if self.target_id is None:
            if self._visitor_in_range(None):  # a talk-spot chat nobody on the webcam is matched to
                self.in_range_seen = now
            return a
        people = self._people()
        match = next((p for p in people if p.get("id") == self.target_id), None)
        if match is None and self.target_box is not None:
            best = max(people, key=lambda p: iou(tuple(p["bbox"]), self.target_box), default=None)
            if best is not None and iou(tuple(best["bbox"]), self.target_box) >= self.cfg.reacquire_iou:
                log.info("target track %d is now %d", self.target_id, best["id"])
                self.target_id, match = int(best["id"]), best
        if match is not None:
            self.target, self.target_box, self.target_seen = match, tuple(match["bbox"]), now
            if match.get("group_size"):
                self.group_size = max(self.group_size, int(match["group_size"]))
        if self._visitor_in_range(match):
            self.in_range_seen = now
        return a

    def on_spot_speech(self, now: float) -> List[Action]:
        """Someone on the talk spot started speaking (any clothing)."""
        if self.state is not State.IDLE or not self.snapshot.get("spot_occupied"):
            return []
        if self.spot_since is not None and self.spot_since <= self.session_ended_at:
            return []  # the visitor we just said goodbye to is still standing there
        spot = [p for p in self._people() if p.get("at_spot")]
        if not spot:  # depth sees someone the webcam's estimate doesn't put on the spot
            spot = [p for p in self._people() if (p.get("distance") or 99) <= self.cfg.converse_range]
        target = min(spot, key=lambda p: p.get("distance") or 99, default=None)
        if target is not None:
            self.target_id, self.target_box, self.target = int(target["id"]), tuple(target["bbox"]), target
        self.target_seen = now
        return [OpenSession(None, prompts.SPOT_NOTE)] + self._enter(State.CONVERSE, now, "talk-spot speech")

    def on_opener_ready(self, now: float) -> List[Action]:
        self.opener_ready = True
        if self.state is State.BID and not self.bid_played:
            self.bid_played = True
            return [PlayOpener()]
        return []

    def on_bot_audio(self, seconds: float, now: float) -> List[Action]:
        self.speech_until = max(self.speech_until, now) + seconds
        if self.state is State.BID:
            self.bid_audio_seen = True
        if self.thinking:
            self.thinking = False
            return self._led_mode("speaking")
        return []

    def on_user_activity(self, now: float) -> List[Action]:
        self.last_user = now
        if self.state is State.OPEN:
            return self._enter(State.CONVERSE, now, "they replied")
        return []

    def on_user_text(self, text: str, now: float) -> List[Action]:
        a = self.on_user_activity(now)
        if self.state is State.CONVERSE and GOODBYE.search(text or ""):
            a += self._enter(State.CLOSE, now, "goodbye")
        return a

    def on_user_turn_end(self, now: float) -> List[Action]:
        self.last_user = now
        if self.state is State.CONVERSE:
            self.thinking = True
            return self._led_mode("thinking")
        return []

    def on_turn_complete(self, now: float) -> List[Action]:
        self.turn_done = True
        return []

    def on_interrupted(self, now: float) -> List[Action]:
        self.speech_until = now
        return [StopAudio()]

    def on_playback(self, state: str, now: float) -> List[Action]:
        playing = state == "playing"
        if self.robot_playing and not playing:
            self.speech_until = max(self.speech_until, now)
        self.robot_playing = playing
        if not playing and self.state is State.CONVERSE and not self.thinking:
            return self._led_mode("listening")
        return []

    def on_session_error(self, now: float) -> List[Action]:
        if self.state in (State.NOTICED, State.BID, State.OPEN):
            return self._drop(now, "session error", release=self.state is State.NOTICED)
        if self.state in (State.CONVERSE, State.CLOSE):
            return self._enter(State.COOLDOWN, now, "session error", clip="brain_offline")
        return []

    def tick(self, now: float) -> List[Action]:
        cfg, state = self.cfg, self.state
        in_state = now - self.entered_at
        lost = now - self.target_seen >= cfg.lost_s
        if state is State.NOTICED:
            if lost:
                return self._drop(now, "target left", release=True)
            if self._bid_ready(now):
                return self._enter(State.BID, now, "in range and facing")
            if in_state >= cfg.notice_timeout_s:
                return self._drop(now, "never came closer", release=True)
        elif state is State.BID:
            if not self.bid_played and in_state >= cfg.opener_wait_s:
                self.bid_played = True
                return [PlayClip("hey_green")]
            # a live (non pre-generated) invitation takes a moment to start: wait for its audio
            done = self.bid_audio_seen and in_state > 0.3 and not self.speaking(now)
            if self.bid_played and (done or in_state >= 6.0):
                return self._enter(State.OPEN, now, "invitation played")
        elif state is State.OPEN:
            # the spot filling up around the invitation is the visitor accepting it (the head
            # D435i can't tell who it is; the webcam's own at_spot estimate can)
            stepped_on = self.spot_since is not None and self.spot_since >= self.last_bid - cfg.spot_accept_margin_s
            if self.target.get("at_spot") or stepped_on:
                return self._enter(State.CONVERSE, now, "stepped onto the spot", begin=prompts.BEGIN_INSTRUCTION)
            facing_for = self.target.get("facing_for") or 0.0
            if not lost and in_state >= cfg.open_facing_s and facing_for >= in_state:
                return self._enter(State.CONVERSE, now, "kept facing", begin=prompts.BEGIN_INSTRUCTION)
            if lost or in_state >= cfg.open_timeout_s:
                return self._drop(now, "no response", release=False)
        elif state is State.CONVERSE:
            visit = now - self.visit_started
            if now - self.in_range_seen >= cfg.spot_empty_s:
                return self._enter(State.CLOSE, now, "nobody there", spoken=False)
            if visit >= cfg.max_visit_s:
                return self._enter(State.CLOSE, now, "4 min cap")
            if visit >= cfg.queue_after_s and self._queued(now):
                return self._enter(State.CLOSE, now, "someone is waiting")
            if cfg.silence_s and not self.speaking(now) and not self.thinking:
                if now - max(self.last_user, self.speech_until, self.entered_at) >= cfg.silence_s:
                    return self._enter(State.CLOSE, now, "long silence")
        elif state is State.CLOSE:
            if (self.turn_done and not self.speaking(now) and in_state > 0.5) or in_state >= cfg.close_timeout_s:
                return self._enter(State.COOLDOWN, now, self.end_reason)
        elif state is State.COOLDOWN:
            # let an apology clip finish before the next visitor can be invited
            if in_state >= cfg.cooldown_s and (not self.speaking(now) or in_state >= cfg.close_timeout_s):
                return self._enter(State.IDLE, now, "ready")
        return []
