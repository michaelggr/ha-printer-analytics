# operateLog

- 时间：2026-03-27 04:06
- 操作类型：[修改]
- 影响文件：G:\dev\ha\ha\ha_export\configuration.yaml；G:\dev\ha\ha\ui-lovelace.yaml
- 变更摘要：亮灯统计切换为“今日/本周/本月=History Stats， 本年/总计=累计源”，并同步更新亮灯对比页实体引用。
- 原因：修复“总计小于本年”等口径不一致问题，统一统计链路。
- 测试状态：[待测试]

- 时间：2026-03-27 05:51
- 操作类型：[修改]
- 影响文件：G:\dev\ha\ha\ha_export\configuration.yaml；G:\dev\ha\ha\ui-lovelace.yaml
- 变更摘要：移除重复 	emplate 键，保留单一模板配置；亮灯页改为“今/周/月=history_stats 求和，本年/总计=累计源”。
- 原因：修复重复键导致的实体丢失（404）与统计口径不一致。
- 测试状态：[待测试]

- 时间：2026-03-27 06:12
- 操作类型：[修改]
- 影响文件：G:\dev\ha\ha\ha_export\configuration.yaml
- 变更摘要：修复 MQTT 空气传感器单位编码，HCHO 从非法单位改为 µg/m³。
- 原因：HA 报错 olatile_organic_compounds 与 mg/m³ 组合无效，且配置存在乱码。
- 测试状态：[待测试]

- 时间：2026-03-27 06:33
- 操作类型：[修改]
- 影响文件：G:\dev\ha\ha\ha_export\configuration.yaml；G:\dev\ha\ha\ui-lovelace.yaml
- 变更摘要：按备份回滚配置（移除 history_stats YAML 方案），仅保留 MQTT 单位修复；UI 同步回滚到稳定版。
- 原因：history_stats 在你的环境不支持 YAML 配置，避免继续引发集成报错。
- 测试状态：[待测试]

- 时间：2026-03-27 07:15
- 操作类型：[修改]
- 影响文件：G:\dev\ha\ha\ha_export\configuration.yaml；G:\dev\ha\ha\ui-lovelace.yaml
- 变更摘要：按可用方案重做亮灯统计：sensor.platform=history_stats 实现今/周/月，累计输入源+utility_meter实现年/总，并更新亮灯对比页实体映射。
- 原因：你的环境不接受顶层 history_stats: YAML，需要改为平台语法并兼容现有插件链。
- 测试状态：[待测试]
