import base64
import json
import sys
import urllib.error
import urllib.request


DEFAULT_OBICO_HOST = "http://192.168.0.130:3333"
DEFAULT_AUTH_TOKEN = "obico"


def build_detect_url(obico_host: str) -> str:
    """Normalize user-provided Obico host into a usable /detect endpoint."""
    host = (obico_host or "").strip()
    if not host:
        host = DEFAULT_OBICO_HOST
    host = host.rstrip("/")
    if host.endswith("/detect"):
        return f"{host}/"
    if host.endswith("/detect/"):
        return host
    return f"{host}/detect/"


def main() -> int:
    """Fetch image, call Obico detect API, and return compact JSON for HA automation."""
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print(json.dumps({"detections": [], "error": "missing image_url"}))
        return 1

    image_url = sys.argv[1].strip()
    obico_host = sys.argv[2].strip() if len(sys.argv) > 2 and sys.argv[2].strip() else DEFAULT_OBICO_HOST
    auth_token = sys.argv[3].strip() if len(sys.argv) > 3 and sys.argv[3].strip() else DEFAULT_AUTH_TOKEN
    detect_url = build_detect_url(obico_host)

    try:
        with urllib.request.urlopen(image_url, timeout=8) as resp:
            image_bytes = resp.read()
    except Exception as exc:
        print(json.dumps({"detections": [], "error": f"image fetch failed: {exc}"}))
        return 1

    payload = json.dumps(
        {"img": base64.b64encode(image_bytes).decode("ascii")}
    ).encode("utf-8")

    request = urllib.request.Request(
        detect_url,
        data=payload,
        headers={
            "Authorization": auth_token,
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=15) as resp:
            body = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        print(json.dumps({"detections": [], "error": f"http {exc.code}", "body": body}))
        return 1
    except Exception as exc:
        print(json.dumps({"detections": [], "error": f"detect failed: {exc}"}))
        return 1

    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        print(json.dumps({"detections": [], "error": "invalid json", "body": body[:2000]}))
        return 1

    # Keep HA response small. The automation only consumes `detections`.
    print(json.dumps({"detections": parsed.get("detections", [])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
