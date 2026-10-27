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

# 灯光动作
LIGHT_ACTION_ON = "on"
LIGHT_ACTION_OFF = "off"

# 灯光类 switch 识别: 部分灯以 switch 域存在 (如智能开关/补光灯),
# entity_id 含关键字或 friendly_name 含 "灯"/"light"/"lamp" 时纳入灯光统计
LIGHT_SWITCH_ID_KEYWORDS = ("light", "lamp")
LIGHT_SWITCH_NAME_KEYWORDS = ("灯", "light", "lamp")


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
