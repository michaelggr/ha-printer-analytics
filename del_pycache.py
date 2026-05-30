import os, shutil

cache_dir = r'\\192.168.0.130\config\custom_components\printer_analytics\__pycache__'
if os.path.exists(cache_dir):
    shutil.rmtree(cache_dir)
    print(f"Deleted: {cache_dir}")
else:
    print("No __pycache__ directory found")
