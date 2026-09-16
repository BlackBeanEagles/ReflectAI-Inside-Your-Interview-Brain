"""
Two bugs in the rate limiter that only show up in production.

1. Its per-IP table grew forever. Nothing ever removed a key, so every
   address that ever posted kept an entry for the life of the process --
   including the empty deques left behind after a visitor stopped. On a
   public endpoint that is unbounded growth driven by traffic.

2. It was measuring the wrong address entirely. uvicorn ignores
   X-Forwarded-For unless the immediate peer is trusted, and trusts only
   127.0.0.1 by default, so on a hosted deployment behind a proxy every
   request looked like it came from that proxy -- one shared bucket for
   the whole user base, and interviewees throttling each other. That one
   is fixed in the Dockerfile, so it is asserted there.
"""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.main import app


@pytest.fixture(autouse=True)
def _clear_log():
    main._request_log.clear()
    main._sweep_counter = 0
    yield
    main._request_log.clear()
    main._sweep_counter = 0


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_stale_buckets_are_swept():
    now = time.monotonic()
    # One address active right now, many that went quiet long ago.
    main._request_log["10.0.0.1"].append(now)
    for i in range(50):
        main._request_log[f"10.9.9.{i}"].append(now - main.RATE_LIMIT_WINDOW_S - 60)

    main._sweep_rate_limit_log(now)

    assert "10.0.0.1" in main._request_log
    assert len(main._request_log) == 1, "stale addresses should be gone"


def test_empty_buckets_are_swept():
    # defaultdict access alone creates one of these, so they accumulate
    # even for addresses that were rate-limited rather than served.
    main._request_log["10.0.0.2"]
    assert len(main._request_log) == 1
    main._sweep_rate_limit_log(time.monotonic())
    assert len(main._request_log) == 0


def test_the_sweep_runs_on_its_own_during_traffic(client: TestClient):
    # The sweep is driven by a request counter, so it has to actually fire
    # without anyone calling it.
    main._sweep_counter = main._RATE_LIMIT_SWEEP_EVERY - 1
    main._request_log["10.9.9.9"].append(
        time.monotonic() - main.RATE_LIMIT_WINDOW_S - 60
    )

    client.post("/session/start")

    assert "10.9.9.9" not in main._request_log, "a stale bucket survived a sweep"


def test_sweeping_does_not_forget_someone_mid_window(client: TestClient):
    # A sweep must not hand an active client a fresh allowance -- that
    # would turn the cleanup into a way around the limit.
    for _ in range(main.RATE_LIMIT_MAX_REQUESTS):
        client.post("/session/start")

    main._sweep_rate_limit_log(time.monotonic())

    r = client.post("/session/start")
    assert r.status_code == 429, "the limit was reset by a sweep"


def test_limit_still_applies(client: TestClient):
    for _ in range(main.RATE_LIMIT_MAX_REQUESTS):
        assert client.post("/session/start").status_code == 200
    assert client.post("/session/start").status_code == 429


def test_deployment_trusts_proxy_headers():
    # Without this the limiter buckets every visitor under the platform's
    # proxy address, which silently turns a per-client limit into a global
    # one. It is a deployment flag, so this is where it can be checked.
    import io

    dockerfile = io.open("Dockerfile", encoding="utf-8").read()
    cmd = [ln for ln in dockerfile.splitlines() if ln.startswith("CMD")]
    assert cmd, "no CMD in the Dockerfile"
    assert "--proxy-headers" in cmd[0]
    assert "--forwarded-allow-ips" in cmd[0]
