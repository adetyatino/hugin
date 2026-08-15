"""BR-12 stages a-e: turning a written well name into a canonical identity.

One physical wellbore appears across the Volve deliveries under many names. The
same hole is written ``15_9-F-12``, ``Norway-Statoil-15_$47$_9-F-12``,
``NO 15/9-F-12``, ``15_9_F-12`` and ``P-F-12`` depending on which system wrote
it down. This module turns any of those into the canonical form ``15/9-F-12``,
in the order BR-12 lays down:

    a  unescape_slash            $47$ -> /
    b  strip_prefixes            Norway-, NO, NA-, Statoil, StatoilHydro
    c  canonical_separators      -> 15/9-F-nn
    d  split_sidetrack           sidetrack suffix into its own field
    e  classify_identifier       W-number, wellbore B-number, UUID, NPD number

Every stage is a pure function that can be tested on its own, and
:func:`normalize` records what each one did in a trace. That matters more than
it sounds: when a mapping is questioned — and in this dataset one of them
*should* be questioned — the answer has to be "stage c rewrote the separators,
stage d took ``B`` off as a sidetrack", not "the regex matched".

There is deliberately no fuzzy matching here. See ADR 003.

What this module will *not* do:

*   Guess. A name that does not carry a block and quadrant number produces a
    result with ``failure`` set and no ``well_code``. The caller decides what to
    do with that; it never gets a silent default.
*   Treat a suffix it does not recognise as a sidetrack. ``15/9-F-4 AH`` parses
    to sidetrack ``AH`` here, and the production system that wrote that name
    also wrote NPD code 5693 next to it, which says the wellbore is plain
    ``15/9-F-4``. Stage e exists so an official identifier can overrule a
    parsed name, and :mod:`hugin.identity.crosswalk` lets it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

__all__ = [
    "FIELD_BLOCK_QUADRANT",
    "Identifier",
    "NormalizedName",
    "Stage",
    "apply_field_prefix",
    "canonical_separators",
    "classify_identifier",
    "normalize",
    "split_sidetrack",
    "split_simulator_role",
    "strip_prefixes",
    "unescape_slash",
]

#: ``$47$`` is how the source systems encode ``/`` (ASCII 47) inside a name that
#: has to survive as a folder name. It appears in archive names and inside
#: WITSML entry paths alike.
SLASH_ESCAPE = "$47$"

#: Origin-system prefixes, longest first. ``NA`` is the placeholder the export
#: writes when no operator label applies.
SYSTEM_PREFIXES = ("Norway", "NO", "NA")

#: Operator labels, longest first — ``StatoilHydro`` must be tried before
#: ``Statoil`` or it would leave ``Hydro`` behind. The label changed with
#: corporate history (Statoil -> StatoilHydro -> Statoil -> Equinor) and is
#: recorded rather than discarded: ``dim_wellbore`` is SCD2 over exactly this.
OPERATOR_LABELS = ("StatoilHydro", "Statoil", "Equinor")

#: Separators that appear between the parts of a written well name.
_SEP = r"[\s_/\-]"

#: Leading block and quadrant, e.g. the ``15`` and ``9`` of ``15/9-F-12``.
_BLOCK_QUADRANT = re.compile(rf"^(\d{{1,3}}){_SEP}+(\d{{1,2}})(?!\d)")

#: Optional series letters then the well number, e.g. ``F-12`` or bare ``19``.
_SERIES_NUMBER = re.compile(rf"^(?:([A-Za-z]{{1,2}}){_SEP}*)?(\d{{1,3}})(?!\d)(.*)$")

#: A suffix this dataset actually uses for a sidetrack: a letter (``A``..``S``),
#: a technical sidetrack (``T2``), or both (``BT2``). Anything else is reported
#: rather than assumed to be a sidetrack.
_SIDETRACK = re.compile(r"^(?:([A-Z]{1,2})|([A-Z]?)(T[0-9]))$")

#: Official identifier shapes. The W/B numbers come from the Statoil well master,
#: the UUIDs from the newer system, the bare number from the NPD register.
_W_NUMBER = re.compile(r"^W-\d{4,10}$")
_B_NUMBER = re.compile(r"^B-\d{4,10}$")
_UUID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I
)
_NPD_NUMBER = re.compile(r"^\d{3,6}$")

#: The Volve field sits in block 15/9. Used only where a source omits the block
#: entirely and the caller opts in — see :func:`apply_field_prefix`.
FIELD_BLOCK_QUADRANT = "15/9"

IdentifierKind = Literal["W_NUMBER", "B_NUMBER", "UUID", "NPD_NUMBER"]


@dataclass(frozen=True)
class Stage:
    """What one normalisation stage did, for the trace."""

    name: str
    before: str
    after: str
    note: str = ""

    @property
    def changed(self) -> bool:
        return self.before != self.after


@dataclass(frozen=True)
class Identifier:
    kind: IdentifierKind
    value: str


@dataclass(frozen=True)
class NormalizedName:
    """The result of running stages a-d over one written name."""

    raw: str
    unescaped: str
    without_prefixes: str
    canonical: str | None
    well_code: str | None
    sidetrack_code: str | None
    system_prefixes: tuple[str, ...] = ()
    operator_label: str | None = None
    failure: str | None = None
    trace: tuple[Stage, ...] = field(default_factory=tuple)

    @property
    def resolved(self) -> bool:
        return self.well_code is not None

    @property
    def wellbore_name(self) -> str | None:
        """Canonical wellbore name: well code plus sidetrack, e.g. ``15/9-F-15 C``."""
        if self.well_code is None:
            return None
        return f"{self.well_code} {self.sidetrack_code}" if self.sidetrack_code else self.well_code

    @property
    def decided_by(self) -> str:
        """The last stage that changed the string. Answers "why this mapping?"."""
        changed = [s.name for s in self.trace if s.changed]
        return changed[-1] if changed else "none (already canonical)"


# -- stage a ---------------------------------------------------------------


def unescape_slash(text: str) -> str:
    """Stage a. Restore ``$47$`` to the ``/`` it stands for.

    ``15_$47$_9-F-12`` becomes ``15_/_9-F-12``. The surrounding underscores are
    left for stage c: this stage does one thing, so a failure here cannot be
    confused with a separator problem.
    """
    return text.replace(SLASH_ESCAPE, "/")


# -- stage b ---------------------------------------------------------------


def strip_prefixes(text: str) -> tuple[str, tuple[str, ...], str | None]:
    """Stage b. Remove origin-system prefixes and operator labels.

    Returns ``(remainder, system_prefixes_found, operator_label_found)``.

    Applied repeatedly, because they stack: ``Norway-Statoil-NO 15/9-F-12``
    carries an origin, an operator, and a country code before the name proper.
    The labels are returned, not thrown away — ``operator_label`` is a column of
    ``silver.wellbore_identity`` and the input to the SCD2 in ``dim_wellbore``.
    """
    remainder = text.strip()
    systems: list[str] = []
    operator: str | None = None

    changed = True
    while changed:
        changed = False
        for label in OPERATOR_LABELS:
            m = re.match(rf"^{re.escape(label)}(?:{_SEP}+|$)", remainder, re.I)
            if m:
                # Keep the canonical spelling, not the source's casing.
                operator = label
                remainder = remainder[m.end():].strip()
                changed = True
                break
        if changed:
            continue
        for prefix in SYSTEM_PREFIXES:
            m = re.match(rf"^{re.escape(prefix)}(?:{_SEP}+)", remainder, re.I)
            if m:
                systems.append(prefix)
                remainder = remainder[m.end():].strip()
                changed = True
                break

    return remainder, tuple(systems), operator


# -- stage c ---------------------------------------------------------------


def canonical_separators(text: str) -> tuple[str | None, str | None]:
    """Stage c. Rewrite separators into the canonical ``15/9-F-nn`` shape.

    Returns ``(canonical, failure_reason)``; exactly one is ever set.

    The written forms this has to absorb are all real:
    ``15_9-F-11``, ``15_/_9-F-12``, ``15_9_F_14``, ``15/9-F15``, ``15/9-F-15B``,
    ``15_9-19 SR``. The output keeps any suffix, separated by a single space,
    so that stage d has one place to look.
    """
    collapsed = re.sub(r"\s+", " ", text.strip())
    if not collapsed:
        return None, "empty"

    head = _BLOCK_QUADRANT.match(collapsed)
    if not head:
        return None, "no_block_and_quadrant"
    block, quadrant = head.group(1), head.group(2)

    rest = collapsed[head.end():].lstrip("".join(" _/-"))
    body = _SERIES_NUMBER.match(rest)
    if not body:
        return None, "no_well_number"
    series, number, tail = body.group(1), body.group(2), body.group(3)

    canonical = f"{block}/{quadrant}-"
    if series:
        canonical += f"{series.upper()}-"
    canonical += number

    suffix = re.sub(r"\s+", " ", re.sub(r"[_\-]+", " ", tail)).strip().upper()
    if suffix:
        canonical += f" {suffix}"
    return canonical, None


# -- stage d ---------------------------------------------------------------


def split_sidetrack(canonical: str) -> tuple[str | None, str | None, str | None]:
    """Stage d. Split a canonical name into ``(well_code, sidetrack, failure)``.

    ``15/9-F-15 C`` is well ``15/9-F-15``, sidetrack ``C``. A well with no
    suffix has ``sidetrack_code`` None, which is not the same as an empty
    string and is why the column is nullable.

    A suffix outside the shapes this field actually uses is a failure, not a
    sidetrack. That is the point of the stage: ``15/9-F-4 AH`` reaching here
    means something wrote a name whose suffix is not a sidetrack code, and the
    caller must resolve it by identifier instead of believing the name.
    """
    if " " not in canonical:
        return canonical, None, None

    well_code, _, suffix = canonical.partition(" ")
    m = _SIDETRACK.match(suffix)
    if not m:
        return None, None, f"unrecognised_suffix:{suffix}"

    letters, letter, technical = m.group(1), m.group(2), m.group(3)
    sidetrack = letters if letters else f"{letter}{technical}"
    return well_code, sidetrack, None


# -- stage e ---------------------------------------------------------------


def classify_identifier(value: str) -> Identifier | None:
    """Stage e. Recognise an official identifier, or return None.

    Four systems issue identifiers in this dataset, and each has a shape that
    cannot be confused with the others:

    ``W-353084``   Statoil well master, well level
    ``B-353084``   Statoil well master, wellbore level
    a UUID         the newer Statoil system, well and wellbore level
    ``5599``       NPD (Sodir) register, the only nationally authoritative one

    The NPD number is the loosest shape — a bare integer — so it is only ever
    read from a field that says it is one (``NPD number`` naming system in DDR,
    ``NPD_WELL_BORE_CODE`` in production), never sniffed out of free text.
    """
    text = value.strip()
    if not text:
        return None
    if _W_NUMBER.match(text):
        return Identifier("W_NUMBER", text.upper())
    if _B_NUMBER.match(text):
        return Identifier("B_NUMBER", text.upper())
    if _UUID.match(text):
        return Identifier("UUID", text.lower())
    if _NPD_NUMBER.match(text):
        return Identifier("NPD_NUMBER", text)
    return None


# -- simulator names (opt-in, and never on their own) ----------------------


def split_simulator_role(name: str) -> tuple[str | None, str]:
    """Split an Eclipse well name's role prefix: ``P-F-14`` -> ``("PRODUCER", "F-14")``.

    The simulator names wells by what they do, not by where they are. This is a
    convention, not an identifier, so the caller gets the pieces and decides;
    :mod:`hugin.identity.crosswalk` only accepts the result when another source
    already knows the wellbore it points at.
    """
    m = re.match(r"^([PI])[\s_-]+(.*)$", name.strip())
    if not m:
        return None, name.strip()
    role = {"P": "PRODUCER", "I": "INJECTOR"}[m.group(1).upper()]
    return role, m.group(2).strip()


def apply_field_prefix(name: str, prefix: str = FIELD_BLOCK_QUADRANT) -> str:
    """Prepend the block and quadrant to a name that omits it.

    ``F-14`` -> ``15/9-F-14``. This is an assumption — that a name with no block
    belongs to the only field in the dataset — and it is deliberately a separate,
    opt-in function so it can never happen by accident inside :func:`normalize`.
    Anything resolved this way is marked lower confidence and must be
    corroborated by a source that named the block itself.
    """
    return f"{prefix}-{name.strip()}"


# -- composition -----------------------------------------------------------


def normalize(raw: str) -> NormalizedName:
    """Run stages a-d over one written name and record what each did."""
    trace: list[Stage] = []

    unescaped = unescape_slash(raw)
    trace.append(Stage("a_unescape_slash", raw, unescaped,
                       "restored $47$ to /" if unescaped != raw else ""))

    without, systems, operator = strip_prefixes(unescaped)
    note = []
    if systems:
        note.append("system prefixes: " + ", ".join(systems))
    if operator:
        note.append(f"operator label: {operator}")
    trace.append(Stage("b_strip_prefixes", unescaped, without, "; ".join(note)))

    canonical, failure = canonical_separators(without)
    trace.append(Stage("c_canonical_separators", without, canonical or "", failure or ""))
    if canonical is None:
        return NormalizedName(
            raw=raw, unescaped=unescaped, without_prefixes=without, canonical=None,
            well_code=None, sidetrack_code=None, system_prefixes=systems,
            operator_label=operator, failure=failure, trace=tuple(trace),
        )

    well_code, sidetrack, failure = split_sidetrack(canonical)
    trace.append(Stage(
        "d_split_sidetrack", canonical,
        canonical if failure else (f"{well_code} + sidetrack {sidetrack}" if sidetrack else well_code or ""),
        failure or (f"sidetrack {sidetrack}" if sidetrack else "no sidetrack suffix"),
    ))

    return NormalizedName(
        raw=raw, unescaped=unescaped, without_prefixes=without, canonical=canonical,
        well_code=well_code, sidetrack_code=sidetrack, system_prefixes=systems,
        operator_label=operator, failure=failure, trace=tuple(trace),
    )
