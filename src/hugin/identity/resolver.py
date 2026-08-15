"""Lookup from a written identity to a canonical wellbore, for the readers.

The crosswalk in :mod:`hugin.identity.crosswalk` is the slow, thorough pass over
the whole delivery. This is the fast path ingestion uses per row: a dictionary
built from the crosswalk's output, plus the normaliser as a fallback for a name
the crosswalk never saw.

Returning ``None`` is a normal outcome, not an error. An identity nothing can
resolve is ingested with a NULL ``_wellbore_uid`` and counted; BR-12 forbids
both dropping it and guessing it.
"""

from __future__ import annotations

import csv
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from hugin.identity.crosswalk import IDENTITY_PATH, read_name

__all__ = ["IdentityResolver", "get_resolver"]


@dataclass
class IdentityResolver:
    """(source_system, source_identifier) -> wellbore_uid.

    Three chances, in order of authority:

    1. the crosswalk, keyed by source system and identifier as written,
    2. the crosswalk, keyed by identifier alone — the same string written by a
       system the crosswalk did not attribute it to still names the same hole,
    3. the normaliser, for a name that appeared after the crosswalk was built.

    Misses are counted so a reader can report how much of what it ingested
    resolved, rather than leaving that to be discovered downstream.
    """

    by_system: Mapping[tuple[str, str], str] = field(default_factory=dict)
    by_identifier: Mapping[str, str] = field(default_factory=dict)
    hits: int = 0
    misses: int = 0
    _unresolved: set[tuple[str, str]] = field(default_factory=set)

    @classmethod
    def from_crosswalk(cls, path: Path | None = None) -> IdentityResolver:
        path = path or IDENTITY_PATH
        by_system: dict[tuple[str, str], str] = {}
        by_identifier: dict[str, str] = {}
        ambiguous: set[str] = set()

        if path.exists():
            with open(path, newline="", encoding="utf-8") as handle:
                for row in csv.DictReader(handle):
                    uid = row["wellbore_uid"]
                    by_system[(row["source_system"], row["source_identifier"])] = uid
                    known = by_identifier.get(row["source_identifier"])
                    if known is not None and known != uid:
                        # The same string meaning two wellbores across systems
                        # would make the system-blind lookup a coin flip.
                        ambiguous.add(row["source_identifier"])
                    by_identifier[row["source_identifier"]] = uid

        for identifier in ambiguous:
            by_identifier.pop(identifier, None)

        return cls(by_system=by_system, by_identifier=by_identifier)

    def resolve(self, source_system: str, identifier: str | None) -> str | None:
        if not identifier:
            return None

        uid = self.by_system.get((source_system, identifier))
        if uid is None:
            uid = self.by_identifier.get(identifier)
        if uid is None:
            reading = read_name(identifier)
            uid = reading.wellbore_name

        if uid is None:
            self.misses += 1
            self._unresolved.add((source_system, identifier))
        else:
            self.hits += 1
        return uid

    @property
    def unresolved(self) -> list[tuple[str, str]]:
        """Every identity this resolver could not place, for reporting."""
        return sorted(self._unresolved)

    @property
    def coverage(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total else 0.0


@lru_cache(maxsize=1)
def get_resolver() -> IdentityResolver:
    """The process-wide resolver, built once from the crosswalk on disk."""
    return IdentityResolver.from_crosswalk()
