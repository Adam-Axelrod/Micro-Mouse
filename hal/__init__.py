"""The hardware abstraction layer: everything that touches the board.

The directory IS the rule. `setup` is the ONE place the platform is probed and
the pins are constructed; `drive` is the ONE place a wheel moves; `clock` is the
ONE clock a timed run reads. A module here may reach `record` and the PC-only
`sim`, and nothing above it: no mode, no brain, no motion.

Nothing here computes a DURATION. `motion.py` turns a distance or an angle into
seconds, and this layer holds a power for as long as it is told to.
`test_the_layers_hold` enforces the rule. Empty at import time on purpose.
"""
