"""Unit tests for lab_manager.api.validation — email validation edge cases."""

from __future__ import annotations

from lab_manager.api.validation import is_valid_email_address


class TestIsValidEmailAddressRejects:
    """Negative cases — every branch that returns False."""

    # --- line 14: empty / too long / whitespace ---

    def test_empty_string(self) -> None:
        assert is_valid_email_address("") is False

    def test_none_like_empty(self) -> None:
        assert is_valid_email_address("") is False

    def test_exceeds_255_chars(self) -> None:
        local = "a" * 244  # 244 + 1(@) + 11(example.com) = 256 > 255
        email = f"{local}@example.com"
        assert len(email) > 255
        assert is_valid_email_address(email) is False

    def test_whitespace_in_email(self) -> None:
        assert is_valid_email_address("user @example.com") is False

    def test_tab_in_email(self) -> None:
        assert is_valid_email_address("user\t@example.com") is False

    def test_newline_in_email(self) -> None:
        assert is_valid_email_address("user\n@example.com") is False

    # --- line 18: no @ / empty local / empty domain ---

    def test_no_at_sign(self) -> None:
        assert is_valid_email_address("plaintext") is False

    def test_empty_local_part(self) -> None:
        assert is_valid_email_address("@example.com") is False

    def test_empty_domain(self) -> None:
        assert is_valid_email_address("user@") is False

    # --- line 20: no dot in domain ---

    def test_domain_without_dot(self) -> None:
        assert is_valid_email_address("user@localhost") is False

    # --- line 22: local starts/ends with dot or has double dot ---

    def test_local_starts_with_dot(self) -> None:
        assert is_valid_email_address(".user@example.com") is False

    def test_local_ends_with_dot(self) -> None:
        assert is_valid_email_address("user.@example.com") is False

    def test_local_has_double_dot(self) -> None:
        assert is_valid_email_address("user..name@example.com") is False

    # --- line 24: domain starts/ends with dot or has double dot ---

    def test_domain_starts_with_dot(self) -> None:
        assert is_valid_email_address("user@.example.com") is False

    def test_domain_ends_with_dot(self) -> None:
        assert is_valid_email_address("user@example.com.") is False

    def test_domain_has_double_dot(self) -> None:
        assert is_valid_email_address("user@ex..ample.com") is False

    # --- line 26: invalid char in local part ---

    def test_invalid_char_parentheses(self) -> None:
        assert is_valid_email_address("user(abc)@example.com") is False

    def test_invalid_char_bracket(self) -> None:
        assert is_valid_email_address("user[abc]@example.com") is False

    def test_invalid_char_comma(self) -> None:
        assert is_valid_email_address("user,name@example.com") is False

    def test_invalid_char_colon(self) -> None:
        assert is_valid_email_address("user:name@example.com") is False

    def test_invalid_char_semicolon(self) -> None:
        assert is_valid_email_address("user;name@example.com") is False

    def test_invalid_char_double_quote(self) -> None:
        assert is_valid_email_address('user"name@example.com') is False

    # --- line 30: empty label in domain ---

    def test_domain_trailing_dot_creates_empty_label(self) -> None:
        # This is already caught by line 24 (ends with dot), but
        # a domain like "a..b.com" is caught by line 24 (double dot).
        # To hit line 30 independently, we need an empty label not from
        # leading/trailing/double dots — which is impossible with split(".")
        # since those are all caught earlier. We verify it via the existing
        # double-dot path which hits both line 24 and 30.
        assert is_valid_email_address("user@example..com") is False

    # --- line 34: label starts/ends with hyphen ---

    def test_domain_label_starts_with_hyphen(self) -> None:
        assert is_valid_email_address("user@-example.com") is False

    def test_domain_label_ends_with_hyphen(self) -> None:
        assert is_valid_email_address("user@example-.com") is False

    def test_subdomain_label_starts_with_hyphen(self) -> None:
        assert is_valid_email_address("user@-sub.example.com") is False

    def test_subdomain_label_ends_with_hyphen(self) -> None:
        assert is_valid_email_address("user@sub-.example.com") is False

    # --- line 36: invalid char in domain label ---

    def test_domain_label_has_underscore(self) -> None:
        assert is_valid_email_address("user@ex_ample.com") is False

    def test_domain_label_has_space(self) -> None:
        assert is_valid_email_address("user@exa mple.com") is False

    def test_domain_label_has_bang(self) -> None:
        assert is_valid_email_address("user@exa!mple.com") is False

    def test_domain_label_has_plus(self) -> None:
        assert is_valid_email_address("user@exa+mple.com") is False


class TestIsValidEmailAddressAccepts:
    """Positive cases — valid email addresses."""

    def test_simple_email(self) -> None:
        assert is_valid_email_address("user@example.com") is True

    def test_dot_in_local(self) -> None:
        assert is_valid_email_address("first.last@example.com") is True

    def test_plus_in_local(self) -> None:
        assert is_valid_email_address("user+tag@example.com") is True

    def test_hyphen_in_local(self) -> None:
        assert is_valid_email_address("user-name@example.com") is True

    def test_underscore_in_local(self) -> None:
        assert is_valid_email_address("user_name@example.com") is True

    def test_subdomain(self) -> None:
        assert is_valid_email_address("user@sub.example.com") is True

    def test_numeric_local(self) -> None:
        assert is_valid_email_address("12345@example.com") is True

    def test_numeric_domain(self) -> None:
        assert is_valid_email_address("user@123.com") is True

    def test_hyphen_in_domain_label(self) -> None:
        assert is_valid_email_address("user@my-example.com") is True

    def test_bare_minimum(self) -> None:
        assert is_valid_email_address("a@b.co") is True

    def test_bang_in_local(self) -> None:
        assert is_valid_email_address("user!name@example.com") is True

    def test_hash_in_local(self) -> None:
        assert is_valid_email_address("user#name@example.com") is True

    def test_dollar_in_local(self) -> None:
        assert is_valid_email_address("user$name@example.com") is True

    def test_percent_in_local(self) -> None:
        assert is_valid_email_address("user%name@example.com") is True

    def test_ampersand_in_local(self) -> None:
        assert is_valid_email_address("user&name@example.com") is True

    def test_apostrophe_in_local(self) -> None:
        assert is_valid_email_address("user'name@example.com") is True

    def test_asterisk_in_local(self) -> None:
        assert is_valid_email_address("user*name@example.com") is True

    def test_slash_in_local(self) -> None:
        assert is_valid_email_address("user/name@example.com") is True

    def test_equals_in_local(self) -> None:
        assert is_valid_email_address("user=name@example.com") is True

    def test_question_mark_in_local(self) -> None:
        assert is_valid_email_address("user?name@example.com") is True

    def test_caret_in_local(self) -> None:
        assert is_valid_email_address("user^name@example.com") is True

    def test_backtick_in_local(self) -> None:
        assert is_valid_email_address("user`name@example.com") is True

    def test_curly_braces_in_local(self) -> None:
        assert is_valid_email_address("user{name}@example.com") is True

    def test_pipe_in_local(self) -> None:
        assert is_valid_email_address("user|name@example.com") is True

    def test_tilde_in_local(self) -> None:
        assert is_valid_email_address("user~name@example.com") is True

    def test_exactly_255_chars(self) -> None:
        local = "a" * 243
        email = f"{local}@example.com"
        assert len(email) == 255
        assert is_valid_email_address(email) is True

    def test_single_char_domain_label(self) -> None:
        assert is_valid_email_address("user@a.bc") is True
