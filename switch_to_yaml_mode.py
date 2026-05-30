import urllib.request, json

TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiI3Y2EyNjc2MzdmZGU0YzliOWQ3Y2Y3ODM3N2YwMzA5ZSIsImlhdCI6MTc3ODk2OTYzNCwiZXhwIjoyMDk0MzI5NjM0fQ.iFan1gdP67hAY5jn0ilFABv98DbA79TFTHg76PyNhJY"
HA_URL = "http://192.168.0.130:8123"

def api_request(path, method="GET", data=None):
    req = urllib.request.Request(f"{HA_URL}{path}", 
                                  headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
                                  method=method)
    if data:
        req.data = json.dumps(data).encode()
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        return json.loads(resp.read())
    except Exception as e:
        print(f"API Error {path}: {e}")
        return None

# 获取当前 lovelace 配置
print("=== 当前 Lovelace 配置 ===")
config = api_request("/api/config/core/config")
if config:
    mode = config.get("lovelace_mode", "unknown")
    print(f"当前模式: {mode}")
    
    if mode == "storage":
        print("\n正在切换到 YAML 模式...")
        
        # 更新配置为 YAML 模式
        update_data = {"lovelace_mode": "yaml"}
        result = api_request("/api/config/core/config", "POST", update_data)
        if result:
            print("✅ 已切换到 YAML 模式！")
            print("⚠️  请重启 HA 使配置生效")
        else:
            print("❌ 切换失败")
    else:
        print(f"已经是 {mode} 模式，无需修改")
else:
    print("无法获取配置")