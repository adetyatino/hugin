# Volve archive inventory

Generated 2026-08-12T22:29:31 from `C:\Apply Kerja\DE\volve`.

The archive folder is read-only by policy: nothing in it was written, renamed,
moved or deleted. Every output lives in this repository.

Folder and file names inside the archives are treated as **data**, not labels.
Every name this pipeline had to change is recorded in
`data/_inventory/name-mapping.csv` with its original alongside it.

## 1. Archive summary

| Archive | Source code | Entries | Dominant ext | Compressed | Uncompressed | Status |
|---|---|---:|---|---:|---:|---|
| `15_9-F-11.zip` | MIXED: DOC, LOG | 29 | `.pdf` (48.3%) | 78.8 MB | 166.5 MB | extracted |
| `15_9-F-12.zip` | MIXED: DOC, LOG | 250 | `.dlis` (48.8%) | 262.3 MB | 595.6 MB | extracted |
| `15_9-F-14.zip` | MIXED: DOC, LOG | 234 | `.dlis` (44.4%) | 439.4 MB | 912.1 MB | extracted |
| `15_9-F-15 A.zip` | MIXED: DOC, LOG, VSP | 129 | `.pdf` (27.9%) | 324.7 MB | 481.9 MB | extracted |
| `15_9-F-15 B.zip` | MIXED: DOC, LOG | 51 | `.pdf` (33.3%) | 75.1 MB | 113.9 MB | extracted |
| `15_9-F-15 C.zip` | MIXED: DOC, LOG | 92 | `.pdf` (40.2%) | 243.0 MB | 402.0 MB | extracted |
| `15_9-F-15 D.zip` | MIXED: DOC, LOG | 76 | `.pdf` (44.7%) | 205.9 MB | 687.1 MB | extracted |
| `15_9-F-15.zip` | MIXED: DOC, LOG | 109 | `.pdf` (43.1%) | 472.2 MB | 616.4 MB | extracted |
| `Norway-NA-15_$47$_9-F-9 A.zip` | MIXED: TRAJ, WITSML | 8 | `.xml` (50.0%) | 10.0 KB | 92.8 KB | extracted |
| `Norway-Statoil-15_$47$_9-F-12.zip` | MIXED: TRAJ, WITSML | 15 | `.xml` (66.7%) | 100.3 KB | 1.5 MB | extracted |
| `Norway-Statoil-NO 15_$47$_9-F-12.zip` | MIXED: TRAJ, WITSML | 694 | `.xml` (98.7%) | 369.3 KB | 952.5 KB | extracted |
| `Norway-Statoil-NO 15_$47$_9-F-14.zip` | MIXED: TRAJ, WITSML | 609 | `.xml` (98.4%) | 309.2 KB | 703.7 KB | extracted |
| `Norway-Statoil-NO 15_$47$_9-F-15.zip` | MIXED: TRAJ, WITSML | 2817 | `.xml` (99.3%) | 1.5 MB | 3.7 MB | extracted |
| `Norway-StatoilHydro-15_$47$_9-F-10.zip` | MIXED: TRAJ, WITSML | 12 | `.xml` (58.3%) | 83.2 KB | 1.6 MB | extracted |
| `Norway-StatoilHydro-15_$47$_9-F-14.zip` | MIXED: TRAJ, WITSML | 15 | `.xml` (53.3%) | 36.0 KB | 538.0 KB | extracted |
| `Norway-StatoilHydro-15_$47$_9-F-15.zip` | MIXED: TRAJ, WITSML | 9 | `.txt` (55.6%) | 26.0 KB | 392.5 KB | extracted |
| `Norway-StatoilHydro-15_$47$_9-F-15A.zip` | MIXED: TRAJ, WITSML | 9 | `.txt` (55.6%) | 21.6 KB | 362.1 KB | extracted |
| `Norway-StatoilHydro-15_$47$_9-F-15B.zip` | MIXED: TRAJ, WITSML | 8 | `.txt` (62.5%) | 12.3 KB | 211.7 KB | extracted |
| `Norway-StatoilHydro-15_$47$_9-F-15S.zip` | MIXED: TRAJ, WITSML | 9 | `.txt` (55.6%) | 24.0 KB | 388.6 KB | extracted |
| `Volve_Production_data.zip` | PROD | 3 | `.txt` (50.0%) | 1.9 MB | 2.2 MB | extracted |
| `Volve_Reports.zip` | DOC | 4 | `.pdf` (66.7%) | 161.6 MB | 178.6 MB | extracted |
| `Volve_Reservoir_Model-Eclipse_model.zip` | SIM | 67 | `<noext>` (23.1%) | 390.4 MB | 1.6 GB | extracted |
| `Volve_Seismic_VSP.zip` | MIXED: DOC, VSP | 53 | `.segy` (70.8%) | 95.3 MB | 118.4 MB | extracted |
| `Volve_Well_technical_data.zip` | MIXED: DDR, DOC, TRAJ | 5568 | `.pdf` (33.4%) | 210.4 MB | 391.2 MB | extracted |

### Structural facts

Directory counts are given twice on purpose. Most of these archives carry no
directory entries at all — the tree exists only as slashes inside file names —
so the first column reads 0 for an archive that is plainly five levels deep.
The second column counts the directories those file paths imply.

| Archive | Dir entries | Dirs implied by paths | Max depth | Longest path | UTF-8 flag |
|---|---:|---:|---:|---:|---|
| `15_9-F-11.zip` | 0 | 6 | 3 | 98 chars | all entries |
| `15_9-F-12.zip` | 0 | 17 | 4 | 86 chars | all entries |
| `15_9-F-14.zip` | 0 | 20 | 5 | 109 chars | all entries |
| `15_9-F-15 A.zip` | 0 | 10 | 4 | 81 chars | all entries |
| `15_9-F-15 B.zip` | 0 | 9 | 4 | 86 chars | all entries |
| `15_9-F-15 C.zip` | 0 | 13 | 4 | 86 chars | all entries |
| `15_9-F-15 D.zip` | 0 | 8 | 4 | 88 chars | all entries |
| `15_9-F-15.zip` | 0 | 11 | 4 | 116 chars | all entries |
| `Norway-NA-15_$47$_9-F-9 A.zip` | 0 | 7 | 5 | 94 chars | all entries |
| `Norway-Statoil-15_$47$_9-F-12.zip` | 0 | 8 | 5 | 97 chars | all entries |
| `Norway-Statoil-NO 15_$47$_9-F-12.zip` | 0 | 12 | 5 | 115 chars | all entries |
| `Norway-Statoil-NO 15_$47$_9-F-14.zip` | 0 | 13 | 5 | 115 chars | all entries |
| `Norway-Statoil-NO 15_$47$_9-F-15.zip` | 0 | 25 | 5 | 117 chars | all entries |
| `Norway-StatoilHydro-15_$47$_9-F-10.zip` | 0 | 8 | 5 | 102 chars | all entries |
| `Norway-StatoilHydro-15_$47$_9-F-14.zip` | 0 | 12 | 5 | 106 chars | all entries |
| `Norway-StatoilHydro-15_$47$_9-F-15.zip` | 0 | 8 | 5 | 102 chars | all entries |
| `Norway-StatoilHydro-15_$47$_9-F-15A.zip` | 0 | 8 | 5 | 104 chars | all entries |
| `Norway-StatoilHydro-15_$47$_9-F-15B.zip` | 0 | 8 | 5 | 104 chars | all entries |
| `Norway-StatoilHydro-15_$47$_9-F-15S.zip` | 0 | 8 | 5 | 104 chars | all entries |
| `Volve_Production_data.zip` | 1 | 1 | 2 | 42 chars | no entries (cp437) |
| `Volve_Reports.zip` | 1 | 1 | 2 | 28 chars | no entries (cp437) |
| `Volve_Reservoir_Model-Eclipse_model.zip` | 2 | 2 | 3 | 125 chars | no entries (cp437) |
| `Volve_Seismic_VSP.zip` | 5 | 5 | 4 | 78 chars | no entries (cp437) |
| `Volve_Well_technical_data.zip` | 88 | 88 | 5 | 215 chars | 3 of 5568 entries |

### Per-subdirectory codes for mixed archives

**`15_9-F-11.zip`**

| Subdirectory | Code | Files | Confidence | Leading evidence |
|---|---|---:|---|---|
| `01.MUD_LOG` | LOG | 3 | high | 66.7% of entries carry well-log extensions (2/3) |
| `02.LWD_EWL` | LOG | 10 | high | 90.0% of entries carry well-log extensions (9/10) |
| `04.COMPOSITE` | LOG | 4 | high | 50.0% of entries carry well-log extensions (2/4) |
| `05.PETROPHYSICAL INTERPRETATION` | LOG | 3 | high | 66.7% of entries carry well-log extensions (2/3) |
| `14.DIV.REPORTS` | DOC | 9 | high | 100.0% of entries are documents (9/9) |

**`15_9-F-12.zip`**

| Subdirectory | Code | Files | Confidence | Leading evidence |
|---|---|---:|---|---|
| `01.MUD_LOG` | LOG | 7 | high | 14.3% of entries carry well-log extensions (1/7) |
| `02.LWD_EWL` | LOG | 65 | high | 98.5% of entries carry well-log extensions (64/65) |
| `03.PRESSURE` | DOC | 4 | high | 50.0% of entries are documents (2/4) |
| `04.COMPOSITE` | LOG | 4 | high | 50.0% of entries carry well-log extensions (2/4) |
| `05.PETROPHYSICAL INTERPRETATION` | LOG | 7 | high | 57.1% of entries carry well-log extensions (4/7) |
| `07.IMAGE` | LOG | 12 | high | 91.7% of entries carry well-log extensions (11/12) |
| `10.PRODUCTION LOGS/PLT March 2009` | DOC | 2 | medium | 50.0% of entries are documents (1/2) |
| `10.PRODUCTION LOGS/PLT Sept 2010` | LOG | 4 | high | 75.0% of entries carry well-log extensions (3/4) |
| `10.PRODUCTION LOGS/RAW` | LOG | 128 | high | 96.9% of entries carry well-log extensions (124/128) |
| `11. INTEGRITY LOGS` | LOG | 5 | high | 60.0% of entries carry well-log extensions (3/5) |
| `12.BIOSTRAT` | DOC | 2 | high | 50.0% of entries are documents (1/2) |
| `13.GEOCHEM` | DOC | 1 | high | 100.0% of entries are documents (1/1) |
| `14.DIV.REPORTS` | DOC | 9 | high | 100.0% of entries are documents (9/9) |

**`15_9-F-14.zip`**

| Subdirectory | Code | Files | Confidence | Leading evidence |
|---|---|---:|---|---|
| `01.MUD_LOG` | LOG | 7 | high | 14.3% of entries carry well-log extensions (1/7) |
| `02.LWD_EWL` | LOG | 61 | high | 88.5% of entries carry well-log extensions (54/61) |
| `03.PRESSURE` | LOG | 16 | high | 93.8% of entries carry well-log extensions (15/16) |
| `04.COMPOSITE` | LOG | 4 | high | 50.0% of entries carry well-log extensions (2/4) |
| `05.PETROPHYSICAL INTERPRETATION` | LOG | 6 | high | 66.7% of entries carry well-log extensions (4/6) |
| `07.IMAGE` | LOG | 14 | medium | 42.9% of entries carry well-log extensions (6/14) |
| `10.PRODUCTION LOGS/PLT March 2009` | DOC | 3 | medium | 33.3% of entries are documents (1/3) |
| `10.PRODUCTION LOGS/PLT_RST Sept 2010` | LOG | 7 | high | 71.4% of entries carry well-log extensions (5/7) |
| `10.PRODUCTION LOGS/RAW` | LOG | 105 | high | 96.2% of entries carry well-log extensions (101/105) |
| `12.BIOSTRAT` | DOC | 2 | medium | 50.0% of entries are documents (1/2) |
| `14.DIV.REPORTS` | DOC | 9 | high | 100.0% of entries are documents (9/9) |

**`15_9-F-15 A.zip`**

| Subdirectory | Code | Files | Confidence | Leading evidence |
|---|---|---:|---|---|
| `01.MUD_LOG` | LOG | 7 | high | 14.3% of entries carry well-log extensions (1/7) |
| `02.LWD_EWL` | LOG | 38 | high | 50.0% of entries carry well-log extensions (19/38) |
| `03.PRESSURE` | LOG | 11 | high | 90.9% of entries carry well-log extensions (10/11) |
| `04.COMPOSITE` | LOG | 4 | high | 50.0% of entries carry well-log extensions (2/4) |
| `05.PETROPHYSICAL INTERPRETATION` | LOG | 6 | high | 66.7% of entries carry well-log extensions (4/6) |
| `08.VSP_VELOCITY` | VSP | 57 | high | 59.6% SEG-Y entries, all under a VSP/checkshot path (34/57) |
| `12.BIOSTRAT` | DOC | 2 | medium | 50.0% of entries are documents (1/2) |
| `14.DIV.REPORTS` | DOC | 4 | high | 100.0% of entries are documents (4/4) |

**`15_9-F-15 B.zip`**

| Subdirectory | Code | Files | Confidence | Leading evidence |
|---|---|---:|---|---|
| `01.MUD_LOG` | LOG | 7 | high | 14.3% of entries carry well-log extensions (1/7) |
| `02.LWD_EWL` | LOG | 22 | high | 86.4% of entries carry well-log extensions (19/22) |
| `03.PRESSURE` | LOG | 6 | high | 83.3% of entries carry well-log extensions (5/6) |
| `04.COMPOSITE` | LOG | 4 | high | 50.0% of entries carry well-log extensions (2/4) |
| `05.PETROPHYSICAL INTERPRETATION` | LOG | 6 | high | 66.7% of entries carry well-log extensions (4/6) |
| `12.BIOSTRAT` | DOC | 2 | medium | 50.0% of entries are documents (1/2) |
| `14.DIV.REPORTS` | DOC | 4 | high | 75.0% of entries are documents (3/4) |

**`15_9-F-15 C.zip`**

| Subdirectory | Code | Files | Confidence | Leading evidence |
|---|---|---:|---|---|
| `01.MUD_LOG` | LOG | 7 | high | 14.3% of entries carry well-log extensions (1/7) |
| `02.LWD_EWL` | LOG | 34 | high | 52.9% of entries carry well-log extensions (18/34) |
| `03.PRESSURE` | LOG | 10 | high | 90.0% of entries carry well-log extensions (9/10) |
| `04.COMPOSITE` | LOG | 4 | high | 50.0% of entries carry well-log extensions (2/4) |
| `05.PETROPHYSICAL INTERPRETATION` | LOG | 6 | high | 66.7% of entries carry well-log extensions (4/6) |
| `10.PRODUCTION LOGS` | LOG | 18 | high | 83.3% of entries carry well-log extensions (15/18) |
| `11. INTEGRITY LOGS` | LOG | 6 | high | 66.7% of entries carry well-log extensions (4/6) |
| `12.BIOSTRAT` | LOG | 2 | high | 50.0% of entries carry well-log extensions (1/2) |
| `14.DIV.REPORTS` | DOC | 5 | high | 100.0% of entries are documents (5/5) |

**`15_9-F-15 D.zip`**

| Subdirectory | Code | Files | Confidence | Leading evidence |
|---|---|---:|---|---|
| `01.MUD_LOG` | LOG | 8 | high | 25.0% of entries carry well-log extensions (2/8) |
| `02.LWD_EWL` | LOG | 25 | high | 52.0% of entries carry well-log extensions (13/25) |
| `04.COMPOSITE` | LOG | 4 | high | 50.0% of entries carry well-log extensions (2/4) |
| `05.PETROPHYSICAL INTERPRETATION` | LOG | 4 | high | 75.0% of entries carry well-log extensions (3/4) |
| `10.PRODUCTION LOGS` | LOG | 21 | high | 90.5% of entries carry well-log extensions (19/21) |
| `14.DIV.REPORTS` | DOC | 14 | high | 85.7% of entries are documents (12/14) |

**`15_9-F-15.zip`**

| Subdirectory | Code | Files | Confidence | Leading evidence |
|---|---|---:|---|---|
| `01.MUD_LOG` | LOG | 7 | high | 14.3% of entries carry well-log extensions (1/7) |
| `02.LWD_EWL` | LOG | 58 | high | 56.9% of entries carry well-log extensions (33/58) |
| `03.PRESSURE` | LOG | 4 | high | 75.0% of entries carry well-log extensions (3/4) |
| `04.COMPOSITE` | LOG | 4 | high | 50.0% of entries carry well-log extensions (2/4) |
| `05.PETROPHYSICAL INTERPRETATION` | LOG | 5 | high | 60.0% of entries carry well-log extensions (3/5) |
| `12.BIOSTRAT` | DOC | 2 | medium | 50.0% of entries are documents (1/2) |
| `13.GEOCHEM` | LOG | 18 | medium | 33.3% of entries carry well-log extensions (6/18) |
| `14.DIV.REPORTS` | DOC | 11 | high | 90.9% of entries are documents (10/11) |

**`Norway-NA-15_$47$_9-F-9 A.zip`**

| Subdirectory | Code | Files | Confidence | Leading evidence |
|---|---|---:|---|---|
| `.` | WITSML | 1 | high | 100.0% of entries are WITSML export manifests (1/1) |
| `1/_wellboreInfo` | WITSML | 1 | high | 100.0% of entries sit in WITSML object subtrees (1/1) |
| `1/log` | WITSML | 2 | high | 100.0% of entries sit in WITSML object subtrees (2/2) |
| `1/trajectory` | TRAJ | 3 | high | 100.0% of entries sit in a WITSML trajectory/ subtree (3/3) |
| `_wellInfo` | WITSML | 1 | high | 100.0% of entries sit in WITSML object subtrees (1/1) |

**`Norway-Statoil-15_$47$_9-F-12.zip`**

| Subdirectory | Code | Files | Confidence | Leading evidence |
|---|---|---:|---|---|
| `.` | WITSML | 1 | high | 100.0% of entries are WITSML export manifests (1/1) |
| `1/_wellboreInfo` | WITSML | 1 | high | 100.0% of entries sit in WITSML object subtrees (1/1) |
| `1/log` | WITSML | 3 | high | 100.0% of entries sit in WITSML object subtrees (3/3) |
| `1/trajectory` | TRAJ | 9 | high | 100.0% of entries sit in a WITSML trajectory/ subtree (9/9) |
| `_wellInfo` | WITSML | 1 | high | 100.0% of entries sit in WITSML object subtrees (1/1) |

**`Norway-Statoil-NO 15_$47$_9-F-12.zip`**

| Subdirectory | Code | Files | Confidence | Leading evidence |
|---|---|---:|---|---|
| `.` | WITSML | 1 | high | 100.0% of entries are WITSML export manifests (1/1) |
| `1/_wellboreInfo` | WITSML | 1 | high | 100.0% of entries sit in WITSML object subtrees (1/1) |
| `1/bhaRun` | WITSML | 11 | high | 100.0% of entries sit in WITSML object subtrees (11/11) |
| `1/log` | WITSML | 2 | high | 100.0% of entries sit in WITSML object subtrees (2/2) |
| `1/message` | WITSML | 660 | high | 100.0% of entries sit in WITSML object subtrees (660/660) |
| `1/rig` | WITSML | 2 | high | 100.0% of entries sit in WITSML object subtrees (2/2) |
| `1/trajectory` | TRAJ | 2 | high | 100.0% of entries sit in a WITSML trajectory/ subtree (2/2) |
| `1/tubular` | WITSML | 10 | high | 100.0% of entries sit in WITSML object subtrees (10/10) |
| `1/wbGeometry` | WITSML | 4 | high | 100.0% of entries sit in WITSML object subtrees (4/4) |
| `_wellInfo` | WITSML | 1 | high | 100.0% of entries sit in WITSML object subtrees (1/1) |

**`Norway-Statoil-NO 15_$47$_9-F-14.zip`**

| Subdirectory | Code | Files | Confidence | Leading evidence |
|---|---|---:|---|---|
| `.` | WITSML | 1 | high | 100.0% of entries are WITSML export manifests (1/1) |
| `1/_wellboreInfo` | WITSML | 1 | high | 100.0% of entries sit in WITSML object subtrees (1/1) |
| `1/bhaRun` | WITSML | 8 | high | 100.0% of entries sit in WITSML object subtrees (8/8) |
| `1/log` | WITSML | 3 | high | 100.0% of entries sit in WITSML object subtrees (3/3) |
| `1/message` | WITSML | 581 | high | 100.0% of entries sit in WITSML object subtrees (581/581) |
| `1/rig` | WITSML | 2 | high | 100.0% of entries sit in WITSML object subtrees (2/2) |
| `1/trajectory` | TRAJ | 2 | high | 100.0% of entries sit in a WITSML trajectory/ subtree (2/2) |
| `1/tubular` | WITSML | 7 | high | 100.0% of entries sit in WITSML object subtrees (7/7) |
| `1/wbGeometry` | WITSML | 3 | high | 100.0% of entries sit in WITSML object subtrees (3/3) |
| `_wellInfo` | WITSML | 1 | high | 100.0% of entries sit in WITSML object subtrees (1/1) |

**`Norway-Statoil-NO 15_$47$_9-F-15.zip`**

| Subdirectory | Code | Files | Confidence | Leading evidence |
|---|---|---:|---|---|
| `.` | WITSML | 1 | high | 100.0% of entries are WITSML export manifests (1/1) |
| `1/_wellboreInfo` | WITSML | 1 | high | 100.0% of entries sit in WITSML object subtrees (1/1) |
| `1/bhaRun` | WITSML | 15 | high | 100.0% of entries sit in WITSML object subtrees (15/15) |
| `1/log` | WITSML | 3 | high | 100.0% of entries sit in WITSML object subtrees (3/3) |
| `1/message` | WITSML | 502 | high | 100.0% of entries sit in WITSML object subtrees (502/502) |
| `1/rig` | WITSML | 2 | high | 100.0% of entries sit in WITSML object subtrees (2/2) |
| `1/trajectory` | TRAJ | 2 | high | 100.0% of entries sit in a WITSML trajectory/ subtree (2/2) |
| `1/tubular` | WITSML | 15 | high | 100.0% of entries sit in WITSML object subtrees (15/15) |
| `1/wbGeometry` | WITSML | 2 | high | 100.0% of entries sit in WITSML object subtrees (2/2) |
| `2/_wellboreInfo` | WITSML | 1 | high | 100.0% of entries sit in WITSML object subtrees (1/1) |
| `2/bhaRun` | WITSML | 17 | high | 100.0% of entries sit in WITSML object subtrees (17/17) |
| `2/log` | WITSML | 3 | high | 100.0% of entries sit in WITSML object subtrees (3/3) |
| `2/message` | WITSML | 2205 | high | 100.0% of entries sit in WITSML object subtrees (2205/2205) |
| `2/mudLog` | WITSML | 2 | high | 100.0% of entries sit in WITSML object subtrees (2/2) |
| `2/rig` | WITSML | 3 | high | 100.0% of entries sit in WITSML object subtrees (3/3) |
| `2/trajectory` | TRAJ | 2 | high | 100.0% of entries sit in a WITSML trajectory/ subtree (2/2) |
| `2/tubular` | WITSML | 37 | high | 100.0% of entries sit in WITSML object subtrees (37/37) |
| `2/wbGeometry` | WITSML | 3 | high | 100.0% of entries sit in WITSML object subtrees (3/3) |
| `_wellInfo` | WITSML | 1 | high | 100.0% of entries sit in WITSML object subtrees (1/1) |

**`Norway-StatoilHydro-15_$47$_9-F-10.zip`**

| Subdirectory | Code | Files | Confidence | Leading evidence |
|---|---|---:|---|---|
| `.` | WITSML | 1 | high | 100.0% of entries are WITSML export manifests (1/1) |
| `1/_wellboreInfo` | WITSML | 1 | high | 100.0% of entries sit in WITSML object subtrees (1/1) |
| `1/log` | WITSML | 3 | high | 100.0% of entries sit in WITSML object subtrees (3/3) |
| `1/trajectory` | TRAJ | 6 | high | 100.0% of entries sit in a WITSML trajectory/ subtree (6/6) |
| `_wellInfo` | WITSML | 1 | high | 100.0% of entries sit in WITSML object subtrees (1/1) |

**`Norway-StatoilHydro-15_$47$_9-F-14.zip`**

| Subdirectory | Code | Files | Confidence | Leading evidence |
|---|---|---:|---|---|
| `.` | WITSML | 1 | high | 100.0% of entries are WITSML export manifests (1/1) |
| `1/_wellboreInfo` | WITSML | 1 | high | 100.0% of entries sit in WITSML object subtrees (1/1) |
| `1/log` | WITSML | 3 | high | 100.0% of entries sit in WITSML object subtrees (3/3) |
| `1/trajectory` | TRAJ | 6 | high | 100.0% of entries sit in a WITSML trajectory/ subtree (6/6) |
| `2` | WITSML | 3 | high | 100.0% of entries sit in WITSML object subtrees (3/3) |
| `_wellInfo` | WITSML | 1 | high | 100.0% of entries sit in WITSML object subtrees (1/1) |

**`Norway-StatoilHydro-15_$47$_9-F-15.zip`**

| Subdirectory | Code | Files | Confidence | Leading evidence |
|---|---|---:|---|---|
| `.` | WITSML | 1 | high | 100.0% of entries are WITSML export manifests (1/1) |
| `1/_wellboreInfo` | WITSML | 1 | high | 100.0% of entries sit in WITSML object subtrees (1/1) |
| `1/log` | WITSML | 3 | high | 100.0% of entries sit in WITSML object subtrees (3/3) |
| `1/trajectory` | TRAJ | 3 | high | 100.0% of entries sit in a WITSML trajectory/ subtree (3/3) |
| `_wellInfo` | WITSML | 1 | high | 100.0% of entries sit in WITSML object subtrees (1/1) |

**`Norway-StatoilHydro-15_$47$_9-F-15A.zip`**

| Subdirectory | Code | Files | Confidence | Leading evidence |
|---|---|---:|---|---|
| `.` | WITSML | 1 | high | 100.0% of entries are WITSML export manifests (1/1) |
| `1/_wellboreInfo` | WITSML | 1 | high | 100.0% of entries sit in WITSML object subtrees (1/1) |
| `1/log` | WITSML | 3 | high | 100.0% of entries sit in WITSML object subtrees (3/3) |
| `1/trajectory` | TRAJ | 3 | high | 100.0% of entries sit in a WITSML trajectory/ subtree (3/3) |
| `_wellInfo` | WITSML | 1 | high | 100.0% of entries sit in WITSML object subtrees (1/1) |

**`Norway-StatoilHydro-15_$47$_9-F-15B.zip`**

| Subdirectory | Code | Files | Confidence | Leading evidence |
|---|---|---:|---|---|
| `.` | WITSML | 1 | high | 100.0% of entries are WITSML export manifests (1/1) |
| `1/_wellboreInfo` | WITSML | 1 | high | 100.0% of entries sit in WITSML object subtrees (1/1) |
| `1/log` | WITSML | 3 | high | 100.0% of entries sit in WITSML object subtrees (3/3) |
| `1/trajectory` | TRAJ | 2 | high | 100.0% of entries sit in a WITSML trajectory/ subtree (2/2) |
| `_wellInfo` | WITSML | 1 | high | 100.0% of entries sit in WITSML object subtrees (1/1) |

**`Norway-StatoilHydro-15_$47$_9-F-15S.zip`**

| Subdirectory | Code | Files | Confidence | Leading evidence |
|---|---|---:|---|---|
| `.` | WITSML | 1 | high | 100.0% of entries are WITSML export manifests (1/1) |
| `1/_wellboreInfo` | WITSML | 1 | high | 100.0% of entries sit in WITSML object subtrees (1/1) |
| `1/log` | WITSML | 3 | high | 100.0% of entries sit in WITSML object subtrees (3/3) |
| `1/trajectory` | TRAJ | 3 | high | 100.0% of entries sit in a WITSML trajectory/ subtree (3/3) |
| `_wellInfo` | WITSML | 1 | high | 100.0% of entries sit in WITSML object subtrees (1/1) |

**`Volve_Seismic_VSP.zip`**

| Subdirectory | Code | Files | Confidence | Leading evidence |
|---|---|---:|---|---|
| `.` | DOC | 2 | medium | 50.0% of entry names look like report/licence documents (1/2) |
| `15_9_F_15A_VSP` | VSP | 41 | high | 82.9% SEG-Y entries, all under a VSP/checkshot path (34/41) |
| `Checkshots` | VSP | 5 | high | 100.0% of entry names contain 'checkshot' (5/5) |

**`Volve_Well_technical_data.zip`**

| Subdirectory | Code | Files | Confidence | Leading evidence |
|---|---|---:|---|---|
| `.` | DOC | 1 | high | 100.0% of entries are documents (1/1) |
| `CasingSeat` | UNCLASSIFIED | 1 | placeholder | all 1 entries are 'left_intentionally_empty' placeholders: the source shipped this folder deliberately empty, so there is no content to classify |
| `CasingWear` | UNCLASSIFIED | 1 | placeholder | all 1 entries are 'left_intentionally_empty' placeholders: the source shipped this folder deliberately empty, so there is no content to classify |
| `Compass` | UNCLASSIFIED | 1 | placeholder | all 1 entries are 'left_intentionally_empty' placeholders: the source shipped this folder deliberately empty, so there is no content to classify |
| `Daily Drilling Report - HTML Version` | DDR | 1759 | high | 100.0% of entries sit under a 'Daily Drilling Report' folder (1759/1759) |
| `Daily Drilling Report - XML Version` | DDR | 1759 | high | 100.0% of entries sit under a 'Daily Drilling Report' folder (1759/1759) |
| `Daily Drilling report - PDF Version` | DDR | 1759 | high | 100.0% of entries sit under a 'Daily Drilling Report' folder (1759/1759) |
| `EDM.XML` | TRAJ | 2 | high | 100.0% of entry names carry a Compass/EDM survey marker (2/2) |
| `Site` | DOC | 2 | medium | 50.0% of entries are documents (1/2) |
| `Site_TemplateSlot` | DOC | 2 | medium | 50.0% of entries are documents (1/2) |
| `StressCheck` | UNCLASSIFIED | 8 | none | no rule matched; extension mix is .sck x8 |
| `WellPlan` | UNCLASSIFIED | 1 | placeholder | all 1 entries are 'left_intentionally_empty' placeholders: the source shipped this folder deliberately empty, so there is no content to classify |
| `WellWellbore/15_9-19/15_9-19 A` | TRAJ | 2 | high | 50.0% of entry names carry a Compass/EDM survey marker (1/2) |
| `WellWellbore/15_9-19/15_9-19 B` | TRAJ | 2 | high | 50.0% of entry names carry a Compass/EDM survey marker (1/2) |
| `WellWellbore/15_9-19/15_9-19 BT2` | TRAJ | 2 | high | 50.0% of entry names carry a Compass/EDM survey marker (1/2) |
| `WellWellbore/15_9-19/15_9-19 S` | TRAJ | 2 | high | 50.0% of entry names carry a Compass/EDM survey marker (1/2) |
| `WellWellbore/15_9-19/15_9-19 SR` | TRAJ | 2 | high | 50.0% of entry names carry a Compass/EDM survey marker (1/2) |
| `WellWellbore/15_9-F-1/15_9-F-1` | TRAJ | 4 | high | 50.0% of entry names carry a Compass/EDM survey marker (2/4) |
| `WellWellbore/15_9-F-1/15_9-F-1 A` | TRAJ | 4 | high | 50.0% of entry names carry a Compass/EDM survey marker (2/4) |
| `WellWellbore/15_9-F-1/15_9-F-1 B` | TRAJ | 4 | high | 50.0% of entry names carry a Compass/EDM survey marker (2/4) |
| `WellWellbore/15_9-F-1/15_9-F-1 C` | TRAJ | 4 | high | 50.0% of entry names carry a Compass/EDM survey marker (2/4) |
| `WellWellbore/15_9-F-10/15_9-F-10` | TRAJ | 4 | high | 50.0% of entry names carry a Compass/EDM survey marker (2/4) |
| `WellWellbore/15_9-F-10/15_9-F-10 A` | TRAJ | 10 | high | 10.0% of entry names carry a Compass/EDM survey marker (1/10) |
| `WellWellbore/15_9-F-11/15_9-F-11` | TRAJ | 4 | high | 50.0% of entry names carry a Compass/EDM survey marker (2/4) |
| `WellWellbore/15_9-F-11/15_9-F-11 A` | TRAJ | 4 | high | 50.0% of entry names carry a Compass/EDM survey marker (2/4) |
| `WellWellbore/15_9-F-11/15_9-F-11 B` | TRAJ | 4 | high | 50.0% of entry names carry a Compass/EDM survey marker (2/4) |
| `WellWellbore/15_9-F-11/15_9-F-11 T2` | TRAJ | 5 | high | 40.0% of entry names carry a Compass/EDM survey marker (2/5) |
| `WellWellbore/15_9-F-11/Relief well 1049m West` | TRAJ | 2 | high | 100.0% of entry names end in a Compass wellpath status (_PLAN/_PROTOTYPE/_ACTUAL/_DEFINITIVE) (2/2) |
| `WellWellbore/15_9-F-11/Relief well 1352m South` | TRAJ | 2 | high | 100.0% of entry names end in a Compass wellpath status (_PLAN/_PROTOTYPE/_ACTUAL/_DEFINITIVE) (2/2) |
| `WellWellbore/15_9-F-11/Relief well 508m West` | TRAJ | 2 | high | 100.0% of entry names end in a Compass wellpath status (_PLAN/_PROTOTYPE/_ACTUAL/_DEFINITIVE) (2/2) |
| `WellWellbore/15_9-F-11/Relief well 966m North` | TRAJ | 2 | high | 100.0% of entry names end in a Compass wellpath status (_PLAN/_PROTOTYPE/_ACTUAL/_DEFINITIVE) (2/2) |
| `WellWellbore/15_9-F-12` | TRAJ | 5 | high | 40.0% of entry names carry a Compass/EDM survey marker (2/5) |
| `WellWellbore/15_9-F-13` | TRAJ | 11 | high | 9.1% of entry names carry a Compass/EDM survey marker (1/11) |
| `WellWellbore/15_9-F-14/15_9-F-14` | TRAJ | 4 | high | 50.0% of entry names carry a Compass/EDM survey marker (2/4) |
| `WellWellbore/15_9-F-14/15_9-F-14 A` | TRAJ | 3 | high | 100.0% of entry names end in a Compass wellpath status (_PLAN/_PROTOTYPE/_ACTUAL/_DEFINITIVE) (3/3) |
| `WellWellbore/15_9-F-15/15_9-F-15` | TRAJ | 2 | high | 50.0% of entry names carry a Compass/EDM survey marker (1/2) |
| `WellWellbore/15_9-F-15/15_9-F-15 A` | TRAJ | 2 | high | 50.0% of entry names carry a Compass/EDM survey marker (1/2) |
| `WellWellbore/15_9-F-15/15_9-F-15 B` | TRAJ | 4 | high | 50.0% of entry names carry a Compass/EDM survey marker (2/4) |
| `WellWellbore/15_9-F-15/15_9-F-15 C` | TRAJ | 2 | high | 50.0% of entry names carry a Compass/EDM survey marker (1/2) |
| `WellWellbore/15_9-F-15/15_9-F-15 D` | TRAJ | 4 | high | 50.0% of entry names carry a Compass/EDM survey marker (2/4) |
| `WellWellbore/15_9-F-2` | TRAJ | 10 | high | 10.0% of entry names carry a Compass/EDM survey marker (1/10) |
| `WellWellbore/15_9-F-3` | TRAJ | 7 | high | 14.3% of entry names carry a Compass/EDM survey marker (1/7) |
| `WellWellbore/15_9-F-4` | TRAJ | 6 | high | 33.3% of entry names carry a Compass/EDM survey marker (2/6) |
| `WellWellbore/15_9-F-5` | TRAJ | 5 | high | 40.0% of entry names carry a Compass/EDM survey marker (2/5) |
| `WellWellbore/15_9-F-6` | DOC | 1 | high | 100.0% of entries are documents (1/1) |
| `WellWellbore/15_9-F-7` | TRAJ | 5 | high | 40.0% of entry names carry a Compass/EDM survey marker (2/5) |
| `WellWellbore/15_9-F-8/15_9-F-8` | TRAJ | 4 | high | 25.0% of entry names carry a Compass/EDM survey marker (1/4) |
| `WellWellbore/15_9-F-8/15_9-F-8 A` | TRAJ | 1 | high | 100.0% of entry names end in a Compass wellpath status (_PLAN/_PROTOTYPE/_ACTUAL/_DEFINITIVE) (1/1) |
| `WellWellbore/15_9-F-9/15_9-F-9` | TRAJ | 4 | high | 50.0% of entry names carry a Compass/EDM survey marker (2/4) |
| `WellWellbore/15_9-F-9/15_9-F-9 A` | TRAJ | 4 | high | 50.0% of entry names carry a Compass/EDM survey marker (2/4) |
| `WellWellbore/Relief well location 1/F-1 A Northwest Injector 9 58 csg. shoe` | TRAJ | 1 | high | 100.0% of entry names end in a Compass wellpath status (_PLAN/_PROTOTYPE/_ACTUAL/_DEFINITIVE) (1/1) |
| `WellWellbore/Relief well location 1/F-1 B 9 58 csg.shoe` | TRAJ | 1 | high | 100.0% of entry names end in a Compass wellpath status (_PLAN/_PROTOTYPE/_ACTUAL/_DEFINITIVE) (1/1) |
| `WellWellbore/Relief well location 1/F-1 North Upside Pilot 13 38 csg. shoe` | TRAJ | 1 | high | 100.0% of entry names end in a Compass wellpath status (_PLAN/_PROTOTYPE/_ACTUAL/_DEFINITIVE) (1/1) |
| `WellWellbore/Relief well location 2/F-1 A Nortwest Injector 9 58 csg. shoe` | TRAJ | 1 | high | 100.0% of entry names end in a Compass wellpath status (_PLAN/_PROTOTYPE/_ACTUAL/_DEFINITIVE) (1/1) |
| `WellWellbore/Relief well location 2/F-1 North Upside Pilot 13 38 csg. shoe` | TRAJ | 1 | high | 100.0% of entry names end in a Compass wellpath status (_PLAN/_PROTOTYPE/_ACTUAL/_DEFINITIVE) (1/1) |
| `WellWellbore/Relief well location 3/F-1 C` | TRAJ | 1 | high | 100.0% of entry names end in a Compass wellpath status (_PLAN/_PROTOTYPE/_ACTUAL/_DEFINITIVE) (1/1) |
| `WellWellbore/Relief well location 3/F-12` | TRAJ | 1 | high | 100.0% of entry names end in a Compass wellpath status (_PLAN/_PROTOTYPE/_ACTUAL/_DEFINITIVE) (1/1) |
| `WellWellbore/Relief well location 3/F-15 C Top Resevoir Intersection` | TRAJ | 1 | high | 100.0% of entry names end in a Compass wellpath status (_PLAN/_PROTOTYPE/_ACTUAL/_DEFINITIVE) (1/1) |
| `WellWellbore/Relief well location 3/F-15 D` | TRAJ | 2 | high | 100.0% of entry names end in a Compass wellpath status (_PLAN/_PROTOTYPE/_ACTUAL/_DEFINITIVE) (2/2) |
| `WellWellbore/Relief well location 4/F-1 C` | TRAJ | 1 | high | 100.0% of entry names end in a Compass wellpath status (_PLAN/_PROTOTYPE/_ACTUAL/_DEFINITIVE) (1/1) |
| `WellWellbore/Relief well location 4/F-15 C Top Reservoir Intersection` | TRAJ | 1 | high | 100.0% of entry names end in a Compass wellpath status (_PLAN/_PROTOTYPE/_ACTUAL/_DEFINITIVE) (1/1) |
| `WellWellbore/Relief well location 4/F-15 D` | TRAJ | 2 | high | 100.0% of entry names end in a Compass wellpath status (_PLAN/_PROTOTYPE/_ACTUAL/_DEFINITIVE) (2/2) |
| `WellWellbore/Relief well location 5/F-1 A  Northwest Injector 9 58 csg.shoe` | TRAJ | 1 | high | 100.0% of entry names end in a Compass wellpath status (_PLAN/_PROTOTYPE/_ACTUAL/_DEFINITIVE) (1/1) |
| `WellWellbore/Relief well location 5/F-1 B 9 58 csg.shoe` | TRAJ | 1 | high | 100.0% of entry names end in a Compass wellpath status (_PLAN/_PROTOTYPE/_ACTUAL/_DEFINITIVE) (1/1) |
| `WellWellbore/Relief well location 5/F-1 North Upside Pilot 13 38 csg.shoe` | TRAJ | 1 | high | 100.0% of entry names end in a Compass wellpath status (_PLAN/_PROTOTYPE/_ACTUAL/_DEFINITIVE) (1/1) |
| `WellWellbore/Relief well location 5/F-12` | TRAJ | 1 | high | 100.0% of entry names end in a Compass wellpath status (_PLAN/_PROTOTYPE/_ACTUAL/_DEFINITIVE) (1/1) |
| `Wellcat` | UNCLASSIFIED | 3 | none | no rule matched; extension mix is .wcd x3 |

### Classification evidence, per archive

- **`15_9-F-11.zip`** → `LOG` (confidence: high)
  - 51.7% of entries carry well-log extensions (15/29)
  - 65.5% of entry names use the wireline/LWD naming convention (19/29)
  - secondary signal present: DOC scored 69
- **`15_9-F-12.zip`** → `LOG` (confidence: high)
  - 85.2% of entries carry well-log extensions (213/250)
  - 84.8% of entry names use the wireline/LWD naming convention (212/250)
- **`15_9-F-14.zip`** → `LOG` (confidence: high)
  - 80.3% of entries carry well-log extensions (188/234)
  - 76.9% of entry names use the wireline/LWD naming convention (180/234)
- **`15_9-F-15 A.zip`** → `LOG` (confidence: high)
  - 44.2% of entries carry well-log extensions (57/129)
  - 40.3% of entry names use the wireline/LWD naming convention (52/129)
  - secondary signal present: VSP scored 64
- **`15_9-F-15 B.zip`** → `LOG` (confidence: high)
  - 60.8% of entries carry well-log extensions (31/51)
  - 70.6% of entry names use the wireline/LWD naming convention (36/51)
  - secondary signal present: DOC scored 41
- **`15_9-F-15 C.zip`** → `LOG` (confidence: high)
  - 58.7% of entries carry well-log extensions (54/92)
  - 77.2% of entry names use the wireline/LWD naming convention (71/92)
  - secondary signal present: DOC scored 45
- **`15_9-F-15 D.zip`** → `LOG` (confidence: high)
  - 51.3% of entries carry well-log extensions (39/76)
  - 80.3% of entry names use the wireline/LWD naming convention (61/76)
  - secondary signal present: DOC scored 57
- **`15_9-F-15.zip`** → `LOG` (confidence: high)
  - 44.0% of entries carry well-log extensions (48/109)
  - 66.1% of entry names use the wireline/LWD naming convention (72/109)
  - secondary signal present: DOC scored 53
- **`Norway-NA-15_$47$_9-F-9 A.zip`** → `WITSML` (confidence: high)
  - 50.0% of entries sit in WITSML object subtrees (4/8)
  - 50.0% of entries are WITSML export manifests (4/8)
  - secondary signal present: TRAJ scored 62
- **`Norway-Statoil-15_$47$_9-F-12.zip`** → `WITSML` (confidence: high)
  - 33.3% of entries sit in WITSML object subtrees (5/15)
  - 33.3% of entries are WITSML export manifests (5/15)
  - 66.7% of entries are XML (10/15)
  - secondary signal present: TRAJ scored 85
- **`Norway-Statoil-NO 15_$47$_9-F-12.zip`** → `WITSML` (confidence: high)
  - 99.6% of entries sit in WITSML object subtrees (691/694)
  - 1.3% of entries are WITSML export manifests (9/694)
  - 98.7% of entries are XML (685/694)
  - secondary signal present: TRAJ scored 25
- **`Norway-Statoil-NO 15_$47$_9-F-14.zip`** → `WITSML` (confidence: high)
  - 99.5% of entries sit in WITSML object subtrees (606/609)
  - 1.6% of entries are WITSML export manifests (10/609)
  - 98.4% of entries are XML (599/609)
  - secondary signal present: TRAJ scored 25
- **`Norway-Statoil-NO 15_$47$_9-F-15.zip`** → `WITSML` (confidence: high)
  - 99.8% of entries sit in WITSML object subtrees (2812/2817)
  - 0.7% of entries are WITSML export manifests (20/2817)
  - 99.3% of entries are XML (2797/2817)
  - secondary signal present: TRAJ scored 25
- **`Norway-StatoilHydro-15_$47$_9-F-10.zip`** → `WITSML` (confidence: high)
  - 41.7% of entries sit in WITSML object subtrees (5/12)
  - 41.7% of entries are WITSML export manifests (5/12)
  - 58.3% of entries are XML (7/12)
  - secondary signal present: TRAJ scored 75
- **`Norway-StatoilHydro-15_$47$_9-F-14.zip`** → `WITSML` (confidence: high)
  - 53.3% of entries sit in WITSML object subtrees (8/15)
  - 46.7% of entries are WITSML export manifests (7/15)
  - 53.3% of entries are XML (8/15)
  - secondary signal present: TRAJ scored 65
- **`Norway-StatoilHydro-15_$47$_9-F-15.zip`** → `WITSML` (confidence: high)
  - 55.6% of entries sit in WITSML object subtrees (5/9)
  - 55.6% of entries are WITSML export manifests (5/9)
  - secondary signal present: TRAJ scored 58
- **`Norway-StatoilHydro-15_$47$_9-F-15A.zip`** → `WITSML` (confidence: high)
  - 55.6% of entries sit in WITSML object subtrees (5/9)
  - 55.6% of entries are WITSML export manifests (5/9)
  - secondary signal present: TRAJ scored 58
- **`Norway-StatoilHydro-15_$47$_9-F-15B.zip`** → `WITSML` (confidence: high)
  - 62.5% of entries sit in WITSML object subtrees (5/8)
  - 62.5% of entries are WITSML export manifests (5/8)
  - secondary signal present: TRAJ scored 50
- **`Norway-StatoilHydro-15_$47$_9-F-15S.zip`** → `WITSML` (confidence: high)
  - 55.6% of entries sit in WITSML object subtrees (5/9)
  - 55.6% of entries are WITSML export manifests (5/9)
  - secondary signal present: TRAJ scored 58
- **`Volve_Production_data.zip`** → `PROD` (confidence: high)
  - 100.0% of entries sit under a production-data folder (2/2)
  - secondary signal present: DOC scored 25
- **`Volve_Reports.zip`** → `DOC` (confidence: high)
  - 66.7% of entries are documents (2/3)
  - 100.0% of entry names look like report/licence documents (3/3)
- **`Volve_Reservoir_Model-Eclipse_model.zip`** → `SIM` (confidence: high)
  - 47.7% of entries carry Eclipse deck/output extensions (31/65)
  - 100.0% of entry names contain an Eclipse model marker (65/65)
- **`Volve_Seismic_VSP.zip`** → `VSP` (confidence: high)
  - 70.8% SEG-Y entries, all under a VSP/checkshot path (34/48)
  - 10.4% of entry names contain 'checkshot' (5/48)
- **`Volve_Well_technical_data.zip`** → `DDR` (confidence: high)
  - 96.3% of entries sit under a 'Daily Drilling Report' folder (5277/5480)
  - 96.3% of entries use the per-well per-day report filename pattern (5277/5480)
  - secondary signal present: DOC scored 82

## 2. Duplicate groups

Comparison method: crc32 of sorted (root-stripped lowercased entry name, uncompressed size, entry CRC32) triples read from the zip central directory.
Archives are compared by **content, never by name**. Duplicates are skipped
during extraction and are never deleted.

**No duplicate groups were found.** All 24 archives have distinct content checksums.

This is worth stating explicitly, because the brief expected duplicates from
double downloads and `(1)`-suffixed names. Neither is present in this folder:
no filename carries a `(1)` suffix, and no two archives share a payload.

## 3. Unclassified archives and subdirectories

- **`Volve_Well_technical_data.zip` → `CasingSeat/`** → `UNCLASSIFIED` (1 files, confidence: placeholder)
  - all 1 entries are 'left_intentionally_empty' placeholders: the source shipped this folder deliberately empty, so there is no content to classify
- **`Volve_Well_technical_data.zip` → `CasingWear/`** → `UNCLASSIFIED` (1 files, confidence: placeholder)
  - all 1 entries are 'left_intentionally_empty' placeholders: the source shipped this folder deliberately empty, so there is no content to classify
- **`Volve_Well_technical_data.zip` → `Compass/`** → `UNCLASSIFIED` (1 files, confidence: placeholder)
  - all 1 entries are 'left_intentionally_empty' placeholders: the source shipped this folder deliberately empty, so there is no content to classify
- **`Volve_Well_technical_data.zip` → `StressCheck/`** → `UNCLASSIFIED` (8 files, confidence: none)
  - no rule matched; extension mix is .sck x8
- **`Volve_Well_technical_data.zip` → `WellPlan/`** → `UNCLASSIFIED` (1 files, confidence: placeholder)
  - all 1 entries are 'left_intentionally_empty' placeholders: the source shipped this folder deliberately empty, so there is no content to classify
- **`Volve_Well_technical_data.zip` → `Wellcat/`** → `UNCLASSIFIED` (3 files, confidence: none)
  - no rule matched; extension mix is .wcd x3

## 4. Representative file per source code

### DDR — Daily Drilling Report (HTML, PDF, XML)

- Original entry: `Well_technical_data/Daily Drilling Report - XML Version/15_9_F_1_2007_12_02.xml`
- Archive: `Volve_Well_technical_data.zip`
- Extracted to: `data/landing/ddr/Well_technical_data/Daily Drilling Report - XML Version/15_9_F_1_2007_12_02.xml`
- Size on disk: 12.6 KB

Element structure, two levels deep (not raw content):

```
drillReports   [attrs: version, {http://www.w3.org/2001/XMLSchema-instance}schemaLocation]
  documentInfo x1   [attrs: none]
    documentName x1
    owner x1
  drillReport x1   [attrs: none]
    nameWell x1
    nameWellbore x1
    name x1
    dTimStart x1
    dTimEnd x1
    versionKind x1
    createDate x1
    wellAlias x1
    wellboreAlias x2
    wellboreInfo x1
    statusInfo x1
    fluid x1
```

### DOC — other documents and reports

- Original entry: `Reports/Volve PUD .pdf`
- Archive: `Volve_Reports.zip`
- Extracted to: `data/landing/doc/Reports/Volve PUD .pdf`
- Size on disk: 4.6 MB

Binary format (`.pdf`) — hexdump of the first 256 bytes:

```
00000000  25 50 44 46 2d 31 2e 36 0d 25 e2 e3 cf d3 0d 0a  |%PDF-1.6.%......|
00000010  31 34 34 34 20 30 20 6f 62 6a 20 3c 3c 2f 4c 69  |1444 0 obj <</Li|
00000020  6e 65 61 72 69 7a 65 64 20 31 2f 4c 20 34 38 34  |nearized 1/L 484|
00000030  34 39 39 33 2f 4f 20 31 34 34 39 2f 45 20 31 37  |4993/O 1449/E 17|
00000040  35 34 34 36 2f 4e 20 35 33 2f 54 20 34 38 31 36  |5446/N 53/T 4816|
00000050  30 36 34 2f 48 20 5b 20 31 34 35 36 20 31 39 33  |064/H [ 1456 193|
00000060  36 5d 3e 3e 0d 65 6e 64 6f 62 6a 0d 20 20 20 20  |6]>>.endobj.    |
00000070  20 20 0d 0a 78 72 65 66 0d 0a 31 34 34 34 20 35  |  ..xref..1444 5|
00000080  38 0d 0a 30 30 30 30 30 30 30 30 31 36 20 30 30  |8..0000000016 00|
00000090  30 30 30 20 6e 0d 0a 30 30 30 30 30 30 33 33 39  |000 n..000000339|
000000a0  32 20 30 30 30 30 30 20 6e 0d 0a 30 30 30 30 30  |2 00000 n..00000|
000000b0  30 33 35 31 33 20 30 30 30 30 30 20 6e 0d 0a 30  |03513 00000 n..0|
000000c0  30 30 30 30 30 33 35 35 38 20 30 30 30 30 30 20  |000003558 00000 |
000000d0  6e 0d 0a 30 30 30 30 30 30 33 36 39 30 20 30 30  |n..0000003690 00|
000000e0  30 30 30 20 6e 0d 0a 30 30 30 30 30 30 33 37 33  |000 n..000000373|
000000f0  35 20 30 30 30 30 30 20 6e 0d 0a 30 30 30 30 30  |5 00000 n..00000|
```

### GEOM — geophysical interpretation (fault polygons, horizons, picks, perforations)

_No file in this dataset carries this code. See section 6._

### LOG — well logs (LAS and other log files)

- Original entry: `15_9-F-15 C/12.BIOSTRAT/NO_15_9-F-15_C.las`
- Archive: `15_9-F-15 C.zip`
- Extracted to: `data/landing/log/15_9-F-15_C/12.BIOSTRAT/NO_15_9-F-15_C.las`
- Size on disk: 172.1 KB

First 30 lines:

```
#------------------------------------------------------------------------------
#
#   Created by   : las_export
#   Created on   : 2009-06-18 13:07:55
#   Project      : VOLVE
#   User         : TONYG
#   Interpreters : *
#
#------------------------------------------------------------------------------
~VERSION INFORMATION
VERS. 2.0 : CWLS Log ASCII Standard - version 2.0
WRAP.  NO : One line per depth step

~WELL INFORMATION
#MNEMONIC   .UNIT                                           VALUE :DESCRIPTION
#------------------------------------------------------------------------------
STRT        .M                                       2560.0412 :START DEPTH
STOP        .M                                       3222.0668 :STOP DEPTH
STEP        .M                                          0.1524 :STEP
NULL        .                                        -999.2500 :NULL VALUE
COMP        .                                                  :COMPANY
WELL        .                                      15/9-F-15 C :WELL
FLD         .                                            VOLVE :FIELD
LOC         .                                          UNKNOWN :LOCATION
CNTY        .                                          UNKNOWN :COUNTY
STAT        .                                          UNKNOWN :STATE
CTRY        .                                           Norway :COUNTRY
SRVC        .                                          UNKNOWN :SERVICE COMPANY
DATE        .                                          UNKNOWN :LOG DATE
UWI         .                                   NO 15/9-F-15 C :UNIQUE WELL ID
```

### PROD — daily and monthly production per well (tabular)

- Original entry: `Production_data/Volve production data.xlsx`
- Archive: `Volve_Production_data.zip`
- Extracted to: `data/landing/prod/Production_data/Volve production data.xlsx`
- Size on disk: 2.2 MB

Binary format (`.xlsx`) — hexdump of the first 256 bytes:

```
00000000  50 4b 03 04 14 00 06 00 08 00 00 00 21 00 21 8c  |PK..........!.!.|
00000010  46 3a 73 01 00 00 8c 05 00 00 13 00 08 02 5b 43  |F:s...........[C|
00000020  6f 6e 74 65 6e 74 5f 54 79 70 65 73 5d 2e 78 6d  |ontent_Types].xm|
00000030  6c 20 a2 04 02 28 a0 00 02 00 00 00 00 00 00 00  |l ...(..........|
00000040  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  |................|
00000050  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  |................|
00000060  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  |................|
00000070  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  |................|
00000080  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  |................|
00000090  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  |................|
000000a0  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  |................|
000000b0  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  |................|
000000c0  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  |................|
000000d0  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  |................|
000000e0  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  |................|
000000f0  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  |................|
```

### SEIS — SEG-Y surface seismic

_No file in this dataset carries this code. See section 6._

### SIM — Eclipse simulation output (PRT and input decks)

- Original entry: `Reservoir_Model-Eclipse_model/Volve_sim_model_PPA-Eclipse Res Model/VOLVE_2016.PRT`
- Archive: `Volve_Reservoir_Model-Eclipse_model.zip`
- Extracted to: `data/landing/sim/Reservoir_Model-Eclipse_model/Volve_sim_model_PPA-Eclipse Res Model/VOLVE_2016.PRT`
- Size on disk: 227.7 MB

First 30 lines:

```



 $$$$$   $$$   $      $$$  $$$$    $$$   $$$$$     $    $$$    $$$ 
 $      $   $  $       $   $   $  $   $  $        $$   $   $  $   $
 $      $      $       $   $   $  $      $         $   $   $  $   $
 $$$$   $      $       $   $$$$    $$$   $$$$      $   $   $  $   $
 $      $      $       $   $          $  $         $   $   $  $   $
 $      $   $  $       $   $      $   $  $         $   $   $  $   $
 $$$$$   $$$   $$$$$  $$$  $       $$$   $$$$$    $$$   $$$    $$$ 



                       $$$$$   $$$   $      $$$  $$$$    $$$   $$$$$     $    $$$    $$$ 
                       $      $   $  $       $   $   $  $   $  $        $$   $   $  $   $
                       $      $      $       $   $   $  $      $         $   $   $  $   $
                       $$$$   $      $       $   $$$$    $$$   $$$$      $   $   $  $   $
                       $      $      $       $   $          $  $         $   $   $  $   $
                       $      $   $  $       $   $      $   $  $         $   $   $  $   $
                       $$$$$   $$$   $$$$$  $$$  $       $$$   $$$$$    $$$   $$$    $$$ 



                                             $$$$$   $$$   $      $$$  $$$$    $$$   $$$$$     $    $$$    $$$ 
                                             $      $   $  $       $   $   $  $   $  $        $$   $   $  $   $
                                             $      $      $       $   $   $  $      $         $   $   $  $   $
                                             $$$$   $      $       $   $$$$    $$$   $$$$      $   $   $  $   $
                                             $      $      $       $   $          $  $         $   $   $  $   $
                                             $      $   $  $       $   $      $   $  $         $   $   $  $   $
                                             $$$$$   $$$   $$$$$  $$$  $       $$$   $$$$$    $$$   $$$    $$$ 
```

### TRAJ — directional surveys (EDT/EDM/Compass)

- Original entry: `Norway-NA-15_$47$_9-F-9 A/1/trajectory/1.xml`
- Archive: `Norway-NA-15_$47$_9-F-9 A.zip`
- Extracted to: `data/landing/traj/Norway-NA-15-9-F-9_A/1/trajectory/1.xml`
- Size on disk: 49.1 KB

Element structure, two levels deep (not raw content):

```
trajectorys   [attrs: version]
  trajectory x1   [attrs: uidWell, uidWellbore, uid]
    nameWell x1
    nameWellbore x1
    name x1
    dTimTrajStart x1
    dTimTrajEnd x1
    mdMn x1
    mdMx x1
    serviceCompany x1
    magDeclUsed x1
    gridCorUsed x1
    aziVertSect x1
    memory x1
```

### VSP — checkshot / vertical seismic profile

- Original entry: `VSP/Checkshots/checkshot_15_9_19A.txt`
- Archive: `Volve_Seismic_VSP.zip`
- Extracted to: `data/landing/vsp/VSP/Checkshots/checkshot_15_9_19A.txt`
- Size on disk: 18.5 KB

First 30 lines:

```
Curve Name                     TVDBTDD          TVD              TVDSS            Two Way Time       
TIME-CKS                       0.00             25.00            0.00             0.0000             
TIME-CKS                       1053.30          1078.30          -1053.30         1102.2000          
TIME-CKS                       1063.50          1088.50          -1063.50         1111.8000          
TIME-CKS                       1073.60          1098.60          -1073.60         1121.2000          
TIME-CKS                       1083.80          1108.80          -1083.80         1130.0000          
TIME-CKS                       1093.10          1118.10          -1093.10         1138.6000          
TIME-CKS                       1148.20          1173.20          -1148.20         1191.2000          
TIME-CKS                       1156.20          1181.20          -1156.20         1199.0000          
TIME-CKS                       1164.10          1189.10          -1164.10         1207.0000          
TIME-CKS                       1172.10          1197.10          -1172.10         1214.6000          
TIME-CKS                       1180.10          1205.10          -1180.10         1222.4000          
TIME-CKS                       1233.50          1258.50          -1233.50         1272.4000          
TIME-CKS                       1241.50          1266.50          -1241.50         1279.4000          
TIME-CKS                       1249.40          1274.40          -1249.40         1287.2000          
TIME-CKS                       1257.20          1282.20          -1257.20         1293.8000          
TIME-CKS                       1265.00          1290.00          -1265.00         1300.8000          
TIME-CKS                       1315.70          1340.70          -1315.70         1344.4000          
TIME-CKS                       1323.00          1348.00          -1323.00         1352.0000          
TIME-CKS                       1330.30          1355.30          -1330.30         1358.8000          
TIME-CKS                       1337.70          1362.70          -1337.70         1366.8000          
TIME-CKS                       1345.00          1370.00          -1345.00         1374.8000          
TIME-CKS                       1352.60          1377.60          -1352.60         1382.4000          
TIME-CKS                       1360.20          1385.20          -1360.20         1389.6000          
TIME-CKS                       1367.80          1392.80          -1367.80         1397.0000          
TIME-CKS                       1375.40          1400.40          -1375.40         1404.6000          
TIME-CKS                       1383.00          1408.00          -1383.00         1412.0000          
TIME-CKS                       1390.60          1415.60          -1390.60         1419.2000          
TIME-CKS                       1398.30          1423.30          -1398.30         1426.6000          
TIME-CKS                       1406.00          1431.00          -1406.00         1434.2000          
```

### WITSML — drilling telemetry (WITSML XML, or CSV when already parsed)

- Original entry: `Norway-Statoil-NO 15_$47$_9-F-12/1/rig/1.xml`
- Archive: `Norway-Statoil-NO 15_$47$_9-F-12.zip`
- Extracted to: `data/landing/witsml/Norway-Statoil-NO_15-9-F-12/1/rig/1.xml`
- Size on disk: 1.9 KB

Element structure, two levels deep (not raw content):

```
rigs   [attrs: version]
  rig x1   [attrs: uidWell, uidWellbore, uid]
    nameWell x1
    nameWellbore x1
    name x1
    owner x1
    typeRig x1
    bop x1
    surfaceEquipment x1
    ratingDerrick x1
    htDerrick x1
    wtBlock x1
    numBlockLines x1
    typeDrawWorks x1
```

## 5. Temuan yang perlu tindak lanjut

1. **The folder holds 24 archives, matching the brief.** An earlier run
   of this tool found only 20 and recorded the shortfall; the four remaining
   downloads have since landed and are included here. Alongside them sits one
   non-zip file (`HRS and Terms and conditions for license to data - Volve.pdf`), a licence/terms
   PDF loose beside the archives rather than inside one.

2. **No duplicate archives exist.** The brief anticipated double downloads and
   `(1)`-suffixed names. Content checksums are all distinct and no filename
   carries a `(1)` suffix.

   5 sets of archives *name* the same wellbore while holding
   different content. They are deliberately all kept:

   - **F-12**: `Norway-Statoil-15_$47$_9-F-12.zip` (15 files) vs `15_9-F-12.zip` (250 files) vs `Norway-Statoil-NO 15_$47$_9-F-12.zip` (694 files)
   - **F-14**: `Norway-StatoilHydro-15_$47$_9-F-14.zip` (15 files) vs `15_9-F-14.zip` (234 files) vs `Norway-Statoil-NO 15_$47$_9-F-14.zip` (609 files)
   - **F-15**: `Norway-StatoilHydro-15_$47$_9-F-15.zip` (9 files) vs `15_9-F-15.zip` (109 files) vs `Norway-Statoil-NO 15_$47$_9-F-15.zip` (2817 files)
   - **F-15A**: `Norway-StatoilHydro-15_$47$_9-F-15A.zip` (9 files) vs `15_9-F-15 A.zip` (129 files)
   - **F-15B**: `Norway-StatoilHydro-15_$47$_9-F-15B.zip` (8 files) vs `15_9-F-15 B.zip` (51 files)

   In each set the larger archive is a different, much fuller export of the
   same wellbore, not a second copy of the smaller one. Comparing by name
   alone would have discarded real data here.

3. **A second copy of the dataset sits next to this one, and it is now out of
   date.**

   `C:\Apply Kerja\DE\data_volve_mentah` holds 20 archives, 20 of which share a filename with this folder.
   Missing from it (4): `15_9-F-15 A.zip`, `15_9-F-15 C.zip`, `15_9-F-15.zip`, `Norway-Statoil-NO 15_$47$_9-F-15.zip`.

   Only the folder named in the brief was scanned. The divergence is the
   point: an earlier run of this tool saw both folders holding the same 20
   archives, and the four newer downloads landed in this one alone. Anything
   reading the other folder is now working from a stale subset. Comparison is
   by filename only — no content checksum was taken across folders.

4. **Nested archives are present and were not recursed into.** Some archives
   contain `.zip` entries of their own (for example inside `15_9-F-12.zip`,
   `15_9-F-14.zip`, `15_9-F-15 D.zip` and `Volve_Well_technical_data.zip`).
   They were extracted as opaque files. Whatever they hold is not represented
   in the per-code counts above.

5. **`GEOM` has no archive of its own.** Fault polygons exist only as
   `FAULT_*.GRDECL` inside the Eclipse model archive, facies/pick spreadsheets
   only inside the per-well log archives under `05.PETROPHYSICAL INTERPRETATION/`,
   and perforation logs only as `WL_RAW_PROD_CCL-PERF*` entries. Geophysical
   interpretation is therefore embedded in other deliveries rather than
   delivered as a product, which the per-subdirectory mapping reflects.

6. **`SEIS` is absent while SEG-Y is present.** All 68 `.segy` files
   are borehole seismic, not surface seismic, and are coded
   `VSP` (68).
   They arrive twice, from two separate deliveries of the same F-15 A survey:

   - `15_9-F-15 A/08.VSP_VELOCITY` — 34 files
   - `VSP/15_9_F_15A_VSP/VSPNI_COMPUTED_2009-01-05` — 30 files
   - `VSP/15_9_F_15A_VSP/VSPNI_RAW_2009-01-05` — 4 files

   The per-well archive carries a copy under `08.VSP_VELOCITY` and the dedicated
   seismic archive carries one under `VSP/`. The 34 basenames match exactly and
   both sets total 123,548,304 bytes. Archive-level duplicate detection does not
   group them, correctly: the archives as wholes are different. Both copies are
   kept. See the conflict noted below before treating either as authoritative.
   No surface seismic volume was delivered.

7. **`PROD` arrives as a single Excel workbook**, not as tabular text:
   `Production_data/Volve production data.xlsx` (2.2 MB). There is no CSV form
   of it anywhere in the dataset, so the whole production history — the code
   with the fewest files — sits in one binary file. It is not blocked: `.xlsx`
   is a zip of XML parts and the standard library can read it with `zipfile`
   plus `ElementTree`. Whether to do that or take a dependency is a real
   decision, recorded in `docs/adr/0001-stdlib-only-ingestion.md`.

8. **Four `left_intentionally_empty.txt` markers** stand in for content in
   `Well_technical_data/CasingSeat/`, `CasingWear/`, `Compass/` and `WellPlan/`.
   The `Compass` one matters: it means the directional-survey product named in
   the brief was deliberately not shipped in that folder. The surveys that do
   exist come from the WITSML `trajectory/` subtrees and from
   `WellWellbore/*/Standard Survey Report_*` files instead.
   These four folders are reported as `UNCLASSIFIED` on purpose. An earlier
   pass coded `Compass/` as `TRAJ` on the strength of its directory name; that
   was wrong, because the only file in it is a marker saying the folder is
   empty. A placeholder is evidence of absence, so it is no longer allowed to
   drive a source code.

9. **The producer's own readme reclassified a whole subtree, and it was right.**
   `Well_technical_data/EDT_EDM_read_me.txt` (Statoil, 2018-04-11) states that
   `CasingSeat, CasingWear, Compass, EDM.XML, Site, Site_TemplateSlot,
   StressCheck, Wellcat, WellPlan, WellWellbore` are one **EDT/EDM export from
   Landmark software** — which is the brief's own definition of `TRAJ`
   (EDT/EDM/Compass). An early pass had coded `WellWellbore/` as `DOC`, because
   39% of its files are PDF and the DOC rule outscored the survey rule.
   Checking the content against the readme showed 159 of its 180 files are
   Compass wellpath exports: 49 `Standard Survey Report_*`, plus 110 named with
   the Compass status suffixes `_PLAN`, `_PROTOTYPE` and `_ACTUAL`. The PDFs are
   the *rendering* of the surveys, not unrelated documents. That suffix
   convention is now an explicit rule and `WellWellbore/` is coded `TRAJ`.
   `StressCheck/` and `Wellcat/` remain unclassified on purpose: they are
   casing-stress and tubing-design files from the same export, and no source
   code in the brief covers well engineering design.

10. **Encoding: the mangling the brief warned about does not occur, but the
   flag is inconsistent.** 19 archives set the UTF-8 flag on every
   entry; 4 set it on none; 1 set it on some
   entries only.
   `Volve_Well_technical_data.zip` sets it on 3 of
   5,568 entries — the ones whose names carry `æ ø å`.
   Across all 24 archives, 0 entry names are genuinely
   ambiguous (unflagged *and* non-ASCII). Every unflagged name in this dataset
   is pure ASCII, so the cp437 fallback decodes them identically to UTF-8 and
   latin-1. Where a name does carry non-ASCII, every reading is still recorded
   per entry in `name-mapping.csv` rather than one being chosen silently.

11. **`$47$` is a live encoding in entry names, not only in archive names.**
    It appears inside WITSML entry paths too, e.g.
    `15_$47$_9-F-9 A - Main Wellbore (B-986464)(NULL).xml`. It encodes a forward
    slash from the source system. Slugs restore it as a hyphen for directory
    names; entry paths keep it verbatim, because `$` is legal on Windows and the
    string is data.

12. **Layout deviation, deliberate.** The brief shows a `<slug>` level only under
    `witsml/` and `log/`. That level is applied under every code directory here.
    Several archives contribute to `doc/`, `geom/` and `traj/`, and without a
    per-source level their entry paths collide — `license.txt` alone arrives from
    five archives. The slug is derived from the archive's own root folder name,
    so it preserves the source-given name rather than inventing one.

13. **Path safety:** 0 entries were rejected as unsafe
    (traversal or absolute paths).

14. **Renames:** 0 of 10773 extracted files needed a name change.

15. **10 entry names are percent-encoded** and were left that way.
    For example `F-13_AB%20DG2_Target%20btw%20F12_F14%20Rev2%2C3%20141210-Final%2C%20v1.sck`,
    where `%20` is a space and `%2C` a comma. Sibling files in the same folder
    use literal spaces, so the encoding is inconsistent within one directory —
    two different export paths fed the same folder. The names are stored
    verbatim: decoding them here would be a transformation, and this session
    writes none. Identity resolution will have to normalise them, and should
    treat `%20` and a literal space as the same character when it does.

16. **2 Windows shortcut (`.lnk`) file(s) shipped inside the data**, e.g.
    `15_9-F-15 B/14.DIV.REPORTS/FWR_DRILLING_15_9_F-15_F-15A_F-15B_F-15C.pdf - Shortcut.lnk`. A shortcut points at a path on the
    machine that produced the archive; it carries no data of its own and its
    target almost certainly does not exist here.

17. **Same file, same size, different bytes — in 2 cases.**
    80 files appear in more than one
    archive under the same name and size. 42 of
    them are byte-identical everywhere, which is reassuring and expected for
    partially overlapping deliveries. A further
    36 are coincidence rather than
    overlap — sequence-numbered WITSML exports and fixed export-manifest names
    (`1.xml`, `100.xml`, `106.xml`, `113.xml`, `158.xml`)
    that describe *different* wellbores and merely happen to match in length;
    those are excluded by the corroboration rule in the method note. These are
    the real conflicts:

    - `vspni_computed_17.segy` (819,792 bytes)
      - CRC32 `371aa27e` — `15_9-F-15 A.zip` → `15_9-F-15 A/08.VSP_VELOCITY/VSPNI_COMPUTED_17.SEGY`
      - CRC32 `7c2d0690` — `Volve_Seismic_VSP.zip` → `VSP/15_9_F_15A_VSP/VSPNI_COMPUTED_2009-01-05/VSPNI_COMPUTED_17.SEGY`
    - `vspni_computed_26.segy` (872,112 bytes)
      - CRC32 `9dbc1efc` — `15_9-F-15 A.zip` → `15_9-F-15 A/08.VSP_VELOCITY/VSPNI_COMPUTED_26.SEGY`
      - CRC32 `10b116d5` — `Volve_Seismic_VSP.zip` → `VSP/15_9_F_15A_VSP/VSPNI_COMPUTED_2009-01-05/VSPNI_COMPUTED_26.SEGY`

    Identical name, identical byte length, different CRC32. That cannot be a
    truncated download: a partial copy would be shorter. It is either a
    re-processed version that kept the original length, or one copy is
    corrupt. Nothing here can tell which, because deciding would mean reading
    the trace data, and this session parses nothing. Both copies were
    extracted and neither was preferred. **Resolve this before either copy is
    used**, and note that a pipeline picking files by name alone would silently
    choose one at random.

18. **One file appeared inside the read-only archive folder during this session,
    and it was not put there by this pipeline.** The interactive tool session
    ran with the archive folder as its working directory and wrote
    `.claude/settings.local.json` there. Nothing in `inventory.py` opens that
    folder for writing. It was left in place rather than deleted, because
    deleting inside the archive folder would itself break the read-only rule.
    It is noted here so the folder's contents are not mistaken for source data.


## 6. Sumber yang belum tersedia

These source codes are defined by the ingestion brief but **no archive in
this folder produces a single file under them**:

- **GEOM** — geophysical interpretation (fault polygons, horizons, picks, perforations)
- **SEIS** — SEG-Y surface seismic

Counts of extracted files per code:

| Code | Files extracted |
|---|---:|
| DDR | 5277 |
| WITSML | 4162 |
| LOG | 828 |
| TRAJ | 211 |
| DOC | 110 |
| VSP | 103 |
| SIM | 65 |
| UNCLASSIFIED | 15 |
| PROD | 2 |

