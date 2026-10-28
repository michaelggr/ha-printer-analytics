"""Utility Tracker 常量定义"""

DOMAIN = "utility_tracker"

# 配置键
CONF_MARIADB_HOST = "mariadb_host"
CONF_MARIADB_PORT = "mariadb_port"
CONF_MARIADB_USER = "mariadb_user"
CONF_MARIADB_PASSWORD = "mariadb_password"
CONF_MARIADB_DATABASE = "mariadb_database"
CONF_ENABLE_ELECTRICITY = "enable_electricity"
CONF_ENABLE_GAS = "enable_gas"
CONF_ENABLE_DEVICE_POWER = "enable_device_power"
CONF_ENABLE_LIGHT_STATS = "enable_light_stats"
CONF_SYNC_INTERVAL_HOURS = "sync_interval_hours"
CONF_POWER_SAMPLE_MINUTES = "power_sample_minutes"
CONF_RAW_RETENTION_DAYS = "raw_retention_days"

# 默认值
DEFAULT_MARIADB_HOST = "core-mariadb"
DEFAULT_MARIADB_PORT = 3306
DEFAULT_MARIADB_USER = "ha_utility"
DEFAULT_MARIADB_DATABASE = "utility_bills"
DEFAULT_SYNC_INTERVAL_HOURS = 1
DEFAULT_POWER_SAMPLE_MINUTES = 5
DEFAULT_RAW_RETENTION_DAYS = 30

# 工具类型
UTILITY_TYPE_ELECTRICITY = "electricity"
UTILITY_TYPE_GAS = "gas"

# 粒度
GRANULARITY_DAY = "day"
GRANULARITY_MONTH = "month"

# 设备功耗 device_class 过滤
POWER_DEVICE_CLASSES = ("power", "energy")

# 功耗异常值过滤阈值
POWER_MAX_W = 10000.0        # 单设备功率绝对上限 (W), 超过视为异常采样
POWER_JUMP_ABS_W = 3000.0    # 跳变判定: 最小绝对增量 (W)
POWER_JUMP_RATIO = 10.0      # 跳变判定: 新值 / 上次有效值 的倍数阈值
POWER_LAST_LOOKBACK_HOURS = 24  # 读取上次有效值的回溯窗口 (小时)


def is_power_outlier(
    last_w: float | None,
    new_w: float | None,
    max_w: float = POWER_MAX_W,
    jump_abs_w: float = POWER_JUMP_ABS_W,
    jump_ratio: float = POWER_JUMP_RATIO,
) -> bool:
    """判断单次功率采样是否为异常值 (True 表示应丢弃该采样)

    规则:
    1. 无值 (None) 不判定为异常, 交给调用方按跳过处理
    2. 超过绝对上限 max_w 或为负数 -> 异常 (家用单设备不可能出现)
    3. 与上次有效值比较, 同时满足「倍数 >= jump_ratio」且「增量 > jump_abs_w」-> 异常
       两个条件同时成立才判定, 避免小功率设备 (5W 待机 -> 80W) 因倍数放大被误杀;
       上次值 <= 0 (首次采样/设备刚上电) 时不做跳变判定, 避免把真实启动功率误杀
    """
    if new_w is None:
        return False
    if new_w < 0 or new_w > max_w:
        return True
    if last_w is None or last_w <= 0:
        return False
    return (new_w - last_w) > jump_abs_w and new_w >= last_w * jump_ratio

# 灯光动作
LIGHT_ACTION_ON = "on"
LIGHT_ACTION_OFF = "off"

# 灯光类 switch 识别: 部分灯以 switch 域存在 (如智能开关/补光灯),
# entity_id 含关键字或 friendly_name 含 "灯"/"light"/"lamp" 时纳入灯光统计
LIGHT_SWITCH_ID_KEYWORDS = ("light", "lamp")
LIGHT_SWITCH_NAME_KEYWORDS = ("灯", "light", "lamp")


# 13 个区域主灯 -> 区域名
# 实体来自 sensor.yaml 中 platform: history_stats 的「区域灯亮灯时长」,
# 其值即「今日该灯累计亮灯小时数」,每日 0 点归零,是入库时长的权威来源
LIGHT_AREA_DURATION_ENTITIES: dict[str, str] = {
    "sensor.ke_ting_deng_liang_deng_shi_chang": "客厅",
    "sensor.zhu_wo_deng_liang_deng_shi_chang": "主卧",
    "sensor.ci_wo_deng_liang_deng_shi_chang": "次卧",
    "sensor.bei_wo_deng_liang_deng_shi_chang": "北卧",
    "sensor.chu_fang_deng_liang_deng_shi_chang": "厨房",
    "sensor.can_ting_deng_liang_deng_shi_chang": "餐厅",
    "sensor.zhu_wei_deng_liang_deng_shi_chang": "主卫",
    "sensor.gong_wei_deng_liang_deng_shi_chang": "公卫",
    "sensor.nan_yang_tai_deng_liang_deng_shi_chang": "南阳台",
    "sensor.bei_yang_tai_deng_liang_deng_shi_chang": "北阳台",
    "sensor.zou_lang_deng_liang_deng_shi_chang": "走廊",
    "sensor.men_kou_deng_liang_deng_shi_chang": "门口",
    "sensor.gong_wei_gan_qu_deng_liang_deng_shi_chang": "公卫干区",
}


# 12 个区域停留时长 -> 区域名
# 实体来自 sensor.yaml 中 platform: history_stats 的「区域停留时长」,
# 值是「今日该区域累计有人小时数」, 每日 0 点归零; 与灯光时长同样每 5 分钟快照入库
AREA_STAY_DURATION_ENTITIES: dict[str, str] = {
    "sensor.ke_ting_ting_liu_shi_chang": "客厅",
    "sensor.zhu_wo_ting_liu_shi_chang": "主卧",
    "sensor.ci_wo_ting_liu_shi_chang": "次卧",
    "sensor.bei_wo_ting_liu_shi_chang": "北卧",
    "sensor.chu_fang_ting_liu_shi_chang": "厨房",
    "sensor.can_ting_ting_liu_shi_chang": "餐厅",
    "sensor.zhu_wei_ting_liu_shi_chang": "主卫",
    "sensor.gong_wei_ting_liu_shi_chang": "公卫",
    "sensor.gong_wei_gan_qu_ting_liu_shi_chang": "公卫干区",
    "sensor.nan_yang_tai_ting_liu_shi_chang": "南阳台",
    "sensor.bei_yang_tai_ting_liu_shi_chang": "北阳台",
    "sensor.zou_lang_ting_liu_shi_chang": "走廊",
}


def is_light_entity(entity_id: str, friendly_name: str | None) -> bool:
    """判断是否为灯光实体: light.* 全收; switch.* 仅收灯光类"""
    if entity_id.startswith("light."):
        return True
    if not entity_id.startswith("switch."):
        return False
    eid_lower = entity_id.lower()
    if any(kw in eid_lower for kw in LIGHT_SWITCH_ID_KEYWORDS):
        return True
    name_lower = (friendly_name or "").lower()
    return any(kw in name_lower for kw in LIGHT_SWITCH_NAME_KEYWORDS)

# 数据源集成 domain
SOURCE_STATE_GRID = "state_grid"
SOURCE_CRCGAS = "crcgas"

# 服务
SERVICE_SYNC_NOW = "sync_now"
SERVICE_BACKFILL_HISTORY = "backfill_history"
SERVICE_PURGE_DEVICE_DATA = "purge_device_data"

# 属性键
ATTR_LAST_SYNC = "last_sync"
ATTR_TOTAL_RECORDS = "total_records"
ATTR_LAST_ERROR = "last_error"
