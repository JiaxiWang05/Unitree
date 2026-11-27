# Hand-over: where the G1 Open Day greeter stands (11 Nov 2026)

Read this first in a new chat. It says what exists, what has been checked, what is next and
which decisions are already made. Details live in `README.md`, the guides in `docs/` and the
notes in `notes/`.

## The project in one paragraph

A Unitree G1 EDU (23 DoF) stands at a Durham University Open Day stand, notices visitors
(anyone by default, or only people in green with `--invite green`), invites them over by
naming something they wear, and chats by voice through OpenAI's Realtime model. A Logitech
Brio webcam finds people; the G1's head D435i depth camera checks the talk spot on the floor.
Everything runs in one Python process on the robot's Jetson. **The code never moves the
robot.** No face recognition.

## Where things are

| What | Where |
|---|---|
| Code and tests | `greeter/`, `tests/` (174 tests, `pytest`), `scripts/` (setup, deploy, API key) |
| How to run it | `README.md`; first robot session step by step: [g1-robot-session.html](https://jiaxiwang05.github.io/Unitree/g1-robot-session.html); lab commands: [g1-lab-commands.html](https://jiaxiwang05.github.io/Unitree/g1-lab-commands.html) |
| **Test plan to 5 Dec 2026** | [`docs/TEST-PLAN.md`](docs/TEST-PLAN.md) (Chinese): four robot sessions with pass marks; the last is a dress rehearsal on 3 Dec |
| **Live to-do list** | [`docs/TODO.md`](docs/TODO.md): the detailed checklist from the first robot session. Keep it up to date |
| Pages (GitHub Pages from `docs/`) | [Open Day scene](https://jiaxiwang05.github.io/Unitree/g1-open-day-scene.html), [animation only](https://jiaxiwang05.github.io/Unitree/g1-open-day-animation.html), [lab day guide (Chinese)](https://jiaxiwang05.github.io/Unitree/g1-lab-day.html), [mic and camera guide](https://jiaxiwang05.github.io/Unitree/mic-camera-guide.html), [head arch install animation (Chinese)](https://jiaxiwang05.github.io/Unitree/head-arch-install.html). Sources and rebuild: `docs/src/` |
| The three camera mounts compared, with 3D viewers | [camera-mounts.html](https://jiaxiwang05.github.io/Unitree/camera-mounts.html) (`docs/camera-mounts.html`, simplified models in `docs/stl/`) |
| Chest bracket for the Brio | `hardware/brio_chest_mount/` (test print done in PLA) |
| Head arch for the Brio (v2) | `hardware/helmet_ring_mount/`: trial feet `trial_feet_plate.stl` (PLA, fit check), then `helmet_crown.stl` + `helmet_foot_left.stl` + `helmet_foot_right.stl` (PETG). Parts and assembly in its README |
| Brio bracket inside the head (trial, v2 of 12 Nov) | `hardware/head_brio_mount/`: Unitree's renewed-head (88 mm) stereo mount with its tray swapped for a crossbar, two side plates and a level Brio seat above the depth camera's window. Placed in the public head model (position worked out by fitting Unitree's own mount, about 1 mm) it clears the head and blocks none of the depth camera's talk-spot sight lines; Unitree's own tray blocks all of them. Not printed or fitted. Backup to the arch |
| One-download bundle | [Release v0.6](https://github.com/JiaxiWang05/Unitree/releases/tag/v0.6), `g1-greeter.zip` (made before the v2 arch and the robot-session fixes; prefer `git clone`) |
| History and research notes | `notes/` (build log, head-mount notes, paper plan files) |

## Status

**Software (laptop):** 174 tests pass with the robot, camera and AI replaced by stand-ins.
Features: invite anyone or green; groups and two people talking at once; Durham fees and
assessment questions handed to staff; polite cut-in after 20 s of non-stop talk; wrap-up at
90 s; the robot's own goodbye ends a chat; `--duplex` barge-in (off by default); both
talk-spot answers logged (`python -m greeter.spot_compare`); `--roam` pauses inviting while
a person walks the robot with the remote (read-only leg-speed detection).

**First robot session (11 Nov 2026), from the session's notes:**
- Lab setup: robot `G1_06864`; lab Ubuntu laptop `adaptive@adaptive-Recoil-18`, wired port `enp213s0` (NetworkManager connection `g1`, manual `192.168.123.99/24`, no gateway), Wi-Fi `wlp131s0f0`. Passwords are not kept in this repo.
- The robot was reached by cable from the lab Ubuntu laptop: laptop `192.168.123.99`, Jetson
  `192.168.123.164`, login `unitree`. A backup of the robot was made to `~/g1-backup` on the
  Ubuntu laptop.
- A lab USB webcam (Trust, AONI chip, through a USB-C hub on the neck panel) works at
  640 × 480 but points at the floor; its microphone records clearly.
- **The robot's built-in mic multicast sent only zeros**, even in wake-up mode. Unsolved:
  use a USB mic (`--mic-device`) if it stays that way. The robot's speaker is untested.
- Nothing is installed on the Jetson yet. No OpenAI API credit yet.
- Fixes pushed afterwards: run `setup-jetson.sh` by copying it over and running it with
  `ssh -t ... sudo bash` (piping it into `ssh` breaks sudo); damping on the G1 remote is
  **L2 + B**.

**Second robot session (18 Nov 2026):** Brio arrived and is detected by the robot (video and
mic). Robot internet through the laptop and the robot's apt are fixed (details in
[`docs/TODO.md`](docs/TODO.md)). `setup-jetson.sh` is done; `deploy.sh` installed everything up to the
TensorRT export, which failed for want of `onnx` on aarch64 + Python 3.8. With `install.sh` fixed,
the re-run built the TensorRT engine (885 s), then the robot's battery ran out while the slow
offline voice lines were being made (now fixed in `clips.py`; all 16 were made on the laptop).
Next: finish `deploy.sh`, then the self-test, speaker and mic.

**Third robot session (25 Nov 2026):** the self-test now passes for the camera (Brio), YOLO
(21 ms/frame with TensorRT), the head depth camera (floor fit 48.6 deg, 1.31 m) and the robot SDK
(volume 100). Still failing: **the robot's speaker is silent** although `PlayStream` returns no
error, and **the built-in mic sends only zeros**. The robot also joined the lab Wi-Fi itself
(wlan0), so it has internet without the laptop. Its copy of the code is behind: run `deploy.sh`.

**Hardware:** bought a Logitech Brio 4K for Business (part 960-001746) and a CableCreation 1 m
USB-C to USB-C cable (check both arrived). The head arch v2 is ready to print but not printed
or fitted.

## Problems met on the robot, and what fixed them

| Problem | Cause | Fix |
|---|---|---|
| The robot had no internet through the laptop | Docker on the laptop blocks forwarding; the robot's default route pointed at a missing 192.168.123.1; no DNS | Laptop: NAT plus `DOCKER-USER` accept and `FORWARD` accept. Robot: `ip route replace default via 192.168.123.99`, `resolvectl dns eth0 192.168.50.1 1.1.1.1` (commands page step 7). Resets on every restart |
| "No internet" although it worked | The lab Wi-Fi blocks ping | Test with `curl -sI https://google.com` instead |
| `apt` on the robot installed nothing | Expired ROS repository key; `systemd-timesyncd` (from a 2024 upgrade) conflicted with Unitree's `chrony` | Refreshed the ROS key (now valid to 2030-06-01); removed `systemd-timesyncd`. Never run `apt upgrade` or `apt autoremove` on the robot |
| `setup-jetson.sh` could not ask for the sudo password | Piping the script into `ssh -t` leaves sudo without a terminal | Copy it over, then `ssh -t ... 'sudo bash ~/setup-jetson.sh'` |
| The install stopped at the TensorRT export | Ultralytics installs onnx together with onnxruntime-gpu, which has no aarch64 + Python 3.8 wheel | `install.sh` installs onnx and onnxslim first, and falls back to the `.pt` model if the export fails. The engine then built in 885 s |
| Making the offline voice lines took about 2.5 min each | The numpy resampler is slow on the Jetson | `clips.py` resamples with `audioop`: seconds for all 16 |
| The robot switched off mid-install | Battery ran out | Charge first. All 16 voice lines were made on the laptop instead |
| The self-test crashed with `EOFError` | `recorded.wav` was 0 bytes (made when the battery died) | Replaced by hand; `clips.load` now skips a broken clip |
| Commands typed in the wrong place | Laptop and robot terminals look alike | Check the prompt: `adaptive@...` is the laptop, `unitree@ubuntu` the robot |
| **Speaker silent (open)** | Not known: `PlayStream` returns no error | `scripts/speaker_test.py` on the robot: LED, then the robot's own TtsMaker voice, then our PlayStream, each with its return code. TtsMaker silent too = robot speaker, volume or voice service (ask the lab or Unitree; check the voice service firmware in the app, About Robot). TtsMaker heard but not ours = our audio path. A USB speaker also works: `GREETER_SPEAKER_DEVICE` |
| **Built-in mic sends zeros (open)** | Wake-up mode (remote L1 + L2) not confirmed; L1 + L2 toggles, so pressing it again turns it off | Use the Brio's mic instead: `GREETER_MIC_DEVICE=BRIO` (see below) |

**Using the Brio's microphone instead of the robot's.** Supported: `GREETER_MIC_DEVICE` in
`~/.config/g1-greeter/greeter.env` makes the program record from a USB mic through PortAudio
(`sounddevice`) instead of the robot's multicast stream. On 11 Nov the Brio mic recorded clear
speech with `arecord`. It has not worked in the program yet because the pieces were not all on the
robot: `setup-jetson.sh` ran from a laptop copy older than the change that installs
`libportaudio2`, so `sounddevice` cannot load PortAudio, and the robot's runtime is behind. To set it up:
1. `sudo apt install -y libportaudio2` on the robot (it has internet), then run `deploy.sh` from the laptop.
2. `cd ~/g1-greeter && .venv/bin/python -m sounddevice` must list a device with `BRIO` in its name.
3. Add `GREETER_MIC_DEVICE=BRIO` to the settings file; `--check` should then show `mic PASS` from `USB mic 'BRIO'`.
The Brio has no speaker, so it cannot replace the robot's speaker; a USB speaker can (`GREETER_SPEAKER_DEVICE`).

## Next steps, in order

The detailed checklist, with the problems found on 11 Nov (no `sounddevice` in `install.sh`,
the service crash-looping without a key, `--scripted` only chiming), is in
[`docs/TODO.md`](docs/TODO.md). In short:

1. Update the robot's code: `git pull` on the laptop, then `scripts/deploy.sh unitree@192.168.123.164 --no-service`.
   Then `scripts/speaker_test.py` (speaker) and the Brio mic setup above. Step-by-step list: [`docs/TODO.md`](docs/TODO.md), "Next on the robot".
2. Self-test without a key: `.venv/bin/python -m greeter --check --check-sound --scripted`,
   then the full loop with `--scripted`.
3. Mic: use the Brio's mic (`GREETER_MIC_DEVICE=BRIO`) unless the built-in mic starts working.
4. Once the school buys the OpenRouter credit (budget: `docs/openrouter-budget.xlsx`), store the key with
   `scripts/set-api-key.sh unitree@<robot> OPENROUTER_API_KEY` (typed by the user, never pasted into a chat),
   set `GREETER_BACKEND=openrouter`, then deploy again **without** `--no-service`.
5. Print the trial feet (PLA) and fit them on the shoulder rings; check whether the rings are
   fixed or swivel. Then print the arch in PETG and fit it (install animation above).
6. After moving the Brio to the head, re-run the distance calibration
   (`python -m greeter.robot.calibrate --stand-at 1 2 3`).
7. Test on the robot: a 20 s non-stop talker, two people at once, a fees question, a 90 s chat,
   `--roam` with someone walking it, and an echo test before ever turning on `--duplex`.
8. Update the risk assessment before the robot walks among visitors.

## Decisions already made (don't reopen without a reason)

- Invite anyone by default; `--invite green` keeps the original study rule.
- The program sends no motion commands; walking is only ever a person with the remote.
- Half duplex by default (mic muted while the robot speaks) until the echo test.
- Brio on the head arch hung from the two shoulder lifting rings (confirmed again on 12 Nov after a trial bracket inside the head was drawn: the arch keeps both the Brio and the built-in depth camera usable; its legs shade about 10° of the lidar on each side). Until the arch is printed, the camera is stuck on top of the head with Blu Tack for standing tests only (docs/TODO.md). Unitree's own head camera
  mount sits inside the head and points 49° down where the depth camera looks, so it can't
  carry the Brio. The chest bracket remains the fallback.
- Buy the Brio 4K for Business 960-001746, not the "New version" 960-001718 (the brackets
  weren't checked against it).

## Open questions

- Are the shoulder rings fixed, or do they swivel or wobble?
- Why does the built-in mic send zeros? (Workaround: the Brio mic.)
- Why is the robot's speaker silent? (`scripts/speaker_test.py` will narrow it down.)
- Is the purple test print of the chest bracket PLA? (The final one should be PETG.)

## Rules for any AI session working on this repo

- Commit as `Jiaxi Wang <125281693+JiaxiWang05@users.noreply.github.com>`; never use a personal
  email. Never delete or recreate the repo; old emails in history are accepted.
- Deploy from the Mac clone `~/Documents/GitHub/Unitree` (or a fresh clone), never from the
  old copy in `~/Documents/GitHub/JiaxiWang05.github.io`.
- Never ask for, paste or commit passwords or API keys; the user types them into prompts.
- Don't add motion commands; `tests/test_setup.py` fails if any arm, waist or walking client
  is used.

## Private links (open only for the user)

- Paper plan: https://claude.ai/artifact/YVEeY4ABvZDPSY1kt561YR
- Technical deck: https://claude.ai/artifact/LECR4pNGaUQWSydYBFhJeH
- Literature review: https://claude.ai/artifact/UbzZRLt5f9v3JJNA9iPT6v
- Procurement report: https://claude.ai/artifact/J88uJ8WEhdBfYvRk3g8Rbh
- Robot session commands page: https://claude.ai/artifact/5zXA52qHNspHFsWhxVc5ey
