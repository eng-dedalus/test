# Oracle → PostgreSQL DWH Migration Tool

A Python script that migrates tables from an Oracle Data Warehouse to PostgreSQL,
with a daily GitHub Actions schedule.

## Project structure

```
├── migrate.py           – Main migration script
├── type_mapping.py      – Oracle-to-PostgreSQL type conversion
├── config.py            – Configuration via environment variables
├── requirements.txt     – Python dependencies
├── tests/
│   ├── test_type_mapping.py
│   ├── test_config.py
│   └── test_migrate.py
└── .github/
    └── workflows/
        ├── daily_migration.yml  – Scheduled migration (daily @ 02:00 UTC)
        └── ci.yml               – CI: run tests on every push / PR
```

## Quick start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Set environment variables

| Variable | Description | Default |
|---|---|---|
| `ORACLE_HOST` | Oracle server hostname | **required** |
| `ORACLE_PORT` | Oracle listener port | `1521` |
| `ORACLE_SERVICE` | Oracle service name or SID | **required** |
| `ORACLE_USER` | Oracle schema/user | **required** |
| `ORACLE_PASSWORD` | Oracle password | **required** |
| `PG_HOST` | PostgreSQL hostname | **required** |
| `PG_PORT` | PostgreSQL port | `5432` |
| `PG_DATABASE` | PostgreSQL database name | **required** |
| `PG_SCHEMA` | Target PostgreSQL schema | `public` |
| `PG_USER` | PostgreSQL user | **required** |
| `PG_PASSWORD` | PostgreSQL password | **required** |
| `MIGRATION_TABLES` | Comma-separated table list (empty = all) | *(all tables)* |
| `MIGRATION_BATCH_SIZE` | Rows fetched per batch | `10000` |
| `MIGRATION_MODE` | `full` (truncate+reload) or `incremental` | `full` |
| `LOG_LEVEL` | Python logging level | `INFO` |

### 3. Run the migration

```bash
# Migrate all tables (full reload)
python migrate.py

# Migrate specific tables
python migrate.py --tables ORDERS,CUSTOMERS,PRODUCTS

# Incremental mode (append only)
python migrate.py --mode incremental

# Dry run – connect to both DBs but write nothing
python migrate.py --dry-run
```

## GitHub Actions

### Daily schedule

The workflow `.github/workflows/daily_migration.yml` runs automatically every day
at **02:00 UTC** (`cron: "0 2 * * *"`).

You can also trigger it manually from the **Actions** tab, optionally overriding
the table list, mode, and dry-run flag.

### Secrets required

Add the following secrets to your repository (or the `production` environment):

- `ORACLE_HOST`, `ORACLE_PORT`, `ORACLE_SERVICE`, `ORACLE_USER`, `ORACLE_PASSWORD`
- `PG_HOST`, `PG_PORT`, `PG_DATABASE`, `PG_USER`, `PG_PASSWORD`

### CI

The workflow `.github/workflows/ci.yml` runs unit tests on every push and pull
request.

## Running tests

```bash
pytest tests/ -v
```

## How it works

1. **Schema discovery** – the script queries `ALL_TAB_COLUMNS` in Oracle to
   retrieve the full column list (name, data type, precision, scale, nullability).
2. **Type mapping** – Oracle types are converted to the closest PostgreSQL
   equivalents (see `type_mapping.py`).
3. **DDL** – `CREATE TABLE IF NOT EXISTS` is executed in PostgreSQL.
4. **Data transfer** – rows are streamed from Oracle in configurable batches and
   bulk-inserted into PostgreSQL using `psycopg2.extras.execute_values`.
5. **Full vs incremental** – in `full` mode the target table is truncated before
   loading; in `incremental` mode rows are appended.