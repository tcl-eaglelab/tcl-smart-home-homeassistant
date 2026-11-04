# Architecture

Country routes choose the domestic or overseas API. Both clients share TLS-only fixed-origin transport, disabled redirects, safe error handling and bounded cooldowns. Credentials are supplied by local HA YAML; user tokens remain in config entries.

The coordinator fetches device lists/status/models. Discovery and writes share capabilities.py and reviewed capability_profiles.json. Schema changes fail closed. Entity platforms are projections of admitted capabilities, not a blanket rendering of cloud writability. Composite climate roles use explicit mappings; lock/text controls are not exposed. Backend validation cannot be bypassed by a hidden entity or raw service call.

Raw property actions require an administrator user context; normal platform actions rely on HA entity permissions. Migration disables retired registry entries without deleting history and preserves safe existing user settings. Diagnostic output is structural and allowlisted.

The QR script observes dialog DOM and delegates to native flow handlers without replacing prototypes. This remains a custom-integration compatibility layer. Official Core work still requires an external SDK, native tests and an accepted UI approach.
