"""The interaction ladder: IDLE -> NOTICED -> BID -> OPEN -> CONVERSE -> CLOSE -> COOLDOWN."""

from greeter.dialogue import prompts
from greeter.dialogue.machine import (
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

BOX = [250, 100, 390, 400]


def p(tid=3, distance=1.8, facing_for=2.0, at_spot=False, group=None, present_for=5.0, bbox=BOX):
    return {"id": tid, "bbox": bbox, "distance": distance, "facing": True, "facing_for": facing_for,
            "at_spot": at_spot, "group": group, "present_for": present_for, "green": True}


def snap(*people, crowd=False, spot=False):
    return {"people": list(people), "crowd": crowd, "spot_occupied": spot or any(x["at_spot"] for x in people)}


NOTICE = {"track_id": 3, "bbox": BOX, "distance": 3.0, "group_size": 1}


def ticks(d, t0, t1, scene=None, dt=0.1):
    actions, t = [], t0
    while t <= t1 + 1e-9:
        if scene is not None:
            actions += d.on_tracks(scene, t)
        actions += d.tick(t)
        t += dt
    return actions


def noticed(cfg=None):
    d = Dialogue(cfg or DialogueConfig())
    d.start(0.0)
    d.on_notice(NOTICE, b"jpeg", 1.0)
    return d


def bid(cfg=None, opener=True):
    d = noticed(cfg)
    if opener:
        d.on_opener_ready(1.2)
    ticks(d, 1.0, 1.3, snap(p()))
    assert d.state is State.BID
    return d


def opened(cfg=None):
    d = bid(cfg)
    d.on_bot_audio(1.5, 1.3)  # the opener plays
    ticks(d, 1.4, 3.0, snap(p(facing_for=0.0)))
    assert d.state is State.OPEN
    return d


def conversing(cfg=None):
    d = opened(cfg)
    d.on_user_activity(3.1)
    assert d.state is State.CONVERSE
    return d


# --- IDLE / NOTICED -------------------------------------------------------------


def test_start_idle_breathing_and_armed():
    d = Dialogue()
    a = d.start(0.0)
    assert d.state is State.IDLE and EnableTriggers(True) in a and LedMode("idle") in a


def test_notice_opens_warm_session_and_prepares_opener():
    d = Dialogue()
    d.start(0.0)
    a = d.on_notice(NOTICE, b"jpeg", 1.0)
    assert d.state is State.NOTICED
    assert EnableTriggers(False) in a and LedMode("noticed") in a
    assert OpenSession(b"jpeg", prompts.scene_note(3.0, 1)) in a
    assert PrepareOpener(b"jpeg", prompts.opener_instruction(1)) in a


def test_group_gets_a_group_opener():
    d = Dialogue()
    d.start(0.0)
    a = d.on_notice(dict(NOTICE, group_size=3), b"j", 1.0)
    assert PrepareOpener(b"j", prompts.opener_instruction(3)) in a
    assert "the group" in prompts.opener_instruction(3)


def test_notice_while_busy_is_released():
    d = noticed()
    assert d.on_notice(dict(NOTICE, track_id=9), b"j", 2.0) == [Release(9)]


def test_no_bid_while_too_far_or_not_facing_or_crowded():
    d = noticed()
    ticks(d, 1.0, 3.0, snap(p(distance=3.0)))
    ticks(d, 3.1, 4.0, snap(p(facing_for=0.5)))
    ticks(d, 4.1, 5.0, snap(p(), crowd=True))
    assert d.state is State.NOTICED


def test_noticed_target_leaving_is_released_silently():
    d = noticed()
    a = ticks(d, 1.0, 4.5, snap())
    assert d.state is State.IDLE and Release(3) in a and not any(isinstance(x, (PlayOpener, PlayClip)) for x in a)


def test_noticed_but_never_closer_times_out():
    d = noticed(DialogueConfig(notice_timeout_s=5.0))
    a = ticks(d, 1.0, 6.5, snap(p(distance=4.0)))
    assert d.state is State.IDLE and Release(3) in a


# --- BID / OPEN ---------------------------------------------------------------------


def test_bid_plays_ready_opener_immediately():
    d = noticed()
    d.on_opener_ready(1.1)
    a = ticks(d, 1.2, 1.3, snap(p()))
    assert d.state is State.BID and PlayOpener() in a and LedMode("speaking") in a


def test_opener_arriving_during_bid_is_played():
    d = bid(opener=False)
    assert d.on_opener_ready(1.5) == [PlayOpener()]


def test_canned_clip_when_opener_not_ready_within_1s():
    d = bid(opener=False)
    a = ticks(d, 1.4, 2.4, snap(p()))
    assert PlayClip("hey_there") in a
    assert d.on_opener_ready(2.6) == []  # too late: not played on top of the clip


def test_green_mode_keeps_the_green_wording_and_clip():
    d = bid(DialogueConfig(invite="green"), opener=False)
    assert ticks(d, 1.4, 2.4, snap(p())) == [PlayClip("hey_green")]
    d = Dialogue(DialogueConfig(invite="green"))
    d.start(0.0)
    a = d.on_notice(NOTICE, b"jpeg", 1.0)
    note = next(x for x in a if isinstance(x, OpenSession)).note
    instruction = next(x for x in a if isinstance(x, PrepareOpener)).instruction
    assert "wearing green" in note and "green item" in instruction


def test_anyone_mode_names_whatever_they_wear():
    d = Dialogue()
    d.start(0.0)
    a = d.on_notice(NOTICE, b"jpeg", 1.0)
    note = next(x for x in a if isinstance(x, OpenSession)).note
    instruction = next(x for x in a if isinstance(x, PrepareOpener)).instruction
    assert "green" not in note and "wear or carry" in instruction and "talk spot" in instruction


def test_roam_invites_them_over_instead_of_to_the_talk_spot():
    d = Dialogue(DialogueConfig(roam=True))
    d.start(0.0)
    instruction = next(x for x in d.on_notice(NOTICE, b"jpeg", 1.0) if isinstance(x, PrepareOpener)).instruction
    assert "come over" in instruction and "talk spot" not in instruction


def test_bid_waits_for_live_invitation_audio():
    d = bid()
    ticks(d, 1.4, 3.0, snap(p()))
    assert d.state is State.BID  # no audio yet (live backends need a moment)
    d.on_bot_audio(1.0, 3.0)
    ticks(d, 3.1, 4.2, snap(p()))
    assert d.state is State.OPEN


def test_global_cooldown_between_bids():
    d = opened()
    ticks(d, 3.1, 8.0, snap(p(facing_for=0.0)))  # no response: dropped
    assert d.state is State.IDLE
    d.on_notice(dict(NOTICE, track_id=4), b"j", 8.1)
    d.on_opener_ready(8.2)
    ticks(d, 8.2, 9.0, snap(p(tid=4)))
    assert d.state is State.NOTICED  # 8 s since the last bid at 1.3 not over yet
    ticks(d, 9.1, 9.5, snap(p(tid=4)))
    assert d.state is State.BID


def test_open_reply_starts_conversation():
    d = opened()
    a = d.on_user_activity(3.1)
    assert d.state is State.CONVERSE and Stream(mic=True, video=True) in a


def test_open_stepping_on_spot_starts_conversation():
    d = opened()
    a = ticks(d, 3.1, 3.2, snap(p(distance=1.0, at_spot=True, facing_for=0.0)))
    assert d.state is State.CONVERSE and Begin(prompts.BEGIN_INSTRUCTION) in a


def test_open_keep_facing_starts_conversation():
    d = opened()
    t0 = d.entered_at
    a, t = [], t0
    while t < t0 + 1.7:
        a += d.on_tracks(snap(p(facing_for=t - t0 + 1.0)), t)
        a += d.tick(t)
        t += 0.1
    assert d.state is State.CONVERSE and Begin(prompts.BEGIN_INSTRUCTION) in a


def test_open_no_response_drops_silently_and_never_reinvites():
    d = opened()
    a = ticks(d, 3.1, 8.0, snap(p(facing_for=0.0)))
    assert d.state is State.IDLE
    assert not any(isinstance(x, (SendText, PlayClip, PlayOpener)) for x in a) and CloseSession() in a
    assert Release(3) not in a  # stays "already invited" on the robot side too
    assert d.on_notice(NOTICE, b"j", 600.0) == []  # same person within 30 min


# --- CONVERSE / CLOSE / COOLDOWN ----------------------------------------------------


def test_thinking_and_speaking_leds():
    d = conversing()
    assert d.on_user_turn_end(4.0) == [LedMode("thinking")]
    assert d.on_bot_audio(1.0, 4.5) == [LedMode("speaking")]
    d.on_playback("playing", 4.5)
    assert d.on_playback("idle", 5.5) == [LedMode("listening")]


def test_goodbye_closes_with_takeaway():
    d = conversing()
    a = d.on_user_text("ok thanks, bye!", 5.0)
    assert d.state is State.CLOSE and SendText(prompts.CLOSE_INSTRUCTION) in a
    d.on_bot_audio(2.0, 5.5)
    d.on_turn_complete(5.6)
    ticks(d, 5.7, 7.4, snap(p()))
    assert d.state is State.CLOSE  # still speaking
    a = ticks(d, 7.6, 7.7, snap(p()))
    assert d.state is State.COOLDOWN and CloseSession() in a and StopAudio() in a
    a = ticks(d, 7.8, 10.0)
    assert d.state is State.IDLE and EnableTriggers(True) in a


def test_visitor_leaving_closes_quietly():
    d = conversing()
    a = ticks(d, 3.2, 8.0, snap())
    assert d.state is State.COOLDOWN and not any(isinstance(x, SendText) for x in a)
    assert ("converse", "close", "nobody there") in d.transitions


def test_passer_by_does_not_keep_the_visit_alive():
    d = conversing()
    ticks(d, 3.2, 8.0, snap(p(tid=50, distance=1.5, bbox=[0, 0, 60, 300])))
    assert d.state is State.COOLDOWN


def test_someone_queueing_after_two_minutes():
    d = conversing(DialogueConfig(silence_s=0))
    other = p(tid=7, distance=2.5, present_for=40.0, bbox=[500, 100, 600, 400])
    ticks(d, 3.2, 100.0, snap(p(), other), dt=1.0)
    assert d.state is State.CONVERSE  # under 2 min of chat
    ticks(d, 101.0, 125.0, snap(p(), other), dt=1.0)
    assert d.state is State.CLOSE and d.end_reason == "someone is waiting"


def test_four_minute_cap():
    d = conversing(DialogueConfig(silence_s=0))
    ticks(d, 3.2, 245.0, snap(p()), dt=1.0)
    assert d.state is State.CLOSE and d.end_reason == "4 min cap"


def test_long_silence_safety_net():
    d = conversing(DialogueConfig(silence_s=15.0))
    ticks(d, 3.2, 20.0, snap(p()), dt=0.5)
    assert d.state is State.CLOSE and d.end_reason == "long silence"


def test_follows_target_across_tracker_id_switch():
    d = conversing()
    shifted = [BOX[0] + 10, BOX[1], BOX[2] + 10, BOX[3]]
    ticks(d, 3.2, 9.0, snap(p(tid=17, bbox=shifted)))
    assert d.state is State.CONVERSE and d.target_id == 17


def test_session_error_mid_conversation_apologises():
    d = conversing()
    a = d.on_session_error(5.0)
    assert PlayClip("brain_offline") in a and d.state is State.COOLDOWN


def test_apology_is_queued_after_the_cooldown_stops_the_audio():
    # regression: the clip came before the cooldown's StopAudio and was cut off at once
    d = conversing()
    a = d.on_session_error(5.0)
    assert a.index(StopAudio()) < a.index(PlayClip("brain_offline")) < a.index(CloseSession())


def test_cooldown_waits_for_the_apology_to_finish():
    d = conversing(DialogueConfig(cooldown_s=2.0))
    d.on_session_error(5.0)
    d.on_bot_audio(3.5, 5.0)  # the apology clip plays until 8.5
    ticks(d, 5.1, 8.0)
    assert d.state is State.COOLDOWN
    ticks(d, 8.1, 9.0)
    assert d.state is State.IDLE


def test_cooldown_is_not_held_by_audio_it_stopped():
    d = conversing(DialogueConfig(cooldown_s=2.0))
    d.on_bot_audio(30.0, 3.2)  # a long reply, cut off when the visitor walks away
    ticks(d, 3.2, 10.0, snap())
    assert ("converse", "close", "nobody there") in d.transitions and d.state is State.IDLE


# --- talk spot ---------------------------------------------------------------------


def test_spot_listening_follows_occupancy():
    d = Dialogue()
    d.start(0.0)
    assert d.on_tracks(snap(p(distance=1.0, at_spot=True)), 1.0) == [Stream(mic=True, video=False)]
    assert d.on_tracks(snap(), 2.0) == [Stream(mic=False, video=False)]


def test_anyone_speaking_on_the_spot_starts_a_conversation():
    d = Dialogue()
    d.start(0.0)
    d.on_tracks(snap(p(tid=8, distance=1.0, at_spot=True)), 1.0)
    a = d.on_spot_speech(1.5)
    assert d.state is State.CONVERSE and OpenSession(None, prompts.SPOT_NOTE) in a
    assert d.target_id == 8


def test_spot_speech_ignored_when_spot_empty():
    d = Dialogue()
    d.start(0.0)
    assert d.on_spot_speech(1.0) == []


# --- groups of rules added for the open day ---------------------------------------


def chatting(d, t0, t1, every=5.0, scene=None):
    """Keep a chat alive from t0 to t1: the visitor speaks briefly every ``every`` seconds."""
    actions, t, next_turn = [], t0, t0
    while t <= t1 + 1e-9:
        if t >= next_turn:
            actions += d.on_user_activity(t) + d.on_user_turn_end(t)
            next_turn += every
        actions += d.on_tracks(scene or snap(p()), t) + d.tick(t)
        t += 0.1
    return actions


def test_long_talker_gets_one_polite_cut_in():
    d = conversing()
    a, t = [], 4.0
    while t < 30.0:
        if abs(t - round(t)) < 1e-6:
            a += d.on_user_activity(t)  # keep-alive every second while their turn stays open
        a += d.on_tracks(snap(p()), t) + d.tick(t)
        t = round(t + 0.1, 1)
    cut_ins = [x for x in a if isinstance(x, CutIn)]
    assert cut_ins == [CutIn(prompts.CUT_IN_INSTRUCTION)]
    assert d.state is State.CONVERSE
    d.on_user_turn_end(30.0)  # the cut-in closed their turn
    assert d.talk_since is None and not d.cut_in_done


def test_a_transcript_after_the_turn_is_not_more_talking():
    d = conversing()
    d.on_user_activity(4.0)
    d.on_user_turn_end(5.0)
    d.on_user_text("so what does this robot do?", 5.5)  # transcripts arrive after the turn
    a = ticks(d, 5.6, 30.0, snap(p()))
    assert not any(isinstance(x, CutIn) for x in a)


def test_wrap_up_note_after_90_seconds():
    d = conversing()
    a = chatting(d, 3.2, 100.0)
    assert [x for x in a if isinstance(x, AddNote)] == [AddNote(prompts.WRAP_UP_NOTE)]
    assert d.state is State.CONVERSE


def test_robot_goodbye_ends_the_chat_without_another_line():
    d = conversing()
    chatting(d, 3.2, 29.9)
    d.on_bot_audio(2.0, 30.0)
    d.on_turn_complete(30.1, "Lovely chatting with you. Enjoy the open day, bye!")
    ticks(d, 30.2, 31.8, snap(p()))
    assert d.state is State.CONVERSE  # still saying it
    a = ticks(d, 32.1, 32.3, snap(p()))
    assert d.state is State.COOLDOWN and ("converse", "close", "robot said goodbye") in d.transitions
    assert not any(isinstance(x, SendText) for x in a)


def test_an_early_bye_from_the_robot_does_not_end_the_chat():
    d = conversing()
    d.on_turn_complete(5.0, "Bye-bye boring robots, hello me!")
    assert not d.bot_goodbye


def walking(scene):
    return dict(scene, walking=True)


def test_walking_drops_an_invitation_and_blocks_new_ones():
    d = noticed()
    a = d.on_tracks(walking(snap(p())), 1.5)
    assert d.state is State.IDLE and ("noticed", "idle", "robot walking") in d.transitions and Release(3) in a
    assert d.on_notice(dict(NOTICE, track_id=7), b"j", 2.0) == [Release(7)]
    d.on_tracks(snap(p(tid=7)), 3.0)  # standing again
    d.on_notice(dict(NOTICE, track_id=7), b"j", 3.1)
    assert d.state is State.NOTICED


def test_walking_on_during_a_chat_closes_it():
    d = conversing()
    ticks(d, 3.2, 4.0, snap(p()))
    a = ticks(d, 4.1, 6.5, walking(snap(p())))
    assert d.state is State.CLOSE and ("converse", "close", "robot walked on") in d.transitions
    assert SendText(prompts.CLOSE_INSTRUCTION) in a


def test_walking_stops_talk_spot_listening():
    d = Dialogue()
    d.start(0.0)
    a = d.on_tracks(walking(snap(p(distance=1.0, at_spot=True))), 1.0)
    assert Stream(mic=True, video=False) not in a
    assert d.on_spot_speech(1.5) == []
