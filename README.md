# TCL Smart Home for Home Assistant

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![HA Integration](https://img.shields.io/badge/Home%20Assistant-Custom%20Integration-blue.svg)](https://www.home-assistant.io/)
[![Version](https://img.shields.io/badge/version-0.3.3-green.svg)](CHANGELOG.md)

A single Home Assistant integration for TCL accounts in **mainland China** and **overseas regions**. The integration keeps one domain (`tcl_smart_home`) while selecting the account-center, IoT protocol, QR authorization, request headers, and timezone from the country chosen during setup.

## Supported appliances

| Appliance | Controls | Read-only sensors |
|---|---|---|
| **Air conditioner** | Power, mode, target temperature, fan speed, swing | Current temperature |
| **Refrigerator** | Fridge/freezer temperature, quick cool/freeze, child lock | Actual temperatures, door status |
| **Washing machine** | Program, start/pause, wash temperature, spin speed, rinse count | Running status, remaining time, current program |
| **Washer-dryer** | All washing controls + drying program, start/pause dry, dry level | Drying status, remaining time |
| **Door lock** | Electronic deadlock, voice volume, chime volume, loitering alert | Door status, battery levels, lock state |

Capability discovery is **fail-closed**: only reviewed product/schema pairs can write. Unrecognised properties never become controls merely because the cloud marks them writable. See [control scope](docs/CONTROLS-0.3.2.md) and [capability profiles](docs/CAPABILITIES-0.3.0.md).

## Installation

### Prerequisites

- Home Assistant ≥ 2026.9.4
- A TCL account with devices registered (mainland China or overseas)
- TCL application credentials obtained through an authorized channel

### Step 1: Configure credentials

Application secrets are **not bundled**. Add them to your HA configuration before installing:

`configuration.yaml`:
```yaml
tcl_smart_home:
  domestic_app_secret: !secret tcl_ha_domestic_app_secret
  overseas_client_secret: !secret tcl_ha_overseas_client_secret
```

`secrets.yaml`:
```yaml
tcl_ha_domestic_app_secret: "YOUR_AUTHORIZED_DOMESTIC_SECRET"
tcl_ha_overseas_client_secret: "YOUR_AUTHORIZED_OVERSEAS_SECRET"
```

Configure only the route you use. Never publish `secrets.yaml` or backups. `!secret` separates configuration; it is not encryption.

### Step 2: Install the integration

**Via HACS** (recommended once publicly listed):

1. Add this repository as a HACS custom Integration repository.
2. Search for "TCL Smart Home" in HACS and install.
3. Restart Home Assistant.

**Manual installation**:

1. Copy the `custom_components/tcl_smart_home/` folder into your HA `custom_components/` directory.
2. Restart Home Assistant.

### Step 3: Add your TCL account

1. Go to **Settings → Devices & services → Add integration → TCL Smart Home**.
2. Select the **country where your TCL account is registered** (e.g. Mainland China [CN], Germany [DE]).
3. The integration automatically chooses the matching account center, QR protocol, IoT gateway, and timezone.
4. Scan the displayed QR code with the TCL App and click **I have scanned — continue**.
5. The integration discovers your devices and creates entities for reviewed capabilities.

> The country is the **TCL account country**, not the HA installation country, IP location, or UI language. Add the integration again with another country to manage multiple TCL accounts.

## Route selection

| Selection | Account center | IoT gateway | QR protocol |
| --- | --- | --- | --- |
| Mainland China [CN] | `cn.account.tcl.com` | `io.zx.tcljd.com` | Domestic TCL QR API |
| Overseas country | Country's mapped account center | Regional gateway | Overseas TCL QR API |

Overseas countries are mapped to the SG, FR, US, or BR service region from the bundled country table (249 countries). Users select their actual country; they never select the service region.

## Features

- **Unified integration**: Domestic and overseas QR authorization behind one domain
- **Country-based routing**: Independent config entries per country with automatic protocol selection
- **Model-driven entities**: Device discovery, status polling, Thing Model discovery, and capability-based entity creation
- **Reviewed controls**: Climate, binary sensor, sensor, switch, number, select, and button entities — all validated against product/schema profiles
- **Bilingual**: Chinese names for domestic accounts, English for overseas, independent of HA locale
- **Security hardening**: TLS-only, redirect rejection, domain allowlist, redacted diagnostics, admin-only raw service, bounded rate limiting
- **Polling**: Default 30 seconds, configurable 15–300 seconds, with bounded backoff on 429/5xx/connection failures

## Polling

The default polling interval is **30 seconds**. Change it from **Settings → Devices & services → TCL Smart Home → Configure**. Valid range is 15–300 seconds. The backend refreshes the device list and each device's properties. Thing Models are cached for 15 minutes. Saving a changed interval reloads the integration automatically.

## Upgrading from previous versions

### From 0.2.x (bundled secrets)

**Application secrets are no longer bundled.** Configure local credentials before upgrading. The optional migration helper can extract credentials from an old installation:

```text
python tools/migrate_credentials.py /path/to/ha/config          # dry run
python tools/migrate_credentials.py /path/to/ha/config --apply   # backup + migrate
```

Previously distributed packages still contain the old credentials and may require vendor rotation.

### From 0.3.0+

Existing domestic config entries are upgraded in place. Tokens and supported entity IDs are retained. Retired/unsafe/duplicate entities are disabled without deleting registry/history. Review dependent automations.

### From the overseas package (`tcl_smart_home_overseas`)

The old overseas package used a different domain and cannot be silently converted. Migration steps:

1. Install the unified package while keeping the old overseas integration temporarily.
2. Add **TCL Smart Home** and choose the same account country.
3. Complete QR authorization and confirm devices/entities are present.
4. Update automations and dashboards to the new entity IDs.
5. Remove the old overseas integration after verifying the new entry.

## Security

- **No bundled secrets**: Application credentials are read from local HA YAML only
- **TLS enforced**: All requests use HTTPS with certificate verification; redirects are rejected
- **Domain allowlist**: Only known TCL account and IoT endpoints are contacted
- **Write validation**: Product + schema match, type/range/step/enum validation before any command
- **Admin-only raw service**: `set_property` requires a user context and administrator role
- **Redacted diagnostics**: Only structural counts and boolean status are exported
- **No remote unlock**: Door lock controls are limited to settings; `openDoor` is not implemented

See [the security audit](docs/AUDIT-0.3.3.md) and [security policy](SECURITY.md) for details and remaining risks.

## Development

```bash
python -m pip install -r requirements-test.txt
python -m compileall -q custom_components
python -m pytest -q
black --check custom_components tests
ruff check custom_components tests tools
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Control scope](docs/CONTROLS-0.3.2.md)
- [Capability profiles](docs/CAPABILITIES-0.3.0.md)
- [Security audit](docs/AUDIT-0.3.3.md)
- [Changelog](CHANGELOG.md)

## License

MIT. See [LICENSE](LICENSE).

## Disclaimer

This is a custom integration, not an official Home Assistant Core integration or a security certification. TCL, the TCL logo, and product names are trademarks of TCL — verify brand and API usage terms before public distribution.
