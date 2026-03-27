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

- 时间：2026-03-28 13:20
- 操作类型：[重构]
- 影响文件：G:\dev\ha\ha\automations.yaml；G:\dev\ha\ha\operateLog.md
- 变更摘要：将 automations.yaml 统一为新风格字段（triggers/conditions/actions），保持业务逻辑不变并同步到服务器后重载。
- 原因：避免新旧风格混用导致维护成本高、UI 回写风格反复变化。
- 测试状态：[待测试]

- 时间：2026-03-28 13:58
- 操作类型：[修改]
- 影响文件：G:\dev\ha\ha\automations.yaml；G:\dev\ha\ha\operateLog.md
- 变更摘要：将 8 条“虚拟事件”自动化统一为按 `triggers.attribute=事件名称 + to=具体值` 的触发模式，并将 `conditions` 清空；保留原动作链，`电视切直播` 继续保留 ACK 回写动作。
- 原因：减少插件重载带来的误触发，统一与 UI 编辑器当前保存风格一致。
- 测试状态：[待测试]

- 时间：2026-03-28 00:28
- 操作类型：[修改]
- 影响文件：G:\dev\ha\ha\ui-lovelace.yaml；G:\dev\ha\ha\ha_export\configuration.yaml；G:\dev\ha\ha\operateLog.md
- 变更摘要：修复 UI 与实体显示名中文乱码；UI 回滚到稳定快照并修复打印历史区块中文名；同步修复配置中“最常访问区域/最长停留区域”模板中文键值。
- 原因：当前仪表盘与实体名出现大面积中文乱码，影响可读性与状态解释。
- 测试状态：[待测试]

- 时间：2026-03-28 04:40
- 操作类型：[修改]
- 影响文件：G:\dev\ha\ha\configuration.server.verify2.yaml；G:\dev\ha\ha\configuration.server.finalcheck.yaml；G:\dev\ha\ha\operateLog.md
- 变更摘要：分两轮清理 configuration.yaml 中注释与显示名称乱码，并回传服务器；保留实体 ID、触发条件与动作逻辑不变。
- 原因：侧边栏标题已修复后，配置文件其余中文注释/名称仍有大量历史乱码，影响可读性与维护。
- 测试状态：[待测试]

- 时间：2026-03-28 05:06
- 操作类型：[修改]
- 影响文件：G:\dev\ha\ha\_server_configuration_after_fullfix.yaml；G:\dev\ha\ha\_server_ui_after_fullfix.yaml；G:\dev\ha\ha\_server_configuration_verify_fullfix.yaml；G:\dev\ha\ha\_server_ui_verify_fullfix.yaml；G:\dev\ha\ha\operateLog.md
- 变更摘要：对服务器 configuration.yaml 与 ui-lovelace.yaml 执行逐行全量中文乱码修复（含 name/title/state 文本与注释），上传后回读校验为 0 残留。
- 原因：用户要求“每一行都检查”，此前仍存在多处漏网乱码（尤其 UI 文案与单位文本）。
- 测试状态：[待测试]

- 时间：2026-03-28 06:07
- 操作类型：[修改]
- 影响文件：G:\dev\ha\ha\backups\automations.yaml.20260328_060648.pre-add-ack-all.server.bak；G:\dev\ha\ha\operateLog.md
- 变更摘要：为 8 条“虚拟事件”自动化统一补齐“执行完成 ACK 虚拟事件”末尾动作；原已存在 ACK 的“虚拟事件电视切直播”保持不变。
- 原因：降低插件重载重放时的误判风险，通过每次执行后上报唯一 ACK（含时间戳）标记完成态。
- 测试状态：[已测试]

- 时间：2026-03-28 06:12
- 操作类型：[修改]
- 影响文件：G:\dev\ha\ha\backups\automations.yaml.20260328_061201.pre-rename-mobile-tv.server.bak；G:\dev\ha\ha\backups\automations.yaml.20260328_061243.pre-fix-mobile-prefix.server.bak；G:\dev\ha\ha\operateLog.md
- 变更摘要：将 8 条“虚拟事件”自动化名称统一加前缀“【移动电视】”，并修复首次写入时前缀被错误保存为问号的问题。
- 原因：按用户要求为同类自动化增加统一标识，便于筛选和识别。
- 测试状态：[已测试]

- 时间：2026-03-28 06:17
- 操作类型：[删除]
- 影响文件：G:\dev\ha\ha\backups\automation.82883509159345bdbc715990d3954e71.20260328_061739.pre-delete.json；G:\dev\ha\ha\operateLog.md
- 变更摘要：删除自动化“[亮灯] 每日重置所有灯亮灯时长（已停用）”，并先导出该条配置备份。
- 原因：该自动化当前处于停用状态，按用户要求清理不再使用项。
- 测试状态：[已测试]

- 时间：2026-03-28 06:23
- 操作类型：[修改]
- 影响文件：G:\dev\ha\ha\ha_export\configuration.yaml
- 变更摘要：将11个亮灯累计input_number上限由315360000提升至3153600000（秒）
- 原因：避免长期运行达到上限后累计停滞
- 测试状态：[待测试]
