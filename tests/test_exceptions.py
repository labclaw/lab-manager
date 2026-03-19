"""Tests for custom exception classes in lab_manager.exceptions."""

from lab_manager.exceptions import (
    BusinessError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)


def test_business_error_defaults():
    """BusinessError should have a default status_code and message."""
    err = BusinessError()
    assert err.status_code == 400
    assert err.message == "Bad request"
    assert isinstance(err, Exception)


def test_business_error_custom_message():
    """BusinessError should accept a custom message."""
    err = BusinessError("Something went wrong")
    assert err.message == "Something went wrong"
    assert str(err) == "Something went wrong"


def test_not_found_error_defaults():
    """NotFoundError should have a default status_code and message."""
    err = NotFoundError()
    assert err.status_code == 404
    assert err.message == "Resource not found"
    assert isinstance(err, BusinessError)
    assert isinstance(err, Exception)


def test_not_found_error_with_resource():
    """NotFoundError should format message with a resource name."""
    err = NotFoundError(resource="Product")
    assert err.message == "Product not found"


def test_not_found_error_with_resource_and_id():
    """NotFoundError should format message with a resource name and ID."""
    err = NotFoundError(resource="Product", id=123)
    assert err.message == "Product 123 not found"


def test_not_found_error_with_resource_and_str_id():
    """NotFoundError should format message with a resource name and string ID."""
    err = NotFoundError(resource="Order", id="PO-XYZ")
    assert err.message == "Order PO-XYZ not found"


def test_validation_error_defaults():
    """ValidationError should have a default status_code and inherited message."""
    err = ValidationError()
    assert err.status_code == 422
    assert err.message == "Bad request"  # Inherits from BusinessError
    assert isinstance(err, BusinessError)
    assert isinstance(err, Exception)


def test_validation_error_custom_message():
    """ValidationError should accept a custom message."""
    err = ValidationError("Invalid input data")
    assert err.message == "Invalid input data"
    assert str(err) == "Invalid input data"


def test_conflict_error_defaults():
    """ConflictError should have a default status_code and inherited message."""
    err = ConflictError()
    assert err.status_code == 409
    assert err.message == "Bad request"  # Inherits from BusinessError
    assert isinstance(err, BusinessError)
    assert isinstance(err, Exception)


def test_conflict_error_custom_message():
    """ConflictError should accept a custom message."""
    err = ConflictError("Item already exists")
    assert err.message == "Item already exists"
    assert str(err) == "Item already exists"


def test_forbidden_error_defaults():
    """ForbiddenError should have a default status_code and inherited message."""
    err = ForbiddenError()
    assert err.status_code == 403
    assert err.message == "Bad request"  # Inherits from BusinessError
    assert isinstance(err, BusinessError)
    assert isinstance(err, Exception)


def test_forbidden_error_custom_message():
    """ForbiddenError should accept a custom message."""
    err = ForbiddenError("Access denied")
    assert err.message == "Access denied"
    assert str(err) == "Access denied"
