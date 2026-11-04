from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any


def model_properties(model: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(model, Mapping):
        return []
    properties = model.get("properties", [])
    if not isinstance(properties, list):
        return []
    return [
        dict(item)
        for item in properties
        if isinstance(item, Mapping) and property_identifier(item)
    ]


def property_identifier(prop: Mapping[str, Any]) -> str:
    return str(prop.get("identifier") or "")


def property_name(prop: Mapping[str, Any], language: str = "en") -> str:
    if language == "zh-Hans":
        for field in ("name", "desc"):
            label = prop.get(field)
            if isinstance(label, str) and re.search(r"[\u3400-\u9fff]", label):
                return label.strip()
    key = property_translation_key(prop)
    label = ROUTE_PROPERTY_NAMES.get(language, {}).get(key)
    if label:
        return label
    if language == "zh-Hans":
        return "未命名功能"
    # Cloud TSL labels may be Chinese even when the API language is English.
    for field in ("name", "desc"):
        label = prop.get(field)
        if isinstance(label, str) and label.strip() and label.isascii():
            return label.strip()
    identifier = property_identifier(prop)
    words = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", identifier)
    words = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", words)
    words = re.sub(r"[_\-]+", " ", words).strip()
    return words[:1].upper() + words[1:] if words and words.isascii() else "Property"


def property_type(prop: Mapping[str, Any]) -> str:
    data_type = prop.get("dataType")
    if isinstance(data_type, Mapping):
        return str(data_type.get("type") or "").lower()
    return str(prop.get("type") or "").lower()


def property_specs(prop: Mapping[str, Any]) -> Any:
    data_type = prop.get("dataType")
    if isinstance(data_type, Mapping):
        return data_type.get("specs")
    return prop.get("specs")


def is_writable(prop: Mapping[str, Any]) -> bool:
    access_mode = str(prop.get("accessMode") or prop.get("access_mode") or "").lower()
    return "w" in access_mode


def find_property(
    properties: list[Mapping[str, Any]],
    *identifiers: str,
    contains: tuple[str, ...] = (),
    writable: bool | None = None,
) -> dict[str, Any] | None:
    exact = {value.lower() for value in identifiers}
    for prop in properties:
        identifier = property_identifier(prop)
        if writable is not None and is_writable(prop) != writable:
            continue
        if identifier.lower() in exact:
            return dict(prop)
    for prop in properties:
        identifier = property_identifier(prop).lower()
        if writable is not None and is_writable(prop) != writable:
            continue
        if any(part.lower() in identifier for part in contains):
            return dict(prop)
    return None


def device_category(device: Mapping[str, Any]) -> str:
    values = (
        device.get("category"),
        device.get("type"),
        device.get("deviceType"),
        device.get("productName"),
    )
    return " ".join(str(value or "").lower() for value in values)


def _category_tokens(category: str) -> set[str]:
    return {token for token in re.split(r"[\s/_-]+", category.lower()) if token}


def is_refrigerator(device: Mapping[str, Any]) -> bool:
    category = device_category(device)
    return "rf" in _category_tokens(category) or any(
        value in category for value in ("refrigerator", "fridge", "\u51b0\u7bb1")
    )


def is_washing_machine(device: Mapping[str, Any]) -> bool:
    category = device_category(device)
    return bool({"dw", "iwd"} & _category_tokens(category)) or any(
        value in category for value in ("washing", "washer", "\u6d17\u8863\u673a")
    )


def is_enum_type(prop: Mapping[str, Any]) -> bool:
    return property_type(prop) in ("enum", "enumeration")


def model_fingerprint(model: Mapping[str, Any] | None) -> str:
    """Return a stable fingerprint for the entity-relevant part of a TSL model."""
    if not isinstance(model, Mapping):
        return ""
    properties = []
    for prop in model_properties(model):
        data_type = prop.get("dataType")
        properties.append(
            {
                "identifier": property_identifier(prop),
                "accessMode": prop.get("accessMode") or prop.get("access_mode"),
                "type": property_type(prop),
                "specs": (
                    data_type.get("specs")
                    if isinstance(data_type, Mapping)
                    else prop.get("specs")
                ),
            }
        )
    payload = {
        "productKey": model.get("productKey"),
        "tslVersion": model.get("tslVersion") or model.get("version"),
        "properties": sorted(properties, key=lambda item: item["identifier"]),
    }
    encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def property_icon(prop: Mapping[str, Any]) -> str | None:
    """Return a useful icon for common TCL property identifiers."""
    identifier = property_identifier(prop).lower()
    if "temperature" in identifier:
        return "mdi:thermometer"
    if "humidity" in identifier:
        return "mdi:water-percent"
    if "battery" in identifier:
        return "mdi:battery"
    if "fan" in identifier or "wind" in identifier:
        return "mdi:fan"
    if "power" in identifier:
        return "mdi:power"
    if "lock" in identifier:
        return "mdi:lock"
    if "door" in identifier:
        return "mdi:door"
    if "light" in identifier or "lamp" in identifier:
        return "mdi:lightbulb"
    return None


PROPERTY_TRANSLATION_KEYS = {
    "cuser": "p2p_users",
    "max": "maximum_online_users",
    "micuserid": "microphone_user_id",
    "micenable": "microphone",
    "iotp2p": "p2p_support",
    "p2pdatachannelstate": "p2p_data_channel",
    "autolockalarm": "auto_lock_alarm",
    "powersavemode": "power_save_mode",
    "keepalivestatus": "keep_alive_status",
    "onlinenumber": "online_connections",
    "alwaysopenenable": "always_open",
    "voicevolume": "voice_volume",
    "tamperenable": "tamper_alarm",
    "wifikeepaliveswitch": "wifi_keep_alive",
    "volume": "volume",
    "stayalarmswitch": "loitering_alert",
    "mutiopenmethod": "unlock_verification_mode",
    "stayalarmlevel": "loitering_alert_delay",
    "mainlockstatus": "main_bolt_state",
    "pir": "motion_detection",
    "reverselockstatus": "deadbolt_state",
    "lithiumbatterycapacity": "lithium_battery",
    "securitymode": "security_mode",
    "drybatterycapacity": "dry_battery",
    "electroniclock": "electronic_deadlock",
    "insidedoorswitch": "inside_button",
    "facerecognitionmode": "face_recognition_mode",
    "videoparam": "video_parameters",
    "audioparam": "audio_parameters",
    "power": "power",
    "powerswitch": "power",
    "switch": "power",
    "targettemperature": "target_temperature",
    "settemperature": "target_temperature",
    "currenttemperature": "current_temperature",
    "indoortemperature": "indoor_temperature",
    "outdoortemperature": "outdoor_temperature",
    "temperature": "temperature",
    "humidity": "humidity",
    "currenthumidity": "humidity",
    "targethumidity": "target_humidity",
    "sethumidity": "target_humidity",
    "battery": "battery",
    "batterylevel": "battery",
    "workmode": "work_mode",
    "operationmode": "work_mode",
    "mode": "work_mode",
    "fanspeed": "fan_speed",
    "fanmode": "fan_speed",
    "windspeed": "fan_speed",
    "childlock": "child_lock",
    "lockstate": "lock_state",
    "lockstatus": "lock_state",
    "lockswitch": "lock_state",
    "doorlock": "lock_state",
    "doorstate": "door_state",
    "doorstatus": "door_state",
    "sleep": "sleep",
    "sleepmode": "sleep",
    "sleepswitch": "sleep",
    "eco": "eco",
    "ecomode": "eco",
    "light": "light",
    "lightswitch": "light",
    "display": "display",
    "displayswitch": "display",
    "screenswitch": "display",
    "swing": "swing",
    "swingmode": "swing",
    "verticalswing": "vertical_swing",
    "updownswing": "vertical_swing",
    "horizontalswing": "horizontal_swing",
    "leftrightswing": "horizontal_swing",
    "fridgetemperature": "fridge_temperature",
    "refrigeratortemperature": "fridge_temperature",
    "freezertemperature": "freezer_temperature",
    "remainingtime": "remaining_time",
    "remaintime": "remaining_time",
    "runstatus": "running_status",
    "workstatus": "running_status",
    "currentprogram": "current_program",
    "errorcode": "error_code",
    "faultcode": "error_code",
}


def property_translation_key(prop: Mapping[str, Any]) -> str | None:
    """Use exact matches so target/current temperatures keep distinct names."""
    return PROPERTY_TRANSLATION_KEYS.get(property_identifier(prop).lower())


def enum_options(prop: Mapping[str, Any]) -> list[tuple[Any, str]]:
    specs = property_specs(prop)
    values: list[tuple[Any, str]] = []
    if isinstance(specs, Mapping):
        raw_values = specs.get("values") or specs.get("options") or specs
        if isinstance(raw_values, list):
            specs = raw_values
        elif isinstance(raw_values, Mapping):
            for raw, label in raw_values.items():
                values.append((raw, str(label)))
            return values
    if isinstance(specs, list):
        for item in specs:
            if isinstance(item, Mapping):
                raw = item.get("value", item.get("code", item.get("id")))
                label = item.get("name", item.get("label", item.get("desc", raw)))
                if raw is not None:
                    values.append((raw, str(label)))
            else:
                values.append((item, str(item)))
    return values


def numeric_spec(prop: Mapping[str, Any], key: str, default: float) -> float:
    specs = property_specs(prop)
    if isinstance(specs, Mapping):
        value = specs.get(key)
        try:
            return float(value)
        except (TypeError, ValueError):
            pass
    return default


def spec_unit(prop: Mapping[str, Any]) -> str | None:
    specs = property_specs(prop)
    if isinstance(specs, Mapping):
        unit = specs.get("unit") or specs.get("unitName")
        if not unit or str(unit).strip().lower() in {"na", "n/a"}:
            return None
        return "°C" if unit == "℃" else str(unit)
    return None


def as_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in ("1", "true", "on", "yes", "open", "locked"):
            return True
        if normalized in ("0", "false", "off", "no", "closed", "unlocked"):
            return False
    return None


def display_state(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if isinstance(value, bool):
        return "on" if value else "off"
    return value


def mode_label_to_hvac(label: str) -> str | None:
    normalized = label.lower()
    if any(value in normalized for value in ("off", "\u5173\u95ed", "\u5173\u673a")):
        return "off"
    if any(value in normalized for value in ("auto", "\u81ea\u52a8")):
        return "auto"
    if any(value in normalized for value in ("cool", "\u5236\u51b7")):
        return "cool"
    if any(value in normalized for value in ("heat", "\u5236\u70ed")):
        return "heat"
    if any(value in normalized for value in ("dry", "\u9664\u6e7f", "\u62bd\u6e7f")):
        return "dry"
    if any(value in normalized for value in ("fan", "\u9001\u98ce", "\u901a\u98ce")):
        return "fan_only"
    return None


ENUM_LABEL_KEYS = {
    "低音量": "low_volume",
    "中音量": "medium_volume",
    "高音量": "high_volume",
    "静音音量": "muted_volume",
    "单开模式": "single_verification",
    "双指纹模式": "two_fingerprints",
    "指纹密码模式": "fingerprint_password",
    "指纹门卡模式": "fingerprint_card",
    "人脸密码模式": "face_password",
    "auto": "auto",
    "自动": "auto",
    "自动模式": "auto",
    "automatic": "auto",
    "cool": "cool",
    "制冷": "cool",
    "制冷模式": "cool",
    "cooling": "cool",
    "heat": "heat",
    "制热": "heat",
    "制热模式": "heat",
    "heating": "heat",
    "dry": "dry",
    "除湿": "dry",
    "抽湿": "dry",
    "除湿模式": "dry",
    "fan_only": "fan_only",
    "fan only": "fan_only",
    "送风": "fan_only",
    "通风": "fan_only",
    "fan": "fan_only",
    "low": "low",
    "低": "low",
    "低风": "low",
    "低速": "low",
    "低档": "low",
    "medium": "medium",
    "中": "medium",
    "中风": "medium",
    "中速": "medium",
    "中档": "medium",
    "mid": "medium",
    "high": "high",
    "高": "high",
    "高风": "high",
    "高速": "high",
    "高档": "high",
    "quiet": "quiet",
    "静音": "quiet",
    "静音模式": "quiet",
    "silent": "quiet",
    "turbo": "turbo",
    "强劲": "turbo",
    "强力": "turbo",
    "强劲模式": "turbo",
    "sleep": "sleep",
    "睡眠": "sleep",
    "睡眠模式": "sleep",
    "eco": "eco",
    "节能": "eco",
    "节能模式": "eco",
    "on": "on",
    "开": "on",
    "开启": "on",
    "打开": "on",
    "开机": "on",
    "off": "off",
    "关": "off",
    "关闭": "off",
    "关机": "off",
    "open": "open",
    "closed": "closed",
    "已关闭": "closed",
    "locked": "locked",
    "已锁定": "locked",
    "已上锁": "locked",
    "上锁": "locked",
    "unlocked": "unlocked",
    "已解锁": "unlocked",
    "解锁": "unlocked",
}


APPLIANCE_OPTION_NAMES = {
    "待机": "Standby",
    "暂停": "Paused",
    "运行": "Running",
    "完成": "Completed",
    "冷水": "Cold water",
    "常温": "Ambient",
    "不脱水": "No spin",
    "免脱": "No spin",
    "混合": "Mixed",
    "快洗": "Quick wash",
    "快洗15'": "Quick wash 15 min",
    "快洗15'/30'": "Quick wash 15/30 min",
    "快洗烘60": "Wash and dry 60 min",
    "洗烘60'": "Wash and dry 60 min",
    "洗烘60′": "Wash and dry 60 min",
    "羊毛": "Wool",
    "大件": "Bulky items",
    "真丝": "Silk",
    "热力除菌": "Heat sanitizing",
    "单脱水": "Spin only",
    "单脱": "Spin only",
    "漂+脱": "Rinse and spin",
    "高温洁筒": "Hot drum clean",
    "筒清洁": "Drum clean",
    "筒洗烘": "Drum wash and dry",
    "羽绒服": "Down jackets",
    "羽绒": "Down",
    "棉织物": "Cotton",
    "棉麻": "Cotton and linen",
    "运动服": "Sportswear",
    "衬衣": "Shirts",
    "衬衫": "Shirts",
    "内衣": "Underwear",
    "巴氏除菌": "Pasteurization",
    "除菌螨": "Sanitize and mite removal",
    "童装": "Children's clothes",
    "护色": "Color care",
    "冲锋衣": "Outdoor jackets",
    "AI智慧洗": "AI wash",
    "毛绒玩具": "Soft toys",
    "蓝心日常洗": "Lanxin daily wash",
    "蓝心激烈强洗": "Lanxin intensive wash",
    "快烘": "Quick dry",
    "婴儿服": "Baby clothes",
    "热风清新": "Warm air refresh",
    "毛巾": "Towels",
    "冷风护理": "Cool air care",
    "家纺": "Household textiles",
    "轻柔": "Delicates",
    "化纤": "Synthetics",
    "牛仔": "Denim",
    "AI智慧烘": "AI dry",
    "支架烘": "Rack dry",
    "户外服": "Outdoor clothes",
    "除毛烘": "Hair removal dry",
    "暖衣": "Warm clothes",
    "晒被子": "Bedding refresh",
    "蓝心柔烘": "Lanxin gentle dry",
    "蓝心除菌": "Lanxin sanitizing",
    "储藏": "Cupboard dry",
    "即穿": "Ready to wear",
    "熨烫": "Iron dry",
    "单烘干": "Dry only",
    "消毒洗": "Sanitizing wash",
    "空气洗": "Air refresh",
    "超净": "Intensive",
    "超净洗": "Intensive wash",
}


def enum_display_options(
    prop: Mapping[str, Any], language: str = "en"
) -> list[tuple[Any, str]]:
    """Localize display labels without changing a control value or its type.

    Labels follow the account route. Unknown English labels are preserved for
    overseas accounts; untranslated labels fall back to their code.
    Keep every option distinct even when cloud labels or translations collide.
    """
    result: list[tuple[Any, str]] = []
    used: set[str] = set()
    for index, (raw, label) in enumerate(enum_options(prop), start=1):
        label = label.strip()
        display = ENUM_LABEL_KEYS.get(label.casefold())
        if display is not None:
            display = ROUTE_OPTION_NAMES[language].get(display)
        if language == "en" and display is None:
            display = APPLIANCE_OPTION_NAMES.get(label)
            if re.fullmatch(r"\d+(?:℃|°C)", label):
                display = label.replace("℃", " C").replace("°C", " C")
        if language == "zh-Hans" and re.search(r"[\u3400-\u9fff]", label):
            display = label
        if display is None:
            code = str(raw)
            if language == "zh-Hans":
                display = (
                    label
                    if re.fullmatch(r"[\d .%°+-]+|\d+[pP]", label)
                    else f"选项 {code if code.isdecimal() else index}"
                )
            else:
                display = (
                    label
                    if label and label.isascii()
                    else (f"Value {code}" if code.isascii() else f"Option {index}")
                )
        base = display
        suffix = 2
        while display in used:
            display = f"{base} ({suffix})"
            suffix += 1
        used.add(display)
        result.append((raw, display))
    return result


# Route-specific labels are explicit so HA locale cannot change capabilities.
ROUTE_PROPERTY_NAMES = {
    "en": {
        "fridge_temperature": "Fridge temperature",
        "freezer_temperature": "Freezer temperature",
        "remaining_time": "Remaining time",
        "running_status": "Running status",
        "current_program": "Current program",
        "always_open": "Always open",
        "audio_parameters": "Audio parameters",
        "auto_lock_alarm": "Lock timeout alarm",
        "battery": "Battery",
        "child_lock": "Child lock",
        "current_temperature": "Current temperature",
        "deadbolt_state": "Deadbolt state",
        "display": "Display",
        "door_state": "Door state",
        "dry_battery": "Dry-cell battery level",
        "eco": "Eco mode",
        "electronic_deadlock": "Electronic deadlock",
        "error_code": "Error code",
        "face_recognition_mode": "Face recognition mode",
        "fan_speed": "Fan speed",
        "horizontal_swing": "Horizontal swing",
        "humidity": "Humidity",
        "indoor_temperature": "Indoor temperature",
        "inside_button": "Inside door button",
        "keep_alive_status": "Keep-alive state",
        "light": "Light",
        "lithium_battery": "Lithium battery level",
        "lock_state": "Lock state",
        "loitering_alert": "Loitering alert",
        "loitering_alert_delay": "Loitering alert delay",
        "main_bolt_state": "Main bolt state",
        "maximum_online_users": "Maximum online users",
        "microphone": "Microphone",
        "microphone_user_id": "Microphone user ID",
        "motion_detection": "Motion detection",
        "online_connections": "Live stream connections",
        "outdoor_temperature": "Outdoor temperature",
        "p2p_data_channel": "P2P data channel",
        "p2p_support": "P2P support",
        "p2p_users": "P2P users",
        "power": "Power",
        "power_save_mode": "Power saving mode",
        "security_mode": "Security mode",
        "sleep": "Sleep",
        "swing": "Swing",
        "tamper_alarm": "Tamper alarm",
        "target_humidity": "Target humidity",
        "target_temperature": "Target temperature",
        "temperature": "Temperature",
        "unlock_verification_mode": "Unlock verification mode",
        "vertical_swing": "Vertical swing",
        "video_parameters": "Video parameters",
        "voice_volume": "Voice volume",
        "volume": "Volume",
        "wifi_keep_alive": "Wi-Fi keep-alive",
        "work_mode": "Operating mode",
    },
    "zh-Hans": {
        "fridge_temperature": "冷藏温度",
        "freezer_temperature": "冷冻温度",
        "remaining_time": "剩余时间",
        "running_status": "运行状态",
        "current_program": "当前程序",
        "always_open": "常开模式",
        "audio_parameters": "音频参数",
        "auto_lock_alarm": "超时上锁报警设置",
        "battery": "电量",
        "child_lock": "童锁",
        "current_temperature": "当前温度",
        "deadbolt_state": "反锁舌状态",
        "display": "显示屏",
        "door_state": "门状态",
        "dry_battery": "干电池电量",
        "eco": "节能模式",
        "electronic_deadlock": "电子反锁",
        "error_code": "故障代码",
        "face_recognition_mode": "人脸识别模式",
        "fan_speed": "风速",
        "horizontal_swing": "左右扫风",
        "humidity": "湿度",
        "indoor_temperature": "室内温度",
        "inside_button": "门内按键开关",
        "keep_alive_status": "保活状态",
        "light": "灯光",
        "lithium_battery": "锂电池电量",
        "lock_state": "门锁状态",
        "loitering_alert": "逗留提醒开关",
        "loitering_alert_delay": "逗留提醒时间档位",
        "main_bolt_state": "主锁舌状态",
        "maximum_online_users": "同时在线用户个数",
        "microphone": "麦克风开关",
        "microphone_user_id": "麦克风用户 ID",
        "motion_detection": "人体移动检测",
        "online_connections": "直播在线连接数",
        "outdoor_temperature": "室外温度",
        "p2p_data_channel": "P2P 数据通道状态",
        "p2p_support": "P2P 支持",
        "p2p_users": "P2P 用户状态",
        "power": "电源",
        "power_save_mode": "省电模式",
        "security_mode": "安防模式",
        "sleep": "睡眠",
        "swing": "扫风",
        "tamper_alarm": "防撬报警",
        "target_humidity": "目标湿度",
        "target_temperature": "目标温度",
        "temperature": "温度",
        "unlock_verification_mode": "开锁验证模式",
        "vertical_swing": "上下扫风",
        "video_parameters": "视频参数",
        "voice_volume": "语音音量",
        "volume": "音量",
        "wifi_keep_alive": "Wi-Fi 保活开关",
        "work_mode": "工作模式",
    },
}

ROUTE_OPTION_NAMES = {
    "en": {
        "auto": "Auto",
        "closed": "Closed",
        "cool": "Cool",
        "dry": "Dry",
        "eco": "Eco",
        "face_password": "Face and password",
        "fan_only": "Fan only",
        "fingerprint_card": "Fingerprint and card",
        "fingerprint_password": "Fingerprint and password",
        "heat": "Heat",
        "high": "High",
        "high_volume": "High volume",
        "locked": "Locked",
        "low": "Low",
        "low_volume": "Low volume",
        "medium": "Medium",
        "medium_volume": "Medium volume",
        "muted_volume": "Muted",
        "off": "Off",
        "on": "On",
        "open": "Open",
        "quiet": "Quiet",
        "single_verification": "Single verification",
        "sleep": "Sleep",
        "turbo": "Turbo",
        "two_fingerprints": "Two fingerprints",
        "unlocked": "Unlocked",
    },
    "zh-Hans": {
        "auto": "自动",
        "closed": "已关闭",
        "cool": "制冷",
        "dry": "除湿",
        "eco": "节能",
        "face_password": "人脸密码模式",
        "fan_only": "送风",
        "fingerprint_card": "指纹门卡模式",
        "fingerprint_password": "指纹密码模式",
        "heat": "制热",
        "high": "高",
        "high_volume": "高音量",
        "locked": "已锁定",
        "low": "低",
        "low_volume": "低音量",
        "medium": "中",
        "medium_volume": "中音量",
        "muted_volume": "静音音量",
        "off": "关闭",
        "on": "开启",
        "open": "打开",
        "quiet": "静音",
        "single_verification": "单开模式",
        "sleep": "睡眠",
        "turbo": "强劲",
        "two_fingerprints": "双指纹模式",
        "unlocked": "已解锁",
    },
}
