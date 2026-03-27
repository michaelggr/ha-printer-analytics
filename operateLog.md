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

- 时间：2026-03-27 08:45
- 操作类型：[修改]
- 影响文件：G:\dev\ha\ha\ha_export\configuration.yaml
- 变更摘要：新增 logger.default: debug，为重启后的日志排查开启调试级别。
- 原因：配合本次重启抓取更详细的 HA 日志。
- 测试状态：[待测试]

- 时间：2026-03-27 09:05
- 操作类型：[修改]
- 影响文件：G:\dev\ha\ha\ha_export\configuration.yaml
- 变更摘要：移除亮灯累计 input_number 的 initial: 0，并将上限提升到 315360000 秒。
- 原因：修复重启后累计值归零，并避免总计/本年累计触达 24 小时上限。
- 测试状态：[待测试]

- 时间：2026-03-27 12:20
- 操作类型：[修改]
- 影响文件：G:\dev\ha\ha\automations.yaml；G:\dev\ha\ha\operateLog.md
- 变更摘要：恢复 8 条名字带“虚拟”的电视/音箱自动化，重新接入中枢网关虚拟事件触发。
- 原因：服务器当前 YAML 丢失该批自动化，但 .storage 仍保留自动化名称与 ID 痕迹，需要先恢复最小可用版本。
- 测试状态：[待测试]

- 时间：2026-03-28 09:24
- 操作类型：[修改]
- 影响文件：G:\dev\ha\ha\automations.yaml；G:\dev\ha\ha\operateLog.md
- 变更摘要：根据 HA 数据库中 automation_triggered/call_service 历史链路，将“虚拟”自动化动作从 media_player 方案修正为原按钮链路（机顶盒/音箱按钮）。
- 原因：用户反馈此前仅恢复名字，动作与旧配置不一致；需要按历史执行证据回填真实逻辑。
- 测试状态：[待测试]

- 时间：2026-03-28 00:28
- 操作类型：[修改]
- 影响文件：G:\dev\ha\ha\ui-lovelace.yaml；G:\dev\ha\ha\ha_export\configuration.yaml；G:\dev\ha\ha\operateLog.md
- 变更摘要：修复 UI 与实体显示名中文乱码；UI 回滚到稳定快照并修复打印历史区块中文名；同步修复配置中“最常访问区域/最长停留区域”模板中文键值。
- 原因：当前仪表盘与实体名出现大面积中文乱码，影响可读性与状态解释。
- 测试状态：[待测试]
