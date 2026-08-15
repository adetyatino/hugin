-- A DDR row may carry a null activity_seq only if the report it came from
-- declared no activities at all.
--
-- Two reports in the delivery do exactly that:
-- 15_9_F_11_T2_2013_04_01.xml and 15_9_F_1_C_2014_03_31.xml. Both are complete
-- reports - report number, status, survey stations, fluid, stratigraphy - with
-- no <activity> element anywhere in the document. The reader emits one row so
-- the report is not lost, and every activity-shaped column on that row is null
-- because the report has nothing to put in them.
--
-- This replaces a blanket not_null on activity_seq. The blanket test asserted
-- something the data does not support - that every drill report contains an
-- activity breakdown - and passing it would have meant dropping two real
-- reports. The narrower assertion is the one worth making: a null sequence is
-- allowed, but only on a row that is empty of activity in every other respect.
-- A parser that started losing sequence numbers on real activities still fails
-- here.

select
    source_identifier,
    report_date,
    activity_seq,
    phase,
    activity_state,
    activity_code,
    activity_md_m
from {{ ref('silver_ddr_activity') }}
where activity_seq is null
  and (
      phase is not null
      or activity_state is not null
      or activity_code is not null
      or activity_md_m is not null
      or activity_started_at is not null
  )
