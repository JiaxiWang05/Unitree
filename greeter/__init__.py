"""Proactive greeter for the Unitree G1 EDU.

Default deployment: one process on the G1's Jetson Orin NX (PC2) runs the
camera, person detector and green trigger (``greeter.robot``), the dialogue
state machine (``greeter.dialogue``) and the conversation backend
(``greeter.backends``: OpenAI Realtime by default). ``python -m greeter``.

An optional WebSocket bridge (``greeter.robot.server``) splits the robot
hardware from the dialogue so a laptop can run the latter.
"""

__version__ = "0.2.0"
