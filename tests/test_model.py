import importlib.util
import json
from pathlib import Path

import pytest

_MODEL_PATH = (
    Path(__file__).parents[1] / "custom_components" / "tcl_smart_home" / "model.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "tcl_smart_home_model",
    _MODEL_PATH,
)
assert _SPEC and _SPEC.loader
model = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(model)


def test_appliance_category_codes_and_units():
    assert model.is_refrigerator({"category": "RF"})
    assert not model.is_refrigerator({"category": "RFID"})
    assert model.is_washing_machine({"category": "DW"})
    assert model.is_washing_machine({"category": "IWD"})
    assert not model.is_washing_machine({"category": "DWR"})
    for raw, expected in [("℃", "°C"), ("NA", None), ("min", "min")]:
        assert model.spec_unit({"dataType": {"specs": {"unit": raw}}}) == expected


def test_enum_options_supports_tsl_mapping() -> None:
    prop = {
        "dataType": {
            "type": "enum",
            "specs": {"0": "自动", "1": "制冷"},
        }
    }

    assert model.enum_options(prop) == [("0", "自动"), ("1", "制冷")]


def test_air_conditioner_detection_and_mode_mapping() -> None:
    assert model.mode_label_to_hvac("制冷") == "cool"
    assert model.mode_label_to_hvac("制热") == "heat"


def test_model_fingerprint_changes_when_property_capability_changes() -> None:
    first = {
        "productKey": "pk",
        "tslVersion": "1",
        "properties": [
            {
                "identifier": "power",
                "accessMode": "rw",
                "dataType": {"type": "bool"},
            }
        ],
    }
    second = {
        **first,
        "properties": [
            {
                "identifier": "power",
                "accessMode": "r",
                "dataType": {"type": "bool"},
            }
        ],
    }

    assert model.model_fingerprint(first) != model.model_fingerprint(second)


def test_property_icons_cover_common_controls() -> None:
    assert model.property_icon({"identifier": "targetTemperature"}) == "mdi:thermometer"
    assert model.property_icon({"identifier": "powerSwitch"}) == "mdi:power"
    assert model.property_icon({"identifier": "unknownProperty"}) is None


def test_localized_property_names_keep_distinct_capabilities() -> None:
    assert (
        model.property_translation_key({"identifier": "targetTemperature"})
        == "target_temperature"
    )
    assert (
        model.property_translation_key({"identifier": "currentTemperature"})
        == "current_temperature"
    )
    # A substring match must not rename an unrelated capability to Temperature.
    prop = {"identifier": "temperatureAlarmDelay", "name": "温度报警延时"}
    assert model.property_translation_key(prop) is None
    assert model.property_name(prop) == "Temperature Alarm Delay"
    assert (
        model.property_name({"identifier": "PTCStatus", "name": "电加热状态"})
        == "PTC Status"
    )
    assert (
        model.property_name({"identifier": "custom", "name": "Custom setting"})
        == "Custom setting"
    )


@pytest.mark.parametrize(
    "specs,expected",
    [
        (
            {"0": "自动", "1": "低风", "2": "高风"},
            [("0", "Auto"), ("1", "Low"), ("2", "High")],
        ),
        (
            {"values": [{"value": 7, "name": "制冷"}, {"value": 9, "name": "制热"}]},
            [(7, "Cool"), (9, "Heat")],
        ),
        (
            {"options": {"a": "Quick wash", "b": "未定义模式"}},
            [("a", "Quick wash"), ("b", "Value b")],
        ),
    ],
)
def test_enum_display_keeps_original_control_codes_and_types(specs, expected) -> None:
    prop = {"dataType": {"type": "enum", "specs": specs}}
    assert model.enum_display_options(prop) == expected
    assert [raw for raw, _ in model.enum_display_options(prop)] == [
        raw for raw, _ in model.enum_options(prop)
    ]


def test_enum_labels_remain_unambiguous_after_translation() -> None:
    prop = {
        "dataType": {
            "type": "enum",
            "specs": {"a": "低速", "b": "低风", "c": "low (2)"},
        }
    }
    options = model.enum_display_options(prop)
    assert len({label for _, label in options}) == 3
    assert {label: raw for raw, label in options}["Low (2)"] == "b"


def test_english_and_chinese_resources_cover_dynamic_translation_keys() -> None:
    component = _MODEL_PATH.parent
    en = json.loads((component / "translations/en.json").read_text(encoding="utf-8"))
    zh = json.loads(
        (component / "translations/zh-Hans.json").read_text(encoding="utf-8")
    )
    assert en == json.loads((component / "strings.json").read_text(encoding="utf-8"))

    def leaf_paths(value, prefix=()):
        if isinstance(value, dict):
            return {
                p
                for key, item in value.items()
                for p in leaf_paths(item, (*prefix, key))
            }
        return {prefix}

    assert leaf_paths(en) == leaf_paths(zh)
    # Capabilities now use route-specific labels, not duplicated HA resources.
    for language in ("en", "zh-Hans"):
        assert (
            set(model.PROPERTY_TRANSLATION_KEYS.values())
            <= model.ROUTE_PROPERTY_NAMES[language].keys()
        )
        assert (
            set(model.ENUM_LABEL_KEYS.values())
            <= model.ROUTE_OPTION_NAMES[language].keys()
        )
    assert model.ROUTE_OPTION_NAMES["en"]["cool"] == "Cool"
    assert model.ROUTE_OPTION_NAMES["zh-Hans"]["cool"] == "制冷"
