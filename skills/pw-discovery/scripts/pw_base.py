"""pw_base.py - what the plugin's scripts share: which version is installed, and how a file is written.

Part of the Product Weaver pw-discovery skill · https://productweaver.com

kb_tool.py, kb_map.py, pw_usage.py and pw_about.py each load this file from beside them, so the plugin's version is
read in one way and every file is replaced in one way. It runs nothing by itself, reads only the plugin's own
files, and makes no network call. Only the standard library is used.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import time
from pathlib import Path
from typing import Any, Callable

PLUGIN = "productweaver"
VERSION_PATTERN = r"[0-9]+\.[0-9]+\.[0-9]+"
MANIFESTS = ("plugin.json", ".claude-plugin/plugin.json")  # at the plugin's root; hosts read one or the other
HERE = Path(__file__).resolve().parent  # <plugin>/skills/pw-discovery/scripts


def is_version(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(VERSION_PATTERN, value, re.ASCII) is not None


def plugin_root() -> Path | None:
    """The plugin's folder, or None for a copy of the scripts that sits too near the disk's root to have one."""
    return HERE.parents[2] if len(HERE.parents) > 2 else None


def manifest_version(path: Path) -> str | None:
    """The version one manifest gives. None when the file is missing, is not this plugin's, or holds no version."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, RecursionError):
        return None
    if not isinstance(data, dict) or data.get("name") != PLUGIN:
        return None
    return data["version"] if is_version(data.get("version")) else None


def plugin_version() -> str | None:
    """The plugin's version, from the first manifest that gives one. None outside the plugin folder."""
    root = plugin_root()
    found = (manifest_version(root / name) for name in MANIFESTS) if root else ()
    return next((version for version in found if version), None)


def tool_version(text: str | None = None) -> str | None:
    """The version of the kb_tool.py beside this file, or of the kb_tool.py source given as `text`."""
    if text is None:
        try:
            text = (HERE / "kb_tool.py").read_text(encoding="utf-8")
        except (OSError, ValueError):
            return None
    found = re.search(r'^__version__ = "([^"\n]*)"', text, re.M)
    return found.group(1) if found and is_version(found.group(1)) else None


def write_atomic(path: Any, data: str | bytes, check: Callable[[str], Any] | None = None,
                 mode: int | None = None) -> None:
    """Write a temporary file beside the target, then swap it in, so a reader never sees half a file.

    `check` is called with the temporary file's path before the swap: when it raises, the target is left as it
    was. A file that is replaced keeps its mode (a map or a study holds names and quotes: the mode the user gave
    it stays); a new file gets `mode` when one is given. On Windows another program may hold the old file for a
    moment: try again, then write in place."""
    path = os.fspath(path)
    raw = data.encode("utf-8") if isinstance(data, str) else data
    tmp = f"{path}.{os.getpid()}.tmp"
    try:
        with open(tmp, "wb") as handle:
            handle.write(raw)
        if check:
            check(tmp)
        with contextlib.suppress(OSError):
            if os.path.exists(path):
                shutil.copymode(path, tmp)
            elif mode is not None:
                os.chmod(tmp, mode)
        for attempt in range(3):
            try:
                os.replace(tmp, path)
                return
            except PermissionError:
                if attempt == 2:
                    with open(path, "wb") as handle:
                        handle.write(raw)
                    return
                time.sleep(0.2)
    finally:
        with contextlib.suppress(OSError):
            os.remove(tmp)
