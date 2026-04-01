"""Tests for migrate.py – uses mocks to avoid real DB connections."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch, call

import migrate
from migrate import (
    build_create_table_sql,
    get_columns,
    get_tables,
    migrate_table,
)


# ---------------------------------------------------------------------------
# build_create_table_sql
# ---------------------------------------------------------------------------

class TestBuildCreateTableSql:
    def test_basic_table(self):
        columns = [
            ("ID", "NUMBER", 10, 0, False),
            ("NAME", "VARCHAR2", 100, None, True),
            ("CREATED_AT", "DATE", None, None, True),
        ]
        sql = build_create_table_sql("public", "ORDERS", columns)
        assert 'CREATE TABLE IF NOT EXISTS "public"."orders"' in sql
        assert '"id" BIGINT NOT NULL' in sql
        assert '"name" VARCHAR(100)' in sql
        assert '"created_at" TIMESTAMP' in sql

    def test_nullable_column_has_no_not_null(self):
        columns = [("NOTES", "CLOB", None, None, True)]
        sql = build_create_table_sql("public", "T", columns)
        assert "NOT NULL" not in sql

    def test_non_nullable_column_has_not_null(self):
        columns = [("CODE", "CHAR", 3, None, False)]
        sql = build_create_table_sql("public", "T", columns)
        assert '"code" CHAR(3) NOT NULL' in sql


# ---------------------------------------------------------------------------
# get_tables
# ---------------------------------------------------------------------------

class TestGetTables:
    def test_returns_table_names(self):
        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = [("ORDERS",), ("CUSTOMERS",)]
        result = get_tables(mock_cur, "DWH")
        assert result == ["ORDERS", "CUSTOMERS"]
        mock_cur.execute.assert_called_once()
        # Schema should be upper-cased in query
        args = mock_cur.execute.call_args
        assert args[1]["owner"] == "DWH"


# ---------------------------------------------------------------------------
# get_columns
# ---------------------------------------------------------------------------

class TestGetColumns:
    def test_returns_column_info(self):
        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = [
            ("ID", "NUMBER", 10, 0, "N"),
            ("NAME", "VARCHAR2", 200, None, "Y"),
        ]
        result = get_columns(mock_cur, "DWH", "ORDERS")
        assert len(result) == 2
        assert result[0] == ("ID", "NUMBER", 10, 0, False)
        assert result[1] == ("NAME", "VARCHAR2", 200, None, True)


# ---------------------------------------------------------------------------
# migrate_table – dry run
# ---------------------------------------------------------------------------

class TestMigrateTableDryRun:
    def _make_oracle_conn(self, columns, rows):
        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = columns
        mock_cur.fetchmany.side_effect = [rows, []]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        return mock_conn, mock_cur

    def test_dry_run_does_not_execute_write(self):
        columns = [("ID", "NUMBER", 10, 0, "N"), ("VAL", "VARCHAR2", 50, None, "Y")]
        rows = [(1, "alpha"), (2, "beta")]

        mock_ora_cur = MagicMock()
        # get_columns call
        mock_ora_cur.fetchall.return_value = columns
        # data fetch
        mock_ora_cur.fetchmany.side_effect = [rows, []]
        mock_ora_conn = MagicMock()
        mock_ora_conn.cursor.return_value = mock_ora_cur

        mock_pg_cur = MagicMock()
        mock_pg_conn = MagicMock()
        mock_pg_conn.cursor.return_value = mock_pg_cur

        count = migrate_table(
            oracle_conn=mock_ora_conn,
            pg_conn=mock_pg_conn,
            oracle_schema="DWH",
            pg_schema="public",
            table="ORDERS",
            batch_size=1000,
            mode="full",
            dry_run=True,
        )

        assert count == 2
        # In dry-run mode, no DDL or DML should be executed on Postgres
        mock_pg_cur.execute.assert_not_called()
        mock_pg_conn.commit.assert_not_called()

    def test_empty_table_skipped_gracefully(self):
        mock_ora_cur = MagicMock()
        mock_ora_cur.fetchall.return_value = []  # no columns → table not found
        mock_ora_conn = MagicMock()
        mock_ora_conn.cursor.return_value = mock_ora_cur

        mock_pg_conn = MagicMock()

        count = migrate_table(
            oracle_conn=mock_ora_conn,
            pg_conn=mock_pg_conn,
            oracle_schema="DWH",
            pg_schema="public",
            table="MISSING_TABLE",
            batch_size=1000,
            mode="full",
            dry_run=True,
        )
        assert count == 0


# ---------------------------------------------------------------------------
# CLI argument parsing
# ---------------------------------------------------------------------------

class TestParseArgs:
    def test_defaults(self):
        args = migrate.parse_args([])
        assert args.tables == ""
        assert args.mode is None
        assert args.batch_size is None
        assert args.dry_run is False

    def test_dry_run_flag(self):
        args = migrate.parse_args(["--dry-run"])
        assert args.dry_run is True

    def test_tables_and_mode(self):
        args = migrate.parse_args(["--tables", "A,B", "--mode", "incremental"])
        assert args.tables == "A,B"
        assert args.mode == "incremental"
