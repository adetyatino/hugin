"""`hugin` must be an installed package, not a directory on PYTHONPATH.

For most of this repo's life it was the latter: `pytest` put `src/` on the path
through a `pythonpath` setting, the Makefile exported `PYTHONPATH=src`, and every
test module opened with a `sys.path.insert`. Everything passed, and
`python -c "import hugin"` still raised ModuleNotFoundError. Airflow, dbt and the
Spark image have none of those three mechanisms, so code that imports cleanly
under pytest could fail on the first container that runs it.

These tests close that gap the only way it can be closed — by importing `hugin`
in a subprocess that has *nothing* helping it: no PYTHONPATH, no inherited
`sys.path` entries, and a working directory outside the repository, so neither
`src/` nor the repo root can be picked up implicitly. If the package is not
genuinely installed into the environment, they fail.

They also guard the fix from being undone: a `sys.path` insertion reappearing in
a test module makes the suite pass for a reason the containers do not share, and
`test_no_test_module_puts_src_on_sys_path` fails when one does.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TESTS_DIR = Path(__file__).resolve().parent

#: Anything that would let an import succeed without the package being installed.
CLEAN_ENV = {k: v for k, v in os.environ.items() if k not in {"PYTHONPATH", "PYTHONSTARTUP"}}


def run_clean(code: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run `code` in a subprocess with no path help of any kind.

    `-I` is isolated mode: it ignores PYTHONPATH and the user site directory, and
    drops the script directory from sys.path. `cwd` is outside the repo so the
    implicit "" entry cannot resolve `hugin` either.
    """
    return subprocess.run(
        [sys.executable, "-I", "-c", code],
        cwd=cwd, env=CLEAN_ENV, capture_output=True, text=True,
    )


def test_hugin_is_importable_without_pythonpath(tmp_path):
    """The failure this whole module exists for: `python -c "import hugin"`."""
    result = run_clean("import hugin; print(hugin.__file__)", cwd=tmp_path)
    assert result.returncode == 0, (
        "`import hugin` failed in a clean subprocess — the package is not installed "
        f"into this environment. Run `uv sync --all-groups`.\n{result.stderr}"
    )
    assert result.stdout.strip().endswith(("hugin\\__init__.py", "hugin/__init__.py"))


def test_hugin_is_installed_as_a_distribution():
    """Importable is not enough; it must come from an install, with metadata.

    A distribution record is what `uv sync` produces and what a container image
    inherits. Its absence means `hugin` is being found by accident.
    """
    try:
        dist = distribution("hugin")
    except PackageNotFoundError:  # pragma: no cover - the failure being guarded
        pytest.fail(
            "no installed distribution named 'hugin'. pyproject.toml needs a "
            "[build-system] and must not set [tool.uv] package = false."
        )
    assert dist.version


@pytest.mark.parametrize(
    "module",
    [
        "hugin.ingestion.inventory",
        "hugin.identity.crosswalk",
        "hugin.ingestion.load_job",
        "hugin.synthetic",
    ],
)
def test_every_entry_point_module_runs_without_pythonpath(module, tmp_path):
    """`python -m hugin.<x>` is how the Makefile and the DAGs invoke this code.

    Each of these is a `python -m` target in the Makefile or an Airflow task, so
    each must resolve from the installed package alone.
    """
    result = subprocess.run(
        [sys.executable, "-I", "-m", module, "--help"],
        cwd=tmp_path, env=CLEAN_ENV, capture_output=True, text=True,
    )
    assert result.returncode == 0, f"python -m {module} --help failed\n{result.stderr}"
    assert "usage:" in result.stdout.lower()


def test_package_data_travels_with_the_package(tmp_path):
    """The JSON files are read at runtime, so they must be part of the install.

    A packaging config that ships only `*.py` breaks these at import time in a
    container while passing every test run from a source checkout.
    """
    code = (
        "from hugin.osdu.validate_osdu import SCHEMA_DIR\n"
        "from hugin.synthetic.calibrate import PROFILES_PATH\n"
        "assert list(SCHEMA_DIR.glob('*.json')), SCHEMA_DIR\n"
        "print(PROFILES_PATH.parent.name)\n"
    )
    result = run_clean(code, cwd=tmp_path)
    assert result.returncode == 0, result.stderr


def test_no_test_module_puts_src_on_sys_path():
    """The path hack must not come back.

    `sys.path.insert(..., "src")` in a test module makes the suite pass through a
    mechanism no container has, which is what hid the packaging bug in the first
    place. Test modules import `hugin` like any other consumer or not at all.
    """
    pattern = re.compile(r"sys\.path\.(insert|append)\([^)]*['\"]src['\"]")
    offenders = [
        p.name for p in sorted(TESTS_DIR.glob("test_*.py"))
        if p.name != Path(__file__).name  # this module quotes the hack to describe it
        if pattern.search(p.read_text(encoding="utf-8"))
    ]
    assert not offenders, (
        f"{offenders} put src/ on sys.path. Import `hugin` directly — `uv sync` "
        "installs it."
    )


def test_pytest_config_does_not_set_pythonpath():
    """Same rule for the config: no `pythonpath` setting in pyproject.toml.

    `[tool.pytest.ini_options] pythonpath = ["src"]` is the collective form of the
    same hack, and it hides the bug for the whole suite at once.
    """
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    section = text.partition("[tool.pytest.ini_options]")[2].partition("\n[")[0]
    assert "pythonpath" not in section, (
        "pyproject.toml sets a pytest pythonpath. Tests must resolve `hugin` "
        "through the installed package, as the Airflow and dbt containers do."
    )
