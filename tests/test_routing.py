import importlib.util
import sys
from pathlib import Path

_ROUTING_PATH = (
    Path(__file__).parents[1] / "custom_components" / "tcl_smart_home" / "routing.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "tcl_smart_home_routing",
    _ROUTING_PATH,
)
assert _SPEC and _SPEC.loader
routing = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = routing
_SPEC.loader.exec_module(routing)


def test_country_routes_resolve_overseas_regions() -> None:
    assert routing.get_country_route("IN").auth_url == "https://sg.account.tcl.com"
    assert (
        routing.get_country_route("DE").iot_url == "https://eu-iot-api-prod.tcljd.com"
    )
    assert (
        routing.get_country_route("US").iot_url == "https://us-iot-api-prod.tcljd.com"
    )
    assert routing.get_country_route("BR").auth_url == "https://br.account.tcl.com"


def test_country_routes_include_domestic_china() -> None:
    assert routing.get_country_route("CN").auth_url == "https://cn.account.tcl.com"
    assert routing.get_country_route("CN").iot_url == "https://io.zx.tcljd.com"
    assert len(routing.COUNTRY_ROUTES) == 249


def test_country_options_are_label_value_pairs() -> None:
    options = routing.country_options()

    assert {"label": "India [IN]", "value": "IN"} in options
    assert {"label": "Holy See [VA]", "value": "VA"} in options
    assert {"label": "Virgin Islands (U.S.) [VI]", "value": "VI"} in options
    assert {"label": "Congo(Democratic Republic of the) [CD]", "value": "CD"} in options
    assert {"label": "Monaco [MC]", "value": "MC"} in options
    assert {"label": "Kosovo [XK]", "value": "XK"} in options


def test_country_options_use_english_labels_and_alphabetic_order() -> None:
    options = routing.country_options()
    labels = [option["label"] for option in options]
    assert labels[0] == "Mainland China [CN]"
    assert labels[1:] == sorted(labels[1:], key=str.casefold)
    assert all(
        not any("\u4e00" <= char <= "\u9fff" for char in label) for label in labels
    )
