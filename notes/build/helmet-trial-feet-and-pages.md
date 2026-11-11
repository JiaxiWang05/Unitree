# Head-mount trial feet + GitHub pages update (2026-11-04)

Pushed to JiaxiWang05/Unitree main as 634f972.

## Trial feet (hardware/helmet_ring_mount/)
- Two printable ends of a head-top arch that hang on the G1's shoulder lifting rings (flat steel lugs, eye facing sideways).
- Ring geometry from torso_link_23dof_rev_1_0.STL by ray casting: eye 11.7 mm wide, round top R 5.83 centred x -0.9 / z 345 (torso frame mm), straight sides to z 339.5; plate 4.2 mm flat, up to 6.2 mm lower down; centres |y| 71.2 (left) and 73.6 (right): model 2.4 mm asymmetric; ~144.8 mm centre to centre.
- Changed from the plan: M5x25 ISO 4762 A2 + DIN 985 M5 nyloc + ISO 7089 M5 washer (not M6). With M6 the nut pocket broke through the cheek bottom and the nut came 1.3 mm from the shell bump beside the neck. Pin at z 347 (1.33 mm clear of the eye top). Slot 8.5 mm. Inner cheek 7 mm with a 1 mm chamfer on its bottom inner edge.
- check_trial_feet.py: ALL CLEAR (ring >=1.19, shell >=2.20, under cheeks >=2.51, head >=21.9, bolt/nut >=1.4 from ring and >=3 from shell). Output in check_output.txt. Takes ~1 min (KD-tree nearest points).
- Sources/build scripts used this session live in the scratchpad (render_feet.py, build_labday.py, build_scene.py, patch_labday.py, patch_scene.py) — the scratchpad can be wiped.

## Pages
- docs/g1-lab-day.html (Chinese): new phase E, bring item, sections #helmet (images inline as WebP), #parts (tables stack on phones), #laptop (Ubuntu/Mac), #walking.
- docs/g1-open-day-scene.html: "Questions people ask" FAQ (8 questions), status lists, head-mount link.
- Rebuilt from <old scratchpad>/viz/template.html and /scene/template2.html (backups: template.before-helmet.html, template2.before-faq.html). The private claude.ai artifact copies were NOT republished.

## Not done
- Code changes for multi-person prompts, duplex barge-in bug, non-stop talker cut-in, walking pause: still awaiting the user's go-ahead.
- Full arch: waits for the user's ring measurements.
