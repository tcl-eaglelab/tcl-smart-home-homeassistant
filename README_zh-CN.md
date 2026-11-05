# TCL Smart Home Home Assistant 统一集成

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![HA Integration](https://img.shields.io/badge/Home%20Assistant-Custom%20Integration-blue.svg)](https://www.home-assistant.io/)
[![Version](https://img.shields.io/badge/version-1.0.0-green.svg)](CHANGELOG.md)
[![在 Home Assistant 中开始配置此集成。](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=tcl_smart_home)

一个同时支持**中国大陆**和**海外** TCL 账号的 Home Assistant 集成。统一域名为 `tcl_smart_home`，根据用户选择的国家自动匹配账号中心、IoT 协议、扫码方式、请求头和时区。

## 支持设备

| 设备 | 可控制 | 只读传感器 |
|---|---|---|
| **空调** | 开关、模式、目标温度、风速、扫风 | 当前温度 |
| **冰箱** | 冷藏/冷冻温度、速冷/速冻、童锁 | 实际温度、门状态 |
| **洗衣机** | 程序、启动/暂停、洗涤温度、脱水转速、漂洗次数 | 运行状态、剩余时间、当前程序 |
| **洗烘一体机** | 上述洗涤控制 + 烘干程序、启动/暂停烘干、烘干程度 | 烘干状态、剩余时间 |
| **门锁** | 电子反锁、语音音量、门铃音量、逗留提醒 | 门状态、电量、锁舌状态 |

能力发现采用**失败即关闭**策略：只有审核过的产品/属性组合才能写入。未识别的属性不会因为云端标记为可写就自动变成控制项。

## 安装

### 前提条件

- Home Assistant ≥ 2026.9.4
- 已注册设备的 TCL 账号（国内或海外）
- 通过授权渠道获取的 TCL 应用凭据

### 第一步：配置凭据

安装包**不含应用密钥**。安装前在 HA 配置中设置：

`configuration.yaml`：
```yaml
tcl_smart_home:
  domestic_app_secret: !secret tcl_ha_domestic_app_secret
  overseas_client_secret: !secret tcl_ha_overseas_client_secret
```

`secrets.yaml`：
```yaml
tcl_ha_domestic_app_secret: "你的国内应用密钥"
tcl_ha_overseas_client_secret: "你的海外应用密钥"
```

只使用一条区域路线时可只配置对应键。不要将 `secrets.yaml` 或备份上传 GitHub。

### 第二步：安装集成

**通过 HACS**（仓库公开后推荐）：

1. 将本仓库添加为 HACS 自定义 Integration 仓库。
2. 在 HACS 中搜索 "TCL Smart Home" 并安装。
3. 重启 Home Assistant。

**手动安装**：

1. 将 `custom_components/tcl_smart_home/` 目录复制到 HA 的 `custom_components/` 下。
2. 重启 Home Assistant。

### 第三步：添加 TCL 账号

1. 打开 **设置 → 设备与服务 → 添加集成 → TCL Smart Home**。
2. 选择 **TCL 账号注册所在的国家**（如 Mainland China [CN]、Germany [DE]）。
3. 插件自动选择对应的账号中心、扫码协议、IoT 网关和时区。
4. 使用 TCL App 扫描二维码并确认授权，点击 **我已扫码，继续**。
5. 插件自动发现设备并创建审核过的能力实体。

> 选择的是 **TCL 账号所属国家**，不是 HA 所在国家或界面语言。如需管理多个 TCL 账号，按不同国家重复添加。

## 路由

| 选择 | 账号中心 | IoT 网关 | 扫码协议 |
| --- | --- | --- | --- |
| Mainland China [CN] | `cn.account.tcl.com` | `io.zx.tcljd.com` | 国内扫码接口 |
| 海外国家 | 按国家映射的账号中心 | 区域网关 | 海外扫码接口 |

海外国家按内置国家表（249 个国家）映射到 SG、FR、US 或 BR 服务区域。用户选择实际国家，不选择服务区域。

## 功能

- **统一集成**：国内和海外扫码授权在同一个域名下
- **按国家路由**：每个国家一个配置条目，自动选择协议
- **物模型驱动**：设备发现、状态轮询、物模型发现、基于能力的实体创建
- **审核控制**：climate、binary_sensor、sensor、switch、number、select、button 实体，均经产品/属性审核
- **双语**：国内中文、海外英文，独立于 HA 语言设置
- **安全加固**：强制 TLS、拒绝重定向、域名白名单、诊断脱敏、管理员原始服务、有界限流
- **轮询**：默认 30 秒，可调 15–300 秒，429/5xx/连接失败时有界退避

## 轮询

默认轮询间隔 **30 秒**，可在 **设置 → 设备与服务 → TCL Smart Home → 配置** 中修改，范围 15–300 秒。物模型缓存 15 分钟。修改间隔后自动重载集成。

## 安全

- **不含密钥**：应用凭据仅从本机 YAML 读取
- **强制 TLS**：所有请求使用 HTTPS 并校验证书，拒绝重定向
- **域名白名单**：仅连接已知 TCL 端点
- **写入校验**：产品+属性结构匹配，类型/范围/步长/枚举校验后才发命令
- **管理员限制**：`set_property` 原始服务需用户上下文和管理员权限
- **诊断脱敏**：仅导出结构计数和布尔状态
- **无远程开门**：门锁仅开放设置，`openDoor` 未接入

详见[安全策略](SECURITY.md)。

## 动作

`tcl_smart_home.set_property` 写入一个已审核属性。调用必须带用户身份，并且是管理员。自动化应使用实体自己的动作。

| 字段 | 必填 | 含义 |
| --- | --- | --- |
| `device_id` | 是 | TCL `deviceId` |
| `property` | 是 | 已审核的属性标识。工程属性和开锁指令会被拒绝 |
| `value` | 是 | 布尔用 `0` 或 `1`，范围用数字，枚举用选项代码 |

## 移除

1. 打开 **设置 → 设备与服务 → TCL Smart Home**，删除该集成条目。
2. 从 `configuration.yaml` 去掉 `tcl_smart_home` 配置，并从 `secrets.yaml` 去掉对应密钥。
3. 手动安装的，删除 `custom_components/tcl_smart_home`。
4. Home Assistant 提示重启时再重启。已经加载过的集成，更新或删除后需要重启。

## 文档

- [架构](docs/ARCHITECTURE.md)
- [更新日志](CHANGELOG.md)
- [贡献说明](CONTRIBUTING.md)

## 许可

MIT。详见 [LICENSE](LICENSE)。

## 免责声明

本插件是自定义集成，不是 Home Assistant 官方内置集成，也不代表安全认证。TCL 及 TCL logo 为 TCL 商标——公开发布前请核实品牌和 API 使用条款。
