"""Unit tests for domain exception hierarchy."""

from lab_manager.exceptions import (
    BusinessError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)


class TestBusinessError:
    def test_default_message(self):
        err = BusinessError()
        assert err.message == "Bad request"
        assert err.status_code == 400

    def test_custom_message(self):
        err = BusinessError("Custom error")
        assert err.message == "Custom error"
        assert str(err) == "Custom error"

    def test_is_exception(self):
        assert issubclass(BusinessError, Exception)


class TestNotFoundError:
    def test_without_id(self):
        err = NotFoundError("Order")
        assert err.message == "Order not found"
        assert err.status_code == 404

    def test_with_id(self):
        err = NotFoundError("Product", 42)
        assert err.message == "Product 42 not found"
        assert err.status_code == 404

    def test_with_string_id(self):
        err = NotFoundError("File", "abc.txt")
        assert err.message == "File abc.txt not found"

    def test_default_resource(self):
        err = NotFoundError()
        assert "not found" in err.message

    def test_inherits_business_error(self):
        assert issubclass(NotFoundError, BusinessError)


class TestValidationError:
    def test_default(self):
        err = ValidationError()
        assert err.status_code == 422
        assert err.message == "Bad request"

    def test_custom_message(self):
        err = ValidationError("Invalid CAS number")
        assert err.message == "Invalid CAS number"

    def test_inherits_business_error(self):
        assert issubclass(ValidationError, BusinessError)


class TestConflictError:
    def test_default(self):
        err = ConflictError()
        assert err.status_code == 409

    def test_custom_message(self):
        err = ConflictError("Duplicate catalog number")
        assert err.message == "Duplicate catalog number"

    def test_inherits_business_error(self):
        assert issubclass(ConflictError, BusinessError)


class TestForbiddenError:
    def test_default(self):
        err = ForbiddenError()
        assert err.status_code == 403

    def test_custom_message(self):
        err = ForbiddenError("Admin only")
        assert err.message == "Admin only"

    def test_inherits_business_error(self):
        assert issubclass(ForbiddenError, BusinessError)
