"""Main Entry Point for UKMARS Gemini Micromouse.

Unified control loop running on both Raspberry Pi Pico 2 W and PC simulation.
SW1 (Pin 15): Select Mode (cycles through registered mode modules)
SW2 (Pin 14): Execute Selected Mode
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

import bench_test
import exploration
import speed_run
import setup

def run_bench(**kwargs):
    import bench_test
    bench_test.run_all()


# 0-indexed array of available modes: (Name, Runner Function)
MODES = [
    ("Explorer", exploration.run),
    ("Speed Run", speed_run.run),
    ("Bench Test", run_bench),
]


def blink_led(times, on_duration_ms=100, off_duration_ms=100):
    for _ in range(times):
        setup.LED_PIN.value(1)
        time.sleep(on_duration_ms / 1000.0)
        setup.LED_PIN.value(0)
        time.sleep(off_duration_ms / 1000.0)


def main():
    enable_render = "--render" in sys.argv or "-r" in sys.argv

    # Check CLI mode overrides (0-indexed map)
    cli_mode_idx = None
    if "--step" in sys.argv or "--explorer" in sys.argv:
        cli_mode_idx = 0
    elif "--speed" in sys.argv:
        cli_mode_idx = 1
    elif "--bench" in sys.argv:
        cli_mode_idx = 2
    else:
        for arg in sys.argv:
            if arg.startswith("--mode="):
                try:
                    val = int(arg.split("=")[1])
                    if 1 <= val <= len(MODES):
                        cli_mode_idx = val - 1
                except ValueError:
                    pass

    speed_run.stop_motors()

    print("Maze Mouse Ready.")
    for idx, (name, _) in enumerate(MODES):
        print(f"  Mode {idx + 1}: {name}")
    print("SW1: Select Mode | SW2: Execute Selected Mode")

    # If CLI requested a specific mode directly, execute it
    if cli_mode_idx is not None:
        name, runner = MODES[cli_mode_idx]
        print(f"CLI requested Mode {cli_mode_idx + 1}: {name}")
        runner(enable_render=enable_render) if cli_mode_idx < 2 else runner()
        return

    current_mode = 0  # 0-based index (Mode 1 default)

    # Initial check if SW1 or SW2 is held at startup
    if setup.sw1.value() == 0:
        current_mode = (current_mode + 1) % len(MODES)
        print(f"[SW1] Selected Mode {current_mode + 1}: {MODES[current_mode][0]}")
        blink_led(current_mode + 1)
        while setup.sw1.value() == 0:
            time.sleep(0.02)
    elif setup.sw2.value() == 0:
        name, runner = MODES[current_mode]
        print(f"[SW2] Executing Mode {current_mode + 1}: {name}")
        runner(enable_render=enable_render) if current_mode < 2 else runner()
        return

    # Non-interactive PC sim default: if no button is held and running on PC
    if not setup.IS_HARDWARE:
        print("No button pressed (PC Sim). Defaulting to Mode 2: Speed Run.")
        speed_run.run(enable_render=enable_render)
        return

    # Symmetrical button polling loop (Pico & PC sim)
    blink_led(current_mode + 1)
    while True:
        if setup.sw1.value() == 0:
            current_mode = (current_mode + 1) % len(MODES)
            print(f"[SW1] Selected Mode {current_mode + 1}: {MODES[current_mode][0]}")
            blink_led(current_mode + 1)
            while setup.sw1.value() == 0:
                time.sleep(0.02)
        elif setup.sw2.value() == 0:
            name, runner = MODES[current_mode]
            print(f"[SW2] Executing Mode {current_mode + 1}: {name}")
            while setup.sw2.value() == 0:
                time.sleep(0.02)
            runner(enable_render=enable_render) if current_mode < 2 else runner()
            break
        time.sleep(0.05)


if __name__ == "__main__":
    main()

