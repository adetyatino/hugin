-- Iceberg's JDBC catalog tables, created up front.
--
-- Without them Trino fails every statement with "Cannot check and eventually
-- update SQL schema". The reason is visible only in the PostgreSQL log:
--
--   ERROR: relation "iceberg_tables" does not exist
--   STATEMENT: ALTER TABLE iceberg_tables ADD COLUMN iceberg_type VARCHAR(5)
--
-- The catalog runs its V1 -> V2 migration before its create-if-missing path,
-- so it tries to alter a table it has not made yet. Creating the V1 shape here
-- gives the migration something to migrate; it then adds iceberg_type itself.
\connect iceberg_catalog

CREATE TABLE IF NOT EXISTS iceberg_tables (
    catalog_name               VARCHAR(255) NOT NULL,
    table_namespace            VARCHAR(255) NOT NULL,
    table_name                 VARCHAR(255) NOT NULL,
    metadata_location          VARCHAR(1000),
    previous_metadata_location VARCHAR(1000),
    PRIMARY KEY (catalog_name, table_namespace, table_name)
);

CREATE TABLE IF NOT EXISTS iceberg_namespace_properties (
    catalog_name   VARCHAR(255) NOT NULL,
    namespace      VARCHAR(255) NOT NULL,
    property_key   VARCHAR(255) NOT NULL,
    property_value VARCHAR(1000),
    PRIMARY KEY (catalog_name, namespace, property_key)
);
