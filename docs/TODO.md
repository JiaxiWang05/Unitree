# To do

Status after the first robot session (11 November 2026). No OpenAI API key yet. The robot hung on the gantry the whole time and never moved.

## Done on 11 November

- Lab Ubuntu laptop on the robot by cable: manual address `192.168.123.99/24` (a NetworkManager connection named `g1`), SSH to `unitree@192.168.123.164` works.
- Backup of the robot computer copied to the laptop (`~/g1-backup`): `/etc`, the home folder (665 MB), the apt and pip package lists.
- USB webcam (Trust, AONI chip) through a USB-C hub on the neck panel: 640x480 frames. It points at the floor and needs tilting up.
- The webcam's built-in mic records clearly with `arecord` (ALSA card 0 on the robot).
- Unitree Explore app: voice assistant in wake-up mode. chat_go was switched back on for a test; switch it off again.

## Problems found

- [ ] **Built-in robot mic sends only zeros.** The multicast `239.168.123.161:5555` delivers 5 s of packets (163840 bytes), all silent, in wake-up mode with chat_go both on and off. Pressing L1 + L2 after setting the mode in the app toggles it off again. To try: speak the wake word first, keypad conversation mode, the firmware version in the app, [g1-audio-driver](https://github.com/experientialtech/g1-audio-driver).
- [ ] **Use the webcam mic meanwhile.** `GREETER_MIC_DEVICE` goes through `SoundDeviceAudio`, but `install.sh` does not install `sounddevice` (only `requirements/mock.txt` lists it). Add it to `install.sh`, find the device name with `arecord -l`, set `GREETER_MIC_DEVICE` in `greeter.env`, and check the level (the test clips peaked near full scale, so a lower capture gain may be needed).
- [ ] **No key: the service crash-loops.** Without `OPENAI_API_KEY`, `python -m greeter` opens the robot I/O and the camera, then exits, and systemd restarts it every 5 s. `install.sh` still enables it at boot. Until there is a key, deploy with `--no-service`. Better: don't enable the service without a key, or let it fall back to `--scripted`.
- [ ] **Library path for manual runs.** The service sets `LD_LIBRARY_PATH` to the CycloneDDS lib (and cuSPARSELt on JetPack 6); the guide's manual commands don't. Check on the robot whether `--check` works without it, and fix the guide or the code.
- [ ] **`--scripted` only chimes.** Make it speak the canned lines offline: render `models/clips/*.wav` (16 kHz mono) with macOS `say` or `espeak-ng`, and let the scripted backend play them instead of chimes. The self-test's `--check-sound` already plays `hello.wav` when it exists.

## Next session (no API key needed)

Commands: [`g1-lab-commands.html`](https://jiaxiwang05.github.io/Unitree/g1-lab-commands.html).

- [ ] Tilt the webcam up so a person 1.5–2 m away is in frame from head to waist.
- [ ] Passwordless SSH from the laptop (`ssh-copy-id`).
- [ ] Internet for the robot through the laptop (NAT on the **laptop**, default route on the robot). Check `date` on the robot.
- [ ] `setup-jetson.sh` (copy it over, run with `ssh -t`); press Enter at the API key prompt.
- [ ] `scripts/deploy.sh unitree@192.168.123.164 --no-service`.
- [ ] Robot speaker: `--check --check-sound --scripted`, listen for the beep.
- [ ] Live camera numbers on the 1, 2 and 3 m floor marks (`greeter.robot.calibrate`), then `--stand-at 1 2 3`.
- [ ] A full visit in `--scripted` mode: light changes, invitation, reply, close after 15 s of silence.

## After the API key

- [ ] Credit on platform.openai.com (at least $100 before the open day so it isn't rate-limited), create a key, store it with `scripts/set-api-key.sh` (the human types it).
- [ ] Re-run `deploy.sh` without `--no-service`: renders the voice clips and starts the service.
- [ ] Section 4 of the [session guide](https://jiaxiwang05.github.io/Unitree/g1-robot-session.html): a real visit, long talker, 90 s wrap-up, two people at once, Durham questions, `--roam`, the `--duplex` echo test.
- [ ] Section 5: compare the two cameras (`greeter.spot_compare`), save the day's log, tune the thresholds.

## Guide fixes still to make

- [ ] Add the no-API path and the "internet through the laptop" option to `g1-robot-session.html`.
- [ ] Say which commands run on the laptop and which on the robot more visibly; mixing them up cost time.

## Safety

- Damping on this remote is **L2 + B** (the chart printed on the remote). L1 + L2 toggles the voice mode and does not move the robot.
- Never put the robot's password or the API key in this repository.
