# G1 proactive greeter

> **New here, or a new chat?** Start with [`HANDOVER.md`](HANDOVER.md): status, next steps and decisions as of 11 Nov 2026.

A Unitree G1 EDU (23 DoF) notices open-day visitors, invites them over by
naming something they wear, and chats with them. By default it invites anyone
who looks interested; `--invite green` brings back the original rule of inviting
only people wearing **green**. It refers only to clothing and objects, never to
appearance.

**This program never moves the robot.** There are no arm, waist or walking
commands anywhere in the code. It only talks, listens, looks, and uses the LED
strip. With `--roam`, a team member walks the robot around with the Unitree
remote (the robot's own walking mode); the program only reads the legs' joint
speeds, so it can stop inviting people while the robot walks.

Everything runs **in one process on the robot's Jetson Orin NX (PC2)**. The
laptop is only used over SSH. This is the "simplest route" / phase 1 of the
design doc.

```
                      G1 Jetson Orin NX (PC2) — one process: python -m greeter
 ┌─────────────────────────────────────────────────────────────────────────────────────┐
 │ chest USB webcam ─► YOLO26n-pose + BoT-SORT (ReID) ─► CIELAB torso green, distance,  │
 │                    facing, speed, groups, crowd, talk spot ─► interaction ladder     │
 │                                                                     │               │
 │  NOTICED: warm OpenAI session + opener generated out of band ◄──────┤               │
 │  BID: play it (or "Hey, you in the green!") ── OPEN ── CONVERSE ── CLOSE ── COOLDOWN │
 │                                                                     │               │
 │ mic (UDP multicast 239.168.123.161:5555) ─► 24 kHz ─► OpenAI Realtime gpt-realtime-2.1│
 │ AudioClient.PlayStream ◄── 16 kHz ◄── reply     (fresh frame at every visitor turn)  │
 │ LedControl: white breathing / light green / green / amber                            │
 │ recordings/: WAVs, frames, transcripts, detector trace (for tuning)                  │
 └────────────────────────────────────┬────────────────────────────────────────────────┘
                                      │ Wi-Fi: pocket 4G/5G router (or a phone hotspot)
```

## Pages

Published with GitHub Pages from `docs/` (sources and build in `docs/src/`):

- [Open Day scene](https://jiaxiwang05.github.io/Unitree/g1-open-day-scene.html): one visit in 3D, how it works, common questions, status.
- [Animation only](https://jiaxiwang05.github.io/Unitree/g1-open-day-animation.html): the same visit full-screen, for meetings.
- [Lab day guide](https://jiaxiwang05.github.io/Unitree/g1-lab-day.html) (Chinese): fitting the bracket, testing the mic, setting up the robot, parts to buy, the head mount.
- [First robot session](https://jiaxiwang05.github.io/Unitree/g1-robot-session.html) (Chinese): step by step from the network cable to the last test.
- [Lab commands](https://jiaxiwang05.github.io/Unitree/g1-lab-commands.html): copy-paste commands for the next session (backup, camera and mic checks, internet through the laptop, install, speaker test).
- [Test plan](docs/TEST-PLAN.md) (Chinese): what to test, step by step, before 5 December.
- [To do](docs/TODO.md): status after the first robot session and what comes next.
- [Camera mounts](https://jiaxiwang05.github.io/Unitree/camera-mounts.html) (Chinese): the three ways to mount the Brio (head arch, chest bracket, bracket inside the head), each as a 3D model you can drag to turn, with what each blocks and the print files.
- [Head Brio bracket install](https://jiaxiwang05.github.io/Unitree/head-brio-install.html) (Chinese): step-by-step animation for the trial bracket inside the renewed head, and how to use it afterwards.
- [Mic and camera guide](https://jiaxiwang05.github.io/Unitree/mic-camera-guide.html): what to buy and why.
- [Test results](https://jiaxiwang05.github.io/Unitree/test-results.txt).

## What the human does

About an hour, once. Claude does everything else over SSH.

1. **Webcam.** Bolt a Logitech Brio to the robot's chest with the 3D-printed
   bracket in [`hardware/brio_chest_mount/`](hardware/brio_chest_mount/README.md),
   facing forward. Not in the face opening: that is the built-in depth
   camera's window, and the talk spot needs that camera. For a higher view
   (about 1.37 m), the Brio can instead ride on a printed arch over the head
   that hangs on the shoulder lifting rings
   ([`hardware/helmet_ring_mount/`](hardware/helmet_ring_mount/README.md));
   after moving it, redo the distance calibration. Plug the Brio
   into a free USB-C port on the panel at the back of the neck with a 1 m
   USB-C to USB-C cable. Any UVC webcam works with the software; the bracket
   holds the Brio with its clip taken off, looking 20° up.
2. **OpenAI API key.** A ChatGPT Plus subscription does **not** include API
   access; API use is billed separately.
   1. Create an account at [platform.openai.com](https://platform.openai.com).
   2. Add credit: at least **$100**, ideally **$500**. A $500 top-up moves the
      account straight to the Grow tier, so open-day traffic isn't
      rate-limited.
   3. Create an API key and keep it to paste in step 4.
3. **Internet: a pocket 4G/5G router with a data SIM.** It is used exactly like a
   phone hotspot (the setup script asks for its Wi-Fi name and password), but it is
   dedicated, has its own battery and doesn't drop out on calls or screen lock.
   - **4G, cheap:** [TP-Link M7350](https://www.tp-link.com/uk/home-networking/mifi/m7350/)
     or [GL.iNet Mudi V2 (GL-E750)](https://www.gl-inet.com/products/gl-e750/).
   - **5G:** [GL.iNet Mudi 7 (GL-E5800)](https://www.gl-inet.com/products/gl-e5800/).
   - **SIM:** any UK prepaid, no-contract, data-only SIM, bought by the department so it
     can be claimed. It doesn't need to be unlimited: the robot uses about 1–3 GB a day,
     so a 5–10 GB monthly plan is plenty.
   - **Or no SIM at all:** ask university IT for a network port at the stand and plug it
     into a small travel router's WAN port, for example the
     [GL.iNet Opal (GL-SFT1200)](https://www.gl-inet.com/products/gl-sft1200/).
   - A phone hotspot also works.
   - eduroam won't: it needs an enterprise login the robot can't do.
   - Don't plug venue Ethernet into the robot's port, because it clashes with
     the robot's internal 192.168.123.x network.
4. **Laptop to robot, once.**
   1. Plug the laptop into the robot with an Ethernet cable.
   2. Set the laptop's wired network to the manual address `192.168.123.99`,
      mask `255.255.255.0`.
   3. Allow passwordless SSH from now on (it asks for the robot's password
      once):

      ```bash
      ssh-copy-id unitree@192.168.123.164
      ```

   4. Run the one setup script. It asks for the sudo password, the Wi-Fi name
      and password, and the OpenAI key; the key is typed hidden and never
      stored in the code:

      ```bash
      scp scripts/setup-jetson.sh unitree@192.168.123.164:~ && ssh -t unitree@192.168.123.164 'sudo bash ~/setup-jetson.sh'
      ```

   Then tell Claude *"the Jetson is set up"*. Claude deploys with
   `scripts/deploy.sh`, runs the self-test and starts the service.
5. **Voice assistant mode.** Put the robot's voice assistant in **wake-up
   mode**: press **L1 + L2** together on the remote, or in the Unitree app go
   to Device > Data > Audio > Voice assistant. Otherwise the robot's
   microphone sends no audio, or all zeros. Also switch off **chat_go** in the
   app (Device > Service Status), so Unitree's own assistant doesn't answer
   visitors who say its wake word.
6. **On site.**
   1. Stand the robot up with the remote, and keep the remote in your hand.
   2. Wear something green and walk up to about 1.5–2 m, facing the robot.
   3. It should invite you over. Step onto the talk spot (about 1 m in front)
      or just reply.
   4. Tell Claude what worked so it can tune the thresholds.
   5. For distance calibration, stand on floor marks at 1, 2 and 3 m while
      Claude runs the calibration.

After that the greeter starts by itself whenever the robot boots.

**Only if the on-site test says so (Tier 1):**
- **Hard to hear:** add a USB mic (`GREETER_MIC_DEVICE`) or a USB speaker/DAC
  (`GREETER_SPEAKER_DEVICE`).
- **4G unstable:** use the 5G router, or place it higher and away from the crowd.

## What Claude does (over SSH)

```bash
scripts/deploy.sh unitree@<jetson-address>
```

This copies the code and runs `scripts/install.sh` on the Jetson. It needs no
sudo and is safe to repeat. The install script:

- Creates a virtual environment on the Jetson's system Python 3.8 with
  [uv](https://docs.astral.sh/uv/).
- Installs NVIDIA's CUDA torch for JetPack 5 (or 6), pinned so no package can
  swap it out.
- Installs Ultralytics, CycloneDDS 0.10 (built from source) and
  `unitree_sdk2_python`.
- Downloads `yolo26n-pose.pt` and builds a TensorRT FP16 engine (about 5
  minutes, once).
- Finds the chest webcam (skipping the RealSense) and writes
  `~/.config/g1-greeter/greeter.env`.
- Renders the ~15 fallback voice clips with OpenAI TTS.
- Runs the self-test.
- Enables a systemd user service that starts at boot and restarts on failure.

Day-to-day commands on the Jetson, all run from `~/g1-greeter`:

```bash
journalctl --user -u g1-greeter -f
```

```bash
systemctl --user stop g1-greeter
```

```bash
.venv/bin/python -m greeter --check --check-sound
```

```bash
.venv/bin/python -m greeter.robot.calibrate
```

```bash
.venv/bin/python -m greeter.robot.calibrate --stand-at 1 2 3
```

```bash
systemctl --user start g1-greeter
```

In order, these:
1. Show the live log: states, what was said, and spend.
2. Stop the service. The tools below need the camera, so stop it first.
3. Run the self-test: key, internet, camera, YOLO speed, SDK, mic level, then a
   spoken line.
4. Print live numbers each second: green, distance, facing, speed, groups.
5. Calibrate distance on the floor marks; this saves `GREETER_DIST_K`.
6. Start the service again.

**First day on the robot: voice reproduction checklist.** The audio plumbing
follows namanbansal013/unitree-openai-voice, which has no track record yet.
So check it in this order:
1. `--check` reports the JetPack and Python versions, and that the SDK talks
   to the voice service.
2. `--check --check-sound` plays a line through `PlayStream`.
3. `--check` captures 3 s from the mic multicast and reports the level. If it
   gets 0 bytes or all zeros, put the voice assistant in wake-up mode
   (L1 + L2 on the remote; Unitree's VuiClient docs and unitree_sdk2_python
   PR #133). While running, the program logs the same warning. To listen to
   the mic, run `python3 scripts/record_mic.py` in `~/g1-greeter`: it saves
   5 s as `mic_test.wav` and says if nothing arrives or it is all zeros.
4. Run the full loop: start the service and talk to it.
5. If the mic path fails, fall back to
   [g1-audio-driver](https://github.com/experientialtech/g1-audio-driver) (it
   exposes PulseAudio devices) and point `GREETER_MIC_DEVICE` /
   `GREETER_SPEAKER_DEVICE` at them.

**Without an API key** the service stops with exit status 78 and systemd leaves it stopped
(no restart loop). `install.sh` then makes stand-in voice lines with `espeak-ng`, so
`python -m greeter --scripted` and `--check --check-sound` speak instead of chiming. The first
install with a key replaces them with the real voice.

**Settings** live in `~/.config/g1-greeter/greeter.env` (mode 600, `KEY=value`).
Keys are never kept in the code.

| variable | default | |
|---|---|---|
| `OPENAI_API_KEY` | — | required |
| `GEMINI_API_KEY` | — | optional hot standby (needs Python 3.10+, see below) |
| `GREETER_OPENAI_VOICE` | `marin` | |
| `GREETER_DIST_K` | `160` | shoulder px × metres; set by `calibrate --stand-at` |
| `GREETER_MIN_GREEN` | `0.25` | green share of the torso |
| `GREETER_CAMERA` | auto | `/dev/v4l/by-id/...-video-index0` |
| `GREETER_VOLUME` | `80` | |
| `GREETER_INVITE` | `anyone` | `green`: only invite people wearing green |
| `GREETER_ROAM` | off | `1`: a team member walks the robot with the remote; no invitations while it walks |
| `GREETER_DUPLEX` | off | `1` keeps the mic open while the robot talks (barge-in) |
| `GREETER_MAX_VISIT` | `240` | seconds |
| `GREETER_RECORD` | on | `0` stops recording |
| `GREETER_MIC_DEVICE` / `GREETER_SPEAKER_DEVICE` | — | USB mic / DAC instead of the robot's own: part of the device's name as listed by `.venv/bin/python -m sounddevice` (for example `webcam`) |

## The interaction ladder

| state | LED | what happens | next |
|---|---|---|---|
| **IDLE** | white breathing | perception only | someone (in green, with `--invite green`) within 5 m, not walking past (sideways < 0.6 m/s, watched ≥ 1 s), while the robot isn't walking → NOTICED |
| **NOTICED** | light green | open a warm session and generate the opener *out of band*: `response.create` with `conversation: "none"`, the frame as `input_image` plus a scene note, audio out, ≤ 15 words naming something they wear | target at 1.2–2.2 m **and** facing ≥ 0.8 s **and** no crowd **and** 8 s since the last bid → BID. Left, 20 s without coming closer, or the robot starts walking → IDLE |
| **BID** | green | play the opener; if it isn't ready within 1 s, play the canned "Hey there! Come and say hi!" ("Hey, you in the green!" with `--invite green`) | invitation played → OPEN |
| **OPEN** | green | listen | they reply, step onto the talk spot, or keep facing 1.5 s → CONVERSE. Otherwise drop silently; they count as invited for 30 min |
| **CONVERSE** | green listening / amber thinking | one fresh session per visitor or group, append-only (no item deletes, prompt cache stays warm). A frame goes in at speech start, and again at commit if the scene changed | their goodbye or the robot's own, nobody there for 4 s, someone queued 30 s after 2 min of chat, the 4 min cap, 15 s of silence, or the robot walked on for 2 s → CLOSE |
| **CLOSE** | green | one line: a stand highlight plus a callback to something they said or wore (the green item with `--invite green`); skipped if they left or the robot already said goodbye | → COOLDOWN |
| **COOLDOWN** | white | close the session | 2 s → IDLE |

**Other triggers:**
- **Talk spot:** anyone (any clothing) who speaks while standing on the talk
  spot starts a conversation directly. A loudness trigger over the learned hall
  noise is used for this, and the words that started it are replayed into the
  session.
- **Crowd:** with more than 8 people, or 3 or more groups, within 2.5 m, the
  robot doesn't invite anyone; it only answers the talk spot.
- **Groups:** people within 1.5 m of each other, moving at under 0.4 m/s
  relative to each other, for at least 1 s, are treated as a group. A group gets
  a group opener. The persona tells the model it may be talking to several
  people: talk to the whole group, and if two speak at once, answer one and
  invite the other next.
- **Long talkers:** a visitor who talks for 20 s without a break gets a polite
  cut-in: their turn is closed so the model hears what they said, and it
  answers in one sentence and offers someone else a turn.
- **Wrap-up:** after 90 s of chat the model gets a silent note to start
  wrapping up. When the robot then says goodbye itself, the chat ends without
  another line. The 4 min cap stays as a backstop.
- **Durham questions:** the persona forbids guessing fees, entry requirements,
  offers, module content, how coursework or exams are weighted, accommodation
  or funding; the robot passes those to the team.
- **Walking (`--roam`):** while the robot is being walked, nothing new starts,
  an invitation in progress is dropped, and walking on for 2 s during a chat
  closes it with a goodbye. "Walking" is the RMS speed of the 12 leg joints
  from `rt/lowstate`, read only (`greeter/robot/motion.py`); the thresholds
  still need checking on the robot.

## How it sees green, distance and facing

- **Detection:** YOLO26n-pose, as a TensorRT FP16 engine at 640 px on the
  Jetson, with Ultralytics' BoT-SORT with ReID (`greeter/robot/botsort_reid.yaml`).
  Camera motion compensation is off and lost tracks are kept for about 6 s. No
  face recognition.
- **Green:** CIELAB inside the torso, counting pixels with hue 110–170° and
  C* > 20.
  - Hi-vis vests are rejected (L* > 85, C* > 70, h < 125).
  - A person is green when ≥ 25 % of the torso is green in 6 of the last 10
    frames.
  - White balance and exposure are locked after 2 s of auto, so colours stay
    stable.
  - On test colours this accepts green, olive, jade and forest, and rejects
    hi-vis, yellow, teal, khaki, washed-out sage, deep shadow, red, blue and
    grey.
- **Distance:** distance = `GREETER_DIST_K` ÷ shoulder width in pixels.
  Calibrate it on 3 floor marks. Without shoulders it falls back to full-body
  height. Sideways position comes from the box centre, and speed is smoothed.
- **Facing:** nose and both eyes visible, head yaw ≤ 30°, shoulder line within
  30° of the camera, and not their back.
- **Same person:** a new track ID that appears where an invited person was just
  lost inherits "already invited".

## Talk spot from the built-in head D435i (nothing extra to buy)

The G1's own head D435i is fixed 47.6° down at about 1.26 m. It never sees
torsos or faces, but the talk spot (0.6–1.4 m ahead, 1.2 m wide) is right in
the middle of its floor view. So depth decides **"is someone standing on the
talk spot?"**, while the webcam keeps doing green, facing and the visitor's
picture. The two are independent: no matching between webcam tracks and depth.

**How it works** (`greeter/robot/depth_spot.py`), per depth frame:
1. Deproject about 212 × 120 sampled pixels into the robot's ground frame.
2. Re-fit the floor plane, folding the robot's real lean and height into the
   camera pose. The first fit runs at start-up, then again every 20 s while
   the spot is empty.
3. Count points on the spot 5 cm–1.2 m above the floor, requiring some at
   thigh height (≥ 0.55 m), so bags don't count. The blob must be centred on
   the spot, so a bystander just beside it doesn't count.
4. Call it occupied after 1.5 s of presence while slow (under 0.3 m/s), so
   people walking across don't count. Release it after 0.7 s empty.
5. Something tall that stays perfectly still for 60 s (a sign, a pushchair)
   is treated as an object. "Still" means under 1.5 mm of jitter, far below a
   standing person's sway. It is reconsidered as soon as someone joins it or
   it moves.
6. If the camera drops off USB, the reader backs off and restarts the stream.
   The spot keeps its last reading for 5 s, then falls back to the webcam
   estimate.

**Effect on the ladder:**
- During OPEN, the spot filling up from the start of the invitation counts as
  "stepped onto the spot", so the conversation starts. Someone already
  standing there doesn't count.
- In IDLE, an occupied spot turns on the talk-spot voice trigger. The visitor
  who just said goodbye can't restart a chat until they step off.
- In CONVERSE, an occupied spot keeps the visit alive.
- A talk-spot chat with someone the webcam can't place (a child, or someone
  side-on) stays open while depth sees them.

**Settings:**
- `--depth auto` (the default) uses the D435i on the robot when pyrealsense2
  works, and is off in `--mock`. Force it with `--depth realsense`, or turn it
  off with `--depth off`.
- The URDF pose can be overridden with `GREETER_DEPTH_PITCH` /
  `GREETER_DEPTH_HEIGHT`, but the floor fit normally makes that unnecessary.
- `--check` prints the fitted pitch and height and whether the spot is empty.

**Human part:** mark the spot on the floor with tape or a mat, about 1 m in
front of the robot.

**Test it without the robot:** a synthetic D435i ray-casts people, passers-by
and objects through the same pose and field of view, with D435i-like noise:

```bash
.venv/bin/python -m greeter --mock --scripted --camera green_visitor.avi --depth synthetic --no-mic --no-speaker
```

The `visit` scenario is timed to the test clip: the visitor steps onto the
spot after the invitation, and later a passer-by walks straight across it.
Other scenarios: `--depth-scenario walkby | bag | empty`.

**Limits:**
- Depth can't tell who is on the spot.
- A visitor standing almost perfectly still for over a minute could in
  principle be taken for an object. The tolerance is set well below normal
  sway, and the webcam still keeps the visit alive.
- Unverified on the robot: that no Unitree service already holds the camera,
  and the real noise on dark trousers.

## Backends and spend

| order | provider | notes |
|---|---|---|
| 1 | OpenAI `gpt-realtime-2.1` | Default. Raw WebSocket (works on Python 3.8). Reasoning effort `minimal`, semantic VAD, voice `marin`. Reconnects once and re-seeds the conversation if the socket drops. Truncates the reply at what was actually heard on barge-in. |
| 2 | Gemini `gemini-3.8-live` | Only if `GEMINI_API_KEY` is set and google-genai is installed (Python 3.10+). Speaks first with `send_client_content(turn_complete=True)`. Context compression and session resumption are on. |
| 3 | OpenAI `gpt-realtime-2.1-mini` | |
| 4 | ~15 pre-recorded clips | Same voice. The last resort says "my cloud brain has dropped out, please ask one of the team". |

- **Moving down the chain:** a 429, spend-limit, quota or auth error moves to
  the next provider for the rest of the day.
- **Spend tracking:** usage from every `response.done` is priced (gpt-realtime-2.1:
  audio $32 in / $64 out, image $5, text $4 / $24 per 1M tokens) and added up
  in the log and the recordings.
- **Limits:** OpenAI spend limits are monthly; set one at platform.openai.com.
- **Other backends:**
  - `--backend gemini` puts Gemini first.
  - `--local` is the offline cascade (Silero, Whisper, Ollama, Kokoro). On the
    Jetson it needs JetPack 6 / Python 3.10+, otherwise run it on a Mac through
    the optional split below.
  - `--scripted` uses canned lines for tests.

## Recording (privacy is not required here)

For tuning, every visit is saved under `~/g1-greeter/recordings/<date>/<time>-track<N>/`:
- `mic.wav` and `robot.wav`;
- the notice frame plus one frame every 2 s;
- `events.jsonl` with transcripts, states and spend.

A day-long `trace.jsonl` holds every scene snapshot (~5 Hz) and the battery
state every 10 s. Each snapshot keeps both talk-spot answers, the head depth
camera's and the webcam's own estimate, so a lab session can compare them:

```bash
.venv/bin/python -m greeter.spot_compare recordings/<date>/trace.jsonl
```

It prints how often they agree, how long each one said "occupied" on its own,
and when. Recording pauses when less than 2 GB is free. There is no face
recognition.

If this data is used for PhD research, it needs Durham ethics approval first
(UK GDPR). Put a notice at the stand saying conversations are recorded. The
robot also says so if asked.

## Testing without the robot (`--mock`)

The same process runs with the laptop webcam, mic and speaker standing in for
the G1.

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements/dev.txt
```

```bash
.venv/bin/python -m greeter --mock --scripted
```

```bash
OPENAI_API_KEY=... .venv/bin/python -m greeter --mock
```

The second command needs no key. The third uses the real model.

No webcam? Build a test clip: a visitor in red, then green, then gone.

```bash
.venv/bin/python scripts/make_test_clip.py green_visitor.avi
```

```bash
.venv/bin/python -m greeter --mock --scripted --camera green_visitor.avi --no-mic --no-speaker
```

## Design choices and limits

- **One process instead of three services and Docker.** The design doc
  suggests a perception container, a Python 3.11 voice service and a DDS
  bridge. This keeps it to one process: the voice client here runs on the
  Jetson's Python 3.8, and NVIDIA's CUDA torch wheel gives GPU YOLO without
  Docker. There are fewer moving parts and no IPC.
  - Trade-offs: a crash restarts everything (systemd restarts it in 5 s, but
    the current visitor is lost), and Python 3.8 rules out Gemini and the local
    cascade on the Jetson.
  - If on-site tests show audio stutter or crashes, the existing WebSocket
    bridge (`--serve` / `--robot`) can split perception from dialogue.
- **Not built (only if the on-site test needs them):**
  - WebRTC AEC3 echo cancellation, Smart Turn v3 end-of-turn detection, and
    duck-then-confirm barge-in.
  - Dual-uplink network switching, and Tailscale.
  - A 30-minute ReID gallery and "welcome back". Today "already invited" is
    per track ID.
  - Latency fillers or apologies.
- **Barge-in (`--duplex`):** the visitor can interrupt the robot while its
  reply is being generated and while its audio is still playing. Off by
  default, because without echo cancellation the robot may hear itself: test
  the echo on the robot first.
- **Unverified on the robot:** the battery topic `rt/lf/bmsstate` (logged
  best-effort), and the walk-detection thresholds on `rt/lowstate`.

## Tests

```bash
.venv/bin/python -m pytest
```

174 tests:

| file | covers |
|---|---|
| `test_vision.py` | CIELAB colours including hi-vis rejection, the 6-of-10 window, torso crop, head and shoulder yaw, distance, walking past, notice once and release, ID-switch inheritance, groups, crowd, talk spot, invite anyone vs green, no notices while walking, both spot estimates kept |
| `test_dialogue.py` | Every rung and threshold of the ladder, including the "cloud brain" apology playing out after a session error; anyone vs green invitations, roam wording, the long-talker cut-in, the 90 s wrap-up note, the robot's own goodbye, walking |
| `test_openai_backend.py` | Out-of-band opener, append-only commit, frames at speech start and commit, truncate on barge-in (also after the reply was generated, while it still plays), cut-in, silent notes, reconnect and re-seed, spend limit → provider down, cost |
| `test_motion.py` | Walk detection from leg speeds: standing balance, start, short stops, stop after a quiet pause |
| `test_spot_compare.py` | Depth vs webcam talk-spot comparison from a trace |
| `test_gemini_backend.py` | Speaks first, session resumption after a drop |
| `test_local_backend.py` | The local cascade's glue, with stub models |
| `test_e2e.py` | The full ladder in one process (with recording), visitor walking away, the apology clip not cut off by the cooldown, the WebSocket split, token, LED, spot trigger over hall noise |
| `test_setup.py` | Offline voice clips, the scripted backend speaking them, stopping without a key (exit 78, no restart), the library path for hand-typed commands; env file, camera auto-detect and control lock (50 Hz, fixed frame rate, focus), CLI defaults, provider chain, a scan proving no motion API is used, recorder, clips |
| `test_g1_io.py` | Mic multicast warnings: stream stopped, or arriving all zeros (wrong voice-assistant mode) |
| `test_audio_protocol.py` | Resampler, muted-mic detection, wire format |
| `test_depth_spot.py` | Head-D435i talk spot on rendered depth: floor at zero, floor fit recovers lean and height, 1.5 s dwell, whole footprint, outside and bystanders ignored, fast and slow walkers ignored, bags ignored, release, still object vs quiet visitor, a visitor joining an object, USB 2 mode, the visit timeline, OPEN acceptance (early in a long invitation; not a lingering visitor; not a depth stall), depth-only chats, no restart by the same visitor, recovery after a USB drop, bad env values, end to end |

**Verified on a laptop:**
- Real YOLO26n-pose + BoT-SORT ReID through the whole ladder, on the test clip.
- The D435i talk spot with the synthetic depth camera alongside it: occupied
  while the visitor stood there, no false trigger from the passer-by, released
  when they left.
- The default code path checks as Python 3.8-compatible.

**Not verified, needs the robot or keys:**
- On the robot: DDS, mic multicast, `PlayStream`, `LedControl`, the battery
  topic, the install and setup scripts, and the real head D435i through
  pyrealsense2 2.55.1.
- Live OpenAI, Gemini and Ollama runs, and the TTS clip rendering.

## Project layout and credits

```
greeter/
  cli.py, __main__.py   python -m greeter (all modes), provider chain
  vision.py             CIELAB green, geometry, groups, crowd, Scene (noticing: anyone or green)
  dialogue/             machine.py (ladder), app.py (runner, LED, spot trigger), prompts.py, links.py
  backends/             openai_realtime.py, gemini.py, local.py, scripted.py (+ canned clips), spend.py
  robot/                core.py, camera.py, detector.py, botsort_reid.yaml, g1_io.py, mock_io.py,
                        motion.py (walk detection for --roam), server.py (optional bridge), calibrate.py
  recorder.py, clips.py, check.py, envfile.py, audio.py, protocol.py,
  spot_compare.py       depth vs webcam talk-spot comparison from a day's trace
scripts/                setup-jetson.sh (human, once), deploy.sh + install.sh (Claude), set-api-key.sh,
                        make_test_clip.py, record_mic.py (5 s test recording from the built-in mic)
docs/                   the GitHub Pages site; docs/src/ has the page templates, mesh exports and build_pages.py
hardware/               brio_chest_mount/: 3D-printed chest bracket for the Brio (STL, STEP, CadQuery source, checks)
                        helmet_ring_mount/: head-top arch for the Brio on the shoulder lifting rings (trial ends + full arch)
                        head_brio_mount/: trial bracket for the Brio inside the renewed head, after Unitree's stereo camera mount
```

Ideas reused from:
- [namanbansal013/unitree-openai-voice](https://github.com/namanbansal013/unitree-openai-voice)
  (MIT, © 2026 Naman Bansal): the G1 audio plumbing, rewritten here with
  asyncio, reconnect and truncation.
- [pipecat](https://github.com/pipecat-ai/pipecat): the Gemini 3.x
  realtime-input nudge.
- [OpenMind OM1](https://github.com/OpenMind/OM1): the greeting flow.
- [Project Babis](https://github.com/GeoZach08/UnitreeG1-Autonomous-Edge-AI-Voice-Interaction-for-Unitree-G1)
  by GeoZach08: greeting a nearby person on the G1 and resetting when nobody is
  there. The repo has no licence file; the author has given permission for its
  code to be used in this project.

## Author

Jiaxi Wang, Durham University, supervised by Dr Amir Atapour-Abarghouei and
Dr Chris Chen. [Research profile](https://adaptive-intelligence.co.uk/jiaxi-wang/) ·
[website](https://jiaxiwang05.github.io/).
