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
CONF_SYNC_INTERVAL_HOURS = "sync_interval_hours"

# 默认值
DEFAULT_MARIADB_HOST = "core-mariadb"
DEFAULT_MARIADB_PORT = 3306
DEFAULT_MARIADB_USER = "ha_utility"
DEFAULT_MARIADB_DATABASE = "utility_bills"
DEFAULT_SYNC_INTERVAL_HOURS = 1

# 工具类型
UTILITY_TYPE_ELECTRICITY = "electricity"
UTILITY_TYPE_GAS = "gas"

# 粒度
GRANULARITY_DAY = "day"
GRANULARITY_MONTH = "month"

# 数据源集成 domain
SOURCE_STATE_GRID = "state_grid"
SOURCE_CRCGAS = "crcgas"

# 服务
SERVICE_SYNC_NOW = "sync_now"
SERVICE_BACKFILL_HISTORY = "backfill_history"

# 属性键
ATTR_LAST_SYNC = "last_sync"
ATTR_TOTAL_RECORDS = "total_records"
ATTR_LAST_ERROR = "last_error"
