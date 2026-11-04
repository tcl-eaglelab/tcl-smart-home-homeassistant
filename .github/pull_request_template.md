## Summary

<!-- Describe the user-visible change. -->

## Testing

- [ ] `python -m pip install -r requirements-test.txt`
- [ ] `python -m compileall -q custom_components`
- [ ] `python -m pytest -q`
- [ ] `black --check custom_components tests`
- [ ] Home Assistant config check or equivalent runtime validation

## Security

- [ ] No access token, refresh token, QR code, password, or device master key is included.
