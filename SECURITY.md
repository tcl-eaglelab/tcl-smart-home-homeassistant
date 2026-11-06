# Security policy

Version 1.0.0 reads application credentials from local Home Assistant configuration. It restricts controls to reviewed product/schema profiles, validates writes, makes raw property actions administrator-only with a required user context, forces TLS verification, rejects redirects, and exports only allowlisted structural diagnostics.

Before any public release, confirm the vendor API, client-credential, license, and brand terms, and enable a private vulnerability-reporting channel. This repository does not claim vendor authorization, official Home Assistant acceptance, or that all vulnerabilities have been eliminated.

Do not post QR challenges, tokens, passwords, application secrets, device keys, Home Assistant configuration, or backups in public issues. Share only reviewed diagnostic reports.

漏洞请通过 TCL SRC 平台报告：https://src.tcl.com 。解决时限为：严重（S）15 个工作日，高危（A）90 个工作日，中危（B）90 个工作日，低危（C）180 个工作日。报告中不要附带二维码、令牌、密码、应用密钥、设备密钥和 Home Assistant 的 .storage 备份。

Credentials reside in local Home Assistant storage. 用户的 access_token 和 refresh_token 保存在 Home Assistant 配置项中，路径为 `.storage/core.config_entries`。应用密钥在 `secrets.yaml`，不在上述配置项里。拷走已安装实例的 Home Assistant 配置目录、`.storage` 或整机备份，会把 access_token 和 refresh_token 一起带走。持有该副本的人可以继续控制对应账号下的设备。只拷贝仓库或 `custom_components/tcl_smart_home` 源码，不会带走用户令牌。Deleting an integration entry does not prove the cloud token was revoked.

This package does not patch Home Assistant's own Python libraries. Do not describe it as a security certification or as regulatory compliance.
