"""Code Console webapp surface contract lint (SDD-112).

Pins the Code Console panel — a claude.ai/code-style interface for the sovereign
LOCAL LM — to the same sovereignty-clean webapp doctrine every other panel obeys:
a single-file monochrome SPA served by its API daemon under /webapp/ from the SAME
host:port binding as the JSON endpoints, zero external dependencies, same-origin
fetches only, and READ-ONLY (R10212) — the ONLY sanctioned POST is the loopback
chat (a NON-mutating inference read-compute); every real action is an MS003-signed
CLI verb the console copies to the clipboard.

The panel composes two SHIPPED cores (no new data model): the M057 session-registry
(scripts/lifecycle/session-registry.py) for the LEFT rail and the SDD-062/103 prompt
engine (scripts/inference/prompt.py) for the composer. The center persisted-thread,
the right Plan pane, and the repo chips have NO producer on the box → they render as
explicit honest-deferred cards (SB-077), never fabricated.

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
WEBAPP_HTML = REPO_ROOT / "webapp" / "code-console" / "index.html"
API_DAEMON = REPO_ROOT / "scripts" / "operator" / "code-console-api.py"
SURFACE_MAP = REPO_ROOT / "scripts" / "operator" / "surface-map.py"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _spawn_api(port: int):
    env = {
        "CODE_CONSOLE_API_BIND": "127.0.0.1",
        "CODE_CONSOLE_API_PORT": str(port),
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
    raise RuntimeError("code-console-api failed to start within 6s")


def test_webapp_html_present():
    assert WEBAPP_HTML.is_file(), f"code-console webapp asset missing: {WEBAPP_HTML}"


def test_webapp_html_is_html5():
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert body.lstrip().lower().startswith("<!doctype html>")
    assert "<html lang=" in body
    assert 'name="viewport"' in body


def test_webapp_carries_sovereign_meta_tags():
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert 'name="x-sovereign-module"' in body
    assert "code-console-webapp" in body
    assert 'name="x-sovereign-shipped-in"' in body
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


def test_webapp_is_read_only_one_sanctioned_post():
    """The console is read-only (R10212). The ONLY permitted mutating POSTs are the
    shared control-surface exec (/api/control/execute, R10274) and the loopback chat
    (/api/code-console/chat, a NON-mutating inference read-compute). No other
    POST/PUT/DELETE may leak; real actions are clipboard-copied signed CLI verbs."""
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert "/api/code-console/sessions" in body
    assert "/api/code-console/chat" in body
    assert re.search(r'fetch\(\s*["\']/(set|apply|mutate)', body) is None, (
        "webapp leaks a mutation verb as fetch() target (R10212 violation)"
    )
    _PERMITTED_POST = ("/api/control/execute", "/api/code-console/chat")
    for m in re.finditer(r'fetch\(\s*["\']([^"\']+)["\'][^)]*method:\s*["\']POST["\']', body):
        assert m.group(1) in _PERMITTED_POST, (
            f"code-console leaks an unsanctioned POST to {m.group(1)!r} — only "
            f"{_PERMITTED_POST} are permitted (R10212 / SDD-112)"
        )
    if re.search(r'method:\s*["\'](PUT|DELETE|PATCH)["\']', body):
        raise AssertionError("code-console must not PUT/DELETE/PATCH (R10212)")


def test_webapp_inlines_control_surface():
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert 'id="control-surface"' in body
    assert "SovereignControlSurface" in body


def test_webapp_quotes_standing_rule_in_footer():
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert "<footer" in body and "</footer>" in body
    footer = body[body.index("<footer"): body.index("</footer>")]
    assert "We do not minimize anything." in footer


# ── SDD-112: the claude.ai/code three-pane layout + honest-deferred posture ──

def test_three_pane_scaffold_present():
    """The design's three panes (rail · thread · plan) + top tabs + bottom composer
    are all present in the markup."""
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    for anchor in ('id="cc-tabs"', 'id="cc-rail"', 'id="cc-thread"', 'id="cc-plan"',
                   'class="cc-composer"', 'id="cc-input"', 'id="cc-send"'):
        assert anchor in body, f"the three-pane console must carry {anchor}"


def test_scaffold_is_always_visible_offline():
    """The three-pane scaffold renders even with the daemon offline — a
    FIXED_SESSIONS fallback + an initial paint of rail/thread/plan, never a blank
    console (the SDD-111 'seeing all sections' lesson, built-in; SB-077)."""
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert "FIXED_SESSIONS" in body, "a fixed honest-empty sessions fallback must exist"
    assert re.search(r"renderRail\(\s*FIXED_SESSIONS\s*\)", body), (
        "an initial paint of the rail must run before the live fetch"
    )
    for fn in ("renderThread()", "renderPlanPane()"):
        assert fn in body, f"the initial paint must call {fn}"
    # the fetch catch must fall back to the fixed model, never leave the rail blank
    assert re.search(r"catch\s*\([^)]*\)\s*\{[^}]*FIXED_SESSIONS", body, re.DOTALL), (
        "the fetch catch must fall back to FIXED_SESSIONS (never a blank rail)"
    )


def test_honest_deferred_panes_never_fabricated():
    """The center persisted-thread, the right Plan pane, and the repo chips have no
    producer on the box → they render explicit honest-deferred cards (SB-077),
    never fabricated messages / plans / repos."""
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert "cc-defer" in body, "honest-deferred cards must be present"
    assert "honest-deferred" in body or "honest-deferred (SB-077)" in body
    # the rail is honestly relabelled as OS task-sessions, not chat threads
    assert "task-session" in body.lower()
    # repo chips are an explicit deferred chip, never invented repos
    assert re.search(r'cc-chip deferred', body), "repo chips must render as a deferred chip"


def test_plan_pane_is_live_for_plans_and_reasoning():
    """The right Plan pane is no longer a static placeholder: it mirrors the active
    Plan-Mode plan from the conversation and renders a clicked deliberation's CoAT
    reasoning trace. Artifacts stay honest-deferred (SB-077) — the real producers
    (Plan Mode + the CoAT engine + the jobs runtime) now feed it."""
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    # the live dispatcher + its producers
    for fn in ("function renderPlanPane", "function activePlan", "function renderTraceHTML", "function renderPlanHTML"):
        assert fn in body, f"the live Plan pane is missing {fn}"
    # a deliberation task with a trace is clickable → renders in the Plan pane
    assert "data-trace" in body and "focusTask" in body, "a deliberation task must open its trace in the Plan pane"
    # the plan pane reflects its mode (plan / reasoning / artifact) in the header
    assert 'id="cc-plan-head"' in body, "the Plan pane header must reflect what it shows"
    # a finished deliberation can be brought into the conversation
    assert "bringTrace" in body, "a trace must be bring-able into the conversation"
    # the AUQ parser is lenient (a plan card with raw newlines must still parse),
    # and no stray control bytes leaked into the file
    assert "function parseAUQ" in body, "the AUQ parser must tolerate raw control chars"
    raw = WEBAPP_HTML.read_bytes()
    stray = [b for b in raw if b < 0x20 and b not in (9, 10, 13)]
    assert not stray, f"no stray control bytes allowed in the panel ({len(stray)} found)"

    # the jobs runtime keeps the FULL trace on a deliberation job (what the pane reads)
    japi = (REPO_ROOT / "scripts" / "operator" / "jobs-api.py").read_text(encoding="utf-8")
    assert '"trace"' in japi and "best_path" in japi, "deliberation jobs must persist the CoAT trace"


def test_composer_targets_m075_devices():
    """The composer's model selector maps to the M075 SRP device targets."""
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert 'id="cc-target"' in body
    for dev in ("CPU0", "GPU0", "GPU1"):
        assert dev in body, f"the device target must offer {dev}"


def test_api_daemon_serves_webapp_path():
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
            assert "Code Console" in body
            assert "We do not minimize anything." in body
            assert r.headers.get("X-Sovereign-Module") == "code-console-webapp"
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_api_daemon_sessions_endpoint_shape():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/api/code-console/sessions", timeout=3
        ) as r:
            data = json.loads(r.read())
        assert "sessions" in data and isinstance(data["sessions"], list)
        assert "producer" in data  # honest provenance (m057 / absent / offline)
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_api_daemon_is_read_only_except_chat():
    """A POST to a NON-chat endpoint must be 405; the chat endpoint must NOT 405
    (200 on a real completion, or 503 when the loopback router is down — never
    fabricated, R10212 / SDD-112)."""
    port = _free_port()
    proc = _spawn_api(port)
    try:
        # non-chat POST → 405
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/code-console/sessions", method="POST", data=b"{}")
        try:
            urllib.request.urlopen(req, timeout=3)
            raised = False
        except urllib.error.HTTPError as e:
            raised = e.code == 405
        assert raised, "POST to a non-chat endpoint must be rejected 405 (read-only)"
        # chat POST → not 405
        creq = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/code-console/chat", method="POST",
            data=b'{"messages":[{"role":"user","content":"hi"}]}',
            headers={"Content-Type": "application/json"})
        code = None
        try:
            with urllib.request.urlopen(creq, timeout=6) as cr:
                code = cr.status
        except urllib.error.HTTPError as e:
            code = e.code
        assert code != 405, "the sanctioned chat POST must NOT be 405"
        assert code in (200, 503), f"chat must be 200 or an honest 503, got {code}"
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
        assert "webapp" in data.get("surfaces", [])
        assert data.get("module") == "code-console"
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_surface_map_registers_module():
    result = subprocess.run(
        ["python3", str(SURFACE_MAP), "coverage", "--module", "code-console", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, (
        f"surface-map coverage code-console failed: {result.stderr[:300]}"
    )
    data = json.loads(result.stdout)
    entries = data.get("coverage", [data])
    entry = entries[0] if entries else {}
    matrix = entry.get("matrix", [])
    webapp_row = next((r for r in matrix if r.get("surface") == "webapp"), None)
    assert webapp_row is not None and webapp_row.get("state") == "shipped"


def test_catalog_registers_code_console():
    catalog = (REPO_ROOT / "config" / "dashboard-catalog.yaml").read_text()
    assert "slug: code-console" in catalog
    assert "/code-console/" in catalog


def test_thread_layout_survives_assist_pane():
    """SDD-117 — the 3-pane grid must not crush the conversation into a vertical
    sliver: the center column uses minmax(0,1fr) (so it can shrink below its
    longest word), messages wrap with overflow-wrap (not mid-word word-break),
    and the assist-pane-open case reflows (body.so-assist-open .cc-grid)."""
    import re
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert "minmax(0,1fr)" in body, "the center column must be minmax(0,1fr) so it can shrink"
    assert re.search(r"\.cc-msg\s*\{[^}]*overflow-wrap:\s*break-word", body), (
        "messages must use overflow-wrap:break-word (not mid-word word-break)"
    )
    assert re.search(r"\.cc-msg\s*\{(?![^}]*word-break:\s*break-word)[^}]*\}", body), (
        "the mid-word word-break:break-word must be removed from .cc-msg"
    )
    assert "body.so-assist-open .cc-grid" in body, (
        "the layout must reflow when the assistant pane is open"
    )
