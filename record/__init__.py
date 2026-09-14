"""Instruments: what a run wrote down, so it can be read after the fact.

The Pico has no renderer and the PC was not there, so a hardware run is only
visible in what it recorded. `motor_log` traces commanded motor powers;
`lap_log` appends one row per lap of a route.

A module here may reach `hal`, and nothing above it. `test_the_layers_hold`
enforces the rule. Empty at import time on purpose.
"""
