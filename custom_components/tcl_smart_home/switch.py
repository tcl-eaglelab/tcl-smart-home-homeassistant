from __future__ import annotations

from homeassistant.components.switch import SwitchEntity

from .capabilities import platform_for
from .entity import TCLPropertyEntity
from .model import (
    as_bool,
    model_properties,
)

PARALLEL_UPDATES = 1


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        TCLPropertySwitch(coordinator, device, prop)
        for device in coordinator.devices.values()
        for prop in model_properties(device.model)
        if platform_for(device.device, device.model, prop) == "switch"
    )


class TCLPropertySwitch(TCLPropertyEntity, SwitchEntity):
    """Expose a writable boolean TSL property as a switch."""

    def __init__(self, coordinator, device_data, prop) -> None:
        super().__init__(coordinator, device_data, prop)

    @property
    def is_on(self) -> bool | None:
        return as_bool(self.value)

    async def async_turn_on(self, **kwargs) -> None:
        await self.async_write_value(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.async_write_value(False)
