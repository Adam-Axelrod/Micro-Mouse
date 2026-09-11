"""Run every test division and report per-division pass/fail.

    python3 tests/run_all.py            # everything
    python3 tests/run_all.py pure       # one division

Divisions are organised by RESPONSIBILITY, not by the mode that happens to
exercise them. The old suites were organised by mode, and they stayed green
through weeks of breakage because no suite imported the modules that were
broken. `contract/` exists specifically to stop that recurring: it asserts that
the symbols other modules call actually exist and behave.

Each division answers one question:

    logic/     does the brain compute the right thing? Cells and compass sides.
    hardware/  would this hold on the board? The drive boundary and the trace.
    sim/       is the simulation's arithmetic right? Kinematics, rays, renderer.
    health/    is the repo still well formed? Imports, deployment set, layering.

Plain functions and bare asserts. No pytest, no external dependencies.
"""

import os
import subprocess
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PACKAGE_DIR = os.path.dirname(TESTS_DIR)

DIVISIONS = ("logic", "hardware", "sim", "health")


def division_files(name):
    """Test module paths in a division, sorted, or [] if it does not exist yet."""
    directory = os.path.join(TESTS_DIR, name)
    if not os.path.isdir(directory):
        return []
    return [os.path.join(directory, f) for f in sorted(os.listdir(directory))
            if f.startswith("test_") and f.endswith(".py")]


def run_file(path):
    """Run one test module in a fresh interpreter.

    Returns (ok, summary, full_output). The summary is the last line of STDOUT
    only: third-party import warnings land on stderr, and merging the two let a
    pygame deprecation notice masquerade as the test result.
    """
    result = subprocess.run(
        [sys.executable, path],
        cwd=PACKAGE_DIR,
        capture_output=True,
        text=True,
    )
    stdout = result.stdout.strip()
    summary = stdout.split("\n")[-1] if stdout else "no output"
    return result.returncode == 0, summary, (result.stdout + result.stderr)


def main():
    wanted = sys.argv[1:] or list(DIVISIONS)
    unknown = [name for name in wanted if name not in DIVISIONS]
    if unknown:
        print("Unknown division(s): {}. Known: {}".format(
            ", ".join(unknown), ", ".join(DIVISIONS)))
        return 2

    total_passed = total_failed = 0
    missing = []
    failures = []

    for name in wanted:
        files = division_files(name)
        if not files:
            missing.append(name)
            print("\n{}/  -- no tests yet".format(name))
            continue

        print("\n{}/".format(name))
        for path in files:
            ok, summary, output = run_file(path)
            label = os.path.basename(path)
            if ok:
                total_passed += 1
                print("  PASS  {:<34} {}".format(label, summary))
            else:
                total_failed += 1
                failures.append((name, label, output))
                print("  FAIL  {:<34}".format(label))

    print("\n" + "=" * 64)
    for division, label, output in failures:
        print("\nFAILED  {}/{}".format(division, label))
        print(output.rstrip())
        print("-" * 64)

    print("{} module(s) passed, {} failed".format(total_passed, total_failed))
    if missing:
        print("Divisions with no tests yet: {}".format(", ".join(missing)))
    return 1 if total_failed else 0


if __name__ == "__main__":
    sys.exit(main())
