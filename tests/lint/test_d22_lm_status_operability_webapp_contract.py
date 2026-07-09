"""D-22 lm-status-operability webapp surface contract lint.

Pins the D-22 "Language Model Status & Operability" cockpit panel to the
same sovereignty-clean webapp doctrine every other panel obeys: a
single-file monochrome SPA served by its API daemon under /webapp/ from
the SAME host:port binding as the JSON endpoints, zero external
dependencies, same-origin fetches only, and READ-ONLY (all model/agent
actions are MS003-signed CLI verbs, never web mutations — R10212).

The panel is a different *rendering* of the shared model-health core
(scripts/inference/model-health.py) — per-device (CPU0/GPU0/GPU1) Model
0/1/2 status + operability Actions/Tests + a render-only Chat — NOT a new
data source.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

import json
import re
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WEBAPP_HTML = REPO_ROOT / "webapp" / "d-22-lm-status-operability" / "index.html"
API_DAEMON = REPO_ROOT / "scripts" / "operator" / "lm-status-operability-api.py"
SURFACE_MAP = REPO_ROOT / "scripts" / "operator" / "surface-map.py"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _spawn_api(port: int):
    env = {
        "LM_STATUS_API_BIND": "127.0.0.1",
        "LM_STATUS_API_PORT": str(port),
        "SOVEREIGN_OS_METRICS_DIR": "/tmp/sovereign-os-test-metrics",
        "PATH": "/usr/bin:/bin",
    }
    proc = subprocess.Popen(
        ["python3", str(API_DAEMON)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    deadline = time.time() + 6
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/healthz", timeout=0.5
            ) as r:
                if r.status == 200:
                    return proc
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(0.1)
    proc.kill()
    raise RuntimeError("lm-status-operability-api failed to start within 6s")


def test_webapp_html_present():
    assert WEBAPP_HTML.is_file(), f"D-22 webapp asset missing: {WEBAPP_HTML}"


def test_webapp_html_is_html5():
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert body.lstrip().lower().startswith("<!doctype html>")
    assert "<html lang=" in body
    assert 'name="viewport"' in body


def test_webapp_carries_sovereign_meta_tags():
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert 'name="x-sovereign-module"' in body
    assert "d-22-lm-status-operability-webapp" in body
    assert 'name="x-sovereign-shipped-in"' in body
    assert "D-22" in body
    assert 'name="x-sovereign-standing-rule"' in body
    assert "We do not minimize anything." in body


def test_webapp_has_zero_external_dependencies():
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    forbidden_hosts = [
        "https://cdn.", "http://cdn.", "https://cdnjs.",
        "https://unpkg.", "https://fonts.googleapis.",
        "https://fonts.gstatic.", "https://ajax.googleapis.",
        "https://code.jquery.", "https://stackpath.",
        "https://maxcdn.", "https://bootstrapcdn.",
        "https://use.fontawesome.", "//cdn.",
    ]
    for host in forbidden_hosts:
        assert host not in body, f"webapp must NOT reference external host {host!r}"
    assert re.search(r'<script[^>]+src="https?://', body) is None
    assert re.search(r'<link[^>]+href="https?://', body) is None


def test_webapp_fetches_only_same_origin_endpoints():
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    for m in re.finditer(r'fetch\(\s*(["\'])([^"\']+)\1', body):
        target = m.group(2)
        assert target.startswith("/"), f"fetch() target {target!r} not same-origin"
        assert "//" not in target


def test_webapp_advertises_read_only_endpoints():
    """D-22's OWN operability surface stays read-only — its lm-status endpoints
    are GET, and its Actions clipboard-copy MS003-signed CLI verbs (R10212).
    The only mutating request in the page is the inlined shared control-surface
    component's sanctioned exec POST to the dedicated control-exec-api
    (/api/control/execute) — R10274 — which is allowlisted + confirm/key-gated +
    DRY_RUN-default; it is NOT a D-22-specific mutation endpoint."""
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert "/api/lm-status/devices" in body
    # D-22's own surface never posts to a lm-status mutation verb.
    assert re.search(r'fetch\(\s*["\']/(set|apply|mutate)', body) is None, (
        "webapp leaks a mutation verb as fetch() target (R10212 violation)"
    )
    # Actions must be clipboard-copied signed CLI verbs, never HTTP writes.
    assert "navigator.clipboard.writeText" in body, (
        "operability Actions must clipboard-copy MS003-signed CLI verbs"
    )
    # The permitted mutating POSTs are: the shared component's sanctioned exec
    # endpoint (/api/control/execute, R10274) AND — per SDD-062, operator-sanctioned
    # "the full deal, no minimizing" — the D-22 chat endpoint (/api/lm-status/chat),
    # a NON-MUTATING inference read-compute to the loopback router. No OTHER
    # POST/PUT/DELETE fetch may leak. All actual state mutations stay 405.
    for m in re.finditer(r'fetch\(\s*["\']([^"\']+)["\']', body):
        assert m.group(1).startswith("/"), "non-same-origin fetch"
    _PERMITTED_POST = ("/api/control/execute", "/api/lm-status/chat")
    # every POST-target fetch in the page must be one of the permitted endpoints
    for m in re.finditer(r'fetch\(\s*["\']([^"\']+)["\'][^)]*method:\s*["\']POST["\']', body):
        assert m.group(1) in _PERMITTED_POST, (
            f"D-22 leaks an unsanctioned POST to {m.group(1)!r} — only "
            f"{_PERMITTED_POST} are permitted (R10212 / SDD-062)"
        )
    if re.search(r'method:\s*["\'](PUT|DELETE|PATCH)["\']', body):
        raise AssertionError("D-22 must not PUT/DELETE/PATCH (R10212)")


def test_api_daemon_serves_webapp_path():
    """Live-spawn the daemon and assert GET /webapp/ returns 200 text/html
    with the §1g standing rule embedded."""
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/webapp/", timeout=3
        ) as r:
            assert r.status == 200
            assert "text/html" in r.headers.get("Content-Type", "")
            body = r.read().decode("utf-8")
            assert "<!DOCTYPE html>" in body or "<!doctype html>" in body
            assert "d-22-lm-status-operability" in body
            assert "We do not minimize anything." in body
            assert r.headers.get("X-Sovereign-Module") == \
                "d-22-lm-status-operability-webapp"
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_api_daemon_webapp_aliases():
    """/webapp, /webapp/, /webapp/index.html all resolve to the SPA."""
    port = _free_port()
    proc = _spawn_api(port)
    try:
        for path in ("/webapp", "/webapp/", "/webapp/index.html"):
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}{path}", timeout=3
            ) as r:
                assert r.status == 200
                assert "text/html" in r.headers.get("Content-Type", "")
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_api_daemon_devices_endpoint_shape():
    """/api/lm-status/devices returns the per-device (CPU0/GPU0/GPU1) shape
    with 3 Model slots each — the exact contract the webapp renders."""
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/api/lm-status/devices", timeout=3
        ) as r:
            data = json.loads(r.read())
        slots = [d["slot"] for d in data.get("devices", [])]
        assert slots == ["CPU0", "GPU0", "GPU1"], f"unexpected device slots: {slots}"
        for d in data["devices"]:
            assert len(d.get("models", [])) == 3, (
                f"device {d['slot']} must expose Model 0/1/2 slots"
            )
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_api_daemon_is_read_only():
    """POST/PUT/DELETE must be fail-closed with 405 (R10212)."""
    port = _free_port()
    proc = _spawn_api(port)
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/lm-status/devices", method="POST", data=b"{}"
        )
        try:
            urllib.request.urlopen(req, timeout=3)
            raised = False
        except urllib.error.HTTPError as e:
            raised = e.code == 405
        assert raised, "POST must be rejected 405 (read-only cockpit)"
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_chat_endpoint_is_the_one_sanctioned_post():
    """SDD-062 — POST /api/lm-status/chat is the ONE sanctioned mutating-method
    endpoint (a non-mutating inference read-compute): it must NOT be 405. With no
    router backend reachable it still opens the SSE stream and emits an honest
    `error` event (SB-077) — never a fabricated completion. Every OTHER POST path
    stays 405."""
    port = _free_port()
    proc = _spawn_api(port)
    try:
        # the chat endpoint is NOT 405 (it is the sanctioned inference read-compute)
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/lm-status/chat", method="POST",
            data=json.dumps({"prompt": "hello"}).encode(),
            headers={"Content-Type": "application/json"},
        )
        code, ctype, body = None, None, ""
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                code, ctype = r.status, r.headers.get("Content-Type", "")
                body = r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            code = e.code
        assert code != 405, "the chat endpoint must not be 405 (SDD-062 sanctioned POST)"
        # 200 SSE stream (honest error event since no backend) OR 503 if engine absent
        assert code in (200, 503)
        if code == 200:
            assert "text/event-stream" in ctype
            assert "event: error" in body and "router unreachable" in body  # honest, no fabrication

        # a DIFFERENT POST path stays 405
        req2 = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/lm-status/devices", method="POST", data=b"{}")
        try:
            urllib.request.urlopen(req2, timeout=3)
            rejected = False
        except urllib.error.HTTPError as e:
            rejected = e.code == 405
        assert rejected, "non-chat POST must stay 405"
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_webapp_sends_multiturn_messages_client_side():
    """SDD-103 — the D-22 webapp keeps a client-side conversation buffer and POSTs the
    bounded `{messages}` history (the server holds no state); a "New chat" clears it."""
    html = WEBAPP_HTML.read_text(encoding="utf-8")
    assert "chatHistory" in html and "messages: chatHistory" in html
    assert "chat-new" in html and "function newChat" in html


def test_chat_endpoint_accepts_multiturn_messages():
    """SDD-103 — the chat endpoint accepts a {messages:[{role,content}]} multi-turn
    body (in addition to {prompt}); with no backend it still opens the SSE stream with
    an honest error (or 503). A malformed `messages` (not a list) is 400 — the server
    holds no conversation state (client sends the bounded history each turn, R10212)."""
    port = _free_port()
    proc = _spawn_api(port)
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/lm-status/chat", method="POST",
            data=json.dumps({"messages": [
                {"role": "user", "content": "hi"},
                {"role": "assistant", "content": "hello"},
                {"role": "user", "content": "again"}]}).encode(),
            headers={"Content-Type": "application/json"})
        code = None
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                code = r.status
        except urllib.error.HTTPError as e:
            code = e.code
        assert code in (200, 503), "the multi-turn chat body must be accepted (not 405/400)"

        # a malformed `messages` (not a list) → 400
        req2 = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/lm-status/chat", method="POST",
            data=json.dumps({"messages": "not-a-list"}).encode(),
            headers={"Content-Type": "application/json"})
        bad = None
        try:
            urllib.request.urlopen(req2, timeout=3)
        except urllib.error.HTTPError as e:
            bad = e.code
        assert bad == 400, "a malformed messages body must be 400"
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_api_daemon_version_advertises_webapp_surface():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/version", timeout=3
        ) as r:
            data = json.loads(r.read())
        assert "webapp" in data.get("surfaces", []), (
            f"/version must advertise 'webapp' surface; got {data}"
        )
        assert "D-22" in data.get("shipped_in", ""), (
            f"/version shipped_in must mention D-22; got {data}"
        )
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_surface_map_registers_module():
    """surface-map must track lm-status-operability with webapp shipped."""
    result = subprocess.run(
        ["python3", str(SURFACE_MAP), "coverage", "--module",
         "lm-status-operability", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, (
        f"surface-map coverage lm-status-operability failed: {result.stderr[:300]}"
    )
    data = json.loads(result.stdout)
    entries = data.get("coverage", [data])
    entry = entries[0] if entries else {}
    matrix = entry.get("matrix", [])
    webapp_row = next((r for r in matrix if r.get("surface") == "webapp"), None)
    assert webapp_row is not None
    assert webapp_row.get("state") == "shipped", (
        f"lm-status-operability webapp surface must be shipped; got {webapp_row}"
    )


def test_webapp_quotes_standing_rule_in_footer():
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert "<footer" in body and "</footer>" in body
    footer = body[body.index("<footer"): body.index("</footer>")]
    assert "We do not minimize anything." in footer
    assert "§1g" in footer


def test_nav_registry_includes_d22():
    nav = (REPO_ROOT / "webapp" / "_shared" / "nav-snippet.html").read_text()
    assert "d-22-lm-status-operability" in nav, (
        "D-22 must be registered in the nav-snippet DASHBOARDS array"
    )
