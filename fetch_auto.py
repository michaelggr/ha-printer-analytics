from ftplib import FTP
from pathlib import Path
with FTP('192.168.0.130', timeout=30) as ftp:
    ftp.login('hassio','2zCMbIdjPbjnxX')
    ftp.cwd('/config')
    with open('automations.yaml', 'wb') as f:
        ftp.retrbinary('RETR automations.yaml', f.write)
