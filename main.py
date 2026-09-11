"""Main Entry Point for UKMARS Gemini Micromouse.

Unified control loop running on both Raspberry Pi Pico 2 W and PC simulation.
SW1 (Pin 15): Select Mode (cycles through registered mode modules)
SW2 (Pin 14): Execute Selected Mode

This module is a dispatcher and nothing else. The motor contract lives in
`drive.py`; each mode owns its own behaviour.
"""

import os
import sys
import time

try:
    PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
    if PACKAGE_DIR not in sys.path:
        sys.path.insert(0, PACKAGE_DIR)
except AttributeError:
    pass

import drive
import exploration
import max_speed_test
import setup
import speed_run

# The e-stop printed in CHEATSHEET.md is `import main; main.stop_motors()`. It is
# typed at a REPL with a robot already moving, so it is kept working here rather
# than being renamed out from under the operator.
stop_motors = drive.stop_motors


def run_bench(**kwargs):
    """Mode 3. Imported lazily on purpose.

    `bench_test` is 914 lines and is NOT in the minimal deployment set
    (CLAUDE.md, CHEATSHEET.md section 2). Importing it at module scope made a
    minimal Pico deployment fail to boot, and cost the RAM on every ordinary run.
    """
    import bench_test
    bench_test.run_all()


# 0-indexed array of available modes: (Name, Runner, extra CLI option names).
# Every runner accepts enable_render, so the dispatcher never special-cases an
# index. The third element lists which of CLI_OPTIONS that runner will accept,
# so an option meant for one mode is never silently handed to another.
MODES = [
    ("Explorer", exploration.run, ()),
    ("Speed Run", speed_run.run, ()),
    ("Bench Test", run_bench, ()),
    ("Max Speed Test", max_speed_test.run, ()),
    ("Lap Soak", speed_run.soak, ("laps", "route_path", "map_path", "power", "retrace")),
    ("Follow Route", speed_run.follow, ("route_path", "map_path", "laps", "retrace")),
]

# CLI overrides, so a headless PC run does not need a button. Index into MODES.
CLI_MODE_FLAGS = {
    "--step": 0,
    "--explorer": 0,
    "--speed": 1,
    "--bench": 2,
    "--maxspeed": 3,
    "--soak": 4,
    "--follow": 5,
}

# `--name=value` options, mapped to the keyword the runner takes. PC convenience
# only: on the Pico there is no command line, so these fall back to config.
CLI_OPTIONS = {
    "--route": ("route_path", str),
    "--map": ("map_path", str),
    "--laps": ("laps", int),
    "--power": ("power", float),
}

# Bare on/off flags, mapped the same way. Kept apart from CLI_OPTIONS because they
# carry no value: `--retrace=True` is not a thing anyone should have to type.
CLI_SWITCHES = {
    "--retrace": "retrace",
}


def blink_led(times, on_duration_ms=100, off_duration_ms=None):
    """Kept as an alias so REPL habits and bench_test keep working."""
    drive.blink_led(times, on_duration_ms, off_duration_ms)


def cli_options(argv, accepted):
    """The options this mode accepts, parsed from argv."""
    options = {}
    for flag, keyword in CLI_SWITCHES.items():
        if flag in argv and keyword in accepted:
            options[keyword] = True
    for arg in argv:
        for flag, (keyword, cast) in CLI_OPTIONS.items():
            if arg.startswith(flag + "=") and keyword in accepted:
                try:
                    options[keyword] = cast(arg.split("=", 1)[1])
                except ValueError:
                    print("Ignoring {}: not a valid value.".format(arg))
    return options


def selected_cli_mode(argv):
    """The mode index requested on the command line, or None."""
    for flag, index in CLI_MODE_FLAGS.items():
        if flag in argv:
            return index
    for arg in argv:
        if arg.startswith("--mode="):
            try:
                value = int(arg.split("=")[1])
            except ValueError:
                return None
            if 1 <= value <= len(MODES):
                return value - 1
    return None


def execute(mode_index, enable_render, argv=()):
    """Run one mode with the motor trace open around it."""
    name, runner, accepted = MODES[mode_index]
    options = cli_options(argv, accepted)
    print(f"Executing Mode {mode_index + 1}: {name}")
    if options:
        print(f"  options: {options}")
    try:
        runner(enable_render=enable_render, **options)
    finally:
        drive.stop_trace()


def main():
    enable_render = "--render" in sys.argv or "-r" in sys.argv

    # The trace is on by default without a sim, because a hardware run is
    # otherwise unobservable. `--log` forces it on for a PC run too.
    drive.start_trace(force="--log" in sys.argv)
    drive.stop_motors()

    print("Maze Mouse Ready.")
    for idx, (name, _, _accepted) in enumerate(MODES):
        print(f"  Mode {idx + 1}: {name}")
    print("SW1: Select Mode | SW2: Execute Selected Mode")

    cli_mode_idx = selected_cli_mode(sys.argv)
    if cli_mode_idx is not None:
        print(f"CLI requested Mode {cli_mode_idx + 1}: {MODES[cli_mode_idx][0]}")
        execute(cli_mode_idx, enable_render, sys.argv)
        return

    current_mode = 0  # 0-based index (Mode 1 default)

    # Initial check if SW1 or SW2 is held at startup
    if setup.sw1.value() == 0:
        current_mode = (current_mode + 1) % len(MODES)
        print(f"[SW1] Selected Mode {current_mode + 1}: {MODES[current_mode][0]}")
        drive.blink_led(current_mode + 1)
        while setup.sw1.value() == 0:
            time.sleep(0.02)
    elif setup.sw2.value() == 0:
        execute(current_mode, enable_render, sys.argv)
        return

    # Non-interactive PC sim default: if no button is held and running on PC
    if not setup.IS_HARDWARE:
        print("No button pressed (PC Sim). Defaulting to Mode 2: Speed Run.")
        execute(1, enable_render, sys.argv)
        return

    # Symmetrical button polling loop (Pico & PC sim)
    drive.blink_led(current_mode + 1)
    while True:
        if setup.sw1.value() == 0:
            current_mode = (current_mode + 1) % len(MODES)
            print(f"[SW1] Selected Mode {current_mode + 1}: {MODES[current_mode][0]}")
            drive.blink_led(current_mode + 1)
            while setup.sw1.value() == 0:
                time.sleep(0.02)
        elif setup.sw2.value() == 0:
            while setup.sw2.value() == 0:
                time.sleep(0.02)
            execute(current_mode, enable_render, sys.argv)
            break
        time.sleep(0.05)


if __name__ == "__main__":
    main()
