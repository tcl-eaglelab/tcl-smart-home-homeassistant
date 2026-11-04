# Changelog

## 0.3.3

- Remove inactive lock/text platforms and seven unused model helpers without changing approved controls.
- Add reproducible source/manual packaging and document the current code/security review.
- Record unresolved HA host dependency advisories and vendor authorization requirements.
- Correct current documentation links, historical version notices and HACS discovery claims; add CI lint and Python update checks.


## 0.3.2

- Restore reviewed basic AC, refrigerator, washer and lock settings.
- Add explicit washer/dryer start and pause buttons; reject reported-only run states as commands.
- Re-enable integration-disabled primary controls while preserving user-disabled choices.
- Translate appliance program labels for overseas accounts; keep schema/range checks and engineering restrictions.


## 0.3.1

- Keep every cloud-listed device visible through a connectivity diagnostic entity.
- Add reviewed read-only RF/DW/IWD appliance profiles with explicit setting/delay labels.
- Normalize Celsius and unspecified units; retry missing models after 60 seconds.
- Preserve control restrictions and existing entity IDs.


## 0.3.0 — capability policy and security hardening

Breaking upgrade: configure locally authorized application secrets before replacing the previous component. No application secrets are bundled. See README and the optional local migration helper.

- Reviewed product/schema policy shared by discovery and backend writes; lock read-only; advanced entities disabled by default; preserve safe user choices and disable retired controls without deleting history.
- Strict values, admin-only raw actions, HTTPS-only endpoints, no redirects, safe errors and allowlisted diagnostics.
- Default 30-second polling with a 15-second floor and bounded rate-limit/server/network backoff.
- QR presentation no longer patches global HA prototypes; CI actions pinned; tested-version metadata corrected.
- No claim of all-model support, vendor authorization or full security certification. See docs/SECURITY-0.3.0.md for remaining requirements.

## 0.2.6 - 2026-11-03

- Center and size the QR image consistently, with balanced dialog spacing.
- Present refresh and continue as outlined/filled buttons without navigation arrows, scoped to TCL authorization dialogs and delegated to the existing HA flow.

## 0.2.5 - 2026-11-03

- Replace QR checkboxes with direct native HA buttons for confirmation and refresh, with retryable pending/expired/error states.
- Consolidate regional client transport, QR authorization, errors and token helpers; remove the unused blocking QR loop and dynamic proxy.
- Remove inactive entity translation resources, unused icon mappings, SVG wrapper and helpers; retain route-based capability names.
- Add QR flow regression tests and update setup instructions.

## 0.2.4 - 2026-11-03

- Replace the integration brand with the supplied TCL wordmark, preserving its aspect ratio with transparent padding and standard/high-resolution icon and logo assets.

## 0.2.3 - 2026-11-03

- Fix capability names and custom options to Chinese for domestic accounts and English for overseas accounts, independently of HA locale.
- Fix the polling options flow for current HA versions; preserve the default 3-second refresh and 1–300 second range.

## 0.2.2 - 2026-11-03

- Add English and Simplified Chinese names for door-lock properties and verification/volume options using native Home Assistant translations.

## 0.2.1 - 2026-11-03

- Restore `/tsl/{productKey}/tsl/openclaw` for both domestic and overseas clients as requested.
- Create read-only capabilities even before a status value arrives; expose boolean properties as binary sensors.
- Do not mistake alarm or lock-status settings for a lock control command.

## 0.2.0 - 2026-11-03

- Added five-minute QR validity guidance, a refresh control, and immediate pending/expired/unchecked authorization errors.

- Unified mainland China and overseas account routing under `tcl_smart_home`.
- Added one account-country selection step and automatic QR/API protocol selection.
- Preserved existing domestic config entries; documented the overseas migration path.
- Kept the exposed Thing Model endpoint and English/Chinese resources.


## 0.1.1 - 2026-11-03

- Use the exposed Thing Model endpoint and URL-escape product keys.
- Add explicit English translations, localized property names and enum states, and alphabetically sorted English country labels.

## 0.1.0 - 2026-10-14

- Initial overseas Home Assistant integration.
- Added country/region selection with 249 non-domestic routes.
- Added regional QR authorization and overseas token refresh.
- Added device, status, Thing Model, and HTTP control support.
- Added model-driven entities, diagnostics, tests, HACS metadata, and CI.
