-- Utility Tracker 数据库 Schema
-- 统一电费/燃气费数据模型,长期存储

-- 表 1: 统一用量/费用记录
-- 电费日记录 + 电费月结算 + 燃气月账单 全在这张表
CREATE TABLE IF NOT EXISTS utility_records (
  id INT AUTO_INCREMENT PRIMARY KEY,
  utility_type ENUM('electricity','gas') NOT NULL COMMENT '类型',
  account_id VARCHAR(32) NOT NULL COMMENT '户号后缀或户号',
  granularity ENUM('day','month') NOT NULL COMMENT '粒度',
  period_date DATE NOT NULL COMMENT '日期(日) 或 月份第一天(月)',
  -- 单据号: 燃气=applicationNo (同月可能有多张单据,如正常账单+退款), 电费/非单据记录为空串
  bill_no VARCHAR(64) NOT NULL DEFAULT '' COMMENT '单据号',
  usage_amount DECIMAL(12,3) NULL COMMENT '用量: 电=kWh, 气=m³ (退款为负数)',
  charge DECIMAL(12,2) NULL COMMENT '费用(元, 退款为负数)',
  peak DECIMAL(12,3) NULL COMMENT '峰(电)',
  flat DECIMAL(12,3) NULL COMMENT '平(电)',
  valley DECIMAL(12,3) NULL COMMENT '谷(电)',
  tip DECIMAL(12,3) NULL COMMENT '尖(电)',
  tier1_usage DECIMAL(12,3) NULL COMMENT '一阶梯用量(气)',
  tier2_usage DECIMAL(12,3) NULL COMMENT '二阶梯用量(气)',
  tier3_usage DECIMAL(12,3) NULL COMMENT '三阶梯用量(气)',
  meter_reading DECIMAL(12,2) NULL COMMENT '抄表读数',
  meter_date DATE NULL COMMENT '抄表日期',
  extra JSON NULL COMMENT '扩展字段',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uniq_record (utility_type, account_id, granularity, period_date, bill_no),
  KEY idx_type_date (utility_type, period_date),
  KEY idx_account (account_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='统一用量/费用记录';

-- 表 2: 账户快照(日级)
CREATE TABLE IF NOT EXISTS account_snapshots (
  id INT AUTO_INCREMENT PRIMARY KEY,
  utility_type ENUM('electricity','gas') NOT NULL,
  account_id VARCHAR(32) NOT NULL,
  snapshot_date DATE NOT NULL,
  balance DECIMAL(12,2) NULL COMMENT '账户余额',
  amount_due DECIMAL(12,2) NULL COMMENT '应交/欠费',
  year_total_usage DECIMAL(12,3) NULL COMMENT '本年累计用量',
  year_total_charge DECIMAL(12,2) NULL COMMENT '本年累计费用',
  extra JSON NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uniq_snapshot (utility_type, account_id, snapshot_date),
  KEY idx_type_date (utility_type, snapshot_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='账户余额快照';

-- =====================================================================
-- 设备功耗 (单设备功率/电量 sensor,5 分钟级原始 + 小时/日聚合)
-- =====================================================================

-- 表 3: 设备功耗原始采样 (5 分钟级,保留 30 天)
CREATE TABLE IF NOT EXISTS device_power_raw (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  entity_id VARCHAR(128) NOT NULL COMMENT 'HA 实体 ID',
  friendly_name VARCHAR(128) NULL COMMENT '实体友好名称',
  sampled_at DATETIME NOT NULL COMMENT '采样时间(对齐 5 分钟)',
  power_w DECIMAL(10,3) NULL COMMENT '功率(W), device_class=power',
  energy_kwh DECIMAL(14,4) NULL COMMENT '累计电量(kWh), device_class=energy',
  state VARCHAR(32) NULL COMMENT '原始状态字符串',
  UNIQUE KEY uniq_sample (entity_id, sampled_at),
  KEY idx_entity_time (entity_id, sampled_at),
  KEY idx_time (sampled_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='设备功耗原始采样(5分钟)';

-- 表 4: 设备功耗小时聚合 (永久保留)
CREATE TABLE IF NOT EXISTS device_power_hourly (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  entity_id VARCHAR(128) NOT NULL,
  friendly_name VARCHAR(128) NULL,
  hour_start DATETIME NOT NULL COMMENT '小时起点',
  avg_w DECIMAL(10,3) NULL COMMENT '平均功率(W)',
  max_w DECIMAL(10,3) NULL,
  min_w DECIMAL(10,3) NULL,
  energy_kwh DECIMAL(14,4) NULL COMMENT '本小时耗电(kWh)',
  sample_count INT NOT NULL DEFAULT 0 COMMENT '采样点数',
  UNIQUE KEY uniq_hour (entity_id, hour_start),
  KEY idx_entity_time (entity_id, hour_start)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='设备功耗小时聚合';

-- 表 5: 设备功耗日聚合 (永久保留)
CREATE TABLE IF NOT EXISTS device_power_daily (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  entity_id VARCHAR(128) NOT NULL,
  friendly_name VARCHAR(128) NULL,
  period_date DATE NOT NULL,
  avg_w DECIMAL(10,3) NULL,
  max_w DECIMAL(10,3) NULL,
  min_w DECIMAL(10,3) NULL,
  energy_kwh DECIMAL(14,4) NULL COMMENT '当日耗电(kWh)',
  peak_hour TINYINT NULL COMMENT '功率最高的小时(0-23)',
  sample_count INT NOT NULL DEFAULT 0,
  UNIQUE KEY uniq_day (entity_id, period_date),
  KEY idx_entity_date (entity_id, period_date),
  KEY idx_date (period_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='设备功耗日聚合';

-- =====================================================================
-- 灯光统计 (开/关事件 + 每日亮灯时长)
-- =====================================================================

-- 表 6: 灯光开关事件
CREATE TABLE IF NOT EXISTS light_events (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  entity_id VARCHAR(128) NOT NULL,
  friendly_name VARCHAR(128) NULL,
  event_time DATETIME NOT NULL COMMENT '事件时间',
  action ENUM('on','off') NOT NULL COMMENT '动作',
  brightness SMALLINT NULL COMMENT '亮度 0-255 (开灯时, TINYINT 不够存 255)',
  color_temp SMALLINT NULL COMMENT '色温 mired',
  KEY idx_entity_time (entity_id, event_time),
  KEY idx_time (event_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='灯光开关事件';

-- =====================================================================
-- 区域主灯每日亮灯时长 (history_stats 快照, 永久保留)
-- =====================================================================

-- 表 8: 区域主灯每日亮灯时长
-- 数据来源: sensor.yaml 的 13 个 history_stats 区域主灯实体,
-- 每 5 分钟快照今日累计小时数 -> 秒, 同一天覆盖更新;
-- 与表 7 light_daily(事件流, 记录开关次数/亮度) 分工:
--   本表是「亮灯时长」的权威来源, 表 7 负责「开关次数/首次开灯/最后关灯」
CREATE TABLE IF NOT EXISTS light_duration_daily (
  id INT AUTO_INCREMENT PRIMARY KEY,
  entity_id VARCHAR(128) NOT NULL COMMENT 'history_stats 传感器实体 ID',
  area_name VARCHAR(32) NOT NULL COMMENT '区域名',
  period_date DATE NOT NULL,
  duration_sec INT NOT NULL DEFAULT 0 COMMENT '当日累计亮灯时长(秒)',
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uniq_entity_day (entity_id, period_date),
  KEY idx_area_date (area_name, period_date),
  KEY idx_date (period_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='区域主灯每日亮灯时长(history_stats)';

-- 表 7: 灯光日聚合 (事件流: 开关次数/首次开灯/最后关灯/平均亮度, 永久保留)
CREATE TABLE IF NOT EXISTS light_daily (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  entity_id VARCHAR(128) NOT NULL,
  friendly_name VARCHAR(128) NULL,
  period_date DATE NOT NULL,
  on_count INT NOT NULL DEFAULT 0 COMMENT '开灯次数',
  on_duration_sec INT NOT NULL DEFAULT 0 COMMENT '亮灯时长(秒)',
  first_on_time DATETIME NULL COMMENT '当日首次开灯',
  last_off_time DATETIME NULL COMMENT '当日最后关灯',
  avg_brightness DECIMAL(6,2) NULL COMMENT '平均亮度',
  UNIQUE KEY uniq_day (entity_id, period_date),
  KEY idx_entity_date (entity_id, period_date),
  KEY idx_date (period_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='灯光日聚合';

-- 表 9: 区域每日停留时长
-- 数据来源: sensor.yaml 的 12 个 history_stats 区域停留时长实体,
-- 每 5 分钟快照今日累计小时数 -> 秒, 同一天覆盖更新, 永久保留历史;
-- 与灯光时长(表 8)结构一致, 仅数据源换成「有人/无人」统计
CREATE TABLE IF NOT EXISTS area_stay_daily (
  id INT AUTO_INCREMENT PRIMARY KEY,
  entity_id VARCHAR(128) NOT NULL COMMENT 'history_stats 传感器实体 ID',
  area_name VARCHAR(32) NOT NULL COMMENT '区域名',
  period_date DATE NOT NULL,
  duration_sec INT NOT NULL DEFAULT 0 COMMENT '当日累计停留时长(秒)',
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uniq_entity_day (entity_id, period_date),
  KEY idx_area_date (area_name, period_date),
  KEY idx_date (period_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='区域每日停留时长(history_stats)';

-- 表 10: 区域分时段停留时长 (热力图数据源)
-- 数据来源: 与表 9 同一批 history_stats 实体, 每次采样把「今日累计秒数」
-- 相对上次采样的增量, 累加进当前小时(0-23)的桶里;
-- UNIQUE(entity_id, period_date, period_hour) 保证同小时多次采样是累加而非覆盖
CREATE TABLE IF NOT EXISTS area_stay_hourly (
  id INT AUTO_INCREMENT PRIMARY KEY,
  entity_id VARCHAR(128) NOT NULL COMMENT 'history_stats 传感器实体 ID',
  area_name VARCHAR(32) NOT NULL COMMENT '区域名',
  period_date DATE NOT NULL,
  period_hour TINYINT UNSIGNED NOT NULL COMMENT '小时时段 0-23',
  duration_sec INT NOT NULL DEFAULT 0 COMMENT '该小时累计停留增量(秒)',
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uniq_entity_hour (entity_id, period_date, period_hour),
  KEY idx_area_hour (area_name, period_hour),
  KEY idx_date (period_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='区域分时段停留时长(小时粒度)';
