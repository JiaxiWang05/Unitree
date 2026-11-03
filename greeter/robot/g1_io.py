"""Real G1 hardware via unitree_sdk2_python: speaker, mic multicast, LED, battery. No motion.

Audio plumbing follows unitree_sdk2's g1_audio_client_example and
namanbansal013/unitree-openai-voice (MIT, (c) 2026 Naman Bansal):

* mic: UDP multicast 239.168.123.161:5555, raw 16 kHz mono s16le, joined on
  PC2's own address (192.168.123.164). It carries real audio only while the
  Unitree voice assistant is in wake-up mode (remote: L1+L2; app: Device > Data >
  Audio > Voice assistant); otherwise packets stop or arrive all zeros (Unitree
  VuiClient docs, unitree_sdk2_python PR #133);
* speaker: ``AudioClient.PlayStream(app_name, stream_id, pcm)`` with one
  ``stream_id`` per utterance and ``PlayStop`` for barge-in.

Tier 1 upgrade: ``mic_device`` / ``speaker_device`` switch either side to a USB
mic (e.g. a Lark M2 receiver) or a USB-C DAC through ALSA/PortAudio.

This module never imports the arm, waist or locomotion clients.
"""

from __future__ import annotations

import logging
import os
import socket
import struct
import threading
import time
from typing import Optional

from greeter.audio import is_flat
from greeter.robot.io_base import BYTES_PER_S, RGB, MicCallback, RobotIO, SoundDeviceAudio

log = logging.getLogger(__name__)

MIC_GROUP = "239.168.123.161"
MIC_PORT = 5555
PC2_IP = "192.168.123.164"
APP_NAME = "greeter"
BMS_TOPIC = os.environ.get("GREETER_BMS_TOPIC", "rt/lf/bmsstate")  # unverified on the G1: check on the robot
WAKE_UP_HINT = "set the Unitree voice assistant to wake-up mode (remote: L1+L2; app: Device > Data > Audio > Voice assistant)"


class MicWatch:
    """Warns once when the mic multicast stops, and once when it keeps arriving flat (all zeros),
    which is what the robot sends while the voice assistant is not in wake-up mode."""

    def __init__(self, now: float, after_s: float = 5.0) -> None:
        self.after_s = after_s
        self.last_packet = now
        self.flat_since: Optional[float] = None
        self.warned_missing = self.warned_flat = False

    def timeout(self, now: float) -> Optional[str]:
        if not self.warned_missing and now - self.last_packet > self.after_s:
            self.warned_missing = True
            return "mic: no multicast audio for %.0f s: %s, and check --local-ip" % (self.after_s, WAKE_UP_HINT)
        return None

    def packet(self, pcm: bytes, now: float) -> Optional[str]:
        self.last_packet, self.warned_missing = now, False
        if not is_flat(pcm):
            self.flat_since, self.warned_flat = None, False
            return None
        if self.flat_since is None:
            self.flat_since = now
        if not self.warned_flat and now - self.flat_since >= self.after_s:
            self.warned_flat = True
            return "mic: multicast audio has been all zeros for %.0f s, so the robot's mic is muted: %s" % (self.after_s, WAKE_UP_HINT)
        return None


class G1RobotIO(RobotIO):
    def __init__(
        self,
        iface: str = "eth0",
        local_ip: str = PC2_IP,
        volume: Optional[int] = 80,
        chunk_s: float = 0.2,
        max_lead_s: float = 1.5,
        domain_id: int = 0,
        mic_device: Optional[str] = None,
        speaker_device: Optional[str] = None,
        battery: bool = True,
    ) -> None:
        from unitree_sdk2py.core.channel import ChannelFactoryInitialize
        from unitree_sdk2py.g1.audio.g1_audio_client import AudioClient

        ChannelFactoryInitialize(domain_id, iface)
        self._audio_lock = threading.Lock()  # one RPC at a time on the voice service
        self.audio = AudioClient()
        self.audio.SetTimeout(10.0)
        self.audio.Init()
        if volume is not None:
            self.audio.SetVolume(int(volume))
        super().__init__()

        self.local_ip = local_ip
        self._usb = None
        if mic_device or speaker_device:
            self._usb = SoundDeviceAudio(mic_device, speaker_device, use_input=bool(mic_device), use_output=bool(speaker_device))
        self._chunk_bytes = int(chunk_s * BYTES_PER_S) & ~1
        self._max_lead = max_lead_s
        self._cond = threading.Condition()
        self._buf = bytearray()
        self._stream_id: Optional[str] = None
        self._until = 0.0  # monotonic time at which audio already pushed finishes
        self._generation = 0  # bumped by stop_playback so in-flight chunks get stopped
        self._closed = False
        self._battery: dict = {}
        self._bms_sub = None
        if battery:
            self._subscribe_battery()
        if speaker_device is None:
            self._speaker = threading.Thread(target=self._speaker_loop, name="g1-speaker", daemon=True)
            self._speaker.start()

    # --- battery (read only) ---------------------------------------------
    def _subscribe_battery(self) -> None:
        try:
            from unitree_sdk2py.core.channel import ChannelSubscriber

            try:
                from unitree_sdk2py.idl.unitree_hg.msg.dds_ import BmsState_
            except ImportError:
                from unitree_sdk2py.idl.unitree_go.msg.dds_ import BmsState_

            def on_bms(msg) -> None:
                self._battery = {
                    "soc": getattr(msg, "soc", None),
                    "current": getattr(msg, "current", None),
                    "t": time.monotonic(),
                }

            self._bms_sub = ChannelSubscriber(BMS_TOPIC, BmsState_)
            self._bms_sub.Init(on_bms, 10)
        except Exception as exc:
            log.warning("battery logging off (%s on %s): %s", "BmsState_", BMS_TOPIC, exc)

    def status(self) -> dict:
        bat = dict(self._battery)
        if bat and time.monotonic() - bat.pop("t", 0) > 30:
            return {"battery": "stale"}
        return {"battery_soc": bat.get("soc"), "battery_current": bat.get("current")} if bat else {}

    # --- mic -------------------------------------------------------------
    def start(self, on_mic: MicCallback) -> None:
        if self._usb is not None:
            self._usb.start(on_mic if self._usb.use_input else None)
        if self._usb is None or not self._usb.use_input:
            threading.Thread(target=self._mic_loop, args=(on_mic,), name="g1-mic", daemon=True).start()

    def _mic_loop(self, on_mic: MicCallback) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, "SO_REUSEPORT"):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        sock.bind(("", MIC_PORT))
        mreq = struct.pack("=4s4s", socket.inet_aton(MIC_GROUP), socket.inet_aton(self.local_ip))
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        sock.settimeout(1.0)
        log.info("mic: joined %s:%d on %s", MIC_GROUP, MIC_PORT, self.local_ip)
        watch = MicWatch(time.monotonic())
        while not self._closed:
            try:
                data, _ = sock.recvfrom(65536)
            except socket.timeout:
                warning = watch.timeout(time.monotonic())
                if warning:
                    log.warning(warning)
                continue
            if len(data) % 2:
                data = data[:-1]
            if data:
                warning = watch.packet(data, time.monotonic())
                if warning:
                    log.warning(warning)
                on_mic(data)
        sock.close()

    # --- speaker ---------------------------------------------------------
    def play(self, pcm: bytes) -> None:
        if self._usb is not None and self._usb.use_output:
            self._usb.play(pcm)
            return
        with self._cond:
            self._buf.extend(pcm)
            self._cond.notify()

    def stop_playback(self) -> None:
        if self._usb is not None and self._usb.use_output:
            self._usb.stop()
            return
        with self._cond:
            self._buf.clear()
            self._stream_id = None
            self._until = 0.0
            self._generation += 1
        self._play_stop()

    def playing_until(self) -> float:
        if self._usb is not None and self._usb.use_output:
            return self._usb.playing_until()
        with self._cond:
            if self._buf:
                return max(self._until, time.monotonic()) + len(self._buf) / float(BYTES_PER_S)
            return self._until

    def _play_stop(self) -> None:
        try:
            with self._audio_lock:
                self.audio.PlayStop(APP_NAME)
        except Exception:
            log.exception("PlayStop failed")

    def _speaker_loop(self) -> None:
        while True:
            with self._cond:
                while True:
                    if self._closed:
                        return
                    now = time.monotonic()
                    if self._stream_id is not None and not self._buf and now > self._until + 0.5:
                        self._stream_id = None  # utterance finished: next speech gets a new stream
                    # stay at most max_lead seconds ahead of the robot's playback
                    if self._buf and self._until - now < self._max_lead:
                        break
                    self._cond.wait(0.05)
                if len(self._buf) < self._chunk_bytes:
                    self._cond.wait(0.04)  # give the network a moment to fill a whole chunk
                chunk = bytes(self._buf[: self._chunk_bytes])
                del self._buf[: self._chunk_bytes]
                if not chunk:
                    continue
                now = time.monotonic()
                if self._stream_id is None:
                    self._stream_id = str(int(time.time() * 1000))
                stream_id, generation = self._stream_id, self._generation
                self._until = max(self._until, now) + len(chunk) / float(BYTES_PER_S)
            try:
                with self._audio_lock:
                    ret = self.audio.PlayStream(APP_NAME, stream_id, chunk)
                code = ret[0] if isinstance(ret, tuple) else ret
                if code not in (0, None):
                    log.warning("PlayStream returned %s", code)
            except Exception:
                log.exception("PlayStream failed")
            if generation != self._generation:
                self._play_stop()  # stop_playback() ran while this chunk was in flight

    # --- LED -------------------------------------------------------------
    def _set_led(self, rgb: RGB) -> None:
        with self._audio_lock:
            self.audio.LedControl(*rgb)

    def close(self) -> None:
        with self._cond:
            self._closed = True
            self._cond.notify_all()
        self._play_stop()
        if self._usb is not None:
            self._usb.close()
        super().close()
