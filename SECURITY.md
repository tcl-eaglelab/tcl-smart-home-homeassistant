# Security policy

The current release excludes embedded application secrets, restricts controls to reviewed product/schema profiles, validates writes, makes raw property actions administrator-only with a required user context, forces TLS verification, rejects redirects, and exports only allowlisted structural diagnostics.

Before any public release, confirm the vendor API/client-credential/license/brand terms, rotate previously exposed confidential credentials as applicable, and enable a private vulnerability-reporting channel. This repository does not claim vendor authorization, official HA acceptance or that all vulnerabilities have been eliminated.

Do not post QR challenges, tokens, passwords, application secrets, device keys, HA configuration or backups in public issues. Share only reviewed diagnostic reports. Credentials reside in local HA storage/secrets; protect host access and backups. Deleting an entry does not prove cloud token revocation.

See [the 0.3.3 security audit](docs/AUDIT-0.3.3.md) for current evidence and unresolved risks. The inspected HA 2026.9.4 environment has dependency advisories; this package does not patch the host. Do not claim complete security or regulatory compliance. Older 0.2.x archives retain embedded credentials and known flaws and should not be used for new public distribution.
