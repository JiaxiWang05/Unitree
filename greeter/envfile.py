"""Load settings and API keys from an env file (never from the code).

The default file is ``~/.config/g1-greeter/greeter.env`` (mode 600), the same
file the systemd service reads. Lines look like ``KEY=value``; ``#`` starts a
comment and an optional ``export`` prefix is ignored. Variables already set in
the environment win.
"""

from __future__ import annotations

import logging
import os
import stat
from pathlib import Path
from typing import List, Optional

log = logging.getLogger(__name__)

DEFAULT_ENV_FILE = Path.home() / ".config" / "g1-greeter" / "greeter.env"


def parse_env(text: str) -> dict:
    values = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        key, sep, value = line.partition("=")
        key = key.strip()
        if not sep or not key.replace("_", "").isalnum():
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        values[key] = value
    return values


def load_env_file(path: Optional[Path] = None) -> List[str]:
    """Put the file's variables into ``os.environ``; returns the names loaded (never values)."""
    path = Path(path or os.environ.get("GREETER_ENV_FILE") or DEFAULT_ENV_FILE).expanduser()
    if not path.is_file():
        return []
    mode = path.stat().st_mode
    if mode & (stat.S_IRGRP | stat.S_IROTH):
        log.warning("%s is readable by other users; run: chmod 600 %s", path, path)
    loaded = []
    for key, value in parse_env(path.read_text()).items():
        if value and key not in os.environ:
            os.environ[key] = value
            loaded.append(key)
    return loaded


def mask(secret: Optional[str]) -> str:
    """For status lines: shows that a key is present without revealing it."""
    if not secret:
        return "missing"
    return "set (%d chars, ends …%s)" % (len(secret), secret[-4:]) if len(secret) > 12 else "set"


def set_value(name: str, value: str, path: Optional[Path] = None) -> Path:
    """Add or replace ``name=value`` in the env file, creating it with mode 600."""
    path = Path(path or DEFAULT_ENV_FILE).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = path.read_text().splitlines() if path.is_file() else []
    lines = [line for line in lines if not line.strip().startswith(name + "=")]
    lines.append("%s=%s" % (name, value))
    old_umask = os.umask(0o077)
    try:
        path.write_text("\n".join(lines) + "\n")
    finally:
        os.umask(old_umask)
    os.chmod(path, 0o600)
    return path


def main(argv=None) -> None:
    """``python3 -m greeter.envfile --set NAME`` reads the value from stdin (so it never hits argv or history)."""
    import argparse
    import sys

    p = argparse.ArgumentParser(prog="python3 -m greeter.envfile")
    p.add_argument("--set", metavar="NAME", required=True, help="variable to store, e.g. OPENAI_API_KEY")
    p.add_argument("--file", default=str(DEFAULT_ENV_FILE))
    args = p.parse_args(argv)
    value = sys.stdin.readline().strip()
    if not value:
        sys.exit("no value on stdin")
    path = set_value(args.set, value, Path(args.file))
    print("stored %s in %s (%s)" % (args.set, path, mask(value)))


if __name__ == "__main__":
    main()
