# 打印分析卡片 - 修改记录

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
