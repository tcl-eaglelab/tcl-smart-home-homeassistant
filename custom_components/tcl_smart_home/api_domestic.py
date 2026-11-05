from __future__ import annotations

import secrets
import time
from collections.abc import Mapping
from typing import Any
from urllib.parse import quote, urlencode

from .api_common import (
    TCLApiError,
    TCLAuthError,
    TCLCloudClient,
    is_success,
    is_token_error,
    jwt_expiry_ms,
    jwt_user_id,
    lock_online_headers,
    parse_lock_types,
    response_succeeded,
    safe_qr_url,
)
from .const import (
    DOMESTIC_APP_ID as APP_ID,
)
from .const import (
    DOMESTIC_AUTH_URL as AUTH_URL,
)
from .const import (
    DOMESTIC_IOT_URL as IOT_URL,
)
from .const import (
    DOMESTIC_STORE_UUID as STORE_UUID,
)
from .const import (
    DOMESTIC_TENANT_ID as TENANT_ID,
)
from .const import (
    TOKEN_REFRESH_WINDOW_MS,
)


class DomesticApi(TCLCloudClient):
    """Domestic TCL account-center and IoT client."""

    async def async_get_qr(self) -> dict[str, str]:
        query = urlencode(
            {
                "appId": APP_ID,
                "width": "400",
                "height": "400",
                "to": "qrlogin",
                "deviceName": "home-assistant",
                "from": f"home-assistant_{int(time.time() * 1000)}",
            }
        )
        response = await self._raw_request(
            "GET",
            f"{AUTH_URL}/auth/common/v2/getQRCodePic?{query}",
            authenticated=False,
        )
        if response.get("status") != 1:
            raise TCLAuthError("Unable to generate QR code")
        data = response.get("data") or {}
        code = str(data.get("code") or "")
        if not code:
            raise TCLAuthError("QR response did not contain a code")
        image_url = str(data.get("imageUrl") or "")
        if not image_url:
            image_url = f"{AUTH_URL}/auth/common/v2/generateQRCodePic?" + urlencode(
                {"code": code}
            )
        return {"code": code, "image_url": safe_qr_url(image_url, AUTH_URL)}

    async def async_check_qr(self, code: str) -> dict[str, Any]:
        query = urlencode({"code": code})
        return await self._raw_request(
            "GET",
            f"{AUTH_URL}/auth/common/v2/checkQRCodeAuthor?{query}",
            authenticated=False,
        )

    async def _async_refresh_token(
        self,
        *,
        failed_access_token: str | None = None,
    ) -> None:
        """Refresh once for concurrent callers sharing the same account."""
        async with self._token_lock:
            if (
                failed_access_token
                and self.access_token
                and self.access_token != failed_access_token
            ):
                return
            if (
                not failed_access_token
                and self.access_token
                and self.token_expires
                > int(time.time() * 1000) + TOKEN_REFRESH_WINDOW_MS
            ):
                return
            if not self.application_secret:
                raise TCLAuthError("Application credentials are not configured")
            if not self.refresh_token:
                raise TCLAuthError("Missing refresh token")
            query = urlencode(
                {
                    "appId": APP_ID,
                    "appSecret": self.application_secret,
                    "tenantId": TENANT_ID,
                }
            )
            response = await self._raw_request(
                "POST",
                f"{AUTH_URL}/auth/auth/refershToken?{query}",
                headers={"refreshToken": self.refresh_token},
                authenticated=False,
            )
            if not is_success(response):
                raise TCLAuthError("Token refresh failed")
            token_data = response.get("data")
            if not isinstance(token_data, Mapping):
                token_data = response
            access_token = token_data.get("accessToken")
            refresh_token = token_data.get("refreshToken")
            if not access_token:
                raise TCLAuthError("Refresh response did not contain accessToken")
            self.access_token = str(access_token)
            self.refresh_token = str(refresh_token or self.refresh_token)
            self.token_expires = jwt_expiry_ms(self.access_token)
            self.tokens_changed = True

    async def async_get_devices(self) -> list[dict[str, Any]]:
        data = await self._request(
            "GET", f"{IOT_URL}/v1/tclplus/user/user_devices/openclaw"
        )
        if not isinstance(data, list):
            raise TCLApiError("Device list response is not a list")
        return [dict(device) for device in data if isinstance(device, Mapping)]

    async def async_get_lock_online(
        self,
        device_id: str,
        *,
        product_key: str = "",
        user_id: str = "",
    ) -> dict[str, Any]:
        """Shadow online plus TCP keepalive for one door lock."""
        query = urlencode({"deviceId": device_id})
        data = await self._request(
            "GET",
            f"{IOT_URL}/v1/slk/device/online/status?{query}",
            headers=lock_online_headers(
                device_id, product_key=product_key, user_id=user_id
            ),
        )
        return dict(data) if isinstance(data, Mapping) else {}

    async def async_get_lock_types(
        self, product_keys: list[str], *, user_id: str = ""
    ) -> dict[str, int]:
        """Map productKey to lockType: 0 short-link, 1 long-link."""
        keys = [str(key) for key in product_keys if str(key)]
        if not keys:
            return {}
        resolved_user = user_id or jwt_user_id(self.access_token)
        if not resolved_user:
            raise TCLApiError("Missing userId for lock type lookup")
        data = await self._request(
            "POST",
            f"{IOT_URL}/v1/slk/settings/lock/type",
            payload={"userId": resolved_user, "pks": keys},
            accept_codes=(0, "0"),
        )
        return parse_lock_types(data)

    async def async_get_status(self, device_id: str) -> dict[str, Any]:
        data = await self._request(
            "POST",
            f"{IOT_URL}/v1/thing/status/openclaw",
            payload={"deviceId": device_id},
        )
        if isinstance(data, Mapping) and isinstance(data.get("status"), Mapping):
            return dict(data["status"])
        return dict(data) if isinstance(data, Mapping) else {}

    async def async_get_model(self, product_key: str) -> dict[str, Any]:
        data = await self._request(
            "GET",
            f"{IOT_URL}/tsl/{quote(product_key, safe="")}/tsl/openclaw",
        )
        return dict(data) if isinstance(data, Mapping) else {}

    async def async_control(
        self,
        device_id: str,
        properties: Mapping[str, Any],
    ) -> None:
        await self._request(
            "POST",
            f"{IOT_URL}/v1/control/property/{quote(device_id, safe="")}/openclaw",
            payload={
                "msgId": secrets.token_hex(16),
                "params": [dict(properties)],
                "version": "1.0",
            },
        )

    async def _request(
        self,
        method: str,
        request_url: str,
        *,
        payload: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        accept_codes: tuple[Any, ...] = (),
        retry: bool = True,
    ) -> Any:
        await self._ensure_token()
        request_headers = {
            "accessToken": self.access_token,
            "Content-Type": "application/json",
            "t-store-uuid": STORE_UUID,
        }
        if headers:
            request_headers.update(headers)
        response = await self._raw_request(
            method,
            request_url,
            payload=payload,
            headers=request_headers,
            authenticated=True,
        )
        if is_token_error(response) and retry:
            failed_access_token = self.access_token
            await self._async_refresh_token(
                failed_access_token=failed_access_token,
            )
            return await self._request(
                method,
                request_url,
                payload=payload,
                headers=headers,
                accept_codes=accept_codes,
                retry=False,
            )
        if not response_succeeded(response, accept_codes):
            raise TCLApiError(
                "TCL API request failed",
            )
        return response.get("data")
