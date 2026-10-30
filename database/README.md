# Database foundation

This folder contains a lightweight PostgreSQL schema and synthetic seed dataset for the EV Infra Map India prototype. The SQL does not create or require PostGIS extensions; longitude and latitude are initially stored in numeric columns.

## Tables

- `states`: state or union territory identifiers and names.
- `districts`: district identifiers and names, linked to a state.
- `charger_source_records`: source-specific station observations, including source keys and optional raw attributes.
- `chargers_unified`: deduplicated station records with coordinates, type, source reference, and confidence score.
- `ev_registrations`: EV counts by district, vehicle class, and reporting period.
- `hex_metrics`: demand, charger count, coverage, and gap score by spatial cell and reporting period. `cell_id` is an opaque text key suitable for a future H3 or other cell identifier.
- `candidate_sites`: proposed sites with location, estimated cost, and suitability score.
- `assumptions`: editable named parameters with values, units, descriptions, and provenance.
- `optimizer_runs`: saved budget/objective scenarios, recommended candidate site IDs, and estimated outcomes.

## Initialize PostgreSQL

From this directory, run the schema against an empty database:

```bash
psql -d your_database -f schema.sql
```

Then load the sample records:

```bash
psql -d your_database -f seed.sql
```

The schema creates parent tables before dependent tables. Load `seed.sql` only after `schema.sql`; the seed inserts states and districts before records that reference them. The scripts are intended for a fresh database and are not migration or repeat-safe scripts.

## Illustrative data

All records in `seed.sql` are synthetic examples for development and testing. They are not official government statistics, verified charging station listings, or policy targets. Replace them with sourced and validated data before using outputs for planning decisions.

## Adding PostGIS later

When PostgreSQL and PostGIS are available, enable the extension in the target database with `CREATE EXTENSION postgis;` (subject to the database administrator's permissions). A later migration can add geometry columns such as `geography(Point, 4326)` or `geometry(Point, 4326)`, populate them from the existing longitude/latitude fields using `ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)`, and add GiST indexes. This initial schema deliberately does not enable extensions or require PostGIS.
