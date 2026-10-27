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
  usage_amount DECIMAL(12,3) NULL COMMENT '用量: 电=kWh, 气=m³',
  charge DECIMAL(12,2) NULL COMMENT '费用(元)',
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
  UNIQUE KEY uniq_record (utility_type, account_id, granularity, period_date),
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
