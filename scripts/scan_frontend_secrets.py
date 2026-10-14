from pathlib import Path
import argparse
import os
import re
import zipfile


ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "frontend" / "apps" / "web" / ".next"
EXTENSION = ROOT / "frontend" / "apps" / "web" / "private"
SENSITIVE_KEYS = {
    "AZURE_SERVICE_BUS_CONNECTION_STRING",
    "CLERK_JWT_KEY",
    "CLERK_SECRET_KEY",
    "DATABASE_URL",
    "YESCALE_API_KEY",
}
FORBIDDEN_PATTERNS = (
    re.compile(rb"sk_(?:test|live)_[A-Za-z0-9]{12,}"),
    re.compile(rb"Endpoint=sb://[^\s]+SharedAccessKey=[^\s]+", re.I),
    re.compile(rb"postgres(?:ql)?://[^\s:/]+:[^\s@]+@", re.I),
)


def configured_secrets() -> dict[str, bytes]:
    values: dict[str, bytes] = {
        name: value.encode() for name in SENSITIVE_KEYS
        if (value := os.getenv(name))
    }
    for env_file in (ROOT / ".env", ROOT / ".env.clerk", ROOT / "frontend" / "apps" / "web" / ".env.local"):
        if not env_file.exists():
            continue
        for raw_line in env_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)
            if name in SENSITIVE_KEYS and value:
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                    value = value[1:-1]
                if value:
                    values[name] = value.encode()
    return values


def scan(paths: list[Path], secrets: dict[str, bytes]) -> list[tuple[str, Path]]:
    hits: list[tuple[str, Path]] = []
    for root in paths:
        files = root.rglob("*") if root.is_dir() else (root,)
        for path in files:
            if not path.is_file():
                continue
            payloads = [(path, path.read_bytes())]
            if path.suffix == ".zip":
                with zipfile.ZipFile(path) as archive:
                    payloads.extend((path / item.filename, archive.read(item)) for item in archive.infolist())
            for location, data in payloads:
                for name, value in secrets.items():
                    if len(value) >= 8 and value in data:
                        hits.append((name, location))
                if any(pattern.search(data) for pattern in FORBIDDEN_PATTERNS):
                    hits.append(("credential pattern", location))
    return hits


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-log", type=Path, action="append", default=[])
    args = parser.parse_args()
    if not BUILD.exists():
        print("Frontend build is missing; run npm run build --prefix frontend first.")
        return 2
    missing_logs = [path for path in args.build_log if not path.is_file()]
    if missing_logs:
        print("Requested build log is missing.")
        return 2
    hits = scan([BUILD, EXTENSION, *args.build_log], configured_secrets())
    if hits:
        for name, path in hits:
            print(f"{name} found in {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path.name}")
        return 1
    print("No configured server credentials found in the frontend build.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
