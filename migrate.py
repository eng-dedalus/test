"""Oracle to PostgreSQL DWH migration script.

Usage
-----
    python migrate.py [--tables TABLE1,TABLE2] [--mode full|incremental]
                      [--batch-size N] [--dry-run]

All database connection parameters are supplied through environment variables
(see config.py).  Pass --help for a full list of command-line options.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from contextlib import contextmanager
from typing import Generator

import oracledb
import psycopg2
import psycopg2.extras

from config import MigrationConfig, OracleConfig, PostgresConfig
from type_mapping import map_column_type

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------

@contextmanager
def oracle_connection(cfg: OracleConfig) -> Generator[oracledb.Connection, None, None]:
    """Yield an Oracle connection and close it when done."""
    conn = oracledb.connect(user=cfg.user, password=cfg.password, dsn=cfg.dsn)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def postgres_connection(cfg: PostgresConfig) -> Generator[psycopg2.extensions.connection, None, None]:
    """Yield a PostgreSQL connection and close it when done."""
    conn = psycopg2.connect(
        host=cfg.host,
        port=cfg.port,
        dbname=cfg.database,
        user=cfg.user,
        password=cfg.password,
    )
    conn.autocommit = False
    try:
        yield conn
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Schema helpers
# ---------------------------------------------------------------------------

def get_tables(oracle_cur: oracledb.Cursor, schema: str) -> list[str]:
    """Return all user-visible table names in *schema* (upper-cased)."""
    oracle_cur.execute(
        "SELECT table_name FROM all_tables WHERE owner = :owner ORDER BY table_name",
        owner=schema.upper(),
    )
    return [row[0] for row in oracle_cur.fetchall()]


ColumnInfo = tuple[str, str, int | None, int | None, bool]
# (name, oracle_type, precision, scale, nullable)


def get_columns(oracle_cur: oracledb.Cursor, schema: str, table: str) -> list[ColumnInfo]:
    """Return column metadata for *schema*.*table* from Oracle."""
    oracle_cur.execute(
        """
        SELECT column_name,
               data_type,
               data_precision,
               data_scale,
               nullable
        FROM   all_tab_columns
        WHERE  owner      = :owner
        AND    table_name = :table_name
        ORDER  BY column_id
        """,
        owner=schema.upper(),
        table_name=table.upper(),
    )
    return [
        (row[0], row[1], row[2], row[3], row[4] == "Y")
        for row in oracle_cur.fetchall()
    ]


def build_create_table_sql(pg_schema: str, table: str, columns: list[ColumnInfo]) -> str:
    """Generate a PostgreSQL CREATE TABLE statement from Oracle column metadata."""
    col_defs: list[str] = []
    for name, oracle_type, precision, scale, nullable in columns:
        pg_type = map_column_type(oracle_type, precision, scale)
        null_clause = "" if nullable else " NOT NULL"
        col_defs.append(f'    "{name.lower()}" {pg_type}{null_clause}')
    cols_sql = ",\n".join(col_defs)
    return f'CREATE TABLE IF NOT EXISTS "{pg_schema}"."{table.lower()}" (\n{cols_sql}\n);'


# ---------------------------------------------------------------------------
# Migration logic
# ---------------------------------------------------------------------------

def migrate_table(
    oracle_conn: oracledb.Connection,
    pg_conn: psycopg2.extensions.connection,
    oracle_schema: str,
    pg_schema: str,
    table: str,
    batch_size: int,
    mode: str,
    dry_run: bool,
) -> int:
    """Migrate a single table from Oracle to PostgreSQL.

    Returns the total number of rows copied.
    """
    oracle_cur = oracle_conn.cursor()
    pg_cur = pg_conn.cursor()

    # Fetch column metadata from Oracle
    columns = get_columns(oracle_cur, oracle_schema, table)
    if not columns:
        logger.warning("Table %s.%s not found in Oracle; skipping.", oracle_schema, table)
        return 0

    col_names = [col[0] for col in columns]
    pg_col_names = [f'"{c.lower()}"' for c in col_names]

    # Ensure target table exists in PostgreSQL
    create_sql = build_create_table_sql(pg_schema, table, columns)
    logger.debug("DDL:\n%s", create_sql)
    if not dry_run:
        pg_cur.execute(f'CREATE SCHEMA IF NOT EXISTS "{pg_schema}";')
        pg_cur.execute(create_sql)
        pg_conn.commit()

    # Truncate on full reload
    if mode == "full" and not dry_run:
        pg_cur.execute(f'TRUNCATE TABLE "{pg_schema}"."{table.lower()}";')
        pg_conn.commit()

    # Stream data from Oracle and bulk-insert into PostgreSQL
    # Column names are double-quoted to handle reserved words and special characters.
    quoted_col_names = [f'"{c}"' for c in col_names]
    select_sql = (
        f'SELECT {", ".join(quoted_col_names)} '
        f'FROM "{oracle_schema}"."{table}"'
    )
    oracle_cur.arraysize = batch_size
    oracle_cur.execute(select_sql)

    insert_sql = (
        f'INSERT INTO "{pg_schema}"."{table.lower()}" '
        f"({', '.join(pg_col_names)}) "
        f"VALUES %s"
    )

    total_rows = 0
    while True:
        rows = oracle_cur.fetchmany(batch_size)
        if not rows:
            break
        total_rows += len(rows)
        if not dry_run:
            psycopg2.extras.execute_values(pg_cur, insert_sql, rows, page_size=batch_size)
            pg_conn.commit()
        logger.debug("  … %d rows inserted into %s.%s", total_rows, pg_schema, table)

    oracle_cur.close()
    pg_cur.close()
    return total_rows


def run_migration(cfg: MigrationConfig, dry_run: bool = False) -> dict[str, int]:
    """Run the full migration according to *cfg*.

    Returns a dict mapping table name → row count.
    """
    results: dict[str, int] = {}

    with oracle_connection(cfg.oracle) as oracle_conn, \
         postgres_connection(cfg.postgres) as pg_conn:

        oracle_cur = oracle_conn.cursor()

        # Resolve which tables to migrate
        if cfg.tables:
            tables = [t.upper() for t in cfg.tables]
        else:
            tables = get_tables(oracle_cur, cfg.oracle.user)
            logger.info("Discovered %d tables in schema %s", len(tables), cfg.oracle.user)

        oracle_cur.close()

        for table in tables:
            logger.info("Migrating table %s …", table)
            start = time.monotonic()
            rows = migrate_table(
                oracle_conn=oracle_conn,
                pg_conn=pg_conn,
                oracle_schema=cfg.oracle.user,
                pg_schema=cfg.postgres.schema,
                table=table,
                batch_size=cfg.batch_size,
                mode=cfg.mode,
                dry_run=dry_run,
            )
            elapsed = time.monotonic() - start
            logger.info(
                "  ✓ %s – %d rows in %.1f s (%.0f rows/s)",
                table,
                rows,
                elapsed,
                rows / elapsed if elapsed > 0 else 0,
            )
            results[table] = rows

    return results


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Migrate tables from Oracle DWH to PostgreSQL."
    )
    parser.add_argument(
        "--tables",
        default="",
        help="Comma-separated list of tables to migrate (default: all tables).",
    )
    parser.add_argument(
        "--mode",
        choices=["full", "incremental"],
        default=None,
        help="Migration mode: 'full' (truncate+reload) or 'incremental'. "
             "Overrides MIGRATION_MODE env var.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Number of rows per batch. Overrides MIGRATION_BATCH_SIZE env var.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Connect to both databases and enumerate tables/columns but do not write data.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    cfg = MigrationConfig.from_env()

    # CLI arguments override environment variables
    if args.tables:
        cfg = cfg.__class__(
            oracle=cfg.oracle,
            postgres=cfg.postgres,
            tables=[t.strip() for t in args.tables.split(",") if t.strip()],
            batch_size=args.batch_size or cfg.batch_size,
            mode=args.mode or cfg.mode,
            log_level=cfg.log_level,
        )
    elif args.mode or args.batch_size:
        cfg = cfg.__class__(
            oracle=cfg.oracle,
            postgres=cfg.postgres,
            tables=cfg.tables,
            batch_size=args.batch_size or cfg.batch_size,
            mode=args.mode or cfg.mode,
            log_level=cfg.log_level,
        )

    logging.basicConfig(
        level=getattr(logging, cfg.log_level, logging.INFO),
        format="%(asctime)s %(levelname)-8s %(name)s – %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    if args.dry_run:
        logger.info("DRY RUN – no data will be written to PostgreSQL.")

    logger.info(
        "Starting migration: Oracle %s → PostgreSQL %s (mode=%s, batch=%d)",
        cfg.oracle.dsn,
        cfg.postgres.database,
        cfg.mode,
        cfg.batch_size,
    )

    results = run_migration(cfg, dry_run=args.dry_run)

    total = sum(results.values())
    logger.info("Migration complete. %d tables, %d total rows.", len(results), total)
    return 0


if __name__ == "__main__":
    sys.exit(main())
