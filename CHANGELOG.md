﻿﻿﻿﻿﻿﻿﻿# 打印分析卡片 - 修改记录

## 新集成：Utility Tracker v0.1.0 (2026-10-27)

| 类型 | 内容 | 涉及文件 |
|------|------|----------|
| 功能 | 新增能源账单监控集成,统一从 state_grid (SGCC 电费) + crcgas (华润燃气) 抓数据,持久化到 MariaDB。数据库含 2 张表: `utility_records` (日/月用量费用, 含峰谷平尖/三阶梯) + `account_snapshots` (账户余额快照),通过 UNIQUE KEY 幂等 upsert | custom_components/utility_tracker/ |
| 功能 | 配置文件流式 UI,支持 MariaDB 连接参数 + 数据源开关 + 同步间隔 (1-24h), 提交时调 `async_test_connection` 验证 | config_flow.py |
| 功能 | 5 个统计实体: last_sync / total_records / db_status / electricity_this_month / gas_this_month | sensor.py |
| 功能 | 服务: `utility_tracker.sync_now` 手动同步, `utility_tracker.backfill_history` 历史回填 | services.yaml, __init__.py |
| 功能 | crcgas 历史 JSON 账单自动回填到 MariaDB (兼容负数退款) | coordinator.py `_backfill_gas_history` |
| 看板 | 新增能源账单 dashboard `ui-energy.yaml`,含 4 个 view (概览/电费/燃气费/深度分析),已注册到 configuration.yaml | ui-energy.yaml, configuration.yaml#L77-82 |
| 测试 | 21 个单元测试,覆盖 `_safe_float` / `bill_month_to_date` / SGCC daily_history 映射 / crcgas 账单映射 / SQL 字段一致性 | tests/test_utility_tracker.py |
| 部署 | MariaDB Add-on (core_mariadb v3.0.1) 已安装配置: databases=[homeassistant, utility_bills], 用户 ha_utility (密码 ha_utility_pwd_2026), 自动建表 2 张 | (HA Add-on) |
| 部署 | Utility Tracker 集成已通过 UI 配置连接 MariaDB,首同步写入 141 条记录 (电费日数据 122 条 + 月数据 18 条 + 燃气月数据 1 条) | config_entries |
| 部署 | Grafana Add-on (a0d7b954_grafana v13.2.4) 已安装, 配置 MySQL 数据源连 core-mariadb:3306/utility_bills, 创建「能源账单监控」看板 (10 面板: 本月电费/燃气费/本年总费用 + 电费月度趋势/日用量/峰谷平 + 燃气月度费用/用量 + 电气对比) | (HA Add-on) |
| 看板 | ui-energy.yaml「深度分析」view 已替换为 Grafana iframe 嵌入 (kiosk 模式) | ui-energy.yaml#L417-427 |
| 修复 | crcgas 把欠费账单记为负数 (如 -49.99 元 / -19.76 m³),业务上应为正数应缴金额。新增 `_abs_or_none` 工具函数,当月账单与历史回填两处写入点前对 `charge`/`usage_amount` 取绝对值 | coordinator.py#L255-257, L331-333, L359-361 |
| 测试 | 燃气账单映射新增 3 个用例:负数欠费取绝对值 / 正数账单不受影响 / 零值账单不受影响 | tests/test_utility_tracker.py#L198-217 |
| 修复 | `electricity_this_month` / `gas_this_month` 永远 unknown 的 bug:两个 sensor 是 CoordinatorEntity (默认 should_poll=False), `async_update` 不会被调用,`_value` 永远 None。改为在 `_async_update_data` 末尾查询并放入 stats dict,sensor 从 `coordinator.data` 读取 | coordinator.py#L77-84, sensor.py#L115-151 |
| 测试 | 新增 TestCoordinatorDataKeys 3 个用例: stats dict 含月度费用 key / 空 data 时返回 None / 缺 key 时返回 None | tests/test_utility_tracker.py#L254-286 |
| 部署 | 重启 HA 使 sensor.py/coordinator.py 修改生效 (reload 不重载 Python 模块) | (HA 重启) |
| 看板 | 电费 view 顶部 2 张「应交」卡片(永远 unknown, 户号无欠费 API 不返回)替换为「本月用电」卡片 | ui-energy.yaml#L211-244 |

## 新集成：CTM电信 china_telecom v1.1.7 (2026-10-27)

| 类型 | 内容 | 涉及文件 |
|------|------|----------|
| 功能 | 新增中国电信话费/流量/语音监控集成（来源 github.com/hlhk2017/ChinaTelecomMonitor-Homeassistant-Integration），共 18 个传感器：账户余额、本月消费、流量总量/已用/剩余/超量、通用与专用流量、流量使用率、通话总量/已用/剩余/使用率、积分、更新时间 | custom_components/china_telecom/ |
| 配置 | configuration.yaml 新增 `china_telecom` 导入段（手机号 + 服务密码），并注册 CTM 卡片资源 `/china_telecom/ctm-telecom-card.js` | configuration.yaml |
| 修复 | 电信 2026 风控升级后登录返回 3006「设备未信任」，需通过 telecom.nufe.ccwu.cc 短信授权获取 DeviceId 并写入集成选项 | (集成选项) |
| 说明 | 首次登录 token 位于 `responseData.data.loginSuccessResult.token`，非 `data.token` | telecom_class.py |

## 清理老家用电残留 (2026-10-27)

| 类型 | 内容 | 涉及文件 |
|------|------|----------|
| 清理 | 删除 24 个老家/废弃 utility_meter 条目（小黑奴/大黑奴/豆浆机/烤箱/洗衣机周期计量）及 8 个老家空调计量，仅保留新家设备 | utility_meter.yaml |
| 清理 | 删除 templates.yaml 中 70 个引用已删实体的残留模板块（含 *-corrected、*-fixed 等重复定义），文件从 2076 行缩至 1495 行 | templates.yaml |
| 修复 | home_*_total_v2 只统计新家设备（电脑/NAS/取暖器/小打印机），电费换算 0.6 元/kWh | templates.yaml |
| 修复 | 今日总用电/历史累计/本周用电改为引用 home_daily_total_v2、li_shi_zong_gong_hao_2、home_weekly_total_v2 | ui-lovelace.yaml |
| 修复 | 今日/本月/本年电费卡片改用 home_daily/monthly/yearly_cost_v2 | ui-lovelace.yaml |
| 修复 | 打印机累计用电引用修正（integration 传感器重名产生的 xiao_da_yin_ji_lei_ji_yong_dian 实体） | utility_meter.yaml |
| 修复 | sensor.yaml 删除已消失的大打印机(台电) integration，燃气标签误命名条目改为「取暖器累计用电」并补 unique_id | sensor.yaml |
| 修复 | 修复 templates.yaml 中 34 处 UTF-8 损坏字符（卫生间/元/亮灯等），消除模板渲染报错 | templates.yaml |
| 修复 | 通过 WS 实体注册表删除 143 个失效模板/计量实体，重启后无残留 | (实体注册表) |

## 新集成：国家电网 state_grid v0.10.0 (2026-10-27)

| 类型 | 内容 | 涉及文件 |
|------|------|----------|
| 功能 | 新增国家电网集成（来源 github.com/stevenjoezhang/hass-state-grid）：网上国网 App API 接入，支持余额/日用电/月账单/年累计等 18 个传感器，支持两个绑定户号 | custom_components/state_grid/ |
| 修复 | gmssl 依赖 vendored 到 `_vendor/gmssl/`（HAOS 容器无法 pip install gmssl），crypto.py 添加 import fallback | custom_components/state_grid/crypto.py |
| 修复 | manifest.json 移除 gmssl 依赖，只保留 cryptography | custom_components/state_grid/manifest.json |
| 修复 | `__init__.py` 首次 refresh 失败不阻塞 setup（try/except 包裹 coordinator.async_config_entry_first_refresh） | custom_components/state_grid/__init__.py |
| 修复 | `sensor.py` 支持 coordinator 空数据时从 config_entry 预创建实体（避免 setup 后无实体） | custom_components/state_grid/sensor.py |
| 功能 | 新增 Lovelace「国家电网」视图：两个户号各显示余额/本月/昨日/上月/本年 + 7 天用电趋势图 | ui-lovelace.yaml |
| 优化 | 「国家电网」视图布局重构：原 3 列 entity 卡片数字被截断，改为 2 列大字号 tile 卡片（8 项/户号），并新增两户号 7 天用电对比图 | ui-lovelace.yaml |
| 功能 | 首页新增「国家电网」导航按钮 + 「用电概览」卡片（两户号余额、昨日用电，点击行跳转详情页） | ui-lovelace.yaml |
| 修复 | 7 天用电图原用 HA 状态历史，刷新间隔 12h 导致阶梯失真、刚接入时无历史；改为 apexcharts-card 直读 API `daily_history` 真实日数据 | ui-lovelace.yaml |
| 修复 | `daily_history` 末尾含 API 返回的未来日期空值（当月 1 号~月末），直接取末 7 条会得到空数据；data_generator 增加 null/空串/NaN 过滤 | ui-lovelace.yaml |
| 优化 | 户号标题显示 `latest_date`（数据截至日），避免 T+1 延迟被误读为"昨日" | ui-lovelace.yaml |

## 新集成：crcgas v2.1.0 (2026-10-27)

| 类型 | 内容 | 涉及文件 |
|------|------|----------|
| 功能 | 新增华润燃气集成（来源 github.com/C3H3-AI/ha-crcgas v2.1.0）：抓取微信小程序 wmp-svc.crcgas.com 账单/用气量/阶梯气价，48 个传感器，支持能源面板历史注入；需在配置流程中填入抓包获取的 refresh-token、bo-token、wxCode | custom_components/crcgas/ |
| 功能 | 新增华润燃气统计卡片前端资源（年度对比、阶梯进度） | www/community/crcgas-card/ |

## v5.24.0 (2026-07-11)

| 类型 | 内容 | 涉及文件 |
|------|------|----------|
| 功能 | 打印结束后自动验证模型名：从 HA task_name 传感器历史中查找打印开始时的真实名称，若与记录不一致则自动纠正 | print_tracker.py#L304-373 |
| 修复 | 延迟模型名查找逻辑增加 task_id 匹配验证：当 gcode_task_id 与传感器值不匹配时跳过使用历史模型名，防止继承上一个打印的旧名称 | print_tracker.py#L1026-1050 |
| 修复 | 修复大量历史记录模型名错误（手动从 HA 历史记录中逐条修正最近20条及部分更早记录） | 22E8BJ5A2401765_2026.json |

## v5.23.0 (2026-06-07)

| 类型 | 内容 | 涉及文件 |
|------|------|----------|
| 修复 | Cloud 同步后不补封面图：触发条件从 `added > 0` 改为 `added > 0 or merged > 0`（合并的记录也需要补图） | coordinator.py#1836 |
| 修复 | `_download_synced_covers` 改用 `full_scan=True` 全量扫描补图（之前只处理内存50条） | coordinator.py#1859 |
| 功能 | `backfill_cover_images` 新增 `full_scan` 参数，支持从文件读取全量记录批量下载封面图 | image_manager.py#527 |
| 功能 | 新增 `_load_all_records` / `_save_all_records` 辅助方法，支持全量记录的文件读写 | image_manager.py#596 |
| 修复 | `full_scan` 模式禁止 HA 实体回退（实体只返回当前打印封面，导致历史记录全部相同） | image_manager.py#592 |
| 修复 | 跳过 `/api/image_proxy/` 内部 URL（无法 HTTP 下载，之前回退到实体获取错误封面） | image_manager.py#589 |
| 修复 | 新增批量重复检测：同一图片被超过3条记录使用时自动视为默认图并删除 | image_manager.py#598 |
| 修复 | `backfill_cover_images` 手动服务调用改为 `full_scan=True` 全量模式 | __init__.py#547 |
| 修复 | **Cloud 同步合并时强制覆盖** `cover_image_url`/`task_name`/`design_id` 等字段（本地捕获的 HA 内部 URL 和配置名不再阻止 Cloud 真实数据写入） | coordinator.py#1810,1899 |

## v5.22.0 (2026-06-07)

| 类型 | 内容 | 涉及文件 |
|------|------|----------|
| 修复 | 封面图全部显示相同占位图：Bambu Cloud 默认占位图哈希加入检测集合，阻止保存 | image_manager.py#30 |
| 修复 | `detect_placeholder_images` 自动删除占位图文件（之前只检测不删除） | image_manager.py#40 |
| 修复 | `_clean_invalid_cover_refs` 全量清理指向不存在文件的 cover_image_local 引用 | coordinator.py#305 |
| 修复 | `backfill_cover_images` 优先用 CDN URL HTTP 下载（之前优先用 HA 实体，导致历史记录都用当前封面） | image_manager.py#537 |
| 修复 | `_download_cover_image` 新增 `prefer_http` 参数，跳过 HA 实体直接 HTTP 下载 | image_manager.py#227 |
| 优化 | `async_import_history` 导入后自动全量去重 | coordinator.py#1660 |

## v5.21.0 (2026-06-07)

| 类型 | 内容 | 涉及文件 |
|------|------|----------|
| 修复 | 重复记录去重失效：`_dedup_history_records` 改为从文件读取全量数据（原来只读内存缓存50条） | coordinator.py#476 |
| 修复 | `_dedup_history_records` 中 `_extract_year_from_end_time` 返回 int 但代码调用 `.isdigit()` 导致 AttributeError | coordinator.py#537 |
| 修复 | `_is_duplicate_record` 时区比较：双候选 UTC 比较，支持无时区旧格式与 UTC ISO 格式的匹配 | coordinator.py#1400 |
| 修复 | `_parse_time` 丢失时区信息：返回 UTC ISO 格式替代 `%Y-%m-%d %H:%M` | bambu_cloud.py#271 |
| 功能 | 新增 WS 命令 `printer_analytics/dedup_history` 手动触发去重 | __init__.py#1038 |
| 优化 | 去重逻辑移至 `_load_history` 中独立执行，带异常保护 | coordinator.py#288 |

## v5.20.0 (2026-06-04)

| 类型 | 内容 | 涉及文件 |
|------|------|----------|
| 功能 | V2 紧凑布局设为默认监控面板，移除 V1/V3/原始版代码和切换按钮 | pa-v5.11.js |
| 功能 | 多 AMS 支持：从 AMS1（4托盘）扩展到 AMS1~4（16托盘），多 AMS 时显示编号分隔 | pa-v5.11.js |
| 功能 | 摄像头按钮改为文字按钮「📷 摄像头」，打开时按钮亮起（渐变蓝紫色 active 状态） | pa-v5.11.js |
| 功能 | 摄像头视图打开/关闭过渡动画（max-height + opacity 平滑切换，0.4秒展开/收起） | pa-v5.11.js |
| 功能 | 任务名手机端跑马灯：CSS 动画 + 两端渐隐遮罩 + 起止暂停缓冲 | pa-v5.11.js |
| 功能 | 摄像头按钮 toggle 行为：再次点击同一打印机可关闭摄像头视图 | pa-v5.11.js |
| 修复 | 摄像头按钮点击事件与打印机切换按钮冲突：camera-btn 排除 monitor-switch-btn 事件处理 | pa-v5.11.js |
| 修复 | 统计分析页打印记录点击无法弹出详情：统一 recordId 生成逻辑（end_time+printer_serial+task_name 组合键） | pa-v5.11.js |
| 修复 | 统计分析页无限刷新循环：_checkBambuStatus 不再强制清缓存和调 updateData | pa-v5.11.js |
| 修复 | Bambu Cloud API 返回非 JSON Content-Type：3处 resp.json() 改为 resp.json(content_type=None) | bambu_cloud.py |
| 修复 | check_token 网络异常时不清除 Token，返回三态（valid/expired/unknown） | bambu_cloud.py |
| 优化 | 摄像头按钮样式与打印机切换按钮一致（同等大小+背景） | pa-v5.11.js |
| 优化 | 提取 _initCameraStream 方法，复用摄像头流初始化逻辑 | pa-v5.11.js |

---

## v5.17.1 (2026-06-02)

| 类型 | 内容 | 涉及文件 |
|------|------|----------|
| 修复 | 打印详情点不开：_getAllMergedRecords 返回的记录 id 为 null，新增 _findRecordById 优先从 WS 数据查找 | pa-v5.11.js |
| 修复 | 历史记录丢失：save_history 直接覆盖文件导致内存缓存外的旧记录丢失，改为合并写入 | storage.py |
| 修复 | 重置历史不清空文件：async_reset_history 清空内存但文件保留，新增 clear_all_history_files 同时清空 | coordinator.py, storage.py |
| 修复 | _yearly_stats 计数不准：只统计内存记录数，改为使用合并后的实际记录数 | storage.py |
| 修复 | 删除与保存竞态写入：删除不再单独写文件，改为 _pending_delete_ids 标记由 save_history 统一排除 | storage.py, coordinator.py |
| 修复 | _save_year_data 迁移直接覆盖：改为调用 _save_year_file 合并写入 | storage.py |
| 修复 | BOM 字符导致集成加载失败：移除 manifest.json 和 pa-v5.11.js 的 BOM | manifest.json, pa-v5.11.js |

---

## v5.17.0 (2026-05-28)

| 类型 | 内容 | 涉及文件 |
|------|------|----------|
| 重构 | 提取 match_record_filter() 统一筛选逻辑，消除 __init__.py 和 storage.py 约70行重复代码 | utils.py, __init__.py, storage.py |
| 重构 | 提取 _collect_task_name/_collect_cover_image/_collect_print_metadata 复用方法，消除 on_print_start 约80行重复代码 | print_tracker.py |
| 重构 | 提取 _detect_ams_usage/_detect_slice_mode 辅助方法 | print_tracker.py |
| 配置 | CI 流水线优化：HACS 验证和 hassfest 并行运行，新增 push 到 main 触发，移除自动 Release | .github/workflows/build.yml |
| 配置 | hacs.json 移除 icon 字段（HACS 不允许），修复拼写错误 | hacs.json |

---

## v5.14.1 (2026-05-27)

| 类型 | 内容 | 涉及文件 |
|------|------|----------|
| 修复 | 打印结束事件丢失导致记录未保存：添加3分钟周期性健康检查兜底机制，检测 current_print 卡住并强制结束 | coordinator.py#L543-576 |
| 修复 | 手动补录5月26日打印记录（A01：适配5mm厚度洞洞板） | 服务器历史文件 |

---

## v5.14.0 (2026-05-26)

| 类型 | 内容 | 涉及文件 |
|------|------|----------|
| 修复 | 模型名捕获：idle 状态下只关注 task_name 变化事件，不再缓存静态值（避免缓存上一次打印的项目名） | coordinator.py#L531-598 |
| 修复 | 模型名→项目名过渡捕获：当 task_name 从模型名变为不同的非参数描述值时，保留模型名 | coordinator.py#L580-586 |
| 修复 | 打印结束时清除预缓存，避免上一次打印的模型名污染下一次 | print_tracker.py#L1195-1197 |
| 功能 | 新增 `_pre_print_project_name` 字段，记录项目名与模型名区分 | coordinator.py#L80 |
| 功能 | `_collect_task_name` / `on_print_start` 集成项目名识别和 gcode 回退 | print_tracker.py#L147-227, 1046-1088 |
| 功能 | 新增 `gcode_file_downloaded` 实体发现与映射 | const.py#L59, entity_discovery.py#L130 |
| 功能 | 新增 `extract_model_from_gcode_filename` 工具函数 | utils.py#L29-70 |
| 文档 | README 更新最新功能、更新日志、QQ交流群 | README.md |

---

## v5.13.0 (2026-05-25)

| 类型 | 内容 | 涉及文件 |
|------|------|----------|
| 功能 | 切片模式新增 auto_repeat（自动重复），统计图表和导入模板同步更新 | pa-v5.11.js, storage.py |
| 功能 | 新增全局删除 WS 命令，支持删除已删除打印机的记录 | __init__.py#L825-897 |
| 功能 | 删除后即时更新 UI，无需手动刷新 | pa-v5.11.js#L3154-3168 |
| 修复 | 打印机筛选不生效（_source_serial 未参与匹配） | __init__.py#L142-151, storage.py#L358-366, pa-v5.11.js#L5178 |
| 修复 | 删除记录不生效（_get_coordinator_from_call 无法匹配 print_status_entity） | __init__.py#L675-680 |
| 修复 | 删除记录不生效（内存缓存仅50条，旧记录无法删除） | coordinator.py#L923-967 |
| 修复 | query_all_history 中 _printer_name 使用错误的 printer_serial 查找 | __init__.py#L784-801 |
| 修复 | BOM 字符导致集成加载失败（print_tracker.py 双重 BOM） | 服务器文件 |

---

## v5.12.1 (2026-05-25)

| 类型 | 内容 | 涉及文件 |
|------|------|----------|
| 功能 | 新增 design_id 字段（MakerWorld模型ID），详情弹窗可点击跳转 MakerWorld | coordinator.py#L389, print_tracker.py#L1040, pa-v5.11.js#L5960 |
| 功能 | 实现 async_import_history 导入方法，支持向后兼容合并（序列号+结束时间±2分钟判定重复，仅填充空字段） | coordinator.py#L1052-1117 |
| 功能 | 实现 async_backup_history 备份方法 | coordinator.py#L1119-1123 |
| 功能 | 云端反查任务名时同步补全 design_id | coordinator.py#L882-885 |
| 功能 | CSV导出新增模型ID列 | pa-v5.11.js#L5306,5355 |
| 功能 | 导入模板更新所有新字段（design_id、printer_serial、ams_used、slice_mode等） | pa-v5.11.js#L5447-5525 |
| 功能 | 导入页面添加合并规则说明文字 | pa-v5.11.js#L5407-5409 |
| 修复 | 移除不可哈希的 _DEFAULT_VALUES frozenset（[]和{}不可放入frozenset，导致集成加载失败） | coordinator.py#L968 |

---

## v5.12.0 (2026-05-24)

| 类型 | 内容 | 涉及文件 |
|------|------|----------|
| 功能 | 打印记录添加序列号唯一标识，筛选/导出/选择器改用序列号 | print_tracker.py, coordinator.py, sensor.py, storage.py, pa-v5.11.js |
| 功能 | 打印记录新增6个字段：AMS使用、多色打印、速度模式、准备时间、切片模式、超500g | print_tracker.py |
| 功能 | 准备时间自动计算（从打印开始到running状态的时间差） | print_tracker.py |
| 功能 | 切片模式自动判断（gcode路径含/data/为云端切片） | print_tracker.py |
| 功能 | 统计分析新增6个图表：多色占比、准备时间对比、切片模式分布、超500g占比、喷嘴尺寸分布、失败仓温分布 | statistics.py, pa-v5.11.js |
| 功能 | 准备时间统计使用IQR方法排除异常值 | statistics.py |
| 功能 | 筛选面板新增切片模式和重量筛选 | storage.py, pa-v5.11.js |
| 功能 | CSV导出新增6列：使用AMS、多色打印、速度模式、准备时间、切片模式、超500g | pa-v5.11.js |
| 功能 | 打印机选择器显示格式改为"序列号(名称)"，避免同型号重复 | pa-v5.11.js |
| 功能 | 实体发现添加serial_number和gcode_filename模式 | entity_discovery.py |
| 修复 | 添加缺失的query_history方法，修复前端只显示6条缓存记录 | coordinator.py |
| 修复 | 打印恢复机制：磁盘持久化+延迟颜色验证+能耗恢复+防重复触发 | print_tracker.py |
| 修复 | current_stage过渡方法推断模型名和项目名 | print_tracker.py |
| 修复 | 反查按钮使用current_stage过渡方法 | print_tracker.py, coordinator.py |
| 优化 | 已有记录自动补全multi_color和over_500g派生字段 | coordinator.py |

---

## v5.11.23 (2026-05-22)

| 类型 | 内容 | 涉及文件 |
|------|------|----------|
| 功能 | 外挂耗材支持：检测 externalspool_active 状态，自动切换显示外挂/AMS 耗材信息 | pa-v5.11.js#L3858 |
| 功能 | 添加 _findEntityBySuffix 辅助方法，按后缀模糊匹配实体 | pa-v5.11.js#L245 |
| 优化 | 当前耗材：类型文字颜色改为耗材颜色，换行显示 | pa-v5.11.js#L3971 |

---

## v5.11.22 (2026-05-22)

| 类型 | 内容 | 涉及文件 |
|------|------|----------|
| 优化 | 当前耗材：重量换行显示类型，类型文字颜色改为耗材颜色，去掉色块圆点 | pa-v5.11.js#L3971 |

---

## v5.11.21 (2026-05-22)

| 类型 | 内容 | 涉及文件 |
|------|------|----------|
| 修复 | 当前任务名显示"0"：e.task_name 未配置时 _getState(undefined) 返回"0"，添加存在性检查 | pa-v5.11.js#L3781 |
| 优化 | AMS 耗材盘精简：色块 36→20px，字体 13→10px，间距缩小，去掉悬停动画 | pa-v5.11.js#L1159 |

---

## v5.11.20 (2026-05-22)

| 类型 | 内容 | 涉及文件 |
|------|------|----------|
| 优化 | 监控面板精简：去掉喷嘴、缩小间距和字体 | pa-v5.11.js#L3714 |
| 修复 | 预计完成时间显示0：自动发现 end_time/remaining_time 实体，修复 remaining_time 单位为小时的问题 | pa-v5.11.js#L201 |
| 功能 | 当前耗材显示类型和颜色（从 active_tray 属性获取） | pa-v5.11.js |
| 功能 | 自动发现未配置实体（_discoverPrinterEntities） | pa-v5.11.js#L201 |

---

## v5.11.19 (2026-05-22)

| 类型 | 内容 | 涉及文件 |
|------|------|----------|
| 修复 | 摄像头自动发现优先匹配 camera 关键词实体，避免误匹配 cover_image | pa-v5.11.js#L186 |
| 优化 | image 类型摄像头自动刷新间隔从5秒缩短到2秒，更接近实时 | pa-v5.11.js#L236 |

---

## v5.11.18 (2026-05-22)

| 类型 | 内容 | 涉及文件 |
|------|------|----------|
| 功能 | 摄像头自动发现：从传感器实体ID提取设备前缀，匹配 camera/image 实体 | pa-v5.11.js#L156 |
| 功能 | 摄像头视图切换：点击📷按钮替换监控信息为摄像头画面，支持关闭返回 | pa-v5.11.js#L3478 |
| 功能 | camera 类型实时视频流：使用 ha-camera-stream 组件 | pa-v5.11.js#L3514 |
| 功能 | image 类型自动刷新：每5秒更新图片URL模拟实时画面 | pa-v5.11.js#L208 |
| 修复 | currentTask 未定义：替换为 displayTaskName | pa-v5.11.js |
| 修复 | _isParamDescription 未定义：添加方法实现 | pa-v5.11.js#L145 |

---

## v5.11.17 (2026-05-22)

| 类型 | 内容 | 涉及文件 |
|------|------|----------|
| 修复 | 实时监控渲染失败: _isParamDescription 未定义，添加方法实现 | pa-v5.11.js#L142 |

---

## v5.11.16 (2026-05-22)

| 类型 | 内容 | 涉及文件 |
|------|------|----------|
| 修复 | 实时监控渲染失败: currentTask 未定义，替换为 displayTaskName | pa-v5.11.js#L3906 |

---

## v5.11.15 (2026-05-21)

| 类型 | 内容 | 涉及文件 |
|------|------|----------|
| 功能 | 摄像头自动发现：从传感器实体ID提取设备前缀，匹配 camera/image 实体 | pa-v5.11.js |
| 功能 | 摄像头视图切换：点击摄像头按钮替换监控信息区域，支持关闭返回 | pa-v5.11.js |
| 功能 | P2S 实时视频流：使用 ha-camera-stream 组件替代静态图片 | pa-v5.11.js |
| 功能 | A1 Mini 实时画面：image 类型实体每5秒自动刷新模拟实时画面 | pa-v5.11.js |
| 修复 | 摄像头按钮不显示：正则表达式无法提取 a1mini_0300aa5a1600497 格式前缀 | pa-v5.11.js |
| 修复 | hass 对象访问错误：this.hass 改为 this._hass \|\| this.hass | pa-v5.11.js |
| 修复 | 摄像头视图切换后不刷新：_cameraViewPrinter 未加入数据快照比较 | pa-v5.11.js |
| 修复 | P2S 摄像头画面断裂(404)：区分 camera/image 类型使用正确 proxy 路径和 token | pa-v5.11.js |
| 修复 | 22个 BOM 字符导致页面乱码 | pa-v5.11.js |
| 修复 | ES 模块缓存问题：多次更新版本号强制刷新 | configuration.yaml |

---

## v5.11.7 (2026-05-13)

| 类型 | 内容 | 涉及文件 |
|------|------|----------|
| 修复 | fmtDur 箭头函数语法错误：改为多行函数体 | pa-v5.2.js |
| 修复 | replace 正则 $ 匹配失败：改为 split+join | pa-v5.2.js |
| 修复 | __init__.py UTF-8 BOM 字符 (U+FEFF)：移除 BOM 重新保存 | __init__.py |
| 修复 | 9个 BOM 字符导致页面乱码 | pa-v5.2.js |

---

## 记录规范

每次修改后按以下格式追加记录：

```
## vX.X.X (YYYY-MM-DD)

| 类型 | 内容 | 涉及文件 |
|------|------|----------|
| 类型 | 修改描述 | 文件名#行号(可选) |
```

**类型取值：**
- `功能` - 新增功能
- `修复` - Bug 修复
- `重构` - 代码重构（不改变行为）
- `优化` - 性能或体验优化
- `文档` - 文档更新
- `配置` - 配置文件变更
