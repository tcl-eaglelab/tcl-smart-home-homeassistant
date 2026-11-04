"""QR button transitions; HA rendering is also checked against a running instance."""

import importlib
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


@pytest.fixture
def flow_module(monkeypatch):
    def stub(name, **attrs):
        module = types.ModuleType(name)
        module.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, name, module)
        return module

    class Flow:
        def __init_subclass__(cls, **kwargs):
            pass

        def async_show_menu(self, **kwargs):
            assert hasattr(self, f"async_step_{kwargs['step_id']}")
            return {"type": "menu", **kwargs}

        def async_show_form(self, **kwargs):
            return {"type": "form", **kwargs}

        def async_create_entry(self, **kwargs):
            return {"type": "create_entry", **kwargs}

        def async_update_reload_and_abort(self, entry, **kwargs):
            return {
                "type": "abort",
                "reason": "reauth_successful",
                "entry": entry,
                **kwargs,
            }

        def async_abort(self, **kwargs):
            return {"type": "abort", **kwargs}

    stub("homeassistant", __path__=[])
    stub("homeassistant.config_entries", ConfigFlow=Flow, OptionsFlowWithReload=Flow)
    stub("homeassistant.core", callback=lambda f: f)
    stub("homeassistant.helpers", __path__=[])
    stub(
        "homeassistant.helpers.aiohttp_client",
        async_get_clientsession=lambda _: object(),
    )
    package = "tcl_flow_tests"
    path = Path(__file__).parents[1] / "custom_components/tcl_smart_home"
    stub(package, __path__=[str(path)])
    # Remove modules from prior tests so exception identities stay aligned.
    for name in list(sys.modules):
        if name.startswith(package + "."):
            monkeypatch.delitem(sys.modules, name)
    stub(f"{package}.qr_frontend", async_setup_qr_frontend=AsyncMock())
    return importlib.import_module(package + ".config_flow")


@pytest.fixture
def qr_flow(flow_module, monkeypatch):
    api = SimpleNamespace(
        async_get_qr=AsyncMock(
            side_effect=[
                {"code": "first", "image_url": "https://example.test/first.png"},
                {"code": "second", "image_url": "https://example.test/second.png"},
            ]
        ),
        async_try_authorize_qr=AsyncMock(return_value=False),
        async_get_devices=AsyncMock(return_value=[]),
        access_token="test-access",
        refresh_token="test-refresh",
        token_expires=1234,
    )
    monkeypatch.setattr(flow_module, "create_api", lambda *args, **kwargs: api)
    flow = flow_module.TCLConfigFlow()
    flow.hass = SimpleNamespace(
        data={"tcl_smart_home": {"domestic_app_secret": "synthetic-only"}}
    )
    flow._country_code = "CN"
    return flow, api


@pytest.mark.asyncio
async def test_refresh_button_changes_code_once_without_authorizing(qr_flow):
    flow, api = qr_flow
    first = await flow.async_step_refresh_qr()
    second = await flow.async_step_refresh_qr()
    assert first["type"] == second["type"] == "menu"
    assert second["menu_options"] == ["check_authorization", "refresh_qr"]
    assert first["description_placeholders"] != second["description_placeholders"]
    assert flow._qr_code == "second"
    assert api.async_get_qr.await_count == 2
    api.async_try_authorize_qr.assert_not_awaited()


@pytest.mark.asyncio
async def test_pending_check_returns_buttons_then_can_succeed(qr_flow):
    flow, api = qr_flow
    await flow.async_step_refresh_qr()
    pending = await flow.async_step_check_authorization()
    assert pending["step_id"] == "authorize_pending"
    assert "refresh_qr" in pending["menu_options"]
    api.async_try_authorize_qr.assert_awaited_once_with("first")
    api.async_try_authorize_qr.return_value = True
    success = await flow.async_step_check_authorization()
    assert success["type"] == "create_entry"
    assert success["data"]["country_code"] == "CN"
    assert success["data"]["access_token"] == "test-access"


@pytest.mark.asyncio
async def test_expired_code_is_replaced_without_authorizing(
    qr_flow, flow_module, monkeypatch
):
    flow, api = qr_flow
    await flow.async_step_refresh_qr()
    monkeypatch.setattr(
        flow_module.time, "monotonic", lambda: flow._qr_created_at + 301
    )
    result = await flow.async_step_check_authorization()
    assert result["step_id"] == "authorize_expired"
    assert flow._qr_code == "second"
    api.async_try_authorize_qr.assert_not_awaited()


@pytest.mark.asyncio
async def test_refresh_failure_clears_old_code_and_is_retryable(qr_flow, flow_module):
    flow, api = qr_flow
    await flow.async_step_refresh_qr()
    api.async_get_qr.side_effect = flow_module.TCLConnectionError("offline")
    result = await flow.async_step_refresh_qr()
    assert result["step_id"] == "authorize_unavailable"
    assert result["menu_options"] == ["refresh_qr"]
    assert not flow._qr_code and not flow._qr_url
    api.async_get_qr.side_effect = None
    api.async_get_qr.return_value = {
        "code": "retry",
        "image_url": "https://example.test/retry.png",
    }
    assert (await flow.async_step_refresh_qr())["step_id"] == "authorize"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error_name,expected",
    [
        ("TCLConnectionError", "authorize_retry"),
        ("TCLApiError", "authorize_failed"),
        ("TCLAuthError", "authorize_expired"),
    ],
)
async def test_cloud_errors_keep_flow_recoverable(
    qr_flow, flow_module, error_name, expected
):
    flow, api = qr_flow
    await flow.async_step_refresh_qr()
    api.async_try_authorize_qr.side_effect = getattr(flow_module, error_name)(
        "QR code expired"
    )
    result = await flow.async_step_check_authorization()
    assert result["step_id"] == expected
    assert "refresh_qr" in result["menu_options"]
    api.async_try_authorize_qr.side_effect = None
    api.async_try_authorize_qr.return_value = True
    assert (await flow.async_step_check_authorization())["type"] == "create_entry"


@pytest.mark.asyncio
async def test_reauth_keeps_existing_entry_data(qr_flow):
    flow, api = qr_flow
    entry = SimpleNamespace(data={"country_code": "CN", "keep_me": True})
    flow.context = {"entry_id": "existing"}
    flow.hass.config_entries = SimpleNamespace(async_get_entry=lambda _: entry)
    result = await flow.async_step_reauth(entry.data)
    assert result["type"] == "menu"
    api.async_try_authorize_qr.return_value = True
    result = await flow.async_step_check_authorization()
    assert result["reason"] == "reauth_successful"
    assert result["data"]["keep_me"] is True
    assert result["entry"] is entry


@pytest.mark.asyncio
async def test_missing_application_credentials_does_not_request_a_qr(qr_flow):
    flow, api = qr_flow
    flow.hass.data = {}
    result = await flow.async_step_refresh_qr()
    assert result["reason"] == "missing_application_credentials"
    api.async_get_qr.assert_not_awaited()


@pytest.mark.asyncio
async def test_authorized_token_without_device_api_access_does_not_create_entry(
    qr_flow, flow_module
):
    flow, api = qr_flow
    await flow.async_step_refresh_qr()
    api.async_try_authorize_qr.return_value = True
    api.async_get_devices.side_effect = flow_module.TCLAuthError("Access denied")
    result = await flow.async_step_check_authorization()
    assert result["type"] == "menu"
    assert result["step_id"] == "authorize_failed"
