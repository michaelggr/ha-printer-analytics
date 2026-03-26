from ftplib import FTP
from pathlib import Path
from io import BytesIO
path = Path('ha_export/blueprints/automation/spaghetti_detection_xiaomi.yaml')
data = BytesIO(path.read_bytes())
with FTP('192.168.0.130', timeout=30) as ftp:
    ftp.login('hassio','2zCMbIdjPbjnxX')
    ftp.cwd('/config/blueprints/automation')
    ftp.storbinary('STOR spaghetti_detection_xiaomi.yaml', data)
