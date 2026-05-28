"""Exceptions for shared authentication and authorization."""


class SharedAuthError(Exception):
    """Base exception for shared auth failures."""


class AuthenticationRequiredError(SharedAuthError):
    """Raised when a request has no active authenticated user."""


class ApplicationAccessDeniedError(SharedAuthError):
    """Raised when a user cannot access an application."""


class ApplicationRoleDeniedError(SharedAuthError):
    """Raised when a user lacks a required application role."""
