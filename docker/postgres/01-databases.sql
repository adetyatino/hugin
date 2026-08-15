-- Three databases in one instance, because they have nothing to do with each
-- other and only the middle one is PostGIS's business:
--
--   iceberg    the PostGIS-enabled database (BR-10 geometry, later)
--   iceberg_catalog  Iceberg's JDBC catalog tables, created by Trino
--   metabase   Metabase's own application state
--
-- The catalog gets its own database rather than sharing the PostGIS one: the
-- postgis image installs its extensions and the tiger schemas into POSTGRES_DB,
-- and Iceberg's schema check has to run against a database it fully owns.
SELECT 'CREATE DATABASE iceberg_catalog OWNER ' || current_user
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'iceberg_catalog')\gexec

SELECT 'CREATE DATABASE metabase OWNER ' || current_user
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'metabase')\gexec

SELECT 'CREATE DATABASE airflow OWNER ' || current_user
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'airflow')\gexec
