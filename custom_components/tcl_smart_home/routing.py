from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CountryRoute:
    """Country metadata and regional TCL service routing."""

    code: str
    name: str
    area: str
    timezone: str
    sso_region: str
    cloud_region: str

    @property
    def auth_url(self) -> str:
        return {
            "CN": "https://cn.account.tcl.com",
            "SG": "https://sg.account.tcl.com",
            "FR": "https://pa.account.tcl.com",
            "US": "https://us.account.tcl.com",
            "BR": "https://br.account.tcl.com",
        }[self.sso_region]

    @property
    def iot_url(self) -> str:
        return {
            "CN": "https://io.zx.tcljd.com",
            "SG": "https://sgp-iot-api-prod.tcljd.com",
            "FR": "https://eu-iot-api-prod.tcljd.com",
            "US": "https://us-iot-api-prod.tcljd.com",
            "BR": "https://br-iot-api-prod.tcljd.com",
        }[self.sso_region]

    @property
    def label(self) -> str:
        normalized = self.name.replace("（", "(").replace("）", ")")
        # Some rows have a Chinese qualifier before the English name, and
        # English names themselves may contain parentheses (e.g. Congo).
        match = re.search(r"\([A-Za-z]", normalized)
        display_name = self.code
        if match:
            start = match.start() + 1
            depth = 1
            for index in range(start, len(normalized)):
                if normalized[index] == "(":
                    depth += 1
                elif normalized[index] == ")":
                    depth -= 1
                if depth == 0:
                    display_name = normalized[start:index].strip()
                    break
        return f"{display_name} [{self.code}]"


def _load_routes() -> dict[str, CountryRoute]:
    path = Path(__file__).with_name("country_regions.csv")
    with path.open(encoding="utf-8-sig", newline="") as source:
        rows = csv.DictReader(source)
        routes: dict[str, CountryRoute] = {}
        for row in rows:
            code = str(row["country_code"]).strip().upper()
            route = CountryRoute(
                code=code,
                name=str(row["country_name"]).strip(),
                area=str(row["country_area"]).strip(),
                timezone=str(row["time_zone"]).strip(),
                sso_region=str(row["sso_region"]).strip().upper(),
                cloud_region=str(row["cloud_region"]).strip(),
            )
            routes[code] = route
        return routes


COUNTRY_ROUTES = _load_routes()


def get_country_route(country_code: str) -> CountryRoute:
    code = country_code.strip().upper()
    try:
        return COUNTRY_ROUTES[code]
    except KeyError as err:
        raise ValueError(f"Unsupported TCL account country code: {code}") from err


def country_options() -> list[dict[str, str]]:
    options = [
        {"label": route.label, "value": route.code}
        for route in sorted(
            COUNTRY_ROUTES.values(), key=lambda item: item.label.casefold()
        )
    ]
    # Mainland China is the domestic route, but it is selected through the
    # same account-country screen so users never choose a server manually.
    return [{"label": "Mainland China [CN]", "value": "CN"}] + [
        option for option in options if option["value"] != "CN"
    ]
