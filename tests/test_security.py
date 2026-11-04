"""Offline security regressions; no credentials or live device commands."""

import asyncio
import copy
import importlib
import json
import sys
import types
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import aiohttp
import pytest

PACKAGE = "tcl_security_tests"
COMPONENT = Path(__file__).parents[1] / "custom_components/tcl_smart_home"
package = types.ModuleType(PACKAGE)
package.__path__ = [str(COMPONENT)]
sys.modules[PACKAGE] = package
policy = importlib.import_module(PACKAGE + ".capabilities")
transport = importlib.import_module(PACKAGE + ".api_common")
api_module = importlib.import_module(PACKAGE + ".api")
diagnostics = importlib.import_module(PACKAGE + ".diagnostics")


def approved(identifier="targetTemperature"):
    for product, profile in policy.PROFILES.items():
        if identifier in profile["properties"]:
            rule = profile["properties"][identifier]
            prop = {"identifier": identifier, **copy.deepcopy(rule["schema"])}
            return {"productKey": product}, {"properties": [prop]}, prop
    raise AssertionError("Fixture capability missing")


@pytest.mark.parametrize(
    "value", [-100, 999, 16.1, True, "22", float("nan"), float("inf"), [], {}]
)
def test_invalid_temperature_is_rejected(value):
    device, model, prop = approved()
    with pytest.raises(ValueError):
        policy.validate_write(device, model, prop, value)


def test_valid_temperature_keeps_half_degree_step():
    device, model, prop = approved()
    assert policy.validate_write(device, model, prop, 22.5) == 22.5


@pytest.mark.parametrize("mutation", ["type", "range", "access", "product", "enum"])
def test_changed_cloud_schema_never_grants_write(mutation):
    device, model, prop = approved(
        "workMode" if mutation == "enum" else "targetTemperature"
    )
    if mutation == "type":
        prop["dataType"]["type"] = "text"
    elif mutation == "range":
        prop["dataType"]["specs"]["max"] = "1000"
    elif mutation == "access":
        prop["accessMode"] = "w"
    elif mutation == "product":
        device["productKey"] = "unreviewed-product"
    else:
        prop["dataType"]["specs"]["999"] = "Engineering mode"
    with pytest.raises(ValueError):
        policy.validate_write(device, model, prop, 22)


@pytest.mark.parametrize(
    "identifier",
    [
        "alwaysOpenEnable",
        "electronicLock",
        "mainLockStatus",
        "OutDoorCompTarFreqSet",
        "OutDoorEEVTarOpenDegree",
        "newUnknownSwitch",
    ],
)
def test_sensitive_and_unreviewed_controls_are_never_exposed(identifier):
    for product in policy.PROFILES:
        prop = {
            "identifier": identifier,
            "accessMode": "rw",
            "dataType": {"type": "bool"},
        }
        device, model = {"productKey": product}, {"properties": [prop]}
        assert policy.platform_for(device, model, prop) is None
        with pytest.raises(ValueError):
            policy.validate_write(device, model, prop, True)


def test_lock_controls_are_explicit_settings_not_remote_unlock():
    locks = [p for p in policy.PROFILES.values() if p["kind"] == "lock"]
    assert locks
    for profile in locks:
        writable = {k for k, r in profile["properties"].items() if r["writable"]}
        assert writable == {
            "electronicLock",
            "voiceVolume",
            "volume",
            "stayAlarmSwitch",
            "stayAlarmLevel",
        }
        assert not writable & {
            "mainLockStatus",
            "reverseLockStatus",
            "openDoor",
            "alwaysOpenEnable",
        }


def test_reviewed_appliances_keep_readings_read_only_and_validate_basic_controls():
    appliances = [
        (k, p)
        for k, p in policy.PROFILES.items()
        if p["kind"] in {"refrigerator", "washing_machine"}
    ]
    assert len(appliances) == 61
    for product, profile in appliances:
        for identifier, rule in profile["properties"].items():
            prop = {"identifier": identifier, **copy.deepcopy(rule["schema"])}
            device, model = {"productKey": product}, {"properties": [prop]}
            assert policy.platform_for(device, model, prop) in {
                "sensor",
                "binary_sensor",
                "number",
                "select",
                "switch",
            }
            if not rule["writable"]:
                with pytest.raises(ValueError):
                    policy.validate_write(device, model, prop, 1)
            else:
                kind = prop["dataType"]["type"]
                specs = prop["dataType"]["specs"]
                value = (
                    (rule.get("allowed_values") or list(specs))[0]
                    if kind == "enum"
                    else int(specs["min"]) if kind == "int" else True
                )
                policy.validate_write(device, model, prop, value)
                with pytest.raises(ValueError):
                    policy.validate_write(device, model, prop, 99999)
            assert (
                policy.reviewed_property_name(device, model, prop, "zh-Hans")
                == rule["names"]["zh-Hans"]
            )
            assert policy.reviewed_property_name(device, model, prop, "en").isascii()
            prop["dataType"]["type"] = "struct"
            assert policy.platform_for(device, model, prop) is None


@pytest.mark.parametrize("identifier", ["lowerShellRunStatus", "dryShellRunStatus"])
def test_washer_only_start_and_pause_are_commands(identifier):
    device, model, prop = approved(identifier)
    rule = policy.capability(device, model, prop)
    assert policy.platform_for(device, model, prop) == "sensor"
    assert {a["id"]: a["value"] for a in rule.actions} == {"start": "2", "pause": "1"}
    assert policy.validate_write(device, model, prop, "2") == "2"
    assert policy.validate_write(device, model, prop, 1) == "1"
    for reported_state in ["0", "3", True, None]:
        with pytest.raises(ValueError):
            policy.validate_write(device, model, prop, reported_state)


def test_washer_programs_have_readable_english_options():
    model_helpers = importlib.import_module(PACKAGE + ".model")
    for profile in policy.PROFILES.values():
        if profile["kind"] != "washing_machine":
            continue
        for identifier, rule in profile["properties"].items():
            if rule["writable"] and rule["schema"]["dataType"]["type"] == "enum":
                prop = {"identifier": identifier, **rule["schema"]}
                labels = [
                    label for _, label in model_helpers.enum_display_options(prop, "en")
                ]
                assert all(
                    label.isascii() and not label.startswith("Value ")
                    for label in labels
                )


def test_appliance_setting_and_delay_labels_are_explicit():
    for identifier, expected in [
        ("coldStorageTempC", "冷藏设定温度"),
        ("lowerShellWashingTime", "洗涤剩余时间（含预约）"),
        ("dryShellLeftRunningTime", "烘干剩余时间（含预约）"),
    ]:
        device, model, prop = approved(identifier)
        assert policy.reviewed_property_name(device, model, prop, "zh-Hans") == expected


def test_primary_advanced_diagnostics_and_composite_deduplication():
    for identifier, tier, enabled, platform in [
        ("targetTemperature", "primary", True, None),
        ("screen", "advanced", False, "switch"),
        ("errorCode", "diagnostic", False, "sensor"),
        ("currentTemperature", "primary", True, "sensor"),
    ]:
        device, model, prop = approved(identifier)
        rule = policy.capability(device, model, prop)
        assert (rule.tier, rule.enabled) == (tier, enabled)
        assert policy.platform_for(device, model, prop) == platform


@pytest.mark.parametrize(
    "kind,identifier,unit",
    [
        ("Refrigerator", "fridgeTemperature", "°C"),
        ("Washing machine", "remainingTime", "min"),
    ],
)
def test_unreviewed_appliance_model_is_read_only(kind, identifier, unit):
    prop = {
        "identifier": identifier,
        "accessMode": "r",
        "dataType": {"type": "int", "specs": {"unit": unit}},
    }
    device, model = {"category": kind, "productKey": "new"}, {"properties": [prop]}
    assert policy.platform_for(device, model, prop) == "sensor"
    with pytest.raises(ValueError):
        policy.validate_write(device, model, prop, 1)
    prop["accessMode"] = "rw"
    assert policy.platform_for(device, model, prop) is None


class Response:
    def __init__(self, status=200, payload=None, headers=None, invalid=False):
        self.status = status
        self.payload = payload if payload is not None else {"code": 200}
        self.headers = headers or {}
        self.invalid = invalid

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def text(self):
        raise AssertionError("Raw error body must never be read for logging")

    async def json(self):
        if self.invalid:
            raise json.JSONDecodeError("SYNTHETIC_SECRET", "SYNTHETIC_SECRET", 0)
        return self.payload


class Session:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def request(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def request(client):
    return client._raw_request(
        "GET",
        "https://cn.account.tcl.com/synthetic",
        headers={"accessToken": "SYNTHETIC_SECRET"},
        authenticated=True,
    )


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_redirect_refused_even_when_tls_flag_is_false(status):
    session = Session(
        Response(status, headers={"Location": "https://attacker.invalid"})
    )
    client = transport.TCLCloudClient(session, verify_ssl=False)
    with pytest.raises(transport.TCLApiError, match="redirects"):
        asyncio.run(request(client))
    assert len(session.calls) == 1
    options = session.calls[0][1]
    assert options["allow_redirects"] is False and options["ssl"] is True


@pytest.mark.parametrize(
    "url",
    [
        "http://cn.account.tcl.com/a",
        "https://cn.account.tcl.com.attacker.invalid/a",
        "https://user:secret@cn.account.tcl.com/a",
        "https://127.0.0.1/a",
        "https://cn.account.tcl.com:444/a",
    ],
)
def test_bad_api_origin_rejected_without_a_request(url):
    session = Session(Response())
    client = transport.TCLCloudClient(session)
    with pytest.raises(transport.TCLApiError):
        asyncio.run(client._raw_request("GET", url, authenticated=True))
    assert session.calls == []


@pytest.mark.parametrize(
    "response",
    [
        Response(400),
        Response(500),
        Response(invalid=True),
        aiohttp.ClientConnectionError("SYNTHETIC_SECRET"),
    ],
)
def test_response_and_connection_error_secrets_do_not_escape(response):
    client = transport.TCLCloudClient(Session(response))
    with pytest.raises(transport.TCLApiError) as caught:
        asyncio.run(request(client))
    assert "SYNTHETIC_SECRET" not in str(caught.value)
    assert caught.value.__cause__ is None


def test_cloud_business_error_is_not_reflected():
    route = importlib.import_module(PACKAGE + ".routing").get_country_route("CN")
    client = api_module.create_api(
        Session(
            Response(payload={"code": "SYNTHETIC_SECRET", "msg": "SYNTHETIC_SECRET"})
        ),
        route,
        access_token="synthetic",
    )
    with pytest.raises(transport.TCLApiError) as caught:
        asyncio.run(client.async_get_devices())
    assert str(caught.value) == "TCL API request failed"
    assert caught.value.code is None


def test_rate_limit_and_network_failure_pause_next_request():
    async def run(response):
        session = Session(response)
        client = transport.TCLCloudClient(session)
        for _ in range(2):
            with pytest.raises(transport.TCLApiError):
                await request(client)
        assert len(session.calls) == 1

    asyncio.run(run(Response(429, headers={"Retry-After": "120"})))
    asyncio.run(run(Response(503)))
    asyncio.run(run(aiohttp.ClientConnectionError("failure")))


@pytest.mark.parametrize(
    "value", [None, "nonsense", "NaN", "Infinity", "-100", "999999", "120"]
)
def test_retry_after_is_bounded(value):
    assert 30 <= transport.retry_seconds(value) <= 3600


@pytest.mark.parametrize(
    "value",
    [
        "http://cn.account.tcl.com/a",
        "https://attacker.invalid/a",
        "javascript:alert(1)",
        "//attacker.invalid/a",
        "https://user:secret@cn.account.tcl.com/a",
        "/a)![x](https://attacker.invalid)",
        "https://cn.account.tcl.com:444/a",
    ],
)
def test_qr_origin_and_markdown_injection_rejected(value):
    with pytest.raises(transport.TCLApiError):
        transport.safe_qr_url(value, "https://cn.account.tcl.com")


def test_qr_relative_same_origin_allowed():
    assert (
        transport.safe_qr_url("/qr?code=synthetic", "https://cn.account.tcl.com")
        == "https://cn.account.tcl.com/qr?code=synthetic"
    )


def test_diagnostics_omit_unknown_and_nested_sensitive_data():
    secret = "SYNTHETIC_SECRET"
    device = SimpleNamespace(
        device={
            "deviceId": secret,
            "ssoToken": secret,
            "nested": [{"AccessToken": secret}],
        },
        model={"productKey": secret, "properties": []},
        status={secret: secret},
        status_ok=True,
        status_failures=0,
        status_error=secret,
    )
    coordinator = SimpleNamespace(
        devices={secret: device},
        last_update_success=True,
        update_interval=timedelta(seconds=30),
    )
    entry = SimpleNamespace(
        runtime_data=coordinator, title=secret, options={"app_secret": secret}
    )
    result = asyncio.run(diagnostics.async_get_config_entry_diagnostics(None, entry))
    assert secret not in json.dumps(result)
    assert result["devices"][0]["property_counts"]["blocked"] == 0


def test_source_has_no_embedded_application_secret_assignments():
    source = (COMPONENT / "const.py").read_text(encoding="utf-8")
    assert "DOMESTIC_APP_SECRET" not in source
    assert "OVERSEAS_CLIENT_SECRET" not in source


def test_enum_and_bool_reject_unknown_or_wrong_types():
    device, model, prop = approved("workMode")
    for value in (True, 1.0, "unrecognised", {"value": 1}):
        with pytest.raises(ValueError):
            policy.validate_write(device, model, prop, value)
    device, model, prop = approved("powerSwitch")
    for value in ("true", "1", 2, 1.0):
        with pytest.raises(ValueError):
            policy.validate_write(device, model, prop, value)
    assert policy.validate_write(device, model, prop, True) == 1
