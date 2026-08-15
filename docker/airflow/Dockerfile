# Airflow with this project's ingestion code and dbt available to its tasks.
#
# Built rather than using _PIP_ADDITIONAL_REQUIREMENTS, which reinstalls on
# every container start and turns a scheduler restart into a five-minute wait.
FROM apache/airflow:2.10.5-python3.12

USER root
# segyio and lxml need a compiler toolchain only if no wheel matches; keeping
# the layer small matters more than covering every platform.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

USER airflow
# Pinned to the versions in pyproject.toml. The constraint file is Airflow's,
# so its own dependency tree is not disturbed by ours.
RUN pip install --no-cache-dir \
    pandas pyarrow duckdb pydantic pydantic-settings httpx structlog \
    lasio lxml segyio pyproj selectolax \
    dbt-core dbt-trino dbt-duckdb

ENV PYTHONPATH=/opt/hugin/src
