PYTHON      ?= python
ARCHIVE_DIR ?= C:/Apply Kerja/DE/volve

# No PYTHONPATH here: `make setup` installs hugin into .venv, so `python -m
# hugin.x` resolves the same way it does in the Airflow and dbt containers. If a
# target raises ModuleNotFoundError, the venv is not active or not synced.

# Targets marked TODO print the phase that fills them and exit non-zero, so a
# script never mistakes "not written yet" for "done". Keep make.cmd in step.
.PHONY: help setup inventory extract report identity gen-data seed up down test \
        lint dbt-build dialect-check replay-reset all clean-landing

help:
	@echo "setup        - uv sync: create .venv from pyproject.toml"
	@echo "inventory    - scan archives, detect duplicates, classify (no extraction)"
	@echo "extract      - extract to data/landing/, then regenerate docs/"
	@echo "report       - regenerate docs/ from existing artefacts"
	@echo "identity     - BR-12: build silver.wellbore_identity from data/landing/"
	@echo "gen-data     - calibrate against silver, then generate CI fixtures"
	@echo "seed         - load data/landing/ into the bronze Iceberg tables"
	@echo "counts       - row counts per bronze table, and identity coverage"
	@echo "up           - docker compose --profile core up -d"
	@echo "down         - docker compose --profile core down"
	@echo "test         - pytest"
	@echo "lint         - ruff check + ruff format --check"
	@echo "dbt-build    - dbt build on both targets: trino then duckdb"
	@echo "dialect-check- compare the dialect macros across duckdb and spark (ADR 007)"
	@echo "benchmark    - measure against the SPEC section 13 targets"
	@echo "replay-reset - TODO: reset replay state and drop replayed partitions"
	@echo ""
	@echo "The archive folder is READ-ONLY. No target writes to it."

setup:
	uv sync --all-groups

inventory:
	$(PYTHON) -m hugin.ingestion.inventory --archive-dir "$(ARCHIVE_DIR)" scan --quarantine-duplicates

extract:
	$(PYTHON) -m hugin.ingestion.inventory --archive-dir "$(ARCHIVE_DIR)" extract
	$(PYTHON) -m hugin.ingestion.inventory --archive-dir "$(ARCHIVE_DIR)" report

report:
	$(PYTHON) -m hugin.ingestion.inventory --archive-dir "$(ARCHIVE_DIR)" report

identity:
	$(PYTHON) -m hugin.identity.crosswalk build

# Calibrate against the real silver tables, then generate the CI fixture set.
# The load set is telemetry only and is generated on demand, not by default.
gen-data:
	$(PYTHON) -m hugin.synthetic.calibrate
	$(PYTHON) -m hugin.synthetic generate --out ./data/fixtures --seed 42 --scale ci

seed:
	$(PYTHON) -m hugin.ingestion.load_job --demo

counts:
	$(PYTHON) -m hugin.ingestion.load_job --counts

up:
	docker compose --profile core up -d

down:
	docker compose --profile core down

test:
	$(PYTHON) -m pytest tests/ -q

# sqlfluff joins this target once transform/ holds dbt models.
lint:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .

# Both runnable targets, because a model that builds on one is not portable.
# The third target, databricks, has no workspace to build against - ADR 007.
# dialect-check is what stands in for it.
dbt-build:
	cd transform && DBT_PROFILES_DIR=. dbt build --target trino
	cd transform && DBT_PROFILES_DIR=. dbt build --target duckdb

# Compares every dialect macro's databricks rendering against its duckdb one,
# on the Spark 3.5 container. Needs: docker compose --profile stream up -d spark
dialect-check:
	$(PYTHON) scripts/dialect_check.py --json docs/dialect-check.json

benchmark:
	$(PYTHON) scripts/benchmark.py all

replay-reset:
	@echo "TODO (week 4): clear Airflow DAG runs and drop replayed _replay_date partitions."
	@exit 1

all: inventory extract

# Removes only our own output tree, never the archive folder.
clean-landing:
	rm -rf data/landing
