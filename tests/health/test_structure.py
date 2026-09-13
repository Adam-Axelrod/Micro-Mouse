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

# Copied to the board. AGENTS.md and CHEATSHEET.md section 2 must agree with this.
# Paths, not bare filenames: a package is only importable if its __init__.py
# travels with it, and MicroPython has no namespace packages to paper over the
# one that got left behind.
DEPLOYMENT_SET = (
    "main.py", "setup.py", "config.py", "drive.py",
    "brain/__init__.py", "brain/maze.py", "brain/explorer.py",
    "brain/search_algorithms.py", "brain/commands.py",
    "exploration.py", "speed_run.py", "motor_log.py", "max_speed_test.py",
    "lap_log.py", "clock.py", "diagnostic_encoders.py",
)

# First-party packages that DO go on the board, unlike sim/.
LOCAL_PACKAGES = ("brain",)

# Which package may import what. `config` and the MicroPython builtins are always
# allowed; everything else must be listed. This is how a directory earns its
# place: it encodes a rule that can fail, instead of sorting files by topic.
LAYERS = {
    "brain": {"brain"},   # AGENTS.md invariant 2: the brain stays pure.
}

# Imported lazily, so it may sit outside the deployment set without breaking boot.
OPTIONAL_ON_HARDWARE = ("bench_test.py",)

PICO_ONLY_BUILTINS = ("os", "sys", "time", "math", "gc", "array", "machine", "rp2", "utime")

# Imports MicroPython's `machine`/`rp2` directly, so it cannot load on a PC.
# setup.get_encoders() imports it lazily, on first use, for exactly this reason.
PICO_ONLY_MODULES = ("diagnostic_encoders",)


def _local_modules():
    """Every first-party module, as a path relative to PACKAGE_DIR.

    Paths rather than names, because "maze.py" stopped being unique the moment
    modules moved into packages.
    """
    paths = [f for f in os.listdir(PACKAGE_DIR)
             if f.endswith(".py") and not f.startswith("_")]
    for package in LOCAL_PACKAGES:
        paths += [package + "/" + f
                  for f in os.listdir(os.path.join(PACKAGE_DIR, package))
                  if f.endswith(".py") and not f.startswith("_")]
    return sorted(paths)


def _module_name(path):
    """"brain/maze.py" -> "brain.maze"; "brain/__init__.py" -> "brain"."""
    if path.endswith("/__init__.py"):
        return path[:-len("/__init__.py")]
    return path[:-3].replace("/", ".")


def _tree(path):
    with open(os.path.join(PACKAGE_DIR, path)) as handle:
        return ast.parse(handle.read(), filename=path)


def _import_bindings(path):
    """{local name: dotted target} for every import at module scope.

    `from brain import maze` binds the NAME `maze` to the MODULE `brain.maze`.
    Once modules live in packages the two stop being the same string, and a later
    `maze.num_file_import` resolves against the name, so both have to be kept.
    Imports inside functions are ignored; imports inside try/except are not,
    because that is how the sim and the board are told apart.
    """
    bindings = {}

    def add(node):
        if isinstance(node, ast.Import):
            for alias in node.names:
                bindings[alias.asname or alias.name.split(".")[0]] = alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                bindings[alias.asname or alias.name] = node.module + "." + alias.name

    for node in _tree(path).body:
        add(node)
        if isinstance(node, ast.Try):
            for inner in node.body + [n for handler in node.handlers for n in handler.body]:
                add(inner)
    return bindings


def _toplevel_imports(path):
    """Top-level module names imported at module scope: "brain" for brain.maze."""
    return {dotted.split(".")[0] for dotted in _import_bindings(path).values()}


def _attribute_calls(path):
    """(name, attribute) pairs for every `name.attr` reference in the file."""
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
    importable = [_module_name(p) for p in _local_modules()]
    importable = [m for m in importable if m not in PICO_ONLY_MODULES]
    failures = []
    for module in importable + _sim_modules():
        result = subprocess.run([sys.executable, "-c", "import " + module],
                                cwd=PACKAGE_DIR, capture_output=True, text=True)
        if result.returncode and "No module named 'pygame'" not in result.stderr:
            failures.append((module, result.stderr.strip().split("\n")[-1]))
    assert not failures, failures
    print("\u2713 test_every_module_imports passed")


def test_cross_module_calls_resolve():
    """The 7897f02 bug: callers kept calling main.drive_motors after it moved.

    Three suites stayed green for weeks because none imported those callers.
    """
    import importlib

    local = {_module_name(p) for p in _local_modules()} - set(PICO_ONLY_MODULES)
    failures = []
    for path in _local_modules():
        if _module_name(path) == "main":
            continue
        bindings = {name: dotted for name, dotted in _import_bindings(path).items()
                    if dotted in local}
        for name, attribute in sorted(_attribute_calls(path)):
            if name not in bindings:
                continue
            module = importlib.import_module(bindings[name])
            if not hasattr(module, attribute):
                failures.append("{} calls {}.{}, which does not exist".format(
                    path, name, attribute))
    assert not failures, failures
    print("\u2713 test_cross_module_calls_resolve passed")


def test_the_layers_hold():
    """A directory that encodes no rule is just a folder.

    brain/ exists so that AGENTS.md invariant 2 fails a test instead of a review.
    A brain module may reach `config` and other brain modules. Not `setup`, not
    `drive`, not `sim`, not `machine`. Add a package to LAYERS when it is created,
    or the directory means nothing.
    """
    failures = []
    for path in _local_modules():
        package = path.split("/")[0] if "/" in path else ""
        if package not in LAYERS:
            continue
        for dotted in sorted(_import_bindings(path).values()):
            name = dotted.split(".")[0]
            if name == "config" or name in PICO_ONLY_BUILTINS or name in LAYERS[package]:
                continue
            failures.append("{} imports {}, which {}/ may not reach".format(
                path, dotted, package))
    assert not failures, failures
    print("\u2713 test_the_layers_hold passed")


def test_every_package_ships_its_init():
    """CPython cannot catch this one, so it is checked statically.

    PEP 420 namespace packages mean `brain/` imports perfectly well on the PC
    with no __init__.py at all, so test_the_minimal_deployment_boots would stay
    green on a tree that cannot boot. MicroPython has no namespace packages: the
    board fails with a terse ImportError, which is the usual tell for an
    on-device fault and a miserable thing to diagnose at the bench.
    """
    for package in LOCAL_PACKAGES:
        init = package + "/__init__.py"
        assert os.path.exists(os.path.join(PACKAGE_DIR, init)), init
        assert init in DEPLOYMENT_SET, "{} is not in the deployment set".format(init)
    print("\u2713 test_every_package_ships_its_init passed")


def test_the_deployment_set_exists():
    missing = [f for f in DEPLOYMENT_SET
               if not os.path.exists(os.path.join(PACKAGE_DIR, f))]
    assert not missing, missing
    print("\u2713 test_the_deployment_set_exists passed")


def test_the_deployment_set_is_closed_under_imports():
    """Nothing on the board may import a module that is not on the board."""
    deployed = {_module_name(f) for f in DEPLOYMENT_SET}
    optional = {_module_name(f) for f in OPTIONAL_ON_HARDWARE}
    failures = []
    for path in DEPLOYMENT_SET:
        for dotted in sorted(_import_bindings(path).values()):
            name = dotted.split(".")[0]
            if name in PICO_ONLY_BUILTINS or name == "sim":
                continue  # sim is guarded by try/except; absent on the board by design
            if dotted in deployed or dotted in optional:
                continue
            # `from brain.maze import MazeStructure` binds a symbol, not a module.
            if dotted.rsplit(".", 1)[0] in deployed:
                continue
            failures.append("{} imports {}, which is not deployed".format(path, dotted))
    assert not failures, failures
    print("\u2713 test_the_deployment_set_is_closed_under_imports passed")


def test_bench_test_is_not_imported_at_module_scope():
    """It is 914 lines and not deployed, so a module-scope import fails at boot."""
    assert "bench_test" not in _toplevel_imports("main.py")
    print("\u2713 test_bench_test_is_not_imported_at_module_scope passed")


def test_pygame_stays_inside_sim():
    offenders = [p for p in _local_modules() if "pygame" in _toplevel_imports(p)]
    assert not offenders, offenders
    print("\u2713 test_pygame_stays_inside_sim passed")


def test_only_setup_probes_the_platform():
    """Every other module must take its hardware handles from setup."""
    offenders = []
    for path in _local_modules():
        if path in ("setup.py", "diagnostic_encoders.py"):
            continue
        if "machine" in _toplevel_imports(path):
            offenders.append(path)
    assert not offenders, offenders
    print("\u2713 test_only_setup_probes_the_platform passed")


def test_documented_paths_point_somewhere_real():
    for name in ("DEFAULT_MAZE", "MAZES_DIR", "ROUTES_DIR"):
        assert os.path.exists(getattr(config, name)), name
    print("✓ test_documented_paths_point_somewhere_real passed")


def test_committed_fixtures_parse():
    from brain import commands
    from brain import maze
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


def test_constants_md_names_every_constant():
    """CONSTANTS.md says where each number came from. config.py only says what.

    A constant with no provenance is how a PROVISIONAL number gets treated as a
    MEASURED one. This fails when config.py gains a constant and the document
    does not, which is the only moment anybody knows the answer.
    """
    with open(os.path.join(PACKAGE_DIR, "config.py")) as handle:
        source = handle.read()
    with open(os.path.join(PACKAGE_DIR, "CONSTANTS.md")) as handle:
        document = handle.read()
    declared = []
    for node in ast.parse(source).body:
        targets = node.targets if isinstance(node, ast.Assign) else []
        for target in targets:
            if isinstance(target, ast.Name) and target.id.isupper():
                declared.append(target.id)
        if isinstance(node, ast.Try):
            for inner in node.body + [n for h in node.handlers for n in h.body]:
                for target in getattr(inner, "targets", []):
                    if isinstance(target, ast.Name) and target.id.isupper():
                        declared.append(target.id)
    missing = sorted({name for name in declared if name not in document})
    assert not missing, "CONSTANTS.md does not mention: " + ", ".join(missing)
    print("\u2713 test_constants_md_names_every_constant passed")


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
    test_the_layers_hold,
    test_every_package_ships_its_init,
    test_the_deployment_set_exists,
    test_the_deployment_set_is_closed_under_imports,
    test_bench_test_is_not_imported_at_module_scope,
    test_pygame_stays_inside_sim,
    test_only_setup_probes_the_platform,
    test_documented_paths_point_somewhere_real,
    test_committed_fixtures_parse,
    test_working_files_are_not_tracked,
    test_constants_md_names_every_constant,
    test_the_cheatsheet_names_every_deployed_file,
)


if __name__ == "__main__":
    for test in TESTS:
        test()
    print("ALL {} STRUCTURE TESTS PASSED".format(len(TESTS)))
