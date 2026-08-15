"""Generate fixtures.

    python -m hugin.synthetic generate --out ./data/fixtures --seed 42 \
        --scale ci --dirt-level 0

Two scales, and they exist for different reasons (SPEC.md section 10):

    ci    small and deterministic, enough for the whole dbt test suite to run
          without a lakehouse or a large file
    load  telemetry only, amplified, for a streaming throughput test

``--dirt-level`` controls injected defects:

    0  clean, plus the planted BR cases, which are not dirt but the point
    1  the anomaly classes measured in the real data (dropout only, on this
       delivery)
    2  additionally the classes that do NOT occur in the real data - duplicates,
       frozen values, spikes, clock skew. Those rates are marked ``assumed`` in
       profiles.json, and level 2 exists to test handling of defects this field
       has not shown, not to suggest it has.

Determinism is checked, not hoped for: the same seed writes byte-identical files
and MANIFEST.json records the sha256 of each one.

**Nothing produced here is Volve data.** Wellbores are named 15/9-X-*, which
does not exist in the field, and the manifest repeats the warning.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
from pathlib import Path

from hugin.synthetic.calibrate import PROFILES_PATH
from hugin.synthetic.generators import (
    FIXTURE_WELLBORES,
    GeneratorContext,
    write_las,
    write_production_workbook,
    write_telemetry,
    write_trajectory,
    write_well_picks,
)

MANIFEST_NAME = "MANIFEST.json"

#: Identity spellings that BR-12 must fold onto one wellbore. Every one of these
#: shapes occurs in the real delivery for real wells; only the well number is
#: fictional.
IDENTITY_VARIANTS = (
    "15/9-X-3 A",
    "15_9-X-3 A",
    "NO 15/9-X-3 A",
    "Norway-Statoil-15_$47$_9-X-3 A",
)


def load_profiles(path: Path = PROFILES_PATH) -> dict:
    if not path.exists():
        raise SystemExit(
            f"{path} is missing. Run 'python -m hugin.synthetic.calibrate' "
            f"against the real silver tables first: a fixture generated without "
            f"a profile would be shaped by nothing."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def generate(out_dir: Path, seed: int, scale: str, dirt_level: int) -> dict:
    profiles = load_profiles()
    context = GeneratorContext(
        out_dir=out_dir, seed=seed, scale=scale, dirt_level=dirt_level, profiles=profiles
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    files: dict[str, dict] = {}

    if scale == "ci":
        files["prod/Production_data/Volve production data.xlsx"] = write_production_workbook(
            context, out_dir / "prod" / "Production_data" / "Volve production data.xlsx"
        )

        # BR-08: one file per calibrated sentinel spelling, so the suite covers
        # every one the real delivery declares - including -9999.
        spellings = context.parameter("las_sentinel_spellings", {}) or {"-999.25": {}}
        for index, sentinel in enumerate(sorted(spellings)):
            wellbore = FIXTURE_WELLBORES[index % len(FIXTURE_WELLBORES)]
            relative = f"log/{wellbore.replace('/', '_').replace(' ', '_')}/FIXTURE_{index}.LAS"
            files[relative] = write_las(context, out_dir / relative, sentinel, wellbore)

        # BR-12: the same wellbore written four ways.
        for index, variant in enumerate(IDENTITY_VARIANTS):
            relative = f"traj/variant_{index}/trajectory/1.xml"
            files[relative] = write_trajectory(context, out_dir / relative, variant)

        # BR-13.
        files["geom/well_picks.csv"] = write_well_picks(context, out_dir / "geom" / "well_picks.csv")

        # A small telemetry file so CI exercises the parser, not the throughput.
        relative = "witsml/15_9-X-1/1/log/1.xml"
        files[relative] = write_telemetry(context, out_dir / relative, "15/9-X-1", rows=500)

    else:  # load
        # Telemetry only. SPEC.md section 10 scopes load fixtures to volume
        # amplification, and generating production at this scale would produce a
        # large file nothing needs.
        rows_per_well = 200_000
        for wellbore in FIXTURE_WELLBORES:
            slug = wellbore.replace("/", "_").replace(" ", "_")
            relative = f"witsml/{slug}/1/log/1.xml"
            files[relative] = write_telemetry(
                context, out_dir / relative, wellbore, rows=rows_per_well
            )

    manifest = {
        "generated_by": "hugin.synthetic",
        "warning": (
            "FIXTURE DATA. Generated from distributions measured in the Volve "
            "delivery; it is not Volve data and no figure derived from it may be "
            "presented as a measurement of the Volve field (SPEC.md section 10). "
            "Wellbores are named 15/9-X-*, which does not exist in the field."
        ),
        "parameters": {
            "seed": seed,
            "scale": scale,
            "dirt_level": dirt_level,
        },
        "profiles": {
            "path": str(PROFILES_PATH.name),
            "calibrated_at": profiles.get("calibrated_at"),
            "parameter_counts": profiles.get("parameter_counts"),
            "rows_behind_calibration": profiles.get("rows_behind_calibration"),
        },
        "planted_cases": {
            "BR-02": "monthly volumes disagree with summed daily beyond tolerance",
            "BR-03": "an injector reports produced oil",
            "BR-04": "a day with zero on-stream hours and non-zero volume",
            "BR-08": "one LAS per declared sentinel spelling, including -9999",
            "BR-12": f"{len(IDENTITY_VARIANTS)} spellings of one wellbore",
            "BR-13": "a perforation interval crossing two formations",
        },
        "files": {name: files[name] for name in sorted(files)},
        "totals": {
            "files": len(files),
            "bytes": sum(entry["bytes"] for entry in files.values()),
        },
    }
    # The manifest is written last and excludes itself. It carries no timestamp
    # on purpose: a generated-at field would change every run and break the
    # byte-identical guarantee it exists to record.
    manifest_path = out_dir / MANIFEST_NAME
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=False) + "\n", encoding="utf-8", newline="\n"
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m hugin.synthetic")
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate_parser = subparsers.add_parser("generate", help="write a fixture set")
    generate_parser.add_argument("--out", type=Path, default=Path("./data/fixtures"))
    generate_parser.add_argument("--seed", type=int, default=42)
    generate_parser.add_argument("--scale", choices=("ci", "load"), default="ci")
    generate_parser.add_argument("--dirt-level", type=int, choices=(0, 1, 2), default=0)

    args = parser.parse_args(argv)
    if args.command == "generate":
        manifest = generate(args.out, args.seed, args.scale, args.dirt_level)
        print(f"scale={args.scale} seed={args.seed} dirt={args.dirt_level}")
        for name, entry in manifest["files"].items():
            print(f"  {name:56} {entry['bytes']:>9,} B  {entry['sha256'][:12]}")
        print(f"\n{manifest['totals']['files']} files, "
              f"{manifest['totals']['bytes']:,} bytes")
        print(f"manifest: {args.out / MANIFEST_NAME}")
        print("\nFIXTURE DATA - not Volve measurements. See MANIFEST.json.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
