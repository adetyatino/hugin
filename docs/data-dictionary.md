# Volve data dictionary — observed format facts

Draft. Every statement below was measured from an extracted file, not assumed.
This document records **format** only: encoding, delimiters, headers, date
shapes, sentinel values, non-ASCII characters and units as literally written
in the files. It contains no transformation logic, no domain model and no plan.

Where a code has several file formats, one representative of each was profiled.
A blank field means the probe found no instance, not that none exists.

## DDR

_Daily Drilling Report (HTML, PDF, XML)_ — 5277 extracted files.

Formats present: `.html` x1759, `.xml` x1759, `.pdf` x1759.

### `.html` — probed on `data/landing/ddr/Well_technical_data/Daily Drilling Report - HTML Version/15_9_19_A_1980_01_01.html`

| Property | Observed |
|---|---|
| Encoding | ascii |
| Line endings | LF |
| Delimiter | tab |
| First non-empty line | `<html xmlns:fo="http://www.w3.org/1999/XSL/Format" xmlns:witsml="http://www.witsml.org/schemas/1series"><head><meta charset="utf-8"/><meta name="viewport" conte` |
| Header row present | yes — see line above |
| Date formats seen | YYYY-MM-DD |
| Sentinel values seen | none found in sample |
| Non-ASCII characters | none in sample |
| Units written in file | none declared in sample |

### `.xml` — probed on `data/landing/ddr/Well_technical_data/Daily Drilling Report - XML Version/15_9_19_A_1980_01_01.xml`

| Property | Observed |
|---|---|
| Encoding | ascii |
| Line endings | CRLF |
| Delimiter | none detected |
| First non-empty line | `<witsml:drillReports version="1.4.0.0" xmlns:witsml="http://www.witsml.org/schemas/1series" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLoca` |
| Header row present | yes — see line above |
| Date formats seen | ISO 8601 date-time (YYYY-MM-DDThh:mm:ss), YYYY-MM-DD |
| Sentinel values seen | none found in sample |
| Non-ASCII characters | none in sample |
| Units written in file | `dega`, `m`, `m/h` |

Binary or opaque formats under this code, not text-profiled: `.pdf`.

## DOC

_other documents and reports_ — 110 extracted files.

Formats present: `.pdf` x83, `.doc` x6, `.txt` x6, `.dex` x5, `.zip` x3, `.lnk` x2, `.db` x2, `.asc` x1, `.xls` x1, `.xlsx` x1.

### `.txt` — probed on `data/landing/doc/15_9-F-14/10.PRODUCTION LOGS/PLT March 2009/read me.txt`

| Property | Observed |
|---|---|
| Encoding | not utf-8; cp1252/latin-1 readable |
| Line endings | CRLF |
| Delimiter | whitespace-aligned |
| First non-empty line | `•	Følgende vedlagte fire .LAS-filer er eksportert med dybdeinkrement 0.5m; HR.LAS, MR.LAS, LR.LAS & SI.LAS` |
| Header row present | yes — see line above |
| Date formats seen | none found in sample |
| Sentinel values seen | none found in sample |
| Non-ASCII characters | `«` (U+00AB), `°` (U+00B0), `»` (U+00BB), `å` (U+00E5), `ø` (U+00F8), `–` (U+2013), `•` (U+2022), `…` (U+2026) |
| Units written in file | `K/M3`, `M/MN`, `bara`, `m`, `m3/D` |

### `.asc` — probed on `data/landing/doc/15_9-F-12/03.PRESSURE/FM_PRESS_COMPUTED_MWD_1.ASC`

| Property | Observed |
|---|---|
| Encoding | not utf-8; cp1252/latin-1 readable |
| Line endings | CRLF |
| Delimiter | whitespace-aligned |
| First non-empty line | `OPERATOR     : STATOILHYDRO ASA` |
| Header row present | yes — see line above |
| Date formats seen | none found in sample |
| Sentinel values seen | none found in sample |
| Non-ASCII characters | `§` (U+00A7), `Æ` (U+00C6) |
| Units written in file | none declared in sample |

Binary or opaque formats under this code, not text-profiled: `.pdf`, `.doc`, `.dex`, `.zip`, `.lnk`, `.db`, `.xls`, `.xlsx`.

## LOG

_well logs (LAS and other log files)_ — 828 extracted files.

Formats present: `.dlis` x307, `.pdf` x184, `.asc` x107, `.las` x100, `.pds` x95, `.lis` x10, `.xls` x9, `.xlsx` x6, `.txt` x5, `.cgm` x4.

### `.asc` — probed on `data/landing/log/15_9-F-11/01.MUD_LOG/MUD_LOG_1_INF_1.ASC`

| Property | Observed |
|---|---|
| Encoding | not utf-8; cp1252/latin-1 readable |
| Line endings | CRLF |
| Delimiter | whitespace-aligned |
| First non-empty line | `OPERATOR     : STATOIL PETROLEUM AS` |
| Header row present | yes — see line above |
| Date formats seen | none found in sample |
| Sentinel values seen | none found in sample |
| Non-ASCII characters | `Æ` (U+00C6) |
| Units written in file | none declared in sample |

### `.las` — probed on `data/landing/log/15_9-F-11/05.PETROPHYSICAL INTERPRETATION/WLC_PETRO_COMPUTED_INPUT_1.LAS`

| Property | Observed |
|---|---|
| Encoding | ascii |
| Line endings | CRLF |
| Delimiter | whitespace-aligned |
| First non-empty line | `~Version Information` |
| Header row present | yes — see line above |
| Date formats seen | none found in sample |
| Sentinel values seen | `-999.25`, `NULL` |
| Non-ASCII characters | none in sample |
| Units written in file | `000`, `100`, `200`, `300`, `400`, `500`, `600`, `700`, `800`, `900`, `API`, `M`, `inches`, `m/hr` |

### `.txt` — probed on `data/landing/log/15_9-F-14/07.IMAGE/EcoScope_ImageInterpret/Dips/Statoil_Volve_15_9-F-14_BedBoundary.txt`

| Property | Observed |
|---|---|
| Encoding | ascii |
| Line endings | CRLF |
| Delimiter | whitespace-aligned |
| First non-empty line | `PrimaryIndex Bed_Boundary DE Bed_Boundary HA Bed_Boundary RB Bed_Boundary DP Bed_Boundary DP Bed_Boundary DP Bed_Boundary DP` |
| Header row present | yes — see line above |
| Date formats seen | none found in sample |
| Sentinel values seen | none found in sample |
| Non-ASCII characters | none in sample |
| Units written in file | `0358`, `0477`, `1092`, `1453`, `1620`, `2015`, `2097`, `2263`, `2418`, `2572`, `2959`, `2972`, `3281`, `3370`, `3589`, `3952`, `4199`, `4310`, `4336`, `4694`, `5036`, `5756`, `5837`, `6363`, `6563` |

Binary or opaque formats under this code, not text-profiled: `.dlis`, `.pdf`, `.pds`, `.lis`, `.xls`, `.xlsx`, `.cgm`, `.gif`.

## PROD

_daily and monthly production per well (tabular)_ — 2 extracted files.

Formats present: `.xlsx` x1, `.txt` x1.

### `.txt` — probed on `data/landing/prod/Production_data/license.txt`

| Property | Observed |
|---|---|
| Encoding | not utf-8; cp1252/latin-1 readable |
| Line endings | CRLF |
| Delimiter | comma |
| First non-empty line | `Thank you for your interest in the Volve dataset. Equinor hope you find the dataset useful and that you can apply it in an innovative and useful way.` |
| Header row present | yes — see line above |
| Date formats seen | none found in sample |
| Sentinel values seen | none found in sample |
| Non-ASCII characters | `“` (U+201C), `”` (U+201D) |
| Units written in file | none declared in sample |

Binary or opaque formats under this code, not text-profiled: `.xlsx`.

## SIM

_Eclipse simulation output (PRT and input decks)_ — 65 extracted files.

Formats present: `<noext>` x15, `.grdecl` x6, `.sch` x6, `.inc` x4, `.msg` x4, `.incl` x3, `.txt` x2, `.ecl` x2, `.e100` x2, `.data` x2.

### `.grdecl` — probed on `data/landing/sim/Reservoir_Model-Eclipse_model/Volve_sim_model_PPA-Eclipse Res Model/CONTACT_MAIN-NW-AP2014.GRDECL`

| Property | Observed |
|---|---|
| Encoding | ascii |
| Line endings | LF |
| Delimiter | whitespace-aligned |
| First non-empty line | `-- mabt april. 2014` |
| Header row present | yes — see line above |
| Date formats seen | none found in sample |
| Sentinel values seen | none found in sample |
| Non-ASCII characters | none in sample |
| Units written in file | none declared in sample |

### `.sch` — probed on `data/landing/sim/Reservoir_Model-Eclipse_model/Volve_sim_model_PPA-Eclipse Res Model/MOD2010_VOLVE_AMAP2012_WELLS_IOR_N_UPPERHUGIN_L-F15D.SCH`

| Property | Observed |
|---|---|
| Encoding | ascii |
| Line endings | CRLF |
| Delimiter | whitespace-aligned |
| First non-empty line | `--` |
| Header row present | yes — see line above |
| Date formats seen | none found in sample |
| Sentinel values seen | none found in sample |
| Non-ASCII characters | none in sample |
| Units written in file | none declared in sample |

### `.inc` — probed on `data/landing/sim/Reservoir_Model-Eclipse_model/Volve_sim_model_PPA-Eclipse Res Model/F-10_main-LH.INC`

| Property | Observed |
|---|---|
| Encoding | ascii |
| Line endings | CRLF |
| Delimiter | whitespace-aligned |
| First non-empty line | `--` |
| Header row present | yes — see line above |
| Date formats seen | none found in sample |
| Sentinel values seen | none found in sample |
| Non-ASCII characters | none in sample |
| Units written in file | none declared in sample |

Binary or opaque formats under this code, not text-profiled: `<noext>`, `.db`, `.dbg`, `.eclend`, `.eclrun`, `.grid`, `.init`, `.inspec`, `.log`, `.out`, `.rft`, `.rsspec`, `.smspec`, `.unrst`, `.unsmry`, `.eclrun_dbg`, `.h5`, `.pptx`, `.summary`.

## TRAJ

_directional surveys (EDT/EDM/Compass)_ — 211 extracted files.

Formats present: `<noext>` x109, `.pdf` x56, `.xml` x32, `.txt` x13, `.zip` x1.

### `.xml` — probed on `data/landing/traj/Norway-NA-15-9-F-9_A/1/trajectory/1.xml`

| Property | Observed |
|---|---|
| Encoding | ascii |
| Line endings | none/one line |
| Delimiter | none detected |
| First non-empty line | `<?xml version="1.0" encoding="UTF-8"?><trajectorys xmlns="http://www.witsml.org/schemas/1series" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="` |
| Header row present | yes — see line above |
| Date formats seen | ISO 8601 date-time (YYYY-MM-DDThh:mm:ss) |
| Sentinel values seen | none found in sample |
| Non-ASCII characters | none in sample |
| Units written in file | `dega`, `dega/m`, `m`, `m/s2`, `nT` |

### `.txt` — probed on `data/landing/traj/Norway-NA-15-9-F-9_A/1/trajectory/MetaDataFileInfo.txt`

| Property | Observed |
|---|---|
| Encoding | ascii |
| Line endings | CRLF |
| Delimiter | whitespace-aligned |
| First non-empty line | `1  8.5 in Section - Actual Traj (T-987280-1)` |
| Header row present | yes — see line above |
| Date formats seen | none found in sample |
| Sentinel values seen | none found in sample |
| Non-ASCII characters | none in sample |
| Units written in file | none declared in sample |

Binary or opaque formats under this code, not text-profiled: `<noext>`, `.pdf`, `.zip`.

## UNCLASSIFIED

_not classified_ — 15 extracted files.

Formats present: `.sck` x8, `.txt` x4, `.wcd` x3.

### `.txt` — probed on `data/landing/_unclassified/Volve_Well_technical_data/CasingSeat/left_intentionally_empty.txt`

| Property | Observed |
|---|---|
| Encoding | ascii |
| Line endings | none/one line |
| Delimiter | none detected |
| First non-empty line | `` |
| Header row present | not detected |
| Date formats seen | none found in sample |
| Sentinel values seen | none found in sample |
| Non-ASCII characters | none in sample |
| Units written in file | none declared in sample |

Binary or opaque formats under this code, not text-profiled: `.sck`, `.wcd`.

## VSP

_checkshot / vertical seismic profile_ — 103 extracted files.

Formats present: `.segy` x68, `.asc` x19, `.las` x7, `.pdf` x5, `.txt` x4.

### `.asc` — probed on `data/landing/vsp/15_9-F-15_A/08.VSP_VELOCITY/TZV_DEPTH_MD_CHECKSHOT_1.ASC`

| Property | Observed |
|---|---|
| Encoding | ascii |
| Line endings | CRLF |
| Delimiter | whitespace-aligned |
| First non-empty line | `Page   1 of  22` |
| Header row present | yes — see line above |
| Date formats seen | none found in sample |
| Sentinel values seen | none found in sample |
| Non-ASCII characters | none in sample |
| Units written in file | `0`, `1`, `2`, `4`, `5`, `6`, `7`, `9` |

### `.las` — probed on `data/landing/vsp/15_9-F-15_A/08.VSP_VELOCITY/TZV_DEPTH_MD_COMPUTED_1.LAS`

| Property | Observed |
|---|---|
| Encoding | ascii |
| Line endings | CRLF |
| Delimiter | whitespace-aligned |
| First non-empty line | `~VERSION INFORMATION` |
| Header row present | yes — see line above |
| Date formats seen | none found in sample |
| Sentinel values seen | `-999.2500`, `NULL` |
| Non-ASCII characters | none in sample |
| Units written in file | `0148`, `0336`, `0524`, `1004`, `1192`, `1672`, `1860`, `2048`, `2528`, `2716`, `3196`, `3384`, `3572`, `4052`, `4240`, `4720`, `4908`, `5096`, `5576`, `5764`, `6244`, `6432`, `6620`, `7100`, `7288` |

### `.txt` — probed on `data/landing/vsp/VSP/Checkshots/checkshot_15_9_19A.txt`

| Property | Observed |
|---|---|
| Encoding | ascii |
| Line endings | LF |
| Delimiter | whitespace-aligned |
| First non-empty line | `Curve Name                     TVDBTDD          TVD              TVDSS            Two Way Time` |
| Header row present | yes — see line above |
| Date formats seen | none found in sample |
| Sentinel values seen | none found in sample |
| Non-ASCII characters | none in sample |
| Units written in file | none declared in sample |

Binary or opaque formats under this code, not text-profiled: `.segy`, `.pdf`.

## WITSML

_drilling telemetry (WITSML XML, or CSV when already parsed)_ — 4162 extracted files.

Formats present: `.xml` x4094, `.txt` x68.

### `.xml` — probed on `data/landing/witsml/Norway-NA-15-9-F-9_A/1/_wellboreInfo/15_$47$_9-F-9 A - Main Wellbore (B-986464)(NULL).xml`

| Property | Observed |
|---|---|
| Encoding | ascii |
| Line endings | none/one line |
| Delimiter | none detected |
| First non-empty line | `<?xml version="1.0" encoding="UTF-8"?><wellbores xmlns="http://www.witsml.org/schemas/1series" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="1.` |
| Header row present | yes — see line above |
| Date formats seen | ISO 8601 date-time (YYYY-MM-DDThh:mm:ss) |
| Sentinel values seen | none found in sample |
| Non-ASCII characters | none in sample |
| Units written in file | `m` |

### `.txt` — probed on `data/landing/witsml/Norway-NA-15-9-F-9_A/1/log/1/MetaFileInfo.txt`

| Property | Observed |
|---|---|
| Encoding | ascii |
| Line endings | CRLF |
| Delimiter | whitespace-aligned |
| First non-empty line | `1  12.25 in Section - Time Log` |
| Header row present | yes — see line above |
| Date formats seen | none found in sample |
| Sentinel values seen | none found in sample |
| Non-ASCII characters | none in sample |
| Units written in file | none declared in sample |

