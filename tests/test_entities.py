"""Exercise real entity logic with small HA import-boundary stubs.

These tests do not replace a Home Assistant frontend/integration test.
"""

import asyncio
import importlib.util
import sys
import types
from enum import IntFlag, StrEnum
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def entities(monkeypatch):
    package_name = "tcl_overseas_entity_tests"
    path = Path(__file__).parents[1] / "custom_components/tcl_smart_home"

    def stub(name, **attributes):
        module = types.ModuleType(name)
        module.__dict__.update(attributes)
        monkeypatch.setitem(sys.modules, name, module)
        return module

    class CoordinatorEntity:
        def __class_getitem__(cls, item):
            return cls

        def __init__(self, coordinator):
            self.coordinator = coordinator

    class Feature(IntFlag):
        TARGET_TEMPERATURE = 1
        FAN_MODE = 8

    class Mode(StrEnum):
        OFF = "off"
        AUTO = "auto"
        COOL = "cool"
        HEAT = "heat"
        DRY = "dry"
        FAN_ONLY = "fan_only"

    stub("homeassistant", __path__=[])
    stub("homeassistant.helpers", __path__=[])
    stub("homeassistant.components", __path__=[])
    stub("homeassistant.helpers.device_registry", DeviceInfo=dict)
    stub(
        "homeassistant.helpers.entity",
        EntityCategory=SimpleNamespace(CONFIG="config", DIAGNOSTIC="diagnostic"),
    )
    stub(
        "homeassistant.helpers.update_coordinator", CoordinatorEntity=CoordinatorEntity
    )
    stub("homeassistant.components.select", SelectEntity=type("SelectEntity", (), {}))
    stub("homeassistant.components.button", ButtonEntity=type("ButtonEntity", (), {}))
    stub(
        "homeassistant.components.binary_sensor",
        BinarySensorEntity=type("BinarySensorEntity", (), {}),
        BinarySensorDeviceClass=SimpleNamespace(
            DOOR="door", CONNECTIVITY="connectivity"
        ),
    )
    stub(
        "homeassistant.components.climate",
        ClimateEntity=type("ClimateEntity", (), {}),
        ClimateEntityFeature=Feature,
        HVACMode=Mode,
    )
    stub(
        "homeassistant.const",
        ATTR_TEMPERATURE="temperature",
        UnitOfTemperature=SimpleNamespace(CELSIUS="°C"),
    )
    stub(package_name, __path__=[str(path)])
    stub(f"{package_name}.coordinator", TCLCoordinator=object, TCLDeviceData=object)

    def load(name):
        spec = importlib.util.spec_from_file_location(
            f"{package_name}.{name}", path / f"{name}.py"
        )
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, spec.name, module)
        spec.loader.exec_module(module)
        return module

    for name in list(sys.modules):
        if name.startswith(package_name + ".") and not name.endswith(".coordinator"):
            monkeypatch.delitem(sys.modules, name)
    for name in ("const", "model", "capabilities", "entity"):
        load(name)
    load("binary_sensor")
    load("button")
    return load("select"), load("climate")


def test_missing_door_status_still_discovers_entity_and_updates(entities):
    platform = sys.modules["tcl_overseas_entity_tests.binary_sensor"]
    prop = {"identifier": "doorStatus", "accessMode": "r", "dataType": {"type": "bool"}}
    coordinator, device, writes = setup_device([prop], {})
    coordinator.devices = {device.device_id: device}
    found = []
    asyncio.run(
        platform.async_setup_entry(
            None, SimpleNamespace(runtime_data=coordinator), found.extend
        )
    )
    assert len(found) == 2
    entity = found[1]
    assert entity.is_on is None
    assert entity.device_class == "door"
    for value, expected in [
        (0, False),
        (1, True),
        ("0", False),
        ("1", True),
        (None, None),
        ("invalid", None),
    ]:
        device.status["doorStatus"] = value
        assert entity.is_on is expected
    assert not writes


def test_unknown_device_and_empty_model_keep_connectivity(entities):
    platform = sys.modules["tcl_overseas_entity_tests.binary_sensor"]
    coordinator, device, writes = setup_device([], {})
    device.device["productKey"] = "unreviewed"
    device.model = {}
    device.status_ok = False
    coordinator.devices = {device.device_id: device}
    coordinator.last_update_success = True
    found = []
    asyncio.run(
        platform.async_setup_entry(
            None, SimpleNamespace(runtime_data=coordinator), found.extend
        )
    )
    assert len(found) == 1
    entity = found[0]
    assert entity.available
    assert entity.is_on is None
    for value, expected in [
        (False, False),
        (0, False),
        ("offline", False),
        (True, True),
        ("online", True),
        (None, None),
        ("invalid", None),
    ]:
        device.device["isOnline"] = value
        assert entity.is_on is expected
        assert entity.available
    coordinator.last_update_success = False
    assert not entity.available
    coordinator.last_update_success = True
    coordinator.get_device = lambda _: None
    assert not entity.available
    assert not writes


def test_alarm_setting_never_creates_lock_control(entities):
    policy = sys.modules["tcl_overseas_entity_tests.capabilities"]
    const = sys.modules["tcl_overseas_entity_tests.const"]
    prop = {
        "identifier": "autoLockAlarm",
        "accessMode": "rw",
        "dataType": {"type": "enum", "specs": {"0": "10", "3": "off"}},
    }
    assert "lock" not in const.PLATFORMS
    assert "text" not in const.PLATFORMS
    assert policy.platform_for({"productKey": "unknown"}, {}, prop) is None


def test_washer_buttons_send_only_reviewed_start_pause_values(entities):
    policy = sys.modules["tcl_overseas_entity_tests.capabilities"]
    platform = sys.modules["tcl_overseas_entity_tests.button"]
    product, profile = next(
        (k, p)
        for k, p in policy.PROFILES.items()
        if "dryShellRunStatus" in p["properties"]
    )
    props = [{"identifier": k, **r["schema"]} for k, r in profile["properties"].items()]
    coordinator, device, writes = setup_device([], {})
    device.device["productKey"] = product
    device.model = {"properties": props}
    coordinator.devices = {device.device_id: device}
    coordinator.entry.data["country_code"] = "CN"
    buttons = []
    asyncio.run(
        platform.async_setup_entry(
            None, SimpleNamespace(runtime_data=coordinator), buttons.extend
        )
    )
    assert len(buttons) == 4
    assert not writes
    for button in buttons:
        assert button._attr_name in {"启动洗涤", "暂停洗涤", "启动烘干", "暂停烘干"}
        asyncio.run(button.async_press())
    assert {(p, v) for _, p, v in writes} == {
        ("lowerShellRunStatus", "1"),
        ("lowerShellRunStatus", "2"),
        ("dryShellRunStatus", "1"),
        ("dryShellRunStatus", "2"),
    }


def setup_device(properties, status):
    policy = sys.modules["tcl_overseas_entity_tests.capabilities"]
    roles = {"workMode": "mode", "fanSpeed": "fan"}
    policy.PROFILES["synthetic-product"] = {
        "properties": {
            p["identifier"]: {
                "tier": "primary",
                "writable": "w" in p.get("accessMode", ""),
                "composite": roles.get(p["identifier"]),
                "schema": policy.schema_signature(p),
            }
            for p in properties
        }
    }
    device = SimpleNamespace(
        device_id="test-device",
        device={
            "deviceId": "test-device",
            "nickName": "客厅空调",
            "productKey": "synthetic-product",
        },
        model={"properties": properties},
        status=status,
    )
    writes = []

    async def write(device_id, identifier, value):
        writes.append((device_id, identifier, value))

    coordinator = SimpleNamespace(
        get_device=lambda _: device,
        async_set_property=write,
        entry=SimpleNamespace(data={"country_code": "DE"}),
    )
    return coordinator, device, writes


def test_select_shows_stable_keys_and_writes_original_integer_code(entities):
    select, _ = entities
    prop = {
        "identifier": "workMode",
        "name": "工作模式",
        "accessMode": "rw",
        "dataType": {
            "type": "enum",
            "specs": [{"value": 7, "name": "制冷"}, {"value": 9, "name": "制热"}],
        },
    }
    coordinator, device, writes = setup_device([prop], {"workMode": 9})
    entity = select.TCLPropertySelect(coordinator, device, prop)
    assert entity._attr_translation_key is None
    assert entity._attr_name == "Operating mode"
    assert entity._attr_unique_id == "test-device_workMode"
    assert entity.options == ["Cool", "Heat"]
    assert entity.current_option == "Heat"
    assert entity.device_info["name"] == "客厅空调"
    asyncio.run(entity.async_select_option("Cool"))
    assert writes == [("test-device", "workMode", 7)]
    with pytest.raises(ValueError):
        asyncio.run(entity.async_select_option("unsupported"))
    assert len(writes) == 1


def test_unknown_select_uses_readable_name_and_preserves_string_code(entities):
    select, _ = entities
    prop = {
        "identifier": "customProgram",
        "name": "自定义程序",
        "dataType": {"type": "enum", "specs": {"007": "特殊洗涤"}},
    }
    coordinator, device, writes = setup_device([prop], {"customProgram": "007"})
    entity = select.TCLPropertySelect(coordinator, device, prop)
    assert entity._attr_name == "Custom Program"
    assert entity._attr_translation_key is None
    assert entity.options == ["Value 007"]
    asyncio.run(entity.async_select_option("Value 007"))
    assert writes == [("test-device", "customProgram", "007")]


def test_lock_volume_translations_preserve_control_codes(entities):
    select, _ = entities
    prop = {
        "identifier": "voiceVolume",
        "name": "门锁语音音量",
        "accessMode": "rw",
        "dataType": {
            "type": "enum",
            "specs": {"0": "低音量", "1": "中音量", "2": "高音量", "3": "静音音量"},
        },
    }
    coordinator, device, writes = setup_device([prop], {"voiceVolume": 2})
    entity = select.TCLPropertySelect(coordinator, device, prop)
    assert entity._attr_translation_key is None
    assert entity._attr_name == "Voice volume"
    assert entity.current_option == "High volume"
    asyncio.run(entity.async_select_option("Muted"))
    assert writes == [("test-device", "voiceVolume", "3")]


@pytest.mark.parametrize("country", ["CN", "DE", "US"])
def test_api_route_fixes_names_and_options_independent_of_ha_locale(entities, country):
    select, _ = entities
    prop = {
        "identifier": "voiceVolume",
        "name": "门锁语音音量",
        "dataType": {"type": "enum", "specs": {"0": "低音量", "1": "高音量"}},
    }
    coordinator, device, writes = setup_device([prop], {"voiceVolume": "1"})
    coordinator.entry.data["country_code"] = country
    coordinator.hass = SimpleNamespace(
        config=SimpleNamespace(language="en" if country == "CN" else "zh-Hans")
    )
    entity = select.TCLPropertySelect(coordinator, device, prop)
    assert entity._attr_translation_key is None
    if country == "CN":
        assert entity._attr_name == "门锁语音音量"
        assert entity.options == ["低音量", "高音量"]
    else:
        assert entity._attr_name == "Voice volume"
        assert entity.options == ["Low volume", "High volume"]
    asyncio.run(entity.async_select_option(entity.options[0]))
    assert writes == [("test-device", "voiceVolume", "0")]


def test_climate_fan_label_translation_preserves_wire_values(entities):
    _, climate = entities
    props = [
        {
            "identifier": "fanSpeed",
            "accessMode": "rw",
            "dataType": {"type": "enum", "specs": {"5": "低风", "8": "高风"}},
        },
        {
            "identifier": "workMode",
            "accessMode": "rw",
            "dataType": {"type": "enum", "specs": {"3": "制冷", "6": "制热"}},
        },
    ]
    coordinator, device, writes = setup_device(
        props, {"fanSpeed": "5", "workMode": "3"}
    )
    entity = climate.TCLClimate(coordinator, device)
    assert entity.fan_modes == ["Low", "High"]
    assert entity.fan_mode == "Low"
    assert entity.hvac_mode == climate.HVACMode.COOL
    asyncio.run(entity.async_set_fan_mode("High"))
    asyncio.run(entity.async_set_hvac_mode(climate.HVACMode.HEAT))
    assert writes == [
        ("test-device", "fanSpeed", "8"),
        ("test-device", "workMode", "6"),
    ]
