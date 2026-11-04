"""Allowlisted diagnostic metadata; never export cloud bodies or identifiers."""

from __future__ import annotations

from .capabilities import capability


async def async_get_config_entry_diagnostics(hass, entry):
    coordinator = getattr(entry, "runtime_data", None)
    if coordinator is None:
        return {"loaded": False}
    devices = []
    for device in coordinator.devices.values():
        counts = {"primary": 0, "advanced": 0, "diagnostic": 0, "blocked": 0}
        for prop in device.model.get("properties", []):
            counts[capability(device.device, device.model, prop).tier] += 1
        devices.append(
            {
                "status_ok": bool(device.status_ok),
                "status_failures": int(device.status_failures),
                "property_counts": counts,
            }
        )
    return {
        "loaded": True,
        "update_success": bool(coordinator.last_update_success),
        "poll_interval_seconds": coordinator.update_interval.total_seconds(),
        "devices": devices,
    }
