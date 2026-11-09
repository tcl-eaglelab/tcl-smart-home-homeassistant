"""Resolve the TCL application credential for a country.

Mainland China uses the public client credential shipped with this integration,
unless configuration.yaml sets domestic_app_secret. Other countries use
overseas_client_secret from local YAML.
"""

from .const import DOMESTIC_APP_SECRET, DOMAIN


def application_secret(hass, country: str) -> str:
    config = hass.data.get(DOMAIN, {})
    if country == "CN":
        return config.get("domestic_app_secret") or DOMESTIC_APP_SECRET
    return config.get("overseas_client_secret", "")
