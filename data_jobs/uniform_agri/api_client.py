# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "httpx",
#     "python-dotenv"
# ]
# ///

from typing import Any, Optional

import httpx

from data_jobs.uniform_agri.config import UniformAgriConfig
from data_jobs.uniform_agri import config as uniform_config
from data_jobs.uniform_agri.exceptions import (
    UniformAgriApiError,
    UniformAgriAuthenticationError,
)

DEFAULT_RESPONSE_CONTEXT_LENGTH = 500
RETRYABLE_STATUS_CODES = {500, 502, 503, 504}


def build_token_payload(config: UniformAgriConfig) -> dict[str, str]:
    """Build the OAuth2 password grant payload."""
    return {
        "grant_type": "password",
        "username": config.username,
        "password": config.password,
        "client_id": config.client_id,
    }


class ApiClient:
    """Low-level API client for making HTTP requests with automatic token refresh"""

    def __init__(
        self,
        config: Optional[UniformAgriConfig] = None,
        token: Optional[str] = None,
        http_client: Optional[httpx.Client] = None,
    ):
        self.config = config or uniform_config.load_uniform_config()
        self.base_url = self.config.base_url
        self._owns_http_client = http_client is None
        self.http_client = http_client or httpx.Client(
            base_url=self.base_url,
            timeout=self.config.request_timeout_seconds,
        )

        if token:
            self.token = token
        else:
            self.token = self.config.access_token
            if not self.token:
                self.token = self.get_access_token()

    def close(self) -> None:
        """Close the underlying HTTP client when this instance owns it."""
        if self._owns_http_client:
            self.http_client.close()

    def __enter__(self) -> "ApiClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def get_access_token(self) -> str:
        """Get an OAuth2 access token from Uniform Agri."""
        endpoint = "/oauth2/token"
        response = self._send(
            "POST",
            endpoint,
            headers={"accept": "application/json"},
            json=build_token_payload(self.config),
            authenticated=False,
        )

        try:
            token = response.json()["access_token"]
        except (KeyError, ValueError, TypeError) as error:
            raise UniformAgriAuthenticationError(
                "Uniform Agri token response did not include an access token.",
                endpoint=endpoint,
                status_code=response.status_code,
                response_text=response.text,
            ) from error

        return token

    def _send(
        self,
        method: str,
        endpoint: str,
        authenticated: bool = True,
        raise_for_status: bool = True,
        **kwargs: Any,
    ) -> httpx.Response:
        """Send a request and convert transport/API failures to project errors."""
        headers = kwargs.pop("headers", {})
        if authenticated:
            headers["Authorization"] = f"Bearer {self.token}"

        kwargs.setdefault("timeout", self.config.request_timeout_seconds)

        try:
            response = self.http_client.request(
                method=method.upper(),
                url=endpoint,
                headers=headers,
                **kwargs,
            )
        except httpx.HTTPError as error:
            raise UniformAgriApiError(
                f"Uniform Agri request failed for {endpoint}: {error}",
                endpoint=endpoint,
            ) from error

        if raise_for_status and response.is_error:
            self._raise_response_error(endpoint, response)

        return response

    def _raise_response_error(self, endpoint: str, response: httpx.Response) -> None:
        """Raise a project-specific API error with short response context."""
        error_type = (
            UniformAgriAuthenticationError
            if response.status_code in {401, 403}
            else UniformAgriApiError
        )
        response_context = response.text[:DEFAULT_RESPONSE_CONTEXT_LENGTH]
        raise error_type(
            (
                "Uniform Agri API returned "
                f"HTTP {response.status_code} for {endpoint}: {response_context}"
            ),
            endpoint=endpoint,
            status_code=response.status_code,
            response_text=response_context,
        )

    def _request_with_retry(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Make an authenticated HTTP request with token and transient retries."""
        response = self._send(method, endpoint, raise_for_status=False, **kwargs)

        if response.status_code == 401:
            self.token = self.get_access_token()
            response = self._send(method, endpoint, raise_for_status=False, **kwargs)

        retry_count = 0
        while (
            response.status_code in RETRYABLE_STATUS_CODES
            and retry_count < self.config.max_retries
        ):
            retry_count += 1
            response = self._send(method, endpoint, raise_for_status=False, **kwargs)

        if response.is_error:
            self._raise_response_error(endpoint, response)

        try:
            return response.json()
        except ValueError as error:
            raise UniformAgriApiError(
                f"Uniform Agri response for {endpoint} was not valid JSON.",
                endpoint=endpoint,
                status_code=response.status_code,
                response_text=response.text,
            ) from error

    def request(self, method: str, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        """Make HTTP request and return JSON response"""
        return self._request_with_retry(method, endpoint, **kwargs)

    def get(self, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        """GET request"""
        return self.request("GET", endpoint, **kwargs)

    def post(self, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        """POST request"""
        return self.request("POST", endpoint, **kwargs)
