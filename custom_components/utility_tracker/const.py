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
CONF_ENABLE_AWAY_STATS = "enable_away_stats"
CONF_SYNC_INTERVAL_HOURS = "sync_interval_hours"
CONF_POWER_SAMPLE_MINUTES = "power_sample_minutes"
CONF_RAW_RETENTION_DAYS = "raw_retention_days"

# 出门统计
CONF_AWAY_EVENT_ENTITY = "away_event_entity"
CONF_AWAY_OUT_NAMES = "away_out_names"
CONF_AWAY_HOME_NAMES = "away_home_names"
CONF_AWAY_SHORT_MINUTES = "away_short_minutes"

# 默认值
DEFAULT_MARIADB_HOST = "core-mariadb"
DEFAULT_MARIADB_PORT = 3306
DEFAULT_MARIADB_USER = "ha_utility"
DEFAULT_MARIADB_DATABASE = "utility_bills"
DEFAULT_SYNC_INTERVAL_HOURS = 1
DEFAULT_POWER_SAMPLE_MINUTES = 5
DEFAULT_RAW_RETENTION_DAYS = 30
DEFAULT_AWAY_EVENT_ENTITY = "event.xiaomi_cn_1184711570_hub1_virtual_event_e_4_1"
DEFAULT_AWAY_OUT_NAMES = ("场景-出门",)
DEFAULT_AWAY_HOME_NAMES = ("场景-回家",)
DEFAULT_AWAY_SHORT_MINUTES = 10

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


# 电量读数抖动容差 (kWh)
# 低分辨率设备 (如 0.01 kWh 的 yutai 插座) 会在相邻刻度间反复抖动, 必须与
# 「真实增长」和「计数器清零」区分: 回退超过该容差判为清零, 回退/微增在该
# 容差内且读数有回退时视为抖动归零。取 0.011 略大于一个 0.01 刻度。
ENERGY_RESET_TOLERANCE_KWH = 0.011


def sum_energy_deltas(
    values: list[float], prev_reading: float | None = None
) -> float | None:
    """根据本窗口的累计电量读数序列推算耗电量 (kWh)

    参数:
        values:       本窗口内按时间升序的累计电量读数 (不含窗口外数据)
        prev_reading: 上一窗口最后一条读数, 作为跨窗口基线; 为 None 时用序列首值

    规则:
    1. 窗口内读数跌幅超过容差、且跌到前值一半以下 -> 计数器被清零
       (只按跌幅判断会把低分辨率插座的量化抖动误判成清零, 凭空多记读数)
       此时计入「清零前那段 + 清零后至窗口末的累计值」
    2. 窗口开始前就已清零 (上一窗口末值远大于本窗口首值) -> 只计本窗口累计值
    3. 读数全程单调不减 -> 末值减基线全额计入
       (保护 0.0001 kWh 级高分辨率电表的微小真实增长, 如 5W 设备 0.0003/h)
    4. 读数有回退 -> 属于低分辨率量化抖动, 容差内的差异一律归零
       (否则 0W 插座每小时会凭空多记 0.01 kWh, 一天虚增 0.13 kWh)

    返回 None 表示没有可用读数。
    """
    if not values:
        return None
    ref = prev_reading if prev_reading is not None else values[0]

    # 定位窗口内最后一次「计数器清零」的位置
    reset_idx: int | None = None
    for i in range(1, len(values)):
        prev_v, cur_v = values[i - 1], values[i]
        if prev_v - cur_v > ENERGY_RESET_TOLERANCE_KWH and cur_v < prev_v * 0.5:
            reset_idx = i

    if reset_idx is not None:
        # 清零前那一段 (基线 -> 清零前读数) + 清零后至窗口末的累计值
        return max(values[reset_idx - 1] - ref, 0.0) + max(values[-1], 0.0)

    if (
        prev_reading is not None
        and prev_reading - values[0] > ENERGY_RESET_TOLERANCE_KWH
        and values[0] < prev_reading * 0.5
    ):
        # 本窗口开始前就已清零: 清零前那段属于上一个窗口, 不计入
        return max(values[-1], 0.0)

    diff = values[-1] - ref
    if len(values) == 1:
        # 只有一个读数: 有基线时按差值, 无基线时无从推算
        return max(diff, 0.0) if prev_reading is not None else 0.0
    if all(b >= a for a, b in zip(values, values[1:])):
        # 单调不减: 末值减基线全额计入 (基线可能恰好落在抖动高位, 差值不会为负)
        return max(diff, 0.0)
    # 存在回退: 量化抖动, 容差内归零
    return diff if diff > ENERGY_RESET_TOLERANCE_KWH else 0.0


# 派生电量计量关键词: 这类实体是「日/周/月/年用电量」的中间量,
# 与设备自身的累计电量计数器重复, 同时参与求和会把今日电量放大数倍
ENERGY_DERIVED_KEYWORDS = (
    "daily", "weekly", "monthly", "yearly", "today",
    # 上周期派生 (上月/上周/昨日等), 与累计计数器重复
    "last_day", "last_week", "last_month", "last_year",
    "yesterday",
    "日用电量", "周用电量", "月用电量", "年用电量", "今日耗电量",
    "昨日", "上周", "上月", "去年",
    "ri_yong_dian", "zhou_yong_dian", "yue_yong_dian", "nian_yong_dian",
)

# 组件级功率关键词: CPU/GPU/压缩机等部件功率与整机功率同时求和会重复计量
POWER_COMPONENT_KEYWORDS = ("cpu", "gpu", "cores", "package", "compressor", "压缩机")


def _match_keywords(entity_id: str, friendly_name: str | None, keywords: tuple[str, ...]) -> bool:
    """实体 ID 或友好名称命中任一关键词即返回 True (小写不敏感)"""
    text = f"{entity_id} {friendly_name or ''}".lower()
    return any(kw.lower() in text for kw in keywords)


def is_derived_energy_entity(entity_id: str, friendly_name: str | None) -> bool:
    """判断是否为派生电量实体 (日/周/月/年用电量), True 表示应排除"""
    return _match_keywords(entity_id, friendly_name, ENERGY_DERIVED_KEYWORDS)


def is_component_power_entity(entity_id: str, friendly_name: str | None) -> bool:
    """判断是否为组件级功率实体 (CPU/GPU/压缩机), True 表示应排除"""
    return _match_keywords(entity_id, friendly_name, POWER_COMPONENT_KEYWORDS)


# 自带计量不准的整机实体: 改由对应的空调插座计量
# 新风空调自带「实时功率 6W / 耗电量」与北卧空调插座读数不一致 (插座 0W),
# 两套数据并存会重复计量, 按实际用电以插座为准, 显式排除自带读数
EXCLUDED_POWER_ENTITIES = frozenset({
    "sensor.bei_wo_xin_feng_kong_diao_real_time_power",
})
EXCLUDED_ENERGY_ENTITIES = frozenset({
    # 累计电量: 与插座耗电量重复计算
    "sensor.bei_wo_xin_feng_kong_diao_total_energy_consumption",
    # 当前能源消耗: 非累计计数器, MAX-MIN 求增量无意义
    "sensor.bei_wo_xin_feng_kong_diao_current_energy_consumption",
    # giot 系列「耗电量」单位错标为 mWh (数值实际是 Wh), 入库时被低估 1000 倍,
    # 且与同名设备的「累计用电」重复, 统一以 helper 累计值为准
    "sensor.giot_cn_1162942256_v8icm_power_consumption_p_4_1",  # 电脑电源
    "sensor.giot_cn_1163256502_v8icm_power_consumption_p_4_1",  # NAS
    "sensor.giot_cn_1164778814_v8icm_power_consumption_p_4_1",  # 小黑奴电源
    # 小黑奴「耗电量」模板 (p_4_1/1000): 计数器在 0~2 kWh 间反复归零后重爬,
    # 增量差分会把重爬段当成新增电量, 日电量虚高约 6 倍
    # (10/29-31 报 6.409/5.108/6.202 kWh, 而 150W 上限的物理天花板仅 3.6 kWh/24h)
    # 改为由功率实体积分计量 (见 POWER_INTEGRATION_ENTITIES)
    "sensor.giot_cn_1164778814_v8icm_power_consumption_kwh",
    # 取暖器: 无可用累计电量, 改由功率积分兜底 (见 POWER_INTEGRATION_ENTITIES)
    "sensor.giot_cn_1162898415_v8icm_power_consumption_p_4_1",
    # 小打印机 helper (integration 积分器): 与 utility_tracker 自身按 AVG(power)×采样时长的
    # 积分口径重复, 同一台打印机会被计两次, 故排除 (米家原生计数器已因归零不可用, 见上)
    "sensor.xiao_da_yin_ji_lei_ji_yong_dian",
})


# 需要由功率积分兜底计量的 power 实体
# 对应设备的累计电量传感器不可用 (取暖器累计用电为 unknown, giot 耗电量恒为 0),
# 聚合时按 energy_kwh = AVG(power_w) × 采样覆盖小时数 估算
POWER_INTEGRATION_ENTITIES = frozenset({
    "sensor.giot_cn_1162898415_v8icm_electric_power_p_4_2",
    # 小黑奴: 累计电量计数器反复归零不可用 (见 EXCLUDED_ENERGY_ENTITIES),
    # 改按功率积分, 上限 150W -> 24h 最多 3.6 kWh, 与物理量级自洽
    "sensor.giot_cn_1164778814_v8icm_electric_power_p_4_2",
})


def is_power_integration_entity(entity_id: str) -> bool:
    """该 power 实体需要用功率积分兜底计量电量"""
    return entity_id in POWER_INTEGRATION_ENTITIES


def is_excluded_power_entity(entity_id: str) -> bool:
    """整机自带功率不准、改用插座计量的实体"""
    return entity_id in EXCLUDED_POWER_ENTITIES


def is_excluded_energy_entity(entity_id: str) -> bool:
    """整机自带电量不准、改用插座计量的实体"""
    return entity_id in EXCLUDED_ENERGY_ENTITIES

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
