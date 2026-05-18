﻿#!/usr/bin/env python3
"""模拟打印机分析集成的配置生成逻辑"""

# 从服务器旧配置中提取的两台打印机实体信息
PRINTER_DATA = [
    # a1mini 打印机
    {
        "printer_name": "a1mini",
        "sensors": {
            "print_history": "sensor.a1mini_a1mini_da_yin_li_shi",
            "total_prints": "sensor.a1mini_a1mini_zong_da_yin_ci_shu",
            "success_rate": "sensor.a1mini_a1mini_cheng_gong_lu",
            "average_duration": "sensor.a1mini_a1mini_ping_jun_da_yin_shi_chang",
            "total_print_duration": "sensor.a1mini_a1mini_da_yin_zong_shi_chang",
            "total_energy": "sensor.a1mini_a1mini_zong_neng_hao",
            "material_stats_7d": "sensor.a1mini_a1mini_7tian_hao_cai_tong_ji",
            "material_stats_30d": "sensor.a1mini_a1mini_30tian_hao_cai_tong_ji",
            "material_stats_lifetime": "sensor.a1mini_a1mini_zhong_shen_hao_cai_tong_ji",
            "duration_distribution": "sensor.a1mini_a1mini_da_yin_shi_chang_fen_bu",
            "activity_heatmap": "sensor.a1mini_a1mini_da_yin_huo_dong_re_li_tu",
            "failure_stage_distribution": "sensor.a1mini_a1mini_shi_bai_jie_duan_fen_bu",
            "filament_success_stats": "sensor.a1mini_a1mini_hao_cai_cheng_gong_lu_tong_ji",
            "print_status": "sensor.a1mini_a1mini_da_yin_zhuang_tai",
        },
        "realtime": {
            "current_task": "sensor.a1mini_0300aa5a1600497_task_name",
            "print_progress": "sensor.a1mini_0300aa5a1600497_print_progress",
            "current_weight": "sensor.a1mini_0300aa5a1600497_print_weight",
            "current_length": "sensor.a1mini_0300aa5a1600497_print_length",
            "total_usage": "sensor.a1mini_0300aa5a1600497_total_usage",
            "nozzle_temperature": "sensor.a1mini_0300aa5a1600497_nozzle_temperature",
            "bed_temperature": "sensor.a1mini_0300aa5a1600497_bed_temperature",
            "chamber_temperature": "sensor.qjiang_cn_blt_3_1n7f0sntk4s01_002_temperature_p_2_1001",
            "wifi_signal": "sensor.a1mini_0300aa5a1600497_wi_fi_signal",
            "speed_profile": "sensor.a1mini_0300aa5a1600497_speed_profile",
            "nozzle_size": "sensor.a1mini_0300aa5a1600497_nozzle_size",
        }
    },
    # p2s 打印机
    {
        "printer_name": "p2s",
        "sensors": {
            "print_history": "sensor.p2s_p2s_da_yin_li_shi",
            "total_prints": "sensor.p2s_p2s_zong_da_yin_ci_shu",
            "success_rate": "sensor.p2s_p2s_cheng_gong_lu",
            "average_duration": "sensor.p2s_p2s_ping_jun_da_yin_shi_chang",
            "total_print_duration": "sensor.p2s_p2s_da_yin_zong_shi_chang",
            "total_energy": "sensor.p2s_p2s_zong_neng_hao",
            "material_stats_7d": "sensor.p2s_p2s_7tian_hao_cai_tong_ji",
            "material_stats_30d": "sensor.p2s_p2s_30tian_hao_cai_tong_ji",
            "material_stats_lifetime": "sensor.p2s_p2s_zhong_shen_hao_cai_tong_ji",
            "duration_distribution": "sensor.p2s_p2s_da_yin_shi_chang_fen_bu",
            "activity_heatmap": "sensor.p2s_p2s_da_yin_huo_dong_re_li_tu",
            "failure_stage_distribution": "sensor.p2s_p2s_shi_bai_jie_duan_fen_bu",
            "filament_success_stats": "sensor.p2s_p2s_hao_cai_cheng_gong_lu_tong_ji",
            "print_status": "sensor.p2s_p2s_da_yin_zhuang_tai",
        },
        "realtime": {
            "current_task": "sensor.p2s_22e8bj5a2401765_task_name",
            "print_progress": "sensor.p2s_22e8bj5a2401765_print_progress",
            "current_weight": "sensor.p2s_22e8bj5a2401765_print_weight",
            "current_length": "sensor.p2s_22e8bj5a2401765_print_length",
            "total_usage": "sensor.p2s_22e8bj5a2401765_total_usage",
            "nozzle_temperature": "sensor.p2s_22e8bj5a2401765_nozzle_temperature",
            "bed_temperature": "sensor.p2s_22e8bj5a2401765_bed_temperature",
            "chamber_temperature": "sensor.p2s_22e8bj5a2401765_chamber_temperature",
            "active_tray": "sensor.p2s_22e8bj5a2401765_active_tray",
            "ams_1_tray_1": "sensor.p2s_22e8bj5a2401765_ams_1_tray_1",
            "ams_1_tray_2": "sensor.p2s_22e8bj5a2401765_ams_1_tray_2",
            "ams_1_tray_3": "sensor.p2s_22e8bj5a2401765_ams_1_tray_3",
            "ams_1_tray_4": "sensor.p2s_22e8bj5a2401765_ams_1_tray_4",
            "wifi_signal": "sensor.p2s_22e8bj5a2401765_wi_fi_signal",
            "speed_profile": "sensor.p2s_22e8bj5a2401765_speed_profile",
            "nozzle_size": "sensor.p2s_22e8bj5a2401765_nozzle_size",
        }
    }
]

def generate_config():
    """模拟集成的配置生成逻辑"""
    lines = [
        '# ==================== 打印机分析 - 监控置顶 + 三页签 ====================',
        '# 自动生成 - 顶部监控 / 统计分析 / 之最 / 全部历史',
        'views:',
        '  - title: "🖨️ 打印机分析"',
        '    icon: mdi:printer-3d-eye',
        '    panel: true',
        '    cards:',
        '      - type: custom:printer-analytics-card',
        '        title: "🖨️ 打印机分析"',
    ]
    
    lines.append('        printers:')
    
    for p in PRINTER_DATA:
        lines.append(f'          - printer_name: "{p["printer_name"]}"')
        
        # 写入传感器实体
        for k, v in p["sensors"].items():
            if v:
                lines.append(f'            {k}: {v}')
        
        # 写入实时实体
        for k, v in p["realtime"].items():
            if v:
                lines.append(f'            {k}: {v}')
    
    yaml_content = "\n".join(lines)
    return yaml_content


if __name__ == "__main__":
    config = generate_config()
    print(config)
    
    # 保存到本地文件
    with open("g:/dev/ha/ha/simulated_config.yaml", "w", encoding="utf-8") as f:
        f.write(config)
    print("\n✅ 配置已保存到: g:/dev/ha/ha/simulated_config.yaml")
