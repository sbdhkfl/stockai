"""Shared test fixtures: a real uvicorn server (module-scoped thread) serving
the FastAPI app — used by SDK, CLI and API tests. No fake transports.
"""
import socket
import threading
import time

import pytest
import uvicorn

from fairvalue.api.app import app


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def server_url():
    port = _free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"
    import httpx
    for _ in range(100):
        try:
            if httpx.get(f"{base}/health", timeout=1).status_code == 200:
                break
        except Exception:
            time.sleep(0.1)
    yield base
    server.should_exit = True
    thread.join(timeout=5)
