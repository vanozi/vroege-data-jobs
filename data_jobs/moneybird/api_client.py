"""Read-only Moneybird API client."""

from collections.abc import Callable
import logging
import time
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

import httpx

from data_jobs.moneybird.config import MoneybirdConfig
from data_jobs.moneybird import config as moneybird_config
from data_jobs.moneybird.exceptions import (
    MoneybirdApiError,
    MoneybirdAuthenticationError,
    MoneybirdRateLimitError,
)


DEFAULT_RESPONSE_CONTEXT_LENGTH = 500
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def build_moneybird_client(
    config: Optional[MoneybirdConfig] = None,
) -> "MoneybirdClient":
    """Build a Moneybird API client from explicit or environment config."""
    return MoneybirdClient(config=config)


class MoneybirdClient:
    """Small read-only Moneybird API client with pagination and retries."""

    def __init__(
        self,
        config: Optional[MoneybirdConfig] = None,
        http_client: Optional[httpx.Client] = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.config = config or moneybird_config.load_moneybird_config()
        self._owns_http_client = http_client is None
        self.http_client = http_client or httpx.Client(
            base_url=self.config.base_url,
            timeout=self.config.request_timeout_seconds,
        )
        self._sleep = sleep

    def close(self) -> None:
        """Close the underlying HTTP client when this instance owns it."""
        if self._owns_http_client:
            self.http_client.close()

    def __enter__(self) -> "MoneybirdClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def list_administrations(self) -> list[dict[str, Any]]:
        """Return all administrations accessible for the configured token."""
        response = self.get_json("/administrations.json")
        if not isinstance(response, list):
            raise MoneybirdApiError(
                "Moneybird administrations response was not a list.",
                endpoint="/administrations.json",
            )

        return _ensure_dict_list(response, endpoint="/administrations.json")

    def get_json(
        self,
        path: str,
        params: Optional[dict[str, str]] = None,
    ) -> Any:
        """Perform a GET request and return the parsed JSON response."""
        response = self._request_with_retry("GET", path, params=params)
        return self._parse_json(path, response)

    def post_json(
        self,
        path: str,
        json: Optional[dict[str, object]] = None,
    ) -> Any:
        """Perform a POST request and return the parsed JSON response."""
        response = self._request_with_retry("POST", path, json=json)
        return self._parse_json(path, response)

    def get_paginated(
        self,
        path: str,
        params: Optional[dict[str, str]] = None,
        logger: Optional[logging.Logger] = None,
        progress_interval_pages: int = 5,
    ) -> list[dict[str, Any]]:
        """Collect all pages from a paginated Moneybird list endpoint."""
        collected_rows: list[dict[str, Any]] = []
        request_params = dict(params or {})
        request_params.setdefault("per_page", "100")
        request_params.setdefault("page", "1")
        page_count = 0

        while True:
            response = self._request_with_retry("GET", path, params=request_params)
            parsed_response = self._parse_json(path, response)
            if not isinstance(parsed_response, list):
                raise MoneybirdApiError(
                    "Moneybird paginated response was not a list.",
                    endpoint=path,
                    status_code=response.status_code,
                    response_text=self._safe_response_text(response),
                )

            rows = _ensure_dict_list(parsed_response, endpoint=path)
            collected_rows.extend(rows)
            page_count += 1
            _log_paginated_progress(
                logger,
                path=path,
                page_count=page_count,
                row_count=len(collected_rows),
                progress_interval_pages=progress_interval_pages,
            )

            next_page = _next_page_from_link_header(response.headers.get("Link"))
            if next_page is None:
                if len(rows) >= int(request_params["per_page"]):
                    request_params["page"] = str(int(request_params["page"]) + 1)
                    continue
                break

            request_params["page"] = next_page

        return collected_rows

    def _request_with_retry(
        self,
        method: str,
        path: str,
        params: Optional[dict[str, str]] = None,
        json: Optional[dict[str, object]] = None,
    ) -> httpx.Response:
        attempt = 0

        while True:
            response = self._send(method, path, params=params, json=json)
            if response.status_code not in RETRYABLE_STATUS_CODES:
                break

            if attempt >= self.config.max_retries:
                self._raise_response_error(path, response)

            delay_seconds = _retry_delay_seconds(
                response,
                attempt=attempt,
                fallback_backoff_seconds=self.config.retry_backoff_seconds,
            )
            if delay_seconds > 0:
                self._sleep(delay_seconds)
            attempt += 1

        if response.is_error:
            self._raise_response_error(path, response)

        return response

    def _send(
        self,
        method: str,
        path: str,
        params: Optional[dict[str, str]] = None,
        json: Optional[dict[str, object]] = None,
    ) -> httpx.Response:
        try:
            return self.http_client.request(
                method=method.upper(),
                url=path,
                params=params,
                json=json,
                headers=self._headers(),
            )
        except httpx.HTTPError as error:
            raise MoneybirdApiError(
                f"Moneybird request failed for {path}: {error}",
                endpoint=path,
            ) from error

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.access_token}",
        }
        if self.config.time_zone:
            headers["Time-Zone"] = self.config.time_zone

        return headers

    def _parse_json(self, path: str, response: httpx.Response) -> Any:
        try:
            return response.json()
        except ValueError as error:
            raise MoneybirdApiError(
                f"Moneybird response for {path} was not valid JSON.",
                endpoint=path,
                status_code=response.status_code,
                response_text=self._safe_response_text(response),
            ) from error

    def _raise_response_error(self, path: str, response: httpx.Response) -> None:
        error_type: type[MoneybirdApiError]
        if response.status_code in {401, 403}:
            error_type = MoneybirdAuthenticationError
        elif response.status_code == 429:
            error_type = MoneybirdRateLimitError
        else:
            error_type = MoneybirdApiError

        response_context = self._safe_response_text(response)
        raise error_type(
            f"Moneybird API returned HTTP {response.status_code} for {path}.",
            endpoint=path,
            status_code=response.status_code,
            response_text=response_context,
        )

    def _safe_response_text(self, response: httpx.Response) -> str:
        response_text = response.text[:DEFAULT_RESPONSE_CONTEXT_LENGTH]
        return response_text.replace(self.config.access_token, "[REDACTED]")


def _ensure_dict_list(value: list[Any], *, endpoint: str) -> list[dict[str, Any]]:
    rows = []
    for item in value:
        if not isinstance(item, dict):
            raise MoneybirdApiError(
                "Moneybird list response contained a non-object item.",
                endpoint=endpoint,
            )
        rows.append(item)

    return rows


def _next_page_from_link_header(link_header: Optional[str]) -> Optional[str]:
    if not link_header:
        return None

    for link_part in link_header.split(","):
        segments = [segment.strip() for segment in link_part.split(";")]
        if len(segments) < 2:
            continue

        link_target = segments[0]
        if not link_target.startswith("<") or not link_target.endswith(">"):
            continue
        if 'rel="next"' not in segments[1:]:
            continue

        parsed_url = urlparse(link_target[1:-1])
        next_page = parse_qs(parsed_url.query).get("page")
        if next_page:
            return next_page[0]

    return None


def _retry_delay_seconds(
    response: httpx.Response,
    *,
    attempt: int,
    fallback_backoff_seconds: float,
) -> float:
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            return max(float(retry_after), 0)
        except ValueError:
            pass

    return fallback_backoff_seconds * (2**attempt)


def _log_paginated_progress(
    logger: Optional[logging.Logger],
    *,
    path: str,
    page_count: int,
    row_count: int,
    progress_interval_pages: int,
) -> None:
    if logger is None:
        return
    if progress_interval_pages <= 0:
        return
    if page_count % progress_interval_pages != 0:
        return

    logger.info(
        "Fetched %s Moneybird pages from %s; rows_so_far=%s.",
        page_count,
        path,
        row_count,
    )
