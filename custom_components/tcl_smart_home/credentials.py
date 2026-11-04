"""Read operator-provided application credentials from HA YAML configuration."""

from .const import DOMAIN


def application_secret(hass, country: str) -> str:
    config = hass.data.get(DOMAIN, {})
    key = "domestic_app_secret" if country == "CN" else "overseas_client_secret"
    return config.get(key, "")
