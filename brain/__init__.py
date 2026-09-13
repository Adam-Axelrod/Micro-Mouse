"""The brain: cells, compass sides and headings. Nothing physical.

The directory IS the rule, the same way `sim/` is. A module in here may import
`config` and other `brain` modules, and nothing else. No `setup`, no `drive`, no
`sim`, no `machine`, no pixels, no noise (AGENTS.md invariant 2). The planner and
the Explorer have to stay answerable to "did the brain compute the right thing",
which is the question the `tests/logic/` division asks.

`tests/health/test_structure.py::test_the_layers_hold` enforces this. Until the
directory existed, the rule was prose and nothing could fail.

This package is empty at import time: importing `brain` must pull in nothing.
"""
