"""R527 (E5++) — doc-coverage API + webapp + service surface contract
lint.

Closes the doc-coverage api:FUTURE + webapp:FUTURE waivers AND replaces
the prior service:not-applicable waiver with a REAL systemd-managed
read-only daemon. Raises the doc-coverage surface count from 5 -> 8
shipped surfaces (core / cli / tui / api / service / dashboard / mcp /
webapp). Third and final commit in the doc-coverage tier-3 surface-
expansion arc (R525 TUI -> R526 MCP -> R527 API + webapp + service).
Lands doc-coverage as the EIGHTH §1g module at full 8-surface
structural ceiling — after edge-firewall (R506), network-edge (R509),
global-history (R512), trinity (R515), router (R518), compliance
(R521), and anti-min (R524).

Per operator §1g verbatim (sacrosanct):

  "We do not minimize anything."

Per operator §1g 8-surface delivery contract (verbatim):

  "everything is not just core, not just cli, not just TUI, not just
   API, not just tool and MCP but also Dashboards and Web Apps and
   Services"

Sovereignty boundaries enforced by this contract:
  - read-only at every HTTP method except GET/HEAD (operator §17)
  - doc-coverage has NO mutation verbs at any surface — docs ARE the
    source of truth, this daemon scans the tree, it does not author
  - webapp is single-file, zero external deps, same-origin only
  - loopback-bind default (port 8099, sister to trinity 8095 +
    router 8096 + compliance 8097 + anti-min 8098)
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
API_PY = REPO_ROOT / "scripts" / "operator" / "doc-coverage-api.py"
WEBAPP_HTML = (
    REPO_ROOT / "webapp" / "doc-coverage" / "index.html"
)
UNIT_FILE = (
    REPO_ROOT / "systemd" / "system" / "sovereign-doc-coverage-api.service"
)
SURFACE_MAP = REPO_ROOT / "scripts" / "operator" / "surface-map.py"
DASH_README = (
    REPO_ROOT / "docs" / "observability" / "dashboards" / "README.md"
)

# R454 6 operator-named doc-surface ids. Inline anchors carried for
# consistency with the R524 fixture shape (operator-§1g self-audit
# cleanliness rule).                                                   R454 R527
R454_DOC_SURFACES = (  # R454 R527
    "readme", "sdd",                 # R454 R527
    "helptext", "metric-inventory",  # R454 R527
    "mandate-row", "man-page",       # R454 R527
)


# ---------------------------------------------------------------- static

def test_api_daemon_present_and_executable():
    assert API_PY.is_file(), f"missing API daemon: {API_PY}"
    assert os.access(API_PY, os.X_OK), (
        f"R527: {API_PY} must be executable"
    )


def test_webapp_html_present():
    assert WEBAPP_HTML.is_file(), f"missing webapp asset: {WEBAPP_HTML}"


def test_systemd_unit_present_and_hardened():
    assert UNIT_FILE.is_file(), f"missing systemd unit: {UNIT_FILE}"
    text = UNIT_FILE.read_text()
    # R171 defense-in-depth — same hardening keys as the R515/R518/
    # R521/R524 API units.
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
            f"R527 systemd unit missing R171 hardening key: {key!r}"
        )
    # Loopback-default exposure.
    assert "DOC_COVERAGE_API_BIND=127.0.0.1" in text, (
        "R527 unit must default-bind to loopback"
    )
    assert "DOC_COVERAGE_API_PORT=8099" in text, (
        "R527 unit must use port 8099 (sister to trinity-api 8095 + "
        "router-api 8096 + compliance-api 8097 + anti-min-api 8098)"
    )


def test_webapp_html_shape_sovereign_clean():
    html = WEBAPP_HTML.read_text()
    assert html.lstrip().lower().startswith("<!doctype html>"), (
        "webapp must use HTML5 doctype"
    )
    assert 'name="x-sovereign-module"' in html
    assert 'content="doc-coverage-webapp"' in html
    assert 'name="x-sovereign-shipped-in"' in html
    assert "R527" in html
    # Standing rule meta — operator §1g sacrosanct.
    assert "docs ARE the source of truth." in html


def test_webapp_zero_external_deps():
    """Operator-§1g UX rule: no CDN fetches, no external fonts, no JS
    framework — sovereignty-clean single-file webapp. Same contract
    enforced for trinity/router/compliance/anti-min webapps."""
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
    UI — same shape as router/trinity/compliance/anti-min disclaimers."""
    html = WEBAPP_HTML.read_text()
    low = html.lower()
    assert "§17" in html or "section 17" in low, (
        "webapp must surface the operator §17 boundary disclaimer"
    )
    assert "doc-coverage" in low, (
        "webapp disclaimer must name the doc-coverage mechanism"
    )
    assert ("sovereign-doc-coverage-api" in low
            or "doc-coverage-api.service" in low), (
        "webapp must name the backing systemd service"
    )


def test_webapp_lists_six_doc_surfaces():
    """The R454 6-doc-surface ladder MUST be visible in the webapp
    body — operator-§1g UX rule: full ladder per page."""
    html = WEBAPP_HTML.read_text().lower()
    for kind in R454_DOC_SURFACES:
        assert kind in html, (
            f"webapp must surface R454 doc-surface id {kind!r}"
        )


# ----------------------------------------------------- live daemon spin-up

class _DaemonHarness:
    def __init__(self):
        self.port = None
        self.proc = None

    def __enter__(self):
        # Allocate a free loopback port to avoid colliding with 8099.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            self.port = s.getsockname()[1]
        env = os.environ.copy()
        env["DOC_COVERAGE_API_BIND"] = "127.0.0.1"
        env["DOC_COVERAGE_API_PORT"] = str(self.port)
        env["SOVEREIGN_OS_METRICS_DIR"] = "/tmp/r527-metrics-test"
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
            f"doc-coverage-api daemon never became healthy on port "
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
    """R527 closes the doc-coverage surface ladder — /version MUST
    list all 8 surfaces."""
    with _DaemonHarness() as d:
        with d.fetch("/version") as r:
            assert r.status == 200
            payload = json.loads(r.read())
    assert payload["module"] == "doc-coverage-api"
    assert "R527" in payload["shipped_in"]
    assert payload["spec_ref"] == "R454"
    surfaces = set(payload.get("surfaces", []))
    expected = {"core", "cli", "tui", "api",
                "service", "dashboard", "mcp", "webapp"}
    assert surfaces == expected, (
        f"R527: doc-coverage-api /version must report all 8 surfaces; "
        f"got {sorted(surfaces)}"
    )
    assert payload.get("standing_rule") == "docs ARE the source of truth."
    # 6 read-only inspection verbs — all the doc-coverage.py verbs
    # except `watch` (TUI-only, refresh-loop is an MCP/API anti-
    # pattern).
    assert set(payload.get("verbs", [])) == {
        "kinds", "modules", "coverage",
        "scan", "gaps", "selfdef",
    }


def test_live_kinds_payload_lists_six():
    with _DaemonHarness() as d:
        with d.fetch("/kinds") as r:
            assert r.status == 200
            payload = json.loads(r.read())
    assert payload.get("count") == 6
    ids = {k["id"] for k in payload.get("kinds", [])}
    assert ids == set(R454_DOC_SURFACES), (
        f"/kinds must enumerate all 6 R454 doc-surfaces; "
        f"got {sorted(ids)}"
    )


def test_live_modules_payload_shape():
    with _DaemonHarness() as d:
        with d.fetch("/modules") as r:
            assert r.status == 200
            payload = json.loads(r.read())
    assert isinstance(payload.get("modules"), list)
    assert payload.get("count") == len(payload["modules"])
    assert payload["count"] > 0, "doc-coverage tracks at least one module"


def test_live_coverage_payload_shape():
    with _DaemonHarness() as d:
        with d.fetch("/coverage") as r:
            assert r.status == 200
            payload = json.loads(r.read())
    matrix = payload.get("coverage") or []
    assert matrix, "/coverage must return at least one module row"
    for r in matrix:
        assert "module" in r and "doc_surface_count" in r and "cells" in r
        cell_kinds = {c["kind"] for c in r["cells"]}
        assert cell_kinds == set(R454_DOC_SURFACES), (
            f"row {r['module']!r} cells must enumerate all 6 doc-"
            f"surfaces; got {sorted(cell_kinds)}"
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


def test_live_scan_payload_shape():
    with _DaemonHarness() as d:
        with d.fetch("/scan") as r:
            assert r.status == 200
            payload = json.loads(r.read())
    rows = payload.get("scan") or []
    assert rows
    for r in rows:
        assert "module" in r
        assert "present_in" in r
        assert "missing_from" in r
        assert "doc_surface_count" in r


def test_live_gaps_default_threshold():
    with _DaemonHarness() as d:
        with d.fetch("/gaps") as r:
            assert r.status == 200
            payload = json.loads(r.read())
    assert "threshold" in payload
    assert isinstance(payload.get("below_threshold"), list)


def test_live_gaps_threshold_query():
    """Explicit ?threshold=6 (everything below the 6-surface ceiling)
    MUST surface ALL underdocumented modules."""
    with _DaemonHarness() as d:
        with d.fetch("/gaps?threshold=6") as r:
            assert r.status == 200
            payload = json.loads(r.read())
    assert payload["threshold"] == 6


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
    assert "doc-coverage-webapp" in body


def test_live_mutation_methods_rejected_with_405():
    """Operator §17 sovereignty: no mutation verbs at the API surface.
    Doc-coverage has NO mutation verbs at any surface period — POST/
    PUT/DELETE/PATCH MUST all return 405."""
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
                # Boundary explanation must mention the source-of-truth
                # rule.
                assert ("source of truth" in low or "no mutation" in low)


def test_live_unknown_path_404():
    with _DaemonHarness() as d:
        try:
            d.fetch("/no-such-path")
        except urllib.error.HTTPError as e:
            assert e.code == 404


# ----------------------------------------------------- importlib reuse

def test_api_importlib_loads_doc_coverage_core():
    """The daemon MUST reuse doc-coverage.py's MODULES + DOC_KINDS +
    scan_module — no drift between CLI / TUI / MCP / API surfaces."""
    spec = importlib.util.spec_from_file_location("_r527", API_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod._CORE_PATH.name == "doc-coverage.py", (
        "R527 daemon must importlib-load doc-coverage.py"
    )
    assert hasattr(mod._core, "MODULES")
    assert hasattr(mod._core, "DOC_KINDS")
    assert hasattr(mod._core, "scan_module")
    assert len(mod._core.DOC_KINDS) == 6


# ----------------------------------------------------- surface-map post-

def test_doc_coverage_surface_map_at_structural_ceiling():
    """R527 closes the doc-coverage surface ladder — surface-map MUST
    report at_structural_ceiling=True with 0 FUTURE waivers."""
    result = subprocess.run(
        ["python3", str(SURFACE_MAP), "coverage", "--module",
         "doc-coverage", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr[:300]
    data = json.loads(result.stdout)
    entries = data.get("coverage", [data])
    entry = entries[0] if entries else {}
    assert entry.get("surface_count", 0) == 8, (
        f"doc-coverage must be at 8 surfaces post-R527; got {entry}"
    )
    assert entry.get("at_structural_ceiling") is True, (
        f"doc-coverage must be at_structural_ceiling=True post-R527; "
        f"got {entry}"
    )
    assert entry.get("future_waiver_count", 0) == 0, (
        f"doc-coverage must have 0 FUTURE waivers post-R527; "
        f"got {entry}"
    )
    matrix = entry.get("matrix", [])
    for surface in ("api", "service", "webapp"):
        row = next(
            (r for r in matrix if r.get("surface") == surface), None
        )
        assert row is not None, (
            f"doc-coverage matrix missing {surface!r} row"
        )
        assert row.get("state") == "shipped", (
            f"doc-coverage {surface} must be shipped post-R527; "
            f"got {row}"
        )


def test_dashboards_readme_documents_r527_metric():
    """The metric registry MUST list the R527 metric — operator-§1g
    visibility rule for the observability ladder."""
    text = DASH_README.read_text()
    assert "sovereign_os_operator_doc_coverage_api_request_total" in text
    assert "R527" in text
