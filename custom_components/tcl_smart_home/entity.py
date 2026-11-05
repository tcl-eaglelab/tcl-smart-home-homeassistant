from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .capabilities import capability, profile_kind, reviewed_property_name
from .const import CONF_COUNTRY_CODE, DOMAIN
from .coordinator import TCLCoordinator, TCLDeviceData
from .model import (
    device_is_available,
    model_properties,
    property_icon,
    property_identifier,
)


class TCLDeviceEntity(CoordinatorEntity[TCLCoordinator]):
    """Base entity for a TCL device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TCLCoordinator,
        device_data: TCLDeviceData,
    ) -> None:
        super().__init__(coordinator)
        self._device_id = device_data.device_id
        self._attr_unique_id = f"{self._device_id}_device"

    @property
    def display_language(self) -> str:
        entry = self.coordinator.entry
        return "zh-Hans" if entry.data.get(CONF_COUNTRY_CODE, "CN") == "CN" else "en"

    @property
    def device_data(self) -> TCLDeviceData:
        return self.coordinator.get_device(self._device_id) or TCLDeviceData(
            {}, {}, {}, status_ok=False
        )

    @property
    def device(self) -> dict[str, Any]:
        return self.device_data.device

    @property
    def status(self) -> dict[str, Any]:
        return self.device_data.status

    @property
    def properties(self) -> list[dict[str, Any]]:
        return model_properties(self.device_data.model)

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        if not self.device_data.status_ok:
            return False
        return device_is_available(
            self.device, profile_kind(self.device), self.status
        )

    @property
    def device_info(self) -> DeviceInfo:
        family = self.device.get("family")
        family_name = family.get("familyName") if isinstance(family, Mapping) else None
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=str(
                self.device.get("nickName")
                or self.device.get("name")
                or self.device.get("deviceName")
                or self._device_id
            ),
            manufacturer="TCL",
            model=str(
                self.device.get("productKey") or self.device.get("category") or "TCL"
            ),
            serial_number=self._device_id,
            suggested_area=str(self.device.get("locationName") or family_name or "")
            or None,
        )

    async def async_set_property(self, property_name_value: str, value: Any) -> None:
        await self.coordinator.async_set_property(
            self._device_id,
            property_name_value,
            value,
        )


class TCLPropertyEntity(TCLDeviceEntity):
    """Base entity backed by one TSL property."""

    def __init__(
        self,
        coordinator: TCLCoordinator,
        device_data: TCLDeviceData,
        prop: Mapping[str, Any],
    ) -> None:
        super().__init__(coordinator, device_data)
        rule = capability(device_data.device, device_data.model, dict(prop))
        self._attr_entity_registry_enabled_default = rule.enabled
        self._attr_entity_category = (
            EntityCategory.DIAGNOSTIC
            if rule.tier == "diagnostic"
            else (
                EntityCategory.CONFIG
                if rule.tier == "advanced" and rule.writable
                else None
            )
        )
        self._property = dict(prop)
        identifier = property_identifier(self._property)
        self._property_id = identifier
        self._attr_unique_id = f"{self._device_id}_{identifier}"
        self._attr_icon = property_icon(self._property)
        # Account route fixes capability language independently of HA's locale.
        self._attr_translation_key = None
        self._attr_name = reviewed_property_name(
            device_data.device, device_data.model, self._property, self.display_language
        )

    @property
    def tsl_property(self) -> dict[str, Any]:
        return self._property

    @property
    def property_id(self) -> str:
        return self._property_id

    @property
    def value(self) -> Any:
        return self.status.get(self._property_id)

    async def async_write_value(self, value: Any) -> None:
        await self.async_set_property(self._property_id, value)
