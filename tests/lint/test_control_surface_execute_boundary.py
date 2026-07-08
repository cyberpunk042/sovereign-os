"""Drift-guard: the shared control-surface's R10212 boundary must mirror the
server primitive, and its R10274 exec endpoint must match the write daemon.

The client component (webapp/_shared/control-surface.js) hard-codes a
`PROXY_ONLY` set to decide which controls render NO execute affordance
(selfdef / perimeter — signed-proxy only). The AUTHORITATIVE boundary lives in
scripts/operator/_action_exec.py `SELFDEF_OWNED`, enforced by the exec daemon
(409 on a proxy-only control). If these two ever diverge, the web could offer
an Execute button the server will reject — or worse, hide one it would accept.
This lint pins strict equality, and pins the exec endpoint the client POSTs to
against the endpoint the daemon serves.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
Per operator directive (sacrosanct): "we will fix everything that is a manual
command so that the manual command is only the alternative but we will
otherwise do the features functional from the panels / dashboard."
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
JS = REPO / "webapp" / "_shared" / "control-surface.js"
ACTION_EXEC = REPO / "scripts" / "operator" / "_action_exec.py"
DAEMON = REPO / "scripts" / "operator" / "control-exec-api.py"


def _load_action_exec():
    spec = importlib.util.spec_from_file_location("_action_exec_boundary", ACTION_EXEC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _js_proxy_only() -> set[str]:
    body = JS.read_text(encoding="utf-8")
    m = re.search(r'var\s+PROXY_ONLY\s*=\s*\[([^\]]*)\]', body)
    assert m, "control-surface.js must declare `var PROXY_ONLY = [...]`"
    return set(re.findall(r'["\']([a-z0-9_-]+)["\']', m.group(1)))


def test_client_boundary_mirrors_server_selfdef_owned():
    server = set(_load_action_exec().SELFDEF_OWNED)
    client = _js_proxy_only()
    assert client == server, (
        f"control-surface.js PROXY_ONLY {sorted(client)} drifted from "
        f"_action_exec.SELFDEF_OWNED {sorted(server)} — the web boundary and the "
        f"exec daemon boundary MUST match (else Execute offered where server rejects)."
    )


def test_client_exec_endpoint_matches_daemon_route():
    js = JS.read_text(encoding="utf-8")
    assert "/api/control/execute" in js, "client must POST to /api/control/execute"
    daemon = DAEMON.read_text(encoding="utf-8")
    assert "/api/control/execute" in daemon, (
        "control-exec-api.py must serve the /api/control/execute route the client posts to"
    )


def test_client_posts_only_to_the_exec_endpoint():
    """The only mutating fetch in the component targets the sanctioned exec URL —
    every literal fetch() target is same-origin, and the POST goes to the
    EXECUTE_URL constant (default /api/control/execute)."""
    js = JS.read_text(encoding="utf-8")
    m = re.search(r'var\s+EXECUTE_URL\s*=\s*["\']([^"\']+)["\']', js)
    assert m and m.group(1) == "/api/control/execute", (
        "EXECUTE_URL must default to the same-origin /api/control/execute"
    )
    for lit in re.findall(r'fetch\(\s*["\']([^"\']+)["\']', js):
        assert lit.startswith("/") and "//" not in lit, (
            f"control-surface.js literal fetch {lit!r} is not same-origin"
        )
