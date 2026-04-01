"""Oracle to PostgreSQL data type mapping."""

# Maps Oracle SQL types to PostgreSQL equivalents
ORACLE_TO_POSTGRES: dict[str, str] = {
    # Numeric types
    "NUMBER": "NUMERIC",
    "FLOAT": "DOUBLE PRECISION",
    "BINARY_FLOAT": "REAL",
    "BINARY_DOUBLE": "DOUBLE PRECISION",
    "INTEGER": "INTEGER",
    "INT": "INTEGER",
    "SMALLINT": "SMALLINT",
    # Character types
    "CHAR": "CHAR",
    "NCHAR": "CHAR",
    "VARCHAR2": "VARCHAR",
    "NVARCHAR2": "VARCHAR",
    "CLOB": "TEXT",
    "NCLOB": "TEXT",
    "LONG": "TEXT",
    # Binary types
    "RAW": "BYTEA",
    "LONG RAW": "BYTEA",
    "BLOB": "BYTEA",
    "BFILE": "BYTEA",
    # Date / time types
    "DATE": "TIMESTAMP",
    "TIMESTAMP": "TIMESTAMP",
    "TIMESTAMP WITH TIME ZONE": "TIMESTAMP WITH TIME ZONE",
    "TIMESTAMP WITH LOCAL TIME ZONE": "TIMESTAMP WITH TIME ZONE",
    "INTERVAL YEAR TO MONTH": "INTERVAL",
    "INTERVAL DAY TO SECOND": "INTERVAL",
    # Other
    "XMLTYPE": "XML",
    "ROWID": "VARCHAR(18)",
    "UROWID": "VARCHAR(4000)",
}


def map_column_type(oracle_type: str, precision: int | None, scale: int | None) -> str:
    """Return the PostgreSQL column type for a given Oracle column description.

    Args:
        oracle_type: The Oracle column type name (upper-cased).
        precision: Numeric precision, if applicable.
        scale: Numeric scale, if applicable.

    Returns:
        A PostgreSQL type string.
    """
    oracle_type_upper = oracle_type.upper().strip()

    # NUMBER with scale 0 (or no fractional part) → prefer integer types
    if oracle_type_upper == "NUMBER":
        if precision is not None and scale == 0:
            if precision <= 4:
                return "SMALLINT"
            if precision <= 9:
                return "INTEGER"
            if precision <= 18:
                return "BIGINT"
        if precision is not None:
            # scale can be None when Oracle reports precision without scale (e.g. NUMBER(10));
            # default to 0 in that case to produce a valid NUMERIC declaration.
            return f"NUMERIC({precision}, {scale if scale is not None else 0})"
        return "NUMERIC"

    # VARCHAR2 / NVARCHAR2 / CHAR / NCHAR with length
    if oracle_type_upper in ("VARCHAR2", "NVARCHAR2") and precision is not None:
        return f"VARCHAR({precision})"

    if oracle_type_upper in ("CHAR", "NCHAR") and precision is not None:
        return f"CHAR({precision})"

    # TIMESTAMP with fractional-second precision
    if oracle_type_upper.startswith("TIMESTAMP"):
        if "WITH TIME ZONE" in oracle_type_upper or "WITH LOCAL TIME ZONE" in oracle_type_upper:
            return "TIMESTAMP WITH TIME ZONE"
        return "TIMESTAMP"

    mapped = ORACLE_TO_POSTGRES.get(oracle_type_upper)
    if mapped:
        return mapped

    # Fall back to TEXT for unknown types
    return "TEXT"
