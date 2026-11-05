"""Read-only boolean capabilities, including door contact state."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.helpers.entity import EntityCategory

from .capabilities import platform_for, profile_kind
from .entity import TCLDeviceEntity, TCLPropertyEntity
from .model import cloud_connectivity_on, model_properties

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        TCLCloudConnectivity(coordinator, device)
        for device in coordinator.devices.values()
    )
    async_add_entities(
        TCLPropertyBinarySensor(coordinator, device, prop)
        for device in coordinator.devices.values()
        for prop in model_properties(device.model)
        if platform_for(device.device, device.model, prop) == "binary_sensor"
    )


class TCLCloudConnectivity(TCLDeviceEntity, BinarySensorEntity):
    """Keep every cloud-listed device visible, even without a supported model."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = True

    def __init__(self, coordinator, device_data):
        super().__init__(coordinator, device_data)
        self._attr_unique_id = f"{self._device_id}_cloud_connectivity"
        self._attr_name = (
            "云端在线" if self.display_language == "zh-Hans" else "Cloud connectivity"
        )

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and (
            self.coordinator.get_device(self._device_id) is not None
        )

    @property
    def is_on(self) -> bool | None:
        return cloud_connectivity_on(
            self.device, profile_kind(self.device), self.status
        )


class TCLPropertyBinarySensor(TCLPropertyEntity, BinarySensorEntity):
    """Create capabilities from the model even before the first state arrives."""

    @property
    def device_class(self):
        if self.property_id.lower() in {
            "doorstatus",
            "doorstate",
            "leftupdoorstatus",
            "rightupdoorstatus",
            "leftdowndoorstatus",
            "rightdowndoorstatus",
            "middledoorstatus",
            "downdoorstatus",
        }:
            return BinarySensorDeviceClass.DOOR
        return None

    @property
    def is_on(self) -> bool | None:
        value = self.value
        # Missing/unrecognised status must never imply the door is closed.
        if isinstance(value, bool):
            return value
        if value in (1, "1", "true", "on"):
            return True
        if value in (0, "0", "false", "off"):
            return False
        return None
