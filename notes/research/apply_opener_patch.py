"""Apply the opener-randomisation change to a copy of the greeter repo (exact, one-match replacements)."""
import sys
from pathlib import Path

root = Path(sys.argv[1])


def sub(rel, old, new):
    path = root / rel
    text = path.read_text()
    assert text.count(old) == 1, (rel, old[:60], text.count(old))
    path.write_text(text.replace(old, new))


# --- prompts.py ---------------------------------------------------------------
sub("greeter/dialogue/prompts.py",
'''def opener_instruction(group_size: int = 1) -> str:
    who = "the group" if group_size > 1 else "them"
    return (''',
'''OPENER_CONDITIONS = ("personal", "generic")  # study arms; "personal" alone is the normal behaviour


def opener_instruction(group_size: int = 1, condition: str = "personal") -> str:
    who = "the group" if group_size > 1 else "them"
    if condition == "generic":
        return (
            "Invite %s over now, before they speak. At most 15 words. Do not mention their clothing, colours or "
            "anything else about them: give a friendly general invitation to stand on the green talk spot and "
            "say hi." % who
        )
    return (''')

sub("greeter/dialogue/prompts.py",
'''    "green item you mentioned earlier, then say goodbye. Do not ask a question."
)''',
'''    "green item you mentioned earlier, then say goodbye. Do not ask a question."
)

CLOSE_INSTRUCTION_GENERIC = (
    "Wrap up now in one short line: one highlight of the stand worth seeing, then say goodbye. "
    "Do not ask a question."
)''')

# --- clips.py -----------------------------------------------------------------
sub("greeter/clips.py",
'''    "hey_green": "Hey, you in the green! Come and say hi!",
''',
'''    "hey_green": "Hey, you in the green! Come and say hi!",
    "hey_there": "Hi there! Come and stand on the green spot and say hi!",
''')

# --- machine.py ---------------------------------------------------------------
sub("greeter/dialogue/machine.py",
'''import logging
import re
''',
'''import logging
import random
import re
''')
sub("greeter/dialogue/machine.py",
"from typing import Any, Dict, List, Optional, Tuple\n",
"from typing import Any, Callable, Dict, List, Optional, Tuple\n")
sub("greeter/dialogue/machine.py",
'''    spot_accept_margin_s: float = 0.5  # spot filled from just before the invitation began = they accepted
''',
'''    spot_accept_margin_s: float = 0.5  # spot filled from just before the invitation began = they accepted
    conditions: Tuple[str, ...] = ("personal",)  # opener arms drawn per noticed visitor (prompts.OPENER_CONDITIONS)
    seed: Optional[int] = None  # randomisation seed (None: different every run)
''')
sub("greeter/dialogue/machine.py",
'''        self.end_reason = ""
        self._led = ""
''',
'''        self.end_reason = ""
        self._led = ""
        self.visit_no = 0
        self.condition = ""  # opener arm of the current visit ("" for talk-spot chats)
        self.rng = random.Random(self.cfg.seed)
        self._deck: List[str] = []
        self.on_transition: Optional[Callable[[Dict[str, Any]], None]] = None  # the runner logs these
''')
sub("greeter/dialogue/machine.py",
'''    def _led_mode(self, mode: str) -> List[Action]:''',
'''    def _draw_condition(self) -> str:
        """Shuffled blocks: within every 2 x len(conditions) visitors, each arm comes up equally often."""
        if not self._deck:
            self._deck = list(self.cfg.conditions) * 2
            self.rng.shuffle(self._deck)
        return self._deck.pop()

    def _led_mode(self, mode: str) -> List[Action]:''')
sub("greeter/dialogue/machine.py",
'''        self.transitions.append((self.state.value, state.value, reason))
''',
'''        self.transitions.append((self.state.value, state.value, reason))
        if self.on_transition is not None:
            self.on_transition({"visit": self.visit_no, "condition": self.condition, "from": self.state.value, "to": state.value, "reason": reason})
''')
sub("greeter/dialogue/machine.py",
"PrepareOpener(kw[\"jpeg\"], prompts.opener_instruction(self.group_size))]",
"PrepareOpener(kw[\"jpeg\"], prompts.opener_instruction(self.group_size, self.condition))]")
sub("greeter/dialogue/machine.py",
'''            a += [Stream(mic=False, video=False), SendText(prompts.CLOSE_INSTRUCTION)] + self._led_mode("speaking")''',
'''            close = prompts.CLOSE_INSTRUCTION_GENERIC if self.condition == "generic" else prompts.CLOSE_INSTRUCTION
            a += [Stream(mic=False, video=False), SendText(close)] + self._led_mode("speaking")''')
sub("greeter/dialogue/machine.py",
'''        self.group_size = int(event.get("group_size") or 1)
        self.target = {"id": tid, "distance": event.get("distance"), "facing_for": 0.0}
''',
'''        self.group_size = int(event.get("group_size") or 1)
        self.target = {"id": tid, "distance": event.get("distance"), "facing_for": 0.0}
        self.visit_no += 1
        self.condition = self._draw_condition()
        log.info("visit %d: %s opener", self.visit_no, self.condition)
''')
sub("greeter/dialogue/machine.py",
'''        self.target_seen = now
        return [OpenSession(None, prompts.SPOT_NOTE)]''',
'''        self.target_seen = now
        self.visit_no += 1
        self.condition = ""  # not invited: no opener arm
        return [OpenSession(None, prompts.SPOT_NOTE)]''')
sub("greeter/dialogue/machine.py",
'''                return [PlayClip("hey_green")]''',
'''                return [PlayClip("hey_there" if self.condition == "generic" else "hey_green")]''')

# --- app.py -------------------------------------------------------------------
sub("greeter/dialogue/app.py",
'''        self.dialogue = Dialogue(dialogue_cfg)
''',
'''        self.dialogue = Dialogue(dialogue_cfg)
        self.dialogue.on_transition = lambda record: self.recorder.trace("state", record)  # day-long funnel log
''')
sub("greeter/dialogue/app.py",
'''        self.recorder.start_visit(label)
''',
'''        self.recorder.start_visit(label)
        self.recorder.event("visit", {"visit": self.dialogue.visit_no, "condition": self.dialogue.condition})
''')
sub("greeter/dialogue/app.py",
'''        elif name == "hey_green":''',
'''        elif name in ("hey_green", "hey_there"):''')

# --- cli.py -------------------------------------------------------------------
sub("greeter/cli.py",
'''    d.add_argument("--no-transcripts",''',
'''    d.add_argument("--conditions", default=env("GREETER_CONDITIONS", "personal"), help="study: opener arms drawn per visitor, e.g. personal,generic")
    d.add_argument("--seed", type=int, default=env("GREETER_SEED"), help="randomisation seed (default: different every run)")
    d.add_argument("--no-transcripts",''')
sub("greeter/cli.py",
'''    from greeter.dialogue.machine import DialogueConfig

    return DialogueConfig(max_visit_s=args.max_visit, silence_s=args.silence)''',
'''    from greeter.dialogue.machine import DialogueConfig
    from greeter.dialogue.prompts import OPENER_CONDITIONS

    conditions = tuple(c.strip() for c in args.conditions.split(",") if c.strip())
    if not conditions or not set(conditions) <= set(OPENER_CONDITIONS):
        raise SystemExit("--conditions: a comma-separated list of %s" % ", ".join(OPENER_CONDITIONS))
    seed = int(args.seed) if args.seed is not None else None
    return DialogueConfig(max_visit_s=args.max_visit, silence_s=args.silence, conditions=conditions, seed=seed)''')

# --- tests --------------------------------------------------------------------
sub("tests/test_dialogue.py",
'''def test_notice_while_busy_is_released():''',
'''def test_generic_arm_never_names_clothing():
    d = Dialogue(DialogueConfig(conditions=("generic",)))
    d.start(0.0)
    a = d.on_notice(NOTICE, b"jpeg", 1.0)
    assert d.condition == "generic" and PrepareOpener(b"jpeg", prompts.opener_instruction(1, "generic")) in a
    assert "Do not mention their clothing" in prompts.opener_instruction(1, "generic")
    ticks(d, 1.0, 1.3, snap(p()))
    assert d.state is State.BID
    assert PlayClip("hey_there") in ticks(d, 1.4, 2.2, snap(p()))  # opener late: neutral fallback


def test_generic_arm_closes_without_a_clothing_callback():
    d = conversing(DialogueConfig(conditions=("generic",)))
    a = d.on_user_text("thanks, bye", 4.0)
    assert d.state is State.CLOSE and SendText(prompts.CLOSE_INSTRUCTION_GENERIC) in a


def test_conditions_are_drawn_in_shuffled_blocks_and_logged():
    d = Dialogue(DialogueConfig(conditions=("personal", "generic"), seed=7))
    records = []
    d.on_transition = records.append
    d.start(0.0)
    arms, t = [], 1.0
    for i in range(8):
        d.on_notice(dict(NOTICE, track_id=10 + i), b"j", t)
        arms.append(d.condition)
        d.tick(t + 3.5)  # they walked off: back to idle
        assert d.state is State.IDLE
        t += 5.0
    assert arms[:4].count("generic") == 2 and arms[4:].count("generic") == 2
    noticed = [r for r in records if r["to"] == "noticed"]
    assert [r["condition"] for r in noticed] == arms and [r["visit"] for r in noticed] == list(range(1, 9))
    same = Dialogue(DialogueConfig(conditions=("personal", "generic"), seed=7))
    assert [same._draw_condition() for _ in range(8)] == arms  # the seed reproduces the sequence


def test_notice_while_busy_is_released():''')
sub("tests/test_e2e.py",
'''    assert any(e["kind"] == "robot" for e in events)
    assert (day / "trace.jsonl").stat().st_size > 0
''',
'''    assert any(e["kind"] == "robot" for e in events)
    assert events[0] == dict(events[0], kind="visit", data={"visit": 1, "condition": "personal"})
    trace = [json.loads(line) for line in (day / "trace.jsonl").read_text().splitlines()]
    funnel = [(r["data"]["from"], r["data"]["to"]) for r in trace if r["kind"] == "state"]
    assert funnel[: len(FULL_VISIT)] == FULL_VISIT
''')
print("patched", root)
