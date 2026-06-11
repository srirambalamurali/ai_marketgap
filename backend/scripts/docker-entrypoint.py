from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from urllib.parse import urlparse

import requests


def _wait_for_tcp(host: str, port: int, timeout_seconds: int = 60) -> None:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=5):
                return
        except Exception as exc:
            last_error = exc
            time.sleep(1)
    raise RuntimeError(f"Timed out waiting for TCP {host}:{port}: {last_error}")


def _wait_for_http(url: str, timeout_seconds: int = 60) -> None:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            response = requests.get(url, timeout=5)
            if response.ok:
                return
        except Exception as exc:
            last_error = exc
        time.sleep(1)
    raise RuntimeError(f"Timed out waiting for HTTP {url}: {last_error}")


def main() -> None:
    postgres_host = os.getenv("POSTGRES_HOST", "postgres")
    postgres_port = int(os.getenv("POSTGRES_PORT", "5432"))
    chroma_url = os.getenv("CHROMA_URL")
    chroma_host = os.getenv("CHROMA_HOST", "chroma")
    chroma_port = int(os.getenv("CHROMA_PORT", "8000"))
    startup_timeout = int(os.getenv("STARTUP_TIMEOUT_SECONDS", "120"))

    print(f"Waiting for PostgreSQL at {postgres_host}:{postgres_port} ...", flush=True)
    _wait_for_tcp(postgres_host, postgres_port, timeout_seconds=startup_timeout)

    if chroma_url:
        parsed = urlparse(chroma_url)
        base_url = chroma_url.rstrip("/")
        host = parsed.hostname or chroma_host
        port = parsed.port or chroma_port
        print(f"Waiting for ChromaDB at {base_url} ...", flush=True)
        _wait_for_tcp(host, port, timeout_seconds=startup_timeout)
        _wait_for_http(f"{base_url}/api/v2/heartbeat", timeout_seconds=startup_timeout)
    else:
        print(f"Waiting for ChromaDB at {chroma_host}:{chroma_port} ...", flush=True)
        _wait_for_tcp(chroma_host, chroma_port, timeout_seconds=startup_timeout)

    cmd = [
        "uvicorn",
        "app.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        "8007",
    ]
    print("Starting backend:", " ".join(cmd), flush=True)
    os.execvp(cmd[0], cmd)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Backend startup failed: {exc}", file=sys.stderr, flush=True)
        raise
