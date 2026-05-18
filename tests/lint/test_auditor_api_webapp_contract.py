"""R539 (E5++) — auditor API + webapp surface contract lint.

Closes the auditor api:FUTURE + webapp:FUTURE waivers. Raises the
auditor surface count from 6 -> 8 shipped surfaces (core / cli / tui /
api / service / dashboard / mcp / webapp). Third and final commit in
the auditor tier-3 surface-expansion arc (R537 TUI -> R538 MCP ->
R539 API + webapp). Lands auditor as the TWELFTH §1g module at full
8-surface structural ceiling — after edge-firewall (R506), network-
edge (R509), global-history (R512), trinity (R515), router (R518),
compliance (R521), anti-min (R524), doc-coverage (R527), ux-design-
audit (R530), surface-map (R533), and weaver (R536).

UNLIKE the R510/R515/R518/R521/R524/R527/R530/R533/R536 ceiling-
promotion pattern (which REPLACED a `service: not applicable` waiver
with a new systemd daemon), the auditor `service` surface ALREADY
shipped (R155 guardian-core.service — a SECURITY daemon performing
neutralization). The R539 daemon is a SECOND, SEPARATE systemd unit
(sovereign-auditor-api.service) that coexists with guardian-core.

Per operator §1g verbatim (sacrosanct):

  "We do not minimize anything."

Per operator §1g 8-surface delivery contract (verbatim, R453 anchor):

  "everything is not just core, not just cli, not just TUI, not just
   API, not just tool and MCP but also Dashboards and Web Apps and
   Services"

Sovereignty boundaries enforced by this contract (operator §17):
  - read-only at every HTTP method except GET/HEAD
  - neutralization is sovereignty-critical and stays CCD-triggered +
    CLI-gated — the Tetragon kernel hook → SIGKILL via guardian-core
    path is intentionally NOT exposed at the API or MCP surfaces
  - webapp is single-file, zero external deps, same-origin only
  - loopback-bind default (port 8103 — sister to trinity-api 8095 /
    router-api 8096 / compliance-api 8097 / anti-min-api 8098 / doc-
    coverage-api 8099 / ux-design-audit-api 8100 / surface-map-api
    8101 / weaver-api 8102)
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
API_PY = REPO_ROOT / "scripts" / "operator" / "auditor-api.py"
WEBAPP_HTML = REPO_ROOT / "webapp" / "auditor" / "index.html"
UNIT_FILE = (
    REPO_ROOT / "systemd" / "system"
    / "sovereign-auditor-api.service"
)
SURFACE_MAP = REPO_ROOT / "scripts" / "operator" / "surface-map.py"
DASH_README = (
    REPO_ROOT / "docs" / "observability" / "dashboards" / "README.md"
)

R453_SURFACES = (
    "core", "cli", "tui", "api",
    "mcp", "dashboard", "webapp", "service",
)


# ---------------------------------------------------------------- static

def test_api_daemon_present_and_executable():
    assert API_PY.is_file(), f"missing API daemon: {API_PY}"
    assert os.access(API_PY, os.X_OK), (
        f"R539: {API_PY} must be executable"
    )


def test_webapp_html_present():
    assert WEBAPP_HTML.is_file(), f"missing webapp asset: {WEBAPP_HTML}"


def test_systemd_unit_present_and_hardened():
    assert UNIT_FILE.is_file(), f"missing systemd unit: {UNIT_FILE}"
    text = UNIT_FILE.read_text()
    # R171 defense-in-depth — same hardening keys as the R515/R518/
    # R521/R524/R527/R530/R533/R536 API units.
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
            f"R539 systemd unit missing R171 hardening key: {key!r}"
        )
    # Loopback-default exposure + port allocation.
    assert "AUDITOR_API_BIND=127.0.0.1" in text, (
        "R539 unit must default-bind to loopback"
    )
    assert "AUDITOR_API_PORT=8103" in text, (
        "R539 unit must use port 8103 (sister to trinity-api 8095 / "
        "router-api 8096 / compliance-api 8097 / anti-min-api 8098 / "
        "doc-coverage-api 8099 / ux-design-audit-api 8100 / "
        "surface-map-api 8101 / weaver-api 8102)"
    )


def test_systemd_unit_documents_sovereignty_boundary():
    """The §17 boundary MUST be cited in the unit file — operator-§1g
    visibility rule and a structural anchor that this daemon is
    inspection-only (neutralization stays CCD-triggered + CLI-gated
    via guardian-core, NOT here)."""
    text_lower = UNIT_FILE.read_text().lower()
    text_raw = UNIT_FILE.read_text()
    assert "§17" in text_raw or "section 17" in text_lower, (
        "unit must reference operator §17 sovereignty boundary"
    )
    assert "cli-gated" in text_lower or "cli-only" in text_lower, (
        "unit must note that neutralization stays CLI-only"
    )
    # Coexistence framing — load-bearing distinction vs guardian-core.
    assert "guardian-core" in text_lower, (
        "unit must reference the R155 guardian-core daemon (the "
        "neutralization sibling — R539 is inspection-only, coexists)"
    )


def test_webapp_html_shape_sovereign_clean():
    html = WEBAPP_HTML.read_text()
    assert html.lstrip().lower().startswith("<!doctype html>"), (
        "webapp must use HTML5 doctype"
    )
    assert 'name="x-sovereign-module"' in html
    assert 'content="auditor-webapp"' in html
    assert 'name="x-sovereign-shipped-in"' in html
    assert "R539" in html
    # Standing rule meta — operator §1g sacrosanct (R453 anchor).
    assert "Dashboards and Web Apps and Services" in html, (
        "webapp must carry the R453 8-surface delivery-contract "
        "standing rule verbatim"
    )


def test_webapp_zero_external_deps():
    """Operator-§1g UX rule: no CDN fetches, no external fonts, no JS
    framework — sovereignty-clean single-file webapp."""
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
    UI — same shape as surface-map / weaver / doc-coverage disclaimers."""
    html = WEBAPP_HTML.read_text()
    low = html.lower()
    assert "§17" in html or "section 17" in low, (
        "webapp must surface the operator §17 boundary disclaimer"
    )
    assert "auditor" in low, (
        "webapp disclaimer must name the auditor mechanism"
    )
    assert "sovereign-auditor-api" in low, (
        "webapp must name the backing systemd service"
    )
    # The CLI-gated neutralization framing is the load-bearing R539
    # invariant — agents/operators must learn from the page that
    # neutralization stays CCD-triggered + CLI-only.
    assert "cli" in low and (
        "neutraliz" in low or "guardian-core" in low
    ), (
        "webapp must surface the CLI-gated neutralization framing"
    )


def test_webapp_lists_all_eight_surface_ids():
    """The R453 8-surface ladder MUST be visible in the webapp body —
    operator-§1g UX rule: auditor closes the ladder at R539, so the
    webapp itself MUST enumerate the full ladder."""
    html = WEBAPP_HTML.read_text().lower()
    for surface in R453_SURFACES:
        assert surface in html, (
            f"webapp must surface R453 §1g surface id {surface!r}"
        )


# ----------------------------------------------------- live daemon spin-up

class _DaemonHarness:
    def __init__(self, audit_log: str | None = None):
        self.port = None
        self.proc = None
        self.audit_log = audit_log

    def __enter__(self):
        # Allocate a free loopback port to avoid colliding with 8103.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            self.port = s.getsockname()[1]
        env = os.environ.copy()
        env["AUDITOR_API_BIND"] = "127.0.0.1"
        env["AUDITOR_API_PORT"] = str(self.port)
        env["SOVEREIGN_OS_METRICS_DIR"] = "/tmp/r539-metrics-test"
        if self.audit_log:
            env["AUDITOR_AUDIT_LOG"] = self.audit_log
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
            f"auditor-api daemon never became healthy on port "
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

    def fetch(self, path: str, method: str = "GET", timeout: int = 30):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}", method=method,
        )
        return urllib.request.urlopen(req, timeout=timeout)


def test_live_version_8_surfaces():
    """R539 closes the auditor surface ladder — /version MUST list all
    8 surfaces."""
    with _DaemonHarness() as d:
        with d.fetch("/version") as r:
            assert r.status == 200
            payload = json.loads(r.read())
    assert payload["module"] == "auditor-api"
    assert "R539" in payload["shipped_in"]
    spec = payload.get("spec_ref", "").lower()
    assert "master spec" in spec
    # Both anchors must be present — §17 Module 3 + §10.
    assert "§ 17 module 3" in spec or "section 17 module 3" in spec, (
        f"/version spec_ref must cite master spec § 17 Module 3 "
        f"(Immutable Gatekeeper); got {payload.get('spec_ref')!r}"
    )
    assert "§ 10" in payload.get("spec_ref", "") \
        or "section 10" in spec, (
        f"/version spec_ref must cite master spec § 10 (Native "
        f"Guardian Loop); got {payload.get('spec_ref')!r}"
    )
    surfaces = set(payload.get("surfaces", []))
    expected = set(R453_SURFACES)
    assert surfaces == expected, (
        f"R539: auditor-api /version must report all 8 surfaces; "
        f"got {sorted(surfaces)}"
    )
    rule = payload.get("standing_rule", "")
    assert "Dashboards and Web Apps and Services" in rule, (
        f"R539 /version must carry the R453 standing rule verbatim; "
        f"got {rule!r}"
    )
    # 3 read-only API verbs — neutralization stays CLI-only per §17.
    assert set(payload.get("verbs", [])) == {
        "status", "last-violation", "history"
    }
    assert set(payload.get("cli_gated_verbs", [])) == {
        "neutralize", "kill", "purge"
    }, (
        f"/version must surface that neutralize/kill/purge are CLI-"
        f"gated; got cli_gated_verbs={payload.get('cli_gated_verbs')}"
    )
    boundary = payload.get("sovereignty_boundary", "")
    low = boundary.lower()
    assert "§17" in boundary or "section 17" in low, (
        "/version sovereignty_boundary must cite operator §17"
    )
    # Coexistence framing — load-bearing.
    assert "guardian-core" in low or "ccd-triggered" in low or \
        "cli-gated" in low, (
        "/version sovereignty_boundary must explain the CCD-triggered "
        "+ CLI-gated neutralization path"
    )


def test_live_status_payload_shape():
    """/status MUST emit the trinity-inspect auditor_payload — same
    data the CLI/TUI/MCP surfaces share (no drift across surfaces)."""
    with _DaemonHarness() as d:
        with d.fetch("/status") as r:
            assert r.status == 200
            payload = json.loads(r.read())
    assert payload.get("tier") == "auditor"
    assert payload.get("always_on") is True
    assert "tetragon_available" in payload
    assert "service" in payload
    assert payload["service"].get("name") == "sovereign-auditor"


def test_live_last_violation_payload_shape(tmp_path):
    """/last-violation MUST emit module/verb/spec_ref/log_path/present/
    sovereignty_boundary keys — bound to a temp audit log so the test
    is hermetic."""
    fake_log = tmp_path / "security_audit.log"
    fake_log.write_text(
        '{"ts": "2026-05-17T12:00:00Z", "verdict": "benign"}\n'
        '{"ts": "2026-05-18T09:30:00Z", "verdict": "trigger"}\n'
    )
    with _DaemonHarness(audit_log=str(fake_log)) as d:
        with d.fetch("/last-violation") as r:
            assert r.status == 200
            payload = json.loads(r.read())
    assert payload.get("module") == "auditor"
    assert payload.get("verb") == "last-violation"
    assert "§ 10" in payload.get("spec_ref", "")
    assert payload.get("log_path") == str(fake_log)
    assert payload.get("present") is True
    assert "§17" in payload.get("sovereignty_boundary", "")
    assert '"verdict": "trigger"' in payload.get("line", "")
    assert payload.get("total_lines") == 2


def test_live_last_violation_handles_missing_log(tmp_path):
    """When the audit log file is absent (fresh install, no events
    yet), /last-violation MUST gracefully emit present=False."""
    missing = tmp_path / "no-such-audit-log.log"
    with _DaemonHarness(audit_log=str(missing)) as d:
        with d.fetch("/last-violation") as r:
            payload = json.loads(r.read())
    assert payload.get("present") is False
    assert payload.get("line") is None
    assert payload.get("log_path") == str(missing)


def test_live_history_payload_shape(tmp_path):
    """/history?n=N MUST emit module/verb/log_path/present/requested_n/
    lines[]/count/sovereignty_boundary — bounded tail of the audit
    log."""
    fake_log = tmp_path / "security_audit.log"
    body = "".join(f"line {i}\n" for i in range(50))
    fake_log.write_text(body)
    with _DaemonHarness(audit_log=str(fake_log)) as d:
        with d.fetch("/history?n=5") as r:
            assert r.status == 200
            payload = json.loads(r.read())
    assert payload.get("module") == "auditor"
    assert payload.get("verb") == "history"
    assert payload.get("requested_n") == 5
    assert payload.get("count") == 5
    assert isinstance(payload.get("lines"), list)
    assert payload["lines"][-1] == "line 49"
    assert payload["lines"][0] == "line 45"
    assert payload.get("total_lines") == 50
    assert "§17" in payload.get("sovereignty_boundary", "")


def test_live_history_default_n_is_20(tmp_path):
    """Operator §1g UX consistency: history default N MUST mirror the
    osctl auditor history default (20)."""
    fake_log = tmp_path / "security_audit.log"
    body = "".join(f"row {i}\n" for i in range(100))
    fake_log.write_text(body)
    with _DaemonHarness(audit_log=str(fake_log)) as d:
        with d.fetch("/history") as r:
            payload = json.loads(r.read())
    assert payload.get("requested_n") == 20
    assert payload.get("count") == 20


def test_live_history_caps_at_max_n(tmp_path):
    """history?n must be capped at HISTORY_MAX_N (1000) — operator-§1g
    structural ceiling: large N values get clamped, not honored as-is."""
    fake_log = tmp_path / "security_audit.log"
    fake_log.write_text("just one line\n")
    with _DaemonHarness(audit_log=str(fake_log)) as d:
        with d.fetch("/history?n=999999") as r:
            payload = json.loads(r.read())
    assert payload.get("requested_n") == 1000
    assert payload.get("max_n") == 1000


def test_live_webapp_alias_serves_html():
    with _DaemonHarness() as d:
        with d.fetch("/webapp/") as r:
            assert r.status == 200
            body = r.read().decode("utf-8")
            ct = r.headers.get("Content-Type", "")
    assert "text/html" in ct
    assert "<!DOCTYPE html>" in body or "<!doctype html>" in body.lower()
    assert "auditor-webapp" in body


def test_live_mutation_methods_rejected_with_405():
    """Operator §17 sovereignty: neutralization stays CCD-triggered +
    CLI-gated. POST/PUT/DELETE/PATCH MUST all return 405 with a
    CLI-gated remediation message."""
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
                # The remediation must point at the CLI / CCD.
                assert "cli" in low, (
                    f"{method} 405 body must point at the CLI as "
                    f"the remediation surface; got: {body[:200]}"
                )
                # The §17 boundary MUST be cited in the 405 framing.
                assert "§17" in body or "section 17" in low \
                    or "sovereignty" in low, (
                    f"{method} 405 body must cite §17 / sovereignty "
                    f"boundary; got: {body[:200]}"
                )


def test_live_unknown_path_404():
    with _DaemonHarness() as d:
        try:
            d.fetch("/no-such-path")
        except urllib.error.HTTPError as e:
            assert e.code == 404


def test_live_healthz_ok():
    with _DaemonHarness() as d:
        with d.fetch("/healthz") as r:
            assert r.status == 200
            payload = json.loads(r.read())
    assert payload.get("status") == "ok"


# ----------------------------------------------------- importlib reuse

def test_api_importlib_loads_trinity_inspect_core():
    """The daemon MUST reuse trinity-inspect.py's auditor_payload —
    no drift between CLI / TUI / MCP / API surfaces. Mirrors the
    R536 weaver pattern."""
    spec = importlib.util.spec_from_file_location("_r539", API_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod._CORE_PATH.name == "trinity-inspect.py", (
        "R539 daemon must importlib-load trinity-inspect.py"
    )
    assert hasattr(mod._core, "auditor_payload"), (
        "trinity-inspect must expose auditor_payload (shared with "
        "CLI / TUI / MCP / API surfaces)"
    )


# ----------------------------------------------------- surface-map post-

def test_surface_map_auditor_at_structural_ceiling():
    """R539 closes the auditor surface ladder — surface-map MUST
    report the auditor entry at at_structural_ceiling=True with 0
    FUTURE waivers AND 0 structural waivers (auditor reaches all 8
    surfaces, INCLUDING the pre-existing R155 guardian-core service
    surface)."""
    result = subprocess.run(
        ["python3", str(SURFACE_MAP), "coverage", "--module",
         "auditor", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr[:300]
    data = json.loads(result.stdout)
    entries = data.get("coverage", [data])
    entry = entries[0] if entries else {}
    assert entry.get("surface_count", 0) == 8, (
        f"auditor must be at 8 surfaces post-R539; got {entry}"
    )
    assert entry.get("at_structural_ceiling") is True, (
        f"auditor must be at_structural_ceiling=True post-R539; "
        f"got {entry}"
    )
    assert entry.get("future_waiver_count", 0) == 0, (
        f"auditor must have 0 FUTURE waivers post-R539; got {entry}"
    )
    matrix = entry.get("matrix", [])
    for surface in ("api", "webapp", "service"):
        row = next(
            (r for r in matrix if r.get("surface") == surface), None
        )
        assert row is not None, (
            f"auditor matrix missing {surface!r} row"
        )
        assert row.get("state") == "shipped", (
            f"auditor {surface} must be shipped post-R539; got {row}"
        )


def test_surface_map_r539_milestone_all_modules_at_ceiling():
    """R539 historic invariant: ALL §1g modules at structural ceiling,
    ZERO FUTURE waivers across the entire codebase. This is the
    TWELFTH-and-final §1g module reaching ceiling — the §1g 8-surface
    delivery contract is now operator-fully-described across every
    single §1g instrument."""
    result = subprocess.run(
        ["python3", str(SURFACE_MAP), "coverage", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr[:300]
    data = json.loads(result.stdout)
    future_carrying = [
        e for e in data.get("coverage", [])
        if e.get("future_waiver_count", 0) > 0
    ]
    assert not future_carrying, (
        f"R539: ALL modules must have ZERO FUTURE waivers — got "
        f"future-carrying modules: "
        f"{[e['module'] for e in future_carrying]}"
    )


def test_dashboards_readme_documents_r539_metric():
    """The metric registry MUST list the R539 metric — operator-§1g
    visibility rule for the observability ladder."""
    text = DASH_README.read_text()
    assert (
        "sovereign_os_operator_auditor_api_request_total" in text
    ), "README must register the R539 auditor-api metric"
    assert "R539" in text, "README must anchor the R539 round"
