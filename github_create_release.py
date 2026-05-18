﻿import subprocess, json, base64, urllib.request

def create_github_release(tag_name, title, body):
    """
    创建 GitHub Release
    
    参数:
        tag_name: 标签名 (如 "v5.9.3")
        title: Release 标题
        body: Release 描述 (支持 Markdown)
    """
    # 从 git credential manager 获取凭证
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
    print(f"使用凭证: {username}")

    owner = "michaelggr"
    repo = "ha-printer-analytics"
    api_url = f"https://api.github.com/repos/{owner}/{repo}/releases"

    # 构建 Release 数据
    payload = json.dumps({
        "tag_name": tag_name,
        "target_commitish": "main",
        "name": title,
        "body": body,
        "draft": False,
        "prerelease": False
    }).encode("utf-8")

    # 发送请求
    req = urllib.request.Request(api_url, data=payload, method="POST")
    req.add_header("Accept", "application/vnd.github.v3+json")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Basic {base64.b64encode(f'{username}:{password}'.encode()).decode()}")
    req.add_header("User-Agent", "python")

    try:
        resp = urllib.request.urlopen(req, timeout=60)
        result = json.loads(resp.read())
        print(f"✅ Release 创建成功！")
        print(f"   标签: {result['tag_name']}")
        print(f"   标题: {result['name']}")
        print(f"   URL: {result['html_url']}")
        return result
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"❌ 失败: {e.code} - {body}")
    except Exception as e:
        print(f"❌ 错误: {e}")

# 创建 Release
if __name__ == "__main__":
    create_github_release(
        tag_name="v5.9.4",
        title="v5.9.4",
        body="## v5.9.4\n\n### 修复内容\n\n- **修复了线程安全问题，将同步方法中的 async_create_task 替换为 add_job\n\n## v5.9.3\n\n### 修复内容\n\n- **修复了打印机分析仪表板配置问题，恢复了正确的单一视图结构\n- 顶部实时监控 + 内部三页签（统计分析/之最/全部历史)\n- 支持在统计分析中切换不同打印机"
    )
