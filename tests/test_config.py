"""Tests for the configuration module."""

import os
import pytest

from config import MigrationConfig, OracleConfig, PostgresConfig


ORACLE_ENV = {
    "ORACLE_HOST": "oracle-host",
    "ORACLE_PORT": "1521",
    "ORACLE_SERVICE": "ORCL",
    "ORACLE_USER": "dwh_user",
    "ORACLE_PASSWORD": "secret",
}

PG_ENV = {
    "PG_HOST": "pg-host",
    "PG_PORT": "5432",
    "PG_DATABASE": "dwh_db",
    "PG_USER": "pg_user",
    "PG_PASSWORD": "pg_secret",
}


class TestOracleConfig:
    def test_from_env_success(self, monkeypatch):
        for k, v in ORACLE_ENV.items():
            monkeypatch.setenv(k, v)
        cfg = OracleConfig.from_env()
        assert cfg.host == "oracle-host"
        assert cfg.port == 1521
        assert cfg.service == "ORCL"
        assert cfg.dsn == "oracle-host:1521/ORCL"

    def test_missing_required_raises(self, monkeypatch):
        monkeypatch.delenv("ORACLE_HOST", raising=False)
        with pytest.raises(EnvironmentError, match="ORACLE_HOST"):
            OracleConfig.from_env()

    def test_default_port(self, monkeypatch):
        for k, v in ORACLE_ENV.items():
            monkeypatch.setenv(k, v)
        monkeypatch.delenv("ORACLE_PORT", raising=False)
        cfg = OracleConfig.from_env()
        assert cfg.port == 1521


class TestPostgresConfig:
    def test_from_env_success(self, monkeypatch):
        for k, v in PG_ENV.items():
            monkeypatch.setenv(k, v)
        cfg = PostgresConfig.from_env()
        assert cfg.host == "pg-host"
        assert cfg.port == 5432
        assert cfg.database == "dwh_db"

    def test_missing_required_raises(self, monkeypatch):
        monkeypatch.delenv("PG_HOST", raising=False)
        with pytest.raises(EnvironmentError, match="PG_HOST"):
            PostgresConfig.from_env()

    def test_default_port(self, monkeypatch):
        for k, v in PG_ENV.items():
            monkeypatch.setenv(k, v)
        monkeypatch.delenv("PG_PORT", raising=False)
        cfg = PostgresConfig.from_env()
        assert cfg.port == 5432


class TestMigrationConfig:
    def _set_all_env(self, monkeypatch):
        for k, v in {**ORACLE_ENV, **PG_ENV}.items():
            monkeypatch.setenv(k, v)

    def test_defaults(self, monkeypatch):
        self._set_all_env(monkeypatch)
        monkeypatch.delenv("MIGRATION_TABLES", raising=False)
        monkeypatch.delenv("MIGRATION_BATCH_SIZE", raising=False)
        monkeypatch.delenv("MIGRATION_MODE", raising=False)
        cfg = MigrationConfig.from_env()
        assert cfg.tables == []
        assert cfg.batch_size == 10_000
        assert cfg.mode == "full"

    def test_custom_tables(self, monkeypatch):
        self._set_all_env(monkeypatch)
        monkeypatch.setenv("MIGRATION_TABLES", "ORDERS, CUSTOMERS, PRODUCTS")
        cfg = MigrationConfig.from_env()
        assert cfg.tables == ["ORDERS", "CUSTOMERS", "PRODUCTS"]

    def test_incremental_mode(self, monkeypatch):
        self._set_all_env(monkeypatch)
        monkeypatch.setenv("MIGRATION_MODE", "incremental")
        cfg = MigrationConfig.from_env()
        assert cfg.mode == "incremental"

    def test_invalid_mode_raises(self, monkeypatch):
        self._set_all_env(monkeypatch)
        monkeypatch.setenv("MIGRATION_MODE", "delta")
        with pytest.raises(ValueError, match="MIGRATION_MODE"):
            MigrationConfig.from_env()
