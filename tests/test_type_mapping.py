"""Tests for the Oracle → PostgreSQL type mapping module."""

import pytest

from type_mapping import map_column_type


# ---------------------------------------------------------------------------
# NUMBER mappings
# ---------------------------------------------------------------------------

class TestNumberMapping:
    def test_number_no_precision_returns_numeric(self):
        assert map_column_type("NUMBER", None, None) == "NUMERIC"

    def test_number_with_fractional_scale(self):
        assert map_column_type("NUMBER", 10, 2) == "NUMERIC(10, 2)"

    def test_number_precision_4_scale_0_is_smallint(self):
        assert map_column_type("NUMBER", 4, 0) == "SMALLINT"

    def test_number_precision_9_scale_0_is_integer(self):
        assert map_column_type("NUMBER", 9, 0) == "INTEGER"

    def test_number_precision_18_scale_0_is_bigint(self):
        assert map_column_type("NUMBER", 18, 0) == "BIGINT"

    def test_number_precision_19_scale_0_is_numeric(self):
        result = map_column_type("NUMBER", 19, 0)
        assert result == "NUMERIC(19, 0)"


# ---------------------------------------------------------------------------
# Character type mappings
# ---------------------------------------------------------------------------

class TestCharacterMapping:
    def test_varchar2_with_length(self):
        assert map_column_type("VARCHAR2", 100, None) == "VARCHAR(100)"

    def test_nvarchar2_with_length(self):
        assert map_column_type("NVARCHAR2", 200, None) == "VARCHAR(200)"

    def test_char_with_length(self):
        assert map_column_type("CHAR", 10, None) == "CHAR(10)"

    def test_clob_maps_to_text(self):
        assert map_column_type("CLOB", None, None) == "TEXT"

    def test_long_maps_to_text(self):
        assert map_column_type("LONG", None, None) == "TEXT"


# ---------------------------------------------------------------------------
# Date / time mappings
# ---------------------------------------------------------------------------

class TestDateTimeMapping:
    def test_date_maps_to_timestamp(self):
        assert map_column_type("DATE", None, None) == "TIMESTAMP"

    def test_timestamp_maps_to_timestamp(self):
        assert map_column_type("TIMESTAMP", None, None) == "TIMESTAMP"

    def test_timestamp_with_tz(self):
        result = map_column_type("TIMESTAMP WITH TIME ZONE", None, None)
        assert result == "TIMESTAMP WITH TIME ZONE"

    def test_timestamp_with_local_tz(self):
        result = map_column_type("TIMESTAMP WITH LOCAL TIME ZONE", None, None)
        assert result == "TIMESTAMP WITH TIME ZONE"


# ---------------------------------------------------------------------------
# Binary / other mappings
# ---------------------------------------------------------------------------

class TestOtherMappings:
    def test_blob_maps_to_bytea(self):
        assert map_column_type("BLOB", None, None) == "BYTEA"

    def test_float_maps_to_double_precision(self):
        assert map_column_type("FLOAT", None, None) == "DOUBLE PRECISION"

    def test_binary_double(self):
        assert map_column_type("BINARY_DOUBLE", None, None) == "DOUBLE PRECISION"

    def test_unknown_type_falls_back_to_text(self):
        assert map_column_type("SOME_UNKNOWN_TYPE", None, None) == "TEXT"

    def test_case_insensitive(self):
        assert map_column_type("varchar2", 50, None) == "VARCHAR(50)"
