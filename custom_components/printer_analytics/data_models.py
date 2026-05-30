"""数据模型定义"""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PrinterStats:
    """打印统计数据"""
    total_prints: int = 0
    successful_prints: int = 0
    failed_prints: int = 0
    cancelled_prints: int = 0
    success_rate: float = 0.0
    average_duration_hours: float = 0.0
    total_duration_hours: float = 0.0
    total_weight_g: float = 0.0
    total_length_m: float = 0.0
    total_energy_kwh: float = 0.0
    stats_7d: dict = field(default_factory=dict)
    stats_30d: dict = field(default_factory=dict)
    stats_lifetime: dict = field(default_factory=dict)
    duration_distribution: dict = field(default_factory=dict)
    activity_heatmap: dict = field(default_factory=dict)
    failure_stage_distribution: dict = field(default_factory=dict)
    filament_success_stats: dict = field(default_factory=dict)
    # 新增统计图表
    multi_color_ratio: dict = field(default_factory=dict)       # 多色模型占比 {multi: N, single: N}
    prepare_time_by_filament: dict = field(default_factory=dict) # 各材料类型平均准备时间 {PLA: {avg, count}, ...}
    slice_mode_distribution: dict = field(default_factory=dict)  # 切片模式分布 {cloud: N, local: N}
    over_500g_ratio: dict = field(default_factory=dict)         # 超500g模型占比 {over: N, under: N}
    nozzle_size_distribution: dict = field(default_factory=dict) # 喷嘴尺寸分布 {0.4: N, 0.2: N, ...}
    failed_chamber_temp_distribution: dict = field(default_factory=dict)  # 失败仓温分布
    extreme_stats: dict = field(default_factory=dict)  # 之最打印 {longest, shortest, heaviest, lightest, most_colors}
    # 通用字段
    history: list = field(default_factory=list)
    current_print: dict | None = None
    is_printing: bool = False
    last_update: str = ""
    _entity_map_debug: dict = field(default_factory=dict)


@dataclass
class ChamberTempEntry:
    """腔体温度记录"""
    time: str
    temp: float


@dataclass
class ColorChange:
    """颜色切换记录"""
    timestamp: str
    from_color: str | None
    to_color: str
    from_type: str | None
    to_type: str
    change_number: int


@dataclass
class ColorUsageEntry:
    """耗材使用记录"""
    color: str
    type: str
    weight_g: float
    length_m: float
    tray: str = ""
    start_time: str = ""


@dataclass
class PrintRecord:
    """打印记录"""
    id: str
    start_time: str
    end_time: str
    status: str
    duration_hours: float
    progress: int
    total_weight: float | None
    total_length: float | None
    filament_type: str | None
    filament_color: str | None
    colors_used: list[str]
    types_used: list[str]
    total_colors: int
    color_changes_count: int
    multi_color_summary: dict | None
    color_usage: list[ColorUsageEntry]
    energy_kwh: float | None
    task_name: str | None
    nozzle_type: str | None
    nozzle_size: str | None
    print_bed_type: str | None
    total_layer_count: int | None
    cover_image_url: str | None
    cover_image_local: str | None
    snapshot_image_local: str | None
    chamber_temp_final: float | None
    chamber_temp_last5min: dict | None
