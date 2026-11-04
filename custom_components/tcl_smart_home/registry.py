from __future__ import annotations

from collections.abc import Iterable

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .capabilities import capability, has_climate, platform_for
from .const import DOMAIN


def apply_capability_policy(hass, entry, coordinator) -> None:
    """Disable retired controls without deleting IDs, history or user choices."""
    registry = er.async_get(hass)
    allowed = set()
    enabled_primary = set()
    known_prefixes = []
    unsupported_count = 0
    for device in coordinator.devices.values():
        allowed.add(("binary_sensor", f"{device.device_id}_cloud_connectivity"))
        # A temporary model-fetch failure must not permanently disable old entities.
        if not device.model.get("properties"):
            continue
        known_prefixes.append(f"{device.device_id}_")
        before = len(allowed)
        if has_climate(device.device, device.model):
            allowed.add(("climate", f"{device.device_id}_climate"))
            enabled_primary.add(("climate", f"{device.device_id}_climate"))
        for prop in device.model.get("properties", []):
            rule = capability(device.device, device.model, prop)
            platform = platform_for(device.device, device.model, prop)
            if platform:
                allowed.add((platform, f"{device.device_id}_{prop['identifier']}"))
                if rule.enabled:
                    enabled_primary.add(
                        (platform, f"{device.device_id}_{prop['identifier']}")
                    )
            for action in rule.actions:
                key = (
                    "button",
                    f"{device.device_id}_{prop['identifier']}_{action['id']}",
                )
                allowed.add(key)
                if rule.enabled:
                    enabled_primary.add(key)
        if len(allowed) == before:
            unsupported_count += 1
    if unsupported_count:
        from homeassistant.components import persistent_notification

        persistent_notification.async_create(
            hass,
            (
                f"有 {unsupported_count} 台设备暂时仅显示云端在线状态，具体功能仍需适配产品物模型。"
                if entry.data.get("country_code", "CN") == "CN"
                else f"{unsupported_count} devices currently show only cloud connectivity. Their product capabilities still need review."
            ),
            title="TCL Smart Home",
            notification_id=f"tcl_unsupported_{entry.entry_id}",
        )
    count = 0
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        if entity.platform != DOMAIN or not any(
            entity.unique_id.startswith(prefix) for prefix in known_prefixes
        ):
            continue
        if (
            (entity.domain, entity.unique_id) in enabled_primary
            and entity.disabled_by == er.RegistryEntryDisabler.INTEGRATION
        ):
            registry.async_update_entity(entity.entity_id, disabled_by=None)
        if (
            entity.domain,
            entity.unique_id,
        ) not in allowed and entity.disabled_by is None:
            registry.async_update_entity(
                entity.entity_id, disabled_by=er.RegistryEntryDisabler.INTEGRATION
            )
            count += 1
    if count:
        from homeassistant.components import persistent_notification

        chinese = entry.data.get("country_code", "CN") == "CN"
        persistent_notification.async_create(
            hass,
            (
                f"能力更新已停用 {count} 个未经审核或重复的旧实体。实体记录和历史未删除；请检查引用旧实体的自动化，温度设置和程序现通过控制实体操作。"
                if chinese
                else f"The capability update disabled {count} unreviewed or duplicate old entities. Registry records and history were retained. Review automations using old entities; use the new controls for settings and programs."
            ),
            title="TCL Smart Home",
            notification_id=f"tcl_policy_{entry.entry_id}",
        )


def remove_stale_devices(
    hass: HomeAssistant,
    entry: ConfigEntry,
    active_device_ids: Iterable[str],
) -> None:
    """Remove TCL entities and devices no longer returned by the cloud API."""
    active_ids = {str(device_id) for device_id in active_device_ids}
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    stale_registry_ids: set[str] = set()

    for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        tcl_ids = {
            str(identifier[1])
            for identifier in device.identifiers
            if len(identifier) == 2 and identifier[0] == DOMAIN
        }
        if tcl_ids and tcl_ids.isdisjoint(active_ids):
            stale_registry_ids.add(device.id)

    for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
        if entity.platform == DOMAIN and entity.device_id in stale_registry_ids:
            entity_registry.async_remove(entity.entity_id)

    for registry_id in stale_registry_ids:
        device_registry.async_remove_device(registry_id)
