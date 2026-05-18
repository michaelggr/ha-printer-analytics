# -*- coding: utf-8 -*-
import subprocess, json, base64, urllib.request

def create_github_release(tag_name, title, body):
    """Create GitHub Release"""
    proc = subprocess.run(
        ["git", "credential", "fill"],
        input="protocol=https\nhost=github.com\n\n",
        capture_output=True, text=True, cwd=r"g:\dev\ha\ha"
    )
    creds = {}
    for line in proc.stdout.strip().split("\n"):
        if "=" in line:
            k, v = line.split("=", 1)
            creds[k] = v

    username = creds.get("username", "")
    password = creds.get("password", "")

    owner = "michaelggr"
    repo = "ha-printer-analytics"
    api_url = f"https://api.github.com/repos/{owner}/{repo}/releases"

    payload = json.dumps({
        "tag_name": tag_name,
        "target_commitish": "main",
        "name": title,
        "body": body,
        "draft": False,
        "prerelease": False
    }).encode("utf-8")

    req = urllib.request.Request(api_url, data=payload, method="POST")
    req.add_header("Accept", "application/vnd.github.v3+json")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Basic {base64.b64encode(f'{username}:{password}'.encode()).decode()}")
    req.add_header("User-Agent", "python")

    try:
        resp = urllib.request.urlopen(req, timeout=60)
        result = json.loads(resp.read())
        print(f"SUCCESS: Release created!")
        print(f"   Tag: {result['tag_name']}")
        print(f"   URL: {result['html_url']}")
        return result
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"FAILED: {e.code} - {body}")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    create_github_release(
        tag_name="v5.10.4",
        title="v5.10.4",
        body="""## v5.10.4

### Bug Fixes

- **修复启动时状态同步问题**：当打印机状态已经是 running 但 current_print 为空时，自动恢复打印追踪
- 改进状态获取逻辑，直接读取实体状态而非通过中间层
"""
    )
