# To do

**Dated plan to 5 December: [TEST-PLAN.md](TEST-PLAN.md)** (Chinese): four robot sessions, each step with a pass mark.

Status after the first robot session (11 November 2026). No OpenAI API key yet. The robot hung on the gantry the whole time and never moved.

## Done on 11 November

- Lab Ubuntu laptop on the robot by cable: manual address `192.168.123.99/24` (a NetworkManager connection named `g1`), SSH to `unitree@192.168.123.164` works.
- Backup of the robot computer copied to the laptop (`~/g1-backup`): `/etc`, the home folder (665 MB), the apt and pip package lists.
- USB webcam (Trust, AONI chip) through a USB-C hub on the neck panel: 640x480 frames. It points at the floor and needs tilting up.
- The webcam's built-in mic records clearly with `arecord` (ALSA card 0 on the robot).
- Unitree Explore app: voice assistant in wake-up mode. chat_go was switched back on for a test; switch it off again.

## Problems found

- [ ] **Built-in robot mic sends only zeros.** The multicast `239.168.123.161:5555` delivers 5 s of packets (163840 bytes), all silent, in wake-up mode with chat_go both on and off. Pressing L1 + L2 after setting the mode in the app toggles it off again. To try: speak the wake word first, keypad conversation mode, the firmware version in the app, [g1-audio-driver](https://github.com/experientialtech/g1-audio-driver).
- [x] **Use the webcam mic meanwhile** (code done 12 Nov). `install.sh` now installs `sounddevice` and `setup-jetson.sh` installs `libportaudio2`; `--check` tests the mic named in `GREETER_MIC_DEVICE` and warns when it clips. **Still to do on the robot:** list devices with `.venv/bin/python -m sounddevice`, put part of the webcam's name in `GREETER_MIC_DEVICE` in `greeter.env`, run `--check`. If PortAudio cannot open the webcam at 16 kHz, tell Claude the error.
- [x] **No key: the service crash-looped** (fixed 12 Nov). The program now checks for a backend before it opens the robot or the camera and exits with status 78; the service unit has `RestartPreventExitStatus=78`. `--no-service` is no longer needed for a deploy without a key, though it still works.
- [x] **Library path for manual runs** (fixed 12 Nov, untested on the robot). `python -m greeter` and `python -m greeter.robot.calibrate` restart themselves once with `~/cyclonedds/install/lib` (and cuSPARSELt) on `LD_LIBRARY_PATH` when those folders exist.
- [x] **`--scripted` only chimed** (fixed 12 Nov). Without a key `install.sh` renders the 16 lines with `espeak-ng` (`python -m greeter.clips --render-offline`; `say` on a Mac). The scripted backend and `--check-sound` speak them. A later install with a key replaces them with the OpenAI voice.

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

## Head bracket for the Brio (trial, added 12 November)

[`hardware/head_brio_mount`](../hardware/head_brio_mount/README.md): Unitree's renewed-head stereo camera mount with the tray replaced by a level Brio seat.

- [ ] Confirm the robot has the renewed head (88 mm) and find the two M4 threads Unitree's mount uses.
- [ ] Print `head_brio_mount_print.stl` in PLA and hold it in the head: arms under the ring's top bar, seat in front of the ring, nothing touching.
- [ ] Buy a right-angle USB-C adapter or cable (a straight plug does not fit behind the camera).
- [ ] With the Brio fitted, run `--check` and read the `depth` line: does the head D435i still see the floor?
- [x] Choice made on 12 November: **use the head arch** (`hardware/helmet_ring_mount`), because the Brio and the built-in depth camera can then both be used. This bracket stays as a backup; the steps above are only needed if it is ever tried.

## Camera on the head with Blu Tack (stop-gap, 12 November)

Until the arch is printed, the camera can sit on top of the head, held with Blu Tack. Both the camera and the built-in depth camera stay usable, and nothing has to be printed.

- [ ] Use it only while the robot stands still, sits or hangs. Blu Tack is not enough when the robot walks.
- [ ] Clean, dry head top; a walnut-sized lump pressed flat under the camera; lens level and pointing straight ahead.
- [ ] Tape the cable to the back of the head a few centimetres behind the camera, so the cable's weight doesn't pull the camera off.
- [ ] Keep the face opening clear (depth camera and lidar look out through it).
- [ ] Take a test photo (the camera test in the lab commands page), then `calibrate --stand-at 1 2 3` once the program is installed. Recalibrate whenever the camera is moved.

## Head arch for the Brio (chosen 12 November)

[`hardware/helmet_ring_mount`](../hardware/helmet_ring_mount/README.md), [install animation](https://jiaxiwang05.github.io/Unitree/head-arch-install.html).

- [ ] Print `trial_feet_plate.stl` in PLA and fit the two feet on the shoulder rings. Are the rings fixed, or do they swivel or wobble?
- [ ] If the feet fit: print `helmet_crown.stl`, `helmet_foot_left.stl` and `helmet_foot_right.stl` in PETG.
- [ ] Buy the screws, nuts and foam in the arch's parts list.
- [ ] The arch sits on the rings the gantry hooks use: take it off before hanging the robot, or fit it only when the robot stands or sits.
- [ ] After fitting: `--check` (camera and depth lines), then `calibrate --stand-at 1 2 3`.
- [ ] Known cost: each leg shades about 10° of the head lidar to the left and right. Test before any use of the lidar for walking or mapping.

## Guide fixes still to make

- [ ] Add the no-API path and the "internet through the laptop" option to `g1-robot-session.html`.
- [ ] Say which commands run on the laptop and which on the robot more visibly; mixing them up cost time.

## Safety

- Damping on this remote is **L2 + B** (the chart printed on the remote). L1 + L2 toggles the voice mode and does not move the robot.
- Never put the robot's password or the API key in this repository.
