# 0.3.0 能力分级清单

> 历史版本记录。当前能力见 [基础控制说明](CONTROLS-0.3.2.md)，当前安全结论见 [0.3.3 审查](AUDIT-0.3.3.md)。

产品型号规则保存在 `custom_components/tcl_smart_home/capability_profiles.json`。该文件仅包含产品协议元数据，没有账户设备 ID、状态或凭据。新增产品必须核对物模型语义和 schema 后补规则/测试；未知字段默认不创建控制。

| 产品模型 | 核心属性数（含组合实体成员） | 高级属性数 | 诊断属性数 | 写入属性数 |
|---|---:|---:|---:|---:|
| 1: air_conditioner | 9 | 10 | 2 | 14 |
| 2: lock | 3 | 0 | 1 | 0 |
| 3: air_conditioner | 9 | 11 | 2 | 16 |

上述是属性计数，不是最终卡片数量。空调电源/模式/目标温度及支持的档位风速合并到 climate；百分比风速、自动风、上下/左右扫风按能力单独提供。屏显/提示音/睡眠/ECO/导风位置等可选，未列入的自清洁启动等功能暂不开放。

门锁：门状态、锂电池与干电池电量默认启用；故障码为默认禁用的诊断实体。没有根据 mainLockStatus/reverseLockStatus 猜测锁定状态，不创建 lock 控制实体。

冰箱：未审核型号只读识别 fridgeTemperature/refrigeratorTemperature/freezerTemperature，要求数值型及摄氏单位。洗衣机：只读识别 remainingTime/remainTime（明确秒/分钟单位）、runStatus/workStatus/currentProgram（枚举）。这些是保守兼容规则，不是已完成真实型号测试。

高级功能：HA 设置 → 设备与服务 → 实体，按本集成及已禁用状态筛选，按需启用。已经启用的安全高级实体不会在升级时被强制关闭。工程/未审核/重复实体会被停用；不删除注册记录和历史；通知用户检查自动化。

国内能力名称与选项继续中文、海外英文；HA 系统与标准 climate 文案仍由 HA 用户语言决定。没有新增通过脚本重排设备控制页面的逻辑。
