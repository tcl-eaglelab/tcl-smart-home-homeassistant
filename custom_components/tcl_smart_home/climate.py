from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.exceptions import HomeAssistantError

from .capabilities import climate_property, has_climate
from .coordinator import TCLCoordinator
from .entity import TCLDeviceEntity
from .model import (
    as_bool,
    enum_display_options,
    enum_options,
    find_property,
    mode_label_to_hvac,
    model_properties,
    numeric_spec,
    property_identifier,
)

PARALLEL_UPDATES = 1


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    coordinator: TCLCoordinator = entry.runtime_data
    async_add_entities(
        TCLClimate(coordinator, device_data)
        for device_data in coordinator.devices.values()
        if has_climate(device_data.device, device_data.model)
    )


class TCLClimate(TCLDeviceEntity, ClimateEntity):
    """Map common TCL air-conditioner TSL properties to climate."""

    _attr_translation_key = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = 16
    _attr_max_temp = 32
    _attr_target_temperature_step = 1

    def __init__(self, coordinator, device_data) -> None:
        super().__init__(coordinator, device_data)
        self._attr_name = (
            "空调" if self.display_language == "zh-Hans" else "Air conditioner"
        )
        self._attr_unique_id = f"{device_data.device_id}_climate"
        self._properties = model_properties(device_data.model)
        self._power = climate_property(device_data.device, device_data.model, "power")
        self._mode = climate_property(device_data.device, device_data.model, "mode")
        self._target = climate_property(device_data.device, device_data.model, "target")
        self._fan = climate_property(device_data.device, device_data.model, "fan")
        self._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
        if self._fan:
            self._attr_supported_features |= ClimateEntityFeature.FAN_MODE
        if self._target:
            self._attr_min_temp = numeric_spec(self._target, "min", 16)
            self._attr_max_temp = numeric_spec(self._target, "max", 32)
            self._attr_target_temperature_step = numeric_spec(self._target, "step", 1)
        self._attr_icon = "mdi:air-conditioner"

    @property
    def hvac_modes(self) -> list[HVACMode]:
        modes = [HVACMode.OFF]
        if self._mode:
            for _, label in enum_options(self._mode):
                mapped = mode_label_to_hvac(label)
                if mapped and HVACMode(mapped) not in modes:
                    modes.append(HVACMode(mapped))
        return modes

    @property
    def hvac_mode(self) -> HVACMode | None:
        if (
            self._power
            and as_bool(self.status.get(property_identifier(self._power))) is False
        ):
            return HVACMode.OFF
        if self._mode:
            raw = self.status.get(property_identifier(self._mode))
            for option_value, label in enum_options(self._mode):
                if str(option_value) == str(raw):
                    mapped = mode_label_to_hvac(label)
                    if mapped:
                        return HVACMode(mapped)
        return None

    @property
    def current_temperature(self) -> float | None:
        prop = find_property(
            self._properties,
            "currentTemperature",
            "indoorTemperature",
        )
        return self._number(prop)

    @property
    def target_temperature(self) -> float | None:
        return self._number(self._target)

    @property
    def fan_modes(self) -> list[str]:
        if not self._fan:
            return []
        return [
            label for _, label in enum_display_options(self._fan, self.display_language)
        ]

    @property
    def fan_mode(self) -> str | None:
        if not self._fan:
            return None
        raw = self.status.get(property_identifier(self._fan))
        for option_value, label in enum_display_options(
            self._fan, self.display_language
        ):
            if str(option_value) == str(raw):
                return label
        return str(raw) if raw is not None else None

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode not in self.hvac_modes:
            raise HomeAssistantError("Unsupported HVAC mode")
        if self._power:
            await self.async_set_property(
                property_identifier(self._power),
                hvac_mode != HVACMode.OFF,
            )
        if hvac_mode == HVACMode.OFF or not self._mode:
            return
        for raw, label in enum_options(self._mode):
            if mode_label_to_hvac(label) == hvac_mode:
                await self.async_set_property(property_identifier(self._mode), raw)
                return

    async def async_set_temperature(self, **kwargs: Any) -> None:
        if self._target and ATTR_TEMPERATURE in kwargs:
            value = kwargs[ATTR_TEMPERATURE]
            await self.async_set_property(property_identifier(self._target), value)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        if not self._fan:
            return
        for raw, label in enum_display_options(self._fan, self.display_language):
            if label == fan_mode:
                await self.async_set_property(property_identifier(self._fan), raw)
                return

    def _number(self, prop: dict[str, Any] | None) -> float | None:
        if not prop:
            return None
        value = self.status.get(property_identifier(prop))
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None
