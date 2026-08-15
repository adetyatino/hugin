-- The facility is written with a Scandinavian ligature, and it has now
-- travelled through an xlsx shared-string table, Parquet, MinIO, Iceberg and
-- two query engines. Somewhere in that chain a wrong encoding turns it into two
-- characters or a replacement mark, and nothing else in the build would fail.

select facility_code, facility_name
from {{ ref('dim_facility') }}
where facility_name is not null
  and (
        strpos(facility_name, chr(65533)) > 0
     or strpos(facility_name, '?') > 0
     or strpos(upper(facility_name), chr(198)) = 0
  )
