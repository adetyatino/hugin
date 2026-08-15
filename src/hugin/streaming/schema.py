"""The Avro contract for drilling telemetry, and the rules it enforces.

A schema on the wire is what makes a message rejectable. Without one, a producer
sending a string where a double belongs discovers it three stages later as a
NULL in a mart, and by then nobody can say which producer sent it or when. With
one, the message is refused at the boundary and lands in a dead-letter topic
carrying the reason.

The schema is deliberately strict about two things and permissive about
everything else:

*   ``wellbore_uid`` and ``ts`` are required. They are the dedup key (BR-07), so
    a message without them cannot be deduplicated and must not be accepted.
*   Every channel is nullable. A surface sensor that drops out sends nothing,
    and a schema forcing a number would make the producer invent one.

``bit_depth_m`` and ``hole_depth_m`` are both required because BR-06's physical
invariant — the bit is never below the hole bottom — cannot be checked if either
is absent, and a rig state classified without depth is a guess.
"""

from __future__ import annotations

import json
from typing import Any

__all__ = [
    "DLQ_SCHEMA",
    "DLQ_TOPIC",
    "TELEMETRY_SCHEMA",
    "TELEMETRY_TOPIC",
    "SchemaViolation",
    "validate_record",
]

TELEMETRY_TOPIC = "hugin.drilling.telemetry"
DLQ_TOPIC = "hugin.drilling.telemetry.dlq"

#: Surface channels, all nullable. The names match the assumed telemetry
#: parameters in synthetic/profiles.json, which is where the load fixture's
#: ranges come from.
CHANNELS = (
    "block_position_m",
    "hook_load_klbf",
    "wob_klbf",
    "rpm",
    "torque_kftlbf",
    "flow_in_lpm",
    "spp_bar",
    "rop_mph",
)

TELEMETRY_SCHEMA: dict[str, Any] = {
    "type": "record",
    "name": "DrillingTelemetry",
    "namespace": "no.hugin.drilling",
    "doc": (
        "One surface telemetry sample. Required fields are the ones BR-06 and "
        "BR-07 cannot work without: the dedup key and both depths."
    ),
    "fields": [
        {"name": "wellbore_uid", "type": "string",
         "doc": "Canonical wellbore from BR-12. Half of the dedup key."},
        {"name": "ts", "type": {"type": "long", "logicalType": "timestamp-millis"},
         "doc": "Sample time, epoch millis. The other half of the dedup key."},
        {"name": "source_identifier", "type": ["null", "string"], "default": None,
         "doc": "The wellbore as the source wrote it, before BR-12 resolved it."},
        {"name": "bit_depth_m", "type": "double",
         "doc": "Depth of the bit. BR-06 invariant: never greater than hole_depth_m."},
        {"name": "hole_depth_m", "type": "double", "doc": "Depth of the hole bottom."},
        *[
            {"name": name, "type": ["null", "double"], "default": None}
            for name in CHANNELS
        ],
        {"name": "producer_seq", "type": ["null", "long"], "default": None,
         "doc": "Producer's monotonic counter, for measuring loss end to end."},
    ],
}

#: The dead-letter record. It keeps the raw bytes, because a message that failed
#: to decode cannot be re-serialised, and the reason, because a DLQ nobody can
#: triage is a bin.
DLQ_SCHEMA: dict[str, Any] = {
    "type": "record",
    "name": "DrillingTelemetryRejected",
    "namespace": "no.hugin.drilling",
    "fields": [
        {"name": "rejected_at", "type": {"type": "long", "logicalType": "timestamp-millis"}},
        {"name": "reason", "type": "string"},
        {"name": "field", "type": ["null", "string"], "default": None},
        {"name": "raw_value", "type": ["null", "string"], "default": None},
        {"name": "payload", "type": "string", "doc": "The message as received, JSON-encoded."},
    ],
}


class SchemaViolation(ValueError):
    """A record that does not satisfy the contract, with the field named."""

    def __init__(self, reason: str, field: str | None = None, raw_value: Any = None) -> None:
        self.reason = reason
        self.field = field
        self.raw_value = raw_value
        super().__init__(f"{reason}" + (f" (field {field}={raw_value!r})" if field else ""))


_REQUIRED_DOUBLES = ("bit_depth_m", "hole_depth_m")


def validate_record(record: dict[str, Any]) -> dict[str, Any]:
    """Check a record against the contract, returning it coerced.

    Raises :class:`SchemaViolation` rather than returning a flag, because every
    caller has to do something different with a bad record and a boolean would
    lose the reason. The producer sends it to the DLQ; a test asserts on it.

    The physical invariant is checked here rather than downstream: a sample
    where the bit is below the bottom of the hole is not a measurement, and
    letting it through would put BR-06 in the position of classifying it.
    """
    if not isinstance(record, dict):
        raise SchemaViolation("record is not an object")

    wellbore = record.get("wellbore_uid")
    if not isinstance(wellbore, str) or not wellbore.strip():
        raise SchemaViolation("wellbore_uid is required", "wellbore_uid", wellbore)

    ts = record.get("ts")
    if not isinstance(ts, int) or isinstance(ts, bool):
        raise SchemaViolation("ts must be epoch millis", "ts", ts)

    coerced: dict[str, Any] = {
        "wellbore_uid": wellbore,
        "ts": ts,
        "source_identifier": record.get("source_identifier"),
        "producer_seq": record.get("producer_seq"),
    }

    for name in _REQUIRED_DOUBLES:
        value = record.get(name)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise SchemaViolation(f"{name} is required and must be numeric", name, value)
        coerced[name] = float(value)

    if coerced["bit_depth_m"] > coerced["hole_depth_m"] + 0.5:
        # BR-06 states this as a property test. Enforcing it at the boundary
        # means the property can never be violated downstream.
        raise SchemaViolation(
            "bit_depth_m exceeds hole_depth_m: the bit cannot be below the hole",
            "bit_depth_m", coerced["bit_depth_m"],
        )

    for name in CHANNELS:
        value = record.get(name)
        if value is None:
            coerced[name] = None
        elif isinstance(value, bool) or not isinstance(value, (int, float)):
            raise SchemaViolation(f"{name} must be numeric or absent", name, value)
        else:
            coerced[name] = float(value)

    return coerced


def schema_json(schema: dict[str, Any]) -> str:
    """Canonical JSON for registration. Sorted keys, so the same schema
    registers as the same version rather than a new one."""
    return json.dumps(schema, sort_keys=True, separators=(",", ":"))
