from __future__ import annotations

from homeassistant.components.select import SelectEntity

from .capabilities import platform_for
from .entity import TCLPropertyEntity
from .model import (
    enum_display_options,
    model_properties,
)

PARALLEL_UPDATES = 1


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        TCLPropertySelect(coordinator, device, prop)
        for device in coordinator.devices.values()
        for prop in model_properties(device.model)
        if platform_for(device.device, device.model, prop) == "select"
    )


class TCLPropertySelect(TCLPropertyEntity, SelectEntity):
    """Expose a writable enum TSL property as a select."""

    def __init__(self, coordinator, device_data, prop) -> None:
        super().__init__(coordinator, device_data, prop)
        self._options_by_value = enum_display_options(prop, self.display_language)

    @property
    def options(self) -> list[str]:
        return [label for _, label in self._options_by_value]

    @property
    def current_option(self) -> str | None:
        value = self.value
        for raw, label in self._options_by_value:
            if str(raw) == str(value):
                return label
        return str(value) if value is not None else None

    async def async_select_option(self, option: str) -> None:
        for raw, label in self._options_by_value:
            if label == option:
                await self.async_write_value(raw)
                return
        raise ValueError(f"Unknown TCL option: {option}")
