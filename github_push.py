import json, base64, urllib.request

files = [
    "custom_components/printer_analytics/coordinator.py",
    "custom_components/printer_analytics/www/pa-v5.2.js",
    "www/pa-v5.2.js",
]
owner = "michaelggr"
repo = "ha-printer-analytics"
branch = "main"
base = f"https://api.github.com/repos/{owner}/{repo}/contents"

for path in files:
    local = rf"g:\dev\ha\ha\{path.replace('/', chr(92))}"
    with open(local, "r", encoding="utf-8") as f:
        content = f.read()
    print(f"Read {path}: {len(content)} chars")

    url = f"{base}/{path}"
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github.v3+json")
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        sha = json.loads(resp.read())["sha"]
    except Exception as e:
        print(f"SKIP {path}: {e}")
        continue

    payload = json.dumps({
        "message": "refactor: 魔法数字替换为const常量+移除update_interval",
        "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
        "sha": sha,
        "branch": branch,
    }).encode("utf-8")

    req = urllib.request.Request(url, data=payload, method="PUT")
    req.add_header("Accept", "application/vnd.github.v3+json")
    req.add_header("Content-Type", "application/json")
    try:
        resp = urllib.request.urlopen(req, timeout=60)
        r = json.loads(resp.read())
        print(f"OK: {path} -> {r['commit']['sha'][:8]}")
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:200]
        print(f"FAIL: {path}: {e.code} - {body}")
    except Exception as e:
        print(f"FAIL: {path}: {e}")
