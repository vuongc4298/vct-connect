"""Verify the actual web server's public branding and private ZIP with isolated auth.

The fake token never leaves loopback. No production identity, DB or model calls.
"""
import argparse
import base64
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from html.parser import HTMLParser
from io import BytesIO
import json
import os
from pathlib import Path
import socket
import subprocess
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zipfile import ZipFile


class AuthBoundary(BaseHTTPRequestHandler):
    def do_GET(self):
        valid = self.path == "/api/v1/me" and self.headers.get("Authorization") == "Bearer download-fixture"
        self.send_response(200 if valid else 401)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"plan":"FREE"}' if valid else b'{"detail":"Unauthorized"}')

    def log_message(self, *_):
        pass


def available_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def fetch(url, token=None):
    request = Request(url, headers={"Authorization": f"Bearer {token}"} if token else {})
    try:
        return urlopen(request, timeout=10)
    except HTTPError as response:
        return response


class PageMetadata(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self.in_title = False
        self.icons = []
        self.theme_color = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "title":
            self.in_title = True
        elif tag == "link" and "icon" in attrs.get("rel", "").split():
            self.icons.append(attrs)
        elif tag == "meta" and attrs.get("name") == "theme-color":
            self.theme_color = attrs.get("content")

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title += data


def verify_branding(origin):
    public = Path(__file__).resolve().parents[1] / "frontend" / "apps" / "web" / "public"
    for filename, content_types in [
        ("vct-logo.jpg", {"image/jpeg"}),
        ("vct-icon.ico", {"image/x-icon", "image/vnd.microsoft.icon"}),
    ]:
        with fetch(f"{origin}/{filename}") as response:
            assert response.status == 200, f"Anonymous branding asset missing: {filename}"
            assert response.headers.get_content_type() in content_types, f"Wrong content type: {filename}"
            assert response.read() == (public / filename).read_bytes(), f"Branding asset differs from source: {filename}"
    with fetch(origin) as response:
        assert response.status == 200
        assert response.headers.get_content_type() == "text/html"
        metadata = PageMetadata()
        metadata.feed(response.read().decode("utf-8"))
    assert metadata.title == "VCT Connect", "Missing frontend title"
    assert metadata.theme_color == "#09234c", "Missing frontend theme color"
    assert any(icon.get("href") == "/vct-icon.ico" and icon.get("type") == "image/x-icon"
               and icon.get("sizes") == "56x56" for icon in metadata.icons), "Missing frontend browser icon"


def main():
    parser = argparse.ArgumentParser()
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--image")
    target.add_argument("--standalone", type=Path)
    parser.add_argument("--node", default="node")
    args = parser.parse_args()
    auth = ThreadingHTTPServer(("127.0.0.1", 0), AuthBoundary)
    threading.Thread(target=auth.serve_forever, daemon=True).start()
    port = available_port()
    env = {**os.environ, "PORT": str(port), "HOSTNAME": "127.0.0.1", "API_INTERNAL_ORIGIN": f"http://127.0.0.1:{auth.server_port}"}
    command = (["docker", "run", "--rm", "--network", "host", "--env", f"PORT={port}", "--env", "HOSTNAME=127.0.0.1", "--env", f"API_INTERNAL_ORIGIN={env['API_INTERNAL_ORIGIN']}", args.image]
               if args.image else [args.node, str(args.standalone.resolve())])
    process = subprocess.Popen(command, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}/api/v1/extension-download"
    try:
        deadline = time.monotonic() + 60
        while True:
            try:
                with fetch(url) as response:
                    assert response.status == 401
                    break
            except (URLError, OSError):
                if time.monotonic() > deadline or process.poll() is not None:
                    raise RuntimeError("Web server did not start")
                time.sleep(.25)
        verify_branding(f"http://127.0.0.1:{port}")
        with fetch(url, "invalid-fixture") as response:
            assert response.status == 401
            assert response.headers.get("Cache-Control") == "private, no-store"
        with fetch(url, "download-fixture") as response:
            assert response.status == 200
            assert response.headers.get("Content-Type") == "application/zip"
            assert response.headers.get("Cache-Control") == "private, no-store"
            assert "vct-connect-extension.zip" in response.headers.get("Content-Disposition", "")
            data = response.read()
        with ZipFile(BytesIO(data)) as archive:
            assert archive.testzip() is None
            assert set(archive.namelist()) == {"manifest.json", "popup.html", "popup.css", "icon.png", "popup.js", "background.js"}
            manifest = json.loads(archive.read("manifest.json"))
            assert manifest["version"] == "0.7.3"
            assert "Taobao" not in manifest["description"]
            assert manifest["icons"]["128"] == "icon.png"
            identity = hashlib.sha256(base64.b64decode(manifest["key"])).hexdigest()[:32]
            extension_id = "".join(chr(ord("a") + int(character, 16)) for character in identity)
            assert extension_id == "klggcepemjjbphjclpiabgpfgdbgiljj"
            assert "https://vct-connect-dev-web.blackdesert-0144dda1.southeastasia.azurecontainerapps.io/*" in manifest["host_permissions"]
            assert not any("127.0.0.1" in host or "localhost" in host for host in manifest["host_permissions"])
        # Private files are never public Next/static assets.
        for path in ["/private/vct-connect-extension.zip", "/extension/vct-connect-extension.zip"]:
            with fetch(f"http://127.0.0.1:{port}{path}") as response:
                assert response.status == 404
        print("Actual web server: anonymous branding bytes/content types and page metadata verified; anonymous/invalid download denied, verified download CRC/manifest passed, private paths inaccessible. Auth uses a loopback fixture.")
    finally:
        process.terminate()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        auth.shutdown()


if __name__ == "__main__":
    main()
