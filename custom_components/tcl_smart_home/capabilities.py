"""Fail-closed capability policy shared by discovery and every write path.

Only reviewed product/schema pairs can write. Unrecognised properties never
become controls merely because the cloud marks them writable.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from collections.abc import Mapping
from typing import Any

from .model import (
    enum_command_code,
    enum_options,
    is_refrigerator,
    is_washing_machine,
    property_identifier,
    property_name,
    property_specs,
    property_type,
)


@dataclass(frozen=True)
class Capability:
    tier: str = "blocked"
    writable: bool = False
    composite: str | None = None
    allowed_values: tuple | None = None
    actions: tuple = ()

    @property
    def enabled(self) -> bool:
        return self.tier == "primary"


PROFILES = json.loads(
    Path(__file__).with_name("capability_profiles.json").read_text(encoding="utf-8")
)
BLOCKED = Capability()


def profile_kind(device: Mapping[str, Any]) -> str | None:
    """Reviewed product kind, such as lock or air_conditioner."""
    product = str(device.get("productKey") or "")
    kind = PROFILES.get(product, {}).get("kind")
    return str(kind) if kind else None


def reviewed_property_name(device: dict, model: dict, prop: dict, language: str) -> str:
    """Use reviewed labels to distinguish settings from actual measurements."""
    product = str(device.get("productKey") or model.get("productKey") or "")
    rule = (
        PROFILES.get(product, {}).get("properties", {}).get(property_identifier(prop))
    )
    if rule and rule["schema"] == schema_signature(prop):
        label = rule.get("names", {}).get(language)
        if label:
            return label
    return property_name(prop, language)


def schema_signature(prop: dict) -> dict:
    """Pin types, access and semantics; changed cloud models require review."""
    return {"accessMode": prop.get("accessMode"), "dataType": prop.get("dataType")}


def capability(device: dict, model: dict, prop: dict) -> Capability:
    product = str(device.get("productKey") or model.get("productKey") or "")
    profile = PROFILES.get(product, {})
    rule = profile.get("properties", {}).get(property_identifier(prop))
    if not profile and prop.get("accessMode") == "r":
        # New refrigerator/washer models have no approved controls. Only these
        # explicitly named scalar readings may appear pending a model review.
        identifier = property_identifier(prop)
        kind = property_type(prop)
        if is_refrigerator(device) and identifier in {
            "fridgeTemperature",
            "freezerTemperature",
            "refrigeratorTemperature",
        }:
            specs = property_specs(prop)
            if (
                kind in {"int", "integer", "float", "double"}
                and isinstance(specs, dict)
                and specs.get("unit") in {"°C", "C", "celsius"}
            ):
                return Capability("primary")
        if is_washing_machine(device):
            if identifier in {"remainingTime", "remainTime"} and kind in {
                "int",
                "integer",
            }:
                specs = property_specs(prop)
                if isinstance(specs, dict) and specs.get("unit") in {"min", "s"}:
                    return Capability("primary")
            if (
                identifier in {"runStatus", "workStatus", "currentProgram"}
                and kind == "enum"
                and enum_options(prop)
            ):
                return Capability("primary")
    if rule is None or rule["schema"] != schema_signature(prop):
        return BLOCKED
    return Capability(
        rule["tier"],
        rule.get("writable", False),
        rule.get("composite"),
        tuple(rule["allowed_values"]) if "allowed_values" in rule else None,
        tuple(rule.get("actions", [])),
    )


def platform_for(device: dict, model: dict, prop: dict) -> str | None:
    rule = capability(device, model, prop)
    if rule.tier == "blocked" or rule.composite:
        return None
    if rule.actions:
        # Run status stays a sensor; only reviewed actions become buttons.
        return "sensor"
    kind = property_type(prop)
    if not rule.writable:
        return "binary_sensor" if kind in ("bool", "boolean") else "sensor"
    if kind in ("bool", "boolean"):
        return "switch"
    if kind in ("int", "integer", "float", "double", "number"):
        return "number"
    if kind in ("enum", "enumeration"):
        return "select"
    return None


def climate_property(device: dict, model: dict, role: str) -> dict | None:
    for prop in model.get("properties", []):
        if capability(device, model, prop).composite == role:
            return prop
    return None


def has_climate(device: dict, model: dict) -> bool:
    return all(
        climate_property(device, model, role) for role in ("power", "mode", "target")
    )


def validate_write(device: dict, model: dict, prop: dict, value: Any) -> Any:
    """Reject unreviewed controls and validate before any command is sent."""
    rule = capability(device, model, prop)
    if not rule.writable or "w" not in str(prop.get("accessMode", "")):
        raise ValueError("This property is not approved for control")
    kind = property_type(prop)
    if kind in ("bool", "boolean"):
        if isinstance(value, bool):
            return int(value)
        if type(value) is int and value in (0, 1):
            return value
        raise ValueError("Expected a boolean or integer 0/1")
    if kind in ("enum", "enumeration"):
        if type(value) not in (str, int):
            raise ValueError("Expected an enum code")
        if rule.allowed_values is not None and str(value) not in {
            str(raw) for raw in rule.allowed_values
        }:
            raise ValueError("This enum value is a reported state, not a command")
        for raw, _ in enum_options(prop):
            if type(raw) in (str, int) and str(raw) == str(value):
                return enum_command_code(raw)
        raise ValueError("Unknown enum code")
    if kind in ("int", "integer", "float", "double", "number"):
        if type(value) not in (int, float) or (
            isinstance(value, float) and not math.isfinite(value)
        ):
            raise ValueError("Expected a finite number")
        specs = property_specs(prop)
        if not isinstance(specs, dict):
            raise ValueError("Missing numeric constraints")
        try:
            minimum, maximum, step = (
                Decimal(str(specs[k])) for k in ("min", "max", "step")
            )
            number = Decimal(str(value))
            if (
                not all(v.is_finite() for v in (minimum, maximum, step))
                or step <= 0
                or minimum > maximum
            ):
                raise ValueError("Invalid numeric constraints")
            if not minimum <= number <= maximum or (number - minimum) % step != 0:
                raise ValueError("Value outside allowed range or step")
            if kind in ("int", "integer"):
                if number != number.to_integral_value():
                    raise ValueError("Expected an integer")
                return int(number)
            return float(number)
        except (KeyError, InvalidOperation) as err:
            raise ValueError("Missing or invalid numeric constraints") from err
    raise ValueError("Unsupported control type")
