# Printer Analytics（打印机分析）

在 Home Assistant 中追踪和分析你的 3D 打印机数据。与 Bambu Lab 打印机（P2S、A1 Mini 等）通过 `bambu_lab` 集成无缝协作。

## 功能特性

- **打印历史追踪** - 完整的打印记录，包含任务名、层数、喷嘴类型、热床类型、耗材等
- **时间维度统计** - 总打印次数、成功率、平均时长、能耗统计
- **周期统计** - 7天和30天聚合数据
- **内置 Lovelace 卡片** - 精美的图表和可视化，无外部依赖
- **自动封面图** - 自动下载并显示打印封面图
- **智能快照抓取** - 抓取前自动打开舱内灯，抓取后恢复原状态
- **智能任务名** - 自动区分模型名和参数配置名，从实体历史中捕获模型名
- **自动发现** - 自动检测 `bambu_lab` 集成的打印机实体
- **多打印机支持** - 实时监控面板支持打印机切换按钮
- **双语界面** - 支持中英文

## 支持的打印机

- Bambu Lab P2S
- Bambu Lab A1 Mini
- 其他打印机可通过自定义配置支持

## 安装

### HACS 安装（推荐）

1. 在 Home Assistant 中打开 HACS
2. 进入集成
3. 搜索 "Printer Analytics"
4. 点击安装

### 手动安装

1. 将 `printer_analytics` 文件夹复制到 `custom_components` 目录
2. 重启 Home Assistant

## 配置

### 通过 UI 配置

1. 进入 设置 → 设备与服务 → 添加集成
2. 搜索 "Printer Analytics"
3. 配置打印机名称和打印状态实体

### 配置项

| 选项 | 说明 | 必填 |
|------|------|------|
| 打印机名称 | 打印机的显示名称 | 是 |
| 打印状态实体 | 打印状态传感器实体（如 `sensor.p2s_xxx_print_status`） | 是 |
| 功率实体 | 功率传感器实体 | 否 |
| 能耗实体 | 能耗传感器实体 | 否 |
| 腔体温度实体 | 腔体温度传感器实体 | 否 |

## Lovelace 卡片

安装后，集成会自动创建仪表板。在侧边栏的"打印机分析"中访问。

### 手动卡片配置

```yaml
type: custom:printer-analytics-card
title: "打印机分析"
print_history: sensor.p2s_p2s_da_yin_li_shi
print_status: sensor.p2s_p2s_da_yin_zhuang_tai
current_task: sensor.p2s_xxx_task_name
print_progress: sensor.p2s_xxx_print_progress
nozzle_temp: sensor.p2s_xxx_nozzle_temperature
bed_temp: sensor.p2s_xxx_bed_temperature
```

## 服务

集成提供以下服务：

| 服务 | 说明 |
|------|------|
| `printer_analytics.refresh_stats` | 刷新统计数据 |
| `printer_analytics.reset_history` | 重置打印历史 |
| `printer_analytics.delete_history_records` | 删除指定的历史记录 |
| `printer_analytics.backfill_cover_images` | 补全缺失的封面图 |
| `printer_analytics.backfill_snapshots` | 补全缺失的打印快照 |

## 更新日志

### v5.11.0 (2026-05-20)

- **修复**：线程安全 - `async_write_ha_state` 改为通过事件循环正确调度，消除 11000+ 条警告
- **修复**：识别 `PRINT_STATUS_FAILED`（"failed"）状态，与 "fail" 一样计入失败统计
- **修复**：快照下载连续失败3次后停止重试，不再无限重试刷日志
- **修复**：能耗 delta=0 不再误报为"异常"
- **修复**：智能任务名捕获 - 监听 `task_name` 实体变化，在打印开始前锁定模型名
- **修复**：历史反查取最后一个（最接近打印开始的）非参数描述值，避免取到上一次打印的模型名
- **新增**：快照抓取前自动打开舱内灯，抓取后恢复原状态
- **新增**：实时监控面板标题处增加打印机切换按钮
- **新增**：自动发现 `chamber_light` 实体

### v5.10.9 (2026-05-19)

- 修复缺失的 `get_float_state`/`get_entity_attr` 公共接口
- 统一发布版本号

## 常见问题

### 找不到实体

确保 `bambu_lab` 集成已正确配置且打印机在线。

### 卡片不显示

确保 `pa-v5.11.js` 资源已加载到 Lovelace 配置中。使用 Ctrl+Shift+R 清除浏览器缓存。

### 摄像头快照失败（黑屏）

- 检查打印机摄像头是否可访问：在 HA 中查看摄像头实体，确认能看到实时画面
- 如果打印机 IP 变更，需要重新配置 Bambu Lab 集成并重启 Home Assistant
- 舱内灯自动开关功能需要发现 `chamber_light` 实体

### 任务名显示参数配置名而非模型名

这通常发生在集成启动时打印已经开始的情况。智能捕获系统会在下次打印时自动解决。对于已有记录，可使用 `backfill_cover_images` 服务补全。

## 支持

- 问题反馈：[GitHub Issues](https://github.com/michaelggr/ha-printer-analytics/issues)
- 文档：[Wiki](https://github.com/michaelggr/ha-printer-analytics/wiki)

## 许可证

MIT License
