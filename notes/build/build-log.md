# G1 greeter — hand-over (updated 2026-10-17, v0.3 "final spec, phase 1 / simplest route")

Final package: `g1-greeter.zip` in this session's scratch workspace
`/Users/jiaxi/Library/Application Support/Claude/scratch-workspaces/ac00c5ba-02d8-4256-b1a1-afa230578eb3/85d01ac3-73c1-4e22-96fe-89c6fc55b529/scratch-2026-10-16-69348e`
(also sent to the user). Not committed anywhere. README.md has "What the human does".

## Built (phase 1 default)
- One process on PC2 (`python -m greeter`), system Python 3.8 + NVIDIA CUDA torch wheel, TensorRT FP16 by default.
- No motion at all (AST test proves no arm/loco/ExecuteAction anywhere). LED: white breathing idle, light green
  noticed, green listening, amber thinking (LedControl >= 200 ms apart).
- Perception: YOLO26n-pose + BoT-SORT with ReID (shipped yaml, GMC off); CIELAB green h 110-170, C*>20, hi-vis
  rejected, >=25 % torso in 6/10 frames; WB/exposure locked; distance from shoulder width (calibrate --stand-at 1 2 3);
  facing (head yaw, shoulder line <= 30 deg); speed; groups (1.5 m, 0.4 m/s, 1 s); crowd (>8 people / 3 groups in
  2.5 m); talk spot.
- Ladder IDLE->NOTICED->BID->OPEN->CONVERSE->CLOSE->COOLDOWN with the spec's thresholds; out-of-band opener
  (conversation "none"), canned "Hey, you in the green!" after 1 s, drop silently, 30-min invited memory (per track),
  8 s global cooldown, talk-spot speech start, close on goodbye / 4 s empty / queue 30 s after 2 min / 4 min cap /
  15 s silence safety; takeaway line.
- OpenAI gpt-realtime-2.1 (raw websockets, reasoning minimal, semantic VAD create_response=false, frame at speech
  start + commit if changed, append-only, truncate on barge-in, reconnect+re-seed, spend meter, provider_down).
  Chain: 2.1 -> Gemini (if key, py3.10+, resumption on) -> 2.1-mini -> ~15 TTS clips.
- Recording for tuning (WAVs, frames, transcripts, 5 Hz trace, battery best-effort).
- Human steps: zip-tie webcam, API key ($100+, ideally $500 Grow), ssh-copy-id + one setup script (sudo, hotspot
  password, key hidden), Unitree voice assistant push-button mode, green test.

## Deliberate deviations (user said 要求最省事，能用就行)
- Single process, no Docker perception, no Python 3.11 venv, no 3 services (explained in README "Design choices").
- Not built: AEC3, Smart Turn v3, duck-then-confirm, netwatch/dual uplink, Tailscale, ReID 30-min gallery /
  "welcome back", FSM read, latency fillers.

## Verified / not verified
104 tests pass (fresh unzip too); real YOLO+BoT-SORT ReID mock run walks the whole ladder on the clip; py3.8 OK;
websockets 13.1 OK. Not verified: anything on the real G1/Jetson (DDS, multicast, PlayStream, LedControl,
bmsstate topic, setup/install scripts), live OpenAI/Gemini/Ollama, TTS clip rendering.

## Update 2026-10-24: v0.4, head-D435i depth talk spot (no extra hardware)
- New: greeter/robot/depth_spot.py (deproject the built-in head D435i into the ground frame, floor-fit pose refinement,
  spot 0.6-1.4 m x +/-0.6 m, thigh-height points, blob centred, 1.5 s dwell, 0.3 m/s speed gate, 0.7 s release,
  still-object rule at 1.5 mm with re-check) and greeter/robot/depth_source.py (pyrealsense2 reader with USB-drop
  backoff/restart; synthetic D435i ray-caster + scenarios for --mock). Standalone next to the webcam, no association.
- Ladder: the spot filling from the start of the invitation = "stepped onto the spot"; depth-only talk-spot chats stay
  open; the same visitor can't restart right after a goodbye; source flips don't fake acceptance.
- Flags: --depth auto|realsense|synthetic|off (auto = robot with pyrealsense2; off in --mock), --depth-scenario.
  install.sh installs pyrealsense2==2.55.1.6486 on py3.8; setup-jetson.sh installs RealSense udev rules.
- A 10-agent review found 15 issues (7 verified, 8 lower); all fixed with regression tests. 139 tests pass; py3.8 OK.
- Network advice changed: no personal hotspot needed. Preferred: university IT device Wi-Fi, or a wired port + cheap
  travel router (GL.iNet Opal GL-SFT1200). Fallback: department-bought prepaid data SIM + 4G MiFi (TP-Link M7350).
  For lab testing a personal hotspot works immediately.
- Not verified on the robot: real D435i access (a Unitree service may hold it), real depth noise.

## Update 2026-10-27: v0.5 fix + technical Open Day deck
- Bug fixed (found by a deck fact-check): on a mid-chat session error the "brain_offline" apology was queued before
  COOLDOWN's StopAudio and cut off at once. Now machine.py queues PlayClip after StopAudio (before CloseSession),
  resets speech_until on COOLDOWN, and COOLDOWN waits for playback to finish (capped at close_timeout_s).
  4 regression tests (3 fail on the old code); 143 tests pass, also from a fresh unzip; g1-greeter.zip rebuilt.
- Deck (Slides artifact https://claude.ai/artifact/LECR4pNGaUQWSydYBFhJeH): 19 technical slides, Open Day framing,
  GitHub sources per slide + credits slide. Open Day findings worth knowing: webcam exposure/WB lock 2 s after start
  (restart the service after standing the robot up); use floor tape, not a raised rope, near the talk spot (depth
  blob); battery clip is not wired (no low-battery alert); spend only in events.jsonl / debug log; mini model unpriced;
  internet-down is not "provider refused" (invitations fail silently); TensorRT engine makes BoT-SORT ReID load a
  separate yolo26n-cls encoder (fps unmeasured); nothing times latency yet.

## Update 2026-10-30: mic/camera procurement + wake-up mode fix
- Procurement report (artifact https://claude.ai/artifact/J88uJ8WEhdBfYvRk3g8Rbh): camera Logitech Brio 4K (backup
  C930e); mic: test the built-in array first, else Seeed ReSpeaker USB Mic Array (XVF-3000, CPC SC19968). All 5 V
  USB-C; G1 panel = 3x USB-C 5V/1.5A + Alt-mode C (power undocumented) + XT30 58/24/12 V (never for USB devices).
  EDU+ = D435i cable external into a PC2 USB-C port (one port used).
- Built-in mic: 4-mic linear array at the front of the neck base, wired to PC1; real audio on
  239.168.123.161:5555 only in WAKE-UP mode (remote L1+L2, or app Device>Data>Audio>Voice assistant), not
  push-button. Switch off chat_go (app Device>Service Status) so Unitree's assistant doesn't answer.
- Code: g1_io MicWatch warns on missing or all-zero multicast with the wake-up hint; check.py fails on all
  zeros; camera.py sets 50 Hz + no exposure frame-rate drop before settling, then locks WB/exposure/focus.
  README and deck updated. 148 tests pass (also from a fresh unzip); zip rebuilt. Not run on the robot.

## Update 2026-10-31: Amazon links, built-in mic recorder, bracket findings
- Camera to buy: Amazon UK https://www.amazon.co.uk/dp/B0F1TYFRYT (Brio 4K for Business 960-001746, £69.99 deal, sold by
  Amazon; Logitech UK redirects 960-001106 to 960-001746) + a USB-C to C cable: 1 m for the chest mount (see below;
  the 0.3 m B0BPLRJVK3 first listed here is too short). Not the "New version" 960-001718 (unchecked). Mic: use built-in.
- scripts/record_mic.py: stdlib 5 s recorder for the built-in mic multicast (flags no audio / all zeros). Tested on a
  fake local multicast only; not in g1-greeter.zip.
- No public report of a Brio (or any Logitech webcam) on a G1. Jetson evidence only (Orin NX JP6, TX2 after fw 1.0.423,
  Nano). LeRobot mounted an Arducam board on a G1 head (HF dataset lerobot/unitree-g1-hardware-modifications).
- No ready-made Brio bracket. Unitree's head brackets (xr_teleoperate Device.md, STEP files in 4 zips) hold their
  60 mm-baseline stereo board inside the top of the face opening, 2x M4x16 into the head. Brio is 102 mm wide (too wide
  for the 88/98 mm heads). The Brio's 1/4" tripod thread is under the camera body, behind its detachable clip (the
  clip has no thread; Logitech Brio 4K setup guide/FAQ).
- Gap in the procurement report: Unitree's own head stereo camera (xr_teleoperate Device.md 5.2.1/5.2.2, 125 deg,
  60 mm baseline, Taobao links only) was never compared. teleimager default head config: v4l2, binocular, 1280x480
  @30 MJPG = two 640x480 halves. Pros: official bracket (STEP), used by Unitree on G1. Cons: no UK seller found,
  exposure/WB lock unknown, 125 deg distortion; our camera.py would need a left-half crop. Bracket STEP sizes
  (vertex bbox): mount 72-75 x 108 x 33-39 mm, covers 89-91 mm wide (board ~90 mm) vs Brio 102 x 27 x 26.5 mm.
- Unitree stereo cam: xr_teleoperate README runs teleimager on PC2 (192.168.123.164). Taobao items: 60 fps
  id 941079164958 (~CNY 651-666), 30 fps id 680371983853 (~CNY 209-256); pages need a Taobao login (not read).
  G1+ ships a built-in 60 mm / 125 deg (110 H x 80 V) stereo head camera. Advice given: buy Brio now and the 30 fps
  stereo cam in parallel; keep whichever locks colour and detects at range. Software would need a left-half crop.
- Official stereo bracket tilt (from STEP hole axes): M4 clearance holes (4.5 mm) are vertical; board M2 holes have
  axis (0.652, 0, 0.758) => camera pitched ~49 deg down (teleop view of hands). With 80 deg vertical FOV the top edge is
  ~9 deg below horizontal: only legs visible at 3-5 m. Unusable for the greeter as-is, so the stereo cam loses its
  main advantage; recommendation reverted to Brio only, with a custom chest bracket (see below and 1 Nov). "98/88 mm" head names =
  M4 hole spacing (y = +/-49 vs +/-44 mm).
- Brio bracket designed for the CHEST, not the head: the face-opening "eyes" spot is the D435i's window (talk spot
  needs it). hardware/brio_chest_mount/ (CadQuery .py, .step, .stl, previews, README). Bolts to the two lower front
  M6 holes (64.5 mm apart, ~110 mm above torso origin per Unitree's about_G1 drawing). CAD checks vs unitree_ros
  torso_link_23dof_rev_1_0.STL: pads flush, >=3.3 mm clearance elsewhere, 0/3234 D435i talk-spot sight lines
  blocked. SUPERSEDED 1 Nov: that first version screwed into the clip and pointed level (see the 1 Nov update for the
  redesign). Cable for chest mount: 1 m
  CableCreation USB 3.2 Gen 2 C-to-C https://www.amazon.co.uk/dp/B0BFGSX9JR (0.3 m is too short).

## Update 2026-11-01: bracket redesign, docs, zip, Node for the anatomy skill
- Review found the 31 Oct bracket screwed into the Brio's CLIP, but the 1/4"-20 thread is under the camera body
  (Logitech Brio 4K setup guide/FAQ: remove the clip to expose it). Redesigned hardware/brio_chest_mount/: same
  riser/pads/ribs on the lower M6 pair; the shelf now carries a wedge seat tilted TILT_DEG = 20 deg up for the BARE
  camera (clip off), front/back lips 27.5 mm apart, 1/4" slot square to the seat (+/-2.5 mm play), 11 mm plastic to a
  16 mm spot face underneath. Screws: 1/4"-20 x 5/8" (sticks up 4.9 mm; washers if the camera thread is shallower);
  M6 length = 11.6 + measured depth - 1 (probably M6x18/20; M6x16 gave only 4.4 mm). 58.7 cm3, one watertight solid.
- CAD checks (scratchpad cad/check_fit2.py): pads +/-0.01 mm, >=3.33 mm clearance, lens 1.008 m up / 133 mm ahead of
  the torso origin, 0/3969 Brio view rays blocked (bracket, torso, head), 0/3234 D435i talk-spot lines blocked
  (closest 28 mm). Faces in view from 0.70 m (1.6 m high) / 0.85 m (1.75 m); bottom of view 0.70 m above floor at 3 m.
  Assumes the 640x480 mode keeps full sensor height (unverified). Not verified: Brio underside shape/thread position,
  USB-C plug space (~3 cm, socket is on the back), real holes. The independent CAD reviewer of the redesign hit a usage
  limit and did not run; a documents reviewer did.
- Code/docs: README step 1 = chest bracket + 1 m cable (no zip-tie); "head webcam" -> "chest webcam" in README,
  install.sh, cli.py, depth_spot.py, botsort_reid.yaml and the realtime SYSTEM_PROMPT ("A camera on your chest");
  deploy.sh excludes ./hardware; record_mic.py reports "Audio stopped after X s" instead of exiting when audio stops
  partway (tested on a fake loopback multicast). 148 tests pass, also from a fresh unzip. g1-greeter.zip rebuilt
  (65 files, includes scripts/record_mic.py and hardware/).
- Published: procurement report v3 (https://claude.ai/artifact/J88uJ8WEhdBfYvRk3g8Rbh: Amazon links, 1 m cable, chest
  mount section, Unitree stereo-camera row, C930e needs a new mount) and deck v28 (architecture/deploy/next/testing).
- Node for the anatomy skill: Homebrew has no bottles for macOS 14 (Tier 3); it compiled llvm/rust/node for ~8.5 h,
  then the node build left nothing (logs wiped by its cleanup). Installed nodejs 26.12.1 from conda-forge in conda env
  "node" (~/miniforge3/envs/node), symlinked node/npm/npx into ~/.local/bin. Anatomy skill smoke test passed
  (dial-indicator build + capture.mjs headless Chrome, console clean). Homebrew cleanup: llvm, rust, cmake, openssl@4,
  icu4c@79 etc. were already installed (only upgraded) or are now needed by them, so kept; the 18 formulae the node
  build newly added (python@3.15, sphinx-doc, simdjson, ...) + autoremoved libffi were uninstalled (~0.36 GB);
  brew missing is clean. /opt/homebrew/bin/python3 (3.15 since 31 Oct) is gone; shells use miniforge's python3.

## Update 2026-11-02: final Brio chest bracket (user bought the Brio 4K for Business + CableCreation CC1213 1 m C-C)
- The app restart wiped the session scratchpad (CAD venv, G1 meshes, check scripts, report/deck sources). Rebuilt:
  venv (pip cadquery trimesh scipy manifold3d matplotlib), meshes re-downloaded from unitree_ros, chest map and check
  scripts recreated. Copies of the check scripts + last output are now in this notes folder: cad_checks/.
  Run: python check_fit3.py <bracket dir> <dir with chest_map.npy + view_step.py> <stl> <torso.STL> <head.STL> <png prefix>.
- Research (3 angles + cross-check, sources: Logitech docs, Kurokesu teardown, LanOC photos, Printables 1091243 /
  745064 / 1655660 / 359083 measured): bare body 102 x 27 stadium (R13.5 ends), 26.5 deep (the "27" in the 2024
  guide is a conversion slip), underside flat across the middle ~75 mm, 65 g. 1/4" thread 12.0 mm behind the front /
  14.5 mm in front of the back face, centred L-R (+/-1); it is a thin steel plate held by tape, depth unpublished
  (~4-5 mm) -> screw only 4 mm in. USB-C centred on the back face, centre ~7 mm above the underside; the port has no
  mechanical support. Stock straight cable sticks out 50-75 mm behind. CC1213 plug size unpublished (~12.5x6.5x30-35).
  640x480 is most likely a 4:3 side crop (52 deg tall); worst case 66 deg tall. FOV control: UVC XU, cameractrls
  logitech_brio_fov (whether the Brio 4K stores it in flash is unverified; the OpenLogi report was a Brio 500).
- Changes (hardware/brio_chest_mount): slot centred THREAD_FROM_BACK=14.5 from the back stops (camera slides back
  on the slope), +/-3 mm play, 7 mm wide; GRIP = 5/8" - one 1.6 mm M6 washer - 4.0 mm = 10.28 mm; back lip split
  with a 20 mm gap for the plug; 24 mm channel through the shelf behind the seat; shelf moved forward and down
  (SHELF_D 66.7 -> 96.7, SHELF_Z 150 -> 120) so a 35 mm straight plug + ~24 mm cable bend fit while the D435i
  talk-spot lines still clear by 15 mm (sweep: forward 30 mm at z=150 left only 0.4 mm).
- Checks (check_fit3): one watertight solid 46.5 cm3, 108 x 85 x 40 mm; pads +/-0.01 mm, >=3.33 mm off the chest;
  camera block no overlap; plug 3.5 mm clear; 0 view rays blocked (52 and 66 deg tall); 0/3234 D435i lines blocked,
  closest 15 mm; lens 0.978 m up, 160 mm ahead of the torso origin; faces 1.6 m from 0.76 m, 1.75 m from 0.90 m;
  30 N bump ~2 MPa in the shelf, <1 MPa across layers. README rewritten (three-turns screw check, velcro strain
  relief through the channel, washers). Report v4 published (J88uJ8WEhdBfYvRk3g8Rbh). Deck unchanged (no numbers).
