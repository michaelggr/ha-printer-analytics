# 打印分析卡片 - 修改记录

## 深度分析页 Grafana 401 修复（ingress 会话 cookie）（2026-10-28）

| 类型 | 内容 | 涉及文件 |
|------|------|----------|
| 修复 | 深度分析页 iframe 一直 `401: Unauthorized`：`grafana-ingress-card` 只从 `addon/info` 取 `ingress_url` 就设 iframe.src，但 Supervisor ingress 用 **cookie** 鉴权（`ingress_session`），iframe 导航无法携带 `Authorization` 头，所以每次都被 HA ingress 拦截（连直接在新标签打开 ingress 地址也是 401） | www/grafana-ingress-card.js#L71-101 |
| 修复 | 卡片新增 `_ensureIngressSession()`：WS `supervisor/api` → `POST /ingress/session` 拿会话，再写 `document.cookie = ingress_session=...; path=/api/hassio_ingress; SameSite=Lax`，之后才设置 iframe.src | www/grafana-ingress-card.js#L75-91 |
| 优化 | 会话有有效期，卡片每 5 分钟静默续期 cookie（不重载 iframe，后续请求自动带新 cookie），`disconnectedCallback` 清理定时器防泄漏 | www/grafana-ingress-card.js#L49-69 |
| 配置 | 资源版本 `/local/grafana-ingress-card.js?v=1.2.0` → `v=1.3.0`（YAML resources 变更需重启 HA 生效）；顺带移除该 JS 的 UTF-8 BOM | configuration.yaml#L53, www/grafana-ingress-card.js |
| 验证 | 浏览器实测：补 cookie 前后 health 接口 401 → 200；重启后深度分析页 iframe 文档请求 200，Grafana 面板（本月电费/燃气费）正常渲染，无 401 | (服务器 + 浏览器) |
| 备注 | 同类问题影响所有 addon ingress 页面（MariaDB 等），根因是前端未建立 ingress 会话 cookie；`auth/sign_path` 签名路径对 ingress 无效，只有 `/ingress/session` 可行 | - |

## 房间视图按设备实际区域重排（2026-10-28）

| 类型 | 内容 | 涉及文件 |
|------|------|----------|
| 修复 | 客厅：移出「夕阳灯」`light.zbmesh_cn_2169826771_wy0a02_s_2_light`（区域=走廊）、「电子围栏」`sensor.ainice_cn_919824629_bt_occupancy_status_p_2_1`（走廊）、扫地机器人 `vacuum.xiaomi_cn_1215291301_qv41cn` 及电量（公卫干区）；扫地机移出后客厅「设备」分区为空，整段移除 | ui-lovelace.yaml#L296-330 |
| 修复 | 厨房「养生壶温度」`sensor.xiaomi_cn_2033456684_p1v2_temperature_p_2_11`（区域=餐厅）迁到餐厅视图；餐厅「电风扇」`fan.jipin_cn_2033277764_011_s_2_fan`（区域=北卧）迁到北卧视图 | ui-lovelace.yaml#L620-690 |
| 修复 | 走廊「总水阀」`cover.linp_cn_2079478044_ec1db_s_2_curtain`（区域=公卫干区）迁到卫生间公卫分区；走廊补入夕阳灯、电子围栏 | ui-lovelace.yaml#L745-825,L975-995 |
| 功能 | 按区域补卡片：北卧新增「新风空调」`climate.bei_wo_xin_feng_kong_diao`（同设备 `climate.212305751221743_climate` 为 unavailable 重复实体，未收录）、电风扇；主卧顶部新增「海信空调」`climate.hai_xin_kong_diao_climate` | ui-lovelace.yaml#L335-340,L525-540 |
| 说明 | 「全屋灯光」分组 `light.mijia_cn_group_2111912980119552000_group3_s_2_light` 区域登记为辅助区域「全屋灯光」，作为全屋总控保留在客厅视图，未迁移 | ui-lovelace.yaml#L302-305 |
| 验证 | YAML 解析通过、无 BOM；区域核对脚本不一致项 8 → 1（仅剩上述全屋灯光分组）；上传重启后 WS `lovelace/config` 确认各房间卡片就位，`system_log` 无新增 Lovelace 错误 | (服务器) |

## 电量计数器重置识别与量化抖动过滤（2026-10-28）

| 类型 | 内容 | 涉及文件 |
|------|------|----------|
| 修复 | 带电量统计的插座/电表会把累计电量周期性清零重计，原 `energy_kwh = MAX - MIN` 算法在计数器小时内重置时会把整小时电量算成 0 或负数，造成电量凭空丢失（实测今日全设备少算 3.33 kWh，小黑奴丢 80%、电脑/NAS 各丢约 16%）。聚合改为按「计数周期」结算增量 | db.py#L346-433 |
| 修复 | 逐样本累加会把低分辨率读数抖动当成新增用电：实测北卧空调插座功率恒 0W，电量在 0/0.01 间规律抖动（今日 35 次回退），逐样本累加让它凭空记了 0.13 kWh/天；主卧空调插座 2W 记 0.15 kWh、南阳台洗衣机插座 1W 记 0.13 kWh（虚增 5~9 倍），6 个插座合计虚增约 0.74 kWh。改为跨窗口「末值 - 基线」口径，抖动不再重复计入 | const.py#L71-130 |
| 功能 | `sum_energy_deltas(values, prev_reading)` 定稿：①窗口内读数跌幅超 `ENERGY_RESET_TOLERANCE_KWH(0.011)` 且跌到前值一半以下才判清零，计入「清零前那段 + 清零后累计值」；②窗口开始前已清零则只计本窗口累计值；③读数单调不减 → 末值减基线全额计入（保护 0.0001 kWh 级高分辨率电表的微小真实增长，如 5W 设备 0.0003/h）；④存在回退 → 量化抖动，容差内归零 | const.py#L71-130 |
| 修复 | 容差取 0.011 而非 0.05：0.05 会放过 0.03 级的量化抖动，而 0.011 恰好大于一个 0.01 刻度，同时用「跌到前值一半以下」排除 1.00→0.98 这类小幅回退被误判清零（否则凭空多记 0.98 kWh） | const.py#L71-130 |
| 修复 | `device_power_daily` 聚合原先直接 `SUM(energy_kwh)` 且不过滤，会把同一台设备的日/周/月/年 8 张镜像表一起累加（电脑日电量被算成 11.08×7 kWh）。改为 Python 侧分组后按 `is_derived_energy_entity`/`is_excluded_energy_entity` 过滤，与 `async_sum_power_today` 同口径 | db.py#L435-496 |
| 优化 | 小时聚合把「本小时读数序列」与「上一小时末值基线」分开传给纯函数，基线只作参照点、不参与单调性判定；功率积分兜底（取暖器）逻辑保持不变 | db.py#L400-420 |
| 说明 | 计数器重置与读数抖动均为真机行为，已确认不是采样异常；本轮不回补历史小时行，今日已入库的旧口径行保持原样，从下一个完整小时起生效。低分辨率插座（0.01 kWh）的 <0.01 kWh 真实用电仍无法分辨，属硬件限制 | - |
| 测试 | `TestEnergyDeltaAccumulation` 扩到 15 个用例（等价 MAX-MIN、跨小时基线递增、中途重置、窗口前已清零、抖动不重复累计、抖动后继续增长、高分辨率微小增长、空/单点/单点带基线、容差内回退、小幅回退不误判清零、真重置、全零序列），该文件 120 个用例全部通过 | tests/test_utility_tracker.py |

## giot 耗电量单位纠正与功率积分兜底（2026-10-28）

| 类型 | 内容 | 涉及文件 |
|------|------|----------|
| 修复 | giot 系列「耗电量」实体 `power_consumption_p_4_1` 单位错标为 mWh（数值实际是 Wh），入库被低估 1000 倍，且与同设备「累计用电」重复计量。加入 `EXCLUDED_ENERGY_ENTITIES`：电脑电源 `1162942256`、NAS `1163256502`、小黑奴电源 `1164778814`、取暖器 `1162898415` | const.py#L110-116 |
| 功能 | 新增 `POWER_INTEGRATION_ENTITIES` 与 `is_power_integration_entity()`：取暖器无可用累计电量（累计用电 unknown、耗电量恒 0），聚合时改按 `AVG(power_w) × COUNT(*) × 采样间隔 / 60 / 1000` 估算 kWh | const.py#L113-124 |
| 修复 | `async_aggregate_power_hourly` 新增 `sample_minutes` 参数，energy_kwh 改为 CASE：有累计电量时取「末值 - 初值」，否则对积分名单走功率积分兜底（顺带修掉原 `sum(avg_w)/60*5` 估算逻辑未真正生效的问题） | db.py#L345-386、coordinator.py#L378 |
| 测试 | 新增 `TestPowerIntegrationFallback` 7 个用例（耗电量因单位错误被排除、真正 kwh 实体保留、取暖器走积分、其他 power 不走积分、满一小时采样、零功率与不满采样、量级自洽），该文件 105 个用例全部通过 | tests/test_utility_tracker.py |

## 能源看板电费口径改为最新用量估算（2026-10-28）

| 类型 | 内容 | 涉及文件 |
|------|------|----------|
| 优化 | 概览顶部问候 + 自住/出租两张「本月电费」卡，由 `utility_tracker_electricity_this_month_*`（DB 月账单口径，10 月账单未出时恒为 0）改为 `本月实时用电量 × 上月结算单价` 估算，副文本展示「度数 × 单价」 | ui-energy.yaml#L16-29,L100-118,L144-162 |
| 核对 | 6 个视图共 124 个实体引用全部存在、无失效 ID；插座类 11 个实体（yutai 系列、取暖器、小黑奴等）名称未变但设备离线，状态为 unknown，非页面配置问题 | ui-energy.yaml |
| 验证 | 模板渲染：自住 ¥102.67（184 度 × ¥0.558）、出租 ¥45.51（74.86 度 × ¥0.608）；WS `lovelace/config` 确认新配置已加载，`system_log` 无模板错误 | (服务器) |

## 自动化失效条目清理（2026-10-28）

| 类型 | 内容 | 涉及文件 |
|------|------|----------|
| 修复 | 删除 8 条电视/音响虚拟事件自动化（id `1774512472146`、`1774515470812`、`1774516117948`、`1774516169921`、`1774516581044`、`1774517032087`、`1774517122303`、`1774517227701`），其 `button.*`/`media_player.*` 实体早已不存在 | automations.yaml |
| 修复 | 删除大黑奴（P2S，已卖出）残留 3 处：`daheinu_exhaust_fan`（完成排气）、`ams_humidity_notification`（AMS 湿度通知）、`printer_completion_notification` 内的大黑奴播报分支 | automations.yaml |
| 清理 | WebSocket `config/entity_registry/remove` 移除注册表 11 条失效 automation 实体：8 条电视/音响、`da_yin_da_hei_nu_da_yin_wan_cheng_pai_qi`、`da_yin_ams_1_shi_du_da_yu_50_tong_zhi`、`qu_yu_mei_ri_zhong_zhi_fang_wen_yu_ting_liu_v2`（7 个 counter 已删，触发源不存在） | (实体注册表) |
| 验证 | `automations.yaml` 16 → 6 条；YAML 解析通过、34 个 Jinja 模板语法全部通过；`automation.reload` 后状态列表仅 6 个 automation 实体且全部 `on`，注册表同步剩 6 条 | (服务器) |

## CTM电信卡片恢复显示（2026-10-28）

| 类型 | 内容 | 涉及文件 |
|------|------|----------|
| 修复 | 集成故障期间卡片区块被整体注释隐藏（标注"暂时隐藏…相关实体全部 unavailable"），取消注释恢复：标题卡 + `custom:ctm-telecom-card` + 4 个指标 chips | ui-energy.yaml#L169-211 |
| 说明 | 编辑后 yaml 文件被写入 UTF-8 BOM，已清除；yaml 模式仪表盘需重启 HA 才重新读取配置 | ui-energy.yaml |
| 验证 | `energy-bills` → `overview` view 已含 `ctm-telecom-card`；设备 ID `88311b83…` 匹配，卡片 JS `/china_telecom/ctm-telecom-card.js` 返回 200（20486 字节）；18 实体全部可用 | (服务器) |

## CTM电信集成故障修复（2026-10-28）

| 类型 | 内容 | 涉及文件 |
|------|------|----------|
| 修复 | 18 个实体全部 `unavailable`、配置条目 `not_loaded`，根因是 `manifest.json` 含 UTF-8 BOM（U+FEFF），HA 的 `json.loads()` 解析失败 → 报 `Integration not found`。清除 BOM 后恢复，重启验证 18 实体全部出数、条目回到 `loaded` | custom_components/china_telecom/manifest.json |
| 修复 | `sensor.py` 同时带 BOM（编辑时被写入），一并清除 | custom_components/china_telecom/sensor.py |
| 修复 | 每次启动报 `Flow aborted: already_configured`：`async_setup` 未判断条目是否已存在，重复触发 import flow。改为按手机号比对已有条目后跳过 | __init__.py#L23-42 |
| 说明 | 排查要点：`/api/error_log` 在 HA 2026 已移除，改用 WebSocket `system_log/list` 取日志；`config_entries` 的 flow 命令已迁到 REST（`POST /api/config/config_entries/options/flow`） | (排查方法) |
| 验证 | 余额 18.54 元、本月消费 69.79 元、积分 1694、流量 100% 已超量 0.13 GB；系统日志无电信相关错误 | (服务器) |

## 虚拟事件实体全量迁移到新网关（2026-10-28）

| 类型 | 内容 | 涉及文件 |
|------|------|----------|
| 修复 | 中枢网关设备 ID 变更（`1175403807` → `1184711570`），批量替换 `automations.yaml` 中全部 10 处旧引用：`[系统] 中枢网关虚拟事件播报`、电视切台/音响音量等 9 条虚拟事件自动化、炒面检测蓝图的 `xiaomi_gateway_virtual_event` 输入 | automations.yaml#L8,24,44,64,81,89,109,124,139,154,454 |

## 新风空调改用插座计量（2026-10-28）

| 类型 | 内容 | 涉及文件 |
|------|------|----------|
| 修复 | 新风空调自带计量不准（自带实时功率 6W，实际插座为 0W），改用北卧空调插座 `sensor.yutai_cn_1207439820_fsov8m_*` 的功率与耗电量作为唯一来源；新增 `EXCLUDED_POWER_ENTITIES` / `EXCLUDED_ENERGY_ENTITIES` 显式排除名单与 `is_excluded_power_entity()` / `is_excluded_energy_entity()`，采集与查询双侧排除 `bei_wo_xin_feng_kong_diao_real_time_power`、`total_energy_consumption`、`current_energy_consumption` | const.py、coordinator.py#L314、db.py |
| 说明 | 「当前能源消耗」并非累计计数器，MAX-MIN 求增量本身无意义，一并排除 | const.py |
| 测试 | 新增 `TestExcludedDeviceMeter` 4 个用例（自带功率/电量被排除、北卧插座保留、其他设备不受影响），单测 141 个全部通过 | tests/test_utility_tracker.py |

**验证（重启后）**：`current_power` 184.0 W（raw 合计 190W 已扣除新风空调 6W），`power_today` 2.3634 kWh（扣除自带 0.07kWh），18 实体可用，`db_status=ok`。

## 功耗重复计量过滤（2026-10-28）

| 类型 | 内容 | 涉及文件 |
|------|------|----------|
| 修复 | `current_power` 虚高（363W → 199W）：PC 的 `PC CPU Package` 77.9W、`PC CPU IA Cores` 73.4W、`PC GPU` 28W 与整机插座 145W 重复累加，且 IA Cores 是 Package 的子集；新风空调 `压缩机功率` 5W 与其 `实时功率` 6W 重复。新增 `is_component_power_entity()`（关键词 cpu/gpu/cores/package/compressor/压缩机），采集与查询双侧过滤 | const.py (`is_component_power_entity` + `POWER_COMPONENT_KEYWORDS`)、coordinator.py#L308、db.py (`async_current_total_power`) |
| 修复 | `power_today` 成倍膨胀（46.7kWh → 2.43kWh）：同一设备的「日/周/月/年用电量」四张派生表与累计计数器同时求和，PC 组单项就贡献 6.12kWh × 7 条 ≈ 43kWh。新增 `is_derived_energy_entity()`（关键词 daily/weekly/monthly/yearly/today + 日/周/月/年用电量 + ri/zhou/yue/nian_yong_dian），`async_sum_power_today` 改为按 entity 分组后过滤再累加 | const.py (`is_derived_energy_entity` + `ENERGY_DERIVED_KEYWORDS`)、db.py (`async_sum_power_today`) |
| 优化 | 查询侧同时过滤，历史行不删除，修复当天立即生效，无需等旧采样过期 | db.py |
| 测试 | 新增 `TestDuplicateMeterFilter` 7 个用例（中文/英文派生表、今日耗电量、权威累计计数器反例、CPU/GPU/压缩机、整机与插座反例），单测 137 个全部通过 | tests/test_utility_tracker.py |

**验证数据（2026-10-28 20:00 重启后）**

| 指标 | 修复前 | 修复后 |
|------|--------|--------|
| `sensor.utility_tracker_current_power` | 363.3 W | 199.0 W |
| `sensor.utility_tracker_power_today` | 46.73 kWh | 2.43 kWh |

`power_today` 低于国网电表今日增量（11.23kWh）属预期：本统计只覆盖有计量插座/计数器的设备，冰箱、照明、空调等未计量负载不计入。

## 剩余时间播报改为最新实体 + 统一播报规则（2026-10-28）

| 类型 | 内容 | 涉及文件 |
|------|------|----------|
| 修复 | 虚拟事件实体更新为 `event.xiaomi_cn_1184711570_hub1_virtual_event_e_4_1`（原 `1175403807` 已失效，自动化此前无法触发） | automations.yaml#L169 |
| 修复 | 移除已售出大黑奴（P2S）的 `remaining_time` 逻辑，只播报小黑奴 | automations.yaml#L179 |
| 功能 | 文案补充打印进度，预计完成时间优先取 `end_time`，缺省时用 `now + remaining_time` 兜底 | automations.yaml#L181 |
| 功能 | 播报规则与完成通知一致：睡觉不播报；客餐厅/阳台/走廊有人用餐厅音箱（客厅或南阳台有人 80%，否则 50%），公卫干区有人用公卫音箱 | automations.yaml#L198 |

## 小黑奴排气自动化改造（2026-10-28）

| 类型 | 内容 | 涉及文件 |
|------|------|----------|
| 功能 | `[打印] 小黑奴打印完成打开排气` 改为「打印完成排气 3 分钟」（原 10 分钟），触发源补充 `pause → finish/failed` | automations.yaml#L319 |
| 功能 | 新增 `[打印] 小黑奴打印中排气散热/排毒`：环境温度 >30℃ 开排气、<28℃ 关（回差防抖）；耗材为 ABS/TPU 且北卧有人时强制开排气排毒，直到打印结束 | automations.yaml#L342 |
| 优化 | 删除完成排气自动化中引用已不存在实体（`sensor.linp_cn_blt_3_1n20sdaek4k01_*`）的「排气完成」播报死代码 | automations.yaml |
| 功能 | 完成播报文案由「开始排气10分钟」改为「开始排气3分钟」 | automations.yaml#L243 |

## 区域停留热力图改为「小时时段 × 区域」(2026-10-28)

| 类型 | 内容 | 涉及文件 |
|------|------|----------|
| 功能 | 新增 `area_stay_hourly` 表（`entity_id + period_date + period_hour` 唯一，`duration_sec` 为该小时累计增量） | schemas.sql#L169 |
| 功能 | 新增 `async_upsert_area_stays_hourly`：冲突时 `duration_sec = duration_sec + VALUES(...)` 累加，同一小时多次采样不会覆盖 | db.py#L643 |
| 功能 | 新增纯函数 `diff_area_stay_seconds`：按「本次累计 − 上次基线」算增量，首次采样/跨日/累计值回退时不产生增量 | coordinator.py#L70 |
| 功能 | `_collect_area_stays` 同时写日表（覆盖）与小时表（增量累加），基线存 `self._last_area_stay_sec` | coordinator.py#L436 |
| 看板 | 热力图面板（id 11）数据源由 `area_stay_daily` 改为 `area_stay_hourly`：X 轴固定今天 00:00~现在（panel time override `now/d`），Y 轴区域，颜色=该时段平均停留小时。标题改为「区域停留热力图 (小时时段 × 区域)」 | Grafana 看板 uid `a67f2s` |
| 测试 | 新增 `TestDiffAreaStaySeconds` 5 个用例（首次采样/正常增量/跨日/累计回退/实体缺失），总计 87 个用例通过 | tests/test_utility_tracker.py |

**热力图 SQL**

```sql
SELECT
  TIMESTAMP(CURDATE(), MAKETIME(period_hour, 0, 0)) AS time,
  area_name AS metric,
  ROUND(SUM(duration_sec) / COUNT(DISTINCT period_date) / 3600, 2) AS value
FROM area_stay_hourly
WHERE period_date >= DATE($__timeFrom())
  AND period_date <= DATE($__timeTo())
GROUP BY period_hour, area_name
ORDER BY period_hour ASC
```

**已知限制**：小时数据自本次上线起才开始积累（history_stats 只提供当日累计，历史时段分布无法回填）；HA 停机期间的小时增量无法补齐。

**踩坑**：改 Python 代码后仅调用 `homeassistant.reload_config_entry` 不够——自定义集成模块不会重新导入，必须先 `POST /api/services/homeassistant/restart` 让新代码生效；否则 `async_ensure_schema` 仍执行旧 SQL，新表不会建，面板查询直接报 `Table doesn't exist`。

## Grafana 内网直连打通 + 区域停留热力图 (2026-10-28)

| 类型 | 内容 | 涉及文件 |
|------|------|----------|
| 配置 | Grafana addon (`a0d7b954_grafana`) 增加宿主机端口映射 `80/tcp → 3000`：此前 `network: {"80/tcp": null}` 导致 `192.168.0.130:3000` 拒绝连接。经 HA WebSocket `supervisor/api` 调 `POST /addons/{slug}/options` 设置，并重启 addon 生效（配置持久化，HAOS 重启后保留） | （服务器 Supervisor 配置） |
| 功能 | 能源看板新增 **「区域停留热力图 (日期 × 区域)」** Heatmap panel：Y 轴 12 个区域名、X 轴日期、色深=当日累计停留小时数，数据源 `area_stay_daily`。panel id 11，gridPos `{h:11,w:24,x:0,y:28}` | Grafana 看板 uid `a67f2s` |
| 文档 | 记录 Grafana 完整访问方式与踩坑：`/api/hassio/*` REST 对 Long-Lived Token 一律 401，但 WS `supervisor/api` 可用；API 路径必须带 `/api/hassio_ingress/{token}/` 前缀；ingress_token 在 addon 重启后会变 | .trae/rules/project_rules.md |

**热力图 SQL**

```sql
SELECT period_date AS time, area_name AS metric,
       ROUND(SUM(duration_sec) / 3600, 2) AS value
FROM area_stay_daily
WHERE period_date >= DATE($__timeFrom()) AND period_date <= DATE($__timeTo())
GROUP BY period_date, area_name
ORDER BY period_date ASC
```

**已知限制**：`area_stay_daily` 目前只有 1 天数据，热力图仅 1 列色块；随每日快照积累会自动填充出趋势。

## 设备功耗异常值过滤 (2026-10-28)

| 类型 | 内容 | 涉及文件 |
|------|------|----------|
| 功能 | 功耗入库前新增异常值过滤：① 单设备功率超过绝对上限 10000W 或为负数直接丢弃；② 与同一实体上次有效值比较，同时满足「倍数 ≥10x」且「增量 >3000W」判定为跳变尖峰丢弃；上次值 ≤0（首次采样/刚上电）不做跳变判定，避免误杀真实启动功率。被过滤的采样仅把 `power_w` 置空，保留 `state` 字符串便于排查，聚合与 current_power 基于 NULL 自然忽略 | const.py (`is_power_outlier` + 4 个阈值常量) |
| 功能 | 新增 `async_fetch_last_power_values(lookback_hours)`：查询各实体在 24h 内最近一条非空 `power_w`，作为跳变判定基准 | db.py |
| 功能 | `_collect_device_power` 在写库前批量应用过滤，记录被过滤条数与 WARNING 明细日志 | coordinator.py |
| 修复 | 解决设备功耗 24h 曲线 03:00–04:00 出现 ~13kW 尖峰（其余时段稳定 363W）导致小时 AVG/MAX 与今日电量估算被抬高的问题 | coordinator.py |
| 测试 | 新增 8 个用例（超上限/负值/None/无历史/小功率倍率不误杀/中等跳变/零值启动/正常波动），单测 125 个全部通过 | tests/test_utility_tracker.py |

## 能源看板全量 UI 巡检修复 (2026-10-28)

| 类型 | 内容 | 涉及文件 |
|------|------|----------|
| 修复 | `custom:grafana-ingress-card` 重写：改用 `hass.callWS({type:'supervisor/api', endpoint:'/addons/<slug>/info'})` 拿 `ingress_url` 拼 iframe 地址，替换原先 REST `/api/hassio/ingress_token`（该接口对前端 401，导致深度分析页「配置错误」）；同时修复 `set hass` 先于 `setConfig` 时重复 `attachShadow` 抛 NotSupportedError | www/grafana-ingress-card.js |
| 修复 | 深度分析 View 卡片高度 `aspect_ratio: 100%` → `140%`，手机上 Grafana 内容不再被压扁 | ui-energy.yaml |
| 修复 | 删除 3 张 `custom:auto-entities` 卡片（该卡片未安装，全部渲染「配置错误」）：设备功耗页改为静态 `entities` 列表（15 个插座功率 + 3 个累计电量），灯光页改为全屋灯组 `mushroom-light-card` | ui-energy.yaml |
| 修复 | 灯光页 markdown 模板 `states('light')` 写错（不是实体 ID），改为 `states.light`，此前卡片空白 | ui-energy.yaml |
| 优化 | 区域主灯 grid 4 列 → 2 列、能源核心 grid 4 列 → 2 列，手机上不再出现 88px 窄格与时长时间截断 | ui-energy.yaml, ui-lovelace.yaml |
| 优化 | 电信话费整段（1 卡片 + 4 chips）注释隐藏：china_telecom 集成未认证，实体全部 unavailable，页面显示大量「unavailable」；重新登录集成后可恢复 | ui-energy.yaml |
| 验证 | 390×844 移动端 + 1098 CSS px 桌面宽度全量巡检：能源看板 7 个 view、主页 16 个 view 均 0 张「配置错误」、无横向溢出 | - |

## 区域停留排行榜（独立 sensor）(2026-10-28)

| 类型 | 内容 | 涉及文件 |
|------|------|----------|
| 功能 | 新增 `async_fetch_area_stays_month` (本月 1 日至今按区域分组明细) | db.py |
| 功能 | coordinator 新增 `area_stay_week_ranking` / `area_stay_month_ranking` 聚合明细 | coordinator.py |
| 功能 | 新增 Ranking sensor `sensor.utility_tracker_area_stay_week_ranking` / `sensor.utility_tracker_area_stay_month_ranking`，state 为短 CSV 格式（`区域名=X.Xh`），避开 HA entity state 长度上限 | sensor.py |
| 看板 | View 6「区域停留」新增 **区域停留排行榜** 卡片（周/月各一个 markdown card，jinja2 split 解析 CSV） | ui-energy.yaml |
| 备注 | **踩坑**：HA entity native_value 有长度上限（~500 chars），`json.dumps()` 完整 JSON 会被截断导致 state=unknown，改用 CSV 短格式 (~180 chars) 解决 | sensor.py |

## 区域停留周/月聚合 + 能源账单看板 (2026-10-28)

| 类型 | 内容 | 涉及文件 |
|------|------|----------|
| 功能 | 新增 `async_sum_area_stay_week` (近 7 日含今日) / `async_sum_area_stay_month` (本月 1 日至今) / `async_fetch_area_stays_week` (按区域分组明细) | db.py |
| 功能 | coordinator 新增 `area_stay_week_seconds` / `area_stay_month_seconds` 读库聚合 | coordinator.py |
| 功能 | 新增 `sensor.utility_tracker_area_stay_duration_week` / `sensor.utility_tracker_area_stay_duration_month`（合计 h） | sensor.py |
| 看板 | 能源账单看板新增 View 6「区域停留」(path: area-stay)：今日/近 7 日/本月汇总 + 12 区域今日停留 + 24h history-graph + 入库口径说明 | ui-energy.yaml#L885 |

## 区域停留时长统计入库（新家）(2026-10-28) - 复用灯光时长方案

| 类型 | 内容 | 涉及文件 |
|------|------|----------|
| 功能 | 新增 `area_stay_daily` 表：12 个区域 history_stats 今日停留时长每 5 分钟快照写入，`entity_id + period_date` 唯一键覆盖更新，跨零点自动结算，历史永久保留 | schemas.sql |
| 功能 | 新增 `AREA_STAY_DURATION_ENTITIES` 常量（12 个区域停留时长实体 → 区域名） | const.py |
| 功能 | 新增 `async_upsert_area_stays` / `async_sum_area_stay_today` / `async_fetch_area_stays_today`，并把新表纳入 `purge_device_data` | db.py |
| 功能 | 新增 `_collect_area_stays`，复用 `hours_state_to_seconds` 小时转秒；`stats["area_stay_today_seconds"]` 读库聚合 | coordinator.py |
| 功能 | 新增 `sensor.utility_tracker_area_stay_duration_today`（今日 12 区域停留合计，单位 h） | sensor.py |
| 看板 | 区域活动汇总区改为 2 列：停留最久 + 今日停留合计（读库）；说明补充入库口径与「合计可超 24h」提示 | ui-lovelace.yaml#L1516 |
| 测试 | 新增 4 个用例（12 区域全覆盖 / 区域名不重复 / 实体 ID 不重复 / 均为 sensor 域），总计 74 个用例通过 | tests/test_utility_tracker.py |

## 老房自动化与统计数据清理 (2026-10-28)

| 类型 | 内容 | 涉及文件 |
|------|------|----------|
| 重构 | 删除 8 条老房区域访问计数自动化（7 个 `region_visit_counter_*_v2` + `region_daily_reset_v2`），其触发源传感器已不存在，计数恒为 0 | automations.yaml |
| 重构 | 删除 7 个老房区域访问计数模板传感器（Living Room/Bedroom/Kitchen/Dining/Bathroom/Hallway/Doorway Visits） | templates.yaml |
| 重构 | 删除 `sensor.most_visited_area_today`（依赖已删除的 counter，输出恒为「暂无数据」） | templates.yaml |
| 重构 | `counter.yaml` 清空为 `[]`（7 个老房区域 counter 全部移除） | counter.yaml |
| 看板 | 区域活动视图汇总区去掉「访问最多」卡片，改为单列仅保留「停留最久」 | ui-lovelace.yaml#L1495 |
| 清理 | 删除 37 个孤儿实体注册项：18 个老房自动化（11 个亮灯时长累计 + 7 个访问计数）、11 个 `input_number.light_*_daily_duration`、8 个老房模板传感器 | 实体注册表 |
| 清理 | 删除 7 个 `counter.*_visits` 注册项与 14 个失效 YAML 平台实体（`sensor.light_*_daily_duration_hours`、`sensor.yang_tai_deng_liang_deng_shi_chang` 等） | 实体注册表 |
| 清理 | 分批清除 169 个陈旧统计 ID（对应实体已不存在的老房灯光/空调/设备能耗/已移除米家设备）；保留 `crcgas:*` 外部统计 4 个、打印机 28 个（设备当前离线，实体暂未创建） | recorder 统计库 |

## Grafana 动态 ingress + CTM 卡片前端注册修复 (2026-10-28)

| 类型 | 内容 | 涉及文件 |
|------|------|----------|
| 修复 | 深度分析 view `iframe` 写死 ingress token 导致 401 Unauthorized（token per-user 动态变化，过期即失效）→ 改用 `custom:grafana-ingress-card`，每次加载时通过 `/api/hassio/ingress_token?addon=<slug>` 动态拿当前用户的有效 token 再拼接 iframe URL | ui-energy.yaml#L554 + www/grafana-ingress-card.js |
| 修复 | china_telecom 组件 manifest.json 缺 `frontend_url_path` 声明，HA 不挂载 www/ 目录 → `/china_telecom/ctm-telecom-card.js` 永远 404 → 导致能源账单概览页顶部 CTM 电信卡片加载失败 | custom_components/china_telecom/manifest.json + configuration.yaml resources 段 |
| 新增 | www/grafana-ingress-card.js（约 110 行 custom card）：setConfig 校验 grafana_slug + dashboard_path，set hass 时 REST fetch `/api/hassio/ingress_token` 拿 token，动态拼 iframe src，error 时显示友好错误信息 | www/grafana-ingress-card.js |
| 优化 | lovelace.resources 段新增 `/local/grafana-ingress-card.js?v=1.0.0` 注册 | configuration.yaml |

## utility_tracker v0.3.0 分户 + 燃气退款单据 (2026-10-28)

| 类型 | 内容 | 涉及文件 |
|------|------|----------|
| 功能 | utility_records 加 `bill_no VARCHAR(64)` 列，UNIQUE KEY 扩展为 5 元组 (type,account,gran,date,bill_no)，支持同月多单据（正常账单 + 退款负数单） | schemas.sql |
| 功能 | 燃气账单保留原始正负号（移除 `_abs_or_none`），退款为负数、正常为正数；同 period_date 多 applicationNo 独立入库 | coordinator.py#L_backfill_gas_history |
| 功能 | `async_sum_month_charge` 改按「行数>0」而非「合计>0」判断，负数净额不再误回落到日记录分支 | db.py |
| 功能 | 新增幂等迁移 `async_migrate_bill_no`（information_schema 查表列）和 `async_migrate_light_brightness`（TINYINT→SMALLINT 修复亮度越界崩溃） | db.py |
| 修复 | brightness TINYINT(127) 无法存 HA 亮度 0-255，某灯亮度 >127 时 SQL DataError 导致整个 coordinator 崩溃 → 改 SMALLINT + 幂等迁移 | db.py |
| 修复 | 旧唯一 KEY 缺 bill_no 导致燃气同月多单据互相覆盖 → 扩展 5 元组 | schemas.sql |
| 修复 | 退款符号被 `_abs_or_none` 取反成欠费金额 → 移除该函数，保留原始符号 | coordinator.py |
| 修复 | `async_sum_month_charge` `if monthly > 0` 错落空，负数净额误回落日记录分支 → 改按行数判断 | db.py |
| 修复 | `last_gas_discovery` 永远非空导致 retry 逻辑失效 → 加 `last_gas_accounts` 独立判断 | coordinator.py |
| 优化 | 移除 `_collect_gas` 里的 live 传感器月账单写入（无 applicationNo 会重复计），全部走历史回填 | coordinator.py |
| 看板 | ui-energy.yaml 燃气费页新增「出租 · 缴费记录」4 卡片组（最近缴费时间/金额/年度次数/月均用气） | ui-energy.yaml |
| 测试 | 70 个旧单测 + 43 个新边界测试 = 113 全部通过；新用例覆盖 bill_no 去重/文件名过滤/SQL 字段顺序/负数净额/discover 边界/迁移幂等/重试逻辑 | tests/test_utility_tracker.py + test_utility_tracker_edge.py |

## 北阳台纳入停留统计（新家）(2026-10-28) - PIR 移动 + 10 分钟超时派生有人

| 类型 | 内容 | 涉及文件 |
|------|------|----------|
| 功能 | 新增 trigger 型模板 `binary_sensor.bei_yang_tai_you_ren`：监听 PIR「有人移动」事件置为有人，每分钟刷新，超过传感器自带「自定义超时无人移动时间」（默认 10 分钟）无新移动转回无人 | templates.yaml#L573 |
| 功能 | 新增 `sensor.bei_yang_tai_ting_liu_shi_chang` history_stats，状态取 `binary_sensor.bei_yang_tai_you_ren == on` | sensor.yaml#L234 |
| 重构 | `sensor.longest_stay_area_today` 统计区域从 11 个增加到 12 个（新增北阳台） | templates.yaml#L633 |
| 看板 | 区域活动视图新增北阳台卡片与 24h 趋势，说明改为「门口未纳入；北阳台 PIR 派生、时长偏保守」 | ui-lovelace.yaml#L1571 |

## 灯光统计重构入库（新家）(2026-10-28) - history_stats 每日时长写入 MariaDB

| 类型 | 内容 | 涉及文件 |
|------|------|----------|
| 功能 | 新增表 `light_duration_daily`（entity_id + period_date 唯一，area_name / duration_sec / updated_at），长期保留区域主灯每日亮灯时长 | schemas.sql#表8 |
| 功能 | 新增 `async_upsert_light_durations` / `async_sum_light_duration_today`，同一天覆盖更新，SUM 取今日总时长 | db.py |
| 功能 | 每 5 分钟采样 13 个区域主灯 `history_stats` 今日小时数（`hours_state_to_seconds` 转秒）写入 DB；`Longest/统计` 口径统一 | coordinator.py |
| 重构 | `sensor.utility_tracker_light_duration_today` 改由新表汇总（与区域灯实体合计一致，今日 12.28h），开关次数仍取事件流表 `light_daily` | coordinator.py |
| 清理 | 删除 61 个老房 UI 模板配置条目（45 个「xx灯周/月/年亮灯时长h」、7 个「xx灯今日亮灯时长」、7 个「xx停留时长」、2 个旧汇总） | 服务器 .storage |
| 修复 | 清理 14 个孤儿模板实体与 2 个孤儿自动化注册项，并把 3 个被挤成 `_2` 的停留时长实体改回基础 ID（客厅/厨房/餐厅） | 服务器实体注册表 |
| 测试 | 新增 TestHoursStateToSeconds 5 个用例（正常/浮点精度/零值/无效状态/负数），utility_tracker 单测 70 个全部通过 | tests/test_utility_tracker.py |
| 看板 | 灯光视图末尾新增「统计口径」markdown，说明 history_stats 与 DB 双轨口径 | ui-energy.yaml#L825 |

## 区域停留时长重建（新家）(2026-10-28) - history_stats 替换老房 input_number 累计

| 类型 | 内容 | 涉及文件 |
|------|------|----------|
| 功能 | 新增 11 个区域停留时长 `history_stats`（客厅/主卧/次卧/北卧/厨房/餐厅/主卫/公卫/公卫干区/南阳台/走廊），`type: time` + `start: "{{ today_at() }}"`，输出小时，每日 0 点自动归零 | sensor.yaml#L143-233 |
| 功能 | 8 个原生米家人在传感器直接以 `occupancy_status` 的「有人」为统计状态；厨房/公卫干区/走廊因雷达灯只有 `has_someone_duration_p_5_3`（分钟文本）无布尔状态，新增 3 个 `binary_sensor.*_you_ren`（`device_class: occupancy`，派生 `>0` 判定） | templates.yaml#L548-571 |
| 删除 | 删除 7 个老房 `*_duration` template sensor（living_room/bedroom/kitchen/dining/bathroom/hallway/doorway），其数据源 `input_number.*_duration` 自 2026-09-28 起一直 unavailable | templates.yaml |
| 重构 | `sensor.longest_stay_area_today` 改为读取 11 个新停留 sensor，输出 `区域 (x.xh)` | templates.yaml |
| 删除 | 删除自动化 `region_stay_duration_accumulate_v2`（含 7 个 choose 分支的 input_number 累加）；`region_daily_reset_v2` 移除末尾 input_number 重置动作，仅保留 7 个 counter.reset | automations.yaml |
| 看板 | ui-lovelace.yaml 新增「区域活动」view（path: activity）：停留最久/访问最多汇总卡 + 11 区域停留卡片 + 24h history-graph + 统计说明 | ui-lovelace.yaml#L1484 |

## 亮灯统计重构（新家）(2026-10-28) - 老房配置清理 + 按区域主灯重建

| 类型 | 内容 | 涉及文件 |
|------|------|----------|
| 重构 | 亮灯时长统计从老房机制（input_number 累计 + 30 秒 time_pattern 累加 + template 换算）改为 `history_stats` 原生平台，13 个区域各 1 盏主灯，`start: "{{ today_at() }}"` / `type: time`，每日 0 点自动归零 | sensor.yaml |
| 删除 | 删除 65 个老房亮灯 template sensor（客厅吸顶灯/沙发灯/卧室灯/灯带/厨房/餐厅/卫生间/浴霸/走廊主灯/走廊卫生间/门口筒灯 的 today/week/month 及累计时长等），templates.yaml 1495 行 → 908 行 | templates.yaml |
| 功能 | `light_today_total_hours` 汇总实体改为 13 个新区域主灯 id 列表求和（新增南阳台/北阳台/公卫干区，`阳台灯` 更名 `南阳台灯`） | templates.yaml#L889 |
| 删除 | 删除 12 个老房亮灯自动化（11 个 input_number 累计 + 每日归零），automations.yaml 38 → 26 条 | automations.yaml |
| 删除 | input_number.yaml 清空（老房 11 个 `light_*_daily_duration` 全部废弃） | input_number.yaml |
| 删除 | utility_meter.yaml 删除 60 个老房灯具周期 meter（source 已被删除会报错），保留并重建 4 个新家汇总 meter（weekly/monthly/yearly/all_time） | utility_meter.yaml |
| 功能 | groups.yaml `all_lights` 组改为 13 盏新家主灯 | groups.yaml |
| 看板 | ui-energy.yaml 新增「灯光」view（path: lights）：今日汇总 / 13 区域主灯 / 24h history-graph / 当前亮灯 auto-entities / 区域主灯快捷开关 | ui-energy.yaml#L638 |
| 看板 | 删除独立看板 ui-old-lights.yaml 及 configuration.yaml 中的 old-lights dashboard 定义；首页 chips 跳转改指向 `/energy-bills/lights` | configuration.yaml, ui-lovelace.yaml |
| 数据 | 通过 websocket `recorder/clear_statistics` 清理老房 45 个统计 ID，并 `utility_meter.reset` 归零 4 个汇总 meter（重置前残留 43.51h） | (HA 部署) |

## Utility Tracker v0.3.0 (2026-10-28) - 分户显示 + 退款单据

| 类型 | 内容 | 涉及文件 |
|------|------|----------|
| 功能 | 分户统计: 新增 4 个 sensor (electricity/gas × this_month_main/rental),电费按 state_grid account_suffix 0065(自住东方新天地)/7061(出租东方佳园) 分,燃气按 crcgas cons_no 1040395237/1021540961 分; 统计 SQL 移到 utility_due 节流之外每轮刷新 | coordinator.py, sensor.py, db.py `async_sum_month_charge` 加 account_id 参数 |
| 修复 | 燃气同月多单据互相覆盖: utility_records 加 `bill_no` 列 (燃气=applicationNo),UNIQUE KEY 扩展为 (utility_type,account_id,granularity,period_date,bill_no); 新增幂等迁移 `async_migrate_bill_no` 启动时自动 ALTER TABLE | schemas.sql, db.py, __init__.py |
| 修复 | 退款负数业务修正: 用户确认 -49.99 是燃气公司退款而非欠费,移除 `_abs_or_none`,入库保留原始正负号,月度合计为净额 (主户 2026-10 = 2.53-49.99 = -47.46) | coordinator.py `_backfill_gas_history` |
| 修复 | `async_sum_month_charge` 旧逻辑 `if monthly > 0` 导致负数净额错落到日记录分支,改为按行数判断 (有月记录即返回其合计) | db.py |
| 修复 | crcgas 启动慢导致 `_discover_gas_accounts` 返回空: 新增 `last_gas_accounts` 调试属性,空户时不更新 `last_utility_sync` 下周期重试; `gas_discovery` 属性暴露 states 总数/燃气实体数/样本供排查 | coordinator.py, sensor.py |
| 修复 | `_backfill_gas_history` 错把副户历史 JSON 写到主户 account_id 下: 按户过滤文件名 (主户跳过 `_<10位数字>$` 结尾文件,副户只读匹配自己 cons_no 的); 副户也开始回填历史 | coordinator.py |
| 重构 | 移除 live 传感器写燃气月记录 (zhang_dan_jin_e 等无 applicationNo,会与历史回填同月单据重复计),月记录统一由历史 JSON 回填写入,live 传感器只供快照 | coordinator.py `_collect_gas` |
| 数据 | 一次性清理 v2 (.storage 标记): 删未知 account_id 脏记录 + 两户全部旧 gas 月记录,按新规则重建 (total_records 141→161) | coordinator.py `_async_update_data` |
| 测试 | TestGasBillMapping 更新: 退款保留负号 / 同月多单据按 bill_no 区分且净额 -47.46 / bill_no 缺失 auto- 序号兜底; 新增 TestMultiAccountSplit 4 用例; 总数 65 个 | tests/test_utility_tracker.py |
| 看板 | ui-energy.yaml 概览/电费/燃气费页分户卡片 (自住 vs 出租分开显示,不加总) | ui-energy.yaml |
| 看板 | 燃气费页新增「出租 · 缴费记录」卡片组 (最近缴费时间/金额/年度次数/月均用气) | ui-energy.yaml |
| 修复 | light_events.brightness TINYINT(最大 127)→SMALLINT(HA 亮度范围 0-255),写越界时整个 coordinator 崩溃导致全部 utility_tracker 实体 unavailable; 新增幂等迁移 `async_migrate_light_brightness` 启动时自动检查列类型 | schemas.sql, db.py `async_migrate_light_brightness`, __init__.py |

## crcgas 华润燃气 v2.0.0 (2026-10-28) - 多户化重构

| 类型 | 内容 | 涉及文件 |
|------|------|----------|
| 功能 | 完整多户化重构: config_flow 通过 `_validate_and_get_cons` 获取账号下全部户号列表存入 `cons_list`,async_setup_entry 按 cons_list 循环,每户独立 DataUpdateCoordinator + 全套 51 个传感器 + 2 个按钮 | sensor.py, button.py, config_flow.py, const.py |
| 功能 | sensor.py 拆分为 3 个模块级工厂函数: `_async_update_data_impl` / `_fix_statis_sum_impl` / `_async_initial_setup_impl`,通过 `functools.partial` 绑定每户参数 (cons_no, storage_entry_id, is_primary),避免 for 循环内 re-indent 800 行 + 闭包变量捕获陷阱 | sensor.py#L800, L1393, L1455 |
| 兼容 | 实体 unique_id 策略: 主户保持旧格式 `crcgas_{sensor_type}` 保护历史数据,副户带户号后缀 `crcgas_{cons_no}_{sensor_type}`;HuarunGasSensor 接受可选 cons_info=None 退化旧格式 | sensor.py#L110-122 |
| 隔离 | 历史存储键隔离: 主户 `crcgas_history_{entry_id}` (兼容已有数据),副户 `crcgas_history_{entry_id}_{cons_no}`;统计注入 ID 隔离: 主户 `crcgas:monthly_gas_usage`,副户 `crcgas:monthly_gas_usage_{cons_no}` | sensor.py `_import_history_statistics`, `_import_meter_history_to_entity` |
| 隔离 | coordinator 按户号隔离: `hass.data[DOMAIN][f"{entry_id}_coordinator_{cons_no}"]`,主户同时注册 legacy key `{entry_id}_coordinator` 保证旧服务调用兼容 | sensor.py#L1571, __init__.py |
| 功能 | button.py 重写为多户版,每户一对按钮 (抓取历史+刷新数据),按钮 device_info 按户隔离;FetchHistoryButton 调服务时传 `{"cons_no": ...}`,RefreshDataButton 按户号查 coordinator | button.py |
| 功能 | `crcgas.fetch_history` 服务支持 `cons_no` 参数,缺省时循环所有户;`_fix_statis_sum_impl` 的 sensor_ids 改为参数传入 | sensor.py |
| 部署 | 实际接入 2 户: 主户 1040395237 (*淑萱 东方新天地) 51 实体,副户 1021540961 (*福欣 东方佳园) 51 实体,共 102 实体 + 4 按钮 | (HA 部署) |
| 部署 | 副户能源面板传感器 `sensor.hua_run_ran_qi_1021540961_neng_yuan_yi_biao_pan_ran_qi_fu_xin` 已通过 WebSocket `energy/save_prefs` 加入 HA 能源面板 energy_sources | (HA 部署) |
| 重构 | `async_unload_entry` 增加清理多户 coordinator keys (循环 cons_list pop 每户的 `{entry_id}_coordinator_{cons_no}`) | __init__.py |
| 优化 | 主户设备/实体显示名带户名后缀 ("华润燃气 *淑萱 燃气账户余额"),与副户 ("华润燃气 *福欣") 区分。通过 `_legacy_id=True` 标记保持主户旧 unique_id/identifiers 不动,只改显示名;entity name 不再追加户名,依赖 HA 自动拼接 device 名 (避免 "X X" 重复) | sensor.py, button.py |
| 优化 | device name 改用地址而非户主名 (户主名带 * 掩码不直观)。新增 `_short_addr()` 工具函数: 去掉 "省/市/区/街道" 等行政前缀 + 去掉 "*栋*单元" 分隔符,得到「小区+门牌」格式。效果: 主户 "华润燃气 东方新天地1201",副户 "华润燃气 东方佳园401" | sensor.py `_short_addr`, button.py |

## Utility Tracker v0.2.0 (2026-10-28) - 设备功耗 + 灯光统计

| 类型 | 内容 | 涉及文件 |
|------|------|----------|
| 功能 | 新增单设备功耗采集: 自动扫描 HA 中所有 device_class=power/energy 的 sensor,按 5 分钟对齐采样写入 `device_power_raw`,聚合到 `device_power_hourly` (avg/max/min/energy) 与 `device_power_daily` (含 peak_hour) | coordinator.py `_collect_device_power`, db.py, schemas.sql |
| 功能 | 分层采样保留策略: 原始 5 分钟数据保留 30 天自动清理,小时/日聚合永久保留;采样时间对齐 5 分钟边界保证 UNIQUE 幂等 | coordinator.py, db.py `async_cleanup_power_raw` |
| 功能 | 新增灯光统计: `async_track_state_change_event(MATCH_ALL)` 监听全部实体,回调内过滤 light.* 且只在 on/off 切换时入队 (忽略亮度/色温变化),coordinator 每 5 分钟批量落库 `light_events`,LEAD 窗口函数配对 on/off 聚合 `light_daily` (次数/时长/首末次/平均亮度) | __init__.py `_light_state_changed`, db.py `async_aggregate_light_daily` |
| 功能 | 双频协调器: update_interval = min(账单同步 1h, 功耗采样 5min),电费/燃气按 `last_utility_sync` 节流,crcgas 启动慢返回空户时不更新节流时间戳下周期重试 | coordinator.py `_async_update_data` |
| 功能 | 新增 4 个 sensor: current_power (W, 每实体取 10 分钟内最新采样求和) / power_today (kWh) / light_today_count / light_today_duration (h) | sensor.py, db.py `async_current_total_power` / `async_sum_power_today` / `async_sum_light_today` |
| 功能 | 新增服务 `utility_tracker.purge_device_data`: 清空 5 张设备/灯光表 (不影响电费燃气账单) | services.yaml, __init__.py, db.py `async_purge_device_data` |
| 配置 | config_flow 新增 4 项: enable_device_power / enable_light_stats (默认开) / power_sample_minutes (1-60, 默认 5) / raw_retention_days (1-365, 默认 30) | config_flow.py, const.py |
| 修复 | 传感器反馈回路: 集成自身的 current_power/power_today sensor (dc=power/energy) 被自己采样导致数值指数增长 (power_today 曾达 3211 kWh),采样时排除 `sensor.utility_tracker_*` 与 `osg_uc_*` (SGCC 账单已在 utility_records 跟踪) | coordinator.py `_collect_device_power` |
| 修复 | 单位换算: mWh/Wh 单位的 energy 传感器 (如 nasri 805mWh) 未换算直接当 kWh 存,补 mWh→/1e6、Wh→/1e3 换算 | coordinator.py `_collect_device_power` |
| 修复 | 时区不一致: HA 容器 datetime.now() 返回 UTC 而 MariaDB 会话 NOW()/CURDATE() 用 +8,导致 10 分钟窗口查询错位 (current_power=0) 且日聚合边界早 8 小时。统一为: Python 写入侧用 `dt_util.now().replace(tzinfo=None)` 本地 naive 时间,DB 连接后 `SET time_zone` 为 HA 默认时区偏移 | coordinator.py, __init__.py, db.py `_connect_sync` |
| 修复 | `async_aggregate_light_daily` SQL 有 2 个 %s 但只传 1 个参数,导致 setup_retry "not enough arguments for format string" | db.py |
| 修复 | 灯光 listener 改用显式实体列表订阅 (与 printer_analytics 同款已验证写法),MATCH_ALL 方式不可靠;`_is_light_entity` 识别逻辑移到 const.py 复用为 `is_light_entity`;coordinator 每轮检测灯光实体增减,变化时自动重建订阅 (解决集成加载早于灯实体注册导致的漏订阅) | __init__.py, coordinator.py `_collect_light_stats`, const.py |
| 功能 | 灯光统计支持 switch 域灯具: 米家/京造等灯以 switch 形式存在 (如 `switch.*_fill_light_*`),entity_id 含 light/lamp 或名称含 灯/light/lamp 的 switch 纳入统计,共识别 120 个灯光实体 | const.py `is_light_entity`, __init__.py |
| 测试 | 新增 TestIsLightEntity 7 个用例: light 域全收 / 灯光类 switch / 大小写 / 非灯 switch / 其他域 / None 名称 | tests/test_utility_tracker.py |
| 看板 | ui-energy.yaml 新增 2 个 view: 「设备功耗」(当前总功率/今日用电/24h 曲线/auto-entities 单设备列表) 与「灯光」(今日次数/时长/当前亮灯/全部灯光),共 6 个 view | ui-energy.yaml |
| 测试 | 单元测试 45→57 个: 采样对齐 / dc 分流 / on-off 去抖 / SQL 占位符计数 / 时长换算 / mWh-Wh 换算与排除规则 | tests/test_utility_tracker.py |

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
| 看板 | 概览/电费 view 中所有户号数字标识 (7061/0065) 替换为对应小区地址: 7061=东方佳园14-1-401, 0065=东方新天地2-4-1201 (各 11 处显示名,entity_id 不动) | ui-energy.yaml |

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
