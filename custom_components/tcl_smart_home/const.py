DOMAIN = "tcl_smart_home"
NAME = "TCL Smart Home"

PLATFORMS = [
    "binary_sensor",
    "button",
    "climate",
    "number",
    "select",
    "sensor",
    "switch",
]


# Domestic TCL account and IoT endpoints. They are selected automatically when
# the user chooses mainland China in the account-country step.
DOMESTIC_AUTH_URL = "https://cn.account.tcl.com"
DOMESTIC_IOT_URL = "https://io.zx.tcljd.com"
DOMESTIC_APP_ID = "23301773132314850"
DOMESTIC_TENANT_ID = "tcl"
DOMESTIC_STORE_UUID = "OPENCLAW"

OVERSEAS_CLIENT_ID = "52109545"
QR_CODE_SIZE = "400"

CONF_COUNTRY_CODE = "country_code"
CONF_ACCESS_TOKEN = "access_token"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_TOKEN_EXPIRES = "token_expires"
CONF_VERIFY_SSL = "verify_ssl"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_SCAN_INTERVAL_SECONDS = 30
MIN_SCAN_INTERVAL_SECONDS = 15
MAX_SCAN_INTERVAL_SECONDS = 300
QR_VALIDITY_SECONDS = 300
TOKEN_REFRESH_WINDOW_MS = 300_000
HTTP_TIMEOUT = 30
MAX_CONCURRENT_REQUESTS = 4
MODEL_REFRESH_INTERVAL_SECONDS = 900

APP_VERSION = "7.4.2"
THOME_VERSION = "7.1.0"
PLATFORM = "ios"
LANGUAGE = "en"

ATTR_DEVICE_ID = "device_id"
ATTR_PROPERTY = "property"
ATTR_VALUE = "value"

SERVICE_SET_PROPERTY = "set_property"
