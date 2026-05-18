from typing import Optional


class UniformAgriError(RuntimeError):
    """Base exception for Uniform Agri job failures."""


class UniformAgriApiError(UniformAgriError):
    """Raised when the Uniform Agri API returns an error response."""

    def __init__(
        self,
        message: str,
        endpoint: str,
        status_code: Optional[int] = None,
        response_text: str = "",
    ):
        self.endpoint = endpoint
        self.status_code = status_code
        self.response_text = response_text[:500]
        super().__init__(message)


class UniformAgriAuthenticationError(UniformAgriApiError):
    """Raised when Uniform Agri authentication fails."""
