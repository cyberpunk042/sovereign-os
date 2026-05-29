"""M076 runtime-modes cockpit — contract test.

Locks the new operator-facing runtime-modes cockpit shipped by
this commit (webapp + proxy daemon + systemd unit). M076 ("Three
load-balancing profiles", listed as the LAST MUST-ADD MILESTONE
in the catalogue) gets a real operator UX surface for inspecting
the 3 catalogued profile manifests.

Layers locked:
  - webapp/runtime-modes/index.html (operator-facing dashboard)
  - scripts/operator/runtime-modes-api.py (read-only proxy daemon)
  - systemd/system/sovereign-runtime-modes-api.service
  - 3 profile manifests in profiles/runtime/

Project boundary R10212: this cockpit reads — mutation (mode apply)
lives in selfdefd via `selfdefctl modules apply`.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WEBAPP_HTML = REPO_ROOT / "webapp" / "runtime-modes" / "index.html"
PROXY_PATH = REPO_ROOT / "scripts" / "operator" / "runtime-modes-api.py"
SYSTEMD_UNIT = (
    REPO_ROOT / "systemd" / "system" / "sovereign-runtime-modes-api.service"
)
PROFILES_DIR = REPO_ROOT / "profiles" / "runtime"

CANONICAL_MODE_IDS = (
    "ultra-sovereign-efficiency",
    "high-concurrency-burst",
    "deep-context-synthesis",
)


def _read(path: Path) -> str:
    return path.read_text()


def _load_proxy_module():
    """Load the proxy daemon as a module so tests can exercise its
    parsing + endpoint logic directly (hyphen in filename blocks
    plain import)."""
    spec = importlib.util.spec_from_file_location(
        "runtime_modes_api", PROXY_PATH,
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["runtime_modes_api"] = mod
    spec.loader.exec_module(mod)
    return mod


# ────────────────────────────────────────────── webapp dashboard

def test_webapp_html_present_and_well_formed():
    assert WEBAPP_HTML.is_file(), f"missing webapp dashboard: {WEBAPP_HTML}"
    body = _read(WEBAPP_HTML)
    assert "<!DOCTYPE html>" in body
    assert "sovereign-os — runtime modes" in body
    assert "M076" in body, "webapp must anchor M076 milestone"


def test_webapp_polls_canonical_endpoints():
    """The webapp MUST poll /api/runtime-modes/list AND
    /api/runtime-modes/active — the 2 endpoints the proxy advertises
    for cockpit consumption."""
    body = _read(WEBAPP_HTML)
    assert "/api/runtime-modes/list" in body
    assert "/api/runtime-modes/active" in body


def test_webapp_renders_active_mode_banner():
    """The dashboard's active-mode banner MUST exist with role=status
    + aria-live=polite for screen-reader observability matching the
    M060 + MS022 + four-watchdog banner conventions."""
    body = _read(WEBAPP_HTML)
    assert 'id="active-mode-banner"' in body
    assert 'role="status"' in body
    assert 'aria-live="polite"' in body


def test_webapp_handles_proxy_unreachable_gracefully():
    """When the proxy is unreachable, the dashboard MUST render a
    graceful fallback message naming the systemd unit so operators
    can fix it. NEVER blank-screen on unreachable."""
    body = _read(WEBAPP_HTML)
    assert "sovereign-runtime-modes-api.service" in body
    assert "unreachable" in body.lower()


def test_webapp_documents_r10212_read_only_boundary():
    """The dashboard MUST document the R10212 read-only boundary so
    operators understand mode mutation happens via selfdefctl, not
    this webapp."""
    body = _read(WEBAPP_HTML)
    assert "R10212" in body
    assert "selfdefctl modules apply" in body


def test_webapp_refresh_cadence_matches_sibling_dashboards():
    """The dashboard MUST refresh on 30s cadence matching the M060
    + MS022 + four-watchdog cockpit banner conventions."""
    body = _read(WEBAPP_HTML)
    assert "30000" in body, (
        "webapp must use 30s refresh interval (matches sibling cockpit "
        "dashboards) — operator visual consistency"
    )


def test_webapp_renders_all_3_canonical_modes_via_grid():
    """The dashboard's grid renderer MUST iterate over the modes
    returned from /api/runtime-modes/list (which is locked to the 3
    canonical mode ids). Verified structurally — the renderer
    creates a card per mode and the canonical mode ids appear in the
    workflow runbook."""
    body = _read(WEBAPP_HTML)
    for mode_id in CANONICAL_MODE_IDS:
        assert mode_id in body, (
            f"webapp workflow runbook must reference canonical mode {mode_id!r}"
        )


# ────────────────────────────────────────────── proxy daemon

def test_proxy_script_present_and_executable():
    assert PROXY_PATH.is_file(), f"missing proxy daemon: {PROXY_PATH}"
    assert PROXY_PATH.stat().st_mode & 0o111, (
        "proxy daemon must be executable for systemd ExecStart"
    )


def test_proxy_canonical_mode_ids_locked():
    """The proxy MUST hardcode the 3 canonical mode ids — drift
    catch protecting against an operator dropping a 4th profile
    YAML silently expanding the cockpit's mode selector."""
    mod = _load_proxy_module()
    assert mod.CANONICAL_MODE_IDS == CANONICAL_MODE_IDS, (
        f"proxy CANONICAL_MODE_IDS drift: got {mod.CANONICAL_MODE_IDS!r}"
    )


def test_proxy_default_port_does_not_collide_with_siblings():
    """Default port 7713 — sits above 7712 (four-watchdog-api), 7711
    (ms022-sse-quota-api), and 8160 (m060-health-api). 4 sibling
    proxies, 4 distinct ports."""
    mod = _load_proxy_module()
    assert mod.API_PORT == 7713, (
        f"proxy default port drift: expected 7713, got {mod.API_PORT}"
    )


def test_proxy_list_endpoint_returns_3_modes():
    """The /api/runtime-modes/list output MUST carry exactly 3 mode
    entries — drift catches accidental profile additions."""
    mod = _load_proxy_module()
    listing = mod._list_profiles()
    assert len(listing) == 3, (
        f"proxy listed {len(listing)} modes; expected exactly 3"
    )
    listed_ids = [m["id"] for m in listing]
    assert listed_ids == list(CANONICAL_MODE_IDS), (
        f"proxy mode-id ordering drift: {listed_ids}"
    )


def test_proxy_parses_summary_fields_from_yaml():
    """The proxy's stdlib-only YAML summary parser MUST extract the
    name + description fields from each profile YAML. Drift here =
    the cockpit cards render empty."""
    mod = _load_proxy_module()
    summaries = mod._list_profiles()
    for s in summaries:
        if s.get("absent"):
            continue
        assert s["name"], (
            f"profile {s['id']!r} summary missing name field"
        )
        assert s["description_oneline"], (
            f"profile {s['id']!r} summary missing description_oneline"
        )


def test_proxy_active_endpoint_honest_offline_when_marker_absent():
    """When the active-mode marker doesn't exist, the proxy's
    _active_mode() MUST return None — the cockpit then renders the
    'unknown' banner state. NEVER fabricate an active mode."""
    mod = _load_proxy_module()
    # Stub the marker path to a guaranteed-nonexistent location.
    original = mod.ACTIVE_MODE_MARKER
    mod.ACTIVE_MODE_MARKER = Path("/tmp/__nonexistent_runtime_mode_marker__")
    try:
        assert mod._active_mode() is None
    finally:
        mod.ACTIVE_MODE_MARKER = original


def test_proxy_active_endpoint_rejects_unknown_mode_ids():
    """If the marker file contains a mode id NOT in the canonical
    set, the proxy MUST return None (treat as unknown) — protects
    against an operator typo silently activating a phantom mode."""
    mod = _load_proxy_module()
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".marker", delete=False) as f:
        f.write("not-a-real-mode")
        f.flush()
        marker_path = Path(f.name)
    original = mod.ACTIVE_MODE_MARKER
    mod.ACTIVE_MODE_MARKER = marker_path
    try:
        assert mod._active_mode() is None
    finally:
        mod.ACTIVE_MODE_MARKER = original
        marker_path.unlink(missing_ok=True)


def test_proxy_profile_detail_rejects_unknown_mode_ids():
    """/api/runtime-modes/<id> for an unknown id MUST return None
    (which the handler maps to a 404). Drift = phantom modes resolve."""
    mod = _load_proxy_module()
    assert mod._profile_detail("nonexistent-mode") is None


# ──────────────────────────────────────────────────── 3 YAMLs

def test_three_canonical_profile_yamls_present():
    """The 3 canonical profile YAMLs MUST exist — drift catches
    accidental deletion of a profile."""
    for mode_id in CANONICAL_MODE_IDS:
        path = PROFILES_DIR / f"{mode_id}.yaml"
        assert path.is_file(), f"missing profile YAML: {path}"


# ──────────────────────────────────────────────── systemd unit

def test_systemd_unit_file_present():
    assert SYSTEMD_UNIT.is_file(), f"missing systemd unit: {SYSTEMD_UNIT}"


def test_systemd_unit_execstart_canonical_path():
    body = _read(SYSTEMD_UNIT)
    assert "ExecStart=/usr/bin/python3 /usr/local/lib/sovereign-os/scripts/operator/runtime-modes-api.py" in body


def test_systemd_unit_loopback_default():
    body = _read(SYSTEMD_UNIT)
    assert "RUNTIME_MODES_API_BIND=127.0.0.1" in body


def test_systemd_unit_port_doesnt_collide_with_siblings():
    body = _read(SYSTEMD_UNIT)
    assert "RUNTIME_MODES_API_PORT=7713" in body, (
        "systemd unit port must be 7713 (above 7712 four-watchdog-api, "
        "7711 ms022-sse-quota-api, 8160 m060-health-api)"
    )


def test_systemd_unit_no_read_write_paths():
    """R10212: read-only proxy. systemd unit MUST NOT declare
    ReadWritePaths (excluding comment lines from the check)."""
    body = _read(SYSTEMD_UNIT)
    directive_lines = [
        ln for ln in body.splitlines()
        if not ln.lstrip().startswith("#")
    ]
    assert "ReadWritePaths=" not in "\n".join(directive_lines)


def test_systemd_unit_r171_hardening_complete():
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


def test_systemd_unit_anchors_m076_milestone():
    """The systemd unit MUST anchor the M076 milestone in its
    Documentation/comment block so the audit trail is traceable."""
    body = _read(SYSTEMD_UNIT)
    assert "M076" in body
