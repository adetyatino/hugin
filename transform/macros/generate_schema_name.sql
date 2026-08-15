{#
  Use the schema a model asks for, verbatim.

  dbt's default prefixes the profile's schema onto the model's, which would name
  the layers silver_silver, silver_gold and silver_mart. SPEC.md sections 4.2 to
  4.4 name them silver, gold and mart, and a table whose schema does not match
  the document describing it is a small lie that every later query has to know
  about.

  The default still applies where a model asks for nothing, so a stray model
  lands in the profile's schema rather than somewhere unnamed.
#}

{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
