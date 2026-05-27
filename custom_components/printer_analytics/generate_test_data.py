"""读取现有历史数据，生成 5000 条测试数据"""
import json
import uuid
import random
import os
import shutil
from datetime import datetime, timedelta

# 服务器路径
HISTORY_DIR = r"\\192.168.0.130\config\.printer_analytics\history_by_year"
ENTRY_ID = "01KRTS6CW4PZ1GFDK42CRTTMGV"
SOURCE_FILE = os.path.join(HISTORY_DIR, f"{ENTRY_ID}_2026.json")
BACKUP_FILE = SOURCE_FILE + ".backup_before_test"

# 读取现有数据
print("读取现有数据...")
with open(SOURCE_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

existing = data["history"]
print(f"现有记录: {len(existing)} 条")

if not existing:
    print("没有现有记录，无法作为模板")
    exit(1)

# 备份原始文件
if not os.path.exists(BACKUP_FILE):
    shutil.copy2(SOURCE_FILE, BACKUP_FILE)
    print(f"已备份到: {BACKUP_FILE}")

# 用现有记录作为模板，生成 5000 条
TARGET_COUNT = 5000
print(f"生成 {TARGET_COUNT} 条测试数据...")

# 提取现有记录的模板特征
sample_statuses = [r.get("status", "finish") for r in existing]
sample_types = list(set(r.get("filament_type", "PLA") for r in existing if r.get("filament_type")))
sample_colors = list(set(r.get("filament_color", "White") for r in existing if r.get("filament_color")))
sample_models = list(set(r.get("task_name_model", "Benchy") for r in existing if r.get("task_name_model")))
sample_configs = list(set(r.get("task_name_config", "0.2mm") for r in existing if r.get("task_name_config")))
sample_speeds = list(set(r.get("speed_profile", "Standard") for r in existing if r.get("speed_profile")))
sample_nozzles = list(set(r.get("nozzle_size", "0.4") for r in existing if r.get("nozzle_size")))

# 确保列表非空
sample_types = sample_types or ["PLA"]
sample_colors = sample_colors or ["White"]
sample_models = sample_models or ["Benchy"]
sample_configs = sample_configs or ["0.2mm Standard"]
sample_speeds = sample_speeds or ["Standard"]
sample_nozzles = sample_nozzles or ["0.4"]

# 按年份分文件生成
years_data = {}
base_date = datetime(2024, 1, 1)

for i in range(TARGET_COUNT):
    # 每条约 2 天间隔，5000 条约 27 年，分布到 2024-2026
    day_offset = (i * 2) % 1095  # 3年内的天数
    start = base_date + timedelta(days=day_offset, hours=random.uniform(6, 22))
    duration = random.uniform(0.5, 18)
    end = start + timedelta(hours=duration)
    year = str(start.year)

    # 随机选一个现有记录作为模板
    template = random.choice(existing)

    # 状态分布：70% 成功，20% 失败，10% 取消
    rand = random.random()
    if rand < 0.7:
        status = "finish"
        progress = 100
    elif rand < 0.9:
        status = "failed"
        progress = random.randint(10, 90)
    else:
        status = "cancelled"
        progress = random.randint(5, 60)

    filament_type = random.choice(sample_types)
    filament_color = random.choice(sample_colors)
    num_colors = random.choices([1, 2, 3, 4], weights=[60, 25, 10, 5])[0]
    other_colors = [c for c in sample_colors if c != filament_color]
    colors_used = [filament_color] + random.sample(other_colors, min(num_colors - 1, len(other_colors)))

    total_weight = round(random.uniform(5, 200), 2) if status == "finish" else round(random.uniform(1, 80), 2)

    record = {
        "id": str(uuid.uuid4()),
        "start_time": start.isoformat() + "+08:00",
        "end_time": end.isoformat() + "+08:00",
        "duration_hours": round(duration, 2),
        "status": status,
        "progress": progress,
        "total_weight": total_weight,
        "total_length": round(total_weight * random.uniform(300, 400), 1),
        "filament_type": filament_type,
        "filament_color": filament_color,
        "colors_used": colors_used,
        "types_used": [filament_type],
        "total_colors": num_colors,
        "color_changes_count": max(0, num_colors - 1),
        "multi_color_summary": None,
        "color_usage": None,
        "energy_kwh": round(random.uniform(0.05, 3.0), 4),
        "task_name": f"{random.choice(sample_models)} {random.choice(sample_configs)}",
        "task_name_model": random.choice(sample_models),
        "task_name_config": random.choice(sample_configs),
        "config_name": random.choice(sample_configs),
        "nozzle_type": template.get("nozzle_type", "hardened_steel"),
        "nozzle_size": random.choice(sample_nozzles),
        "speed_profile": random.choice(sample_speeds),
        "print_bed_type": template.get("print_bed_type", "Textured PEI"),
        "total_layer_count": random.randint(50, 2000),
        "cover_image_url": None,
        "chamber_temp_final": round(random.uniform(25, 55), 1) if status == "finish" else None,
        "chamber_temp_last5min": None,
        "cover_image_local": None,
        "snapshot_image_local": None,
        "full_print_info_path": None,
    }

    years_data.setdefault(year, []).append(record)

# 写入各年份文件
for year, records in years_data.items():
    filepath = os.path.join(HISTORY_DIR, f"{ENTRY_ID}_{year}.json")
    year_data = {"version": 3, "year": int(year), "history": records}
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(year_data, f, ensure_ascii=False, indent=2)
    print(f"写入: {filepath} ({len(records)} 条)")

total = sum(len(r) for r in years_data.values())
print(f"\n完成！共写入 {total} 条测试记录")
print(f"原始数据已备份到: {BACKUP_FILE}")
print(f"恢复命令: copy \"{BACKUP_FILE}\" \"{SOURCE_FILE}\"")
