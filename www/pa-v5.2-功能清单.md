# 打印机分析卡片 v5.2 功能清单

## 📋 基本信息
- **开发文件**: `www/pa-v5.2.js`
- **服务器文件**: `Y:\www\pa-v5.2.js`（上传目标）
- **配置引用**: `configuration.yaml` → `/local/pa-v5.2.js?v=5.2`
- **版本**: v5.2 (2026-05-11)
- **类型**: Home Assistant 自定义 Lovelace 卡片 (`custom:printer-analytics-card`)
- **适用**: BambuLab 打印机 (P2S / A1 Mini)

> ⚠️ **缓存绕过方案**：JS 文件已从 pa-v5.1.js 重命名为 pa-v5.2.js。
> 以后改代码只编辑 `www/pa-v5.2.js`，上传时复制到服务器 `pa-v5.2.js` 即可。

---

## 🖥️ 页面结构

### 顶部 Header
- 打印机名称 + 型号
- 版本号徽章 `v5.1`

### mode 配置（控制卡片显示模式）
| mode 值 | 效果 | 用途 |
|---------|------|------|
| `stats` | 仅显示统计分析 | 打印机页签 |
| `history` | 仅显示全部历史 | 全部历史页签 |
| `''` (默认) | 显示标签页切换 | 兼容旧配置 |

### 侧边栏视图结构
- **P2S打印机** → 卡片 mode: stats（仅统计）
- **a1mini打印机** → 卡片 mode: stats（仅统计）
- **全部历史** → 卡片 mode: history（仅历史，合并所有打印机）

---

## 📊 统计分析 (mode: stats)

### 1.1 实时统计维度
- 总打印次数、成功率、平均时长、总时长、总能耗、当前状态
- 六宫格数字卡片

### 1.2 周期统计
- 最近7天 / 最近30天 两张统计表
- 打印次数、成功/失败、成功率、耗材重量/长度、能耗、平均时长

### 1.3 成功率趋势图
- 累计成功率折线图 + 面积填充
- 降采样优化（>100条时自动降采样）

### 1.4 打印时长分布
- 水平条形图，渐变色

### 1.5 失败阶段分布
- 柱状图显示早期/中期/后期失败次数及百分比
- 数据源: `failure_stage_distribution` 传感器

### 1.6 耗材成功率统计
- 按耗材类型显示成功率、成功/失败/取消次数
- 进度条可视化成功率
- 数据源: `filament_success_stats` 传感器

### 1.7 活动热力图
- 7×5 日期矩阵，绿色深浅表示打印密度

### 1.8 耗材使用分析
- 按类型统计 (PLA/PETG/TPU等) - 饼图
- 按颜色统计 - 饼图
- 多色打印记录卡片（含颜色占比、进度条）

### 1.9 实时监控面板
| 指标 | 配置项 | 说明 |
|------|--------|------|
| 📋 当前任务 | `current_task` | 当前打印任务名 |
| 📊 打印进度 | `print_progress` | 百分比进度条 |
| ⚖️ 当前耗材重量 | `current_weight` | 克 |
| 📦 累计使用量 | `total_usage` | 克 |
| 🌡️ 喷嘴温度 | `nozzle_temp` | °C |
| 🔥 热床温度 | `bed_temp` | °C |
| 💨 腔体温度 | `chamber_temp` | °C (a1mini用环境温湿度计) |
| ⚡ 功耗 | `power_consumption` | W (替代原WiFi信号) |
| ⚡ 打印速度 | `speed_profile` | 当前速度档位 |
| 🔧 喷嘴尺寸 | `nozzle_size` | mm |
| 🎨 AMS耗材盘 | `ams_tray_1~4` | 托盘颜色+名称+激活状态 |

### 1.10 终身统计
- 总打印次数、总耗材重量/长度、总能耗

---

## 🗂️ 全部历史 (mode: history)

### 筛选栏
| 筛选项 | 类型 | 说明 |
|--------|------|------|
| 状态筛选 | 下拉 | 全部/成功/失败/已取消 |
| 颜色筛选 | 下拉 | 自动提取历史记录中所有用过的颜色，显示中文色名 |
| 起始日期 | 日期选择 | date-from |
| 结束日期 | 日期选择 | date-to |
| 搜索框 | 文本 | 搜索任务名称或耗材类型 |
| **确定按钮** | 按钮 | 点击后执行筛选（不实时触发） |
| **重置按钮** | 按钮 | 清空所有筛选条件 |

### 摘要统计栏
- 总记录数、成功率、总耗材、总时长

### 历史记录列表
- 每条记录显示：状态图标 + 封面图/缩略图 + 任务名 + 打印机标签 + 时长 + 耗材 + 重量 + 能耗 + 多色标记 + 时间范围
- **分页**: 每页20条，底部分页控件 (◀ 1 2 3 ... ▶)
- 点击记录 → 弹出详情弹窗
- 支持批量选择 + 批量删除（二次确认）

### 详情弹窗
- 任务名称、打印机、状态、完成进度
- 开始时间、结束时间（已修复时区问题）
- 打印时长、耗材类型、耗材重量/长度、能耗
- 颜色信息（含每种颜色重量和占比）
- 打印快照图

---

## 🔧 配置项 (YAML)

### 打印机页签 (mode: stats)
```yaml
type: custom:printer-analytics-card
title: 🖨️ P2S打印机分析
mode: stats
printer_name: P2S
print_history: sensor.xxx_da_yin_li_shi
total_prints: sensor.xxx_zong_da_yin_ci_shu
success_rate: sensor.xxx_cheng_gong_lu
average_duration: sensor.xxx_ping_jun_da_yin_shi_chang
total_print_duration: sensor.xxx_da_yin_zong_shi_chang
total_energy: sensor.xxx_zong_neng_hao
material_stats_7d: sensor.xxx_7tian_hao_cai_tong_ji
material_stats_30d: sensor.xxx_30tian_hao_cai_tong_ji
material_stats_lifetime: sensor.xxx_zhong_shen_hao_cai_tong_ji
duration_distribution: sensor.xxx_da_yin_shi_chang_fen_bu
activity_heatmap: sensor.xxx_da_yin_huo_dong_re_li_tu
print_status: sensor.xxx_da_yin_zhuang_tai
current_task: sensor.xxx_task_name
print_progress: sensor.xxx_print_progress
current_weight: sensor.xxx_print_weight
total_usage: sensor.xxx_total_usage
nozzle_temp: sensor.xxx_nozzle_temperature
bed_temp: sensor.xxx_bed_temperature
chamber_temp: sensor.xxx_chamber_temperature
power_consumption: sensor.xxx_electric_power
speed_profile: sensor.xxx_speed_profile
nozzle_size: sensor.xxx_nozzle_size
active_tray: sensor.xxx_active_tray
ams_tray_1: sensor.xxx_ams_tray_1
ams_tray_2: sensor.xxx_ams_tray_2
ams_tray_3: sensor.xxx_ams_tray_3
ams_tray_4: sensor.xxx_ams_tray_4
extra_print_histories:
  - entity: sensor.other_printer_history
    name: 其他打印机
```

### 全部历史页签 (mode: history)
```yaml
type: custom:printer-analytics-card
title: 🗂️ 全部打印历史
mode: history
printer_name: 全部
print_history: sensor.p2s_da_yin_li_shi
extra_print_histories:
  - entity: sensor.a1mini_da_yin_li_shi
    name: a1mini
```

---

## 📝 当前实体映射

### P2S (大黑奴)
| 配置项 | 实体 |
|--------|------|
| chamber_temp | sensor.p2s_22e8bj5a2401765_chamber_temperature |
| power_consumption | sensor.yutai_cn_1169887446_fsov8m_electric_power_p_4_2 |

### A1 Mini (小黑奴)
| 配置项 | 实体 |
|--------|------|
| chamber_temp | sensor.qjiang_cn_blt_3_1n7f0sntk4s01_002_temperature_p_2_1001 (环境温湿度计) |
| power_consumption | sensor.giot_cn_1164778814_v8icm_electric_power_p_4_2 |

---

## ✅ v5.1 修改记录

| 修改 | 说明 |
|------|------|
| 修复详情弹窗 | `this._render()` → `this.render()` |
| WiFi信号→功耗 | 实时监控面板 + YAML配置 `wifi_signal` → `power_consumption` |
| 时区修复 | 所有时间显示统一通过 `new Date()` 转本地时间 |
| 筛选确定按钮 | 筛选条件变更不实时触发，点击「确定」才执行 |
| 重置按钮 | 一键清空所有筛选条件 |
| 颜色筛选 | 自动提取历史记录中用过的颜色，下拉筛选，显示中文色名 |
| 多重筛选 | 状态 + 颜色 + 日期范围 + 搜索，AND逻辑 |
| 分页 | 每页20条，减少DOM节点，优化内存 |
| a1mini腔体温度 | 使用小黑奴打印机环境温湿度计温度 |
| 版本升级 | pa-v4.0-modern.js → pa-v5.1.js |
| 全部历史独立 | mode: history 独立视图，与打印机页签平级 |
| 去掉本机历史 | 删除本机历史Tab，仅保留合并的"全部历史" |
| mode配置 | stats=仅统计, history=仅历史, ''=默认含tab切换 |
| 条件渲染优化 | mode: stats时不渲染历史，mode: history时不渲染统计 |
| 全部历史增加颜色筛选 | 合并历史页增加颜色下拉筛选 |
| 全部历史增加分页 | 合并历史页增加分页控件，每页20条 |
