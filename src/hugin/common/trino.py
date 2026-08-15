"""A small Trino client over its REST protocol.

Trino has an official Python driver. It is not in ``pyproject.toml``, and
CLAUDE.md makes adding one an ADR-sized decision, so this talks to the protocol
directly with ``httpx``, which is already a declared dependency.

The protocol is genuinely simple: POST the SQL to ``/v1/statement``, then follow
``nextUri`` until it stops appearing, collecting ``data`` as you go. State
arrives as ``QUEUED``, ``RUNNING``, ``FINISHED`` or ``FAILED``; an error is a
JSON object under ``error`` rather than an HTTP status, so a failed query
returns 200 and must be checked for.

This is enough for DDL, procedure calls and counting rows. It is not a driver:
no prepared statements, no parameter binding, no transactions.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import httpx

__all__ = ["TrinoClient", "TrinoQueryError"]


class TrinoQueryError(RuntimeError):
    """A query Trino rejected or failed to execute."""

    def __init__(self, sql: str, error: dict[str, Any]) -> None:
        self.sql = sql
        self.error = error
        message = error.get("message", "unknown error")
        name = error.get("errorName", "")
        super().__init__(f"{name}: {message}\n  in: {sql.strip()[:400]}")


@dataclass
class TrinoClient:
    host: str = "localhost"
    port: int = 8080
    user: str = "hugin"
    catalog: str = "iceberg"
    schema: str = "bronze"
    timeout: float = 600.0

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def _headers(self) -> dict[str, str]:
        return {
            "X-Trino-User": self.user,
            "X-Trino-Catalog": self.catalog,
            "X-Trino-Schema": self.schema,
            "X-Trino-Source": "hugin",
            "Content-Type": "text/plain",
        }

    def execute(self, sql: str) -> list[list[Any]]:
        """Run one statement and return its rows."""
        return list(self.stream(sql))

    def stream(self, sql: str) -> Iterator[list[Any]]:
        """Run one statement, yielding rows as pages arrive."""
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.base_url}/v1/statement", content=sql.encode("utf-8"),
                headers=self._headers(),
            )
            response.raise_for_status()
            payload = response.json()

            while True:
                if "error" in payload:
                    raise TrinoQueryError(sql, payload["error"])
                for row in payload.get("data") or []:
                    yield row

                next_uri = payload.get("nextUri")
                if not next_uri:
                    return
                # Trino asks clients not to hammer nextUri while a query is
                # still queued; a short sleep costs nothing and keeps the
                # coordinator's scheduler quiet.
                if payload.get("stats", {}).get("state") in ("QUEUED", "PLANNING"):
                    time.sleep(0.05)
                payload = client.get(next_uri, headers=self._headers()).json()

    def query_dicts(self, sql: str) -> Iterator[dict[str, Any]]:
        """Run one statement, yielding rows keyed by column name.

        ``stream`` drops the column list, which is fine for counting and for
        DDL and useless for anything that maps a row onto named fields -
        hugin.osdu.mapping takes gold rows by name, because a mapping that
        depended on select order would break the first time a column moved.

        Trino sends ``columns`` with the first page that has any, so the names
        are captured on the way past rather than by a second round trip.
        """
        names: list[str] = []
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.base_url}/v1/statement", content=sql.encode("utf-8"),
                headers=self._headers(),
            )
            response.raise_for_status()
            payload = response.json()

            while True:
                if "error" in payload:
                    raise TrinoQueryError(sql, payload["error"])
                if not names and payload.get("columns"):
                    names = [column["name"] for column in payload["columns"]]
                for row in payload.get("data") or []:
                    yield dict(zip(names, row, strict=False))

                next_uri = payload.get("nextUri")
                if not next_uri:
                    return
                if payload.get("stats", {}).get("state") in ("QUEUED", "PLANNING"):
                    time.sleep(0.05)
                payload = client.get(next_uri, headers=self._headers()).json()

    def scalar(self, sql: str) -> Any:
        rows = self.execute(sql)
        return rows[0][0] if rows and rows[0] else None

    def wait_until_ready(self, attempts: int = 60, delay: float = 2.0) -> bool:
        """Poll ``/v1/info`` until the coordinator will accept queries.

        The port opens well before the server is ready, and a query sent in
        between fails with SERVER_STARTING_UP — which looks like a
        configuration problem and is not one.
        """
        for _attempt in range(attempts):
            try:
                with httpx.Client(timeout=5.0) as client:
                    info = client.get(f"{self.base_url}/v1/info").json()
                if not info.get("starting", True):
                    return True
            except (httpx.HTTPError, ValueError):
                pass
            time.sleep(delay)
        return False
