@echo off
REM Windows shim for the Makefile targets.
REM
REM GNU make is not part of a default Windows or Git-for-Windows install, so the
REM Makefile in this repo cannot be run here as-is. This shim implements the same
REM targets with the same commands, so the documented workflow works either way:
REM
REM   cmd.exe     :  make inventory
REM   PowerShell  :  .\make inventory      (PowerShell does not search the
REM                                         current directory for executables)
REM
REM If GNU make is installed later, the Makefile remains the source of truth and
REM this file can go away. Keep the two in step.

setlocal
if "%PYTHON%"=="" set PYTHON=python
if "%ARCHIVE_DIR%"=="" set ARCHIVE_DIR=C:\Apply Kerja\DE\volve
REM No PYTHONPATH: `make setup` installs hugin into .venv. Keep in step with the
REM Makefile.

if "%1"==""             goto help
if "%1"=="help"         goto help
if "%1"=="setup"        goto setup
if "%1"=="inventory"    goto inventory
if "%1"=="extract"      goto extract
if "%1"=="report"       goto report
if "%1"=="identity"     goto identity
if "%1"=="gen-data"     goto gendata
if "%1"=="seed"         goto seed
if "%1"=="up"           goto up
if "%1"=="down"         goto down
if "%1"=="counts"       goto counts
if "%1"=="test"         goto test
if "%1"=="lint"         goto lint
if "%1"=="dbt-build"    goto dbtbuild
if "%1"=="dialect-check" goto dialectcheck
if "%1"=="benchmark"    goto benchmark
if "%1"=="replay-reset" goto todo_replayreset
if "%1"=="all"          goto all
echo Unknown target "%1". Try: make help
exit /b 2

:help
echo setup        - uv sync: create .venv from pyproject.toml
echo inventory    - scan archives, detect duplicates, classify ^(no extraction^)
echo extract      - extract to data/landing/, then regenerate docs/
echo report       - regenerate docs/ from existing artefacts
echo identity     - BR-12: build silver.wellbore_identity from data/landing/
echo gen-data     - calibrate against silver, then generate CI fixtures
echo seed         - load data/landing/ into the bronze Iceberg tables
echo counts       - row counts per bronze table, and identity coverage
echo up           - docker compose --profile core up -d
echo down         - docker compose --profile core down
echo test         - pytest
echo lint         - ruff check + ruff format --check
echo dbt-build    - dbt build on both targets: trino then duckdb
echo dialect-check- compare the dialect macros across duckdb and spark (ADR 007)
echo benchmark    - measure against the SPEC section 13 targets
echo replay-reset - TODO: reset replay state and drop replayed partitions
echo.
echo The archive folder is READ-ONLY. No target writes to it.
exit /b 0

:setup
uv sync --all-groups
exit /b %ERRORLEVEL%

:inventory
"%PYTHON%" -m hugin.ingestion.inventory --archive-dir "%ARCHIVE_DIR%" scan --quarantine-duplicates
exit /b %ERRORLEVEL%

:extract
"%PYTHON%" -m hugin.ingestion.inventory --archive-dir "%ARCHIVE_DIR%" extract
if errorlevel 1 exit /b %ERRORLEVEL%
"%PYTHON%" -m hugin.ingestion.inventory --archive-dir "%ARCHIVE_DIR%" report
exit /b %ERRORLEVEL%

:report
"%PYTHON%" -m hugin.ingestion.inventory --archive-dir "%ARCHIVE_DIR%" report
exit /b %ERRORLEVEL%

:identity
"%PYTHON%" -m hugin.identity.crosswalk build
exit /b %ERRORLEVEL%

:test
"%PYTHON%" -m pytest tests/ -q
exit /b %ERRORLEVEL%

:lint
"%PYTHON%" -m ruff check .
if errorlevel 1 exit /b %ERRORLEVEL%
"%PYTHON%" -m ruff format --check .
exit /b %ERRORLEVEL%

:gendata
"%PYTHON%" -m hugin.synthetic.calibrate
if errorlevel 1 exit /b %ERRORLEVEL%
"%PYTHON%" -m hugin.synthetic generate --out ./data/fixtures --seed 42 --scale ci
exit /b %ERRORLEVEL%

:seed
"%PYTHON%" -m hugin.ingestion.load_job --demo
exit /b %ERRORLEVEL%

:counts
"%PYTHON%" -m hugin.ingestion.load_job --counts
exit /b %ERRORLEVEL%

:up
docker compose --profile core up -d
exit /b %ERRORLEVEL%

:down
docker compose --profile core down
exit /b %ERRORLEVEL%

:dbtbuild
pushd transform && set DBT_PROFILES_DIR=. && dbt build --target trino && dbt build --target duckdb & popd
exit /b %ERRORLEVEL%

:dialectcheck
REM Needs the Spark container: docker compose --profile stream up -d spark
"%PYTHON%" scripts/dialect_check.py --json docs/dialect-check.json
exit /b %ERRORLEVEL%

:benchmark
"%PYTHON%" scripts/benchmark.py all
exit /b %ERRORLEVEL%

:todo_replayreset
echo TODO ^(week 4^): clear Airflow DAG runs and drop replayed _replay_date partitions.
exit /b 1

:all
call "%~f0" inventory
if errorlevel 1 exit /b %ERRORLEVEL%
call "%~f0" extract
exit /b %ERRORLEVEL%
