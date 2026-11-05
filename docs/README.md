# Outputs

| File | What it is |
|---|---|
| [`g1-open-day-scene.html`](g1-open-day-scene.html) | Interactive 3D of the G1 greeter at the Open Day stand, built from Unitree's G1 model and the bracket STL: one visit you can play through with the robot's states and speech, what the webcam sees, how it works, answers to common questions (who it invites, crowds, two people talking, interruptions, long talkers, Durham questions, why two cameras, walking around), status and links |
| [`g1-open-day-animation.html`](g1-open-day-animation.html) | The same 3D visit full-screen with no text, for showing in a meeting. Drag to turn, scroll to zoom, Space pauses |
| [`mic-camera-guide.html`](mic-camera-guide.html) | Procurement guide: which webcam and microphone to use on the G1 EDU+, the robot's ports and power, how to use the built-in mic, and the chest mount |
| [`g1-lab-day.html`](g1-lab-day.html) | Lab day guide (in Chinese): a 3D step-by-step for fitting the chest bracket, testing the built-in mic, setting up the robot's computer, and running the whole flow with a lab USB webcam; also the head-mount trial fit, a detailed parts list, connecting a Mac or Ubuntu laptop to the robot, and notes on letting the robot walk. Opens in the browser on this site; the 3D view needs an internet connection |
| [`g1-robot-session.html`](g1-robot-session.html) | First robot session, step by step (in Chinese, with diagrams): connecting the lab Ubuntu PC by cable, the setup script, the install, the self-test, mic and camera checks, a full visit, the new features (long talkers, wrap-up, two people at once, Durham questions, `--roam`, the `--duplex` echo test), comparing the two cameras, distance calibration. Steps can be ticked off |
| `test-results.txt` | Output of the test suite (`pytest -v`, 170 tests) on a laptop, with the robot, camera and cloud services replaced by stand-ins |
| [`src/`](src) | Sources of the 3D pages: templates, the mesh export scripts and `build_pages.py`, which rebuilds the pages byte for byte |

The 3D-printable chest bracket for the webcam is in [`hardware/brio_chest_mount`](https://github.com/JiaxiWang05/Unitree/tree/main/hardware/brio_chest_mount). The head-top arch that carries the Brio on the shoulder lifting rings (trial ends and the full arch) is in [`hardware/helmet_ring_mount`](https://github.com/JiaxiWang05/Unitree/tree/main/hardware/helmet_ring_mount).
