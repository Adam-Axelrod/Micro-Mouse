"""Mode 5 drives the saved route many times and keeps the log. Driven here, not read.

The route that prompted the mode closed in HEADING and not in POSITION, so lap 2
would have set off from the wrong cell. Refusing that is the behaviour under test.
"""

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

PACKAGE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PACKAGE_DIR not in sys.path:
    sys.path.insert(0, PACKAGE_DIR)

import tempfile

from brain import commands
import config
from hal import setup
from modes import follow_route

CLOSED_ROUTE = config.ROUTES_DIR + "/lap3x3.mmc"
VIA_CENTRE_ROUTE = config.ROUTES_DIR + "/lap3x3_via_centre.mmc"

OPEN_ROUTE = """# micromouse route v1
# grid: 3x3
# start: 0 0 n
# goal: 1 1
F 2
R
F 2
R
F 2
R
F 1
R
F 1
H
"""


def write_route(text):
    path = os.path.join(tempfile.mkdtemp(), "route.mmc")
    with open(path, "w") as handle:
        handle.write(text)
    return path


# Never over the repository's lap_soak.csv: that file is a real run.
config.SOAK_LOG_PATH = os.path.join(tempfile.mkdtemp(), "lap_soak.csv")


def soak_log_path():
    config.SOAK_LOG_PATH = os.path.join(tempfile.mkdtemp(), "lap_soak.csv")
    return config.SOAK_LOG_PATH


def lap_rows(path):
    with open(path) as handle:
        return [line for line in handle
                if line.strip() and not line.startswith("#") and not line.startswith("lap,")]


def test_a_route_that_does_not_return_to_its_start_cell_is_refused():
    path = write_route(OPEN_ROUTE)
    assert follow_route.run(path, laps=2) is None, "2 laps of an open route must refuse"
    print("✓ test_a_route_that_does_not_return_to_its_start_cell_is_refused passed")


def test_one_lap_of_that_same_route_still_drives():
    """One lap is valid: the route only has to close if it repeats."""
    path = write_route(OPEN_ROUTE)
    assert follow_route.run(path, laps=1) is not None
    print("✓ test_one_lap_of_that_same_route_still_drives passed")


def test_a_route_that_leaves_its_own_grid_is_refused():
    path = write_route("# grid: 3x3\n# start: 0 0 n\nF 4\nH\n")
    assert follow_route.run(path, laps=1) is None
    print("✓ test_a_route_that_leaves_its_own_grid_is_refused passed")


def test_the_soak_writes_one_row_per_lap():
    log_path = soak_log_path()
    follow_route.run(soak=True, laps=3, route_path=CLOSED_ROUTE)
    rows = lap_rows(log_path)
    assert len(rows) == 3, rows
    assert [row.split(",")[0] for row in rows] == ["1", "2", "3"], rows
    print("✓ test_the_soak_writes_one_row_per_lap passed")


def test_every_logged_lap_carries_ticks_and_a_light_reading():
    log_path = soak_log_path()
    follow_route.run(soak=True, laps=2, route_path=VIA_CENTRE_ROUTE)
    for row in lap_rows(log_path):
        fields = row.strip().split(",")
        assert all(field != "" for field in fields), fields
        assert int(fields[4]) > 0, "no wheel travel was recorded for a lap"
    print("✓ test_every_logged_lap_carries_ticks_and_a_light_reading passed")


def test_a_closed_route_returns_the_sim_mouse_to_its_start_cell():
    """No ramp is modelled, so the sim should close a closed route exactly."""
    soak_log_path()
    follow_route.run(soak=True, laps=2, route_path=VIA_CENTRE_ROUTE)
    header = commands.read_route_header(VIA_CENTRE_ROUTE)
    state = setup.sim.get_mouse_state()
    start_x = (header["start"][0] + 0.5) * config.MM_PER_CELL
    start_y = (header["start"][1] + 0.5) * config.MM_PER_CELL
    offset_mm = ((state.x_mm - start_x) ** 2 + (state.y_mm - start_y) ** 2) ** 0.5
    assert offset_mm < 1.0, offset_mm
    print("✓ test_a_closed_route_returns_the_sim_mouse_to_its_start_cell passed")


def test_a_retrace_makes_an_open_route_lappable():
    path = write_route(OPEN_ROUTE)
    soak_log_path()
    assert follow_route.run(soak=True, laps=3, route_path=path, retrace=True) is not None
    assert len(lap_rows(config.SOAK_LOG_PATH)) == 3
    print("✓ test_a_retrace_makes_an_open_route_lappable passed")


def test_a_retraced_lap_returns_the_sim_mouse_to_its_start_cell():
    path = write_route(OPEN_ROUTE)
    soak_log_path()
    follow_route.run(soak=True, laps=2, route_path=path, retrace=True)
    state = setup.sim.get_mouse_state()
    offset_mm = ((state.x_mm - 0.5 * config.MM_PER_CELL) ** 2
                 + (state.y_mm - 0.5 * config.MM_PER_CELL) ** 2) ** 0.5
    assert offset_mm < 1.0, offset_mm
    print("✓ test_a_retraced_lap_returns_the_sim_mouse_to_its_start_cell passed")


TESTS = (
    test_a_retrace_makes_an_open_route_lappable,
    test_a_retraced_lap_returns_the_sim_mouse_to_its_start_cell,
    test_a_route_that_does_not_return_to_its_start_cell_is_refused,
    test_one_lap_of_that_same_route_still_drives,
    test_a_route_that_leaves_its_own_grid_is_refused,
    test_the_soak_writes_one_row_per_lap,
    test_every_logged_lap_carries_ticks_and_a_light_reading,
    test_a_closed_route_returns_the_sim_mouse_to_its_start_cell,
)


if __name__ == "__main__":
    if setup.sim is None:
        print("SKIPPED: no simulation engine (this is hardware)")
        sys.exit(0)
    for test in TESTS:
        test()
    print("ALL {} LAP SOAK TESTS PASSED".format(len(TESTS)))
