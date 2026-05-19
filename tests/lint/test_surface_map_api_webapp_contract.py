"""R533 (E5++) — surface-map API + webapp + service surface contract
lint.

Closes the surface-map api:FUTURE + webapp:FUTURE waivers AND
replaces the prior service:not-applicable waiver with a REAL systemd-
managed read-only daemon. Raises the surface-map surface count from
5 -> 8 shipped surfaces (core / cli / tui / api / service / dashboard
/ mcp / webapp). Third and final commit in the surface-map tier-3
surface-expansion arc (R531 TUI -> R532 MCP -> R533 API + webapp +
service). Lands surface-map as the TENTH §1g module at full 8-surface
structural ceiling — after edge-firewall (R506), network-edge
(R509), global-history (R512), trinity (R515), router (R518),
compliance (R521), anti-min (R524), doc-coverage (R527), and
ux-design-audit (R530).

Eating-our-own-dogfood: surface-map IS the §1g coverage instrument
itself; having it sit at less-than-ceiling while other modules pass
their own contracts would be hypocritical. R531-R533 fix that.

Per operator §1g verbatim (sacrosanct):

  "We do not minimize anything."

Per operator §1g 8-surface delivery contract (verbatim, R453 anchor):

  "everything is not just core, not just cli, not just TUI, not just
   API, not just tool and MCP but also Dashboards and Web Apps and
   Services"

Sovereignty boundaries enforced by this contract:
  - read-only at every HTTP method except GET/HEAD (operator §17)
  - surface-map has NO mutation verbs at any surface — the coverage
    matrix is a query; remediation lives in the audited modules
    themselves, NOT in this daemon
  - webapp is single-file, zero external deps, same-origin only
  - loopback-bind default (port 8101, sister to trinity 8095 +
    router 8096 + compliance 8097 + anti-min 8098 + doc-coverage
    8099 + ux-design-audit 8100)
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
API_PY = REPO_ROOT / "scripts" / "operator" / "surface-map-api.py"
WEBAPP_HTML = REPO_ROOT / "webapp" / "surface-map" / "index.html"
UNIT_FILE = (
    REPO_ROOT / "systemd" / "system"
    / "sovereign-surface-map-api.service"
)
SURFACE_MAP = REPO_ROOT / "scripts" / "operator" / "surface-map.py"
DASH_README = (
    REPO_ROOT / "docs" / "observability" / "dashboards" / "README.md"
)

# R453 8 operator-named §1g surface ids. The instrument under test
# IS the §1g coverage instrument itself — its own /surfaces endpoint
# must enumerate this exact set.                                       R453 R533
R453_SURFACES = (  # R453 R533
    "core", "cli", "tui", "api",         # R453 R533
    "mcp", "dashboard", "webapp", "service",  # R453 R533
)


# ---------------------------------------------------------------- static

def test_api_daemon_present_and_executable():
    assert API_PY.is_file(), f"missing API daemon: {API_PY}"
    assert os.access(API_PY, os.X_OK), (
        f"R533: {API_PY} must be executable"
    )


def test_webapp_html_present():
    assert WEBAPP_HTML.is_file(), f"missing webapp asset: {WEBAPP_HTML}"


def test_systemd_unit_present_and_hardened():
    assert UNIT_FILE.is_file(), f"missing systemd unit: {UNIT_FILE}"
    text = UNIT_FILE.read_text()
    # R171 defense-in-depth — same hardening keys as the R515/R518/
    # R521/R524/R527/R530 API units.
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
            f"R533 systemd unit missing R171 hardening key: {key!r}"
        )
    # Loopback-default exposure.
    assert "SURFACE_MAP_API_BIND=127.0.0.1" in text, (
        "R533 unit must default-bind to loopback"
    )
    assert "SURFACE_MAP_API_PORT=8101" in text, (
        "R533 unit must use port 8101 (sister to trinity-api 8095 + "
        "router-api 8096 + compliance-api 8097 + anti-min-api 8098 + "
        "doc-coverage-api 8099 + ux-design-audit-api 8100)"
    )


def test_webapp_html_shape_sovereign_clean():
    html = WEBAPP_HTML.read_text()
    assert html.lstrip().lower().startswith("<!doctype html>"), (
        "webapp must use HTML5 doctype"
    )
    assert 'name="x-sovereign-module"' in html
    assert 'content="surface-map-webapp"' in html
    assert 'name="x-sovereign-shipped-in"' in html
    assert "R533" in html
    # Standing rule meta — operator §1g sacrosanct (R453 anchor).
    assert (
        "Dashboards and Web Apps and Services" in html
    ), (
        "webapp must carry the R453 8-surface delivery-contract "
        "standing rule verbatim"
    )


def test_webapp_zero_external_deps():
    """Operator-§1g UX rule: no CDN fetches, no external fonts, no JS
    framework — sovereignty-clean single-file webapp. Same contract
    enforced for trinity/router/compliance/anti-min/doc-coverage/
    ux-design-audit webapps."""
    html = WEBAPP_HTML.read_text()
    bad_patterns = [
        r'src\s*=\s*["\']https?://',
        r'href\s*=\s*["\']https?://',
        r'src\s*=\s*["\']//',
        r'href\s*=\s*["\']//',
        r'@import\s+url\(\s*["\']?https?://',
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
    html = WEBAPP_HTML.read_text()
    for m in re.finditer(r'fetch\(\s*["\']([^"\']+)["\']', html):
        url = m.group(1)
        assert not url.startswith(("http://", "https://", "//")), (
            f"webapp fetch() must be same-origin relative; got {url!r}"
        )


def test_webapp_references_sovereignty_boundary():
    """The §17 boundary MUST be visible to the operator in the webapp
    UI — same shape as router/trinity/compliance/anti-min/doc-coverage/
    ux-design-audit disclaimers."""
    html = WEBAPP_HTML.read_text()
    low = html.lower()
    assert "§17" in html or "section 17" in low, (
        "webapp must surface the operator §17 boundary disclaimer"
    )
    assert "surface-map" in low, (
        "webapp disclaimer must name the surface-map mechanism"
    )
    assert ("sovereign-surface-map-api" in low
            or "surface-map-api.service" in low), (
        "webapp must name the backing systemd service"
    )


def test_webapp_lists_all_eight_surface_ids():
    """The R453 8-surface ladder MUST be visible in the webapp body —
    operator-§1g UX rule: full ladder per page. The instrument-under-
    test IS the surface ladder, so this is the load-bearing check."""
    html = WEBAPP_HTML.read_text().lower()
    for surface in R453_SURFACES:
        assert surface in html, (
            f"webapp must surface R453 §1g surface id {surface!r}"
        )


# ----------------------------------------------------- live daemon spin-up

class _DaemonHarness:
    def __init__(self):
        self.port = None
        self.proc = None

    def __enter__(self):
        # Allocate a free loopback port to avoid colliding with 8101.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            self.port = s.getsockname()[1]
        env = os.environ.copy()
        env["SURFACE_MAP_API_BIND"] = "127.0.0.1"
        env["SURFACE_MAP_API_PORT"] = str(self.port)
        env["SOVEREIGN_OS_METRICS_DIR"] = "/tmp/r533-metrics-test"
        self.proc = subprocess.Popen(
            ["python3", str(API_PY)],
            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
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
            f"surface-map-api daemon never became healthy on port "
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

    def fetch(self, path: str, method: str = "GET", timeout: int = 120):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}", method=method,
        )
        return urllib.request.urlopen(req, timeout=timeout)


def test_live_version_8_surfaces():
    """R533 closes the surface-map surface ladder — /version MUST
    list all 8 surfaces."""
    with _DaemonHarness() as d:
        with d.fetch("/version") as r:
            assert r.status == 200
            payload = json.loads(r.read())
    assert payload["module"] == "surface-map-api"
    assert "R533" in payload["shipped_in"]
    assert payload["spec_ref"] == "R453"
    surfaces = set(payload.get("surfaces", []))
    expected = set(R453_SURFACES)
    assert surfaces == expected, (
        f"R533: surface-map-api /version must report all 8 "
        f"surfaces; got {sorted(surfaces)}"
    )
    rule = payload.get("standing_rule", "")
    assert "Dashboards and Web Apps and Services" in rule, (
        f"R533 /version must carry the R453 standing rule verbatim; "
        f"got {rule!r}"
    )
    # Read-only inspection verbs — all the surface-map.py verbs
    # except `watch` (TUI-only, refresh-loop is an MCP/API anti-
    # pattern). R541 added `milestone` (R540 rollup over HTTP).
    assert set(payload.get("verbs", [])) >= {
        "surfaces", "modules", "coverage",
        "gaps", "waivers", "selfdef",
    }
    # R541: post-R541 the verb set MUST include milestone too.
    assert "milestone" in set(payload.get("verbs", [])), (
        "post-R541 /version verbs must include 'milestone'"
    )


def test_live_surfaces_payload_lists_eight():
    with _DaemonHarness() as d:
        with d.fetch("/surfaces") as r:
            assert r.status == 200
            payload = json.loads(r.read())
    assert payload.get("count") == 8
    surfaces = payload.get("surfaces") or []
    ids = {s["id"] if isinstance(s, dict) else s for s in surfaces}
    assert ids == set(R453_SURFACES), (
        f"/surfaces must enumerate all 8 R453 §1g surfaces; "
        f"got {sorted(ids)}"
    )


def test_live_modules_payload_shape():
    with _DaemonHarness() as d:
        with d.fetch("/modules") as r:
            assert r.status == 200
            payload = json.loads(r.read())
    assert isinstance(payload.get("modules"), list)
    assert payload.get("count") == len(payload["modules"])
    assert payload["count"] > 0, (
        "surface-map tracks at least one module"
    )
    # Each row carries the core coverage shape.
    for row in payload["modules"]:
        assert "id" in row
        assert "surface_count" in row
        assert "at_structural_ceiling" in row


def test_live_coverage_payload_shape():
    with _DaemonHarness() as d:
        with d.fetch("/coverage") as r:
            assert r.status == 200
            payload = json.loads(r.read())
    rows = payload.get("coverage") or []
    assert rows, "/coverage must return at least one module"
    for r in rows:
        assert "module" in r
        assert "surface_count" in r
        assert "matrix" in r
        # 8-surface matrix per row.
        cells = r["matrix"]
        seen = {c["surface"] for c in cells}
        assert seen == set(R453_SURFACES), (
            f"row {r['module']!r} matrix must cover all 8 surfaces; "
            f"got {sorted(seen)}"
        )


def test_live_coverage_module_filter():
    """The /coverage?module=<m> filter MUST narrow to that module."""
    with _DaemonHarness() as d:
        with d.fetch("/modules") as r:
            modules = json.loads(r.read())["modules"]
        sample = modules[0]["id"]
        with d.fetch(f"/coverage?module={sample}") as r:
            assert r.status == 200
            payload = json.loads(r.read())
    rows = payload.get("coverage") or []
    assert len(rows) == 1
    assert rows[0]["module"] == sample


def test_live_coverage_unknown_module_400():
    with _DaemonHarness() as d:
        try:
            d.fetch("/coverage?module=not-a-real-module")
            raise AssertionError("expected 400 for unknown module")
        except urllib.error.HTTPError as e:
            assert e.code == 400
            body = json.loads(e.read())
            assert "known" in body


def test_live_gaps_payload_shape():
    with _DaemonHarness() as d:
        with d.fetch("/gaps") as r:
            assert r.status == 200
            payload = json.loads(r.read())
    assert "threshold" in payload
    rows = payload.get("below_threshold") or []
    # Sorted by largest shortfall first.
    if len(rows) > 1:
        shortfalls = [r["shortfall"] for r in rows]
        assert shortfalls == sorted(shortfalls, reverse=True), (
            f"/gaps must be sorted by largest shortfall first; "
            f"got {shortfalls}"
        )


def test_live_gaps_excludes_ceiling_modules():
    """R478: structural-ceiling modules (8 surfaces, zero FUTURE
    waivers) MUST NOT appear in /gaps regardless of threshold —
    they are already at the ceiling."""
    with _DaemonHarness() as d:
        with d.fetch("/gaps?threshold=8") as r:
            assert r.status == 200
            payload = json.loads(r.read())
    # surface-map itself is now at the ceiling, must not show in gaps.
    gap_modules = {r["module"] for r in payload.get("below_threshold")}
    assert "surface-map" not in gap_modules, (
        "post-R533 surface-map is at structural ceiling — it must "
        "NOT appear in /gaps"
    )


def test_live_waivers_payload_shape():
    with _DaemonHarness() as d:
        with d.fetch("/waivers") as r:
            assert r.status == 200
            payload = json.loads(r.read())
    rows = payload.get("waivers") or []
    for r in rows:
        assert "module" in r
        assert "surface" in r
        assert "rationale" in r
        assert "waiver_class" in r


def test_live_waivers_module_filter():
    with _DaemonHarness() as d:
        with d.fetch("/modules") as r:
            modules = json.loads(r.read())["modules"]
        sample = modules[0]["id"]
        with d.fetch(f"/waivers?module={sample}") as r:
            assert r.status == 200
            payload = json.loads(r.read())
    for row in payload.get("waivers") or []:
        assert row["module"] == sample


def test_live_selfdef_endpoint_shape():
    with _DaemonHarness() as d:
        with d.fetch("/selfdef") as r:
            assert r.status == 200
            payload = json.loads(r.read())
    assert "valid" in payload
    assert "count_valid" in payload


def test_live_webapp_alias_serves_html():
    with _DaemonHarness() as d:
        with d.fetch("/webapp/") as r:
            assert r.status == 200
            body = r.read().decode("utf-8")
            ct = r.headers.get("Content-Type", "")
    assert "text/html" in ct
    assert "<!DOCTYPE html>" in body or "<!doctype html>" in body.lower()
    assert "surface-map-webapp" in body


def test_live_mutation_methods_rejected_with_405():
    """Operator §17 sovereignty: no mutation verbs at the API surface.
    Surface-map has NO mutation verbs at any surface period —
    POST/PUT/DELETE/PATCH MUST all return 405."""
    with _DaemonHarness() as d:
        for method in ("POST", "PUT", "DELETE", "PATCH"):
            try:
                d.fetch("/coverage", method=method)
                raise AssertionError(
                    f"{method} /coverage must 405 (got 2xx)"
                )
            except urllib.error.HTTPError as e:
                assert e.code == 405, (
                    f"{method} expected 405; got {e.code}"
                )
                body = e.read().decode("utf-8")
                low = body.lower()
                assert "read-only" in low
                # Boundary explanation must mention either the remediation-
                # lives-elsewhere rule or the no-mutation framing.
                assert ("remediation" in low
                        or "no mutation" in low
                        or "query" in low)


def test_live_unknown_path_404():
    with _DaemonHarness() as d:
        try:
            d.fetch("/no-such-path")
        except urllib.error.HTTPError as e:
            assert e.code == 404


# ----------------------------------------------------- importlib reuse

def test_api_importlib_loads_surface_map_core():
    """The daemon MUST reuse surface-map.py's SURFACES + KNOWN_MODULES
    + coverage_for — no drift between CLI / TUI / MCP / API surfaces."""
    spec = importlib.util.spec_from_file_location("_r533", API_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod._CORE_PATH.name == "surface-map.py", (
        "R533 daemon must importlib-load surface-map.py"
    )
    assert hasattr(mod._core, "SURFACES")
    assert hasattr(mod._core, "KNOWN_MODULES")
    assert hasattr(mod._core, "MODULE_COVERAGE")
    assert hasattr(mod._core, "coverage_for")
    assert len(mod._core.SURFACES) == 8


# ----------------------------------------------------- surface-map post-

def test_surface_map_surface_map_at_structural_ceiling():
    """R533 closes the surface-map surface ladder — the §1g coverage
    instrument MUST report its OWN entry at at_structural_ceiling=True
    with 0 FUTURE waivers. Eating-our-own-dogfood: through R532 the
    surface-map entry carried api:FUTURE + webapp:FUTURE +
    service:not-applicable waivers on its OWN row. R533 fixes that
    hypocrisy."""
    result = subprocess.run(
        ["python3", str(SURFACE_MAP), "coverage", "--module",
         "surface-map", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr[:300]
    data = json.loads(result.stdout)
    entries = data.get("coverage", [data])
    entry = entries[0] if entries else {}
    assert entry.get("surface_count", 0) == 8, (
        f"surface-map must be at 8 surfaces post-R533; got {entry}"
    )
    assert entry.get("at_structural_ceiling") is True, (
        f"surface-map must be at_structural_ceiling=True post-R533; "
        f"got {entry}"
    )
    assert entry.get("future_waiver_count", 0) == 0, (
        f"surface-map must have 0 FUTURE waivers post-R533; "
        f"got {entry}"
    )
    matrix = entry.get("matrix", [])
    for surface in ("api", "service", "webapp"):
        row = next(
            (r for r in matrix if r.get("surface") == surface), None
        )
        assert row is not None, (
            f"surface-map matrix missing {surface!r} row"
        )
        assert row.get("state") == "shipped", (
            f"surface-map {surface} must be shipped post-R533; "
            f"got {row}"
        )


def test_dashboards_readme_documents_r533_metric():
    """The metric registry MUST list the R533 metric — operator-§1g
    visibility rule for the observability ladder."""
    text = DASH_README.read_text()
    assert (
        "sovereign_os_operator_surface_map_api_request_total" in text
    )
    assert "R533" in text
