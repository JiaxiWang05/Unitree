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
| Code and tests | `greeter/`, `tests/` (170 tests, `pytest`), `scripts/` (setup, deploy, API key) |
| How to run it | `README.md`; first robot session step by step: [g1-robot-session.html](https://jiaxiwang05.github.io/Unitree/g1-robot-session.html); lab commands: [g1-lab-commands.html](https://jiaxiwang05.github.io/Unitree/g1-lab-commands.html) |
| **Live to-do list** | [`docs/TODO.md`](docs/TODO.md): the detailed checklist from the first robot session. Keep it up to date |
| Pages (GitHub Pages from `docs/`) | [Open Day scene](https://jiaxiwang05.github.io/Unitree/g1-open-day-scene.html), [animation only](https://jiaxiwang05.github.io/Unitree/g1-open-day-animation.html), [lab day guide (Chinese)](https://jiaxiwang05.github.io/Unitree/g1-lab-day.html), [mic and camera guide](https://jiaxiwang05.github.io/Unitree/mic-camera-guide.html), [head arch install animation (Chinese)](https://jiaxiwang05.github.io/Unitree/head-arch-install.html). Sources and rebuild: `docs/src/` |
| Chest bracket for the Brio | `hardware/brio_chest_mount/` (test print done in PLA) |
| Head arch for the Brio (v2) | `hardware/helmet_ring_mount/`: trial feet `trial_feet_plate.stl` (PLA, fit check), then `helmet_crown.stl` + `helmet_foot_left.stl` + `helmet_foot_right.stl` (PETG). Parts and assembly in its README |
| One-download bundle | [Release v0.6](https://github.com/JiaxiWang05/Unitree/releases/tag/v0.6), `g1-greeter.zip` (made before the v2 arch and the robot-session fixes; prefer `git clone`) |
| History and research notes | `notes/` (build log, head-mount notes, paper plan files) |

## Status

**Software (laptop):** 170 tests pass with the robot, camera and AI replaced by stand-ins.
Features: invite anyone or green; groups and two people talking at once; Durham fees and
assessment questions handed to staff; polite cut-in after 20 s of non-stop talk; wrap-up at
90 s; the robot's own goodbye ends a chat; `--duplex` barge-in (off by default); both
talk-spot answers logged (`python -m greeter.spot_compare`); `--roam` pauses inviting while
a person walks the robot with the remote (read-only leg-speed detection).

**First robot session (11 Nov 2026), from the session's notes:**
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

**Hardware:** bought a Logitech Brio 4K for Business (part 960-001746) and a CableCreation 1 m
USB-C to USB-C cable (check both arrived). The head arch v2 is ready to print but not printed
or fitted.

## Next steps, in order

The detailed checklist, with the problems found on 11 Nov (no `sounddevice` in `install.sh`,
the service crash-looping without a key, `--scripted` only chiming), is in
[`docs/TODO.md`](docs/TODO.md). In short:

1. Give the Jetson internet (phone hotspot, or share the Ubuntu laptop's connection), run
   `setup-jetson.sh` as above, then `scripts/deploy.sh unitree@<ip> --no-service`.
2. Self-test without a key: `.venv/bin/python -m greeter --check --check-sound --scripted`,
   then the full loop with `--scripted`.
3. Solve the built-in mic (zeros), or switch to a USB mic.
4. Buy OpenAI API credit, store the key with `scripts/set-api-key.sh` (typed by the user,
   never pasted into a chat), deploy again **without** `--no-service`.
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
- Brio on the head arch hung from the two shoulder lifting rings. Unitree's own head camera
  mount sits inside the head and points 49° down where the depth camera looks, so it can't
  carry the Brio. The chest bracket remains the fallback.
- Buy the Brio 4K for Business 960-001746, not the "New version" 960-001718 (the brackets
  weren't checked against it).

## Open questions

- Are the shoulder rings fixed, or do they swivel or wobble?
- Why does the built-in mic send zeros?
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
