{#
  SCD Type 2, as a macro.

  dim_wellbore is SCD2 because the operator label attached to a wellbore
  changes: the archives carry Statoil, StatoilHydro and Statoil again, and the
  same physical hole is labelled differently depending on which system wrote it
  down and when. SPEC.md section 4.3 makes tracking that the dimension's job.

  What makes this dataset's SCD2 unusual is that the versions are not a history
  of edits captured over time — there is no change-data-capture stream here.
  They are *disagreements between source systems* about the same wellbore,
  ordered by the evidence each system provides. So the macro takes an explicit
  ordering column rather than assuming an updated_at, and the caller decides
  what "later" means.

  A row is emitted per (business key, run of unchanged tracked attributes), with
  valid_from / valid_to / is_current. Consecutive versions carrying the same
  tracked values are collapsed: two sources agreeing is one version, not two.
#}

{% macro hugin_scd2(
    relation,
    business_key,
    tracked_columns,
    order_column,
    valid_from_column='valid_from',
    valid_to_column='valid_to',
    current_flag='is_current',
    surrogate_key='wellbore_key'
) -%}

with source_versions as (
    select
        {{ business_key }} as business_key,
        {% for column in tracked_columns -%}
        {{ column }},
        {% endfor -%}
        {{ order_column }} as version_order
    from {{ relation }}
    where {{ business_key }} is not null
),

-- A version boundary is where a tracked value differs from the previous row's.
-- Without this, a wellbore named identically by six systems would get six
-- versions, and the dimension would grow with the number of sources rather
-- than with the number of real changes.
flagged as (
    select
        *,
        case
            when lag(
                {% for column in tracked_columns -%}
                coalesce({{ hugin_as_text(column) }}, '')
                {%- if not loop.last %} || '|' || {% endif %}
                {%- endfor %}
            ) over (partition by business_key order by version_order) is null
              then 1
            when lag(
                {% for column in tracked_columns -%}
                coalesce({{ hugin_as_text(column) }}, '')
                {%- if not loop.last %} || '|' || {% endif %}
                {%- endfor %}
            ) over (partition by business_key order by version_order)
              <> (
                {% for column in tracked_columns -%}
                coalesce({{ hugin_as_text(column) }}, '')
                {%- if not loop.last %} || '|' || {% endif %}
                {%- endfor %}
              )
              then 1
            else 0
        end as is_new_version
    from source_versions
),

numbered as (
    select
        *,
        sum(is_new_version) over (
            partition by business_key
            order by version_order
            rows between unbounded preceding and current row
        ) as version_number
    from flagged
),

collapsed as (
    select
        business_key,
        version_number,
        {% for column in tracked_columns -%}
        min({{ column }}) as {{ column }},
        {% endfor -%}
        min(version_order) as {{ valid_from_column }},
        max(version_order) as version_last_seen
    from numbered
    group by business_key, version_number
),

versioned as (
    select
        *,
        lead({{ valid_from_column }}) over (
            partition by business_key order by version_number
        ) as next_version_from
    from collapsed
)

select
    {{ hugin_surrogate_key(['business_key', 'version_number']) }} as {{ surrogate_key }},
    business_key,
    version_number,
    {% for column in tracked_columns -%}
    {{ column }},
    {% endfor -%}
    {{ valid_from_column }},
    -- The current version has no end. An end date of 9999-12-31 would make
    -- every between-join silently include it, which is convenient right up
    -- until someone asks what it means.
    next_version_from as {{ valid_to_column }},
    case when next_version_from is null then true else false end as {{ current_flag }}
from versioned

{%- endmacro %}
