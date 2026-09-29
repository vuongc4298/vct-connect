"""Exercise deployed guest/customer fixtures and the external API ingress boundary."""

import argparse
import json
import os
import re
import time
from http.cookiejar import CookieJar
from urllib.error import HTTPError, URLError
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen

FIXTURE_URL = "https://detail.1688.com/offer/123456789012.html"
EXPECTED_RESULT = {
    "source_url": FIXTURE_URL,
    "supplier_name": "Developer Fixture Supplier",
    "fixture": True,
}
WEB_SECRET_PATTERNS = (
    re.compile(rb"sk_(?:test|live)_[A-Za-z0-9]{12,}"),
    re.compile(rb"Endpoint=sb://[^\s]+SharedAccessKey=[^\s]+", re.I),
    re.compile(rb"postgres(?:ql)?://[^\s:/]+:[^\s@]+@", re.I),
)


def request(url: str, *, token: str | None = None, body: dict | None = None, opener=None):
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = Request(
        url,
        data=json.dumps(body).encode() if body is not None else None,
        headers=headers,
        method="POST" if body is not None else "GET",
    )
    try:
        with (opener.open(req, timeout=10) if opener else urlopen(req, timeout=10)) as response:
            raw = response.read()
            return response.status, json.loads(raw) if raw else {}
    except HTTPError as error:
        raw = error.read()
        try:
            payload = json.loads(raw) if raw else {}
        except ValueError:
            payload = {}
        return error.code, payload


def check_guest_fixture(web_url: str, timeout: int) -> None:
    opener = build_opener(HTTPCookieProcessor(CookieJar()))
    status, submitted = request(
        f"{web_url}/api/v1/guest-analyses",
        body={"source_url": FIXTURE_URL}, opener=opener,
    )
    if status != 202:
        raise AssertionError(f"Guest submission returned {status}, expected 202")
    analysis_id = submitted["id"]
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status, current = request(
            f"{web_url}/api/v1/guest-analyses/{analysis_id}", opener=opener,
        )
        if status != 200:
            raise AssertionError(f"Guest status polling returned {status}")
        if current["status"] == "COMPLETED":
            expected_provenance = {
                "mode": "GUEST_PUBLIC",
                "actor_type": "GUEST",
                "extraction_method": "FIXTURE",
                "scoring_version": "v0.1.0",
            }
            if (current.get("result") != EXPECTED_RESULT
                or current.get("attempt_count") != 1
                or any(current.get(key) != value for key, value in expected_provenance.items())):
                raise AssertionError("Completed guest analysis differs from fixture or provenance")
            print("Guest fixture completed through the deployed queue with cookie-scoped status.")
            return
        if current["status"] == "FAILED_FINAL":
            raise AssertionError("Guest analysis reached FAILED_FINAL")
        time.sleep(5)
    raise TimeoutError("Guest fixture did not complete before timeout")


def run(
    web_url: str, api_url: str, token: str | None, timeout: int,
    *, ingress_only: bool = False, guest_fixture: bool = False,
) -> None:
    if not ingress_only and not token:
        raise AssertionError("Signed-in fixture requires CLERK_SMOKE_TOKEN")
    with urlopen(Request(web_url, headers={"Accept": "text/html"}), timeout=10) as response:
        web_body = response.read()
        if response.status != 200:
            raise AssertionError(f"Deployed web returned {response.status}")
    if any(pattern.search(web_body) for pattern in WEB_SECRET_PATTERNS):
        raise AssertionError("Deployed web response contains a server credential pattern")
    status, _ = request(f"{web_url}/api/v1/analyses", body={"source_url": FIXTURE_URL})
    if status != 401:
        raise AssertionError(f"Unauthenticated web API returned {status}, expected 401")
    try:
        direct_status, _ = request(f"{api_url}/healthz")
    except URLError:
        # A private FQDN may have no route or DNS answer from a hosted runner.
        direct_status = None
    if direct_status not in {None, 403, 404}:
        raise AssertionError(f"FastAPI external ingress returned {direct_status}, expected no route, 403, or 404")
    if guest_fixture:
        check_guest_fixture(web_url, timeout)
    if ingress_only:
        print("Ingress and web response checks passed; signed-in fixture gate is pending.")
        return
    status, submitted = request(
        f"{web_url}/api/v1/analyses", token=token,
        body={"source_url": FIXTURE_URL},
    )
    if status != 202:
        raise AssertionError(f"Signed-in submission returned {status}, expected 202")
    analysis_id = submitted["id"]
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status, current = request(f"{web_url}/api/v1/analyses/{analysis_id}", token=token)
        if status != 200:
            raise AssertionError(f"Status polling returned {status}")
        if current["status"] == "COMPLETED":
            if current["attempt_count"] != 1 or current.get("result") != EXPECTED_RESULT:
                raise AssertionError("Completed analysis does not match the single expected fixture result")
            print("Signed-in fixture completed once through the deployed queue.")
            return
        if current["status"] == "FAILED_FINAL":
            raise AssertionError("Analysis reached FAILED_FINAL")
        time.sleep(5)
    raise TimeoutError("Signed-in fixture did not complete before timeout")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--web-url", required=True)
    parser.add_argument("--api-url", required=True)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--ingress-only", action="store_true")
    parser.add_argument("--guest-fixture", action="store_true")
    args = parser.parse_args()
    try:
        run(
            args.web_url.rstrip("/"), args.api_url.rstrip("/"),
            os.getenv("CLERK_SMOKE_TOKEN"), args.timeout,
            ingress_only=args.ingress_only, guest_fixture=args.guest_fixture,
        )
    except (AssertionError, TimeoutError, URLError, ValueError) as exc:
        print(f"Deployment smoke failed: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
