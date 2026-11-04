# Contributing

## Before opening an issue

- Confirm the issue still occurs after restarting Home Assistant.
- Include the selected country/region and TCL routing region.
- Remove credentials, QR codes, tokens, and personal device identifiers.
- Include Home Assistant and integration versions.
- Attach redacted diagnostics when possible.

## Development checks

```powershell
python -m pip install -r requirements-test.txt
python -m compileall custom_components
python -m pytest -q
black --check custom_components tests
```

When Docker and Home Assistant are available, also run the Home Assistant
configuration check and the HACS/hassfest validation used by CI.

Changes to country routing, QR authorization, or the API client should include
focused tests for the affected regional protocol.

## Pull requests

- Keep changes focused.
- Do not commit Home Assistant `.storage` files or access tokens.
- Update `README.md` and `CHANGELOG.md` for user-visible changes.
- Explain how the change was tested.
- Do not include QR images, tokens, device master keys, or unredacted logs.
