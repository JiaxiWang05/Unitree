# Sources of the 3D pages

The three 3D pages in `docs/` are built from a hand-written template plus mesh data
exported from Unitree's official G1 model and the bracket.

| Page | Template | Data |
|---|---|---|
| `g1-open-day-scene.html` | `scene/template.html` | `window.SCENE` from `scene/export_scene.py` (the whole standing robot, elbows bent, with the chest bracket, Brio and cable; meshes packed as gzip + base64) |
| `g1-open-day-animation.html` | the scene page, plus `animation-only.html` (hides everything but the 3D view; Space pauses) | same as above |
| `g1-lab-day.html` | `lab-day/template.html` | `window.GEOM` from `lab-day/export_geom.py` (the chest, bracket, Brio, screws and cable for the fitting steps) |

## Rebuild

```bash
python docs/src/fetch_g1_model.py g1mesh          # Unitree's URDF and meshes (unitree_ros)
python docs/src/scene/export_scene.py docs/src/scene hardware/brio_chest_mount g1mesh \
    hardware/brio_chest_mount/brio_chest_mount.stl scene.js
python docs/src/lab-day/export_geom.py hardware/brio_chest_mount g1mesh geom.js \
    hardware/brio_chest_mount/brio_chest_mount.stl
python docs/src/build_pages.py scene.js geom.js     # writes the three pages in docs/
```

The exports need `numpy`, `trimesh` (with `fast_simplification`) and CadQuery for
`brio_chest_mount.py`. `build_pages.py` only needs Python.

To change the text of a page, edit its template and run `build_pages.py` again. The
templates are written without `<html>`, `<head>` and `<body>`; `build_pages.py` adds the
document skeleton, so the pages it writes match the published ones byte for byte.

The pages load three.js r128 from cdnjs and jsDelivr and fonts from Google Fonts, so they
need an internet connection.
