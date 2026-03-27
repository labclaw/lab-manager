"""Small request-validation helpers shared across API routes."""

from __future__ import annotations

import string

_EMAIL_LOCAL_CHARS = set(string.ascii_letters + string.digits + "!#$%&'*+/=?^_`{|}~.-")
_EMAIL_DOMAIN_CHARS = set(string.ascii_letters + string.digits + "-")


def is_valid_email_address(value: str) -> bool:
    """Return True for a conservative ASCII email address format."""
    if not value or len(value) > 255 or any(ch.isspace() for ch in value):
        return False

    local_part, separator, domain = value.rpartition("@")
    if separator != "@" or not local_part or not domain:
        return False
    if "." not in domain:
        return False
    if local_part.startswith(".") or local_part.endswith(".") or ".." in local_part:
        return False
    if domain.startswith(".") or domain.endswith(".") or ".." in domain:
        return False
    if any(ch not in _EMAIL_LOCAL_CHARS for ch in local_part):
        return False

    labels = domain.split(".")
    if any(not label for label in labels):
        return False

    for label in labels:
        if label.startswith("-") or label.endswith("-"):
            return False
        if any(ch not in _EMAIL_DOMAIN_CHARS for ch in label):
            return False

    return True
