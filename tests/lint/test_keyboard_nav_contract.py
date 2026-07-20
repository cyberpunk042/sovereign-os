"""M060 R10055 + R10058-R10105 — keyboard-nav apply-snippet contract.

The operator's standing direction catalogues a coherent keyboard-nav
contract:

  R10055 — D-00 main keyboard shortcut palette (Cmd-K / Ctrl-K opens)
  R10058 — D-00 main accessible via Cmd-1 / Ctrl-1
  R10062 — D-01 active sessions accessible via Cmd-2 / Ctrl-2
  R10068 — D-02 profile choices accessible via Cmd-3 / Ctrl-3
  R10074 — D-03 model health accessible via Cmd-4 / Ctrl-4
  R10082 — D-04 costs accessible via Cmd-5 / Ctrl-5
  R10087 — D-05 traces accessible via Cmd-6 / Ctrl-6
  R10092 — D-06 pending approvals accessible via Cmd-7 / Ctrl-7
  R10096 — D-07 memory changes accessible via Cmd-8 / Ctrl-8
  R10101 — D-08 rollback points accessible via Cmd-9 / Ctrl-9
  R10105 — D-09 hardware pressure accessible via Cmd-0 / Ctrl-0

Universal contract: EVERY cockpit webapp embeds the same canonical
nav-snippet so the keyboard shortcuts work coherently regardless of
which dashboard the operator is currently viewing. The palette
(Cmd-K) provides searchable access to D-10..D-20 + the orthogonal
personalization page.

Per "Respect the projects": navigation is CLIENT-SIDE only — the
snippet uses window.location.href, never a server mutation.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
NAV_SHARED = REPO_ROOT / "webapp" / "_shared" / "nav-snippet.html"

# Every D-NN + the 2 D-12 split webapps + personalization + master.
# Kept in lockstep with test_personalization_contract.py ADOPTED_DASHBOARDS
# (personalization page itself is nav-adopted but not pers-adopted).
ADOPTED_NAV_DASHBOARDS = [
    "master-dashboard",
    # D-01..D-11 (sovereign-os-native D-NN dashboards):
    "d-01-active-sessions",
    "d-02-profile-choices",
    "d-03-model-health",
    "d-04-costs",
    "d-05-traces",
    "d-06-pending-approvals",
    "d-07-memory-changes",
    "d-08-rollback-points",
    "d-09-hardware-pressure",
    "d-10-eval-history",
    "d-11-adapter-status",
    # D-12 split-pattern (network-edge + edge-firewall together
    # serve the D-12 networking cockpit per M060 R10112-R10113):
    "network-edge",
    "edge-firewall",
    "d-12-networking",
    # M060 cross-repo mirror dashboards (6):
    "d-13-filesystem-grants",
    "d-14-capability-tokens",
    "d-15-sandboxes",
    "d-16-audit",
    "d-17-quarantine",
    "d-18-trust-scores",
    # D-19..D-29 (remaining D-NN dashboards):
    "d-19-super-model-manifest",
    "d-20-peace-machine-health",
    "d-21-lm-orchestration",
    "d-22-lm-status-operability",
    "d-23-models-catalog",
    "d-24-cpu-features",
    "d-25-selfdef-management",
    "d-26-friction-audit",
    "d-27-guardian",
    "d-28-perimeter",
    "d-29-scheduler",
    # Orthogonal cockpit webapps (operator-facing):
    "auditor",
    "ux-design-audit",
    "anti-minimization-audit",
    "compliance",
    "global-history",
    "surface-map",
    "router",
    "doc-coverage",
    "weaver",
    "trinity",
    "auth-tier",
    "build-configurator",
    "code-console",
    # The personalization control surface itself (has nav, not pers):
    "personalization",
]

# Catalog-mandated Cmd-N → D-NN mapping.
SHORTCUT_MAP = {
    "1": "master-dashboard",       # R10058
    "2": "d-01-active-sessions",   # R10062
    "3": "d-02-profile-choices",   # R10068
    "4": "d-03-model-health",      # R10074
    "5": "d-04-costs",             # R10082
    "6": "d-05-traces",            # R10087
    "7": "d-06-pending-approvals", # R10092
    "8": "d-07-memory-changes",    # R10096
    "9": "d-08-rollback-points",   # R10101
    "0": "d-09-hardware-pressure", # R10105
}


def test_shared_nav_snippet_documentation_exists():
    """The canonical nav-snippet source MUST live at
    webapp/_shared/nav-snippet.html so future adopters can copy it
    verbatim and the contract test has a single source-of-truth."""
    assert NAV_SHARED.is_file(), f"canonical nav-snippet missing: {NAV_SHARED}"


def test_shared_nav_snippet_lists_full_dashboard_catalog():
    """The shared snippet's DASHBOARDS array MUST include every D-NN
    + the 2 D-12 split webapps + personalization (28 entries total)."""
    src = NAV_SHARED.read_text(encoding="utf-8")
    expected_ids = ["D-00", "D-01", "D-02", "D-03", "D-04", "D-05",
                    "D-06", "D-07", "D-08", "D-09", "D-10", "D-11",
                    "D-12a", "D-12b", "D-13", "D-14", "D-15", "D-16",
                    "D-17", "D-18", "D-19", "D-20", "D-21", "D-22",
                    "D-23", "D-24", "D-25", "D-26", "D-27", "D-28",
                    "D-29"]
    for did in expected_ids:
        assert "'" + did + "'" in src, f"DASHBOARDS array missing: {did}"


def test_shared_nav_snippet_maps_catalog_shortcuts():
    """The shared snippet's shortcut mapping MUST match R10058-R10105
    verbatim — Cmd-1..Cmd-9 + Cmd-0 → D-00..D-09 in catalog order."""
    src = NAV_SHARED.read_text(encoding="utf-8")
    for key, dir_name in SHORTCUT_MAP.items():
        # The DASHBOARDS array entry for this dir MUST carry the right
        # shortcut. We look for `dir: 'foo'` followed by the shortcut.
        idx = src.find("dir: '" + dir_name + "'")
        assert idx > 0, f"DASHBOARDS missing dir: {dir_name}"
        # Find the shortcut declaration in the same array row (look
        # forward up to 200 chars for `shortcut: 'N'`).
        row_tail = src[idx:idx + 300]
        expected = "shortcut: '" + key + "'"
        assert expected in row_tail, (
            f"DASHBOARDS row for {dir_name} must declare {expected}; got: {row_tail[:200]!r}"
        )


def test_all_adopted_dashboards_embed_canonical_snippet():
    """Every dashboard listed in ADOPTED_NAV_DASHBOARDS MUST embed
    the canonical nav-snippet (detected by the so-palette-backdrop
    marker class + the DASHBOARDS array)."""
    for slug in ADOPTED_NAV_DASHBOARDS:
        path = REPO_ROOT / "webapp" / slug / "index.html"
        assert path.is_file(), f"adopted dashboard missing: {path}"
        html = path.read_text(encoding="utf-8")
        assert "so-palette-backdrop" in html, (
            f"{slug}: nav-snippet missing so-palette-backdrop marker"
        )
        assert "M060 R10055" in html, (
            f"{slug}: nav-snippet must cite M060 R10055 catalog row"
        )
        # Each adopted dashboard must carry the catalog shortcut map
        # so direct Cmd-N navigation works (DASHBOARDS array present).
        assert "'D-00'" in html and "'D-09'" in html, (
            f"{slug}: nav-snippet must carry the D-00..D-09 shortcut catalog"
        )


def test_nav_snippet_uses_stop_immediate_propagation():
    """Universal nav handlers must stopImmediatePropagation so legacy
    per-dashboard Cmd-N handlers don't clobber the canonical jump."""
    src = NAV_SHARED.read_text(encoding="utf-8")
    assert "stopImmediatePropagation" in src, (
        "nav-snippet must call stopImmediatePropagation on its keydown "
        "handlers so legacy per-dashboard handlers don't override the "
        "catalog-mandated mapping"
    )


def test_nav_snippet_defers_when_on_target():
    """When the operator hits Cmd-N for the dashboard they're ALREADY
    on, the snippet must defer — that way each dashboard's local Cmd-N
    handler (e.g. d-05 Cmd-6 focuses search) keeps working."""
    src = NAV_SHARED.read_text(encoding="utf-8")
    assert "isOnDashboard" in src, (
        "nav-snippet must define isOnDashboard() guard"
    )
    assert "if (isOnDashboard(" in src, (
        "nav-snippet must call isOnDashboard() before jumping to skip self-jumps"
    )


def test_nav_snippet_text_input_guard():
    """Cmd-N must be suppressed when the operator is typing in
    <input>/<textarea>/[contenteditable] so they can type digits."""
    src = NAV_SHARED.read_text(encoding="utf-8")
    for token in ("'INPUT'", "'TEXTAREA'", "isContentEditable"):
        assert token in src, (
            f"nav-snippet must guard text inputs: missing {token}"
        )


def test_nav_snippet_is_client_side_only():
    """Navigation is CLIENT-SIDE only — uses window.location.href, no
    fetch/XHR mutation."""
    src = NAV_SHARED.read_text(encoding="utf-8")
    assert "window.location.href" in src, (
        "nav-snippet must use window.location.href for navigation"
    )
    # No server-mutation calls
    for forbidden in ("fetch(", "XMLHttpRequest", "method: 'POST'",
                      "method:'POST'", "method=\"POST\""):
        assert forbidden not in src, (
            f"nav-snippet must be client-side only; found: {forbidden!r}"
        )


def test_palette_aria_role_for_accessibility():
    """The palette overlay MUST carry role=dialog + aria-modal so
    screen readers announce it — operator-§1g accessibility."""
    src = NAV_SHARED.read_text(encoding="utf-8")
    assert "role" in src and "dialog" in src, (
        "nav-snippet palette must declare role=dialog for accessibility"
    )
    assert "aria-modal" in src, (
        "nav-snippet palette must declare aria-modal=true for accessibility"
    )


def test_adopted_count_matches_personalization_rollout():
    """Sanity invariant: every personalization-adopted dashboard also
    adopts nav (and vice-versa) so the two snippet rollouts stay in
    lock-step. Drift here means a dashboard was added to one rollout
    and forgotten in the other."""
    from tests.lint.test_personalization_contract import ADOPTED_DASHBOARDS as PERS
    # nav adds 'personalization' (which IS the personalization page itself,
    # so isn't in PERS); strip it for comparison.
    nav_set = set(ADOPTED_NAV_DASHBOARDS) - {"personalization"}
    pers_set = set(PERS)
    missing_nav = pers_set - nav_set
    missing_pers = nav_set - pers_set
    assert not missing_nav, (
        f"Dashboards with personalization but no nav: {sorted(missing_nav)}"
    )
    assert not missing_pers, (
        f"Dashboards with nav but no personalization: {sorted(missing_pers)}"
    )
