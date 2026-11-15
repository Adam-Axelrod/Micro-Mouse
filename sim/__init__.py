"""PC-only simulation and rendering. Never deployed to the Pico.

The dual-target rule is physical here: if a module lives in this package it uses
CPython-only libraries (`pygame`) or exists purely to stand in for hardware, so it
must never be copied to the board. Everything the Pico runs stays at the package
root.

Nothing in here is imported unconditionally. `setup.py` reaches for
`sim.sim_machine` and `sim.scene` only when the real `machine` module is absent,
and `sim.scene` imports `sim.renderer` only when a window is asked for. No mode
imports this package: it asks `setup` for `wait`, `now_ms`, `diff_ms` and
`scene()`. A Pico deployment without this directory behaves exactly as it does
today.

This package is deliberately empty at import time: importing `sim` must not pull
in `pygame`.
"""
