"""Structural invariants: is the repository still well formed?

Not behaviour. These check the shape the other divisions assume — that every
module imports, that the Pico deployment set is self-contained, that pygame
stays inside sim/, and that no cross-module call points at a symbol that moved.

Every bug this file guards has already happened here at least once.
"""

import ast
import os
import subprocess
import sys

PACKAGE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PACKAGE_DIR not in sys.path:
    sys.path.insert(0, PACKAGE_DIR)

import config

# Copied to the board. CLAUDE.md and CHEATSHEET.md section 2 must agree with this.
DEPLOYMENT_SET = (
    "main.py", "setup.py", "config.py", "drive.py", "maze.py", "explorer.py",
    "exploration.py", "speed_run.py", "search_algorithms.py", "commands.py",
    "motor_log.py", "max_speed_test.py", "lap_log.py", "clock.py",
    "diagnostic_encoders.py",
)

# Imported lazily, so it may sit outside the deployment set without breaking boot.
OPTIONAL_ON_HARDWARE = ("bench_test.py",)

PICO_ONLY_BUILTINS = ("os", "sys", "time", "math", "gc", "array", "machine", "rp2", "utime")

# Imports MicroPython's `machine`/`rp2` directly, so it cannot load on a PC.
# setup.get_encoders() imports it lazily, on first use, for exactly this reason.
PICO_ONLY_MODULES = ("diagnostic_encoders",)


def _root_modules():
    return sorted(f for f in os.listdir(PACKAGE_DIR)
                  if f.endswith(".py") and not f.startswith("_"))


def _tree(path):
    with open(os.path.join(PACKAGE_DIR, path)) as handle:
        return ast.parse(handle.read(), filename=path)


def _toplevel_imports(path):
    """Module names imported at module scope, ignoring imports inside functions."""
    names = set()
    for node in _tree(path).body:
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
        elif isinstance(node, ast.Try):
            for inner in node.body + [n for handler in node.handlers for n in handler.body]:
                if isinstance(inner, ast.Import):
                    names.update(alias.name.split(".")[0] for alias in inner.names)
                elif isinstance(inner, ast.ImportFrom) and inner.module:
                    names.add(inner.module.split(".")[0])
    return names


def _attribute_calls(path):
    """(module, attribute) pairs for every `module.attr` reference in the file."""
    pairs = set()
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            pairs.add((node.value.id, node.attr))
    return pairs


def _sim_modules():
    sim_dir = os.path.join(PACKAGE_DIR, "sim")
    return ["sim." + f[:-3] for f in sorted(os.listdir(sim_dir))
            if f.endswith(".py") and f != "__init__.py"]


def test_every_module_imports():
    importable = [f[:-3] for f in _root_modules() if f[:-3] not in PICO_ONLY_MODULES]
    failures = []
    for module in importable + _sim_modules():
        result = subprocess.run([sys.executable, "-c", "import " + module],
                                cwd=PACKAGE_DIR, capture_output=True, text=True)
        if result.returncode and "No module named 'pygame'" not in result.stderr:
            failures.append((module, result.stderr.strip().split("\n")[-1]))
    assert not failures, failures
    print("✓ test_every_module_imports passed")


def test_cross_module_calls_resolve():
    """The 7897f02 bug: callers kept calling main.drive_motors after it moved.

    Three suites stayed green for weeks because none imported those callers.
    """
    import importlib

    local_modules = {f[:-3] for f in _root_modules()} - set(PICO_ONLY_MODULES)
    failures = []
    for path in sorted(local_modules - {"main"}):
        imported = _toplevel_imports(path + ".py") & local_modules
        for module_name, attribute in sorted(_attribute_calls(path + ".py")):
            if module_name not in imported:
                continue
            module = importlib.import_module(module_name)
            if not hasattr(module, attribute):
                failures.append("{}.py calls {}.{}, which does not exist".format(
                    path, module_name, attribute))
    assert not failures, failures
    print("✓ test_cross_module_calls_resolve passed")


def test_the_deployment_set_exists():
    missing = [f for f in DEPLOYMENT_SET if not os.path.exists(os.path.join(PACKAGE_DIR, f))]
    assert not missing, missing
    print("✓ test_the_deployment_set_exists passed")


def test_the_deployment_set_is_closed_under_imports():
    """Nothing on the board may import a module that is not on the board."""
    deployed = {f[:-3] for f in DEPLOYMENT_SET}
    optional = {f[:-3] for f in OPTIONAL_ON_HARDWARE}
    failures = []
    for path in DEPLOYMENT_SET:
        for name in _toplevel_imports(path):
            if name in deployed or name in PICO_ONLY_BUILTINS or name in optional:
                continue
            if name == "sim":
                continue  # guarded by try/except; absent on the board by design
            failures.append("{} imports {}, which is not deployed".format(path, name))
    assert not failures, failures
    print("✓ test_the_deployment_set_is_closed_under_imports passed")


def test_bench_test_is_not_imported_at_module_scope():
    """It is 914 lines and not deployed, so a module-scope import fails at boot."""
    assert "bench_test" not in _toplevel_imports("main.py")
    print("✓ test_bench_test_is_not_imported_at_module_scope passed")


def test_pygame_stays_inside_sim():
    offenders = [p for p in _root_modules() if "pygame" in _toplevel_imports(p)]
    assert not offenders, offenders
    print("✓ test_pygame_stays_inside_sim passed")


def test_only_setup_probes_the_platform():
    """Every other module must take its hardware handles from setup."""
    offenders = []
    for path in _root_modules():
        if path in ("setup.py", "diagnostic_encoders.py"):
            continue
        if "machine" in _toplevel_imports(path):
            offenders.append(path)
    assert not offenders, offenders
    print("✓ test_only_setup_probes_the_platform passed")


def test_documented_paths_point_somewhere_real():
    for name in ("DEFAULT_MAZE", "MAZES_DIR", "ROUTES_DIR"):
        assert os.path.exists(getattr(config, name)), name
    print("✓ test_documented_paths_point_somewhere_real passed")


def test_committed_fixtures_parse():
    import commands
    import maze
    for directory, reader in ((config.MAZES_DIR, maze.num_file_import),
                              (config.ROUTES_DIR, commands.read_command_file)):
        for root, _dirs, files in os.walk(directory):
            for name in files:
                if name.endswith(".num") or name.endswith(".mmc"):
                    reader(os.path.join(root, name))
    print("✓ test_committed_fixtures_parse passed")


def test_working_files_are_not_tracked():
    """belief.num and route.mmc are run artefacts, not fixtures."""
    tracked = subprocess.run(["git", "ls-files"], cwd=PACKAGE_DIR,
                             capture_output=True, text=True).stdout.split("\n")
    for artefact in ("belief.num", "route.mmc", "motor_log.csv", "lap_soak.csv"):
        assert artefact not in tracked, artefact
    print("✓ test_working_files_are_not_tracked passed")


def test_the_cheatsheet_names_every_deployed_file():
    """The operator copies the list in CHEATSHEET.md section 2, not DEPLOYMENT_SET."""
    with open(os.path.join(PACKAGE_DIR, "CHEATSHEET.md")) as handle:
        text = handle.read()
    missing = [name for name in DEPLOYMENT_SET if name not in text]
    assert not missing, missing
    print("✓ test_the_cheatsheet_names_every_deployed_file passed")


TESTS = (
    test_every_module_imports,
    test_cross_module_calls_resolve,
    test_the_deployment_set_exists,
    test_the_deployment_set_is_closed_under_imports,
    test_bench_test_is_not_imported_at_module_scope,
    test_pygame_stays_inside_sim,
    test_only_setup_probes_the_platform,
    test_documented_paths_point_somewhere_real,
    test_committed_fixtures_parse,
    test_working_files_are_not_tracked,
    test_the_cheatsheet_names_every_deployed_file,
)


if __name__ == "__main__":
    for test in TESTS:
        test()
    print("ALL {} STRUCTURE TESTS PASSED".format(len(TESTS)))
