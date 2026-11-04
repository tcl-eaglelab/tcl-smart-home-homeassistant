from __future__ import annotations

from homeassistant.components.number import NumberEntity

from .capabilities import platform_for
from .entity import TCLPropertyEntity
from .model import (
    model_properties,
    numeric_spec,
    spec_unit,
)

PARALLEL_UPDATES = 1


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        TCLPropertyNumber(coordinator, device, prop)
        for device in coordinator.devices.values()
        for prop in model_properties(device.model)
        if platform_for(device.device, device.model, prop) == "number"
    )


class TCLPropertyNumber(TCLPropertyEntity, NumberEntity):
    """Expose a writable numeric TSL property as a number."""

    def __init__(self, coordinator, device_data, prop) -> None:
        super().__init__(coordinator, device_data, prop)
        self._attr_native_min_value = numeric_spec(prop, "min", 0)
        self._attr_native_max_value = numeric_spec(prop, "max", 100)
        self._attr_native_step = numeric_spec(prop, "step", 1)
        self._attr_native_unit_of_measurement = spec_unit(prop)

    @property
    def native_value(self) -> float | None:
        try:
            return float(self.value) if self.value is not None else None
        except (TypeError, ValueError):
            return None

    async def async_set_native_value(self, value: float) -> None:
        await self.async_write_value(value)
