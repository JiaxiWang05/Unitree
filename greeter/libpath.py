"""Find the shared libraries that ``scripts/install.sh`` puts in the home folder.

The systemd service sets ``LD_LIBRARY_PATH`` itself. A command typed by hand over SSH
(``.venv/bin/python -m greeter --check``) does not, and then the Unitree SDK cannot load
CycloneDDS (and, on JetPack 6, torch cannot load cuSPARSELt). The dynamic loader reads the
variable only when a process starts, so the fix is to start the same command again with it set.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import List, Optional, Sequence

LIB_DIRS = ("cyclonedds/install/lib", ".local/cusparselt/lib")  # under the home folder, as install.sh
MARK = "GREETER_LIBPATH_SET"


def missing(home: Path, current: str) -> List[str]:
    """Library folders that exist under ``home`` and are not on ``current`` yet."""
    have = [p for p in current.split(":") if p]
    return [str(home / d) for d in LIB_DIRS if (home / d).is_dir() and str(home / d) not in have]


def ensure(module: str, argv: Optional[Sequence[str]] = None) -> None:
    """Restart ``python -m module`` once with the library folders on ``LD_LIBRARY_PATH``.

    Does nothing off Linux, when nothing is missing, or when it has already restarted once.
    """
    if not sys.platform.startswith("linux") or os.environ.get(MARK):
        return
    current = os.environ.get("LD_LIBRARY_PATH", "")
    add = missing(Path.home(), current)
    if not add:
        return
    env = dict(os.environ)
    env["LD_LIBRARY_PATH"] = ":".join(add + ([current] if current else []))
    env[MARK] = "1"
    args = list(sys.argv[1:] if argv is None else argv)
    os.execve(sys.executable, [sys.executable, "-m", module] + args, env)
