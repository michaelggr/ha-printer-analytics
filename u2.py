﻿import shutil
src = r'G:\dev\ha\ha\custom_components\printer_analytics\www\pa-v5.11.js'
shutil.copy2(src, r'\\192.168.0.130\config\custom_components\printer_analytics\www\pa-v5.11.js')
shutil.copy2(src, r'\\192.168.0.130\config\www\pa-v5.11.js')
print("OK")
