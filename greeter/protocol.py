"""Wire protocol between the robot bridge (PC2) and the laptop.

One WebSocket connection carries everything:

* Text frames are JSON control messages and events: ``{"type": ..., ...}``.
* Binary frames start with a one-byte tag followed by the payload:

  ======  =================  ==========================================
  tag     direction          payload
  ======  =================  ==========================================
  ``A``   robot -> laptop    mic audio, 16 kHz mono s16le
  ``V``   robot -> laptop    camera frame, JPEG (2 fps while talking)
  ``P``   laptop -> robot    speech to play, 16 kHz mono s16le
  ======  =================  ==========================================

Robot -> laptop JSON events
    ``hello``     sent on connect: ``robot``, ``mock``, ``audio_rate``.
    ``notice``    a green visitor worth noticing: ``track_id``, ``distance``,
                  ``bbox``, ``group_size``, ``jpeg_b64``.
    ``tracks``    about 5 Hz scene snapshot: ``people`` (see
                  ``greeter.vision.Person.to_dict``), ``crowd``, ``spot_occupied``.
    ``playback``  ``state`` is ``"playing"`` or ``"idle"``.

Laptop -> robot JSON commands
    ``triggers``  ``enabled``: allow or suppress new notice events.
    ``release``   ``track_id``: forget a notice that never became an invitation.
    ``stream``    ``mic`` / ``video``: start or stop media streaming.
    ``led``       ``rgb``: ``[r, g, b]`` 0..255.
    ``audio_stop`` drop queued speech (barge-in).

Recording for tuning happens in the dialogue process (``greeter.recorder``), not here.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Tuple  # noqa: F401

DEFAULT_PORT = 8765
AUDIO_RATE = 16000  # robot mic and speaker rate, both directions
SAMPLE_WIDTH = 2  # s16le

TAG_MIC = b"A"
TAG_VIDEO = b"V"
TAG_PLAY = b"P"
BINARY_TAGS = (TAG_MIC, TAG_VIDEO, TAG_PLAY)

MAX_MESSAGE_BYTES = 4 * 1024 * 1024


def encode_binary(tag: bytes, payload: bytes) -> bytes:
    if tag not in BINARY_TAGS:
        raise ValueError("unknown binary tag %r" % (tag,))
    return tag + payload


def decode_binary(message: bytes) -> Tuple[bytes, bytes]:
    if not message:
        raise ValueError("empty binary message")
    tag = message[:1]
    if tag not in BINARY_TAGS:
        raise ValueError("unknown binary tag %r" % (tag,))
    return tag, message[1:]


def encode_event(kind: str, **fields: Any) -> str:
    fields["type"] = kind
    return json.dumps(fields, separators=(",", ":"))


def decode_event(message: str) -> Dict[str, Any]:
    event = json.loads(message)
    if not isinstance(event, dict) or not isinstance(event.get("type"), str):
        raise ValueError("JSON message without a 'type' field")
    return event
