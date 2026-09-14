"""One module per mode. The directory IS the rule, as in `brain/` and `sim/`.

A module here may reach the brain, the motion layer and the driver. It may NOT
import another mode (AGENTS.md D-016): a mode that needs a driver imports
`drive`, and a mode that needs the executor imports `motion`.
`test_the_layers_hold` enforces it. Empty at import time on purpose.
"""
