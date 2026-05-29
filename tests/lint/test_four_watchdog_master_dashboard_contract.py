"""Four-watchdog master-dashboard banner — contract test.

Locks the master-dashboard banner DOM + CSS + render function +
proxy daemon + systemd unit shipped by this commit. Same shape
as the MS022 + M060 banners (test_master_dashboard_*) so drift in
the IPS-spine banner can't sneak in.

The banner consumes the JSON envelope from
`scripts/operator/four-watchdog-api.py` at `/api/four-watchdog/state`,
proxied via the sovereign-os webapp. The proxy daemon parses
node_exporter's /metrics for the 4 `selfdef_four_watchdog_*`
gauges (shipped at selfdef commits 7869a45 + a009b39).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MASTER_DASHBOARD = REPO_ROOT / "webapp" / "master-dashboard" / "index.html"
PROXY_PATH = REPO_ROOT / "scripts" / "operator" / "four-watchdog-api.py"
SYSTEMD_UNIT = (
    REPO_ROOT / "systemd" / "system" / "sovereign-four-watchdog-api.service"
)


def _read(path: Path) -> str:
    return path.read_text()


# ──────────────────────────────────────────── master-dashboard banner

def test_banner_dom_element_present():
    """The banner div MUST exist with the canonical id + classes."""
    body = _read(MASTER_DASHBOARD)
    assert 'id="four-watchdog-banner"' in body, (
        "master-dashboard missing four-watchdog banner DOM"
    )
    assert 'role="status"' in body and 'aria-live="polite"' in body, (
        "banner must declare role=status + aria-live=polite for "
        "screen-reader observability matching M060 + MS022 banners"
    )


def test_banner_dom_labels_present():
    """The banner MUST carry the 3 canonical label spans the render
    function writes into (label, detail, rollup)."""
    body = _read(MASTER_DASHBOARD)
    for id_ in (
        "four-watchdog-label",
        "four-watchdog-detail",
        "four-watchdog-rollup",
    ):
        assert f'id="{id_}"' in body, (
            f"banner missing label span id={id_!r}"
        )


def test_banner_links_to_grafana_dashboard():
    """The banner MUST deep-link to the Grafana dashboard (uid
    `sovereign-os-four-watchdog`) for operators to drill into the
    full panel set."""
    body = _read(MASTER_DASHBOARD)
    assert '/d/sovereign-os-four-watchdog' in body, (
        "banner must link to the Grafana dashboard /d/sovereign-os-four-watchdog"
    )


def test_banner_render_function_present_and_polls_canonical_endpoint():
    """The renderFourWatchdogBanner() function MUST exist AND fetch
    the canonical /api/four-watchdog/state endpoint."""
    body = _read(MASTER_DASHBOARD)
    assert "async function renderFourWatchdogBanner()" in body
    assert "/api/four-watchdog/state" in body


def test_banner_render_invoked_on_grid_refresh():
    """The render function MUST be called from renderM060Grid() so it
    refreshes on the same tick as the M060 + MS022 banners."""
    body = _read(MASTER_DASHBOARD)
    # Find renderM060Grid body, then search for the four-watchdog call
    # within it.
    grid_start = body.find("async function renderM060Grid()")
    assert grid_start != -1
    # Next sibling function as end-of-body marker.
    next_fn = body.find("\nasync function ", grid_start + 1)
    if next_fn == -1:
        next_fn = body.find("\nfunction ", grid_start + 1)
    grid_body = body[grid_start:next_fn if next_fn > 0 else len(body)]
    assert "renderFourWatchdogBanner()" in grid_body, (
        "renderM060Grid() must invoke renderFourWatchdogBanner() so "
        "the IPS-spine state refreshes on the master-grid tick"
    )


def test_banner_handles_all_canonical_states():
    """The banner CSS + render logic MUST cover all 6 canonical
    states the proxy daemon emits."""
    body = _read(MASTER_DASHBOARD)
    canonical_states = ["ok", "warn", "critical",
                        "observer-fault", "unreachable", "unknown"]
    # CSS classes present.
    for state in canonical_states:
        css_selector = f".four-watchdog-banner.{state}"
        assert css_selector in body, (
            f"banner CSS missing class selector for state {state!r}"
        )
    # JS knownStates list lock.
    m = re.search(
        r'const knownStates\s*=\s*\[\s*([^\]]+)\s*\];\s*\n[\s\S]{0,400}?'
        r'banner\.classList\.add',
        body,
    )
    # We need to find the four-watchdog-specific knownStates — there
    # are multiple knownStates in the file (MS022 has one too).
    # Search inside renderFourWatchdogBanner specifically.
    fn_start = body.find("async function renderFourWatchdogBanner()")
    next_fn = body.find("\nasync function ", fn_start + 1)
    if next_fn == -1:
        next_fn = body.find("\nfunction ", fn_start + 1)
    fn_body = body[fn_start:next_fn if next_fn > 0 else len(body)]
    for state in canonical_states:
        assert f'"{state}"' in fn_body, (
            f"renderFourWatchdogBanner knownStates missing state {state!r}"
        )


def test_banner_observer_fault_takes_precedence_documented():
    """The banner's render function comment MUST document the
    observer-fault precedence — drift here = operators confused
    when seeing observer-fault override a CRITICAL rollup."""
    body = _read(MASTER_DASHBOARD)
    fn_start = body.find("// Four-watchdog (IPS spine) banner")
    fn_end = body.find("async function renderFourWatchdogBanner()", fn_start)
    comment = body[fn_start:fn_end]
    assert "honest-offline" in comment.lower() or "observer-fault" in comment, (
        "banner render comment must document the honest-offline / "
        "observer-fault precedence"
    )


def test_banner_anchors_ips_spine_milestones_in_label():
    """The banner's ok-state detail line MUST anchor the 4 IPS-spine
    milestones so operators see the production-shipped milestone
    family the banner observes."""
    body = _read(MASTER_DASHBOARD)
    fn_start = body.find("async function renderFourWatchdogBanner()")
    next_fn = body.find("\nasync function ", fn_start + 1)
    fn_body = body[fn_start:next_fn if next_fn > 0 else len(body)]
    for ms in ("MS046", "MS047", "MS044", "MS048"):
        assert ms in fn_body, (
            f"banner render function ok-state detail must anchor {ms} "
            f"(IPS spine)"
        )


# ────────────────────────────────────────────────── proxy daemon

def test_proxy_daemon_script_present_and_executable():
    """The proxy daemon script MUST exist + be marked executable."""
    assert PROXY_PATH.is_file(), f"missing proxy daemon: {PROXY_PATH}"
    assert PROXY_PATH.stat().st_mode & 0o111, (
        "proxy daemon must be executable for systemd ExecStart to work"
    )


def test_proxy_default_port_does_not_collide_with_siblings():
    """The proxy MUST use port 7712 — sits above the existing
    sovereign-os api band (8160 m060-health-api, 7711 ms022-sse-quota-api)
    so the 3 proxies don't collide."""
    body = _read(PROXY_PATH)
    assert "7712" in body, (
        "proxy default port must be 7712 (above ms022's 7711)"
    )


def test_proxy_endpoints_match_banner_contract():
    """The proxy MUST advertise the canonical /api/four-watchdog/state
    endpoint the banner fetches."""
    body = _read(PROXY_PATH)
    assert "/api/four-watchdog/state" in body, (
        "proxy missing the /api/four-watchdog/state route"
    )
    for ep in ("/healthz", "/version"):
        assert ep in body, f"proxy missing the {ep} contract endpoint"


def test_proxy_classify_state_includes_observer_fault():
    """The proxy MUST classify into observer-fault when emit_failed > 0
    OR observer-age > 300 — the honest-offline contract that takes
    precedence over rollup-severity."""
    body = _read(PROXY_PATH)
    assert "observer-fault" in body, (
        "proxy must classify into observer-fault state"
    )
    assert "OBSERVER_SILENT_THRESHOLD_SECS = 300" in body, (
        "proxy must use 300s threshold matching the alert rule + "
        "M060 chain stale-age threshold"
    )


def test_proxy_severity_constants_locked():
    """The severity constants MUST match the canonical ladder
    {0=OK, 1=WARN, 2=CRITICAL, -1=UNKNOWN}."""
    body = _read(PROXY_PATH)
    for declaration in (
        "SEVERITY_OK = 0",
        "SEVERITY_WARN = 1",
        "SEVERITY_CRITICAL = 2",
        "SEVERITY_UNKNOWN = -1",
    ):
        assert declaration in body, (
            f"proxy severity constant drift: missing {declaration!r}"
        )


def test_proxy_handles_unreachable_node_exporter_gracefully():
    """The proxy MUST return state=unreachable when node_exporter
    is unreachable — never crashes, banner can render honestly."""
    body = _read(PROXY_PATH)
    assert 'state": "unreachable"' in body or "'state': 'unreachable'" in body, (
        "proxy must return state=unreachable when node_exporter is down"
    )
    assert "URLError" in body or "OSError" in body, (
        "proxy must catch URL/OS errors when fetching node_exporter /metrics"
    )


# ──────────────────────────────────────────────── systemd unit

def test_systemd_unit_file_present():
    assert SYSTEMD_UNIT.is_file(), f"missing systemd unit: {SYSTEMD_UNIT}"


def test_systemd_unit_execstart_canonical_path():
    body = _read(SYSTEMD_UNIT)
    assert "ExecStart=/usr/bin/python3 /usr/local/lib/sovereign-os/scripts/operator/four-watchdog-api.py" in body, (
        "systemd unit ExecStart path drift"
    )


def test_systemd_unit_loopback_default():
    body = _read(SYSTEMD_UNIT)
    assert "FOUR_WATCHDOG_API_BIND=127.0.0.1" in body, (
        "systemd unit must default to loopback bind matching sibling proxies"
    )


def test_systemd_unit_port_doesnt_collide_with_siblings():
    body = _read(SYSTEMD_UNIT)
    assert "FOUR_WATCHDOG_API_PORT=7712" in body, (
        "systemd unit port must be 7712 (matches proxy default)"
    )


def test_systemd_unit_no_read_write_paths():
    """R10212: the proxy is pure-read. systemd unit MUST NOT declare
    ReadWritePaths — drift would expose a mutation surface."""
    body = _read(SYSTEMD_UNIT)
    # Strip comment lines before checking — the comment block legitimately
    # explains WHY ReadWritePaths is omitted; only an actual directive
    # would be drift.
    directive_lines = [
        ln for ln in body.splitlines()
        if not ln.lstrip().startswith("#")
    ]
    directive_body = "\n".join(directive_lines)
    assert "ReadWritePaths=" not in directive_body, (
        "systemd unit must NOT declare ReadWritePaths — proxy is "
        "pure-read per R10212"
    )


def test_systemd_unit_r171_hardening_complete():
    """The systemd unit MUST carry the full R171 defense-in-depth
    hardening matching sibling proxy units."""
    body = _read(SYSTEMD_UNIT)
    for required in (
        "ProtectSystem=strict",
        "NoNewPrivileges=true",
        "RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6",
        "SystemCallFilter=@system-service",
        "SystemCallFilter=~@privileged @resources",
        "LockPersonality=true",
        "RestrictNamespaces=true",
    ):
        assert required in body, (
            f"systemd unit missing R171 hardening clause: {required!r}"
        )


def test_systemd_unit_install_section():
    body = _read(SYSTEMD_UNIT)
    assert "[Install]" in body
    assert "WantedBy=multi-user.target" in body
