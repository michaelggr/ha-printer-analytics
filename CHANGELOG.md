﻿# 打印分析卡片 - 修改记录

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
