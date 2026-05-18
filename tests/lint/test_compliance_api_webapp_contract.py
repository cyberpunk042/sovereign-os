"""R521 (E5++) — Compliance dashboard API + webapp + service surface
contract lint.

Closes the compliance api:FUTURE + webapp:FUTURE waivers AND replaces
the prior service:not-applicable waiver with a REAL systemd-managed
read-only daemon. Raises the compliance surface count from 5 → 8
shipped surfaces (core / cli / tui / api / service / dashboard / mcp
/ webapp). Third and final commit in the compliance tier-3 surface-
expansion arc (R519 TUI → R520 MCP → R521 API + webapp + service).
Lands compliance as the SIXTH §1g module at full 8-surface structural
ceiling — after edge-firewall (R506), network-edge (R509), global-
history (R512), trinity (R515), and router (R518).

Per operator §1g verbatim (sacrosanct):

  "We do not minimize anything."

Per operator §1g 8-surface delivery contract (verbatim):

  "everything is not just core, not just cli, not just TUI, not just
   API, not just tool and MCP but also Dashboards and Web Apps and
   Services"

Sovereignty boundaries enforced by this contract:
  - read-only at every HTTP method except GET/HEAD (operator §17)
  - daemon NEVER writes to the snapshot journal — only the triple-
    gated `compliance snapshot` CLI verb may
  - webapp is single-file, zero external deps, same-origin only
  - loopback-bind default (port 8097, sister to trinity 8095 +
    router 8096)
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
API_PY = REPO_ROOT / "scripts" / "operator" / "compliance-api.py"
WEBAPP_HTML = REPO_ROOT / "webapp" / "compliance" / "index.html"
UNIT_FILE = (
    REPO_ROOT / "systemd" / "system" / "sovereign-compliance-api.service"
)
SURFACE_MAP = REPO_ROOT / "scripts" / "operator" / "surface-map.py"
DASH_README = REPO_ROOT / "docs" / "observability" / "dashboards" / "README.md"


# ---------------------------------------------------------------- static

def test_api_daemon_present_and_executable():
    assert API_PY.is_file(), f"missing API daemon: {API_PY}"
    assert os.access(API_PY, os.X_OK), (
        f"R521: {API_PY} must be executable"
    )


def test_webapp_html_present():
    assert WEBAPP_HTML.is_file(), f"missing webapp asset: {WEBAPP_HTML}"


def test_systemd_unit_present_and_hardened():
    assert UNIT_FILE.is_file(), f"missing systemd unit: {UNIT_FILE}"
    text = UNIT_FILE.read_text()
    # R171 defense-in-depth — same hardening keys as router-api +
    # trinity-api units.
    for key in (
        "ProtectSystem=strict",
        "NoNewPrivileges=true",
        "PrivateTmp=true",
        "ProtectHome=true",
        "ProtectKernelTunables=true",
        "ProtectKernelModules=true",
        "ProtectControlGroups=true",
        "RestrictNamespaces=true",
        "RestrictRealtime=true",
        "LockPersonality=true",
        "SystemCallArchitectures=native",
        "RestrictAddressFamilies=",
        "SystemCallFilter=",
    ):
        assert key in text, (
            f"R521 systemd unit missing R171 hardening key: {key!r}"
        )
    # Loopback-default exposure.
    assert "COMPLIANCE_API_BIND=127.0.0.1" in text, (
        "R521 unit must default-bind to loopback"
    )
    assert "COMPLIANCE_API_PORT=8097" in text, (
        "R521 unit must use port 8097 (sister to trinity-api 8095 + "
        "router-api 8096)"
    )


def test_webapp_html_shape_sovereign_clean():
    html = WEBAPP_HTML.read_text()
    # HTML5 doctype + lang
    assert html.lstrip().lower().startswith("<!doctype html>"), (
        "webapp must use HTML5 doctype"
    )
    # Sovereign meta tags identify the surface.
    assert 'name="x-sovereign-module"' in html
    assert 'content="compliance-webapp"' in html
    assert 'name="x-sovereign-shipped-in"' in html
    assert "R521" in html
    # Standing rule meta — operator §1g sacrosanct.
    assert "We do not minimize anything." in html


def test_webapp_zero_external_deps():
    """Operator-§1g UX rule: no CDN fetches, no external fonts, no JS
    framework — sovereignty-clean single-file webapp. Same contract
    enforced for trinity (R515) + router (R518) webapps."""
    html = WEBAPP_HTML.read_text()
    # No http://, https://, or //cdn URLs in src/href attributes.
    bad_patterns = [
        r'src\s*=\s*["\']https?://',
        r'href\s*=\s*["\']https?://',
        r'src\s*=\s*["\']//',
        r'href\s*=\s*["\']//',
        r'@import\s+url\(\s*["\']?https?://',
        # No common JS-framework markers (operator-§1g sovereignty rule).
        r'\breact(\.|-)',
        r'\bvue(\.|-)',
        r'\bangular(\.|-)',
        r'<script[^>]*\bsrc\s*=\s*["\'][^"\']*\.js["\']',
    ]
    for pat in bad_patterns:
        m = re.search(pat, html, re.IGNORECASE)
        assert not m, (
            f"webapp violates operator-§1g zero-external-deps rule: "
            f"matched {pat!r} at {m.start() if m else '?'}"
        )


def test_webapp_same_origin_fetch_only():
    """Operator-§1g UX rule: webapp fetch() calls MUST be same-origin
    relative URLs (no http(s)://… origins, no //host targets)."""
    html = WEBAPP_HTML.read_text()
    # Extract all fetch("...") calls and inspect the URL.
    for m in re.finditer(r'fetch\(\s*["\']([^"\']+)["\']', html):
        url = m.group(1)
        assert not url.startswith(("http://", "https://", "//")), (
            f"webapp fetch() must be same-origin relative; got {url!r}"
        )


def test_webapp_references_sovereignty_boundary():
    """The §17 boundary MUST be visible to the operator in the
    webapp UI — same shape as router/trinity disclaimers."""
    html = WEBAPP_HTML.read_text()
    low = html.lower()
    assert "§17" in html or "section 17" in low, (
        "webapp must surface the operator §17 boundary disclaimer"
    )
    # The triple-gated CLI snapshot verb is the ONLY mutation —
    # webapp must say so.
    assert "snapshot" in low and "cli" in low, (
        "webapp disclaimer must name the snapshot CLI-only mutation"
    )
    # Service name must be visible so operator knows what to manage.
    assert "sovereign-compliance-api" in low, (
        "webapp must name the backing systemd service"
    )


def test_webapp_lists_four_instruments():
    """The R458 4-instrument compliance ladder MUST be visible in
    the webapp body — operator-§1g UX rule: full ladder per page."""
    html = WEBAPP_HTML.read_text().lower()
    assert "surface-map" in html
    assert "doc-coverage" in html
    assert "anti-min" in html or "anti-minimization" in html
    assert "ux-design" in html


# ----------------------------------------------------- live daemon spin-up

class _DaemonHarness:
    def __init__(self):
        self.port = None
        self.proc = None

    def __enter__(self):
        # Allocate a free loopback port to avoid colliding with 8097.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            self.port = s.getsockname()[1]
        env = os.environ.copy()
        env["COMPLIANCE_API_BIND"] = "127.0.0.1"
        env["COMPLIANCE_API_PORT"] = str(self.port)
        # Sandbox-friendly: redirect textfile-collector emits.
        env["SOVEREIGN_OS_METRICS_DIR"] = "/tmp/r521-metrics-test"
        self.proc = subprocess.Popen(
            ["python3", str(API_PY)],
            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        # Poll until /healthz returns 200 (or 6s elapse).
        deadline = time.time() + 6.0
        last_err = None
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{self.port}/healthz", timeout=1,
                ) as r:
                    if r.status == 200:
                        return self
            except Exception as e:  # noqa: BLE001
                last_err = e
            time.sleep(0.15)
        self._teardown()
        raise AssertionError(
            f"compliance-api daemon never became healthy on port "
            f"{self.port}: {last_err!r}"
        )

    def __exit__(self, *a):
        self._teardown()

    def _teardown(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.proc.kill()

    def fetch(self, path: str, method: str = "GET", timeout: int = 60):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}", method=method,
        )
        return urllib.request.urlopen(req, timeout=timeout)


def test_live_version_8_surfaces():
    """R521 closes the compliance surface ladder — /version MUST list
    all 8 surfaces."""
    with _DaemonHarness() as d:
        with d.fetch("/version") as r:
            assert r.status == 200
            payload = json.loads(r.read())
    assert payload["module"] == "compliance-api"
    assert "R521" in payload["shipped_in"]
    assert payload["spec_ref"] == "R458"
    surfaces = set(payload.get("surfaces", []))
    expected = {"core", "cli", "tui", "api",
                "service", "dashboard", "mcp", "webapp"}
    assert surfaces == expected, (
        f"R521: compliance-api /version must report all 8 surfaces; "
        f"got {sorted(surfaces)}"
    )
    # Standing rule must be present.
    assert payload.get("standing_rule") == "We do not minimize anything."
    # Verbs reported by the API surface (3 read-only inspection verbs).
    assert set(payload.get("verbs", [])) == {"status", "worst", "history"}


def test_live_status_payload_has_four_instruments():
    """The /status endpoint MUST return the canonical 4-instrument
    rollup the CLI surface produces — operator-§1g full ladder."""
    with _DaemonHarness() as d:
        with d.fetch("/status", timeout=120) as r:
            assert r.status == 200
            payload = json.loads(r.read())
    for key in (
        "surface_map", "doc_coverage",
        "anti_minimization_audit", "ux_design_audit",
    ):
        assert key in payload, (
            f"/status missing instrument key {key!r}; got "
            f"{sorted(payload.keys())}"
        )
    # The 5 selfdef cross-repo axes MUST also be reported.
    for key in (
        "selfdef_discovery", "selfdef_surfaces",
        "selfdef_ux", "selfdef_audit", "selfdef_doc",
    ):
        assert key in payload, (
            f"/status missing selfdef axis {key!r}; got "
            f"{sorted(payload.keys())}"
        )


def test_live_worst_payload_shape():
    with _DaemonHarness() as d:
        with d.fetch("/worst?limit=3", timeout=120) as r:
            assert r.status == 200
            payload = json.loads(r.read())
    assert isinstance(payload.get("worst"), list)
    assert payload.get("limit") == 3
    assert payload["count"] == len(payload["worst"])
    # Capped at the limit.
    assert len(payload["worst"]) <= 3


def test_live_worst_limit_ceiling():
    """limit parameter MUST be clamped to ceiling=50 (operator
    sanity rail)."""
    with _DaemonHarness() as d:
        with d.fetch("/worst?limit=10000", timeout=120) as r:
            payload = json.loads(r.read())
    assert payload.get("limit") == 50


def test_live_history_payload_shape():
    with _DaemonHarness() as d:
        with d.fetch("/history?limit=5") as r:
            assert r.status == 200
            payload = json.loads(r.read())
    assert isinstance(payload.get("history"), list)
    assert payload.get("limit") == 5
    assert "path" in payload
    assert "total_journaled" in payload


def test_live_webapp_alias_serves_html():
    """GET /webapp/ MUST serve the single-file SPA (alias to
    /webapp/index.html). Same shape as router/trinity APIs."""
    with _DaemonHarness() as d:
        with d.fetch("/webapp/") as r:
            assert r.status == 200
            body = r.read().decode("utf-8")
            ct = r.headers.get("Content-Type", "")
    assert "text/html" in ct
    assert "<!DOCTYPE html>" in body or "<!doctype html>" in body.lower()
    assert "compliance-webapp" in body


def test_live_mutation_methods_rejected_with_405():
    """Operator §17 sovereignty: no mutation verbs at the API
    surface. POST/PUT/DELETE/PATCH MUST all return 405."""
    with _DaemonHarness() as d:
        for method in ("POST", "PUT", "DELETE", "PATCH"):
            try:
                d.fetch("/status", method=method)
                raise AssertionError(
                    f"{method} /status must 405 (got 2xx)"
                )
            except urllib.error.HTTPError as e:
                assert e.code == 405, (
                    f"{method} expected 405; got {e.code}"
                )
                body = e.read().decode("utf-8")
                low = body.lower()
                assert "read-only" in low
                # Boundary explanation must name the snapshot CLI verb.
                assert "snapshot" in low
                assert "cli" in low


def test_live_unknown_path_404():
    with _DaemonHarness() as d:
        try:
            d.fetch("/no-such-path")
        except urllib.error.HTTPError as e:
            assert e.code == 404


# ----------------------------------------------------- importlib reuse

def test_api_importlib_loads_compliance_core():
    """The daemon MUST reuse compliance.py's collect_status +
    compute_worst — no drift between CLI / TUI / MCP / API surfaces."""
    spec = importlib.util.spec_from_file_location("_r521", API_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod._COMPLIANCE_PATH.name == "compliance.py", (
        "R521 daemon must importlib-load compliance.py"
    )
    assert hasattr(mod._core, "collect_status")
    assert hasattr(mod._core, "compute_worst")


# ----------------------------------------------------- surface-map post-

def test_compliance_surface_map_at_structural_ceiling():
    """R521 closes the compliance surface ladder — surface-map MUST
    report at_structural_ceiling=True with 0 FUTURE waivers."""
    result = subprocess.run(
        ["python3", str(SURFACE_MAP), "coverage", "--module",
         "compliance", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr[:300]
    data = json.loads(result.stdout)
    entries = data.get("coverage", [data])
    entry = entries[0] if entries else {}
    assert entry.get("surface_count", 0) == 8, (
        f"compliance must be at 8 surfaces post-R521; got {entry}"
    )
    assert entry.get("at_structural_ceiling") is True, (
        f"compliance must be at_structural_ceiling=True post-R521; "
        f"got {entry}"
    )
    assert entry.get("future_waiver_count", 0) == 0, (
        f"compliance must have 0 FUTURE waivers post-R521; got {entry}"
    )
    matrix = entry.get("matrix", [])
    for surface in ("api", "service", "webapp"):
        row = next(
            (r for r in matrix if r.get("surface") == surface), None
        )
        assert row is not None, (
            f"compliance matrix missing {surface!r} row"
        )
        assert row.get("state") == "shipped", (
            f"compliance {surface} must be shipped post-R521; got "
            f"{row}"
        )


def test_dashboards_readme_documents_r521_metric():
    """The metric registry MUST list the R521 metric — operator-§1g
    visibility rule for the observability ladder."""
    text = DASH_README.read_text()
    assert "sovereign_os_operator_compliance_api_request_total" in text
    assert "R521" in text
