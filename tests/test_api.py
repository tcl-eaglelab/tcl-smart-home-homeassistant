import asyncio
import importlib.util
import sys
import types
from pathlib import Path

import pytest

PACKAGE_NAME = "tcl_smart_home_test"
PACKAGE_PATH = Path(__file__).parents[1] / "custom_components" / "tcl_smart_home"

package = types.ModuleType(PACKAGE_NAME)
package.__path__ = [str(PACKAGE_PATH)]
sys.modules.setdefault(PACKAGE_NAME, package)

const_spec = importlib.util.spec_from_file_location(
    f"{PACKAGE_NAME}.const", PACKAGE_PATH / "const.py"
)
assert const_spec and const_spec.loader
const_module = importlib.util.module_from_spec(const_spec)
sys.modules[const_spec.name] = const_module
const_spec.loader.exec_module(const_module)

routing_spec = importlib.util.spec_from_file_location(
    f"{PACKAGE_NAME}.routing", PACKAGE_PATH / "routing.py"
)
assert routing_spec and routing_spec.loader
routing_module = importlib.util.module_from_spec(routing_spec)
sys.modules[routing_spec.name] = routing_module
routing_spec.loader.exec_module(routing_module)

api_spec = importlib.util.spec_from_file_location(
    f"{PACKAGE_NAME}.api", PACKAGE_PATH / "api.py"
)
assert api_spec and api_spec.loader
api_module = importlib.util.module_from_spec(api_spec)
sys.modules[api_spec.name] = api_module
api_spec.loader.exec_module(api_module)


class _Response:
    status = 200

    async def text(self) -> str:
        return "not json"

    async def json(self):
        raise api_module.aiohttp.ContentTypeError(
            request_info=None,
            history=(),
        )


class _RequestContext:
    async def __aenter__(self):
        return _Response()

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class _Session:
    def request(self, *args, **kwargs):
        return _RequestContext()


def _route():
    return routing_module.get_country_route("IN")


def _domestic_route():
    return routing_module.get_country_route("CN")


def test_invalid_json_is_reported_as_tcl_api_error() -> None:
    api = api_module.create_api(_Session(), _route())

    async def run():
        try:
            await api._raw_request(
                "GET",
                "https://cn.account.tcl.com/synthetic",
                authenticated=False,
            )
        except api_module.TCLApiError as err:
            return str(err)
        raise AssertionError("expected TCLApiError")

    message = asyncio.run(run())
    assert "invalid JSON" in message


def test_concurrent_expiry_checks_refresh_only_once() -> None:
    api = api_module.create_api(
        _Session(),
        _route(),
        access_token="old-token",
        refresh_token="refresh-token",
        token_expires=1,
        application_secret="synthetic-only",
    )
    refresh_calls = 0

    async def fake_raw_request(*args, **kwargs):
        nonlocal refresh_calls
        refresh_calls += 1
        await asyncio.sleep(0)
        return {
            "code": 200,
            "data": {
                "accessToken": "new-token",
                "refreshToken": "new-refresh-token",
            },
        }

    api._raw_request = fake_raw_request

    async def run():
        await asyncio.gather(api._ensure_token(), api._ensure_token())

    asyncio.run(run())

    assert refresh_calls == 1
    assert api.access_token == "new-token"
    assert api.refresh_token == "new-refresh-token"


def test_model_uses_openclaw_endpoint_and_escapes_product_key() -> None:
    api = api_module.create_api(_Session(), _route())
    calls = []
    model = {"productKey": "pk /?#", "properties": [{"identifier": "powerSwitch"}]}

    async def request(method, url, **kwargs):
        calls.append((method, url))
        return model

    api._request = request
    assert asyncio.run(api.async_get_model("pk /?#")) == model
    assert calls == [("GET", api.route.iot_url + "/tsl/pk%20%2F%3F%23/tsl/openclaw")]


@pytest.mark.parametrize("country", ["IN", "DE", "US", "BR"])
def test_model_request_uses_selected_region_and_english_header(country) -> None:
    model = {"productKey": "test-product", "properties": []}

    class Response(_Response):
        async def json(self):
            return {"code": "200", "data": model}

    class Context(_RequestContext):
        async def __aenter__(self):
            return Response()

    calls = []

    class Session:
        def request(self, method, url, **kwargs):
            calls.append((method, url, kwargs))
            return Context()

    route = routing_module.get_country_route(country)
    api = api_module.create_api(Session(), route, access_token="test-token")
    assert asyncio.run(api.async_get_model("test-product")) == model
    assert len(calls) == 1
    method, url, options = calls[0]
    assert method == "GET"
    assert url == route.iot_url + "/tsl/test-product/tsl/openclaw"
    assert options["headers"]["Accept-Language"] == "en"
    assert options["headers"]["countryCode"] == country


def test_model_failure_propagates_without_endpoint_fallback() -> None:
    api = api_module.create_api(_Session(), _route())
    calls = []

    async def request(method, url, **kwargs):
        calls.append(url)
        raise api_module.TCLApiError("HTTP 404", code=404)

    api._request = request
    with pytest.raises(api_module.TCLApiError):
        asyncio.run(api.async_get_model("test-product"))
    assert calls == [api.route.iot_url + "/tsl/test-product/tsl/openclaw"]


def test_domestic_country_uses_domestic_qr_client_and_new_model_endpoint() -> None:
    api = api_module.create_api(_Session(), _domestic_route())
    calls = []
    model = {"productKey": "domestic-product", "properties": []}

    async def request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return model

    api._request = request
    assert asyncio.run(api.async_get_model("domestic-product")) == model
    assert calls == [
        ("GET", "https://io.zx.tcljd.com/tsl/domestic-product/tsl/openclaw", {})
    ]


def test_qr_check_reports_pending_without_sleeping() -> None:
    api = api_module.create_api(_Session(), _domestic_route())

    async def check(code):
        assert code == "qr"
        return {"status": 204, "msg": "waiting"}

    api.async_check_qr = check
    assert asyncio.run(api.async_try_authorize_qr("qr")) is False


def test_qr_check_accepts_authorization_once() -> None:
    api = api_module.create_api(_Session(), _domestic_route())

    async def check(code):
        return {"status": 1, "data": {"token": "access", "refreshToken": "refresh"}}

    api.async_check_qr = check
    assert asyncio.run(api.async_try_authorize_qr("qr")) is True
    assert api.access_token == "access"
    assert api.refresh_token == "refresh"


def test_qr_check_reports_expiry() -> None:
    api = api_module.create_api(_Session(), _domestic_route())

    async def check(code):
        return {"status": 400, "msg": "QR code expired"}

    api.async_check_qr = check
    with pytest.raises(api_module.TCLAuthError, match="expired"):
        asyncio.run(api.async_try_authorize_qr("qr"))
