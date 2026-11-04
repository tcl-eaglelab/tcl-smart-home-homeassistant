from __future__ import annotations

import time
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import OptionsFlowWithReload
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client

from .api import create_api
from .api_common import TCLApiError, TCLAuthError, TCLConnectionError
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_COUNTRY_CODE,
    CONF_REFRESH_TOKEN,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN_EXPIRES,
    CONF_VERIFY_SSL,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DOMAIN,
    MAX_SCAN_INTERVAL_SECONDS,
    MIN_SCAN_INTERVAL_SECONDS,
    NAME,
    QR_VALIDITY_SECONDS,
)
from .credentials import application_secret
from .qr_frontend import async_setup_qr_frontend
from .routing import country_options, get_country_route


class TCLConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Select an account country, then scan and confirm with native buttons."""

    VERSION = 1

    def __init__(self) -> None:
        self._qr_code = ""
        self._qr_url = ""
        self._country_code = ""
        self._qr_created_at = 0.0
        self._qr_step_id = "authorize"
        self._reauth_entry: config_entries.ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        await async_setup_qr_frontend(self.hass)
        errors = {}
        if user_input is not None:
            try:
                route = get_country_route(
                    str(user_input.get(CONF_COUNTRY_CODE, "")).upper()
                )
            except ValueError:
                errors["base"] = "invalid_country"
            else:
                self._country_code = route.code
                if route.code == "CN":
                    for entry in self.hass.config_entries.async_entries(DOMAIN):
                        if not entry.data.get(CONF_COUNTRY_CODE):
                            return self.async_abort(reason="already_configured")
                await self.async_set_unique_id(f"{DOMAIN}_{route.code.lower()}")
                self._abort_if_unique_id_configured()
                return await self.async_step_refresh_qr()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_COUNTRY_CODE): vol.In(
                        {
                            option["value"]: option["label"]
                            for option in country_options()
                        }
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> config_entries.FlowResult:
        await async_setup_qr_frontend(self.hass)
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        self._country_code = str(entry_data.get(CONF_COUNTRY_CODE, "CN")).upper()
        return await self.async_step_refresh_qr()

    async def async_step_refresh_qr(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """One button click fetches a fresh code; no confirmation form."""
        return await self._async_new_qr()

    async def async_step_authorize(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Redisplay the current menu when HA resumes this flow."""
        return self._show_qr_menu(self._qr_step_id)

    # HA requires a handler for each localized menu step, including redisplay.
    async_step_authorize_pending = async_step_authorize
    async_step_authorize_expired = async_step_authorize
    async_step_authorize_failed = async_step_authorize
    async_step_authorize_retry = async_step_authorize
    async_step_authorize_unavailable = async_step_authorize

    async def _async_new_qr(
        self, step_id: str = "authorize"
    ) -> config_entries.FlowResult:
        # Clear the old code first so a failed refresh cannot authorize it.
        self._qr_code = ""
        self._qr_url = ""
        self._qr_created_at = 0.0
        if not application_secret(self.hass, self._country_code):
            return self.async_abort(reason="missing_application_credentials")
        try:
            api = create_api(
                aiohttp_client.async_get_clientsession(self.hass),
                get_country_route(self._country_code),
                application_secret=application_secret(self.hass, self._country_code),
            )
            qr = await api.async_get_qr()
            self._qr_code, self._qr_url = qr["code"], qr["image_url"]
            self._qr_created_at = time.monotonic()
        except (TCLApiError, ValueError):
            return self._show_qr_menu("authorize_unavailable")
        return self._show_qr_menu(step_id)

    async def async_step_check_authorization(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Check once and leave both buttons usable while authorization is pending."""
        if not self._qr_code:
            return await self._async_new_qr()
        if time.monotonic() - self._qr_created_at >= QR_VALIDITY_SECONDS:
            return await self._async_new_qr("authorize_expired")
        api = create_api(
            aiohttp_client.async_get_clientsession(self.hass),
            get_country_route(self._country_code),
            application_secret=application_secret(self.hass, self._country_code),
        )
        try:
            if not await api.async_try_authorize_qr(self._qr_code):
                return self._show_qr_menu("authorize_pending")
        except TCLAuthError as err:
            if any(word in str(err).lower() for word in ("expired", "invalid")):
                return await self._async_new_qr("authorize_expired")
            return self._show_qr_menu("authorize_failed")
        except TCLConnectionError:
            return self._show_qr_menu("authorize_retry")
        except (TCLApiError, ValueError):
            return self._show_qr_menu("authorize_failed")
        try:
            await api.async_get_devices()
        except TCLApiError:
            return self._show_qr_menu("authorize_failed")
        token_data = {
            CONF_COUNTRY_CODE: self._country_code,
            CONF_ACCESS_TOKEN: api.access_token,
            CONF_REFRESH_TOKEN: api.refresh_token,
            CONF_TOKEN_EXPIRES: api.token_expires,
            CONF_VERIFY_SSL: True,
        }
        if self._reauth_entry:
            return self.async_update_reload_and_abort(
                self._reauth_entry, data={**self._reauth_entry.data, **token_data}
            )
        return self.async_create_entry(
            title=f"{NAME} ({self._country_code})", data=token_data
        )

    def _show_qr_menu(self, step_id: str) -> config_entries.FlowResult:
        self._qr_step_id = step_id
        return self.async_show_menu(
            step_id=step_id,
            menu_options=(
                ["check_authorization", "refresh_qr"]
                if self._qr_code
                else ["refresh_qr"]
            ),
            description_placeholders={"qr_url": self._qr_url},
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return TCLOptionsFlow()


class TCLOptionsFlow(OptionsFlowWithReload):
    """Configure polling behavior for TCL Smart Home."""

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.FlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current_interval = int(
            self.config_entry.options.get(
                CONF_SCAN_INTERVAL,
                DEFAULT_SCAN_INTERVAL_SECONDS,
            )
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=max(
                            MIN_SCAN_INTERVAL_SECONDS,
                            min(current_interval, MAX_SCAN_INTERVAL_SECONDS),
                        ),
                    ): vol.All(
                        vol.Coerce(int),
                        vol.Range(
                            min=MIN_SCAN_INTERVAL_SECONDS,
                            max=MAX_SCAN_INTERVAL_SECONDS,
                        ),
                    ),
                }
            ),
        )
