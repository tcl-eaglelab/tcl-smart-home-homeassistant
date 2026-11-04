from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import (
    ConfigEntryNotReady,
    HomeAssistantError,
    Unauthorized,
)
from homeassistant.helpers import aiohttp_client, service
from homeassistant.helpers import config_validation as cv

from .api import create_api
from .api_common import TCLAuthError, TCLConnectionError
from .const import (
    ATTR_DEVICE_ID,
    ATTR_PROPERTY,
    ATTR_VALUE,
    CONF_ACCESS_TOKEN,
    CONF_COUNTRY_CODE,
    CONF_REFRESH_TOKEN,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN_EXPIRES,
    CONF_VERIFY_SSL,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DOMAIN,
    MIN_SCAN_INTERVAL_SECONDS,
    NAME,
    PLATFORMS,
    SERVICE_SET_PROPERTY,
)
from .coordinator import TCLCoordinator
from .credentials import application_secret
from .qr_frontend import async_setup_qr_frontend
from .registry import apply_capability_policy
from .routing import get_country_route

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(DOMAIN): vol.Schema(
            {
                vol.Optional("domestic_app_secret"): cv.string,
                vol.Optional("overseas_client_secret"): cv.string,
            }
        ),
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the TCL Smart Home integration."""
    hass.data[DOMAIN] = dict(config.get(DOMAIN, {}))
    await async_setup_qr_frontend(hass)

    async def handle_set_property(call: ServiceCall) -> None:
        if not call.context.user_id:
            raise Unauthorized()
        device_id = str(call.data[ATTR_DEVICE_ID])
        property_name = str(call.data[ATTR_PROPERTY])
        value = call.data[ATTR_VALUE]
        for config_entry in hass.config_entries.async_entries(DOMAIN):
            coordinator = getattr(config_entry, "runtime_data", None)
            if coordinator is None:
                continue
            if coordinator.get_device(device_id):
                await coordinator.async_set_property(device_id, property_name, value)
                return
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="device_not_found",
            translation_placeholders={"device_id": device_id},
        )

    service.async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_SET_PROPERTY,
        handle_set_property,
        schema=vol.Schema(
            {
                vol.Required(ATTR_DEVICE_ID): cv.string,
                vol.Required(ATTR_PROPERTY): cv.string,
                vol.Required(ATTR_VALUE): vol.Any(
                    str,
                    bool,
                    int,
                    float,
                ),
            }
        ),
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up TCL Smart Home from a config entry."""
    # Entries created by the former domestic-only plugin had no country code.
    # Treat them as mainland China so an upgrade keeps their tokens and IDs.
    if not entry.data.get(CONF_COUNTRY_CODE):
        data = {**entry.data, CONF_COUNTRY_CODE: "CN"}
        hass.config_entries.async_update_entry(
            entry,
            data=data,
            title=f"{NAME} (CN)",
        )
    try:
        route = get_country_route(str(entry.data.get(CONF_COUNTRY_CODE, "")))
    except ValueError as err:
        raise ConfigEntryNotReady("TCL country routing is not configured") from err

    if (
        entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS)
        < MIN_SCAN_INTERVAL_SECONDS
    ):
        hass.config_entries.async_update_entry(
            entry,
            options={
                **entry.options,
                CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL_SECONDS,
            },
        )
    secret = application_secret(hass, route.code)
    if not secret:
        raise ConfigEntryNotReady(
            "Configure TCL application credentials in configuration.yaml using !secret before loading this integration"
        )
    if entry.data.get(CONF_VERIFY_SSL) is False:
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_VERIFY_SSL: True}
        )
    session = aiohttp_client.async_get_clientsession(
        hass,
        verify_ssl=True,
    )
    api = create_api(
        session,
        route,
        access_token=entry.data.get(CONF_ACCESS_TOKEN),
        refresh_token=entry.data.get(CONF_REFRESH_TOKEN),
        token_expires=entry.data.get(CONF_TOKEN_EXPIRES, 0),
        application_secret=secret,
        verify_ssl=True,
    )
    coordinator = TCLCoordinator(hass, entry, api)
    try:
        await coordinator.async_config_entry_first_refresh()
    except TCLAuthError as err:
        raise ConfigEntryNotReady("TCL authorization is required") from err
    except TCLConnectionError as err:
        raise ConfigEntryNotReady("TCL service is not reachable") from err

    entry.runtime_data = coordinator
    apply_capability_policy(hass, entry, coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a TCL Smart Home config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
