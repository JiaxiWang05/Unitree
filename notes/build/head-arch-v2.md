# Head arch v2 vs Unitree's official head camera mount (2026-11-08)

Pushed to JiaxiWang05/Unitree main as 6c48c85 (on top of afbae89).

## Unitree's official mount (xr_teleoperate Device.md 5.2)
- STEP zips from oss-global-cdn.unitree.com: classic head (98 mm) and renewed head (88 mm), 60 Hz and 30 Hz camera versions.
- Mount: 2x M4 clearance holes (4.5 mm), vertical, 98 mm apart (classic) / 88 mm (renewed) at its back end; camera plate tilted 49 deg (axis 0.65/0.76), M2 holes for the board; cover plate about 89 x 27 mm with two lens rings; small USB-C holder plate.
- Unitree's renewed-head picture shows the camera inside the head's top cap: fitting it means opening the head, and it looks down where the D435i looks. Not usable for the Brio + talk spot.

## v2 changes (hardware/helmet_ring_mount/helmet_arch.py)
- CH_W 5 x CH_D 4.5 mm cable channel in the back of each leg from z 413 over the arch to the middle; tie tunnels moved to x = BACK_X + CH_D + 1 (in front of the channel), on both legs.
- All |Z edges of the camera block filleted 4 mm. Crown 63.1 cm3 / 80 g (was 69.2 / 88 g).
- Ring screws: DIN 464 M5 x 25 knurled thumb screws into the DIN 985 nuts (check_helmet_arch.py models head 16 x 9 mm and shank 25 mm from the outer face).
- check: ALL CLEAR (ring 1.19/1.46, shell 2.20/3.02, thumb screw >= 1.42 ring / 3.46 shell, head 9.03, saddle 2.58-2.98, Brio FOV 0/1575 blocked, D435 0/1275, lidar 10.0/9.5 deg, 117 g, lens 1365 mm). Overhang count rose to 2163 mm2 because the channel floors are 5 mm bridges.
- Feet STLs unchanged. docs/ pages not touched (the lab day page still shows the v1 arch picture).
