# ADR 010 — Ship `hugin` as an installed package, built by uv's own backend

Status: accepted
Date: 2026-08-14
Scope: `pyproject.toml`, the test suite's import mechanism, `Makefile` / `make.cmd`

## Context

`hugin` lived under `src/` but was never installed. `pyproject.toml` declared
`[tool.uv] package = false`, which tells uv to sync the dependencies and skip the
project itself, so `.venv` contained pandas, lasio and segyio but no `hugin`.

Three separate mechanisms hid this:

* `[tool.pytest.ini_options] pythonpath = ["src"]`, which puts `src/` on
  `sys.path` for every pytest run;
* `export PYTHONPATH = src` in the Makefile, mirrored in `make.cmd`;
* `sys.path.insert(0, str(REPO_ROOT / "src"))` at the top of eleven test modules,
  each followed by imports carrying `# noqa: E402`.

The result was a suite that passed in full while `uv run python -c "import
hugin"` raised `ModuleNotFoundError`. That is not a cosmetic gap. None of the
three mechanisms exists inside a container: the Airflow image sets `PYTHONPATH`
by hand in its Dockerfile, dbt's Python models get whatever the warehouse's
interpreter has, and a Spark executor gets neither. Code that imports cleanly
under pytest could therefore fail on the first task that ran it in Airflow, and
the test suite could not have caught it — the suite was measuring an environment
no deployment reproduces.

The original comment argued that a virtual project "keeps the closed dependency
list genuinely closed". The concern is real (CLAUDE.md forbids adding a
dependency without an ADR) but the cost was wrong: a build backend is a
build-time tool, not something the runtime resolves or the containers install.

## Decision

`hugin` is a real distribution. `pyproject.toml` declares a `[build-system]`, and
`uv sync` installs the project into `.venv` in editable mode alongside its
dependencies, so `import hugin` resolves from the environment.

The backend is **uv's own**, `uv_build`:

```toml
[build-system]
requires = ["uv_build>=0.12.4,<0.13.0"]
build-backend = "uv_build"

[tool.uv.build-backend]
module-root = "src"
module-name = "hugin"
```

Together with the decision:

* `pythonpath` is removed from `[tool.pytest.ini_options]`;
* `PYTHONPATH=src` is removed from `Makefile` and `make.cmd`;
* every `sys.path.insert(..., "src")` is removed from `tests/`, along with the
  `# noqa: E402` markers those lines forced;
* `tests/test_packaging.py` asserts the property directly — it imports `hugin` in
  a subprocess run with `python -I` from a working directory outside the
  repository, so no `PYTHONPATH`, no user site directory and no implicit `""`
  entry can help it, and it fails if the package is not installed. It also fails
  if the `pythonpath` setting or a `sys.path` hack reappears.

Install stays editable, which matters here beyond convenience:
`inventory.py`, `crosswalk.py` and `common/config.py` derive `REPO_ROOT` from
`Path(__file__).resolve().parents[3]`. Under an editable install `__file__` still
points into `src/`, so that arithmetic holds. Under a copied wheel install it
would not, and those modules would need reworking to locate the repository some
other way. That is a real constraint on any future non-editable deployment and is
recorded here rather than discovered later.

## Alternatives considered

**Keep `package = false` and add a `conftest.py` that inserts `src/`.** This
would have consolidated eleven copies of the hack into one file, which is tidier,
and it adds nothing at all to the dependency list. It loses because it does not
address the actual defect: `conftest.py` is a pytest artefact, so the suite would
still pass through a mechanism Airflow, dbt and Spark do not have, and
`python -c "import hugin"` would still fail. It makes the illusion cheaper to
maintain instead of removing it.

**hatchling.** The default backend for most modern Python projects, better
documented, and what a reviewer is most likely to have seen. It handles src
layout and package data with no configuration. It loses on exactly one point,
and only in this repo: it is a third-party package that `uv sync` must download
and install, which is the thing CLAUDE.md's closed-list rule is written to
control. `uv_build` ships inside the `uv` binary this project already mandates
for dependency management, so choosing it adds a backend without adding a
package. If uv is ever dropped, hatchling is the replacement and the swap is
four lines.

**setuptools with `[tool.setuptools.packages.find]`.** Universally available and
needs no ADR-worthy justification at all. It loses on configuration surface: src
layout, package data and editable installs each need explicit settings, and its
editable-install mode is the one most likely to surprise. There is no benefit
here to offset that.

## Consequences

`uv sync` now runs a build step for the project. It is fast — under a second —
but it is a step that could fail, and it will fail if `src/hugin/` is renamed
without updating `module-name`.

The `uv_build` version range is pinned to uv's own release series
(`>=0.12.4,<0.13.0`). When uv moves to 0.13, that constraint must be widened or
`uv sync` stops resolving. This is the price of using a backend versioned in
lockstep with the tool; hatchling would not have it. `make setup` failing with a
resolution error on `uv_build` is the symptom, and the fix is one line.

Non-Python files inside `src/hugin/` — `osdu/schemas/*.json` and
`synthetic/profiles.json` — are included by the backend without configuration,
because uv_build ships the whole module directory rather than only `*.py`.
`test_package_data_travels_with_the_package` asserts this rather than trusting
it, since a backend swap could silently change the rule.

What is gained: `python -m hugin.<anything>` works from any directory with the
venv active, the Makefile is one env var simpler, eleven test modules lost their
preamble, and — the point of the exercise — a container that imports `hugin`
without a `PYTHONPATH` shim is now something the test suite can prove works
before the container is built.

## What this does not yet change

`docker/airflow/Dockerfile` still sets `ENV PYTHONPATH=/opt/hugin/src`, and the
three DAG files still carry a defensive `sys.path.insert`. Both are now redundant
in principle and neither is removed here, because the compose stack is not
running in this change and an unverified edit to the image is worse than a
redundant line. The follow-up is to `pip install -e /opt/hugin` in the image and
delete both — see the "When this should be revisited" note.

## When this should be revisited

Two conditions:

1. **uv reaches 0.13.** Widen the `uv_build` pin, or move to hatchling if the
   lockstep versioning becomes a recurring cost.
2. **Anything needs a non-editable install of `hugin`** — publishing a wheel,
   or `pip install` from a copied source tree in the Airflow image. At that point
   the `parents[3]` REPO_ROOT arithmetic in `ingestion/inventory.py`,
   `identity/crosswalk.py` and `common/config.py` breaks and must be replaced
   with an explicit setting before the install mode changes.
