"""R524 (E5++) — anti-minimization-audit API + webapp + service surface
contract lint.

Closes the anti-min api:FUTURE + webapp:FUTURE waivers AND replaces the
prior service:not-applicable waiver with a REAL systemd-managed read-
only daemon. Raises the anti-min surface count from 5 → 8 shipped
surfaces (core / cli / tui / api / service / dashboard / mcp / webapp).
Third and final commit in the anti-min tier-3 surface-expansion arc
(R522 TUI → R523 MCP → R524 API + webapp + service). Lands anti-min
as the SEVENTH §1g module at full 8-surface structural ceiling — after
edge-firewall (R506), network-edge (R509), global-history (R512),
trinity (R515), router (R518), and compliance (R521).

Per operator §1g verbatim (sacrosanct):

  "We do not minimize anything."

Per operator §1g 8-surface delivery contract (verbatim):

  "everything is not just core, not just cli, not just TUI, not just
   API, not just tool and MCP but also Dashboards and Web Apps and
   Services"

Sovereignty boundaries enforced by this contract:
  - read-only at every HTTP method except GET/HEAD (operator §17)
  - anti-min has NO mutation verbs at any surface — the R474
    `anti-min-waiver:` annotations are operator-authored in-source
    markers, NOT something the daemon toggles
  - webapp is single-file, zero external deps, same-origin only
  - loopback-bind default (port 8098, sister to trinity 8095 +
    router 8096 + compliance 8097)
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
API_PY = REPO_ROOT / "scripts" / "operator" / "anti-min-api.py"
WEBAPP_HTML = (
    REPO_ROOT / "webapp" / "anti-minimization-audit" / "index.html"
)
UNIT_FILE = (
    REPO_ROOT / "systemd" / "system" / "sovereign-anti-min-api.service"
)
SURFACE_MAP = REPO_ROOT / "scripts" / "operator" / "surface-map.py"
DASH_README = (
    REPO_ROOT / "docs" / "observability" / "dashboards" / "README.md"
)

# R456 8 operator-named pattern ids. Inline anchors keep the          R456 R524
# self-audit scanners quiet on the pattern-id literals themselves     R456 R524
# (operator-§1g self-audit cleanliness rule).                          R456 R524
R456_PATTERN_IDS = (  # R456 R524
    "todo-no-anchor", "empty-stub",      # R456 R524
    "skipped-no-followup", "surface-gap",  # R456 R524
    "doc-gap", "mandate-todo",            # R456 R524
    "minimize-phrase", "partial-status",  # R456 R524
)


# ---------------------------------------------------------------- static

def test_api_daemon_present_and_executable():
    assert API_PY.is_file(), f"missing API daemon: {API_PY}"
    assert os.access(API_PY, os.X_OK), (
        f"R524: {API_PY} must be executable"
    )


def test_webapp_html_present():
    assert WEBAPP_HTML.is_file(), f"missing webapp asset: {WEBAPP_HTML}"


def test_systemd_unit_present_and_hardened():
    assert UNIT_FILE.is_file(), f"missing systemd unit: {UNIT_FILE}"
    text = UNIT_FILE.read_text()
    # R171 defense-in-depth — same hardening keys as the R515/R518/R521
    # API units.
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
            f"R524 systemd unit missing R171 hardening key: {key!r}"
        )
    # Loopback-default exposure.
    assert "ANTI_MIN_API_BIND=127.0.0.1" in text, (
        "R524 unit must default-bind to loopback"
    )
    assert "ANTI_MIN_API_PORT=8098" in text, (
        "R524 unit must use port 8098 (sister to trinity-api 8095 + "
        "router-api 8096 + compliance-api 8097)"
    )


def test_webapp_html_shape_sovereign_clean():
    html = WEBAPP_HTML.read_text()
    # HTML5 doctype + sovereign meta tags identify the surface.
    assert html.lstrip().lower().startswith("<!doctype html>"), (
        "webapp must use HTML5 doctype"
    )
    assert 'name="x-sovereign-module"' in html
    assert 'content="anti-min-webapp"' in html
    assert 'name="x-sovereign-shipped-in"' in html
    assert "R524" in html
    # Standing rule meta — operator §1g sacrosanct.
    assert "We do not minimize anything." in html


def test_webapp_zero_external_deps():
    """Operator-§1g UX rule: no CDN fetches, no external fonts, no JS
    framework — sovereignty-clean single-file webapp. Same contract
    enforced for trinity/router/compliance webapps."""
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
    UI — same shape as router/trinity/compliance disclaimers."""
    html = WEBAPP_HTML.read_text()
    low = html.lower()
    assert "§17" in html or "section 17" in low, (
        "webapp must surface the operator §17 boundary disclaimer"
    )
    assert "anti-min-waiver" in low, (
        "webapp disclaimer must name the R474 anti-min-waiver mechanism"
    )
    assert "sovereign-anti-min-api" in low or "anti-min-api.service" in low, (
        "webapp must name the backing systemd service"
    )


def test_webapp_lists_eight_patterns():
    """The R456 8-pattern ladder MUST be visible in the webapp body —
    operator-§1g UX rule: full ladder per page."""
    html = WEBAPP_HTML.read_text().lower()
    for pat in R456_PATTERN_IDS:
        assert pat in html, (
            f"webapp must surface R456 pattern id {pat!r}"
        )


# ----------------------------------------------------- live daemon spin-up

class _DaemonHarness:
    def __init__(self):
        self.port = None
        self.proc = None

    def __enter__(self):
        # Allocate a free loopback port to avoid colliding with 8098.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            self.port = s.getsockname()[1]
        env = os.environ.copy()
        env["ANTI_MIN_API_BIND"] = "127.0.0.1"
        env["ANTI_MIN_API_PORT"] = str(self.port)
        env["SOVEREIGN_OS_METRICS_DIR"] = "/tmp/r524-metrics-test"
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
            f"anti-min-api daemon never became healthy on port "
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
    """R524 closes the anti-min surface ladder — /version MUST list
    all 8 surfaces."""
    with _DaemonHarness() as d:
        with d.fetch("/version") as r:
            assert r.status == 200
            payload = json.loads(r.read())
    assert payload["module"] == "anti-min-api"
    assert "R524" in payload["shipped_in"]
    assert payload["spec_ref"] == "R456"
    surfaces = set(payload.get("surfaces", []))
    expected = {"core", "cli", "tui", "api",
                "service", "dashboard", "mcp", "webapp"}
    assert surfaces == expected, (
        f"R524: anti-min-api /version must report all 8 surfaces; "
        f"got {sorted(surfaces)}"
    )
    assert payload.get("standing_rule") == "We do not minimize anything."
    # 7 read-only inspection verbs — all 8 audit verbs minus `watch`
    # (TUI-only, refresh-loop is an MCP/API anti-pattern).
    assert set(payload.get("verbs", [])) == {
        "patterns", "report", "scan", "waivers",
        "module", "cross-module", "selfdef",
    }


def test_live_patterns_payload_lists_eight():
    with _DaemonHarness() as d:
        with d.fetch("/patterns") as r:
            assert r.status == 200
            payload = json.loads(r.read())
    assert payload.get("count") == 8
    ids = {p["id"] for p in payload.get("patterns", [])}
    assert ids == set(R456_PATTERN_IDS), (
        f"/patterns must enumerate all 8 R456 patterns; got {sorted(ids)}"
    )


def test_live_report_payload_shape():
    with _DaemonHarness() as d:
        with d.fetch("/report") as r:
            assert r.status == 200
            payload = json.loads(r.read())
    assert "total" in payload
    summary = payload.get("summary") or {}
    for pat in R456_PATTERN_IDS:
        assert pat in summary, (
            f"/report summary missing pattern {pat!r}"
        )
    assert payload["total"] == sum(summary.values())


def test_live_scan_pattern_filter():
    # Uses pattern-id literal to exercise /scan filter — R456 R524.
    sample_pattern = R456_PATTERN_IDS[0]
    with _DaemonHarness() as d:
        with d.fetch(f"/scan?pattern={sample_pattern}") as r:
            assert r.status == 200
            payload = json.loads(r.read())
    assert payload.get("patterns_scanned") == [sample_pattern]
    assert sample_pattern in (payload.get("results") or {})


def test_live_scan_unknown_pattern_400():
    """Unknown pattern names MUST return 400 (operator-§1g UX:
    discoverable error)."""
    with _DaemonHarness() as d:
        try:
            d.fetch("/scan?pattern=not-a-real-pattern")
            raise AssertionError("expected 400 for unknown pattern")
        except urllib.error.HTTPError as e:
            assert e.code == 400
            body = json.loads(e.read())
            assert "known" in body


def test_live_waivers_payload_shape():
    with _DaemonHarness() as d:
        with d.fetch("/waivers") as r:
            assert r.status == 200
            payload = json.loads(r.read())
    assert isinstance(payload.get("waivers"), list)
    assert payload.get("count") == len(payload["waivers"])


def test_live_module_endpoint_requires_name():
    with _DaemonHarness() as d:
        try:
            d.fetch("/module")
            raise AssertionError("expected 400 for missing name param")
        except urllib.error.HTTPError as e:
            assert e.code == 400


def test_live_cross_module_default_threshold():
    with _DaemonHarness() as d:
        with d.fetch("/cross-module") as r:
            assert r.status == 200
            payload = json.loads(r.read())
    assert payload.get("threshold") == 3
    assert isinstance(payload.get("short_on_both_axes"), list)


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
    assert "anti-min-webapp" in body


def test_live_mutation_methods_rejected_with_405():
    """Operator §17 sovereignty: no mutation verbs at the API surface.
    Anti-min has NO mutation verbs at any surface period — POST/PUT/
    DELETE/PATCH MUST all return 405."""
    with _DaemonHarness() as d:
        for method in ("POST", "PUT", "DELETE", "PATCH"):
            try:
                d.fetch("/report", method=method)
                raise AssertionError(
                    f"{method} /report must 405 (got 2xx)"
                )
            except urllib.error.HTTPError as e:
                assert e.code == 405, (
                    f"{method} expected 405; got {e.code}"
                )
                body = e.read().decode("utf-8")
                low = body.lower()
                assert "read-only" in low
                # Boundary explanation must name the R474 waiver mechanism.
                assert "anti-min-waiver" in low or "no mutation" in low


def test_live_unknown_path_404():
    with _DaemonHarness() as d:
        try:
            d.fetch("/no-such-path")
        except urllib.error.HTTPError as e:
            assert e.code == 404


# ----------------------------------------------------- importlib reuse

def test_api_importlib_loads_anti_min_core():
    """The daemon MUST reuse anti-minimization-audit.py's PATTERNS +
    PATTERN_SCANNERS — no drift between CLI / TUI / MCP / API surfaces."""
    spec = importlib.util.spec_from_file_location("_r524", API_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod._CORE_PATH.name == "anti-minimization-audit.py", (
        "R524 daemon must importlib-load anti-minimization-audit.py"
    )
    assert hasattr(mod._core, "PATTERNS")
    assert hasattr(mod._core, "PATTERN_IDS")
    assert hasattr(mod._core, "PATTERN_SCANNERS")
    assert len(mod._core.PATTERN_IDS) == 8


# ----------------------------------------------------- surface-map post-

def test_anti_min_surface_map_at_structural_ceiling():
    """R524 closes the anti-min surface ladder — surface-map MUST
    report at_structural_ceiling=True with 0 FUTURE waivers."""
    result = subprocess.run(
        ["python3", str(SURFACE_MAP), "coverage", "--module",
         "anti-minimization-audit", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr[:300]
    data = json.loads(result.stdout)
    entries = data.get("coverage", [data])
    entry = entries[0] if entries else {}
    assert entry.get("surface_count", 0) == 8, (
        f"anti-min must be at 8 surfaces post-R524; got {entry}"
    )
    assert entry.get("at_structural_ceiling") is True, (
        f"anti-min must be at_structural_ceiling=True post-R524; "
        f"got {entry}"
    )
    assert entry.get("future_waiver_count", 0) == 0, (
        f"anti-min must have 0 FUTURE waivers post-R524; got {entry}"
    )
    matrix = entry.get("matrix", [])
    for surface in ("api", "service", "webapp"):
        row = next(
            (r for r in matrix if r.get("surface") == surface), None
        )
        assert row is not None, (
            f"anti-min matrix missing {surface!r} row"
        )
        assert row.get("state") == "shipped", (
            f"anti-min {surface} must be shipped post-R524; got {row}"
        )


def test_dashboards_readme_documents_r524_metric():
    """The metric registry MUST list the R524 metric — operator-§1g
    visibility rule for the observability ladder."""
    text = DASH_README.read_text()
    assert "sovereign_os_operator_anti_min_api_request_total" in text
    assert "R524" in text
