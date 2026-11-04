from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import TCLApi
from .api_common import TCLApiError, TCLAuthError
from .capabilities import validate_write
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_REFRESH_TOKEN,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN_EXPIRES,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DOMAIN,
    MAX_SCAN_INTERVAL_SECONDS,
    MIN_SCAN_INTERVAL_SECONDS,
    MODEL_REFRESH_INTERVAL_SECONDS,
)
from .model import (
    model_fingerprint,
    model_properties,
    property_identifier,
)
from .registry import remove_stale_devices

_LOGGER = logging.getLogger(__name__)


@dataclass
class TCLDeviceData:
    """Combined device, status, and TSL data for one TCL device."""

    device: dict[str, Any]
    status: dict[str, Any]
    model: dict[str, Any]
    status_ok: bool = True
    status_error: str | None = None
    status_failures: int = 0
    last_status_success: datetime | None = None
    model_hash: str = ""

    @property
    def device_id(self) -> str:
        return str(self.device.get("deviceId") or self.device.get("id") or "")

    @property
    def product_key(self) -> str:
        return str(self.device.get("productKey") or "")


class TCLCoordinator(DataUpdateCoordinator[dict[str, TCLDeviceData]]):
    """Fetch TCL devices, current status, and TSL models."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: TCLApi,
    ) -> None:
        self.entry = entry
        self.api = api
        self._model_cache: dict[str, dict[str, Any]] = {}
        self._device_cache: dict[str, TCLDeviceData] = {}
        self._known_device_ids: set[str] | None = None
        self._known_model_hashes: dict[str, str] = {}
        self._model_fetched_at: dict[str, float] = {}
        self._write_lock = asyncio.Lock()
        interval = int(
            entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS)
        )
        interval = max(
            MIN_SCAN_INTERVAL_SECONDS, min(interval, MAX_SCAN_INTERVAL_SECONDS)
        )
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(seconds=interval),
        )

    async def _async_update_data(self) -> dict[str, TCLDeviceData]:
        try:
            devices = await self.api.async_get_devices()
            result: dict[str, TCLDeviceData] = {}
            listed_device_ids = {
                str(device.get("deviceId") or device.get("id") or "")
                for device in devices
                if str(device.get("deviceId") or device.get("id") or "")
            }

            async def load_device(device: dict[str, Any]) -> TCLDeviceData:
                device_id = str(device.get("deviceId") or device.get("id") or "")
                previous = self._device_cache.get(device_id)
                status = previous.status if previous else {}
                status_ok = True
                status_error = None
                status_failures = 0
                last_status_success = previous.last_status_success if previous else None
                try:
                    status = await self.api.async_get_status(device_id)
                except TCLAuthError:
                    raise
                except TCLApiError as err:
                    status_ok = False
                    status_error = type(err).__name__
                    status_failures = (previous.status_failures if previous else 0) + 1
                    _LOGGER.warning(
                        "Unable to refresh a TCL device status (%s)",
                        type(err).__name__,
                    )
                else:
                    last_status_success = datetime.now(UTC)

                model = previous.model if previous else {}
                product_key = str(device.get("productKey") or "")
                if product_key and self._should_refresh_model(product_key):
                    model = await self._async_get_model(product_key)
                return TCLDeviceData(
                    device=device,
                    status=status,
                    model=model,
                    status_ok=status_ok,
                    status_error=status_error,
                    status_failures=status_failures,
                    last_status_success=last_status_success,
                    model_hash=model_fingerprint(model),
                )

            loaded = await asyncio.gather(
                *(load_device(device) for device in devices),
                return_exceptions=True,
            )
            for device, item in zip(devices, loaded):
                if isinstance(item, TCLAuthError):
                    raise item
                if isinstance(item, Exception):
                    device_id = str(device.get("deviceId") or device.get("id") or "")
                    previous = self._device_cache.get(device_id)
                    _LOGGER.warning(
                        "Failed to load a TCL device (%s)",
                        type(item).__name__,
                    )
                    if device_id:
                        result[device_id] = TCLDeviceData(
                            device=device,
                            status=previous.status if previous else {},
                            model=previous.model if previous else {},
                            status_ok=False,
                            status_error=type(item).__name__,
                            status_failures=(
                                previous.status_failures if previous else 0
                            )
                            + 1,
                            last_status_success=(
                                previous.last_status_success if previous else None
                            ),
                            model_hash=model_fingerprint(
                                previous.model if previous else {}
                            ),
                        )
                    continue
                if item.device_id:
                    result[item.device_id] = item

            self._device_cache = result
            current_device_ids = set(result)
            current_model_hashes = {
                device_id: item.model_hash
                for device_id, item in result.items()
                if item.model_hash
            }
            # The device list is the authoritative deletion signal. A temporary
            # status/model failure must never make a still-listed device stale.
            remove_stale_devices(self.hass, self.entry, listed_device_ids)
            if (
                self._known_device_ids is not None
                and current_device_ids != self._known_device_ids
            ) or (
                self._known_model_hashes
                and current_model_hashes != self._known_model_hashes
            ):
                self.hass.async_create_task(self._async_reload_entry())
            self._known_device_ids = current_device_ids
            self._known_model_hashes = current_model_hashes
            await self._async_persist_tokens()
            return result
        except TCLAuthError as err:
            raise ConfigEntryAuthFailed("TCL authorization expired") from err
        except TCLApiError:
            raise UpdateFailed("TCL update failed") from None

    async def _async_reload_entry(self) -> None:
        """Reload platforms when the cloud device set changes."""
        try:
            await self.hass.config_entries.async_reload(self.entry.entry_id)
        except Exception:
            _LOGGER.exception("Failed to reload TCL Smart Home after device change")

    def _should_refresh_model(self, product_key: str) -> bool:
        # A failed first fetch must not hide appliance capabilities for 15 minutes.
        interval = (
            MODEL_REFRESH_INTERVAL_SECONDS
            if self._model_cache.get(product_key, {}).get("properties")
            else 60
        )
        return (
            product_key not in self._model_cache
            or time.monotonic() - self._model_fetched_at.get(product_key, 0) >= interval
        )

    async def _async_get_model(self, product_key: str) -> dict[str, Any]:
        try:
            self._model_cache[product_key] = await self.api.async_get_model(product_key)
            self._model_fetched_at[product_key] = time.monotonic()
        except TCLAuthError:
            raise
        except TCLApiError as err:
            _LOGGER.warning("Failed to load a TCL model (%s)", type(err).__name__)
            if product_key not in self._model_cache:
                self._model_cache[product_key] = {}
            self._model_fetched_at[product_key] = time.monotonic()
        return self._model_cache[product_key]

    async def _async_persist_tokens(self) -> None:
        if not self.api.tokens_changed:
            return
        data = dict(self.entry.data)
        data.update(
            {
                CONF_ACCESS_TOKEN: self.api.access_token,
                CONF_REFRESH_TOKEN: self.api.refresh_token,
                CONF_TOKEN_EXPIRES: self.api.token_expires,
            }
        )
        self.hass.config_entries.async_update_entry(self.entry, data=data)
        self.api.tokens_changed = False

    @property
    def devices(self) -> dict[str, TCLDeviceData]:
        return self.data or {}

    def get_device(self, device_id: str) -> TCLDeviceData | None:
        return self.devices.get(device_id)

    async def async_set_property(
        self,
        device_id: str,
        property_name: str,
        value: Any,
    ) -> None:
        async with self._write_lock:
            try:
                device = self.get_device(device_id)
                if device is None:
                    raise HomeAssistantError(
                        translation_domain=DOMAIN,
                        translation_key="device_not_found",
                        translation_placeholders={"device_id": device_id},
                    )

                property_def = next(
                    (
                        prop
                        for prop in model_properties(device.model)
                        if property_identifier(prop) == property_name
                    ),
                    None,
                )
                if property_def is None:
                    raise HomeAssistantError(
                        translation_domain=DOMAIN,
                        translation_key="property_not_found",
                        translation_placeholders={"property": property_name},
                    )
                if "w" not in str(property_def.get("accessMode") or "").lower():
                    raise HomeAssistantError(
                        translation_domain=DOMAIN,
                        translation_key="property_read_only",
                        translation_placeholders={"property": property_name},
                    )

                try:
                    value = validate_write(
                        device.device, device.model, property_def, value
                    )
                except ValueError as err:
                    raise HomeAssistantError(
                        translation_domain=DOMAIN,
                        translation_key="control_not_allowed",
                    ) from err
                await self.api.async_control(
                    device_id,
                    {property_name: value},
                )
                await self.async_request_refresh()
            except TCLAuthError as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="authorization_expired",
                ) from err
            except TCLApiError as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="api_error",
                    translation_placeholders={
                        "code": str(err.code or "unknown"),
                        "message": "TCL request failed",
                    },
                ) from err
