"""R536 (E5++) — weaver API + webapp + service surface contract lint.

Closes the weaver api:FUTURE + webapp:FUTURE waivers AND replaces the
prior service:not-applicable waiver with a REAL systemd-managed read-
only daemon. Raises the weaver surface count from 5 -> 8 shipped
surfaces (core / cli / tui / api / service / dashboard / mcp /
webapp). Third and final commit in the weaver tier-3 surface-
expansion arc (R534 TUI -> R535 MCP -> R536 API + webapp + service).
Lands weaver as the ELEVENTH §1g module at full 8-surface structural
ceiling — after edge-firewall (R506), network-edge (R509), global-
history (R512), trinity (R515), router (R518), compliance (R521),
anti-min (R524), doc-coverage (R527), ux-design-audit (R530), and
surface-map (R533).

Per operator §1g verbatim (sacrosanct):

  "We do not minimize anything."

Per operator §1g 8-surface delivery contract (verbatim, R453 anchor):

  "everything is not just core, not just cli, not just TUI, not just
   API, not just tool and MCP but also Dashboards and Web Apps and
   Services"

Sovereignty boundaries enforced by this contract (operator §17):
  - read-only at every HTTP method except GET/HEAD
  - atomic-state writes are sovereignty-critical and stay manual +
    CLI-gated — the mutation verb `write` (master spec § 21.1 atomic
    commit) and the runtime-arg verb `read` (per-file read) are
    intentionally NOT exposed at the API or MCP surfaces
  - webapp is single-file, zero external deps, same-origin only
  - loopback-bind default (port 8102 — sister to trinity-api 8095 /
    router-api 8096 / compliance-api 8097 / anti-min-api 8098 / doc-
    coverage-api 8099 / ux-design-audit-api 8100 / surface-map-api
    8101)
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
API_PY = REPO_ROOT / "scripts" / "operator" / "weaver-api.py"
WEBAPP_HTML = REPO_ROOT / "webapp" / "weaver" / "index.html"
UNIT_FILE = (
    REPO_ROOT / "systemd" / "system"
    / "sovereign-weaver-api.service"
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
        f"R536: {API_PY} must be executable"
    )


def test_webapp_html_present():
    assert WEBAPP_HTML.is_file(), f"missing webapp asset: {WEBAPP_HTML}"


def test_systemd_unit_present_and_hardened():
    assert UNIT_FILE.is_file(), f"missing systemd unit: {UNIT_FILE}"
    text = UNIT_FILE.read_text()
    # R171 defense-in-depth — same hardening keys as the R515/R518/
    # R521/R524/R527/R530/R533 API units.
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
            f"R536 systemd unit missing R171 hardening key: {key!r}"
        )
    # Loopback-default exposure + port allocation.
    assert "WEAVER_API_BIND=127.0.0.1" in text, (
        "R536 unit must default-bind to loopback"
    )
    assert "WEAVER_API_PORT=8102" in text, (
        "R536 unit must use port 8102 (sister to trinity-api 8095 / "
        "router-api 8096 / compliance-api 8097 / anti-min-api 8098 / "
        "doc-coverage-api 8099 / ux-design-audit-api 8100 / "
        "surface-map-api 8101)"
    )


def test_systemd_unit_documents_sovereignty_boundary():
    """The §17 boundary MUST be cited in the unit file — operator-§1g
    visibility rule and a structural anchor that this daemon is
    inspection-only."""
    text = UNIT_FILE.read_text().lower()
    assert "§17" in UNIT_FILE.read_text() or "section 17" in text, (
        "unit must reference operator §17 sovereignty boundary"
    )
    assert "cli-gated" in text or "cli-only" in text, (
        "unit must note that write/read stay CLI-only"
    )


def test_webapp_html_shape_sovereign_clean():
    html = WEBAPP_HTML.read_text()
    assert html.lstrip().lower().startswith("<!doctype html>"), (
        "webapp must use HTML5 doctype"
    )
    assert 'name="x-sovereign-module"' in html
    assert 'content="weaver-webapp"' in html
    assert 'name="x-sovereign-shipped-in"' in html
    assert "R536" in html
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
    UI — same shape as surface-map / ux-design-audit / doc-coverage
    disclaimers."""
    html = WEBAPP_HTML.read_text()
    low = html.lower()
    assert "§17" in html or "section 17" in low, (
        "webapp must surface the operator §17 boundary disclaimer"
    )
    assert "weaver" in low, (
        "webapp disclaimer must name the weaver mechanism"
    )
    assert "sovereign-weaver-api" in low, (
        "webapp must name the backing systemd service"
    )
    # The CLI-only mutation framing is the load-bearing R536 invariant.
    assert "cli" in low and (
        "atomic-state writes" in low or "write" in low
    ), (
        "webapp must surface the CLI-gated mutation framing"
    )


def test_webapp_lists_all_eight_surface_ids():
    """The R453 8-surface ladder MUST be visible in the webapp body —
    operator-§1g UX rule: weaver closes the ladder at R536, so the
    webapp itself MUST enumerate the full ladder."""
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
        # Allocate a free loopback port to avoid colliding with 8102.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            self.port = s.getsockname()[1]
        env = os.environ.copy()
        env["WEAVER_API_BIND"] = "127.0.0.1"
        env["WEAVER_API_PORT"] = str(self.port)
        env["SOVEREIGN_OS_METRICS_DIR"] = "/tmp/r536-metrics-test"
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
            f"weaver-api daemon never became healthy on port "
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
    """R536 closes the weaver surface ladder — /version MUST list all
    8 surfaces."""
    with _DaemonHarness() as d:
        with d.fetch("/version") as r:
            assert r.status == 200
            payload = json.loads(r.read())
    assert payload["module"] == "weaver-api"
    assert "R536" in payload["shipped_in"]
    assert "master spec" in payload.get("spec_ref", "").lower()
    surfaces = set(payload.get("surfaces", []))
    expected = set(R453_SURFACES)
    assert surfaces == expected, (
        f"R536: weaver-api /version must report all 8 surfaces; "
        f"got {sorted(surfaces)}"
    )
    rule = payload.get("standing_rule", "")
    assert "Dashboards and Web Apps and Services" in rule, (
        f"R536 /version must carry the R453 standing rule verbatim; "
        f"got {rule!r}"
    )
    # 2 read-only API verbs — write/read stay CLI-only per §17.
    assert set(payload.get("verbs", [])) == {"list", "state-files"}
    assert set(payload.get("cli_gated_verbs", [])) == {"write", "read"}, (
        f"/version must surface that write/read are CLI-gated; "
        f"got cli_gated_verbs={payload.get('cli_gated_verbs')}"
    )
    boundary = payload.get("sovereignty_boundary", "").lower()
    assert "§17" in payload.get("sovereignty_boundary", "") \
        or "section 17" in boundary, (
        "/version sovereignty_boundary must cite operator §17"
    )
    # The 4-state-fabric vocabulary is operator-named and load-bearing.
    state_files = set(payload.get("state_files", []))
    assert state_files == {
        "IDENTITY.md", "SOUL.md", "AGENTS.md", "CLAUDE.md"
    }, (
        f"/version state_files must enumerate master spec § 7.1 "
        f"vocabulary; got {sorted(state_files)}"
    )


def test_live_list_payload_shape():
    """/list MUST emit the LIVE 4-state-fabric inventory with present
    + size + mtime per row (mirrors `weaver list --json` exactly)."""
    with _DaemonHarness() as d:
        with d.fetch("/list") as r:
            assert r.status == 200
            payload = json.loads(r.read())
    assert "context_dir" in payload
    assert payload.get("count") == 4
    names = {row["name"] for row in payload["files"]}
    assert names == {
        "IDENTITY.md", "SOUL.md", "AGENTS.md", "CLAUDE.md"
    }
    for row in payload["files"]:
        assert "present" in row
        # Absent rows must still carry the keys (null-shaped).
        assert "size_bytes" in row
        assert "mtime_epoch" in row


def test_live_state_files_catalog_shape():
    """/state-files MUST emit the master spec § 7.1 static 4-state
    catalog independent of whether files exist (mirrors
    `weaver state-files --json` exactly)."""
    with _DaemonHarness() as d:
        with d.fetch("/state-files") as r:
            assert r.status == 200
            payload = json.loads(r.read())
    assert payload.get("count") == 4
    assert "master spec" in payload.get("spec_anchor", "").lower()
    ids = {row["id"] for row in payload["files"]}
    assert ids == {"IDENTITY.md", "SOUL.md", "AGENTS.md", "CLAUDE.md"}
    for row in payload["files"]:
        assert "id" in row
        assert "label" in row
        assert "master_spec_ref" in row
        assert "operator_named" in row


def test_live_webapp_alias_serves_html():
    with _DaemonHarness() as d:
        with d.fetch("/webapp/") as r:
            assert r.status == 200
            body = r.read().decode("utf-8")
            ct = r.headers.get("Content-Type", "")
    assert "text/html" in ct
    assert "<!DOCTYPE html>" in body or "<!doctype html>" in body.lower()
    assert "weaver-webapp" in body


def test_live_mutation_methods_rejected_with_405():
    """Operator §17 sovereignty: state-fabric writes stay CLI-gated.
    POST/PUT/DELETE/PATCH MUST all return 405 with a CLI-gated
    remediation message."""
    with _DaemonHarness() as d:
        for method in ("POST", "PUT", "DELETE", "PATCH"):
            try:
                d.fetch("/list", method=method)
                raise AssertionError(
                    f"{method} /list must 405 (got 2xx)"
                )
            except urllib.error.HTTPError as e:
                assert e.code == 405, (
                    f"{method} expected 405; got {e.code}"
                )
                body = e.read().decode("utf-8")
                low = body.lower()
                assert "read-only" in low
                # The remediation must point at the CLI.
                assert "cli" in low, (
                    f"{method} 405 body must point at the CLI as "
                    f"the remediation surface; got: {body[:200]}"
                )
                assert "weaver write" in low or "write" in low, (
                    f"{method} 405 body must name the gated verb"
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

def test_api_importlib_loads_atomic_state_core():
    """The daemon MUST reuse atomic-state.py's STATE_FILES + CONTEXT_DIR
    — no drift between CLI / TUI / MCP / API surfaces."""
    spec = importlib.util.spec_from_file_location("_r536", API_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod._CORE_PATH.name == "atomic-state.py", (
        "R536 daemon must importlib-load atomic-state.py"
    )
    assert hasattr(mod._core, "STATE_FILES")
    assert hasattr(mod._core, "CONTEXT_DIR")
    assert hasattr(mod._core, "commit_state_atomically")
    assert len(mod._core.STATE_FILES) == 4


# ----------------------------------------------------- surface-map post-

def test_surface_map_weaver_at_structural_ceiling():
    """R536 closes the weaver surface ladder — surface-map MUST
    report the weaver entry at at_structural_ceiling=True with 0
    FUTURE waivers AND 0 structural waivers (service waiver was
    promoted to a real daemon)."""
    result = subprocess.run(
        ["python3", str(SURFACE_MAP), "coverage", "--module",
         "weaver", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr[:300]
    data = json.loads(result.stdout)
    entries = data.get("coverage", [data])
    entry = entries[0] if entries else {}
    assert entry.get("surface_count", 0) == 8, (
        f"weaver must be at 8 surfaces post-R536; got {entry}"
    )
    assert entry.get("at_structural_ceiling") is True, (
        f"weaver must be at_structural_ceiling=True post-R536; "
        f"got {entry}"
    )
    assert entry.get("future_waiver_count", 0) == 0, (
        f"weaver must have 0 FUTURE waivers post-R536; got {entry}"
    )
    matrix = entry.get("matrix", [])
    for surface in ("api", "service", "webapp"):
        row = next(
            (r for r in matrix if r.get("surface") == surface), None
        )
        assert row is not None, (
            f"weaver matrix missing {surface!r} row"
        )
        assert row.get("state") == "shipped", (
            f"weaver {surface} must be shipped post-R536; got {row}"
        )


def test_dashboards_readme_documents_r536_metric():
    """The metric registry MUST list the R536 metric — operator-§1g
    visibility rule for the observability ladder."""
    text = DASH_README.read_text()
    assert (
        "sovereign_os_operator_weaver_api_request_total" in text
    )
    assert "R536" in text
