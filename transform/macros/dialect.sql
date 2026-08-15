{#
  Every place Trino, DuckDB and Databricks SQL disagree, in one file.

  CLAUDE.md forbids `if target.type == ...` inside a model. The reason is not
  style: a branch inside SQL is only exercised on the target you happen to be
  running, so the other target's version is never compiled and rots unseen.
  adapter.dispatch resolves at compile time on both, so `dbt compile --target
  duckdb` fails immediately if the DuckDB implementation is wrong.

  Adding a target means adding an implementation here and nowhere else. That is
  the portability claim in SPEC.md section 12, made mechanical.

  The third target arrived after the first two and is the reason several macros
  below exist at all: Trino and DuckDB happen to agree on strpos, date_diff and
  an unlengthed varchar, so those were written inline in models where they were
  needed. Databricks SQL agrees with neither, which exposed them. Two engines
  agreeing is not portability — it is a coincidence that has not been tested
  yet. See docs/portability-report.md for the audit that found each one.
#}


{# -------------------------------------------------------------------------
   Text.

   Bronze is varchar throughout (SPEC.md section 3), so silver casts to text
   constantly — inside surrogate keys, inside number parsing, inside the SCD2
   change detector. Trino and DuckDB both accept `cast(x as varchar)` with no
   length. Spark's parser rejects an unlengthed VARCHAR outright, and its text
   type is STRING.

   This matters more than it looks: hugin_surrogate_key hashes the result, so
   the cast is inside every surrogate key in the warehouse. Getting it wrong on
   one engine does not produce an error there, it produces different keys.
   ------------------------------------------------------------------------- #}

{% macro hugin_as_text(column) -%}
  {{ return(adapter.dispatch('hugin_as_text', 'hugin')(column)) }}
{%- endmacro %}

{% macro default__hugin_as_text(column) -%}
  cast({{ column }} as varchar)
{%- endmacro %}

{% macro databricks__hugin_as_text(column) -%}
  cast({{ column }} as string)
{%- endmacro %}

{# -------------------------------------------------------------------------
   Surrogate keys.

   SPEC.md section 9: surrogate keys end _key. A hash of the business key gives
   a deterministic key with no sequence to coordinate, which matters because
   the same model must produce the same keys on two engines.
   ------------------------------------------------------------------------- #}

{% macro hugin_surrogate_key(columns) -%}
  {{ return(adapter.dispatch('hugin_surrogate_key', 'hugin')(columns)) }}
{%- endmacro %}

{% macro default__hugin_surrogate_key(columns) -%}
  {%- set parts = [] -%}
  {%- for column in columns -%}
    {%- do parts.append("coalesce(" ~ hugin_as_text(column) ~ ", '')") -%}
  {%- endfor -%}
  md5({{ parts | join(" || '|' || ") }})
{%- endmacro %}

{% macro trino__hugin_surrogate_key(columns) -%}
  {#- Trino's md5 takes varbinary and returns varbinary, so the value has to be
      encoded on the way in and hexed on the way out to match DuckDB's text. -#}
  {%- set parts = [] -%}
  {%- for column in columns -%}
    {%- do parts.append("coalesce(" ~ hugin_as_text(column) ~ ", '')") -%}
  {%- endfor -%}
  lower(to_hex(md5(to_utf8({{ parts | join(" || '|' || ") }}))))
{%- endmacro %}


{# -------------------------------------------------------------------------
   Excel date serials.

   Production's daily sheet stores dates as serials counted from 1899-12-30 —
   see hugin.ingestion.prod for why that epoch reproduces Excel's 1900 leap year
   bug. Bronze keeps the serial as written; this is where it becomes a date.
   ------------------------------------------------------------------------- #}

{% macro hugin_date_from_excel_serial(column) -%}
  {{ return(adapter.dispatch('hugin_date_from_excel_serial', 'hugin')(column)) }}
{%- endmacro %}

{% macro default__hugin_date_from_excel_serial(column) -%}
  (date '1899-12-30' + cast(cast(try_cast({{ column }} as double) as integer) as integer))
{%- endmacro %}

{% macro trino__hugin_date_from_excel_serial(column) -%}
  date_add('day', cast(try_cast({{ column }} as double) as integer), date '1899-12-30')
{%- endmacro %}

{% macro databricks__hugin_date_from_excel_serial(column) -%}
  {#- date_add takes its arguments the other way round from Trino's. Spark 3.5
      turns out to accept `date '1899-12-30' + 41000` even with ANSI mode on, so
      the default would have worked - measured, not assumed. Dispatched anyway
      because date-plus-integer is the arithmetic ANSI SQL does not define, and
      a warehouse that tightens it later should not silently change dim_date. -#}
  date_add(date '1899-12-30', cast(try_cast({{ column }} as double) as int))
{%- endmacro %}


{# -------------------------------------------------------------------------
   Timestamps written with an offset, e.g. 2016-08-04T00:00:00+02:00.

   The date part is taken in the offset the source wrote, because the file name
   agrees with the local date and converting to UTC moves a third of the daily
   drilling reports to the previous day.
   ------------------------------------------------------------------------- #}

{% macro hugin_date_from_iso(column) -%}
  {{ return(adapter.dispatch('hugin_date_from_iso', 'hugin')(column)) }}
{%- endmacro %}

{% macro default__hugin_date_from_iso(column) -%}
  try_cast(substr({{ column }}, 1, 10) as date)
{%- endmacro %}

{% macro trino__hugin_date_from_iso(column) -%}
  try_cast(substr({{ column }}, 1, 10) as date)
{%- endmacro %}


{# -------------------------------------------------------------------------
   Numbers as the sources write them.

   Bronze holds every value as varchar, so silver is where text becomes a
   number. Two hazards, both real in this delivery:

   * a decimal comma. The production workbook has none — measured, all 15,635
     rows — but the ASCII log products do use one, and a silver layer that
     assumes a point would turn 1,5 into NULL rather than 1.5.
   * a sentinel. Handled separately by hugin_null_if_sentinel, because the
     sentinel is per file rather than global (BR-08).
   ------------------------------------------------------------------------- #}

{% macro hugin_to_number(column) -%}
  {{ return(adapter.dispatch('hugin_to_number', 'hugin')(column)) }}
{%- endmacro %}

{% macro default__hugin_to_number(column) -%}
  try_cast(
    nullif(
      replace(
        replace(trim({{ hugin_as_text(column) }}), ' ', ''),
        ',', '.'
      ),
      ''
    ) as double
  )
{%- endmacro %}


{# -------------------------------------------------------------------------
   BR-08: the sentinel is a property of the file, not a constant.

   The delivery declares -999.25, -9999, -999.2500 and -999.25000, each in the
   file that uses it. This compares the parsed value against the parsed
   sentinel the same row carries, so a file declaring something new needs no
   code change here.
   ------------------------------------------------------------------------- #}

{% macro hugin_null_if_sentinel(value_column, sentinel_column) -%}
  {{ return(adapter.dispatch('hugin_null_if_sentinel', 'hugin')(value_column, sentinel_column)) }}
{%- endmacro %}

{% macro default__hugin_null_if_sentinel(value_column, sentinel_column) -%}
  case
    when {{ hugin_to_number(sentinel_column) }} is not null
     and {{ hugin_to_number(value_column) }} = {{ hugin_to_number(sentinel_column) }}
      then cast(null as double)
    {#- lasio replaces the declared sentinel with NaN when it reads a LAS 2.0
        file, so the string 'nan' reaching bronze means the same thing. -#}
    when lower(trim({{ hugin_as_text(value_column) }})) in ('nan', '-nan', 'null')
      then cast(null as double)
    else {{ hugin_to_number(value_column) }}
  end
{%- endmacro %}


{# -------------------------------------------------------------------------
   Division that does not fail on a zero denominator. Water cut and GOR both
   divide by a volume that is legitimately zero on a shut-in day.
   ------------------------------------------------------------------------- #}

{% macro hugin_safe_divide(numerator, denominator) -%}
  {{ return(adapter.dispatch('hugin_safe_divide', 'hugin')(numerator, denominator)) }}
{%- endmacro %}

{% macro default__hugin_safe_divide(numerator, denominator) -%}
  case when coalesce({{ denominator }}, 0) = 0 then cast(null as double)
       else cast({{ numerator }} as double) / cast({{ denominator }} as double)
  end
{%- endmacro %}


{# -------------------------------------------------------------------------
   A month key as an integer, e.g. 200806. Both engines have date_trunc, but
   composing the key from parts is clearer than formatting and parsing.
   ------------------------------------------------------------------------- #}

{% macro hugin_month_key(date_column) -%}
  {{ return(adapter.dispatch('hugin_month_key', 'hugin')(date_column)) }}
{%- endmacro %}

{% macro default__hugin_month_key(date_column) -%}
  (extract(year from {{ date_column }}) * 100 + extract(month from {{ date_column }}))
{%- endmacro %}

{% macro hugin_date_key(date_column) -%}
  {{ return(adapter.dispatch('hugin_date_key', 'hugin')(date_column)) }}
{%- endmacro %}

{% macro default__hugin_date_key(date_column) -%}
  (extract(year from {{ date_column }}) * 10000
   + extract(month from {{ date_column }}) * 100
   + extract(day from {{ date_column }}))
{%- endmacro %}


{# -------------------------------------------------------------------------
   A bounded series of dates, for dim_date. Trino has sequence(); DuckDB has
   generate_series(). Neither spells it the other's way.
   ------------------------------------------------------------------------- #}

{% macro hugin_date_spine(start_date, end_date) -%}
  {{ return(adapter.dispatch('hugin_date_spine', 'hugin')(start_date, end_date)) }}
{%- endmacro %}

{% macro default__hugin_date_spine(start_date, end_date) -%}
  select unnest(generate_series(date '{{ start_date }}', date '{{ end_date }}', interval 1 day))::date as calendar_date
{%- endmacro %}

{% macro trino__hugin_date_spine(start_date, end_date) -%}
  select calendar_date
  from unnest(sequence(date '{{ start_date }}', date '{{ end_date }}', interval '1' day)) as t(calendar_date)
{%- endmacro %}

{% macro databricks__hugin_date_spine(start_date, end_date) -%}
  {#- Spark has sequence() like Trino but expands an array with explode()
      rather than unnest(), and takes the step as a plural interval. -#}
  select explode(sequence(date '{{ start_date }}', date '{{ end_date }}', interval 1 day)) as calendar_date
{%- endmacro %}


{# -------------------------------------------------------------------------
   Position of a substring.

   silver_wellbore_identity splits '15/9-F-15 D' into well and sidetrack at the
   space. Trino and DuckDB both spell that strpos(haystack, needle); Spark has
   no strpos at all, and its locate() takes the arguments the other way round.
   Both return 0 for "not found", which is what the callers test.
   ------------------------------------------------------------------------- #}

{% macro hugin_strpos(haystack, needle) -%}
  {{ return(adapter.dispatch('hugin_strpos', 'hugin')(haystack, needle)) }}
{%- endmacro %}

{% macro default__hugin_strpos(haystack, needle) -%}
  strpos({{ haystack }}, {{ needle }})
{%- endmacro %}

{% macro databricks__hugin_strpos(haystack, needle) -%}
  locate({{ needle }}, {{ haystack }})
{%- endmacro %}


{# -------------------------------------------------------------------------
   Whole seconds between two timestamps.

   fct_drilling_state divides depth change by elapsed time, so this sits under
   the rate that BR-06 classifies on. Trino and DuckDB share
   date_diff('second', a, b). Databricks has no date_diff with that signature —
   its two-argument datediff returns whole days, which would silently give zero
   for every telemetry sample and send every state to STATIC. A wrong answer,
   not an error, which is why this one is dispatched rather than left inline.
   ------------------------------------------------------------------------- #}

{% macro hugin_seconds_between(start_ts, end_ts) -%}
  {{ return(adapter.dispatch('hugin_seconds_between', 'hugin')(start_ts, end_ts)) }}
{%- endmacro %}

{% macro default__hugin_seconds_between(start_ts, end_ts) -%}
  date_diff('second', {{ start_ts }}, {{ end_ts }})
{%- endmacro %}

{% macro databricks__hugin_seconds_between(start_ts, end_ts) -%}
  timestampdiff(SECOND, {{ start_ts }}, {{ end_ts }})
{%- endmacro %}


{# -------------------------------------------------------------------------
   A trailing time window in a RANGE frame.

   The ten-minute block-travel window in fct_drilling_state. Trino and DuckDB
   take the ANSI `interval '10' minute`; Spark's parser wants an unquoted
   number and a plural unit. The window length itself stays in the model, where
   BR-06 can be read against it — only the spelling lives here.
   ------------------------------------------------------------------------- #}

{% macro hugin_minutes_preceding(minutes) -%}
  {{ return(adapter.dispatch('hugin_minutes_preceding', 'hugin')(minutes)) }}
{%- endmacro %}

{% macro default__hugin_minutes_preceding(minutes) -%}
  interval '{{ minutes }}' minute preceding
{%- endmacro %}

{% macro databricks__hugin_minutes_preceding(minutes) -%}
  interval {{ minutes }} minutes preceding
{%- endmacro %}
