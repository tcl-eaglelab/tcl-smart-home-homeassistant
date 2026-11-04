"""Register the integration's narrowly scoped QR dialog presentation."""

import asyncio
from pathlib import Path

from homeassistant.components import frontend
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_URL = "/tcl_smart_home/qr-dialog-1.0.0.js"
_TASK_KEY = f"{DOMAIN}_qr_frontend"


async def async_setup_qr_frontend(hass: HomeAssistant) -> None:
    """Register once, including when onboarding the first account."""
    if _TASK_KEY not in hass.data:
        hass.data[_TASK_KEY] = hass.async_create_task(_async_register(hass))
    try:
        await asyncio.shield(hass.data[_TASK_KEY])
    except Exception:
        hass.data.pop(_TASK_KEY, None)
        raise


async def _async_register(hass: HomeAssistant) -> None:
    await hass.http.async_register_static_paths(
        [StaticPathConfig(_URL, str(Path(__file__).parent / "frontend/qr-dialog.js"))]
    )
    frontend.add_extra_js_url(hass, _URL)
