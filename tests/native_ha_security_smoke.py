"""Run with an installed HA runtime: python tests/native_ha_security_smoke.py.

Uses an isolated temporary HA instance, synthetic identities and mocked cloud.
Never loads the user's config, connects to TCL or sends a real command.
"""

import asyncio
import importlib
import json
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError, Unauthorized
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

integration = importlib.import_module("custom_components.tcl_smart_home")
from custom_components.tcl_smart_home import capabilities as policy
from custom_components.tcl_smart_home.coordinator import TCLCoordinator, TCLDeviceData
from custom_components.tcl_smart_home.registry import apply_capability_policy


async def main():
    with tempfile.TemporaryDirectory(prefix="tcl-ha-security-") as directory:
        hass = HomeAssistant(directory)
        cloud = SimpleNamespace(async_control=AsyncMock(), tokens_changed=False)
        entry = SimpleNamespace(
            entry_id="synthetic-entry",
            options={},
            data={"country_code": "CN"},
            async_on_unload=lambda callback: None,
        )
        coordinator = TCLCoordinator(hass, entry, cloud)
        coordinator._model_cache["empty-model"] = {}
        coordinator._model_fetched_at["empty-model"] = time.monotonic() - 61
        assert coordinator._should_refresh_model("empty-model")
        coordinator._model_fetched_at["empty-model"] = time.monotonic()
        assert not coordinator._should_refresh_model("empty-model")
        coordinator._model_cache["valid-model"] = {"properties": [{"identifier": "a"}]}
        coordinator._model_fetched_at["valid-model"] = time.monotonic() - 61
        assert not coordinator._should_refresh_model("valid-model")
        product, profile = next(
            (k, v) for k, v in policy.PROFILES.items() if v["kind"] == "air_conditioner"
        )
        props = [
            {"identifier": key, **value["schema"]}
            for key, value in profile["properties"].items()
        ]
        props.append(
            {
                "identifier": "OutDoorCompTarFreqSet",
                "accessMode": "rw",
                "dataType": {"type": "int"},
            }
        )
        device = TCLDeviceData(
            {"deviceId": "synthetic-device", "productKey": product},
            {},
            {"productKey": product, "properties": props},
        )
        coordinator.async_set_updated_data({device.device_id: device})
        coordinator.async_request_refresh = AsyncMock()
        entry.runtime_data = coordinator
        hass.config_entries = SimpleNamespace(async_entries=lambda _: [entry])
        users = {
            "admin": SimpleNamespace(is_admin=True),
            "limited": SimpleNamespace(is_admin=False),
        }
        hass.auth = SimpleNamespace(
            async_get_user=AsyncMock(side_effect=lambda uid: users.get(uid))
        )
        with patch.object(integration, "async_setup_qr_frontend", AsyncMock()):
            await integration.async_setup(
                hass, {"tcl_smart_home": {"domestic_app_secret": "synthetic-only"}}
            )
        call = {
            "device_id": device.device_id,
            "property": "targetTemperature",
            "value": 22.5,
        }
        for user in ("limited", None):
            try:
                await hass.services.async_call(
                    "tcl_smart_home",
                    "set_property",
                    call,
                    blocking=True,
                    context=Context(user_id=user),
                )
            except Unauthorized:
                pass
            else:
                raise AssertionError("Non-admin call accepted")
        cloud.async_control.assert_not_awaited()
        await hass.services.async_call(
            "tcl_smart_home",
            "set_property",
            call,
            blocking=True,
            context=Context(user_id="admin"),
        )
        cloud.async_control.assert_awaited_once_with(
            device.device_id, {"targetTemperature": 22.5}
        )
        cloud.async_control.reset_mock()
        for identifier, value in [
            ("targetTemperature", 999),
            ("targetTemperature", 22.1),
            ("OutDoorCompTarFreqSet", 1),
            ("not-a-property", True),
        ]:
            try:
                await coordinator.async_set_property(
                    device.device_id, identifier, value
                )
            except HomeAssistantError:
                pass
            else:
                raise AssertionError("Disallowed write accepted")
        cloud.async_control.assert_not_awaited()
        # Real HA registry rows, injected into the policy migration boundary.
        dr.async_setup(hass)
        await dr.async_load(hass, load_empty=True)
        registry = er.EntityRegistry(hass)
        await registry.async_load(load_empty=True)
        old = registry.async_get_or_create(
            "number", "tcl_smart_home", "synthetic-device_OutDoorCompTarFreqSet"
        )
        primary = registry.async_get_or_create(
            "climate",
            "tcl_smart_home",
            "synthetic-device_climate",
            disabled_by=er.RegistryEntryDisabler.INTEGRATION,
        )
        advanced = registry.async_get_or_create(
            "switch", "tcl_smart_home", "synthetic-device_screen"
        )
        user_disabled = registry.async_get_or_create(
            "sensor",
            "tcl_smart_home",
            "synthetic-device_currentTemperature",
            disabled_by=er.RegistryEntryDisabler.USER,
        )
        connectivity = registry.async_get_or_create(
            "binary_sensor", "tcl_smart_home", "synthetic-device_cloud_connectivity"
        )
        entities = [old, primary, advanced, user_disabled, connectivity]
        with (
            patch(
                "custom_components.tcl_smart_home.registry.er.async_get",
                return_value=registry,
            ),
            patch(
                "custom_components.tcl_smart_home.registry.er.async_entries_for_config_entry",
                return_value=entities,
            ),
            patch(
                "homeassistant.components.persistent_notification.async_create"
            ) as notify,
        ):
            saved_model = device.model
            device.model = {}
            apply_capability_policy(hass, entry, coordinator)
            assert registry.async_get(old.entity_id).disabled_by is None
            notify.assert_not_called()
            device.model = saved_model
            apply_capability_policy(hass, entry, coordinator)
            assert (
                registry.async_get(old.entity_id).disabled_by
                == er.RegistryEntryDisabler.INTEGRATION
            )
            assert registry.async_get(primary.entity_id).disabled_by is None
            assert registry.async_get(connectivity.entity_id).disabled_by is None
            assert registry.async_get(advanced.entity_id).disabled_by is None
            assert (
                registry.async_get(user_disabled.entity_id).disabled_by
                == er.RegistryEntryDisabler.USER
            )
            notify.assert_called_once()
        # Actual coordinator validation and button dispatch, with a mocked transport.
        from custom_components.tcl_smart_home.button import TCLActionButton

        for identifier, value in [
            ("coldStorageTempC", 4),
            ("lowerShellRunStatus", "2"),
            ("lowerShellRunStatus", "1"),
            ("electronicLock", True),
        ]:
            pk, prof = next(
                (k, p)
                for k, p in policy.PROFILES.items()
                if identifier in p["properties"]
                and p["properties"][identifier]["writable"]
            )
            prop = {
                "identifier": identifier,
                **prof["properties"][identifier]["schema"],
            }
            device.device["productKey"] = pk
            device.model = {"properties": [prop]}
            cloud.async_control.reset_mock()
            if identifier == "lowerShellRunStatus":
                action = next(
                    a
                    for a in policy.capability(
                        device.device, device.model, prop
                    ).actions
                    if a["value"] == value
                )
                button = TCLActionButton(coordinator, device, prop, action)
                await button.async_press()
            else:
                await coordinator.async_set_property(
                    device.device_id, identifier, value
                )
            cloud.async_control.assert_awaited_once_with(
                device.device_id,
                {
                    identifier: policy.validate_write(
                        device.device, device.model, prop, value
                    )
                },
            )
            if identifier == "lowerShellRunStatus":
                cloud.async_control.reset_mock()
                for invalid in ("0", "3"):
                    try:
                        await coordinator.async_set_property(
                            device.device_id, identifier, invalid
                        )
                    except HomeAssistantError:
                        pass
                    else:
                        raise AssertionError("Reported state was sent as a command")
                cloud.async_control.assert_not_awaited()
        await coordinator.async_shutdown()
        await hass.async_stop(force=True)
        print(
            json.dumps(
                {
                    "admin_permissions": "passed",
                    "no_user_context_denied": True,
                    "backend_policy_and_values": "passed",
                    "registry_migration": "passed",
                    "real_cloud_commands": 0,
                }
            )
        )


asyncio.run(main())
