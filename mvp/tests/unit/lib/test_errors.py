"""Unit tests for mvp.lib.errors."""

from __future__ import annotations

from mvp.lib.errors import (
    EdgarHttpError,
    ErrorCategory,
    InputValidationError,
    LibError,
    MissingApiKey,
    PdfReadError,
    RateLimitExceeded,
)


def test_liberror_to_dict() -> None:
    e = LibError("oops")
    d = e.to_dict()
    assert d == {
        "error_code": "lib_error",
        "error_category": "internal",
        "retry_safe": False,
        "message": "oops",
    }


def test_input_validation_defaults() -> None:
    e = InputValidationError("bad")
    assert e.error_code == "input_validation"
    assert e.error_category == ErrorCategory.INPUT_VALIDATION
    assert e.retry_safe is False


def test_rate_limit_is_retry_safe() -> None:
    e = RateLimitExceeded("too fast")
    assert e.retry_safe is True
    assert e.error_category == ErrorCategory.RATE_LIMIT


def test_missing_api_key_category_auth() -> None:
    e = MissingApiKey("no key")
    assert e.error_category == ErrorCategory.AUTH


def test_edgar_http_error_attrs() -> None:
    e = EdgarHttpError("nope", status_code=404, url="https://www.sec.gov/x")
    assert e.status_code == 404
    assert e.url == "https://www.sec.gov/x"
    assert e.error_category == ErrorCategory.UPSTREAM


def test_pdf_read_error_attrs() -> None:
    e = PdfReadError("can't read", path="/tmp/x.pdf", reason="corrupt")
    assert e.path == "/tmp/x.pdf"
    assert e.reason == "corrupt"


def test_constructor_overrides() -> None:
    e = LibError(
        "custom",
        error_code="custom_code",
        error_category=ErrorCategory.IO,
        retry_safe=True,
    )
    assert e.error_code == "custom_code"
    assert e.error_category == ErrorCategory.IO
    assert e.retry_safe is True
