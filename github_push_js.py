import subprocess, json, base64, urllib.request

# Get GitHub credentials from git credential manager
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
print(f"Got credentials for: {username}")

files = [
    {
        "path": "custom_components/printer_analytics/www/pa-v5.2.js",
        "sha": "d22486f69894e97fd45782534fb89567ae0e70b3",
    },
    {
        "path": "www/pa-v5.2.js",
        "sha": "944a8d1eedfbefd565ff50e1e0c811ed13a78f4d",
    },
]

base = "https://api.github.com/repos/michaelggr/ha-printer-analytics/contents"

for f in files:
    local = rf"g:\dev\ha\ha\{f['path'].replace('/', chr(92))}"
    with open(local, "rb") as fh:
        content_b64 = base64.b64encode(fh.read()).decode()
    print(f"Read {f['path']}: {len(content_b64)} bytes base64")

    payload = json.dumps({
        "message": "fix: add disconnectedCallback, _sanitizeColor, CSS hover, escape img src, remove console.log",
        "content": content_b64,
        "sha": f["sha"],
        "branch": "main",
    }).encode()

    req = urllib.request.Request(f"{base}/{f['path']}", data=payload, method="PUT")
    req.add_header("Accept", "application/vnd.github.v3+json")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Basic {base64.b64encode(f'{username}:{password}'.encode()).decode()}")
    req.add_header("User-Agent", "python")

    try:
        resp = urllib.request.urlopen(req, timeout=120)
        r = json.loads(resp.read())
        print(f"OK: {f['path']} -> {r['commit']['sha'][:8]}")
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:300]
        print(f"FAIL: {f['path']}: {e.code} - {body}")
    except Exception as e:
        print(f"FAIL: {f['path']}: {e}")
