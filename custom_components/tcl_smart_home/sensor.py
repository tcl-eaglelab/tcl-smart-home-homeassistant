from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import PERCENTAGE, UnitOfTemperature

from .capabilities import platform_for
from .entity import TCLPropertyEntity
from .model import (
    display_state,
    enum_display_options,
    is_enum_type,
    model_properties,
    spec_unit,
)

TEMPERATURE_UNITS = ("\u00b0C", "C", "celsius", "\u6444\u6c0f\u5ea6")


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        TCLPropertySensor(coordinator, device, prop)
        for device in coordinator.devices.values()
        for prop in model_properties(device.model)
        if platform_for(device.device, device.model, prop) == "sensor"
    )


class TCLPropertySensor(TCLPropertyEntity, SensorEntity):
    """Expose a read-only TSL property as a sensor."""

    @property
    def native_value(self):
        if is_enum_type(self.tsl_property):
            if self.value is None:
                return None
            for raw, label in enum_display_options(
                self.tsl_property, self.display_language
            ):
                if str(raw) == str(self.value):
                    return label
            return None
        return display_state(self.value)

    @property
    def device_class(self):
        identifier = self.property_id.lower()
        unit = spec_unit(self.tsl_property)
        if unit in TEMPERATURE_UNITS or "temperature" in identifier:
            return SensorDeviceClass.TEMPERATURE
        if "battery" in identifier:
            return SensorDeviceClass.BATTERY
        if "humidity" in identifier:
            return SensorDeviceClass.HUMIDITY
        return None

    @property
    def native_unit_of_measurement(self):
        unit = spec_unit(self.tsl_property)
        if unit in TEMPERATURE_UNITS or "temperature" in self.property_id.lower():
            return UnitOfTemperature.CELSIUS
        if unit in (PERCENTAGE, "%") or "humidity" in self.property_id.lower():
            return PERCENTAGE
        if self.device_class == SensorDeviceClass.BATTERY:
            return PERCENTAGE
        return unit
