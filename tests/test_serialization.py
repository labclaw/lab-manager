"""Tests for serialization service — serialize_value helper."""

from datetime import date, datetime, timezone
from decimal import Decimal

from lab_manager.services.serialization import serialize_value


class TestSerializeValueNone:
    def test_none_returns_none(self):
        assert serialize_value(None) is None


class TestSerializeValueDatetime:
    def test_datetime_to_isoformat(self):
        dt = datetime(2025, 3, 15, 10, 30, 0, tzinfo=timezone.utc)
        assert serialize_value(dt) == "2025-03-15T10:30:00+00:00"

    def test_datetime_naive(self):
        dt = datetime(2025, 1, 1, 0, 0, 0)
        assert serialize_value(dt) == "2025-01-01T00:00:00"

    def test_date_to_isoformat(self):
        d = date(2025, 6, 30)
        assert serialize_value(d) == "2025-06-30"

    def test_date_before_datetime_check(self):
        """datetime matched first, then date fallback."""
        dt = datetime(2025, 7, 4, 12, 0)
        d = date(2025, 7, 4)
        assert serialize_value(dt) != serialize_value(d)
        assert "T" in serialize_value(dt)
        assert "T" not in serialize_value(d)


class TestSerializeValueDecimal:
    def test_decimal_to_string(self):
        assert serialize_value(Decimal("3.14")) == "3.14"

    def test_decimal_zero(self):
        assert serialize_value(Decimal("0")) == "0"

    def test_decimal_large_precision(self):
        assert serialize_value(Decimal("123456789.123456789")) == "123456789.123456789"


class TestSerializeValuePrimitives:
    def test_int(self):
        assert serialize_value(42) == 42

    def test_float(self):
        assert serialize_value(3.14) == 3.14

    def test_bool_true(self):
        assert serialize_value(True) is True

    def test_bool_false(self):
        assert serialize_value(False) is False

    def test_string(self):
        assert serialize_value("hello") == "hello"

    def test_empty_string(self):
        assert serialize_value("") == ""


class TestSerializeValueCollections:
    def test_list(self):
        assert serialize_value([1, 2, 3]) == [1, 2, 3]

    def test_dict(self):
        assert serialize_value({"a": 1}) == {"a": 1}

    def test_empty_list(self):
        assert serialize_value([]) == []

    def test_empty_dict(self):
        assert serialize_value({}) == {}


class TestSerializeValueNumpyLike:
    """Test the numpy int64/float64 guard path without requiring numpy.

    The code checks type(val).__name__, so we dynamically create classes
    with the expected names.
    """

    def test_int64_by_name(self):
        cls = type("int64", (), {"__int__": lambda self: 99})
        obj = cls()
        assert type(obj).__name__ == "int64"
        assert serialize_value(obj) == 99

    def test_float64_by_name(self):
        cls = type("float64", (), {"__float__": lambda self: 2.718})
        obj = cls()
        assert type(obj).__name__ == "float64"
        assert serialize_value(obj) == 2.718

    def test_int32_by_name(self):
        cls = type("int32", (), {"__int__": lambda self: 7})
        obj = cls()
        assert type(obj).__name__ == "int32"
        assert serialize_value(obj) == 7

    def test_float32_by_name(self):
        cls = type("float32", (), {"__float__": lambda self: 1.5})
        obj = cls()
        assert type(obj).__name__ == "float32"
        assert serialize_value(obj) == 1.5


class TestSerializeValueFallback:
    def test_unknown_type_to_string(self):
        result = serialize_value(object())
        assert isinstance(result, str)
        assert result.startswith("<object object at 0x")

    def test_custom_class_with_str(self):
        class Widget:
            def __str__(self):
                return "widget-123"

        assert serialize_value(Widget()) == "widget-123"

    def test_set_converted_to_string(self):
        result = serialize_value({1, 2, 3})
        assert isinstance(result, str)

    def test_tuple_converted_to_string(self):
        result = serialize_value((1, 2))
        assert isinstance(result, str)
