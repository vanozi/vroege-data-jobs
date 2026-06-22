"""Exceptions for the Moneybird datajob."""

from typing import Optional


class MoneybirdError(RuntimeError):
    """Base exception for Moneybird datajob failures."""


class MoneybirdConfigError(MoneybirdError):
    """Raised when Moneybird configuration is missing or invalid."""


class MoneybirdApiError(MoneybirdError):
    """Raised when the Moneybird API request fails."""

    def __init__(
        self,
        message: str,
        *,
        endpoint: Optional[str] = None,
        status_code: Optional[int] = None,
        response_text: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.endpoint = endpoint
        self.status_code = status_code
        self.response_text = response_text


class MoneybirdAuthenticationError(MoneybirdApiError):
    """Raised when Moneybird rejects authentication or authorization."""


class MoneybirdRateLimitError(MoneybirdApiError):
    """Raised when Moneybird rate limiting continues after retries."""
