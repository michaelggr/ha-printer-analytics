import base64
import json
import sys
import urllib.error
import urllib.request


DETECT_URL = "http://192.168.0.130:3333/detect/"
AUTH_TOKEN = "obico"


def main() -> int:
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print(json.dumps({"detections": [], "error": "missing image_url"}))
        return 1

    image_url = sys.argv[1].strip()

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
        DETECT_URL,
        data=payload,
        headers={
            "Authorization": AUTH_TOKEN,
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
