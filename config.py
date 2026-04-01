"""Configuration helpers for the Oracle → PostgreSQL migration tool.

All sensitive connection parameters are read from environment variables so
that no credentials are stored in source code or configuration files.

Required environment variables
--------------------------------
Oracle (source)
    ORACLE_HOST       – hostname or IP of the Oracle server
    ORACLE_PORT       – listener port (default: 1521)
    ORACLE_SERVICE    – service name *or* SID
    ORACLE_USER       – schema / user name
    ORACLE_PASSWORD   – password

PostgreSQL (destination)
    PG_HOST           – hostname or IP of the PostgreSQL server
    PG_PORT           – port (default: 5432)
    PG_DATABASE       – database name
    PG_SCHEMA         – target schema (default: public)
    PG_USER           – user name
    PG_PASSWORD       – password

Optional
    MIGRATION_TABLES  – comma-separated list of tables to migrate (default: all)
    MIGRATION_BATCH_SIZE – rows fetched per batch (default: 10000)
    MIGRATION_MODE    – 'full' (truncate+reload) or 'incremental' (default: full)
    LOG_LEVEL         – Python logging level name (default: INFO)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise EnvironmentError(
            f"Required environment variable '{name}' is not set."
        )
    return value


def _optional_env(name: str, default: str) -> str:
    return os.environ.get(name, default)


@dataclass(frozen=True)
class OracleConfig:
    host: str
    port: int
    service: str
    user: str
    password: str

    @classmethod
    def from_env(cls) -> "OracleConfig":
        return cls(
            host=_require_env("ORACLE_HOST"),
            port=int(_optional_env("ORACLE_PORT", "1521")),
            service=_require_env("ORACLE_SERVICE"),
            user=_require_env("ORACLE_USER"),
            password=_require_env("ORACLE_PASSWORD"),
        )

    @property
    def dsn(self) -> str:
        return f"{self.host}:{self.port}/{self.service}"


@dataclass(frozen=True)
class PostgresConfig:
    host: str
    port: int
    database: str
    user: str
    password: str
    schema: str = "public"

    @classmethod
    def from_env(cls) -> "PostgresConfig":
        return cls(
            host=_require_env("PG_HOST"),
            port=int(_optional_env("PG_PORT", "5432")),
            database=_require_env("PG_DATABASE"),
            user=_require_env("PG_USER"),
            password=_require_env("PG_PASSWORD"),
            schema=_optional_env("PG_SCHEMA", "public"),
        )


@dataclass(frozen=True)
class MigrationConfig:
    oracle: OracleConfig
    postgres: PostgresConfig
    tables: list[str] = field(default_factory=list)
    batch_size: int = 10_000
    mode: str = "full"  # 'full' | 'incremental'
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "MigrationConfig":
        tables_raw = _optional_env("MIGRATION_TABLES", "")
        tables = [t.strip() for t in tables_raw.split(",") if t.strip()]
        batch_size = int(_optional_env("MIGRATION_BATCH_SIZE", "10000"))
        mode = _optional_env("MIGRATION_MODE", "full").lower()
        if mode not in ("full", "incremental"):
            raise ValueError(f"MIGRATION_MODE must be 'full' or 'incremental', got '{mode}'")
        return cls(
            oracle=OracleConfig.from_env(),
            postgres=PostgresConfig.from_env(),
            tables=tables,
            batch_size=batch_size,
            mode=mode,
            log_level=_optional_env("LOG_LEVEL", "INFO").upper(),
        )
