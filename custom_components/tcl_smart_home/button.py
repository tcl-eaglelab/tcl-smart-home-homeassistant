"""Explicit appliance actions; reported states never become command choices."""

from homeassistant.components.button import ButtonEntity

from .capabilities import capability
from .entity import TCLPropertyEntity
from .model import model_properties

PARALLEL_UPDATES = 1


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        TCLActionButton(coordinator, device, prop, action)
        for device in coordinator.devices.values()
        for prop in model_properties(device.model)
        for action in capability(device.device, device.model, prop).actions
    )


class TCLActionButton(TCLPropertyEntity, ButtonEntity):
    """Send one reviewed value through the same validated coordinator path."""

    def __init__(self, coordinator, device_data, prop, action):
        super().__init__(coordinator, device_data, prop)
        self._action_value = action["value"]
        self._attr_unique_id = f"{self._device_id}_{self.property_id}_{action['id']}"
        self._attr_name = action["names"][self.display_language]
        self._attr_icon = action["icon"]

    async def async_press(self) -> None:
        await self.async_write_value(self._action_value)
