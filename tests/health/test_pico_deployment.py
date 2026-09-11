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
import sys
import drive
import main
import setup

assert setup.IS_HARDWARE, "the machine stub was not picked up"
assert not [m for m in sys.modules if m == "sim" or m.startswith("sim.")], "sim/ was imported"
assert "bench_test" not in sys.modules, "bench_test was imported at module scope"
assert "pygame" not in sys.modules, "pygame reached the board"
assert callable(main.stop_motors), "the CHEATSHEET e-stop is gone"

drive.start_trace()
assert drive.MOTOR_TRACE.is_recording(), "the trace did not open without a sim"
drive.drive_motors(0.55, 0.55)
drive.stop_motors()
drive.stop_trace()

assert len(main.MODES) == 6, main.MODES
print("OK")
'''


def _build_deployment(directory):
    for filename in DEPLOYMENT_SET:
        shutil.copy(os.path.join(PACKAGE_DIR, filename), directory)
    shutil.copy(os.path.join(PACKAGE_DIR, "routes", "lap3x3.mmc"),
                os.path.join(directory, "route.mmc"))
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


def test_a_deployment_missing_drive_fails_loudly():
    """Proves the check above can actually fail."""
    with tempfile.TemporaryDirectory() as directory:
        _build_deployment(directory)
        os.remove(os.path.join(directory, "drive.py"))
        result = subprocess.run([sys.executable, "-c", BOOT_CHECK],
                                cwd=directory, capture_output=True, text=True)
        assert result.returncode != 0, "a deployment with no drive.py appeared to boot"
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


TESTS = (
    test_the_minimal_deployment_boots,
    test_a_deployment_missing_drive_fails_loudly,
    test_the_deployment_set_needs_no_third_party_package,
)


if __name__ == "__main__":
    for test in TESTS:
        test()
    print("ALL {} PICO DEPLOYMENT TESTS PASSED".format(len(TESTS)))
