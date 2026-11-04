"""Download Unitree's official G1 23-DoF model (URDF + every mesh it uses) into a folder.

    python docs/src/fetch_g1_model.py g1mesh            # plus --extra for the other torso versions

Source: github.com/unitreerobotics/unitree_ros, robots/g1_description. The page exports,
the bracket checks and the head-arch checks all read meshes from this folder.
"""

import argparse
import re
import urllib.request
from pathlib import Path

BASE = "https://raw.githubusercontent.com/unitreerobotics/unitree_ros/master/robots/g1_description/"
URDF = "g1_23dof_rev_1_0.urdf"
EXTRA = ("torso_link_rev_1_0.STL", "torso_link.STL", "torso_link_with_2dof_head.STL")  # for compare_ring_models.py


def fetch(url: str, dest: Path) -> None:
    if dest.exists() and dest.stat().st_size > 0:
        return
    with urllib.request.urlopen(url, timeout=60) as r:
        dest.write_bytes(r.read())
    print("  %s (%d kB)" % (dest.name, dest.stat().st_size // 1024))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("folder", type=Path)
    p.add_argument("--extra", action="store_true", help="also the 29-DoF, original and 2-DoF-head torso meshes")
    args = p.parse_args()
    args.folder.mkdir(parents=True, exist_ok=True)
    fetch(BASE + URDF, args.folder / URDF)
    meshes = sorted(set(re.findall(r'filename="(?:package://[^"]*/)?meshes/([^"]+)"', (args.folder / URDF).read_text())))
    for name in meshes + (list(EXTRA) if args.extra else []):
        fetch(BASE + "meshes/" + name, args.folder / name)
    print("%d meshes in %s" % (len(list(args.folder.glob("*.STL"))), args.folder))


if __name__ == "__main__":
    main()
