"""Filesystem primitives that work on both targets.

Root level, like `config`, because every layer needs them and none of them is a
layer's business. `file_exists` lived in `brain/maze.py` until 2026-09-14, where
it made the pure layer the home of an `os.stat` call and made `record/` reach
into the brain to append a CSV.

Pico-portable: `os` only. MicroPython's `os` has no `path` submodule, so nothing
here may use `os.path`.
"""

import os


def file_exists(path_str):
    """os.path-free existence check.

    `os.stat` raises OSError for a missing path on both CPython and MicroPython.
    """
    try:
        os.stat(path_str)
        return True
    except OSError:
        return False


def ensure_dir(path_str):
    """Create the directory `path_str` sits in. Safe to call on every write.

    Artefacts live in `runs/`, and MicroPython will not create a missing parent
    for you: `open("runs/x.csv", "w")` on a fresh Pico raises ENOENT. Every
    writer calls this first rather than each one carrying its own guard.

    One level only. `os.makedirs` does not exist on MicroPython, and the tree is
    one directory deep by design.
    """
    index = path_str.rfind("/")
    if index <= 0:
        return
    directory = path_str[:index]
    if file_exists(directory):
        return
    try:
        os.mkdir(directory)
    except OSError:
        # Lost a race, or the filesystem is read-only. The open() that follows
        # reports the real problem; this must not be the thing that raises.
        pass
