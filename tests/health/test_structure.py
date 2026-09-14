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
    "main.py", "config.py", "files.py", "motion.py", "world.py",
    "hal/__init__.py", "hal/setup.py", "hal/drive.py", "hal/clock.py",
    "hal/diagnostic_encoders.py",
    "record/__init__.py", "record/motor_log.py", "record/lap_log.py",
    "brain/__init__.py", "brain/maze.py", "brain/explorer.py",
    "brain/search_algorithms.py", "brain/commands.py",
    "modes/__init__.py", "modes/exploration.py", "modes/speed_run.py",
    "modes/follow_route.py", "modes/max_speed_test.py",
)

# First-party packages that DO go on the board, unlike sim/.
LOCAL_PACKAGES = ("brain", "hal", "modes", "record")

# Which package may import what. `config` and the MicroPython builtins are always
# allowed; everything else must be listed. This is how a directory earns its
# place: it encodes a rule that can fail, instead of sorting files by topic.
# Root modules every layer may read, because none of them is a layer's business:
# `config` is the numbers, `files` is os.stat without os.path.
ALWAYS_ALLOWED = ("config", "files")

LAYERS = {
    "brain": {"brain"},          # AGENTS.md invariant 2: the brain stays pure.
    "hal": {"hal", "record", "sim"},   # the board, and what it writes down.
    "record": {"hal", "record"},       # an instrument reads the clock, nothing more.
    # D-016 as a test: `modes` is absent from this set, so no mode may import
    # another mode. A mode that wants a driver takes `hal.drive`, and a mode
    # that wants the executor takes `motion`.
    "modes": {"brain", "hal", "motion", "record", "sim", "world"},
}

# Imported lazily, so it may sit outside the deployment set without breaking boot.
OPTIONAL_ON_HARDWARE = ("modes/bench_test.py",)

PICO_ONLY_BUILTINS = ("os", "sys", "time", "math", "gc", "array", "machine", "rp2", "utime")

# Imports MicroPython's `machine`/`rp2` directly, so it cannot load on a PC.
# setup.get_encoders() imports it lazily, on first use, for exactly this reason.
PICO_ONLY_MODULES = ("hal.diagnostic_encoders", "modes.bench_test")


def _local_modules():
    """Every first-party module, as a path relative to PACKAGE_DIR."""
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

    `from brain import maze` binds the name `maze` to the module `brain.maze`, so
    name and module have to be tracked apart. try/except imports count.
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


def _bound_names(path):
    """Every name the file binds locally: assignments, parameters, loops, with, except.

    Anything here shadows a module name legitimately -- `to_ascii(maze, ...)`
    takes a parameter called `maze`, and that is not a missing import.
    """
    names = set()
    for node in ast.walk(_tree(path)):
        # A LAZY import inside a function binds the name too. `main.run_bench`
        # and `setup.get_encoders` both import this way on purpose.
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                names.add(alias.asname or alias.name)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            names.add(node.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
            args = node.args
            for arg in args.posonlyargs + args.args + args.kwonlyargs:
                names.add(arg.arg)
            for arg in (args.vararg, args.kwarg):
                if arg is not None:
                    names.add(arg.arg)
        elif isinstance(node, ast.ClassDef):
            names.add(node.name)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            names.add(node.name)
        elif isinstance(node, ast.Global):
            names.update(node.names)
    return names


def test_a_module_reference_is_actually_imported():
    """`files.file_exists(...)` with no `import files` above it.

    CI caught this on 2026-09-14 and the suite did not: the NameError was inside
    a function only `__main__` calls, so importing the module proved nothing.
    A reference to a first-party module name that the file neither imports nor
    binds is a missing import, and it fails at RUN time, not at import time.
    """
    module_names = {_module_name(p).split(".")[-1] for p in _local_modules()}
    module_names |= {_module_name(p) for p in _local_modules() if "/" not in p}
    module_names |= {p.split("/")[-1][:-3] for p in _sim_modules()}
    module_names |= set(LOCAL_PACKAGES)

    failures = []
    for path in _local_modules() + [p.replace(".", "/") + ".py" for p in _sim_modules()]:
        available = set(_import_bindings(path)) | _bound_names(path)
        for name, attribute in sorted(_attribute_calls(path)):
            if name in module_names and name not in available:
                failures.append("{} calls {}.{} but never imports {}".format(
                    path, name, attribute, name))
    assert not failures, failures
    print("\u2713 test_a_module_reference_is_actually_imported passed")


def test_the_layers_hold():
    """AGENTS.md invariant 2, as a test instead of a review.

    Add a package to LAYERS when you create one, or the directory means nothing.
    """
    failures = []
    for path in _local_modules():
        package = path.split("/")[0] if "/" in path else ""
        if package not in LAYERS:
            continue
        for dotted in sorted(_import_bindings(path).values()):
            name = dotted.split(".")[0]
            if name in ALWAYS_ALLOWED or name in PICO_ONLY_BUILTINS or name in LAYERS[package]:
                continue
            failures.append("{} imports {}, which {}/ may not reach".format(
                path, dotted, package))
    assert not failures, failures
    print("\u2713 test_the_layers_hold passed")


def test_every_package_ships_its_init():
    """Static, because no runtime check on the PC can catch it.

    PEP 420 means `brain/` imports fine here without one. MicroPython has no
    namespace packages, so the same tree fails at boot on the board.
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
        if path in ("hal/setup.py", "hal/diagnostic_encoders.py", "modes/bench_test.py"):
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
    """config.py says what a number is; CONSTANTS.md says how far to trust it.

    Fails when config.py gains a constant the document does not name.
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
    test_a_module_reference_is_actually_imported,
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
