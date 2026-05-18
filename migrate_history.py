﻿import json
import uuid
from datetime import datetime
from pathlib import Path

print("=== 开始迁移旧历史记录 ===")

# 定义文件路径
old_a1mini = Path("g:/dev/ha/ha/printer_history_a1mini.json")
old_p2s = Path("g:/dev/ha/ha/printer_history_p2s.json")
target_file = Path("g:/dev/ha/ha/01KRN9GJCF600K6JNS881DJ81S_2026.json")
output_file = Path("g:/dev/ha/ha/01KRN9GJCF600K6JNS881DJ81S_2026_merged.json")

print(f"读取 {old_a1mini.name}...")
with open(old_a1mini, "r", encoding="utf-8") as f:
    data_a1mini = json.load(f)
print(f"  a1mini 记录数: {len(data_a1mini.get('history', []))}")

print(f"读取 {old_p2s.name}...")
with open(old_p2s, "r", encoding="utf-8") as f:
    data_p2s = json.load(f)
print(f"  p2s 记录数: {len(data_p2s.get('history', []))}")

print(f"读取 {target_file.name}...")
with open(target_file, "r", encoding="utf-8") as f:
    data_target = json.load(f)
existing_records = data_target.get("history", [])
print(f"  现有记录数: {len(existing_records)}")

# 函数：转换旧记录
def convert_old_record(record):
    new_record = {
        "id": str(uuid.uuid4()),
        "start_time": None,
        "end_time": None,
        "duration_hours": 0.0,
        "status": "finish",
        "progress": 100,
        "total_weight": None,
        "total_length": None,
        "filament_type": None,
        "filament_color": None,
        "colors_used": [],
        "types_used": [],
        "total_colors": 0,
        "color_changes_count": 0,
        "color_usage": [],
        "energy_kwh": None,
        "task_name": record.get("task_name"),
        "nozzle_type": None,
        "nozzle_size": None,
        "print_bed_type": None,
        "total_layer_count": None,
        "cover_image_url": record.get("cover_image_url"),
        "cover_image_local": None,
        "snapshot_image_local": None,
        "full_print_info_path": None,
        "chamber_temp_final": None,
        "chamber_temp_last5min": None,
        "multi_color_summary": None,
        "color_changes": []
    }
    
    # 处理时间格式转换
    for key in ["start_time", "end_time"]:
        val = record.get(key)
        if val:
            try:
                # 如果没有 T，尝试解析
                if "T" not in val:
                    dt = datetime.strptime(val, "%Y-%m-%d %H:%M:%S")
                    new_record[key] = dt.strftime("%Y-%m-%dT%H:%M:%S.0000000+00:00")
                else:
                    new_record[key] = val
            except Exception as e:
                new_record[key] = val
        else:
            new_record[key] = None
    
    # 处理 duration
    if record.get("duration_minutes"):
        new_record["duration_hours"] = round(record["duration_minutes"] / 60, 2)
    
    return new_record

# 转换旧记录
print("转换旧记录...")
all_a1mini = [convert_old_record(r) for r in data_a1mini.get("history", [])]
all_p2s = [convert_old_record(r) for r in data_p2s.get("history", [])]

# 合并所有记录
all_records = existing_records + all_a1mini + all_p2s
print(f"合并后总记录数: {len(all_records)}")

# 排序
def get_end_time(record):
    et = record.get("end_time")
    if not et:
        return datetime.min
    try:
        return datetime.fromisoformat(et.replace("+00:00", "Z"))
    except:
        try:
            return datetime.strptime(et[:19], "%Y-%m-%dT%H:%M:%S")
        except:
            return datetime.min

all_records.sort(key=get_end_time)
print("已排序...")

# 保存
print(f"保存到 {output_file.name}...")
output_data = {
    "version": 3,
    "year": 2026,
    "history": all_records
}

with open(output_file, "w", encoding="utf-8") as f:
    json.dump(output_data, f, ensure_ascii=False, indent=2)

print("=== 迁移完成 ===")
print("")
print("请执行以下操作：")
print("1. 备份服务器上的原始文件：")
print("   \\\\192.168.0.130\\config\\.printer_analytics\\history_by_year\\01KRN9GJCF600K6JNS881DJ81S_2026.json")
print("2. 将新文件复制到服务器：")
print(f"   源: {output_file.absolute()}")
print("   目标: \\\\192.168.0.130\\config\\.printer_analytics\\history_by_year\\01KRN9GJCF600K6JNS881DJ81S_2026.json")
print("3. 重启 Home Assistant")
