DOMAIN = "printer_analytics"

CONF_PRINTER_NAME = "printer_name"
CONF_PRINT_STATUS_ENTITY = "print_status_entity"
CONF_POWER_ENTITY = "power_entity"
CONF_ENERGY_ENTITY = "energy_entity"

DATA_COORDINATOR = "coordinator"
DATA_HISTORY = "history"

SERVICE_REFRESH_STATS = "refresh_stats"
SERVICE_RESET_HISTORY = "reset_history"

PRINT_STATUS_RUNNING = "running"
PRINT_STATUS_PAUSE = "pause"
PRINT_STATUS_FINISH = "finish"
PRINT_STATUS_FAIL = "fail"
PRINT_STATUS_IDLE = "idle"

ACTIVE_PRINT_STATUSES = {PRINT_STATUS_RUNNING, PRINT_STATUS_PAUSE}
END_PRINT_STATUSES = {PRINT_STATUS_FINISH, PRINT_STATUS_FAIL}

BAMBULAB_ENTITY_KEYS = {
    "print_progress": "print_progress",
    "print_weight": "print_weight",
    "print_length": "print_length",
    "remaining_time": "remaining_time",
    "active_tray": "active_tray",
    "start_time": "start_time",
    "current_stage": "current_stage",
    "current_layer": "current_layer",
    "total_layer_count": "total_layer_count",
    "task_name": "task_name",
    "nozzle_type": "nozzle_type",
    "nozzle_size": "nozzle_size",
    "print_bed_type": "print_bed_type",
    "gcode_filename": "gcode_filename",
}

BAMBULAB_IMAGE_KEYS = {
    "cover_image": "cover_image",
}

BAMBULAB_CAMERA_KEYS = {
    "camera": "camera",
}

HISTORY_VERSION = 2
MAX_HISTORY_RECORDS = 2000

DURATION_BUCKETS = [
    ("0-30分钟", 0, 30),
    ("30-60分钟", 30, 60),
    ("1-3小时", 60, 180),
    ("3-6小时", 180, 360),
    ("6-12小时", 360, 720),
    ("12小时+", 720, float("inf")),
]
