# Head arch trial feet (G1 shoulder rings)

The Brio could later sit on top of the robot's head, on an arch that runs from one shoulder
lifting ring, over the head, to the other ring. These are only the two **ends** of that arch.
Print them first, fit them on the rings and measure. The full arch is then drawn from your
numbers.

![the idea: an arch from ring to ring over the head, with the Brio on top (sketch)](helmet_concept.png)
![both feet on their rings, from behind and from the side, and one taken apart](preview_on_robot.png)
![the print plate](preview_part.png)

## Why a trial first

The ring shape comes only from Unitree's 3D model. The real rings can differ in thickness, eye
size or spacing, and the full arch is about 15 × 18 cm and a long print. These feet take a
short print and answer those questions.

## The rings in Unitree's model

- A flat steel lug on top of each shoulder, beside the neck. It stands about 18 mm above the
  shell, and the eye faces sideways, so the bolt runs left to right.
- The eye is 11.7 mm wide with a round top (radius 5.8 mm) and straight sides down to the shell.
- The plate is 4.2 mm thick where it is flat and up to 6.2 mm across lower down.
- The centres are about 144.8 mm apart. In the model, the left ring is 71.2 mm from the centre
  line and the right one 73.6 mm, so the model is 2.4 mm asymmetric. Each foot is centred on its
  own ring.

## Parts

| Part | Notes |
|---|---|
| The two printed feet | `trial_feet_plate.stl`: both on one plate |
| 2× M5 × 25 socket cap screws | ISO 4762, A2 stainless. They go through the cheek, the ring's eye and the other cheek |
| 2× M5 nylon-insert lock nuts | DIN 985, A2. Each sits in the hex pocket on the neck side |
| 2× M5 washers | ISO 7089, A2, under the screw heads |
| 4 mm hex key and 8 mm spanner | For the screw and the nut |

**Why M5 and not M6:** the bolt has to sit high in the eye so its nut pocket stays above the
cheek bottom. With M6, the pocket would break through the bottom and the nut would sit 1.3 mm
from the shell beside the neck. M5 still leaves 1.3 mm between the bolt and the eye's round top.

## Printing

- Print both on one plate, standing as they sit on the robot: cheek bottoms on the bed, leg
  stubs up. The plate is 31 × 63 × 59 mm.
- No supports. The slot roof bridges 8.5 mm. The bolt holes are 5.5 mm, and the nut pockets
  have a corner pointing up, so both print without support.
- PLA is fine for this trial. Use 0.2 mm layers, 3–4 walls and 30 % infill. Each foot is
  15.3 cm³ solid, about 19 g if printed solid in PLA, less with infill.

## Fitting

Do this while the robot is **not** hanging from its rings, for example sitting or lying down
with the power off.

1. The feet are mirror images. On each one, the hex pocket faces the neck and the small arrow on
   the roof points forward, the way the robot faces.
2. Slide the foot straight down over its ring until the bolt holes line up with the eye.
3. Put a washer on the M5 screw and push it in from the shoulder side: through the outer cheek,
   the ring's eye and the inner cheek.
4. Put the nut into the hex pocket from the neck side. Turn the screw until it just holds.
   **Don't tighten it**: the foot should still move a little.

Then check:

- The foot slides on and off the ring without force, and the ring doesn't rub hard on the slot.
- The screw went in without forcing, and the foot can move a little up and down on it.
- The cheeks don't touch the shoulder: a sheet of paper slides under them.
- The stub stands straight up beside the head without touching it.

## Measure and send

With a caliper:

1. The ring's eye: its width, and its height from the shell to the top of the eye. The model
   gives 11.7 mm wide and about 11 mm tall.
2. The ring plate's thickness at the top and near the bottom. The model gives 4.2 mm and up to
   6.2 mm.
3. The distance between the two rings, outer face to outer face and inner face to inner face.
   The model gives about 149 mm and 140.5 mm, about 144.8 mm centre to centre.
4. From the top of a ring to the top of the head. The model gives about 131 mm.
5. Whether the rings are fixed solid or can swivel or wobble.
6. A photo of each foot fitted, from behind and from the side.

## Cautions

- **Take the feet off, and later the arch, before hoisting the robot by its rings.** Never lift
  the robot by a printed part.
- The leg stubs cover about 9–10° of the head lidar's all-round view on each side, and so will
  the arch's legs. The greeter doesn't use the lidar, but walking on its own with obstacle
  avoidance would.
- Check the screws before each session: walking shakes things loose.

## What was checked, and what wasn't

Checked against Unitree's model (`torso_link_23dof_rev_1_0.STL` and `head_link.STL`) with
`check_trial_feet.py`. Its output is in `check_output.txt`.

- **Slot:** 1.19 mm (left) and 1.58 mm (right) from the ring at the closest point.
- **Shoulder shell:** the feet are 2.20 mm (left) and 3.01 mm (right) from it. Straight down
  under the cheeks, the gap is 2.51 mm and 3.52 mm.
- **Screw and nut:**
  - The screw is 1.33 mm from the eye's round top and 5 mm above the eye's bottom.
  - Screw and nut are at least 1.4 mm from the ring and at least 3 mm from the shell.
  - The nut fits in its pocket without touching the foot.
- **Head:** the stubs are at least 21.9 mm from it.
- **Overlap:** none of the robot's surface is inside either foot.

Not checked, because it needs the real robot:

- The real rings' size, shape and spacing. This is what the trial is for.
- Whether the rings are solid or can move.
- The arch itself, which comes after these measurements.
