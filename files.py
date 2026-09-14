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
