from ftplib import FTP
ftp=FTP('192.168.0.130', timeout=30)
ftp.login('hassio','2zCMbIdjPbjnxX')
ftp.cwd('/config')
ftp.retrlines('LIST')
ftp.quit()
