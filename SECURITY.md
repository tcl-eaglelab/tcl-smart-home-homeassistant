# Security policy

Version 1.0.0 reads application credentials from local Home Assistant configuration. It restricts controls to reviewed product/schema profiles, validates writes, makes raw property actions administrator-only with a required user context, forces TLS verification, rejects redirects, and exports only allowlisted structural diagnostics.

Before any public release, confirm the vendor API, client-credential, license, and brand terms, and enable a private vulnerability-reporting channel. This repository does not claim vendor authorization, official Home Assistant acceptance, or that all vulnerabilities have been eliminated.

Do not post QR challenges, tokens, passwords, application secrets, device keys, Home Assistant configuration, or backups in public issues. Share only reviewed diagnostic reports. Credentials reside in local Home Assistant storage. Deleting an integration entry does not prove the cloud token was revoked.

This package does not patch Home Assistant's own Python libraries. Do not describe it as a security certification or as regulatory compliance.
