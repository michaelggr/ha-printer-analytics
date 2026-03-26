from ftplib import FTP
with FTP('192.168.0.130', timeout=30) as ftp:
    ftp.login('hassio','2zCMbIdjPbjnxX')
    ftp.cwd('/config/blueprints/automation')
    with open('remote_spaghetti.yaml','wb') as f:
        ftp.retrbinary('RETR spaghetti_detection_xiaomi.yaml', f.write)
