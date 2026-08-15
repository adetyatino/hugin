# Identity resolution report (BR-12)

Generated 2026-08-13T09:53:57.

Every string any source system used to say *which hole this is* — archive
names, folder names, file names, XML elements, spreadsheet columns, Eclipse
well names. Each appears exactly once below, either resolved to a canonical
`wellbore_uid` or listed as unresolved with the reason. Nothing is dropped and
nothing is guessed.

## 1. Coverage

- **379** distinct identities, over 9 source systems
- **337 resolved** (88.9%) to **37** distinct wellbores
- **42 unresolved** (11.1%), listed in full in section 4

### By match method

| match_method | Identities | Confidence | What it means |
|---|---:|---:|---|
| `EXACT` | 51 | 1.00 | the source already wrote the canonical form |
| `IDENTIFIER` | 81 | 1.00 | an official identifier (NPD / W / UUID) decided it |
| `NORMALIZED` | 205 | 0.70, 0.90, 0.95 | stages a-d rewrote the name into canonical form |

### By source system

| source_system | Resolved | Unresolved | Wellbores reached |
|---|---:|---:|---:|
| `ARCHIVE` | 19 | 5 | 11 |
| `DDR` | 101 | 1 | 26 |
| `DOC` | 8 | 3 | 8 |
| `LOG` | 30 | 2 | 9 |
| `PROD` | 21 | 1 | 7 |
| `SIM` | 12 | 5 | 11 |
| `TRAJ` | 90 | 21 | 36 |
| `UNCLASSIFIED` | 0 | 1 | 0 |
| `VSP` | 1 | 1 | 1 |
| `WITSML` | 55 | 2 | 10 |

## 2. The crosswalk

`silver.wellbore_identity`, grouped by the wellbore each identity resolves to.

### `15/9-19`

well_code `15/9-19`, no sidetrack (original hole) — 1 identities

| source_system | source_identifier | match_method | conf. | seen | evidence |
|---|---|---|---:|---:|---|
| `TRAJ` | `15_9-19` | NORMALIZED | 0.95 | 11 | stages a-d; decided at c_canonical_separators |

### `15/9-19 A`

well_code `15/9-19`, sidetrack_code `A` — 5 identities

| source_system | source_identifier | match_method | conf. | seen | evidence |
|---|---|---|---:|---:|---|
| `DDR` | `15/9-19 A` | EXACT | 1.00 | 220 | already canonical; corroborated by NPD_NUMBER 3145 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-19 A') |
| `DDR` | `15_9_19_A` | NORMALIZED | 0.95 | 330 | stages a-d; decided at d_split_sidetrack |
| `DDR` | `3145` | IDENTIFIER | 1.00 | 110 | NPD_NUMBER 3145 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-19 A') |
| `DDR` | `NO 15/9-19 A` | NORMALIZED | 0.95 | 220 | stages a-d; decided at d_split_sidetrack; corroborated by NPD_NUMBER 3145 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-19 A') |
| `TRAJ` | `15_9-19 A` | NORMALIZED | 0.95 | 2 | stages a-d; decided at d_split_sidetrack |

### `15/9-19 B`

well_code `15/9-19`, sidetrack_code `B` — 5 identities

| source_system | source_identifier | match_method | conf. | seen | evidence |
|---|---|---|---:|---:|---|
| `DDR` | `15/9-19 B` | EXACT | 1.00 | 116 | already canonical; corroborated by NPD_NUMBER 3251 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-19 B') |
| `DDR` | `15_9_19_B` | NORMALIZED | 0.95 | 81 | stages a-d; decided at d_split_sidetrack |
| `DDR` | `3251` | IDENTIFIER | 1.00 | 89 | NPD_NUMBER 3251 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-19 B') |
| `DDR` | `NO 15/9-19 B` | NORMALIZED | 0.95 | 116 | stages a-d; decided at d_split_sidetrack; corroborated by NPD_NUMBER 3251 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-19 B') |
| `TRAJ` | `15_9-19 B` | NORMALIZED | 0.95 | 2 | stages a-d; decided at d_split_sidetrack |

### `15/9-19 BT2`

well_code `15/9-19`, sidetrack_code `BT2` — 4 identities

| source_system | source_identifier | match_method | conf. | seen | evidence |
|---|---|---|---:|---:|---|
| `DDR` | `15/9-19 BT2` | EXACT | 1.00 | 62 | already canonical |
| `DDR` | `15_9_19_BT2` | NORMALIZED | 0.95 | 186 | stages a-d; decided at d_split_sidetrack |
| `DDR` | `NO 15/9-19 BT2` | NORMALIZED | 0.95 | 62 | stages a-d; decided at d_split_sidetrack |
| `TRAJ` | `15_9-19 BT2` | NORMALIZED | 0.95 | 2 | stages a-d; decided at d_split_sidetrack |

### `15/9-19 S`

well_code `15/9-19`, sidetrack_code `S` — 5 identities

| source_system | source_identifier | match_method | conf. | seen | evidence |
|---|---|---|---:|---:|---|
| `DDR` | `15/9-19 S` | EXACT | 1.00 | 225 | already canonical; corroborated by NPD_NUMBER 2043 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-19 S') |
| `DDR` | `15_9_19_S` | NORMALIZED | 0.95 | 147 | stages a-d; decided at d_split_sidetrack |
| `DDR` | `2043` | IDENTIFIER | 1.00 | 176 | NPD_NUMBER 2043 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-19 S') |
| `DDR` | `NO 15/9-19 S` | NORMALIZED | 0.95 | 225 | stages a-d; decided at d_split_sidetrack; corroborated by NPD_NUMBER 2043 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-19 S') |
| `TRAJ` | `15_9-19 S` | NORMALIZED | 0.95 | 2 | stages a-d; decided at d_split_sidetrack |

### `15/9-19 SR`

well_code `15/9-19`, sidetrack_code `SR` — 1 identities

| source_system | source_identifier | match_method | conf. | seen | evidence |
|---|---|---|---:|---:|---|
| `TRAJ` | `15_9-19 SR` | NORMALIZED | 0.95 | 2 | stages a-d; decided at d_split_sidetrack |

### `15/9-19 ST2`

well_code `15/9-19`, sidetrack_code `ST2` — 3 identities

| source_system | source_identifier | match_method | conf. | seen | evidence |
|---|---|---|---:|---:|---|
| `DDR` | `15/9-19 ST2` | EXACT | 1.00 | 127 | already canonical |
| `DDR` | `15_9_19_ST2` | NORMALIZED | 0.95 | 381 | stages a-d; decided at d_split_sidetrack |
| `DDR` | `NO 15/9-19 ST2` | NORMALIZED | 0.95 | 127 | stages a-d; decided at d_split_sidetrack |

### `15/9-F-1`

well_code `15/9-F-1`, no sidetrack (original hole) — 5 identities

| source_system | source_identifier | match_method | conf. | seen | evidence |
|---|---|---|---:|---:|---|
| `DDR` | `15/9-F-1` | EXACT | 1.00 | 76 | already canonical; corroborated by NPD_NUMBER 7223 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-1') |
| `DDR` | `15_9_F_1` | NORMALIZED | 0.95 | 114 | stages a-d; decided at c_canonical_separators |
| `DDR` | `7223` | IDENTIFIER | 1.00 | 38 | NPD_NUMBER 7223 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-1') |
| `DDR` | `NO 15/9-F-1` | NORMALIZED | 0.95 | 76 | stages a-d; decided at b_strip_prefixes; corroborated by NPD_NUMBER 7223 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-1') |
| `TRAJ` | `15_9-F-1` | NORMALIZED | 0.95 | 21 | stages a-d; decided at c_canonical_separators |

### `15/9-F-1 A`

well_code `15/9-F-1`, sidetrack_code `A` — 5 identities

| source_system | source_identifier | match_method | conf. | seen | evidence |
|---|---|---|---:|---:|---|
| `DDR` | `15/9-F-1 A` | EXACT | 1.00 | 14 | already canonical; corroborated by NPD_NUMBER 7224 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-1 A') |
| `DDR` | `15_9_F_1_A` | NORMALIZED | 0.95 | 21 | stages a-d; decided at d_split_sidetrack |
| `DDR` | `7224` | IDENTIFIER | 1.00 | 7 | NPD_NUMBER 7224 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-1 A') |
| `DDR` | `NO 15/9-F-1 A` | NORMALIZED | 0.95 | 14 | stages a-d; decided at d_split_sidetrack; corroborated by NPD_NUMBER 7224 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-1 A') |
| `TRAJ` | `15_9-F-1 A` | NORMALIZED | 0.95 | 4 | stages a-d; decided at d_split_sidetrack |

### `15/9-F-1 B`

well_code `15/9-F-1`, sidetrack_code `B` — 6 identities

| source_system | source_identifier | match_method | conf. | seen | evidence |
|---|---|---|---:|---:|---|
| `DDR` | `15/9-F-1 B` | EXACT | 1.00 | 146 | already canonical; corroborated by NPD_NUMBER 7264 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-1 B') |
| `DDR` | `15_9_F_1_B` | NORMALIZED | 0.95 | 219 | stages a-d; decided at d_split_sidetrack |
| `DDR` | `7264` | IDENTIFIER | 1.00 | 73 | NPD_NUMBER 7264 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-1 B') |
| `DDR` | `NO 15/9-F-1 B` | NORMALIZED | 0.95 | 146 | stages a-d; decided at d_split_sidetrack; corroborated by NPD_NUMBER 7264 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-1 B') |
| `SIM` | `I-F-1B` | NORMALIZED | 0.70 | 2 | simulator injector name; block 15/9 assumed because the name omits it, then corroborated by a source that named its own block |
| `TRAJ` | `15_9-F-1 B` | NORMALIZED | 0.95 | 4 | stages a-d; decided at d_split_sidetrack |

### `15/9-F-1 C`

well_code `15/9-F-1`, sidetrack_code `C` — 9 identities

| source_system | source_identifier | match_method | conf. | seen | evidence |
|---|---|---|---:|---:|---|
| `DDR` | `15/9-F-1 C` | EXACT | 1.00 | 196 | already canonical; corroborated by NPD_NUMBER 7405 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-1 C') |
| `DDR` | `15_9_F_1_C` | NORMALIZED | 0.95 | 294 | stages a-d; decided at d_split_sidetrack |
| `DDR` | `7405` | IDENTIFIER | 1.00 | 98 | NPD_NUMBER 7405 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-1 C') |
| `DDR` | `NO 15/9-F-1 C` | NORMALIZED | 0.95 | 196 | stages a-d; decided at d_split_sidetrack; corroborated by NPD_NUMBER 7405 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-1 C') |
| `PROD` | `15/9-F-1 C` | EXACT | 1.00 | 771 | already canonical; corroborated by NPD_NUMBER 7405 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-1 C') |
| `PROD` | `7405` | IDENTIFIER | 1.00 | 746 | NPD_NUMBER 7405 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-1 C') |
| `PROD` | `NO 15/9-F-1 C` | NORMALIZED | 0.95 | 746 | stages a-d; decided at d_split_sidetrack; corroborated by NPD_NUMBER 7405 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-1 C') |
| `SIM` | `P-F-1C` | NORMALIZED | 0.70 | 2 | simulator producer name; block 15/9 assumed because the name omits it, then corroborated by a source that named its own block |
| `TRAJ` | `15_9-F-1 C` | NORMALIZED | 0.95 | 4 | stages a-d; decided at d_split_sidetrack |

### `15/9-F-10`

well_code `15/9-F-10`, no sidetrack (original hole) — 17 identities

| source_system | source_identifier | match_method | conf. | seen | evidence |
|---|---|---|---:|---:|---|
| `ARCHIVE` | `Norway-StatoilHydro-15_$47$_9-F-10` | NORMALIZED | 0.95 | 12 | stages a-d; decided at c_canonical_separators |
| `DDR` | `15/9-F-10` | EXACT | 1.00 | 142 | already canonical; corroborated by NPD_NUMBER 6099 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-10') |
| `DDR` | `15_9_F_10` | NORMALIZED | 0.95 | 213 | stages a-d; decided at c_canonical_separators |
| `DDR` | `6099` | IDENTIFIER | 1.00 | 71 | NPD_NUMBER 6099 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-10') |
| `DDR` | `NO 15/9-F-10` | NORMALIZED | 0.95 | 142 | stages a-d; decided at b_strip_prefixes; corroborated by NPD_NUMBER 6099 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-10') |
| `SIM` | `P-F-10` | NORMALIZED | 0.70 | 2 | simulator producer name; block 15/9 assumed because the name omits it, then corroborated by a source that named its own block |
| `TRAJ` | `15/9-F-10` | EXACT | 1.00 | 5 | already canonical; corroborated by W_NUMBER W-924688 (from TRAJ XML_NAME_WELL '15/9-F-10') |
| `TRAJ` | `15/9-F-10 - Main Wellbore` | NORMALIZED | 0.90 | 5 | WITSML 'Main Wellbore' descriptor: the original hole of well 15/9-F-10; corroborated by B_NUMBER B-924688 (from TRAJ XML_NAME_WELLBORE '15/9-F-10 - Main Wellbore') |
| `TRAJ` | `15_9-F-10` | NORMALIZED | 0.95 | 19 | stages a-d; decided at c_canonical_separators |
| `TRAJ` | `B-924688` | IDENTIFIER | 1.00 | 5 | B_NUMBER B-924688 (from TRAJ XML_NAME_WELLBORE '15/9-F-10 - Main Wellbore') |
| `TRAJ` | `Norway-StatoilHydro-15_$47$_9-F-10` | NORMALIZED | 0.95 | 6 | stages a-d; decided at c_canonical_separators |
| `TRAJ` | `W-924688` | IDENTIFIER | 1.00 | 5 | W_NUMBER W-924688 (from TRAJ XML_NAME_WELL '15/9-F-10') |
| `WITSML` | `15/9-F-10` | EXACT | 1.00 | 2 | already canonical; corroborated by W_NUMBER W-924688 (from TRAJ XML_NAME_WELL '15/9-F-10') |
| `WITSML` | `15/9-F-10 - Main Wellbore` | NORMALIZED | 0.90 | 1 | WITSML 'Main Wellbore' descriptor: the original hole of well 15/9-F-10; corroborated by B_NUMBER B-924688 (from TRAJ XML_NAME_WELLBORE '15/9-F-10 - Main Wellbore') |
| `WITSML` | `B-924688` | IDENTIFIER | 1.00 | 1 | B_NUMBER B-924688 (from TRAJ XML_NAME_WELLBORE '15/9-F-10 - Main Wellbore') |
| `WITSML` | `Norway-StatoilHydro-15_$47$_9-F-10` | NORMALIZED | 0.95 | 6 | stages a-d; decided at c_canonical_separators |
| `WITSML` | `W-924688` | IDENTIFIER | 1.00 | 2 | W_NUMBER W-924688 (from TRAJ XML_NAME_WELL '15/9-F-10') |

### `15/9-F-10 A`

well_code `15/9-F-10`, sidetrack_code `A` — 1 identities

| source_system | source_identifier | match_method | conf. | seen | evidence |
|---|---|---|---:|---:|---|
| `TRAJ` | `15_9-F-10 A` | NORMALIZED | 0.95 | 10 | stages a-d; decided at d_split_sidetrack |

### `15/9-F-11`

well_code `15/9-F-11`, no sidetrack (original hole) — 12 identities

| source_system | source_identifier | match_method | conf. | seen | evidence |
|---|---|---|---:|---:|---|
| `ARCHIVE` | `15_9-F-11` | NORMALIZED | 0.95 | 29 | stages a-d; decided at c_canonical_separators |
| `DDR` | `15/9-F-11` | EXACT | 1.00 | 87 | already canonical; corroborated by NPD_NUMBER 7078 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-11') |
| `DDR` | `15_9_F_11` | NORMALIZED | 0.95 | 51 | stages a-d; decided at c_canonical_separators |
| `DDR` | `7078` | IDENTIFIER | 1.00 | 70 | NPD_NUMBER 7078 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-11') |
| `DDR` | `NO 15/9-F-11` | NORMALIZED | 0.95 | 87 | stages a-d; decided at b_strip_prefixes; corroborated by NPD_NUMBER 7078 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-11') |
| `DOC` | `15_9-F-11` | NORMALIZED | 0.95 | 9 | stages a-d; decided at c_canonical_separators |
| `LOG` | `15/9-F-11` | EXACT | 1.00 | 1 | already canonical |
| `LOG` | `15_9-F-11` | NORMALIZED | 0.95 | 20 | stages a-d; decided at c_canonical_separators |
| `PROD` | `15/9-F-11` | EXACT | 1.00 | 1204 | already canonical; corroborated by NPD_NUMBER 7078 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-11') |
| `PROD` | `7078` | IDENTIFIER | 1.00 | 1165 | NPD_NUMBER 7078 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-11') |
| `PROD` | `NO 15/9-F-11 H` | IDENTIFIER | 1.00 | 1165 | NPD_NUMBER 7078 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-11'); overrules the name, which parses to '15/9-F-11 H' |
| `TRAJ` | `15_9-F-11` | NORMALIZED | 0.95 | 30 | stages a-d; decided at c_canonical_separators |

### `15/9-F-11 A`

well_code `15/9-F-11`, sidetrack_code `A` — 5 identities

| source_system | source_identifier | match_method | conf. | seen | evidence |
|---|---|---|---:|---:|---|
| `DDR` | `15/9-F-11 A` | EXACT | 1.00 | 28 | already canonical; corroborated by NPD_NUMBER 7079 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-11 A') |
| `DDR` | `15_9_F_11_A` | NORMALIZED | 0.95 | 42 | stages a-d; decided at d_split_sidetrack |
| `DDR` | `7079` | IDENTIFIER | 1.00 | 14 | NPD_NUMBER 7079 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-11 A') |
| `DDR` | `NO 15/9-F-11 A` | NORMALIZED | 0.95 | 28 | stages a-d; decided at d_split_sidetrack; corroborated by NPD_NUMBER 7079 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-11 A') |
| `TRAJ` | `15_9-F-11 A` | NORMALIZED | 0.95 | 4 | stages a-d; decided at d_split_sidetrack |

### `15/9-F-11 B`

well_code `15/9-F-11`, sidetrack_code `B` — 6 identities

| source_system | source_identifier | match_method | conf. | seen | evidence |
|---|---|---|---:|---:|---|
| `DDR` | `15/9-F-11 B` | EXACT | 1.00 | 180 | already canonical; corroborated by NPD_NUMBER 7080 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-11 B') |
| `DDR` | `15_9_F_11_B` | NORMALIZED | 0.95 | 270 | stages a-d; decided at d_split_sidetrack |
| `DDR` | `7080` | IDENTIFIER | 1.00 | 90 | NPD_NUMBER 7080 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-11 B') |
| `DDR` | `NO 15/9-F-11 B` | NORMALIZED | 0.95 | 180 | stages a-d; decided at d_split_sidetrack; corroborated by NPD_NUMBER 7080 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-11 B') |
| `SIM` | `P-F-11B` | NORMALIZED | 0.70 | 2 | simulator producer name; block 15/9 assumed because the name omits it, then corroborated by a source that named its own block |
| `TRAJ` | `15_9-F-11 B` | NORMALIZED | 0.95 | 4 | stages a-d; decided at d_split_sidetrack |

### `15/9-F-11 T2`

well_code `15/9-F-11`, sidetrack_code `T2` — 4 identities

| source_system | source_identifier | match_method | conf. | seen | evidence |
|---|---|---|---:|---:|---|
| `DDR` | `15/9-F-11 T2` | EXACT | 1.00 | 53 | already canonical |
| `DDR` | `15_9_F_11_T2` | NORMALIZED | 0.95 | 159 | stages a-d; decided at d_split_sidetrack |
| `DDR` | `NO 15/9-F-11 T2` | NORMALIZED | 0.95 | 53 | stages a-d; decided at d_split_sidetrack |
| `TRAJ` | `15_9-F-11 T2` | NORMALIZED | 0.95 | 5 | stages a-d; decided at d_split_sidetrack |

### `15/9-F-12`

well_code `15/9-F-12`, no sidetrack (original hole) — 36 identities

| source_system | source_identifier | match_method | conf. | seen | evidence |
|---|---|---|---:|---:|---|
| `ARCHIVE` | `15_9-F-12` | NORMALIZED | 0.95 | 250 | stages a-d; decided at c_canonical_separators |
| `ARCHIVE` | `Norway-Statoil-15_$47$_9-F-12` | NORMALIZED | 0.95 | 15 | stages a-d; decided at c_canonical_separators |
| `ARCHIVE` | `Norway-Statoil-NO 15_$47$_9-F-12` | NORMALIZED | 0.95 | 694 | stages a-d; decided at c_canonical_separators |
| `DDR` | `15/9-F-12` | EXACT | 1.00 | 330 | already canonical; corroborated by NPD_NUMBER 5599 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-12') |
| `DDR` | `15_9_F_12` | NORMALIZED | 0.95 | 495 | stages a-d; decided at c_canonical_separators |
| `DDR` | `5599` | IDENTIFIER | 1.00 | 165 | NPD_NUMBER 5599 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-12') |
| `DDR` | `NO 15/9-F-12` | NORMALIZED | 0.95 | 330 | stages a-d; decided at b_strip_prefixes; corroborated by NPD_NUMBER 5599 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-12') |
| `DOC` | `15_9-F-12` | NORMALIZED | 0.95 | 18 | stages a-d; decided at c_canonical_separators |
| `LOG` | `15/9-F-12` | EXACT | 1.00 | 14 | already canonical |
| `LOG` | `15_9-F-12` | NORMALIZED | 0.95 | 232 | stages a-d; decided at c_canonical_separators |
| `LOG` | `15_9_F-12` | NORMALIZED | 0.95 | 6 | stages a-d; decided at c_canonical_separators |
| `LOG` | `NO 15/9-F-12` | NORMALIZED | 0.95 | 8 | stages a-d; decided at b_strip_prefixes |
| `LOG` | `NO_15/9-F-12` | NORMALIZED | 0.95 | 1 | stages a-d; decided at b_strip_prefixes |
| `PROD` | `15/9-F-12` | EXACT | 1.00 | 3160 | already canonical; corroborated by NPD_NUMBER 5599 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-12') |
| `PROD` | `5599` | IDENTIFIER | 1.00 | 3056 | NPD_NUMBER 5599 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-12') |
| `PROD` | `NO 15/9-F-12 H` | IDENTIFIER | 1.00 | 3056 | NPD_NUMBER 5599 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-12'); overrules the name, which parses to '15/9-F-12 H' |
| `SIM` | `P-F-12` | NORMALIZED | 0.70 | 2 | simulator producer name; block 15/9 assumed because the name omits it, then corroborated by a source that named its own block |
| `TRAJ` | `15/9-F-12` | EXACT | 1.00 | 8 | already canonical; corroborated by W_NUMBER W-353084 (from TRAJ XML_NAME_WELL '15/9-F-12') |
| `TRAJ` | `15/9-F-12 - Main Wellbore` | NORMALIZED | 0.90 | 8 | WITSML 'Main Wellbore' descriptor: the original hole of well 15/9-F-12; corroborated by B_NUMBER B-353084 (from TRAJ XML_NAME_WELLBORE '15/9-F-12 - Main Wellbore') |
| `TRAJ` | `15_9-F-12` | NORMALIZED | 0.95 | 9 | stages a-d; decided at c_canonical_separators |
| `TRAJ` | `97debbde-fcef-4ad2-ad00-6205300609fa` | IDENTIFIER | 1.00 | 1 | UUID 97debbde-fcef-4ad2-ad00-6205300609fa (from TRAJ XML_NAME_WELL\|XML_NAME_WELLBORE 'NO 15/9-F-12') |
| `TRAJ` | `B-353084` | IDENTIFIER | 1.00 | 8 | B_NUMBER B-353084 (from TRAJ XML_NAME_WELLBORE '15/9-F-12 - Main Wellbore') |
| `TRAJ` | `NO 15/9-F-12` | NORMALIZED | 0.95 | 2 | stages a-d; decided at b_strip_prefixes; corroborated by UUID a82580d7-d94f-4e5a-9a04-be8bcae02998 (from TRAJ XML_NAME_WELL\|XML_NAME_WELLBORE 'NO 15/9-F-12') |
| `TRAJ` | `Norway-Statoil-15_$47$_9-F-12` | NORMALIZED | 0.95 | 9 | stages a-d; decided at c_canonical_separators |
| `TRAJ` | `Norway-Statoil-NO 15_$47$_9-F-12` | NORMALIZED | 0.95 | 2 | stages a-d; decided at c_canonical_separators |
| `TRAJ` | `W-353084` | IDENTIFIER | 1.00 | 8 | W_NUMBER W-353084 (from TRAJ XML_NAME_WELL '15/9-F-12') |
| `TRAJ` | `a82580d7-d94f-4e5a-9a04-be8bcae02998` | IDENTIFIER | 1.00 | 1 | UUID a82580d7-d94f-4e5a-9a04-be8bcae02998 (from TRAJ XML_NAME_WELL\|XML_NAME_WELLBORE 'NO 15/9-F-12') |
| `WITSML` | `15/9-F-12` | EXACT | 1.00 | 2 | already canonical; corroborated by W_NUMBER W-353084 (from TRAJ XML_NAME_WELL '15/9-F-12') |
| `WITSML` | `15/9-F-12 - Main Wellbore` | NORMALIZED | 0.90 | 1 | WITSML 'Main Wellbore' descriptor: the original hole of well 15/9-F-12; corroborated by B_NUMBER B-353084 (from TRAJ XML_NAME_WELLBORE '15/9-F-12 - Main Wellbore') |
| `WITSML` | `97debbde-fcef-4ad2-ad00-6205300609fa` | IDENTIFIER | 1.00 | 683 | UUID 97debbde-fcef-4ad2-ad00-6205300609fa (from TRAJ XML_NAME_WELL\|XML_NAME_WELLBORE 'NO 15/9-F-12') |
| `WITSML` | `B-353084` | IDENTIFIER | 1.00 | 1 | B_NUMBER B-353084 (from TRAJ XML_NAME_WELLBORE '15/9-F-12 - Main Wellbore') |
| `WITSML` | `NO 15/9-F-12` | NORMALIZED | 0.95 | 1367 | stages a-d; decided at b_strip_prefixes; corroborated by UUID a82580d7-d94f-4e5a-9a04-be8bcae02998 (from TRAJ XML_NAME_WELL\|XML_NAME_WELLBORE 'NO 15/9-F-12') |
| `WITSML` | `Norway-Statoil-15_$47$_9-F-12` | NORMALIZED | 0.95 | 6 | stages a-d; decided at c_canonical_separators |
| `WITSML` | `Norway-Statoil-NO 15_$47$_9-F-12` | NORMALIZED | 0.95 | 692 | stages a-d; decided at c_canonical_separators |
| `WITSML` | `W-353084` | IDENTIFIER | 1.00 | 2 | W_NUMBER W-353084 (from TRAJ XML_NAME_WELL '15/9-F-12') |
| `WITSML` | `a82580d7-d94f-4e5a-9a04-be8bcae02998` | IDENTIFIER | 1.00 | 684 | UUID a82580d7-d94f-4e5a-9a04-be8bcae02998 (from TRAJ XML_NAME_WELL\|XML_NAME_WELLBORE 'NO 15/9-F-12') |

### `15/9-F-13`

well_code `15/9-F-13`, no sidetrack (original hole) — 1 identities

| source_system | source_identifier | match_method | conf. | seen | evidence |
|---|---|---|---:|---:|---|
| `TRAJ` | `15_9-F-13` | NORMALIZED | 0.95 | 21 | stages a-d; decided at c_canonical_separators |

### `15/9-F-14`

well_code `15/9-F-14`, no sidetrack (original hole) — 36 identities

| source_system | source_identifier | match_method | conf. | seen | evidence |
|---|---|---|---:|---:|---|
| `ARCHIVE` | `15_9-F-14` | NORMALIZED | 0.95 | 234 | stages a-d; decided at c_canonical_separators |
| `ARCHIVE` | `Norway-Statoil-NO 15_$47$_9-F-14` | NORMALIZED | 0.95 | 609 | stages a-d; decided at c_canonical_separators |
| `ARCHIVE` | `Norway-StatoilHydro-15_$47$_9-F-14` | NORMALIZED | 0.95 | 15 | stages a-d; decided at c_canonical_separators |
| `DDR` | `15/9-F-14` | EXACT | 1.00 | 268 | already canonical; corroborated by NPD_NUMBER 5351 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-14') |
| `DDR` | `15_9_F_14` | NORMALIZED | 0.95 | 402 | stages a-d; decided at c_canonical_separators |
| `DDR` | `5351` | IDENTIFIER | 1.00 | 134 | NPD_NUMBER 5351 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-14') |
| `DDR` | `NO 15/9-F-14` | NORMALIZED | 0.95 | 268 | stages a-d; decided at b_strip_prefixes; corroborated by NPD_NUMBER 5351 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-14') |
| `DOC` | `15_9-F-14` | NORMALIZED | 0.95 | 14 | stages a-d; decided at c_canonical_separators |
| `LOG` | `15/9-F-14` | EXACT | 1.00 | 22 | already canonical |
| `LOG` | `15_9-F-14` | NORMALIZED | 0.95 | 220 | stages a-d; decided at c_canonical_separators |
| `LOG` | `15_9_F_14` | NORMALIZED | 0.95 | 3 | stages a-d; decided at c_canonical_separators |
| `LOG` | `NO 15/9-F-14` | NORMALIZED | 0.95 | 10 | stages a-d; decided at b_strip_prefixes |
| `LOG` | `NO_15/9-F-14` | NORMALIZED | 0.95 | 1 | stages a-d; decided at b_strip_prefixes |
| `PROD` | `15/9-F-14` | EXACT | 1.00 | 3160 | already canonical; corroborated by NPD_NUMBER 5351 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-14') |
| `PROD` | `5351` | IDENTIFIER | 1.00 | 3056 | NPD_NUMBER 5351 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-14') |
| `PROD` | `NO 15/9-F-14 H` | IDENTIFIER | 1.00 | 3056 | NPD_NUMBER 5351 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-14'); overrules the name, which parses to '15/9-F-14 H' |
| `SIM` | `P-F-14` | NORMALIZED | 0.70 | 2 | simulator producer name; block 15/9 assumed because the name omits it, then corroborated by a source that named its own block |
| `TRAJ` | `05fb8aee-3461-4071-8ac5-975b9bb5cc4f` | IDENTIFIER | 1.00 | 1 | UUID 05fb8aee-3461-4071-8ac5-975b9bb5cc4f (from TRAJ XML_NAME_WELL\|XML_NAME_WELLBORE 'NO 15/9-F-14') |
| `TRAJ` | `15/9-F-14` | EXACT | 1.00 | 5 | already canonical; corroborated by W_NUMBER W-353085 (from TRAJ XML_NAME_WELL '15/9-F-14') |
| `TRAJ` | `15/9-F-14 - Main Wellbore` | NORMALIZED | 0.90 | 5 | WITSML 'Main Wellbore' descriptor: the original hole of well 15/9-F-14; corroborated by B_NUMBER B-353085 (from TRAJ XML_NAME_WELLBORE '15/9-F-14 - Main Wellbore') |
| `TRAJ` | `15_9-F-14` | NORMALIZED | 0.95 | 12 | stages a-d; decided at c_canonical_separators |
| `TRAJ` | `B-353085` | IDENTIFIER | 1.00 | 5 | B_NUMBER B-353085 (from TRAJ XML_NAME_WELLBORE '15/9-F-14 - Main Wellbore') |
| `TRAJ` | `NO 15/9-F-14` | NORMALIZED | 0.95 | 2 | stages a-d; decided at b_strip_prefixes; corroborated by UUID cf870b7d-087b-4797-b000-4968e9f1beaf (from TRAJ XML_NAME_WELL\|XML_NAME_WELLBORE 'NO 15/9-F-14') |
| `TRAJ` | `Norway-Statoil-NO 15_$47$_9-F-14` | NORMALIZED | 0.95 | 2 | stages a-d; decided at c_canonical_separators |
| `TRAJ` | `Norway-StatoilHydro-15_$47$_9-F-14` | NORMALIZED | 0.95 | 6 | stages a-d; decided at c_canonical_separators |
| `TRAJ` | `W-353085` | IDENTIFIER | 1.00 | 5 | W_NUMBER W-353085 (from TRAJ XML_NAME_WELL '15/9-F-14') |
| `TRAJ` | `cf870b7d-087b-4797-b000-4968e9f1beaf` | IDENTIFIER | 1.00 | 1 | UUID cf870b7d-087b-4797-b000-4968e9f1beaf (from TRAJ XML_NAME_WELL\|XML_NAME_WELLBORE 'NO 15/9-F-14') |
| `WITSML` | `05fb8aee-3461-4071-8ac5-975b9bb5cc4f` | IDENTIFIER | 1.00 | 597 | UUID 05fb8aee-3461-4071-8ac5-975b9bb5cc4f (from TRAJ XML_NAME_WELL\|XML_NAME_WELLBORE 'NO 15/9-F-14') |
| `WITSML` | `15/9-F-14` | EXACT | 1.00 | 3 | already canonical; corroborated by W_NUMBER W-353085 (from TRAJ XML_NAME_WELL '15/9-F-14') |
| `WITSML` | `15/9-F-14 - Main Wellbore` | NORMALIZED | 0.90 | 1 | WITSML 'Main Wellbore' descriptor: the original hole of well 15/9-F-14; corroborated by B_NUMBER B-353085 (from TRAJ XML_NAME_WELLBORE '15/9-F-14 - Main Wellbore') |
| `WITSML` | `B-353085` | IDENTIFIER | 1.00 | 1 | B_NUMBER B-353085 (from TRAJ XML_NAME_WELLBORE '15/9-F-14 - Main Wellbore') |
| `WITSML` | `NO 15/9-F-14` | NORMALIZED | 0.95 | 1195 | stages a-d; decided at b_strip_prefixes; corroborated by UUID cf870b7d-087b-4797-b000-4968e9f1beaf (from TRAJ XML_NAME_WELL\|XML_NAME_WELLBORE 'NO 15/9-F-14') |
| `WITSML` | `Norway-Statoil-NO 15_$47$_9-F-14` | NORMALIZED | 0.95 | 607 | stages a-d; decided at c_canonical_separators |
| `WITSML` | `Norway-StatoilHydro-15_$47$_9-F-14` | NORMALIZED | 0.95 | 9 | stages a-d; decided at c_canonical_separators |
| `WITSML` | `W-353085` | IDENTIFIER | 1.00 | 3 | W_NUMBER W-353085 (from TRAJ XML_NAME_WELL '15/9-F-14') |
| `WITSML` | `cf870b7d-087b-4797-b000-4968e9f1beaf` | IDENTIFIER | 1.00 | 598 | UUID cf870b7d-087b-4797-b000-4968e9f1beaf (from TRAJ XML_NAME_WELL\|XML_NAME_WELLBORE 'NO 15/9-F-14') |

### `15/9-F-14 A`

well_code `15/9-F-14`, sidetrack_code `A` — 2 identities

| source_system | source_identifier | match_method | conf. | seen | evidence |
|---|---|---|---:|---:|---|
| `SIM` | `F-14A` | NORMALIZED | 0.70 | 1 | simulator well name; block 15/9 assumed because the name omits it, then corroborated by a source that named its own block |
| `TRAJ` | `15_9-F-14 A` | NORMALIZED | 0.95 | 3 | stages a-d; decided at d_split_sidetrack |

### `15/9-F-15`

well_code `15/9-F-15`, no sidetrack (original hole) — 28 identities

| source_system | source_identifier | match_method | conf. | seen | evidence |
|---|---|---|---:|---:|---|
| `ARCHIVE` | `15_9-F-15` | NORMALIZED | 0.95 | 109 | stages a-d; decided at c_canonical_separators |
| `ARCHIVE` | `Norway-Statoil-NO 15_$47$_9-F-15` | NORMALIZED | 0.95 | 2817 | stages a-d; decided at c_canonical_separators |
| `ARCHIVE` | `Norway-StatoilHydro-15_$47$_9-F-15` | NORMALIZED | 0.95 | 9 | stages a-d; decided at c_canonical_separators |
| `DDR` | `15/9-F-15` | EXACT | 1.00 | 138 | already canonical; corroborated by NPD_NUMBER 6184 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-15') |
| `DDR` | `15_9_F_15` | NORMALIZED | 0.95 | 207 | stages a-d; decided at c_canonical_separators |
| `DDR` | `6184` | IDENTIFIER | 1.00 | 69 | NPD_NUMBER 6184 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-15') |
| `DDR` | `NO 15/9-F-15` | NORMALIZED | 0.95 | 138 | stages a-d; decided at b_strip_prefixes; corroborated by NPD_NUMBER 6184 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-15') |
| `DOC` | `15_9-F-15` | NORMALIZED | 0.95 | 13 | stages a-d; decided at c_canonical_separators |
| `LOG` | `15/9-F-15` | EXACT | 1.00 | 7 | already canonical |
| `LOG` | `15/9-F15` | NORMALIZED | 0.95 | 2 | stages a-d; decided at c_canonical_separators |
| `LOG` | `15_9-F-15` | NORMALIZED | 0.95 | 96 | stages a-d; decided at c_canonical_separators |
| `TRAJ` | `15/9-F-15` | EXACT | 1.00 | 2 | already canonical; corroborated by W_NUMBER W-826806 (from TRAJ XML_NAME_WELL '15/9-F-15') |
| `TRAJ` | `15/9-F-15 - Main Wellbore` | NORMALIZED | 0.90 | 2 | WITSML 'Main Wellbore' descriptor: the original hole of well 15/9-F-15; corroborated by B_NUMBER B-826806 (from TRAJ XML_NAME_WELLBORE '15/9-F-15 - Main Wellbore') |
| `TRAJ` | `15_9-F-15` | NORMALIZED | 0.95 | 17 | stages a-d; decided at c_canonical_separators |
| `TRAJ` | `B-826806` | IDENTIFIER | 1.00 | 2 | B_NUMBER B-826806 (from TRAJ XML_NAME_WELLBORE '15/9-F-15 - Main Wellbore') |
| `TRAJ` | `NO 15/9-F-15` | NORMALIZED | 0.95 | 2 | stages a-d; decided at b_strip_prefixes; corroborated by UUID dd19bf7b-02a7-4383-9038-ce201cee4d91 (from TRAJ XML_NAME_WELL 'NO 15/9-F-15') |
| `TRAJ` | `Norway-Statoil-NO 15_$47$_9-F-15` | NORMALIZED | 0.95 | 4 | stages a-d; decided at c_canonical_separators |
| `TRAJ` | `Norway-StatoilHydro-15_$47$_9-F-15` | NORMALIZED | 0.95 | 3 | stages a-d; decided at c_canonical_separators |
| `TRAJ` | `W-826806` | IDENTIFIER | 1.00 | 2 | W_NUMBER W-826806 (from TRAJ XML_NAME_WELL '15/9-F-15') |
| `TRAJ` | `dd19bf7b-02a7-4383-9038-ce201cee4d91` | IDENTIFIER | 1.00 | 2 | UUID dd19bf7b-02a7-4383-9038-ce201cee4d91 (from TRAJ XML_NAME_WELL 'NO 15/9-F-15') |
| `WITSML` | `15/9-F-15` | EXACT | 1.00 | 2 | already canonical; corroborated by W_NUMBER W-826806 (from TRAJ XML_NAME_WELL '15/9-F-15') |
| `WITSML` | `15/9-F-15 - Main Wellbore` | NORMALIZED | 0.90 | 1 | WITSML 'Main Wellbore' descriptor: the original hole of well 15/9-F-15; corroborated by B_NUMBER B-826806 (from TRAJ XML_NAME_WELLBORE '15/9-F-15 - Main Wellbore') |
| `WITSML` | `B-826806` | IDENTIFIER | 1.00 | 1 | B_NUMBER B-826806 (from TRAJ XML_NAME_WELLBORE '15/9-F-15 - Main Wellbore') |
| `WITSML` | `NO 15/9-F-15` | NORMALIZED | 0.95 | 2795 | stages a-d; decided at b_strip_prefixes; corroborated by UUID dd19bf7b-02a7-4383-9038-ce201cee4d91 (from TRAJ XML_NAME_WELL 'NO 15/9-F-15') |
| `WITSML` | `Norway-Statoil-NO 15_$47$_9-F-15` | NORMALIZED | 0.95 | 2813 | stages a-d; decided at c_canonical_separators |
| `WITSML` | `Norway-StatoilHydro-15_$47$_9-F-15` | NORMALIZED | 0.95 | 6 | stages a-d; decided at c_canonical_separators |
| `WITSML` | `W-826806` | IDENTIFIER | 1.00 | 2 | W_NUMBER W-826806 (from TRAJ XML_NAME_WELL '15/9-F-15') |
| `WITSML` | `dd19bf7b-02a7-4383-9038-ce201cee4d91` | IDENTIFIER | 1.00 | 2795 | UUID dd19bf7b-02a7-4383-9038-ce201cee4d91 (from TRAJ XML_NAME_WELL 'NO 15/9-F-15') |

### `15/9-F-15 A`

well_code `15/9-F-15`, sidetrack_code `A` — 23 identities

| source_system | source_identifier | match_method | conf. | seen | evidence |
|---|---|---|---:|---:|---|
| `ARCHIVE` | `15_9-F-15 A` | NORMALIZED | 0.95 | 129 | stages a-d; decided at d_split_sidetrack |
| `ARCHIVE` | `Norway-StatoilHydro-15_$47$_9-F-15A` | NORMALIZED | 0.95 | 9 | stages a-d; decided at d_split_sidetrack |
| `DDR` | `15/9-F-15 A` | EXACT | 1.00 | 68 | already canonical; corroborated by NPD_NUMBER 5785 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-15 A') |
| `DDR` | `15_9_F_15_A` | NORMALIZED | 0.95 | 102 | stages a-d; decided at d_split_sidetrack |
| `DDR` | `5785` | IDENTIFIER | 1.00 | 34 | NPD_NUMBER 5785 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-15 A') |
| `DDR` | `NO 15/9-F-15 A` | NORMALIZED | 0.95 | 68 | stages a-d; decided at d_split_sidetrack; corroborated by NPD_NUMBER 5785 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-15 A') |
| `DOC` | `15_9-F-15 A` | NORMALIZED | 0.95 | 6 | stages a-d; decided at d_split_sidetrack |
| `LOG` | `15/9-F-15 A` | EXACT | 1.00 | 14 | already canonical |
| `LOG` | `15/9-F-15A` | NORMALIZED | 0.95 | 7 | stages a-d; decided at d_split_sidetrack |
| `LOG` | `15_9-F-15 A` | NORMALIZED | 0.95 | 66 | stages a-d; decided at d_split_sidetrack |
| `LOG` | `NO_15/9-F-15_A` | NORMALIZED | 0.95 | 1 | stages a-d; decided at d_split_sidetrack |
| `TRAJ` | `15/9-F-15A` | NORMALIZED | 0.95 | 2 | stages a-d; decided at d_split_sidetrack; corroborated by W_NUMBER W-861401 (from TRAJ XML_NAME_WELL '15/9-F-15A') |
| `TRAJ` | `15/9-F-15A - Main Wellbore` | NORMALIZED | 0.90 | 2 | WITSML 'Main Wellbore' descriptor: the original hole of well 15/9-F-15 A; corroborated by B_NUMBER B-861401 (from TRAJ XML_NAME_WELLBORE '15/9-F-15A - Main Wellbore') |
| `TRAJ` | `15_9-F-15 A` | NORMALIZED | 0.95 | 2 | stages a-d; decided at d_split_sidetrack |
| `TRAJ` | `B-861401` | IDENTIFIER | 1.00 | 2 | B_NUMBER B-861401 (from TRAJ XML_NAME_WELLBORE '15/9-F-15A - Main Wellbore') |
| `TRAJ` | `Norway-StatoilHydro-15_$47$_9-F-15A` | NORMALIZED | 0.95 | 3 | stages a-d; decided at d_split_sidetrack |
| `TRAJ` | `W-861401` | IDENTIFIER | 1.00 | 2 | W_NUMBER W-861401 (from TRAJ XML_NAME_WELL '15/9-F-15A') |
| `VSP` | `15_9-F-15 A` | NORMALIZED | 0.95 | 57 | stages a-d; decided at d_split_sidetrack |
| `WITSML` | `15/9-F-15A` | NORMALIZED | 0.95 | 2 | stages a-d; decided at d_split_sidetrack; corroborated by W_NUMBER W-861401 (from TRAJ XML_NAME_WELL '15/9-F-15A') |
| `WITSML` | `15/9-F-15A - Main Wellbore` | NORMALIZED | 0.90 | 1 | WITSML 'Main Wellbore' descriptor: the original hole of well 15/9-F-15 A; corroborated by B_NUMBER B-861401 (from TRAJ XML_NAME_WELLBORE '15/9-F-15A - Main Wellbore') |
| `WITSML` | `B-861401` | IDENTIFIER | 1.00 | 1 | B_NUMBER B-861401 (from TRAJ XML_NAME_WELLBORE '15/9-F-15A - Main Wellbore') |
| `WITSML` | `Norway-StatoilHydro-15_$47$_9-F-15A` | NORMALIZED | 0.95 | 6 | stages a-d; decided at d_split_sidetrack |
| `WITSML` | `W-861401` | IDENTIFIER | 1.00 | 2 | W_NUMBER W-861401 (from TRAJ XML_NAME_WELL '15/9-F-15A') |

### `15/9-F-15 B`

well_code `15/9-F-15`, sidetrack_code `B` — 22 identities

| source_system | source_identifier | match_method | conf. | seen | evidence |
|---|---|---|---:|---:|---|
| `ARCHIVE` | `15_9-F-15 B` | NORMALIZED | 0.95 | 51 | stages a-d; decided at d_split_sidetrack |
| `ARCHIVE` | `Norway-StatoilHydro-15_$47$_9-F-15B` | NORMALIZED | 0.95 | 8 | stages a-d; decided at d_split_sidetrack |
| `DDR` | `15/9-F-15 B` | EXACT | 1.00 | 12 | already canonical; corroborated by NPD_NUMBER 6046 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-15 B') |
| `DDR` | `15_9_F_15_B` | NORMALIZED | 0.95 | 18 | stages a-d; decided at d_split_sidetrack |
| `DDR` | `6046` | IDENTIFIER | 1.00 | 6 | NPD_NUMBER 6046 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-15 B') |
| `DDR` | `NO 15/9-F-15 B` | NORMALIZED | 0.95 | 12 | stages a-d; decided at d_split_sidetrack; corroborated by NPD_NUMBER 6046 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-15 B') |
| `DOC` | `15_9-F-15 B` | NORMALIZED | 0.95 | 6 | stages a-d; decided at d_split_sidetrack |
| `LOG` | `15/9-F-15 B` | EXACT | 1.00 | 4 | already canonical |
| `LOG` | `15/9-F-15B` | NORMALIZED | 0.95 | 2 | stages a-d; decided at d_split_sidetrack |
| `LOG` | `15_9-F-15 B` | NORMALIZED | 0.95 | 45 | stages a-d; decided at d_split_sidetrack |
| `LOG` | `NO_15/9-F-15_B` | NORMALIZED | 0.95 | 1 | stages a-d; decided at d_split_sidetrack |
| `TRAJ` | `15/9-F-15B` | NORMALIZED | 0.95 | 1 | stages a-d; decided at d_split_sidetrack; corroborated by W_NUMBER W-854763 (from TRAJ XML_NAME_WELL '15/9-F-15B') |
| `TRAJ` | `15/9-F-15B - Main Wellbore` | NORMALIZED | 0.90 | 1 | WITSML 'Main Wellbore' descriptor: the original hole of well 15/9-F-15 B; corroborated by B_NUMBER B-854763 (from TRAJ XML_NAME_WELLBORE '15/9-F-15B - Main Wellbore') |
| `TRAJ` | `15_9-F-15 B` | NORMALIZED | 0.95 | 4 | stages a-d; decided at d_split_sidetrack |
| `TRAJ` | `B-854763` | IDENTIFIER | 1.00 | 1 | B_NUMBER B-854763 (from TRAJ XML_NAME_WELLBORE '15/9-F-15B - Main Wellbore') |
| `TRAJ` | `Norway-StatoilHydro-15_$47$_9-F-15B` | NORMALIZED | 0.95 | 2 | stages a-d; decided at d_split_sidetrack |
| `TRAJ` | `W-854763` | IDENTIFIER | 1.00 | 1 | W_NUMBER W-854763 (from TRAJ XML_NAME_WELL '15/9-F-15B') |
| `WITSML` | `15/9-F-15B` | NORMALIZED | 0.95 | 2 | stages a-d; decided at d_split_sidetrack; corroborated by W_NUMBER W-854763 (from TRAJ XML_NAME_WELL '15/9-F-15B') |
| `WITSML` | `15/9-F-15B - Main Wellbore` | NORMALIZED | 0.90 | 1 | WITSML 'Main Wellbore' descriptor: the original hole of well 15/9-F-15 B; corroborated by B_NUMBER B-854763 (from TRAJ XML_NAME_WELLBORE '15/9-F-15B - Main Wellbore') |
| `WITSML` | `B-854763` | IDENTIFIER | 1.00 | 1 | B_NUMBER B-854763 (from TRAJ XML_NAME_WELLBORE '15/9-F-15B - Main Wellbore') |
| `WITSML` | `Norway-StatoilHydro-15_$47$_9-F-15B` | NORMALIZED | 0.95 | 6 | stages a-d; decided at d_split_sidetrack |
| `WITSML` | `W-854763` | IDENTIFIER | 1.00 | 2 | W_NUMBER W-854763 (from TRAJ XML_NAME_WELL '15/9-F-15B') |

### `15/9-F-15 C`

well_code `15/9-F-15`, sidetrack_code `C` — 16 identities

| source_system | source_identifier | match_method | conf. | seen | evidence |
|---|---|---|---:|---:|---|
| `ARCHIVE` | `15_9-F-15 C` | NORMALIZED | 0.95 | 92 | stages a-d; decided at d_split_sidetrack |
| `DDR` | `15/9-F-15 C` | EXACT | 1.00 | 168 | already canonical; corroborated by NPD_NUMBER 5794 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-15 C') |
| `DDR` | `15_9_F_15_C` | NORMALIZED | 0.95 | 252 | stages a-d; decided at d_split_sidetrack |
| `DDR` | `5794` | IDENTIFIER | 1.00 | 84 | NPD_NUMBER 5794 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-15 C') |
| `DDR` | `NO 15/9-F-15 C` | NORMALIZED | 0.95 | 168 | stages a-d; decided at d_split_sidetrack; corroborated by NPD_NUMBER 5794 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-15 C') |
| `DOC` | `15_9-F-15 C` | NORMALIZED | 0.95 | 5 | stages a-d; decided at d_split_sidetrack |
| `LOG` | `15/9-F-15 C` | EXACT | 1.00 | 14 | already canonical |
| `LOG` | `15_9-F-15 C` | NORMALIZED | 0.95 | 87 | stages a-d; decided at d_split_sidetrack |
| `LOG` | `NO 15/9-F-15 C` | NORMALIZED | 0.95 | 1 | stages a-d; decided at d_split_sidetrack |
| `LOG` | `NO_15/9-F-15_C` | NORMALIZED | 0.95 | 1 | stages a-d; decided at d_split_sidetrack |
| `SIM` | `P-F-15C` | NORMALIZED | 0.70 | 2 | simulator producer name; block 15/9 assumed because the name omits it, then corroborated by a source that named its own block |
| `TRAJ` | `15_9-F-15 C` | NORMALIZED | 0.95 | 2 | stages a-d; decided at d_split_sidetrack |
| `TRAJ` | `9ab4989d-11c6-4ac1-83c1-e74362292dd8` | IDENTIFIER | 1.00 | 1 | UUID 9ab4989d-11c6-4ac1-83c1-e74362292dd8 (from TRAJ XML_NAME_WELLBORE 'NO 15/9-F-15 C') |
| `TRAJ` | `NO 15/9-F-15 C` | NORMALIZED | 0.95 | 1 | stages a-d; decided at d_split_sidetrack; corroborated by UUID 9ab4989d-11c6-4ac1-83c1-e74362292dd8 (from TRAJ XML_NAME_WELLBORE 'NO 15/9-F-15 C') |
| `WITSML` | `9ab4989d-11c6-4ac1-83c1-e74362292dd8` | IDENTIFIER | 1.00 | 532 | UUID 9ab4989d-11c6-4ac1-83c1-e74362292dd8 (from TRAJ XML_NAME_WELLBORE 'NO 15/9-F-15 C') |
| `WITSML` | `NO 15/9-F-15 C` | NORMALIZED | 0.95 | 532 | stages a-d; decided at d_split_sidetrack; corroborated by UUID 9ab4989d-11c6-4ac1-83c1-e74362292dd8 (from TRAJ XML_NAME_WELLBORE 'NO 15/9-F-15 C') |

### `15/9-F-15 D`

well_code `15/9-F-15`, sidetrack_code `D` — 17 identities

| source_system | source_identifier | match_method | conf. | seen | evidence |
|---|---|---|---:|---:|---|
| `ARCHIVE` | `15_9-F-15 D` | NORMALIZED | 0.95 | 76 | stages a-d; decided at d_split_sidetrack |
| `DDR` | `15/9-F-15 D` | EXACT | 1.00 | 198 | already canonical; corroborated by NPD_NUMBER 7289 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-15 D') |
| `DDR` | `15_9_F_15_D` | NORMALIZED | 0.95 | 297 | stages a-d; decided at d_split_sidetrack |
| `DDR` | `7289` | IDENTIFIER | 1.00 | 99 | NPD_NUMBER 7289 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-15 D') |
| `DDR` | `NO 15/9-F-15 D` | NORMALIZED | 0.95 | 198 | stages a-d; decided at d_split_sidetrack; corroborated by NPD_NUMBER 7289 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-15 D') |
| `DOC` | `15_9-F-15 D` | NORMALIZED | 0.95 | 14 | stages a-d; decided at d_split_sidetrack |
| `LOG` | `15/9-F-15 D` | EXACT | 1.00 | 2 | already canonical |
| `LOG` | `15_9-F-15 D` | NORMALIZED | 0.95 | 62 | stages a-d; decided at d_split_sidetrack |
| `PROD` | `15/9-F-15 D` | EXACT | 1.00 | 1011 | already canonical; corroborated by NPD_NUMBER 7289 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-15 D') |
| `PROD` | `7289` | IDENTIFIER | 1.00 | 978 | NPD_NUMBER 7289 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-15 D') |
| `PROD` | `NO 15/9-F-15 D` | NORMALIZED | 0.95 | 978 | stages a-d; decided at d_split_sidetrack; corroborated by NPD_NUMBER 7289 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-15 D') |
| `SIM` | `P-F-15D` | NORMALIZED | 0.70 | 2 | simulator producer name; block 15/9 assumed because the name omits it, then corroborated by a source that named its own block |
| `TRAJ` | `15_9-F-15 D` | NORMALIZED | 0.95 | 4 | stages a-d; decided at d_split_sidetrack |
| `TRAJ` | `NO 15/9-F-15 D` | NORMALIZED | 0.95 | 1 | stages a-d; decided at d_split_sidetrack; corroborated by UUID e0cab46e-aa2a-4d69-b466-108dafd4ae62 (from TRAJ XML_NAME_WELLBORE 'NO 15/9-F-15 D') |
| `TRAJ` | `e0cab46e-aa2a-4d69-b466-108dafd4ae62` | IDENTIFIER | 1.00 | 1 | UUID e0cab46e-aa2a-4d69-b466-108dafd4ae62 (from TRAJ XML_NAME_WELLBORE 'NO 15/9-F-15 D') |
| `WITSML` | `NO 15/9-F-15 D` | NORMALIZED | 0.95 | 2262 | stages a-d; decided at d_split_sidetrack; corroborated by UUID e0cab46e-aa2a-4d69-b466-108dafd4ae62 (from TRAJ XML_NAME_WELLBORE 'NO 15/9-F-15 D') |
| `WITSML` | `e0cab46e-aa2a-4d69-b466-108dafd4ae62` | IDENTIFIER | 1.00 | 2262 | UUID e0cab46e-aa2a-4d69-b466-108dafd4ae62 (from TRAJ XML_NAME_WELLBORE 'NO 15/9-F-15 D') |

### `15/9-F-15 S`

well_code `15/9-F-15`, sidetrack_code `S` — 12 identities

| source_system | source_identifier | match_method | conf. | seen | evidence |
|---|---|---|---:|---:|---|
| `ARCHIVE` | `Norway-StatoilHydro-15_$47$_9-F-15S` | NORMALIZED | 0.95 | 9 | stages a-d; decided at d_split_sidetrack |
| `LOG` | `15/9-F15S` | NORMALIZED | 0.95 | 2 | stages a-d; decided at d_split_sidetrack |
| `TRAJ` | `15/9-F-15S` | NORMALIZED | 0.95 | 2 | stages a-d; decided at d_split_sidetrack; corroborated by W_NUMBER W-744206 (from TRAJ XML_NAME_WELL '15/9-F-15S') |
| `TRAJ` | `15/9-F-15S - Main Wellbore` | NORMALIZED | 0.90 | 2 | WITSML 'Main Wellbore' descriptor: the original hole of well 15/9-F-15 S; corroborated by B_NUMBER B-744206 (from TRAJ XML_NAME_WELLBORE '15/9-F-15S - Main Wellbore') |
| `TRAJ` | `B-744206` | IDENTIFIER | 1.00 | 2 | B_NUMBER B-744206 (from TRAJ XML_NAME_WELLBORE '15/9-F-15S - Main Wellbore') |
| `TRAJ` | `Norway-StatoilHydro-15_$47$_9-F-15S` | NORMALIZED | 0.95 | 3 | stages a-d; decided at d_split_sidetrack |
| `TRAJ` | `W-744206` | IDENTIFIER | 1.00 | 2 | W_NUMBER W-744206 (from TRAJ XML_NAME_WELL '15/9-F-15S') |
| `WITSML` | `15/9-F-15S` | NORMALIZED | 0.95 | 2 | stages a-d; decided at d_split_sidetrack; corroborated by W_NUMBER W-744206 (from TRAJ XML_NAME_WELL '15/9-F-15S') |
| `WITSML` | `15/9-F-15S - Main Wellbore` | NORMALIZED | 0.90 | 1 | WITSML 'Main Wellbore' descriptor: the original hole of well 15/9-F-15 S; corroborated by B_NUMBER B-744206 (from TRAJ XML_NAME_WELLBORE '15/9-F-15S - Main Wellbore') |
| `WITSML` | `B-744206` | IDENTIFIER | 1.00 | 1 | B_NUMBER B-744206 (from TRAJ XML_NAME_WELLBORE '15/9-F-15S - Main Wellbore') |
| `WITSML` | `Norway-StatoilHydro-15_$47$_9-F-15S` | NORMALIZED | 0.95 | 6 | stages a-d; decided at d_split_sidetrack |
| `WITSML` | `W-744206` | IDENTIFIER | 1.00 | 2 | W_NUMBER W-744206 (from TRAJ XML_NAME_WELL '15/9-F-15S') |

### `15/9-F-2`

well_code `15/9-F-2`, no sidetrack (original hole) — 1 identities

| source_system | source_identifier | match_method | conf. | seen | evidence |
|---|---|---|---:|---:|---|
| `TRAJ` | `15_9-F-2` | NORMALIZED | 0.95 | 19 | stages a-d; decided at c_canonical_separators |

### `15/9-F-3`

well_code `15/9-F-3`, no sidetrack (original hole) — 1 identities

| source_system | source_identifier | match_method | conf. | seen | evidence |
|---|---|---|---:|---:|---|
| `TRAJ` | `15_9-F-3` | NORMALIZED | 0.95 | 13 | stages a-d; decided at c_canonical_separators |

### `15/9-F-4`

well_code `15/9-F-4`, no sidetrack (original hole) — 9 identities

| source_system | source_identifier | match_method | conf. | seen | evidence |
|---|---|---|---:|---:|---|
| `DDR` | `15/9-F-4` | EXACT | 1.00 | 260 | already canonical; corroborated by NPD_NUMBER 5693 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-4') |
| `DDR` | `15_9_F_4` | NORMALIZED | 0.95 | 390 | stages a-d; decided at c_canonical_separators |
| `DDR` | `5693` | IDENTIFIER | 1.00 | 130 | NPD_NUMBER 5693 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-4') |
| `DDR` | `NO 15/9-F-4` | NORMALIZED | 0.95 | 260 | stages a-d; decided at b_strip_prefixes; corroborated by NPD_NUMBER 5693 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-4') |
| `PROD` | `15/9-F-4` | EXACT | 1.00 | 3439 | already canonical; corroborated by NPD_NUMBER 5693 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-4') |
| `PROD` | `5693` | IDENTIFIER | 1.00 | 3327 | NPD_NUMBER 5693 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-4') |
| `PROD` | `NO 15/9-F-4 AH` | IDENTIFIER | 1.00 | 3327 | NPD_NUMBER 5693 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-4'); overrules the name, which parses to '15/9-F-4 AH' |
| `SIM` | `I-F-4` | NORMALIZED | 0.70 | 2 | simulator injector name; block 15/9 assumed because the name omits it, then corroborated by a source that named its own block |
| `TRAJ` | `15_9-F-4` | NORMALIZED | 0.95 | 11 | stages a-d; decided at c_canonical_separators |

### `15/9-F-5`

well_code `15/9-F-5`, no sidetrack (original hole) — 10 identities

| source_system | source_identifier | match_method | conf. | seen | evidence |
|---|---|---|---:|---:|---|
| `DDR` | `15/9-F-5` | EXACT | 1.00 | 206 | already canonical; corroborated by NPD_NUMBER 5769 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-5') |
| `DDR` | `15_9_F_5` | NORMALIZED | 0.95 | 309 | stages a-d; decided at c_canonical_separators |
| `DDR` | `5769` | IDENTIFIER | 1.00 | 103 | NPD_NUMBER 5769 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-5') |
| `DDR` | `NO 15/9-F-5` | NORMALIZED | 0.95 | 206 | stages a-d; decided at b_strip_prefixes; corroborated by NPD_NUMBER 5769 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-5') |
| `PROD` | `15/9-F-5` | EXACT | 1.00 | 3415 | already canonical; corroborated by NPD_NUMBER 5769 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-5') |
| `PROD` | `5769` | IDENTIFIER | 1.00 | 3306 | NPD_NUMBER 5769 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-5') |
| `PROD` | `NO 15/9-F-5 AH` | IDENTIFIER | 1.00 | 3306 | NPD_NUMBER 5769 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-5'); overrules the name, which parses to '15/9-F-5 AH' |
| `SIM` | `I-F-5` | NORMALIZED | 0.70 | 2 | simulator injector name; block 15/9 assumed because the name omits it, then corroborated by a source that named its own block |
| `SIM` | `P-F-5` | NORMALIZED | 0.70 | 3 | simulator producer name; block 15/9 assumed because the name omits it, then corroborated by a source that named its own block |
| `TRAJ` | `15_9-F-5` | NORMALIZED | 0.95 | 9 | stages a-d; decided at c_canonical_separators |

### `15/9-F-6`

well_code `15/9-F-6`, no sidetrack (original hole) — 1 identities

| source_system | source_identifier | match_method | conf. | seen | evidence |
|---|---|---|---:|---:|---|
| `TRAJ` | `15_9-F-6` | NORMALIZED | 0.95 | 1 | stages a-d; decided at c_canonical_separators |

### `15/9-F-7`

well_code `15/9-F-7`, no sidetrack (original hole) — 5 identities

| source_system | source_identifier | match_method | conf. | seen | evidence |
|---|---|---|---:|---:|---|
| `DDR` | `15/9-F-7` | EXACT | 1.00 | 78 | already canonical; corroborated by NPD_NUMBER 5610 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-7') |
| `DDR` | `15_9_F_7` | NORMALIZED | 0.95 | 117 | stages a-d; decided at c_canonical_separators |
| `DDR` | `5610` | IDENTIFIER | 1.00 | 39 | NPD_NUMBER 5610 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-7') |
| `DDR` | `NO 15/9-F-7` | NORMALIZED | 0.95 | 78 | stages a-d; decided at b_strip_prefixes; corroborated by NPD_NUMBER 5610 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-7') |
| `TRAJ` | `15_9-F-7` | NORMALIZED | 0.95 | 9 | stages a-d; decided at c_canonical_separators |

### `15/9-F-8`

well_code `15/9-F-8`, no sidetrack (original hole) — 1 identities

| source_system | source_identifier | match_method | conf. | seen | evidence |
|---|---|---|---:|---:|---|
| `TRAJ` | `15_9-F-8` | NORMALIZED | 0.95 | 10 | stages a-d; decided at c_canonical_separators |

### `15/9-F-8 A`

well_code `15/9-F-8`, sidetrack_code `A` — 1 identities

| source_system | source_identifier | match_method | conf. | seen | evidence |
|---|---|---|---:|---:|---|
| `TRAJ` | `15_9-F-8 A` | NORMALIZED | 0.95 | 1 | stages a-d; decided at d_split_sidetrack |

### `15/9-F-9`

well_code `15/9-F-9`, no sidetrack (original hole) — 5 identities

| source_system | source_identifier | match_method | conf. | seen | evidence |
|---|---|---|---:|---:|---|
| `DDR` | `15/9-F-9` | EXACT | 1.00 | 64 | already canonical; corroborated by NPD_NUMBER 5927 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-9') |
| `DDR` | `15_9_F_9` | NORMALIZED | 0.95 | 96 | stages a-d; decided at c_canonical_separators |
| `DDR` | `5927` | IDENTIFIER | 1.00 | 32 | NPD_NUMBER 5927 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-9') |
| `DDR` | `NO 15/9-F-9` | NORMALIZED | 0.95 | 64 | stages a-d; decided at b_strip_prefixes; corroborated by NPD_NUMBER 5927 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-9') |
| `TRAJ` | `15_9-F-9` | NORMALIZED | 0.95 | 13 | stages a-d; decided at c_canonical_separators |

### `15/9-F-9 A`

well_code `15/9-F-9`, sidetrack_code `A` — 16 identities

| source_system | source_identifier | match_method | conf. | seen | evidence |
|---|---|---|---:|---:|---|
| `ARCHIVE` | `Norway-NA-15_$47$_9-F-9 A` | NORMALIZED | 0.95 | 8 | stages a-d; decided at d_split_sidetrack |
| `DDR` | `15/9-F-9 A` | EXACT | 1.00 | 56 | already canonical; corroborated by NPD_NUMBER 6163 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-9 A') |
| `DDR` | `15_9_F_9_A` | NORMALIZED | 0.95 | 84 | stages a-d; decided at d_split_sidetrack |
| `DDR` | `6163` | IDENTIFIER | 1.00 | 28 | NPD_NUMBER 6163 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-9 A') |
| `DDR` | `NO 15/9-F-9 A` | NORMALIZED | 0.95 | 56 | stages a-d; decided at d_split_sidetrack; corroborated by NPD_NUMBER 6163 (from DDR NPD_CODE_WELL\|NPD_CODE_WELLBORE '15/9-F-9 A') |
| `TRAJ` | `15/9-F-9 A` | EXACT | 1.00 | 2 | already canonical; corroborated by W_NUMBER W-986464 (from TRAJ XML_NAME_WELL '15/9-F-9 A') |
| `TRAJ` | `15/9-F-9 A - Main Wellbore` | NORMALIZED | 0.90 | 2 | WITSML 'Main Wellbore' descriptor: the original hole of well 15/9-F-9 A; corroborated by B_NUMBER B-986464 (from TRAJ XML_NAME_WELLBORE '15/9-F-9 A - Main Wellbore') |
| `TRAJ` | `15_9-F-9 A` | NORMALIZED | 0.95 | 4 | stages a-d; decided at d_split_sidetrack |
| `TRAJ` | `B-986464` | IDENTIFIER | 1.00 | 2 | B_NUMBER B-986464 (from TRAJ XML_NAME_WELLBORE '15/9-F-9 A - Main Wellbore') |
| `TRAJ` | `Norway-NA-15_$47$_9-F-9 A` | NORMALIZED | 0.95 | 3 | stages a-d; decided at d_split_sidetrack |
| `TRAJ` | `W-986464` | IDENTIFIER | 1.00 | 2 | W_NUMBER W-986464 (from TRAJ XML_NAME_WELL '15/9-F-9 A') |
| `WITSML` | `15/9-F-9 A` | EXACT | 1.00 | 2 | already canonical; corroborated by W_NUMBER W-986464 (from TRAJ XML_NAME_WELL '15/9-F-9 A') |
| `WITSML` | `15/9-F-9 A - Main Wellbore` | NORMALIZED | 0.90 | 1 | WITSML 'Main Wellbore' descriptor: the original hole of well 15/9-F-9 A; corroborated by B_NUMBER B-986464 (from TRAJ XML_NAME_WELLBORE '15/9-F-9 A - Main Wellbore') |
| `WITSML` | `B-986464` | IDENTIFIER | 1.00 | 1 | B_NUMBER B-986464 (from TRAJ XML_NAME_WELLBORE '15/9-F-9 A - Main Wellbore') |
| `WITSML` | `Norway-NA-15_$47$_9-F-9 A` | NORMALIZED | 0.95 | 5 | stages a-d; decided at d_split_sidetrack |
| `WITSML` | `W-986464` | IDENTIFIER | 1.00 | 2 | W_NUMBER W-986464 (from TRAJ XML_NAME_WELL '15/9-F-9 A') |

## 3. Official identifiers

What each identifier was found to name, and where that was learnt.

| Identifier | Names wellbore |
|---|---|
| `B_NUMBER B-353084` | `15/9-F-12` |
| `B_NUMBER B-353085` | `15/9-F-14` |
| `B_NUMBER B-744206` | `15/9-F-15 S` |
| `B_NUMBER B-826806` | `15/9-F-15` |
| `B_NUMBER B-854763` | `15/9-F-15 B` |
| `B_NUMBER B-861401` | `15/9-F-15 A` |
| `B_NUMBER B-924688` | `15/9-F-10` |
| `B_NUMBER B-986464` | `15/9-F-9 A` |
| `NPD_NUMBER 2043` | `15/9-19 S` |
| `NPD_NUMBER 3145` | `15/9-19 A` |
| `NPD_NUMBER 3251` | `15/9-19 B` |
| `NPD_NUMBER 5351` | `15/9-F-14` |
| `NPD_NUMBER 5599` | `15/9-F-12` |
| `NPD_NUMBER 5610` | `15/9-F-7` |
| `NPD_NUMBER 5693` | `15/9-F-4` |
| `NPD_NUMBER 5769` | `15/9-F-5` |
| `NPD_NUMBER 5785` | `15/9-F-15 A` |
| `NPD_NUMBER 5794` | `15/9-F-15 C` |
| `NPD_NUMBER 5927` | `15/9-F-9` |
| `NPD_NUMBER 6046` | `15/9-F-15 B` |
| `NPD_NUMBER 6099` | `15/9-F-10` |
| `NPD_NUMBER 6163` | `15/9-F-9 A` |
| `NPD_NUMBER 6184` | `15/9-F-15` |
| `NPD_NUMBER 7078` | `15/9-F-11` |
| `NPD_NUMBER 7079` | `15/9-F-11 A` |
| `NPD_NUMBER 7080` | `15/9-F-11 B` |
| `NPD_NUMBER 7223` | `15/9-F-1` |
| `NPD_NUMBER 7224` | `15/9-F-1 A` |
| `NPD_NUMBER 7264` | `15/9-F-1 B` |
| `NPD_NUMBER 7289` | `15/9-F-15 D` |
| `NPD_NUMBER 7405` | `15/9-F-1 C` |
| `UUID 05fb8aee-3461-4071-8ac5-975b9bb5cc4f` | `15/9-F-14` |
| `UUID 97debbde-fcef-4ad2-ad00-6205300609fa` | `15/9-F-12` |
| `UUID 9ab4989d-11c6-4ac1-83c1-e74362292dd8` | `15/9-F-15 C` |
| `UUID a82580d7-d94f-4e5a-9a04-be8bcae02998` | `15/9-F-12` |
| `UUID cf870b7d-087b-4797-b000-4968e9f1beaf` | `15/9-F-14` |
| `UUID dd19bf7b-02a7-4383-9038-ce201cee4d91` | `15/9-F-15` |
| `UUID e0cab46e-aa2a-4d69-b466-108dafd4ae62` | `15/9-F-15 D` |
| `W_NUMBER W-353084` | `15/9-F-12` |
| `W_NUMBER W-353085` | `15/9-F-14` |
| `W_NUMBER W-744206` | `15/9-F-15 S` |
| `W_NUMBER W-826806` | `15/9-F-15` |
| `W_NUMBER W-854763` | `15/9-F-15 B` |
| `W_NUMBER W-861401` | `15/9-F-15 A` |
| `W_NUMBER W-924688` | `15/9-F-10` |
| `W_NUMBER W-986464` | `15/9-F-9 A` |

No identifier was found naming two different wellbores.

## 4. Unresolved

`silver.wellbore_identity_unresolved`. These are kept, counted, and reported.
Guessing any of them would attribute data to the wrong hole, which is worse
than a gap because it looks like an answer.

### IDENTIFIER_WITHOUT_A_NAME — 1

an official identifier that no source in this dataset ever paired with a name. The wellbore is real; nothing here says which one it is.

| source_system | source_identifier | seen | why |
|---|---|---:|---|
| `WITSML` | `B-782511` | 1 | no_block_and_quadrant |

### NEEDS_ASSUMED_BLOCK — 4

resolvable only by assuming the block and quadrant the name omits, and no source that stated its own block knows the result.

| source_system | source_identifier | seen | why |
|---|---|---:|---|
| `SIM` | `F-1CW` | 1 | simulator well name normalises to '15/9-F-1 CW' only after assuming block 15/9, and no source that names its own block knows that wellbore |
| `SIM` | `I-F4G` | 2 | simulator injector name normalises to '15/9-F-4 G' only after assuming block 15/9, and no source that names its own block knows that wellbore |
| `SIM` | `PIL-N` | 2 | simulator well name: no_well_number even after assuming block 15/9 |
| `SIM` | `PIL-NW` | 2 | simulator well name: no_well_number even after assuming block 15/9 |

### NOT_A_WELL_NAME — 36

the string does not name a wellbore at all — a delivery folder, a planned location, a document title, or a placeholder value.

| source_system | source_identifier | seen | why |
|---|---|---:|---|
| `ARCHIVE` | `Volve_Production_data` | 2 | no_block_and_quadrant |
| `ARCHIVE` | `Volve_Reports` | 3 | no_block_and_quadrant |
| `ARCHIVE` | `Volve_Reservoir_Model-Eclipse_model` | 65 | no_block_and_quadrant |
| `ARCHIVE` | `Volve_Seismic_VSP` | 48 | no_block_and_quadrant |
| `ARCHIVE` | `Volve_Well_technical_data` | 5480 | no_block_and_quadrant |
| `DDR` | `Well_technical_data` | 5277 | no_block_and_quadrant |
| `DOC` | `Reports` | 3 | no_block_and_quadrant |
| `DOC` | `VSP` | 2 | no_block_and_quadrant |
| `DOC` | `Well_technical_data` | 20 | no_block_and_quadrant |
| `LOG` | `08SCA0059` | 13 | no_block_and_quadrant |
| `LOG` | `999999999999` | 4 | no_block_and_quadrant |
| `PROD` | `Production_data` | 2 | no_block_and_quadrant |
| `SIM` | `Reservoir_Model-Eclipse_model` | 65 | no_block_and_quadrant |
| `TRAJ` | `F-1 A  Northwest Injector 9 58 csg.shoe` | 1 | no_block_and_quadrant |
| `TRAJ` | `F-1 A Northwest Injector 9 58 csg. shoe` | 1 | no_block_and_quadrant |
| `TRAJ` | `F-1 A Nortwest Injector 9 58 csg. shoe` | 1 | no_block_and_quadrant |
| `TRAJ` | `F-1 B 9 58 csg.shoe` | 2 | no_block_and_quadrant |
| `TRAJ` | `F-1 C` | 2 | no_block_and_quadrant |
| `TRAJ` | `F-1 North Upside Pilot 13 38 csg. shoe` | 2 | no_block_and_quadrant |
| `TRAJ` | `F-1 North Upside Pilot 13 38 csg.shoe` | 1 | no_block_and_quadrant |
| `TRAJ` | `F-12` | 2 | no_block_and_quadrant |
| `TRAJ` | `F-15 C Top Reservoir Intersection` | 1 | no_block_and_quadrant |
| `TRAJ` | `F-15 C Top Resevoir Intersection` | 1 | no_block_and_quadrant |
| `TRAJ` | `F-15 D` | 4 | no_block_and_quadrant |
| `TRAJ` | `Relief well 1049m West` | 2 | no_block_and_quadrant |
| `TRAJ` | `Relief well 1352m South` | 2 | no_block_and_quadrant |
| `TRAJ` | `Relief well 508m West` | 2 | no_block_and_quadrant |
| `TRAJ` | `Relief well 966m North` | 2 | no_block_and_quadrant |
| `TRAJ` | `Relief well location 1` | 4 | no_block_and_quadrant |
| `TRAJ` | `Relief well location 2` | 3 | no_block_and_quadrant |
| `TRAJ` | `Relief well location 3` | 6 | no_block_and_quadrant |
| `TRAJ` | `Relief well location 4` | 5 | no_block_and_quadrant |
| `TRAJ` | `Relief well location 5` | 5 | no_block_and_quadrant |
| `TRAJ` | `Well_technical_data` | 168 | no_block_and_quadrant |
| `UNCLASSIFIED` | `Well_technical_data` | 15 | no_block_and_quadrant |
| `VSP` | `VSP` | 46 | no_block_and_quadrant |

### SUFFIX_NOT_A_SIDETRACK — 1

a well name whose trailing text is not a sidetrack code. Resolving it needs an official identifier from the source, or a manual decision.

| source_system | source_identifier | seen | why |
|---|---|---:|---|
| `WITSML` | `17 1/2" Final QAQCd Data` | 1 | unrecognised_suffix:" FINAL QAQCD DATA |

## 5. What would settle the unresolved ones

| Category | Identities | Settled by |
|---|---:|---|
| `IDENTIFIER_WITHOUT_A_NAME` | 1 | a source that pairs the identifier with a name — the Sodir FactPages `REF` source would do it for NPD numbers |
| `NEEDS_ASSUMED_BLOCK` | 4 | a manual mapping, if someone who knows the model can confirm it |
| `NOT_A_WELL_NAME` | 36 | nothing. These are not wellbores and should stay out of `dim_wellbore`; they are listed so the count is honest |
| `SUFFIX_NOT_A_SIDETRACK` | 1 | an official identifier, or a manual mapping |

The procedure for adding a resolution by hand is to append a row to
`data/_inventory/identity-manual-mapping.csv` with a reason; it is read
ahead of every rule, and shows up as `match_method = MANUAL`.

