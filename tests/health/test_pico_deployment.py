"""The minimal Pico deployment set must boot with nothing else present.

Copies only the deployed files into an empty directory beside a stub `machine`
module, then imports main. main.py once imported bench_test at module scope,
which is not deployed, so the board did not boot from the documented file list
and nothing caught it.
"""

import os
import shutil
import subprocess
import sys
import tempfile

PACKAGE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PACKAGE_DIR not in sys.path:
    sys.path.insert(0, PACKAGE_DIR)

from tests.health.test_structure import DEPLOYMENT_SET

MACHINE_STUB = '''"""Stand-in for MicroPython's C `machine` module."""


class Pin:
    IN, OUT, PULL_UP = 0, 1, 2

    def __init__(self, *args, **kwargs):
        pass

    def value(self, new_value=None):
        return 1


class PWM:
    def __init__(self, *args, **kwargs):
        pass

    def freq(self, *args):
        pass

    def duty_u16(self, *args):
        pass


class ADC:
    def __init__(self, *args, **kwargs):
        pass

    def read_u16(self):
        return 0
'''

BOOT_CHECK = '''
import os
import sys
from hal import drive
from record import motor_log
import main
from hal import setup

assert setup.IS_HARDWARE, "the machine stub was not picked up"
assert not [m for m in sys.modules if m == "sim" or m.startswith("sim.")], "sim/ was imported"
assert not [m for m in sys.modules if m == "tools" or m.startswith("tools.")], "tools/ was imported at boot"
assert not os.path.exists("tools"), "the deployment holds a tools/ folder"
assert "pygame" not in sys.modules, "pygame reached the board"
assert callable(main.stop_motors), "the CHEATSHEET e-stop is gone"

assert setup.TRACE_BY_DEFAULT and setup.REAL_BOARD
world = setup.scene(grid=(3, 3), start_pose=(1, 1, "n"), render=True)
world.show(belief=None, route=None, done=None, animate=False)
assert world.pose() is None, "the robot has no simulated pose"
started_ms = setup.now_ms()
setup.wait(0.01)
assert setup.diff_ms(setup.now_ms(), started_ms) >= 0
assert motor_log.MOTOR_TRACE.clock_ms is setup.now_ms

motor_log.start_trace()
assert motor_log.MOTOR_TRACE.is_recording(), "the trace did not open without a sim"
drive.drive_motors(0.55, 0.55)
drive.stop_motors()
motor_log.stop_trace()

assert [mode[0] for mode in main.MODES] == ["Explorer", "Speed Run", "Bench Test", "Follow Route"], main.MODES
assert "--maxspeed" not in main.CLI_MODE_FLAGS
assert main.selected_cli_mode(("--follow",)) == 3
assert main.selected_cli_mode(("--soak",)) == 3
print("OK")
'''


def _build_deployment(directory):
    """Copy the deployment set into `directory`, tree and all.

    The set holds paths. Flattening brain/maze.py would boot a layout the board
    will never have.
    """
    for filename in DEPLOYMENT_SET:
        target = os.path.join(directory, filename)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copy(os.path.join(PACKAGE_DIR, filename), target)
    # The board's runs/ directory, deployed the way CHEATSHEET.md section 2 says.
    os.makedirs(os.path.join(directory, "runs"), exist_ok=True)
    shutil.copy(os.path.join(PACKAGE_DIR, "routes", "lap3x3.mmc"),
                os.path.join(directory, "runs", "route.mmc"))
    with open(os.path.join(directory, "machine.py"), "w") as handle:
        handle.write(MACHINE_STUB)


def test_the_minimal_deployment_boots():
    with tempfile.TemporaryDirectory() as directory:
        _build_deployment(directory)
        result = subprocess.run([sys.executable, "-c", BOOT_CHECK],
                                cwd=directory, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr.strip()
        assert "OK" in result.stdout
    print("✓ test_the_minimal_deployment_boots passed")


def test_a_deployment_has_no_tools_folder():
    """tools/ is optional: the boot check above runs on a robot without it."""
    with tempfile.TemporaryDirectory() as directory:
        _build_deployment(directory)
        assert not os.path.exists(os.path.join(directory, "tools"))
        result = subprocess.run(
            [sys.executable, "-c",
             "import main\nfrom tools import bench_test"],
            cwd=directory, capture_output=True, text=True)
        assert result.returncode != 0 and "tools" in result.stderr, \
            "the bench module was reachable with no tools/ folder"
        result = subprocess.run(
            [sys.executable, "-c",
             "import main\nmain.run_bench()"],
            cwd=directory, capture_output=True, text=True)
        assert "tools" in result.stderr, "main.run_bench did not reach for tools/"
    print("\u2713 test_a_deployment_has_no_tools_folder passed")


def test_a_deployment_missing_drive_fails_loudly():
    """Proves the check above can actually fail."""
    with tempfile.TemporaryDirectory() as directory:
        _build_deployment(directory)
        os.remove(os.path.join(directory, "hal", "drive.py"))
        result = subprocess.run([sys.executable, "-c", BOOT_CHECK],
                                cwd=directory, capture_output=True, text=True)
        assert result.returncode != 0, "a deployment with no hal/drive.py appeared to boot"
    print("✓ test_a_deployment_missing_drive_fails_loudly passed")


def test_the_deployment_set_needs_no_third_party_package():
    """MicroPython has no pip. Everything deployed imports builtins only."""
    with tempfile.TemporaryDirectory() as directory:
        _build_deployment(directory)
        result = subprocess.run(
            [sys.executable, "-S", "-c", "import main; print('OK')"],
            cwd=directory, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr.strip()
    print("✓ test_the_deployment_set_needs_no_third_party_package passed")


def test_pico_mode_four_defaults_to_retraced_stress_test():
    check = BOOT_CHECK + """
from modes import follow_route
import config
seen = []
def capture_route(path, laps, retrace=False):
    seen.append((path, laps, retrace))
    return None  # Refuse before motors arm; exercise dispatcher and defaults.
follow_route._load_route = capture_route
index = next(i for i, mode in enumerate(main.MODES) if mode[0] == "Follow Route")
main.execute(index, False)
assert seen == [(config.SAVED_ROUTE, config.SOAK_LAPS, True)], seen
main.execute(index, False, ("--laps=5", "--power=0.3"))
assert seen[-1] == (config.SAVED_ROUTE, 5, True), seen
"""
    with tempfile.TemporaryDirectory() as directory:
        _build_deployment(directory)
        result = subprocess.run([sys.executable, "-c", check],
                                cwd=directory, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr.strip()
        assert "Drive power 0.40" in result.stdout, result.stdout
        assert "Drive power 0.30" in result.stdout, result.stdout
    print("✓ test_pico_mode_four_defaults_to_retraced_stress_test passed")


def test_micropico_upload_includes_operator_route_and_map():
    import json
    with open(os.path.join(PACKAGE_DIR, ".vscode", "settings.json")) as handle:
        settings = json.load(handle)
    assert settings.get("micropico.syncAllFileTypes") or {"mmc", "num"}.issubset(
        settings.get("micropico.syncFileTypes", [])), "MicroPico upload skips route/map files"
    print("✓ test_micropico_upload_includes_operator_route_and_map passed")


TESTS = (
    test_micropico_upload_includes_operator_route_and_map,
    test_pico_mode_four_defaults_to_retraced_stress_test,
    test_the_minimal_deployment_boots,
    test_a_deployment_has_no_tools_folder,
    test_a_deployment_missing_drive_fails_loudly,
    test_the_deployment_set_needs_no_third_party_package,
)


if __name__ == "__main__":
    for test in TESTS:
        test()
    print("ALL {} PICO DEPLOYMENT TESTS PASSED".format(len(TESTS)))
