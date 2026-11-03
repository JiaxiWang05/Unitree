# Fit and view checks for the chest bracket

The scripts used to check `brio_chest_mount.stl` against Unitree's G1 model.
`check_output.txt` is the output for the version in this folder.

They need Python with `cadquery trimesh numpy scipy manifold3d matplotlib rtree`
and three files from [unitree_ros](https://github.com/unitreerobotics/unitree_ros)
(`robots/g1_description/`): `meshes/torso_link_23dof_rev_1_0.STL`,
`meshes/head_link.STL` and `g1_23dof_rev_1_0.urdf`.

```bash
python chest_map.py torso_link_23dof_rev_1_0.STL chest_map.npy
python check_fit3.py .. . ../brio_chest_mount.stl torso_link_23dof_rev_1_0.STL head_link.STL preview
```

| Script | What it does |
|---|---|
| `chest_map.py` | Depth map of the chest front, used to measure the gap between the bracket and the chest |
| `check_fit3.py` | Pads on the chest, camera and USB-C plug on the seat, screw depth, the camera's view, the head D435i's view of the talk spot, previews |
| `sweep.py` | Trade-off between shelf height and length: D435i margin, plug clearance, room to bend the cable |
| `view_step.py` | Small matplotlib renderer for the previews |
