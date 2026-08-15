# Trajectory validation (BR-09)

Minimum curvature, implemented from the formula in `SPEC.md` section 5 and
validated two ways: against the surveying contractor's own computed positions,
and against an independent VSP checkshot.

Measured 2026-08-13 from `src/hugin/geo/minimum_curvature.py` over the
trajectory documents in `data/landing/traj/`.

## 1. Against the contractor's own numbers

Every trajectory document carries the contractor's computed TVD alongside the
raw MD, inclination and azimuth. Recomputing from the raw angles and comparing
is the strongest check available: it puts this implementation against software
that was used to steer a well.

| Survey | Wellbore | Stations | Max TVD error | As % of TD |
|---|---|---:|---:|---:|
| `T-957090-1` | 15/9-F-10 | 469 | **3 mm** | 0.0001% |
| `T-878157-1` | 15/9-F-15A (8.5in) | 80 | **0.7 mm** | 0.00002% |
| `T-680923-1` | 15/9-F-14 | 6 | **0.0 mm** | 0.0000% |
| all others | — | — | < 0.5 m | < 0.1% |

**SPEC.md's threshold is 0.1%. The worst case across every document is three
orders of magnitude inside it.** `TVD <= MD` holds at every station of every
survey, and the maximum dogleg severity on F-15A is 4.89 °/30m, which is a
normal build rate rather than a computational artefact.

Two numerical details are what make this work on real data rather than on a
textbook example, and both are in the module with the reasoning:

- the `arccos` argument is clamped, because a straight interval evaluates to
  `1 + 1e-16` in floating point and `acos` raises on it — every survey with a
  tangent section hits this on the first station;
- the ratio factor is evaluated by series below a dogleg of 1e-4 rad, where
  `(2/DL)·tan(DL/2)` divides two vanishing quantities and returns noise.

## 2. Two things the data does that a naive reading gets wrong

Both were found by this validation failing, not by reading the files.

### Four surveys report angles in radians

`uom` is declared per element, and the delivery is not consistent:

| Unit | Surveys |
|---|---|
| `dega` | 28 |
| `rad` | 4 — `12RGUI47`, `2VG4D36`, `6VFNI35`, `1RJGJ56`(partly) |

The radian surveys read *plausibly* as degrees, which is what makes this
dangerous. `12RGUI47` reports an inclination of `0.371` at 3199 m MD. As
0.371 degrees that is a nearly vertical hole and nothing looks wrong. It is
0.371 **radians** — 21.3° — and reading it as degrees puts the computed TVD
**188 m** above the contractor's.

`Station.from_uom()` now converts from the declared unit and **raises** on a
missing or unrecognised one. Defaulting to degrees would have hidden this.

### F-15A has two surveys, both starting at surface

`T-878157-1` (8.5in section, 80 stations, to 3212 m) and `T-861406-1` (12.25in
section, 69 stations, to 2892 m) are both "Actual Traj" and both begin at MD 0.
They are not sequential sections of one path — they are two independent surveys
of the same hole. Merging them by depth interleaves two survey runs and
produces a trajectory neither contractor computed. Each document is treated
separately.

## 3. Against the VSP checkshot — the independent check

A checkshot measures travel time to a receiver at a known depth. It knows
nothing about the directional survey, which is exactly why SPEC.md asks for the
comparison.

**Only one wellbore in this delivery has both**: 15/9-F-15A, whose checkshot
carries measured depth. The other three checkshot files report TVD without MD
and cannot be looked up against a survey at all.

> That file was initially lost. Three of the four checkshots use a single
> column header; the fourth opens with a metadata block and three columns
> (`Measured Depth`, `Vertical Depth`, `Two-way Time`). The reader assumed five
> whitespace-separated fields and dropped every row of the second layout
> silently. It was the only file with MD — the one this validation needs. Both
> layouts are now detected; 191 rows were recovered.

Comparing survey TVD (interpolated to the checkshot's MD) against checkshot TVD,
142 comparable points between 1067 m and 3212 m MD:

| Statistic | Value |
|---|---|
| Mean difference | **+32.45 m** (survey deeper) |
| Standard deviation | 54.19 m |
| Range | +2.13 m to +219.83 m |
| Worst as % of MD | 6.87% |

| MD (m) | Checkshot TVD | Survey TVD | Difference |
|---:|---:|---:|---:|
| 1067.3 | 1052.0 | 1054.3 | +2.32 |
| 1324.5 | 1295.2 | 1300.0 | +4.78 |
| 1581.6 | 1532.0 | 1535.9 | +3.87 |
| 1838.2 | 1764.2 | 1770.8 | +6.58 |
| 2095.3 | 1992.9 | 1998.8 | +5.85 |
| 2352.5 | 2226.4 | 2232.3 | +5.85 |
| 2609.6 | 2441.7 | 2456.6 | +14.87 |
| 2866.2 | 2613.4 | 2695.8 | **+82.44** |

**This is reported as measured. The two do not agree, and the disagreement has
structure**: a small, roughly constant offset to about 2400 m, then a sharp
divergence.

### What the two parts probably are

Stated as candidates with what would settle each, not as conclusions. The
implementation is validated to sub-millimetre against the contractor, so the
disagreement is between the *survey* and the *checkshot*, not in the arithmetic.

**The shallow offset (+2 to +7 m) is almost certainly a depth reference.** The
checkshot header declares `Depth datum: MSL`. A directional survey is normally
referenced to the rig floor (RKB), which sits tens of metres above MSL — Volve's
`wellheadElevation` is 54.9 m in the WITSML well documents. A pure RKB/MSL
offset would be larger and constant; +2 to +7 m growing slowly is more
consistent with a smaller reference difference plus accumulating survey
tolerance. *Settled by*: the survey's own datum declaration, which these
documents do not carry.

**The deep divergence is not explained by a datum.** A reference offset does not
grow from 6 m to 82 m over 250 m of hole. Candidates:

1. **The checkshot is from a different hole.** It extends to 3940 m MD while the
   survey ends at 3212 m. If the VSP was run in a deeper sidetrack or the pilot
   hole, the deep points describe a path this survey never took. This is the
   most likely explanation and would also explain why the divergence begins
   where it does.
2. **The checkshot's depths are along a different reference path.** A VSP
   records depth along the wireline, and in a deviated well wireline depth and
   driller's MD diverge with hole angle. F-15A builds to significant
   inclination in exactly the section where the divergence starts.
3. **Interpolation between survey stations.** The survey has 80 stations over
   3212 m; between two stations the trajectory is interpolated linearly here,
   while the real path is an arc. This contributes metres, not tens of metres,
   so it is a contributor and not the cause.

*Settled by*: the VSP acquisition report naming the wellbore and depth
reference it was run in. `docs/source-readme/Volve_Seismic_VSP__README.txt` is
the place that would say, and this validation has not yet mined it.

**No threshold was adjusted to improve any number on this page.**

## 4. What is not validated

- **The other three checkshots** (15/9-19 A, BT2, SR) report TVD without MD, so
  they cannot be indexed against a survey. They are ingested and available.
- **Northing and easting** are validated only against the contractor's own
  values, not independently — there is no external position measurement in this
  delivery.
- **The absolute position of any well**, because that needs BR-10 and the
  trajectories declare no CRS. See `silver_trajectory_station.source_crs`, which
  is NULL for exactly that reason.
