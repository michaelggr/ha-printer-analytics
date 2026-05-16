DOMAIN = "printer_analytics"

CONF_PRINTER_NAME = "printer_name"
CONF_PRINT_STATUS_ENTITY = "print_status_entity"
CONF_POWER_ENTITY = "power_entity"
CONF_ENERGY_ENTITY = "energy_entity"
CONF_CHAMBER_TEMP_ENTITY = "chamber_temp_entity"

DATA_COORDINATOR = "coordinator"
DATA_HISTORY = "history"

SERVICE_REFRESH_STATS = "refresh_stats"
SERVICE_RESET_HISTORY = "reset_history"
SERVICE_DELETE_HISTORY_RECORDS = "delete_history_records"
SERVICE_BACKFILL_COVER_IMAGES = "backfill_cover_images"
SERVICE_BACKFILL_SNAPSHOTS = "backfill_snapshots"
SERVICE_BACKFILL_TASK_NAMES = "backfill_task_names"

PRINT_STATUS_RUNNING = "running"
PRINT_STATUS_PAUSE = "pause"
PRINT_STATUS_FINISH = "finish"
PRINT_STATUS_FAIL = "fail"
PRINT_STATUS_IDLE = "idle"
PRINT_STATUS_CANCELLED = "cancelled"

ACTIVE_PRINT_STATUSES = {PRINT_STATUS_RUNNING, PRINT_STATUS_PAUSE}
END_PRINT_STATUSES = {PRINT_STATUS_FINISH, PRINT_STATUS_FAIL, PRINT_STATUS_CANCELLED}

INVALID_ENTITY_STATES = frozenset({"unknown", "unavailable", ""})

BAMBULAB_ENTITY_KEYS = {
    "print_progress": ["print_progress"],
    "print_weight": ["print_weight"],
    "print_length": ["print_length"],
    "remaining_time": ["remaining_time"],
    "active_tray": ["active_tray"],
    "start_time": ["start_time"],
    "current_stage": ["current_stage", "stage"],
    "current_layer": ["current_layer"],
    "total_layer_count": ["total_layer_count", "total_layers"],
    "task_name": ["task_name", "subtask_name"],
    "nozzle_type": ["nozzle_type"],
    "nozzle_size": ["nozzle_size", "nozzle_diameter"],
    "print_bed_type": ["print_bed_type"],
    "speed_profile": ["speed_profile"],
    "gcode_filename": ["gcode_filename", "gcode_file"],
    "chamber_temperature": [
        "chamber_temperature",
        "chamber_temp",
        " enclosure_temp",  # A1 Mini 命名
        "chamber",
    ],
}

BAMBULAB_IMAGE_KEYS = {
    "cover_image": "cover_image",
}

BAMBULAB_CAMERA_KEYS = {
    "camera": "camera",
}

HISTORY_VERSION = 3
MAX_HISTORY_RECORDS = 0

DURATION_BUCKETS = [
    ("0-30分钟", 0, 30),
    ("30-60分钟", 30, 60),
    ("1-3小时", 60, 180),
    ("3-6小时", 180, 360),
    ("6-12小时", 360, 720),
    ("12小时+", 720, float("inf")),
]

FAILURE_STAGE_BUCKETS = [
    ("早期(0-30%)", 0, 30),
    ("中期(30-70%)", 30, 70),
    ("后期(70-99%)", 70, 100),
]

CARD_FILENAME = "pa-v5.2.js"
CARD_VERSION = "5.9.0"
CARD_URL = f"/local/{CARD_FILENAME}?v={CARD_VERSION}"
DASHBOARD_FILE = "ui-printer-analytics.yaml"
PLATFORMS = ["sensor"]

HTTP_CONNECTION_LIMIT = 10
HTTP_CONNECTION_PER_HOST = 5
MATERIAL_CACHE_INTERVAL_SECONDS = 60
MAX_FULL_BACKUPS = 12
SYNC_ARCHIVE_COUNT = 3
COLOR_CONFIRM_THRESHOLD = 3
CHAMBER_TEMP_WINDOW_MINUTES = 5

ENERGY_MAX_DELTA_KWH = 10
IMAGE_MIN_SIZE_BYTES = 100
ENTITY_DISCOVERY_DELAY_SECS = 30
ENTITY_DISCOVERY_RETRY_SECS = 60
TASK_NAME_CAPTURE_WINDOW_SECS = 60
HTTP_REQUEST_TIMEOUT_SECS = 15
HTTP_SESSION_TIMEOUT_SECS = 30
