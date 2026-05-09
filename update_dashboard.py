﻿﻿﻿﻿﻿import requests
import json
import shutil
from datetime import datetime

# 读取连接信息
with open('.ha_connection_info.json', 'r', encoding='utf-8') as f:
    conn_info = json.load(f)

HA_URL = conn_info['ha_api']['url'].rstrip('/')
TOKEN = conn_info['ha_api']['token']

headers = {
    'Authorization': f'Bearer {TOKEN}',
    'Content-Type': 'application/json'
}

# 首先备份当前配置
print("正在获取服务器配置...")
response = requests.get(f'{HA_URL}/api/states', headers=headers)
if response.status_code != 200:
    print(f"获取状态失败: {response}")
    exit(1)

# 获取 Lovelace 配置
print("正在获取 Lovelace 配置...")
lovelace_url = f'{HA_URL}/api/lovelace/config'
response = requests.get(lovelace_url, headers=headers)

# 如果响应是 404，尝试其他方式
if response.status_code == 404:
    print("尝试获取默认仪表板...")
    response = requests.get(f'{HA_URL}/api/lovelace/config/dashboards/lovelace', headers=headers)

print(f"响应状态: {response.status_code}")

# 备份当前配置
backup_file = f'ui-lovelace.yaml.backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
print(f"正在备份配置到 {backup_file}...")
shutil.copy('ui-lovelace.yaml.backup_20260429', backup_file)

# 读取原始配置
with open('ui-lovelace.yaml.backup_20260429', 'r', encoding='utf-8') as f:
    original_config = f.read()

# 替换温湿度监测部分
old_temp_humidity_section = '''      # ==================== 温湿度监测 ====================

      # 温度曲线（多环境对比）
      - type: custom:mini-graph-card
        title: 🌡️ 温度监测
        icon: mdi:thermometer
        entities:
          - entity: sensor.zm1_b0f8931ee681_temperature
            name: 室内
            color: "#f44336"
          - entity: sensor.miaomiaoc_cn_blt_3_14n419k7k5k01_t2_temperature_p_2_1
            name: 客厅
            color: "#2196f3"
          - entity: sensor.vchon_cn_blt_3_1lgrvovgoc400_mbs17_temperature_p_2_1001
            name: 书房
            color: "#4caf50"
        line_width: 2
        hours_to_show: 24
        points_per_hour: 2
        show:
          graph: line
          legend: true
          fill: false
          points: false
        align_header: default
        align_icon: right
        group: false

      # 湿度曲线（多环境对比）
      - type: custom:mini-graph-card
        title: 💧 湿度监测
        icon: mdi:water-percent
        entities:
          - entity: sensor.zm1_b0f8931ee681_humidity
            name: 室内
            color: "#00bcd4"
          - entity: sensor.miaomiaoc_cn_blt_3_14n419k7k5k01_t2_relative_humidity_p_2_2
            name: 客厅
            color: "#9c27b0"
          - entity: sensor.vchon_cn_blt_3_1lgrvovgoc400_mbs17_relative_humidity_p_2_1002
            name: 书房
            color: "#ff9800"
        line_width: 2
        hours_to_show: 24
        points_per_hour: 2
        show:
          graph: line
          legend: true
          fill: false
          points: false
        align_header: default
        align_icon: right
        group: false'''

new_temp_humidity_section = '''      # ==================== 温湿度监测 ====================

      # 9区域湿度曲线
      - type: custom:mini-graph-card
        title: 💧 各区域湿度监测
        icon: mdi:water-percent
        entities:
          - entity: sensor.miaomiaoc_cn_blt_3_11c1qp540lc00_t2_relative_humidity_p_2_2
            name: 客厅
            color: "#f44336"
          - entity: sensor.miaomiaoc_cn_blt_3_14n419k7k5k01_t2_relative_humidity_p_2_2
            name: 厨房
            color: "#2196f3"
          - entity: sensor.miaomiaoc_cn_blt_3_1lip7b874ck01_t2_relative_humidity_p_2_2
            name: 卧室
            color: "#4caf50"
          - entity: sensor.vchon_cn_blt_3_1lgrvovgoc400_mbs17_relative_humidity_p_2_1002
            name: 大阳台
            color: "#ff9800"
          - entity: sensor.linp_cn_blt_3_1ll1gt2c10c00_ks2bb_relative_humidity_p_2_1002
            name: 卫生间
            color: "#9c27b0"
          - entity: sensor.linp_cn_blt_3_1nb2mr6n44s00_ks2bb_relative_humidity_p_2_1002
            name: 门口
            color: "#00bcd4"
          - entity: sensor.ym001_cn_blt_3_1o90bni4h0g00_ymwsdj_relative_humidity_p_2_1002
            name: 洗衣机阳台
            color: "#e91e63"
          - entity: sensor.vchon_cn_blt_3_1o931kgud0400_mbs17_relative_humidity_p_2_1002
            name: 主卧
            color: "#673ab7"
          - entity: sensor.ym001_cn_blt_3_1o9vhlvug4403_ymwsdj_relative_humidity_p_2_1002
            name: 室外
            color: "#009688"
        line_width: 2
        hours_to_show: 24
        points_per_hour: 2
        show:
          graph: line
          legend: true
          fill: false
          points: false
          labels: true
        align_header: default
        align_icon: right
        group: false

      # 小黑奴湿度曲线
      - type: custom:mini-graph-card
        title: 🖨️ 小黑奴环境湿度
        icon: mdi:printer-3d
        entities:
          - entity: sensor.qjiang_cn_blt_3_1n7f0sntk4s01_002_relative_humidity_p_2_1002
            name: 小黑奴环境
            color: "#ff5722"
        line_width: 2
        hours_to_show: 24
        points_per_hour: 2
        show:
          graph: line
          legend: true
          fill: false
          points: false
          labels: true
        align_header: default
        align_icon: right
        group: false

      # 耗材湿度曲线
      - type: custom:mini-graph-card
        title: 📦 耗材密封箱湿度
        icon: mdi:package-variant
        entities:
          - entity: sensor.vchon_cn_blt_3_1nf9gjb3k4000_mbs17_relative_humidity_p_2_1002
            name: 耗材密封箱
            color: "#795548"
        line_width: 2
        hours_to_show: 24
        points_per_hour: 2
        show:
          graph: line
          legend: true
          fill: false
          points: false
          labels: true
        align_header: default
        align_icon: right
        group: false'''

# 替换空气质量部分
old_air_quality_section = '''      # ==================== 空气质量监测 ====================

      # PM2.5 和甲醛实时数值
      - type: glance
        title: 🌫️ 空气质量
        entities:
          - entity: sensor.zm1_b0f8931ee681_pm25
            name: PM2.5
          - entity: sensor.zm1_b0f8931ee681_hcho
            name: 甲醛
        show_state: true
        show_icon: true

      # PM2.5 趋势曲线
      - type: custom:mini-graph-card
        title: PM2.5 趋势
        icon: mdi:blur
        entity: sensor.zm1_b0f8931ee681_pm25
        line_width: 2
        hours_to_show: 24
        points_per_hour: 2
        color_thresholds:
          - value: 0
            color: "#4caf50"
          - value: 35
            color: "#ffeb3b"
          - value: 75
            color: "#ff9800"
          - value: 115
            color: "#f44336"
        show:
          graph: line
          legend: false
          fill: true
          points: false
        align_header: default
        align_icon: right

      # 甲醛趋势曲线
      - type: custom:mini-graph-card
        title: 甲醛(HCHO) 趋势
        icon: mdi:chemical-weapon
        entity: sensor.zm1_b0f8931ee681_hcho
        line_width: 2
        hours_to_show: 24
        points_per_hour: 2
        color_thresholds:
          - value: 0
            color: "#4caf50"
          - value: 0.08
            color: "#ffeb3b"
          - value: 0.1
            color: "#ff9800"
          - value: 0.3
            color: "#f44336"
        show:
          graph: line
          legend: false
          fill: true
          points: false
        align_header: default
        align_icon: right'''

new_air_quality_section = '''      # ==================== 空气质量监测 ====================

      # PM2.5 趋势曲线（带Y轴）
      - type: custom:mini-graph-card
        title: 🌫️ PM2.5 监测
        icon: mdi:blur
        entity: sensor.zm1_b0f8931ee681_pm25
        line_width: 2
        hours_to_show: 24
        points_per_hour: 2
        color_thresholds:
          - value: 0
            color: "#4caf50"
          - value: 35
            color: "#ffeb3b"
          - value: 75
            color: "#ff9800"
          - value: 115
            color: "#f44336"
        show:
          graph: line
          legend: false
          fill: true
          points: false
          labels: true
        align_header: default
        align_icon: right

      # 甲醛趋势曲线（带Y轴）
      - type: custom:mini-graph-card
        title: 🌫️ 甲醛(HCHO) 监测
        icon: mdi:chemical-weapon
        entity: sensor.zm1_b0f8931ee681_hcho
        line_width: 2
        hours_to_show: 24
        points_per_hour: 2
        color_thresholds:
          - value: 0
            color: "#4caf50"
          - value: 0.08
            color: "#ffeb3b"
          - value: 0.1
            color: "#ff9800"
          - value: 0.3
            color: "#f44336"
        show:
          graph: line
          legend: false
          fill: true
          points: false
          labels: true
        align_header: default
        align_icon: right'''

# 执行替换
updated_config = original_config
updated_config = updated_config.replace(old_temp_humidity_section, new_temp_humidity_section)
updated_config = updated_config.replace(old_air_quality_section, new_air_quality_section)

# 写入新配置
with open('ui-lovelace.yaml', 'w', encoding='utf-8') as f:
    f.write(updated_config)

print("配置已更新到 ui-lovelace.yaml")

# 上传到服务器
print("\n正在上传配置到服务器...")

# 读取要上传的YAML
with open('ui-lovelace.yaml', 'r', encoding='utf-8') as f:
    yaml_content = f.read()

# 这里需要使用自定义集成或者直接修改 .storage 中的 lovelace
# 先尝试获取 storage 中的 lovelace
print("\n正在读取 .storage 中的 lovelace 配置...")
try:
    storage_path = '.storage/lovelace'
    with open(storage_path, 'r', encoding='utf-8') as f:
        lovelace_storage = json.load(f)
    
    # 更新 data 部分
    lovelace_storage['data']['config'] = yaml_content
    
    # 写回
    with open(storage_path, 'w', encoding='utf-8') as f:
        json.dump(lovelace_storage, f, ensure_ascii=False, indent=2)
    
    print(".storage/lovelace 已更新")
    
    # 复制到服务器（假设Y盘是挂载点）
    print("\n正在复制到服务器...")
    try:
        server_storage_path = 'Y:/.storage/lovelace'
        shutil.copy(storage_path, server_storage_path)
        print(f"已复制到 {server_storage_path}")
    except Exception as e:
        print(f"复制到服务器失败: {e}")
        print("请手动将 .storage/lovelace 复制到服务器")
    
    # 重载 Home Assistant
    print("\n正在重载 Home Assistant 配置...")
    reload_url = f'{HA_URL}/api/services/homeassistant/reload_config'
    response = requests.post(reload_url, headers=headers, json={})
    print(f"重载响应: {response.status_code}")
    
    print("\n完成！请刷新浏览器查看效果。")
    
except FileNotFoundError:
    print(".storage/lovelace 未找到")
    print("请手动更新服务器配置")
