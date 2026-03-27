"""Unit tests for serialization service.

Tests serialize_value: None, datetime, date, Decimal, numpy types, primitives, collections.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from lab_manager.services.serialization import serialize_value


class TestSerializeValueNone:
    def test_none_returns_none(self):
        assert serialize_value(None) is None


class TestSerializeValueDatetime:
    def test_datetime_converts_to_isoformat(self):
        dt = datetime(2026, 3, 27, 14, 30, 0, tzinfo=timezone.utc)
        result = serialize_value(dt)
        assert result == dt.isoformat()
        assert "2026" in result
        assert "14:30" in result

    def test_datetime_without_timezone(self):
        dt = datetime(2026, 1, 15, 8, 0, 0)
        result = serialize_value(dt)
        assert result == dt.isoformat()

    def test_datetime_with_microseconds(self):
        dt = datetime(2026, 6, 1, 12, 0, 0, 123456)
        result = serialize_value(dt)
        assert "123456" in result


class TestSerializeValueDate:
    def test_date_converts_to_isoformat(self):
        d = date(2026, 3, 27)
        result = serialize_value(d)
        assert result == "2026-03-27"

    def test_date_jan_1(self):
        d = date(2025, 1, 1)
        result = serialize_value(d)
        assert result == "2025-01-01"

    def test_date_dec_31(self):
        d = date(2026, 12, 31)
        result = serialize_value(d)
        assert result == "2026-12-31"


class TestSerializeValueDecimal:
    def test_decimal_converts_to_string(self):
        d = Decimal("123.45")
        result = serialize_value(d)
        assert result == "123.45"
        assert isinstance(result, str)

    def test_decimal_integer_value(self):
        d = Decimal("100")
        result = serialize_value(d)
        assert result == "100"

    def test_decimal_very_precise(self):
        d = Decimal("3.141592653589793")
        result = serialize_value(d)
        assert "3.14159" in result

    def test_decimal_zero(self):
        d = Decimal("0")
        result = serialize_value(d)
        assert result == "0"


class TestSerializeValuePrimitives:
    def test_int_returned_as_is(self):
        assert serialize_value(42) == 42
        assert isinstance(serialize_value(42), int)

    def test_float_returned_as_is(self):
        assert serialize_value(3.14) == 3.14
        assert isinstance(serialize_value(3.14), float)

    def test_bool_returned_as_is(self):
        assert serialize_value(True) is True
        assert serialize_value(False) is False

    def test_string_returned_as_is(self):
        assert serialize_value("hello") == "hello"

    def test_empty_string(self):
        assert serialize_value("") == ""

    def test_negative_int(self):
        assert serialize_value(-5) == -5

    def test_zero_float(self):
        assert serialize_value(0.0) == 0.0

    def test_large_int(self):
        big = 10**18
        assert serialize_value(big) == big

    def test_unicode_string(self):
        assert serialize_value("\u00e9\u00e8\u00ea") == "\u00e9\u00e8\u00ea"


class TestSerializeValueCollections:
    def test_list_returned_as_is(self):
        lst = [1, 2, 3]
        assert serialize_value(lst) == [1, 2, 3]

    def test_dict_returned_as_is(self):
        d = {"key": "value"}
        assert serialize_value(d) == {"key": "value"}

    def test_empty_list(self):
        assert serialize_value([]) == []

    def test_empty_dict(self):
        assert serialize_value({}) == {}

    def test_nested_list(self):
        nested = [[1, 2], [3, 4]]
        assert serialize_value(nested) == [[1, 2], [3, 4]]

    def test_nested_dict(self):
        nested = {"a": {"b": 1}}
        assert serialize_value(nested) == {"a": {"b": 1}}


class TestSerializeValueNumpyLike:
    """Test handling of numpy-style types (int64, float64, etc.)."""

    def test_int64_type(self):
        """Simulate numpy int64 by creating a class with __name__ = 'int64'."""

        class Int64:
            def __init__(self, val):
                self._val = val

            def __int__(self):
                return self._val

            def __repr__(self):
                return f"Int64({self._val})"

        # Override __name__ on the class
        Int64.__name__ = "int64"
        val = Int64(42)
        assert type(val).__name__ == "int64"
        result = serialize_value(val)
        assert result == 42
        assert isinstance(result, int)

    def test_float64_type(self):
        class Float64:
            def __init__(self, val):
                self._val = val

            def __float__(self):
                return self._val

        Float64.__name__ = "float64"
        val = Float64(3.14)
        assert type(val).__name__ == "float64"
        result = serialize_value(val)
        assert result == 3.14
        assert isinstance(result, float)

    def test_int32_type(self):
        class Int32:
            def __init__(self, val):
                self._val = val

            def __int__(self):
                return self._val

        Int32.__name__ = "int32"
        val = Int32(100)
        result = serialize_value(val)
        assert result == 100
        assert isinstance(result, int)

    def test_float32_type(self):
        class Float32:
            def __init__(self, val):
                self._val = val

            def __float__(self):
                return self._val

        Float32.__name__ = "float32"
        val = Float32(2.5)
        result = serialize_value(val)
        assert result == 2.5
        assert isinstance(result, float)


class TestSerializeValueFallback:
    def test_unknown_type_converts_to_string(self):
        """Objects without special handling get str()."""

        class CustomObj:
            def __str__(self):
                return "custom-object"

        result = serialize_value(CustomObj())
        assert result == "custom-object"
        assert isinstance(result, str)

    def test_set_converts_to_string(self):
        """Sets are not in the special-handled list, so str()."""
        result = serialize_value({1, 2, 3})
        assert isinstance(result, str)

    def test_tuple_not_special_handled(self):
        """Tuples are not list/dict, so they fall through to str()."""
        result = serialize_value((1, 2, 3))
        # tuple is not list or dict, so it should be str()
        assert isinstance(result, str)

    def test_bytes_converts_to_string(self):
        result = serialize_value(b"hello")
        assert isinstance(result, str)
