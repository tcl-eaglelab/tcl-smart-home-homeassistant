# TCL Smart Home for Home Assistant

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![HA Integration](https://img.shields.io/badge/Home%20Assistant-Custom%20Integration-blue.svg)](https://www.home-assistant.io/)
[![Version](https://img.shields.io/badge/version-1.0.0-green.svg)](CHANGELOG.md)
[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=tcl_smart_home)

A single Home Assistant integration for TCL accounts in **mainland China** and **overseas regions**. The integration keeps one domain (`tcl_smart_home`) while selecting the account-center, IoT protocol, QR authorization, request headers, and timezone from the country chosen during setup.

## Supported appliances

| Appliance | Controls | Read-only sensors |
|---|---|---|
| **Air conditioner** | Power, mode, target temperature, fan speed, swing | Current temperature |
| **Refrigerator** | Fridge/freezer temperature, quick cool/freeze, child lock | Actual temperatures, door status |
| **Washing machine** | Program, start/pause, wash temperature, spin speed, rinse count | Running status, remaining time, current program |
| **Washer-dryer** | All washing controls + drying program, start/pause dry, dry level | Drying status, remaining time |
| **Door lock** | Electronic deadlock, voice volume, chime volume, loitering alert | Door status, battery levels, lock state |

Capability discovery is **fail-closed**: only reviewed product/schema pairs can write. Unrecognised properties never become controls merely because the cloud marks them writable.

## Installation

### Prerequisites

- Home Assistant ≥ 2026.9.4
- A TCL account with devices registered (mainland China or overseas)
### Step 1: Mainland China can scan immediately

The mainland China application credential is built in. It is the same public OAuth client credential published with TCL Smart Home CLI. Choose Mainland China and scan with the TCL App. A `domestic_app_secret` entry in `configuration.yaml` overrides the built-in value.

Overseas accounts still need `overseas_client_secret` before installation:

`configuration.yaml`:
```yaml
tcl_smart_home:
  overseas_client_secret: !secret tcl_ha_overseas_client_secret
```

`secrets.yaml`:
```yaml
tcl_ha_overseas_client_secret: "YOUR_AUTHORIZED_OVERSEAS_SECRET"
```

Never publish `secrets.yaml` or backups. `!secret` separates configuration; it is not encryption.

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

## Security

- **Domestic credential bundled**: Mainland China uses the public client credential; the overseas credential is still read only from local YAML
- **TLS enforced**: All requests use HTTPS with certificate verification; redirects are rejected
- **Domain allowlist**: Only known TCL account and IoT endpoints are contacted
- **Write validation**: Product + schema match, type/range/step/enum validation before any command
- **Admin-only raw service**: `set_property` requires a user context and administrator role
- **Redacted diagnostics**: Only structural counts and boolean status are exported
- **No remote unlock**: Door lock controls are limited to settings; `openDoor` is not implemented

See [the security policy](SECURITY.md) for the release boundary and [the privacy notice](PRIVACY.md) for what personal data is processed.

## Actions

`tcl_smart_home.set_property` writes one reviewed property. It requires a user context and an administrator. Automations should use the entity actions instead.

| Field | Required | Meaning |
| --- | --- | --- |
| `device_id` | yes | TCL `deviceId` |
| `property` | yes | Approved property identifier. Engineering and lock-unlock commands are rejected |
| `value` | yes | `0` or `1` for a boolean, a number for a range, or the option code for an enum |

## Removal

1. Open **Settings → Devices & services → TCL Smart Home**, then delete the integration entry.
2. Remove the `tcl_smart_home` block from `configuration.yaml` and the matching keys from `secrets.yaml`.
3. For a manual install, delete `custom_components/tcl_smart_home`.
4. Restart Home Assistant when it asks. An update or removal of an already loaded integration needs a restart.

## Documentation

- [Privacy notice](PRIVACY.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Changelog](CHANGELOG.md)
- [Contributing](CONTRIBUTING.md)

## License

MIT. See [LICENSE](LICENSE).

## Disclaimer

This is a custom integration, not an official Home Assistant Core integration or a security certification. TCL, the TCL logo, and product names are trademarks of TCL — verify brand and API usage terms before public distribution.
