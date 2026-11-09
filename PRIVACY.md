# 隐私说明

本说明描述 Home Assistant 自定义集成 TCL Smart Home（域 `tcl_smart_home`，版本 1.0.0）如何处理个人信息。安装者在选择国家并扫码授权前，应先阅读本说明。

## 处理哪些个人信息

扫码授权成功后，集成把以下字段写入 Home Assistant 配置项：

- `access_token`：访问令牌，格式为 JWT。集成读取其中的 `exp` 计算过期时间，并在门锁类型查询时读取 `sub` 作为 IoT 用户标识。
- `refresh_token`：用于向所选区域的账号中心换取新的访问令牌。
- `token_expires`：访问令牌过期时间，单位为毫秒。
- `country_code`：用户选择的账号国家或地区代码。
- `verify_ssl`：配置项中记录为 `true`。当前版本的请求始终校验证书，不提供关闭校验的选项。

中国大陆使用的 `domestic_app_secret` 随本仓库公开内置，与已发布的 TCL Smart Home CLI 使用同一把公开客户端凭据。`configuration.yaml` 里若配置了同名项，以配置为准。海外 `overseas_client_secret` 仍由用户写入 Home Assistant `secrets.yaml`，仓库不内置。

集成从所选区域的云端拉取设备信息，并在 Home Assistant 中显示为设备和实体状态。这些信息包括设备列表、在线状态、物模型属性，以及用户发出的控制指令。已审核能力覆盖空调、冰箱、洗衣机和门锁的相应属性。设备名称和设备标识会进入 Home Assistant 设备注册表，属性值进入实体状态。

配置过程中的扫码内容只保存在当次配置流程的内存中，不写入配置项。

诊断导出不包含令牌、账号标识、设备标识或云端响应正文。它只包含 `loaded`、`update_success`、`poll_interval_seconds`，以及每台设备的 `status_ok`、`status_failures`、`property_counts`。见 `custom_components/tcl_smart_home/diagnostics.py`。

## 存在哪里

- Home Assistant 配置项，位于用户 Home Assistant 的 `.storage`。
- 国内公开客户端凭据在集成源码中。海外应用密钥在 `secrets.yaml`，位于用户 Home Assistant 配置目录。国内密钥也可被 `configuration.yaml` 覆盖。
- 集成进程内存。令牌刷新后，`coordinator.py` 把新的 `access_token`、`refresh_token` 和 `token_expires` 写回同一个配置项。
- 所选国家对应的账号中心和 IoT 接口。控制指令发往该区域的 IoT 接口。

## 保留多久

- 本地配置项保留到用户在 Home Assistant 中删除该集成条目。
- 扫码二维码在客户端的有效期为 300 秒，见 `const.py` 的 `QR_VALIDITY_SECONDS`。超过后需要重新获取二维码。
- 云端账号、令牌和设备数据的保留期限没有写在本集成代码中。该期限以账号中心和 IoT 服务的实际策略为准，此处留待服务方填写，不记载具体天数。

## 如何删除

1. 在 Home Assistant 中打开 **设置 → 设备与服务 → TCL Smart Home**，删除该集成条目。本地配置项随之删除。
2. 从 `secrets.yaml` 删除对应的 `domestic_app_secret` 或 `overseas_client_secret`。
3. 手动安装时，删除 `custom_components/tcl_smart_home`。Home Assistant 要求重启时再重启。

删除本地集成不会吊销云端会话。当前客户端没有调用云端吊销接口。当前不能在账号侧单独吊销该客户端。

## 区域选择会把数据送到哪里

国家选择不让用户手填服务器。`routing.py` 按该国家在 `country_regions.csv` 中的 `sso_region` 选择账号中心和 IoT 主机：

| 区域 | 账号中心 | IoT 接口 |
| --- | --- | --- |
| CN | `https://cn.account.tcl.com` | `https://io.zx.tcljd.com` |
| SG | `https://sg.account.tcl.com` | `https://sgp-iot-api-prod.tcljd.com` |
| FR | `https://pa.account.tcl.com` | `https://eu-iot-api-prod.tcljd.com` |
| US | `https://us.account.tcl.com` | `https://us-iot-api-prod.tcljd.com` |
| BR | `https://br.account.tcl.com` | `https://br-iot-api-prod.tcljd.com` |

中国大陆使用 CN。其他国家按表中的区域归入 SG、FR、US 或 BR。授权、设备列表、状态查询和控制指令都发往这一组主机。

## 诊断和公开求助

从集成页面下载的诊断只含计数字段和布尔状态。一份已加载时的样例如下：

```json
{
  "loaded": true,
  "update_success": true,
  "poll_interval_seconds": 30.0,
  "devices": [
    {
      "status_ok": true,
      "status_failures": 0,
      "property_counts": {
        "primary": 4,
        "advanced": 2,
        "diagnostic": 1,
        "blocked": 3
      }
    }
  ]
}
```

集成尚未加载时，诊断为 `{"loaded": false}`。

公开问题使用 `.github/ISSUE_TEMPLATE/bug_report.yml`。模板已要求不要附上二维码、access token、refresh token、密码和 `.storage` 文件。粘贴诊断前请自行确认其中没有个人数据。

## 遥测

本集成没有另行上报的遥测客户端。以后如果增加上报，先改这份说明再发布。
