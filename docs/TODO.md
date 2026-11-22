# To do

**Dated plan to 5 December: [TEST-PLAN.md](TEST-PLAN.md)** (Chinese): four robot sessions, each step with a pass mark.

Status after the first robot session (11 November 2026). No OpenAI API key yet. The robot hung on the gantry the whole time and never moved.

## Done on 11 November

- Lab Ubuntu laptop on the robot by cable: manual address `192.168.123.99/24` (a NetworkManager connection named `g1`), SSH to `unitree@192.168.123.164` works.
- Backup of the robot computer copied to the laptop (`~/g1-backup`): `/etc`, the home folder (665 MB), the apt and pip package lists.
- USB webcam (Trust, AONI chip) through a USB-C hub on the neck panel: 640x480 frames. It points at the floor and needs tilting up.
- The webcam's built-in mic records clearly with `arecord` (ALSA card 0 on the robot).
- Unitree Explore app: voice assistant in wake-up mode. chat_go was switched back on for a test; switch it off again.

## Done on 18 November (session 2)

- Brio 4K arrived and plugged straight into a neck-panel USB-C port. The robot sees it: video `/dev/v4l/by-id/usb-046d_Logitech_BRIO_BC9F0E13-video-index0`, mic `card 0: BRIO` (ALSA). The head D435i shows up too.
- Robot internet through the laptop works, after three fixes: Docker on the laptop was blocking forwarding (`DOCKER-USER` accept, `FORWARD` policy accept); the robot's default route pointed at a missing 192.168.123.1 (now 192.168.123.99); the robot had no DNS (`resolvectl dns eth0 192.168.50.1 1.1.1.1`). The lab Wi-Fi blocks ping, so check with `curl`. Commands page step 7 updated.
- Why the ROS key: the robot has ROS 1 and ROS 2 apt sources (tuna mirror). apt checks every source's signature, and ROS's signing key (ID `F42ED6FBAB17C654`, fingerprint `C1CF 6E31 E6BA DE88 68B1 72B4 F42E D6FB AB17 C654`) expired on 1 June 2025; ROS republished it with a new expiry date. With the old copy, `apt update` failed and `setup-jetson.sh` could not install anything. Refreshing it installs or upgrades no software and does not touch the robot's ROS. Checked on the robot on 18 Nov: `/usr/share/keyrings/ros-archive-keyring.gpg` holds that key (Open Robotics, created 2019-05-30), now valid until **2030-06-01**; nothing is left in the old `apt-key` store. Check with `gpg --show-keys /usr/share/keyrings/ros-archive-keyring.gpg`.
- Robot apt repaired: refreshed the expired ROS repository key, and removed `systemd-timesyncd` (pulled in by a July 2024 upgrade, it conflicted with Unitree's `chrony`, so apt could install nothing). `chrony` still keeps time with the internal board (.161). Don't run `apt upgrade` or `apt autoremove` on the robot.
- `setup-jetson.sh` done (API key skipped).
- `deploy.sh --no-service` installed uv, the venv, CUDA torch 2.2.0 (GPU seen: Orin), CycloneDDS 0.10, `unitree_sdk2py`, OpenCV and the YOLO26n-pose weights, then **stopped at the TensorRT export**: Ultralytics tried to install onnx, onnxslim and onnxruntime-gpu in one go, onnxruntime-gpu has no aarch64 + Python 3.8 wheel, so onnx never got installed. Fixed in `install.sh` (installs onnx and onnxslim first; a failed export now falls back to the `.pt` model instead of stopping the install). Not yet re-run on the robot.
- The robot's clock is about 8 minutes behind the laptop (tar warnings during deploy). Harmless for now.
- By mistake: a copy of this repo was cloned on the robot (`/home/unitree/Unitree`); unused, can be deleted.

## Done on 18-19 November (session 2, continued)

- Re-ran `deploy.sh` with the fixed `install.sh`: **the TensorRT engine built** (`yolo26n-pose.engine`, 8.7 MB, 885 s on the Orin NX; FP16 warnings about subnormal weights are harmless). A copy is in `~/g1-backup/` on the lab laptop.
- The install then started the offline voice lines and was very slow: about 2.5 minutes per line, because the numpy resampler in `clips.to_clip` is slow on the Jetson. 11 of 16 lines were made when **the robot's battery ran out and it shut down** mid-install. The last clip on the robot may be cut short.
- All 16 lines were then made on the lab laptop in seconds (espeak-ng, resampled with `audioop`), in `~/Unitree/models/clips/` there. `clips.py` now uses `audioop` too, so the robot will also make them in seconds.
- Lab laptop, not the robot: an NVIDIA driver (570) module would not build for a new kernel (7.0.0-30), so four kernel packages are half-installed and every `apt install` retries the build. The laptop still runs its old kernel and works. Leave it to whoever looks after the laptop; don't reboot it into the new kernel.

## OpenRouter mode (added 20 November, reviewed 22 November)

`GREETER_BACKEND=openrouter` sits beside the OpenAI realtime mode. On 22 Nov it was checked against OpenRouter's live API and docs and against the app; 28 confirmed problems were fixed, among them: speech asked for `wav` (OpenRouter offers only `pcm`/`mp3`, so Kokoro was never used); the espeak fallback froze the app for minutes per sentence; a goodbye started a second reply on top of the first; the 20 s cut-in threw the visitor's speech away; a cough started a 30 s recording; replies could be spoken twice; Gemini's compulsory reasoning could use up the reply; notes went out as extra system messages, which some models refuse. 80 tests pass (fake OpenRouter). **Still not run with a real key.**

Things only a real key will show (check on the first turn):
- that `reasoning: {enabled: false}` really switches Qwen's reasoning off (the logged usage should show no reasoning tokens);
- that OpenRouter passes the WAV audio on to Alibaba correctly (the log's `visitor:` lines show what it heard);
- the speech sample rate (`--check` prints it).

**Data protection:** `qwen/qwen3.8-omni-flash` has one provider, Alibaba, with data centres in Singapore and China, and no zero-data-retention option. If the ethics or data-protection review requires zero data retention (an OpenRouter privacy setting), Qwen cannot be used; use Gemini 3.8 Flash (Google Vertex) instead: `GREETER_OPENROUTER_MODEL=google/gemini-3.8-flash`.

## Next on the robot (in person)

Bring: the lab Ubuntu laptop, Ethernet cable, robot remote (charged), Brio and its USB-C cable, Blu Tack and tape, floor tape and a tape measure, headphones.

1. [ ] Charge the robot; hang it on the gantry. Keep the remote in hand (damping: L2 + B).
2. [ ] Ethernet from the laptop to the robot; on the laptop `nmcli con up g1`, then `ping -c 2 192.168.123.164`.
3. [ ] Restore the robot's internet (commands page step 7, laptop side first); check with `ssh unitree@192.168.123.164 'curl -sI --max-time 8 https://google.com | head -1'`.
4. [ ] Check the TensorRT engine survived the power cut: `md5sum` of `~/g1-greeter/models/yolo26n-pose.engine` on the robot against `~/g1-backup/yolo26n-pose.engine`; copy the backup over if they differ.
5. [ ] Copy the voice lines made on the laptop: `scp ~/Unitree/models/clips/*.wav unitree@192.168.123.164:g1-greeter/models/clips/`
6. [ ] `cd ~/Unitree && git pull && scripts/deploy.sh unitree@192.168.123.164 --no-service` (finishes the install; voice lines now take seconds).
7. [ ] Brio on the head top with Blu Tack, lens level and facing forward, cable taped down; take a test photo (commands page step 3).
8. [ ] Self-test: `ssh unitree@192.168.123.164 'cd ~/g1-greeter && .venv/bin/python -m greeter --check --check-sound --scripted'`. Listen for the robot saying "Hello! Lovely to meet you." Note the `depth` and `mic` lines.
9. [ ] Microphone: if the robot's own mic is still silent, add `GREETER_MIC_DEVICE=BRIO` to `~/.config/g1-greeter/greeter.env` and run the self-test again.
10. [ ] Mic level for turn-taking: run the self-test once in silence and once while someone talks at 1 m; speech should be well above -38 dBFS and the quiet room well below. If not, set `GREETER_OPENROUTER_SPEECH_DBFS` in the settings file.
11. [ ] Floor tape: talk spot 0.6-1.4 m in front, marks at 1, 2 and 3 m; then `.venv/bin/python -m greeter.robot.calibrate --stand-at 1 2 3`.
12. [ ] A full visit in `--scripted` mode (free): lights, invitation, reply, goodbye.
13. [ ] When the OpenRouter credit is bought: `scripts/set-api-key.sh unitree@192.168.123.164 OPENROUTER_API_KEY` (you type the key), add `GREETER_BACKEND=openrouter` to the settings file, run `--check` (key, credit, model names, one speech request), then talk to it and note `first audio after ... s` in the log.
14. [ ] Before leaving: save the day's log if the service ran (`journalctl --user -u g1-greeter --since today > ~/g1-greeter/today.log`), copy `~/g1-backup` to a USB stick, L2 + B, switch off.

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

## Head bracket for the Brio (trial, version 2 of 12 November)

[`hardware/head_brio_mount`](../hardware/head_brio_mount/README.md): Unitree's renewed-head stereo camera mount with the tray replaced by a crossbar under the brow, a plate up each side of the depth camera's window, and a level Brio seat above it. Backup to the head arch.

Version 1 was wrong: once Unitree's own mount could be placed in the public head model (it fits in one spot only), version 1's camera cut 11 mm into the forehead and blocked 41% of the depth camera's sight lines to the talk spot. Version 2 clears the head by 3.1 mm and blocks none, in the model. Unitree's own tray blocks all of them.

- [ ] Confirm the robot has the renewed head (88 mm) and find the two M4 threads Unitree's mount uses.
- [ ] Print `head_brio_mount_print.stl` in PLA and hold it in the head: arms out under the brow, crossbar just below it, plates either side of the face ring, nothing touching.
- [ ] Buy a right-angle USB-C adapter that stands at most 13 mm off the camera.
- [ ] With the Brio fitted, run `--check` and read the `depth` line: does the head D435i still see the floor? The model says yes; the public head may differ from the real one by a few millimetres.
- [x] Choice made on 12 November: **use the head arch** (`hardware/helmet_ring_mount`), because the Brio and the built-in depth camera can then both be used. This bracket stays as a backup.

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
- [ ] Buy the screws, nuts and foam in the arch's parts list. Non-Amazon suppliers: [procurement guide](https://jiaxiwang05.github.io/Unitree/mic-camera-guide.html#shops).
- [ ] Thumb screw head: Accu lists the M5 × 25 DIN 464 head as 20 × 11.5 mm, but `check_helmet_arch.py` models 16 × 9 mm. Re-run the check with the real size (set `THUMB_HEAD_D`, `THUMB_HEAD_H`) or hold a screw against the trial feet before buying.
- [ ] The arch sits on the rings the gantry hooks use: take it off before hanging the robot, or fit it only when the robot stands or sits.
- [ ] After fitting: `--check` (camera and depth lines), then `calibrate --stand-at 1 2 3`.
- [ ] Known cost: each leg shades about 10° of the head lidar to the left and right. Test before any use of the lidar for walking or mapping.

## Guide fixes still to make

- [ ] Add the no-API path and the "internet through the laptop" option to `g1-robot-session.html`.
- [ ] Say which commands run on the laptop and which on the robot more visibly; mixing them up cost time.

## Safety

- Damping on this remote is **L2 + B** (the chart printed on the remote). L1 + L2 toggles the voice mode and does not move the robot.
- Never put the robot's password or the API key in this repository.
