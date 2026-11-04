from __future__ import annotations

import asyncio
import base64
import binascii
import json
import time
from collections.abc import Mapping
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urljoin, urlsplit

import aiohttp

from .const import HTTP_TIMEOUT, MAX_CONCURRENT_REQUESTS, TOKEN_REFRESH_WINDOW_MS


class TCLApiError(Exception):
    """Base TCL API error."""

    def __init__(self, message: str, *, code: Any | None = None) -> None:
        super().__init__(message)
        self.code = code


class TCLAuthError(TCLApiError):
    """TCL authentication error."""


class TCLConnectionError(TCLApiError):
    """TCL connection error."""


class TCLRateLimitError(TCLApiError):
    """Account requests are temporarily paused."""


ALLOWED_HOSTS = frozenset(
    {
        "cn.account.tcl.com",
        "sg.account.tcl.com",
        "pa.account.tcl.com",
        "us.account.tcl.com",
        "br.account.tcl.com",
        "io.zx.tcljd.com",
        "sgp-iot-api-prod.tcljd.com",
        "eu-iot-api-prod.tcljd.com",
        "us-iot-api-prod.tcljd.com",
        "br-iot-api-prod.tcljd.com",
    }
)


def safe_qr_url(value: str, auth_url: str) -> str:
    """Only same-origin HTTPS QR images; unexpected CDNs need explicit review."""
    resolved = urljoin(auth_url, value)
    try:
        parts = urlsplit(resolved)
        valid = (
            parts.scheme == "https"
            and parts.hostname == urlsplit(auth_url).hostname
            and parts.hostname in ALLOWED_HOSTS
            and parts.port in (None, 443)
            and not parts.username
            and not parts.password
            and not parts.fragment
            and not any(ch in resolved for ch in "\r\n\t\\()<>")
        )
    except ValueError:
        valid = False
    if not valid:
        raise TCLApiError("Untrusted QR image URL")
    return resolved


def retry_seconds(value: str | None) -> float:
    try:
        delay = float(value)
    except (TypeError, ValueError):
        try:
            delay = (parsedate_to_datetime(value) - datetime.now(UTC)).total_seconds()
        except (TypeError, ValueError, OverflowError):
            delay = 60
    if not 0 <= delay <= 3600:
        delay = 3600 if delay > 3600 else 60
    return max(30, delay)


class TCLCloudClient:
    """Shared transport, authentication state and QR response handling."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        *,
        access_token: str | None = None,
        refresh_token: str | None = None,
        token_expires: int = 0,
        verify_ssl: bool = True,
        application_secret: str = "",
    ) -> None:
        self._session = session
        self.access_token = access_token or ""
        self.refresh_token = refresh_token or ""
        self.token_expires = token_expires
        self.verify_ssl = True
        self.application_secret = application_secret
        self._cooldown_until = 0.0
        self._failure_delay = 30.0
        self.tokens_changed = False
        self._token_lock = asyncio.Lock()
        self._request_semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    async def async_try_authorize_qr(self, code: str) -> bool:
        """Check QR authorization once without blocking the config flow."""
        response = await self.async_check_qr(code)
        data = response.get("data") or {}
        token = data.get("token") or data.get("accessToken")
        if response.get("status") in (1, "1") and token:
            self.access_token = str(token)
            self.refresh_token = str(data.get("refreshToken") or "")
            self.token_expires = jwt_expiry_ms(self.access_token)
            self.tokens_changed = True
            return True
        message = str(response.get("msg") or response.get("message") or "").lower()
        if any(
            value in message
            for value in ("expired", "expire", "invalid", "timeout", "过期", "失效")
        ):
            raise TCLAuthError("QR code expired")
        return False

    async def _ensure_token(self) -> None:
        if not self.access_token:
            raise TCLAuthError("Not authorized")
        if (
            self.token_expires
            and self.token_expires <= int(time.time() * 1000) + TOKEN_REFRESH_WINDOW_MS
        ):
            await self._async_refresh_token()

    async def _raw_request(
        self,
        method: str,
        request_url: str,
        *,
        headers: Mapping[str, str] | None = None,
        payload: Mapping[str, Any] | None = None,
        authenticated: bool,
    ) -> dict[str, Any]:
        try:
            parsed = urlsplit(request_url)
            valid = (
                parsed.scheme == "https"
                and parsed.hostname in ALLOWED_HOSTS
                and parsed.port in (None, 443)
                and not parsed.username
                and not parsed.password
            )
        except ValueError:
            valid = False
        if not valid:
            raise TCLApiError("Untrusted API endpoint")
        request_headers = {"Accept": "application/json"}
        if headers:
            request_headers.update(headers)
        try:
            async with self._request_semaphore:
                if time.monotonic() < self._cooldown_until:
                    raise TCLRateLimitError("TCL requests temporarily paused", code=429)
                async with self._session.request(
                    method,
                    request_url,
                    headers=request_headers,
                    json=payload,
                    ssl=True,
                    allow_redirects=False,
                    timeout=aiohttp.ClientTimeout(total=HTTP_TIMEOUT),
                ) as response:
                    if 300 <= response.status < 400:
                        raise TCLApiError("TCL redirects are not allowed")
                    if response.status in (401, 403) and authenticated:
                        return {"code": 401, "message": "token expired"}
                    if response.status == 429:
                        self._cooldown_until = time.monotonic() + retry_seconds(
                            response.headers.get("Retry-After")
                        )
                        raise TCLRateLimitError("TCL rate limit reached", code=429)
                    if response.status >= 500:
                        self._cooldown_until = time.monotonic() + self._failure_delay
                        self._failure_delay = min(900, self._failure_delay * 2)
                    if response.status >= 400:
                        raise TCLApiError(
                            f"TCL HTTP error {response.status}", code=response.status
                        )
                    try:
                        response_payload = await response.json()
                    except (aiohttp.ContentTypeError, json.JSONDecodeError):
                        raise TCLApiError("TCL returned invalid JSON") from None
                    if not isinstance(response_payload, dict):
                        raise TCLApiError("TCL API response is not an object")
                    self._failure_delay = 30
                    return response_payload
        except TCLApiError:
            raise
        except (aiohttp.ClientError, TimeoutError):
            self._cooldown_until = time.monotonic() + self._failure_delay
            self._failure_delay = min(900, self._failure_delay * 2)
            raise TCLConnectionError("Unable to connect to TCL") from None


def is_success(response: Mapping[str, Any]) -> bool:
    code = response.get("code")
    return response.get("success") is True or code in (1, "1", 200, "200")


def is_token_error(response: Mapping[str, Any]) -> bool:
    code = response.get("code")
    message = str(response.get("message") or response.get("msg") or "").lower()
    return code in (401, "401") or "token" in message


def jwt_expiry_ms(token: str) -> int:
    try:
        payload = token.split(".")[1]
        padding = "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload + padding))
        return int(claims["exp"]) * 1000
    except (
        IndexError,
        KeyError,
        ValueError,
        TypeError,
        binascii.Error,
        json.JSONDecodeError,
    ):
        return int(time.time() * 1000) + 60 * 60 * 1000
