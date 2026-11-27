"""Is the G1's own speaker working? Three tests, each printing the SDK's return code.

Run on the robot (no API key, no camera, the robot does not move):

    cd ~/g1-greeter && .venv/bin/python scripts/speaker_test.py

1. LED: the head light turns red, green, blue  -> the voice service hears us at all
2. TtsMaker: the robot's own text-to-speech says a sentence -> speaker, volume and routing work
3. PlayStream: our WAV clip, sent the way the greeter sends it -> our audio path works

Listen after each step and note which ones you heard. If 2 is heard and 3 is not, the problem is
in how we send audio; if neither is heard, it is the robot's speaker, volume or voice service.
"""
import argparse
import time
import wave

from unitree_sdk2py.core.channel import ChannelFactoryInitialize
from unitree_sdk2py.g1.audio.g1_audio_client import AudioClient


def code(ret):
    return ret[0] if isinstance(ret, tuple) else ret


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--iface", default="eth0")
    p.add_argument("--wav", default="models/clips/hello.wav")
    p.add_argument("--volume", type=int, default=70)
    args = p.parse_args()

    with wave.open(args.wav, "rb") as w:
        rate, channels, width = w.getframerate(), w.getnchannels(), w.getsampwidth()
        pcm = w.readframes(w.getnframes())
    print("clip: %s, %d Hz, %d channel(s), %d-bit, %.1f s" % (args.wav, rate, channels, width * 8, len(pcm) / 2.0 / rate))
    if (rate, channels, width) != (16000, 1, 2) or not pcm:
        raise SystemExit("the clip must be 16 kHz mono 16-bit with sound in it")

    ChannelFactoryInitialize(0, args.iface)
    audio = AudioClient()
    audio.SetTimeout(10.0)
    audio.Init()
    print("volume before:", audio.GetVolume())
    print("SetVolume(%d) ->" % args.volume, code(audio.SetVolume(args.volume)))
    print("volume after:", audio.GetVolume())

    print("\n1. LED test: watch the head light")
    for rgb in ((255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 255)):
        print("   LedControl%s ->" % (rgb,), code(audio.LedControl(*rgb)))
        time.sleep(0.6)

    print("\n2. TtsMaker test: listen now")
    print("   TtsMaker ->", code(audio.TtsMaker("Hello, this is the speaker test.", 0)))
    time.sleep(5)

    print("\n3. PlayStream test (our clip, in 0.5 s chunks like the greeter): listen now")
    stream = str(int(time.time() * 1000))
    step = 16000  # 0.5 s of 16 kHz 16-bit audio
    codes = []
    for i in range(0, len(pcm), step):
        codes.append(code(audio.PlayStream("greeter", stream, pcm[i:i + step])))
        time.sleep(0.4)
    print("   PlayStream codes:", codes)
    time.sleep(len(pcm) / 32000.0 + 1.0)
    print("   PlayStop ->", code(audio.PlayStop("greeter")))

    print("\nWhich did you hear?  2 and 3: speaker fine.  2 only: our audio path.  neither: robot speaker / volume / voice service.")
    print("A non-zero code above is the error to look up.")


if __name__ == "__main__":
    main()
