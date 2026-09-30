"""Register the local VCT Connect extension origin with the Clerk dev instance.

Reads the existing ignored .env.clerk file. Never prints the secret key.
Preserves all allowed origins already present on the Clerk instance.
"""

from pathlib import Path
import json
import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
ORIGIN = "chrome-extension://klggcepemjjbphjclpiabgpfgdbgiljj"
INSTANCE_URL = "https://api.clerk.com/v1/instance"


def main() -> None:
    lines = (ROOT / ".env.clerk").read_text(encoding="utf-8").splitlines()
    values = dict(line.split("=", 1) for line in lines
                  if line and not line.lstrip().startswith("#") and "=" in line)
    key = values.get("CLERK_SECRET_KEY", "").strip().strip('"').strip("'")
    if not key.startswith("sk_test_"):
        raise SystemExit("Expected a Clerk development secret key in .env.clerk")
    headers = {
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
        "User-Agent": "VCT-Connect-Development/0.1",
    }
    try:
        with urllib.request.urlopen(urllib.request.Request(INSTANCE_URL, headers=headers), timeout=20) as response:
            instance = json.load(response)
        existing = instance.get("allowed_origins") or []
        if not isinstance(existing, list) or not all(isinstance(item, str) for item in existing):
            raise SystemExit("Clerk returned an unexpected allowed_origins value")
        if ORIGIN in existing:
            print(f"Already registered: {ORIGIN}")
            return
        body = json.dumps({"allowed_origins": [*existing, ORIGIN]}).encode("utf-8")
        request = urllib.request.Request(INSTANCE_URL, data=body, method="PATCH", headers={
            **headers, "Content-Type": "application/json",
        })
        with urllib.request.urlopen(request, timeout=20) as response:
            if not 200 <= response.status < 300:
                raise SystemExit(f"Clerk update returned HTTP {response.status}")
        print(f"Registered: {ORIGIN}")
    except urllib.error.HTTPError as exc:
        error_body = exc.read(4096).decode("utf-8", errors="replace")
        if "error code: 1010" in error_body.lower():
            raise SystemExit(
                "Clerk's network protection blocked this API client (HTTP 403, Cloudflare 1010). "
                "This response does not verify whether the development key is valid."
            ) from None
        raise SystemExit(f"Clerk returned HTTP {exc.code}; verify API access for the development instance") from None
    except urllib.error.URLError as exc:
        raise SystemExit("Could not reach Clerk API from this network") from None


if __name__ == "__main__":
    main()
