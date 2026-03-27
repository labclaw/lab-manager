"""Comprehensive tests for the domain exception hierarchy."""

import pytest

from lab_manager.exceptions import (
    BusinessError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)


# ---------------------------------------------------------------------------
# BusinessError (base)
# ---------------------------------------------------------------------------


class TestBusinessError:
    """Tests for the base BusinessError class."""

    def test_default_message(self):
        """BusinessError with no args uses the default message."""
        err = BusinessError()
        assert err.message == "Bad request"
        assert str(err) == "Bad request"

    def test_custom_message(self):
        """BusinessError stores and propagates a custom message."""
        err = BusinessError("Something went wrong")
        assert err.message == "Something went wrong"
        assert str(err) == "Something went wrong"

    def test_default_status_code(self):
        """BusinessError maps to HTTP 400."""
        assert BusinessError.status_code == 400
        assert BusinessError("x").status_code == 400

    def test_is_exception(self):
        """BusinessError is a proper Exception subclass."""
        err = BusinessError("fail")
        assert isinstance(err, Exception)
        with pytest.raises(BusinessError):
            raise err

    def test_caught_by_base_exception(self):
        """BusinessError can be caught as a plain Exception."""
        with pytest.raises(Exception):
            raise BusinessError("caught")


# ---------------------------------------------------------------------------
# NotFoundError
# ---------------------------------------------------------------------------


class TestNotFoundError:
    """Tests for NotFoundError."""

    def test_resource_only(self):
        """With resource but no id, message is '{resource} not found'."""
        err = NotFoundError("Vendor")
        assert err.message == "Vendor not found"

    def test_resource_with_int_id(self):
        """With resource and integer id, message includes the id."""
        err = NotFoundError("Product", 42)
        assert err.message == "Product 42 not found"

    def test_resource_with_str_id(self):
        """With resource and string id, message includes the id."""
        err = NotFoundError("Order", "ORD-123")
        assert err.message == "Order ORD-123 not found"

    def test_resource_with_none_id(self):
        """Passing id=None is the same as omitting id."""
        err = NotFoundError("Document", None)
        assert err.message == "Document not found"

    def test_status_code(self):
        """NotFoundError maps to HTTP 404."""
        assert NotFoundError.status_code == 404
        assert NotFoundError("X").status_code == 404

    def test_inherits_business_error(self):
        """NotFoundError is a subclass of BusinessError."""
        err = NotFoundError("Item")
        assert isinstance(err, BusinessError)
        assert isinstance(err, Exception)

    def test_default_resource(self):
        """Default resource name is 'Resource'."""
        err = NotFoundError()
        assert err.message == "Resource not found"

    def test_caught_by_base_class(self):
        """Catching BusinessError also catches NotFoundError."""
        with pytest.raises(BusinessError):
            raise NotFoundError("Vendor", 1)


# ---------------------------------------------------------------------------
# ValidationError
# ---------------------------------------------------------------------------


class TestValidationError:
    """Tests for ValidationError."""

    def test_inherits_business_error(self):
        err = ValidationError("invalid input")
        assert isinstance(err, BusinessError)

    def test_status_code(self):
        assert ValidationError.status_code == 422

    def test_custom_message(self):
        err = ValidationError("email format invalid")
        assert err.message == "email format invalid"

    def test_default_message_inherited(self):
        """ValidationError inherits default message from BusinessError."""
        err = ValidationError()
        assert err.message == "Bad request"


# ---------------------------------------------------------------------------
# ConflictError
# ---------------------------------------------------------------------------


class TestConflictError:
    """Tests for ConflictError."""

    def test_inherits_business_error(self):
        err = ConflictError("duplicate entry")
        assert isinstance(err, BusinessError)

    def test_status_code(self):
        assert ConflictError.status_code == 409

    def test_custom_message(self):
        err = ConflictError("state transition not allowed")
        assert err.message == "state transition not allowed"

    def test_caught_by_base_class(self):
        with pytest.raises(BusinessError):
            raise ConflictError("conflict")


# ---------------------------------------------------------------------------
# ForbiddenError
# ---------------------------------------------------------------------------


class TestForbiddenError:
    """Tests for ForbiddenError."""

    def test_inherits_business_error(self):
        err = ForbiddenError("no access")
        assert isinstance(err, BusinessError)

    def test_status_code(self):
        assert ForbiddenError.status_code == 403

    def test_custom_message(self):
        err = ForbiddenError("insufficient role")
        assert err.message == "insufficient role"


# ---------------------------------------------------------------------------
# Hierarchy & dispatch
# ---------------------------------------------------------------------------


class TestExceptionHierarchy:
    """Cross-cutting tests for the exception hierarchy."""

    @pytest.mark.parametrize(
        "exc_cls, expected_code",
        [
            (BusinessError, 400),
            (NotFoundError, 404),
            (ValidationError, 422),
            (ConflictError, 409),
            (ForbiddenError, 403),
        ],
    )
    def test_status_codes(self, exc_cls, expected_code):
        assert exc_cls.status_code == expected_code

    def test_all_inherit_from_business_error(self):
        """Every domain exception is a subclass of BusinessError."""
        for cls in (NotFoundError, ValidationError, ConflictError, ForbiddenError):
            assert issubclass(cls, BusinessError)

    def test_dispatch_by_status_code(self):
        """Practical dispatch pattern: map status_code to exception class."""
        registry = {
            cls.status_code: cls
            for cls in (
                BusinessError,
                NotFoundError,
                ValidationError,
                ConflictError,
                ForbiddenError,
            )
        }
        assert registry[400] is BusinessError
        assert registry[404] is NotFoundError
        assert registry[422] is ValidationError
        assert registry[409] is ConflictError
        assert registry[403] is ForbiddenError

    def test_catch_specific_then_general(self):
        """Specific exceptions can be caught before the base class."""
        with pytest.raises(NotFoundError):
            try:
                raise NotFoundError("X")
            except NotFoundError:
                raise
            except BusinessError:
                pytest.fail("Should not reach generic handler first")
