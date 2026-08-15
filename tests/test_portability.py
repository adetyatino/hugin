"""SPEC.md section 12: the same models on Trino, DuckDB and Databricks SQL.

Two kinds of check live here, and neither needs a warehouse.

The first is an audit: no model may contain, inline, a construct that one of
the three engines lacks. This is the mechanical form of the CLAUDE.md rule that
dialect differences belong in ``adapter.dispatch`` macros. It matters because
the failure it prevents is invisible on the engine you happen to be running —
`strpos` in a model is perfectly correct on Trino and DuckDB and simply does
not exist on Databricks, so nothing local ever complains.

The second renders every macro in ``dialect.sql`` through a dispatch emulation
and executes the DuckDB rendering, which catches a macro that has been edited
into something that no longer parses. The Databricks half of that comparison
needs the Spark container and lives in ``scripts/dialect_check.py``; it is run
by ``make dialect-check`` rather than by pytest, and its results are recorded
in docs/portability-report.md.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = REPO_ROOT / "transform" / "models"
MACRO_DIR = REPO_ROOT / "transform" / "macros"
SCRIPTS = REPO_ROOT / "scripts"


def model_files() -> list[Path]:
    return sorted(MODEL_DIR.rglob("*.sql"))


def strip_comments(sql: str) -> str:
    """Drop -- line comments and {# jinja #} blocks before matching."""
    sql = re.sub(r"\{#.*?#\}", " ", sql, flags=re.DOTALL)
    return re.sub(r"--[^\n]*", " ", sql)


# Each entry is (pattern, what it breaks on, the macro that replaces it). The
# right-hand column is the whole point: a failure message that names the
# replacement is a five-second fix, and one that says "non-portable SQL" is an
# afternoon.
BANNED = [
    (
        r"\bcast\s*\([^()]*\bas\s+varchar\s*\)",
        "Databricks (Spark rejects an unlengthed VARCHAR; its text type is STRING)",
        "hugin_as_text",
    ),
    (
        r"\bstrpos\s*\(",
        "Databricks (no strpos; locate() takes the arguments the other way round)",
        "hugin_strpos",
    ),
    (
        r"\bdate_diff\s*\(",
        "Databricks (no date_diff with a unit; two-argument datediff returns whole DAYS)",
        "hugin_seconds_between",
    ),
    (
        r"\bdatediff\s*\(",
        "Trino and DuckDB (no datediff), and it means days on Databricks",
        "hugin_seconds_between",
    ),
    (
        r"\bunnest\s*\(",
        "Databricks (arrays expand with explode())",
        "hugin_date_spine, or a new dispatched macro",
    ),
    (
        r"\bgenerate_series\s*\(",
        "Trino and Databricks (DuckDB-only)",
        "hugin_date_spine",
    ),
    (
        r"\bto_hex\s*\(|\bto_utf8\s*\(",
        "DuckDB and Databricks (Trino-only, needed because Trino's md5 is binary)",
        "hugin_surrogate_key",
    ),
    (
        r"\bapprox_percentile\s*\(",
        "DuckDB (spelled quantile_cont there)",
        "a new dispatched macro",
    ),
    (
        r"\bformat_datetime\s*\(|\bdate_format\s*\(",
        "at least one of the three; the three spell formatting differently",
        "a new dispatched macro",
    ),
    (
        r"\bregexp_like\s*\(",
        "Databricks (spelled rlike / regexp there)",
        "a new dispatched macro",
    ),
    (
        r"\bilike\b",
        "Databricks (no ILIKE; lower() both sides)",
        "lower() on both sides",
    ),
]


@pytest.mark.parametrize("model", model_files(), ids=lambda p: p.name)
def test_models_contain_no_engine_specific_sql(model: Path) -> None:
    sql = strip_comments(model.read_text(encoding="utf-8"))
    for pattern, breaks_on, replacement in BANNED:
        match = re.search(pattern, sql, flags=re.IGNORECASE)
        assert match is None, (
            f"{model.relative_to(REPO_ROOT)} contains `{match.group(0).strip()}` inline, "
            f"which breaks on {breaks_on}. Use {replacement} from transform/macros/dialect.sql. "
            "SPEC.md section 12 and CLAUDE.md: dialect differences go in a dispatched macro, "
            "never in a model."
        )


def test_no_model_branches_on_the_target() -> None:
    """`if target.type ==` inside a model is the thing dispatch exists to avoid."""
    offenders = [
        model.relative_to(REPO_ROOT)
        for model in model_files()
        if re.search(r"target\s*\.\s*(type|name)\b", model.read_text(encoding="utf-8"))
    ]
    assert not offenders, (
        f"{offenders} branch on the target inside model SQL. A branch there is only ever "
        "compiled on the engine running it, so the other engines' version rots unseen. "
        "CLAUDE.md forbids it; put the difference in transform/macros/dialect.sql."
    )


def dispatched_macro_names() -> list[str]:
    source = (MACRO_DIR / "dialect.sql").read_text(encoding="utf-8")
    return sorted(set(re.findall(r"adapter\.dispatch\(\s*'([a-z0-9_]+)'", source)))


def test_every_dispatch_has_a_default_implementation() -> None:
    """A dispatch with no default fails on any engine lacking a specific one."""
    source = (MACRO_DIR / "dialect.sql").read_text(encoding="utf-8")
    missing = [
        name
        for name in dispatched_macro_names()
        if f"macro default__{name}(" not in source
    ]
    assert not missing, (
        f"{missing} dispatch with no default__ implementation. Any target without its own "
        "implementation would fail to compile, which is the failure this file exists to catch "
        "before a warehouse does."
    )


def test_dispatched_macros_are_covered_by_the_dialect_check() -> None:
    """Every dispatched macro appears in scripts/dialect_check.py's cases.

    Adding a macro without a case is how a portability claim quietly stops
    being tested: the audit above only proves the macro is *used*, not that its
    Databricks rendering computes the same thing.
    """
    checked = (SCRIPTS / "dialect_check.py").read_text(encoding="utf-8")
    uncovered = [name for name in dispatched_macro_names() if f'macro="{name}"' not in checked]
    assert not uncovered, (
        f"{uncovered} are dispatched in dialect.sql but have no case in scripts/dialect_check.py. "
        "Add one, so `make dialect-check` compares that macro's answer across engines."
    )


def test_duckdb_rendering_of_every_macro_executes() -> None:
    """Render each macro through dispatch and run it. Catches an edited macro."""
    sys.path.insert(0, str(SCRIPTS))
    try:
        import dialect_check
    finally:
        sys.path.pop(0)

    queries = {case.name: case.sql("duckdb") for case in dialect_check.CASES}
    results = dialect_check.run_duckdb(queries)
    broken = {name: res["error"] for name, res in results.items() if not res["ok"]}
    assert not broken, f"the duckdb rendering of these macros does not run: {broken}"
