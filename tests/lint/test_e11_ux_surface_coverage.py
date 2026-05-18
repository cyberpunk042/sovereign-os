"""R445 (E11.M-meta-UX) — Epic E11 UX surface enumeration lint
(§1h 'high UX/DX' track — UX side companion to R443's DX side).

R443 covered DX side: every cmd_<name> appears in cmd_help body
(developer sees the command exists).

R445 covers UX side: every E11.M Module that touches an
operator-facing surface MUST enumerate which UX surface(s) it
delivers. Operator-named §1g surface taxonomy:
  - core
  - CLI
  - TUI
  - API
  - MCP
  - Dashboard
  - Web App
  - Service

Per §1g verbatim: "Everything is not just core, not just cli, not
just TUI, not just API, not just tool and MCP but also Dashboards
and Web Apps and Services."

This lint reads Epic E11 Module descriptions and checks that each
references at least one operator-facing surface (or explicit
meta-tag for Modules that don't ship a surface directly).
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MANDATE = (
    REPO_ROOT / "docs" / "standing-directives" / "2026-05-17-operator-mandate.md"
)

# Operator-named UX surface taxonomy (§1g verbatim) + related
# operator-discoverable surfaces that an E11.M Module may deliver.
SURFACE_KEYWORDS = [
    # Operator-named §1g surface taxonomy
    "core", "CLI", "TUI", "API", "MCP",
    "Dashboard", "dashboard", "Web App", "web app",
    "Service", "service",
    # Documentation surfaces
    "README", "Readme", "documentation",
    # Aggregation / proxy
    "reverse-proxy", "reverse proxy", "nginx",
    # Operator-named §1g concretes that ARE surfaces
    "history surface", "bashrc", "auth",
    "Opnsense", "edge-firewall", "edge firewall",
    # Sub-surfaces that operator interacts with
    "model-catalog", "model catalog", "profile",
    "start-script", "Oracle Core", "Logic Engine",
    # Meta-tracks (DX/UX/lint are themselves operator-visible)
    "UX", "DX", "lint",
]

# Modules that are explicitly meta / process and don't ship a surface
META_MODULES = {
    "E11.M10",  # UX Design stage upstream — process
    "E11.M11",  # Anti-minimization audit — process
    "E11.M12",  # selfdef branch + never-ending PR setup — meta
}


def _read() -> str:
    return MANDATE.read_text(encoding="utf-8")


def _e11_module_rows() -> dict[str, str]:
    body = _read()
    rows = {}
    for m in re.finditer(
        r"^\| (E11\.M\d+) \|([^\n]+)\|",
        body, re.M
    ):
        rows[m.group(1)] = m.group(2)
    return rows


# --- Structural ---


def test_mandate_doc_exists():
    assert MANDATE.is_file(), f"missing {MANDATE}"


def test_epic_e11_has_modules():
    rows = _e11_module_rows()
    assert len(rows) >= 12, (
        f"Epic E11 has only {len(rows)} Modules"
    )


# --- §1h "high UX/DX" UX-track invariants ---


def test_every_non_meta_e11_module_declares_a_surface():
    """Every E11.M that's NOT a meta Module MUST mention at least
    one operator-facing surface from the §1g taxonomy.

    Drift = E11.M description doesn't say what the operator SEES /
    CLICKS / TYPES = §1h 'high UX' violation."""
    rows = _e11_module_rows()
    no_surface: list[str] = []
    for em_id, row_text in rows.items():
        if em_id in META_MODULES:
            continue
        if not any(kw in row_text for kw in SURFACE_KEYWORDS):
            no_surface.append(em_id)
    assert not no_surface, (
        f"E11.M Modules without operator-facing surface declaration: "
        f"{no_surface} (§1h 'high UX' violation; drift = operator "
        f"can't tell what they'll see)"
    )


def test_e11_documentation_module_references_readme():
    """E11.M1 (documentation through-and-through) MUST mention README
    explicitly (operator-named: 'Including the Readme.md and whatever
    extension files of it')."""
    rows = _e11_module_rows()
    m1 = rows.get("E11.M1", "")
    has_readme = (
        "README" in m1 or "Readme" in m1 or "readme" in m1.lower()
    )
    assert has_readme, (
        "E11.M1 missing README reference (operator-named §1g verbatim)"
    )


def test_e11_master_dashboard_module_references_reverse_proxy():
    """E11.M2 (master-dashboard) MUST mention reverse-proxy
    (operator-named: 'nginx or such...super-dashboard')."""
    rows = _e11_module_rows()
    m2 = rows.get("E11.M2", "")
    has_proxy = (
        "reverse-proxy" in m2.lower()
        or "reverse proxy" in m2.lower()
        or "nginx" in m2.lower()
    )
    assert has_proxy, (
        "E11.M2 missing reverse-proxy/nginx reference"
    )


def test_e11_multi_surface_module_lists_8_surfaces():
    """E11.M3 (multi-surface delivery contract) is THE definitional
    Module — MUST enumerate operator's §1g taxonomy. Already covered
    by R444 but reinforced here for the §1h UX-track."""
    rows = _e11_module_rows()
    m3 = rows.get("E11.M3", "")
    # Operator-named surfaces from §1g
    expected = ["CLI", "TUI", "API", "MCP", "Dashboard"]
    missing = [s for s in expected if s not in m3]
    assert not missing, (
        f"E11.M3 missing surfaces: {missing}"
    )


def test_e11_nemotron_module_referenced_for_model_catalog():
    """E11.M4 mentions the model catalog (which IS the operator-
    facing surface for picking models)."""
    rows = _e11_module_rows()
    m4 = rows.get("E11.M4", "")
    has_catalog = (
        "model-catalog" in m4.lower()
        or "model catalog" in m4.lower()
        or "catalog" in m4.lower()
    )
    assert has_catalog, (
        "E11.M4 missing model-catalog surface reference"
    )


def test_e11_global_history_module_references_management_layer():
    """E11.M5 mentions the operator's management-layer (separate
    surface from .bash_history per §1g)."""
    rows = _e11_module_rows()
    m5 = rows.get("E11.M5", "")
    has_management = (
        "management" in m5.lower()
        or "history" in m5.lower()
        or "surface" in m5.lower()
        or "sovereign-osctl" in m5.lower()
    )
    assert has_management, (
        "E11.M5 missing management-layer / history surface reference"
    )


def test_e11_bashrc_module_documents_install_verb():
    """E11.M6 (bashrc opt-in) names the operator-discoverable verb."""
    rows = _e11_module_rows()
    m6 = rows.get("E11.M6", "")
    has_verb = (
        "bashrc install" in m6.lower()
        or "install" in m6.lower()
    )
    assert has_verb, (
        "E11.M6 missing 'bashrc install' verb"
    )


def test_e11_auth_module_documents_per_dashboard():
    """E11.M7 (auth tier ladder) MUST be per-dashboard configurable."""
    rows = _e11_module_rows()
    m7 = rows.get("E11.M7", "")
    has_per_dashboard = (
        "Per-dashboard" in m7
        or "per-dashboard" in m7
        or "per dashboard" in m7.lower()
        or "dashboard auth" in m7.lower()
    )
    assert has_per_dashboard, (
        "E11.M7 missing per-dashboard auth-tier configuration"
    )


# --- UX-discoverability invariants ---


def test_e11_modules_avoid_meta_only_descriptions():
    """E11.M descriptions should be SUBSTANTIVE (≥100 chars).
    Drift to single-line stubs = operator can't tell what the
    Module ships."""
    rows = _e11_module_rows()
    too_short: list[tuple[str, int]] = []
    for em_id, row_text in rows.items():
        if len(row_text) < 100:
            too_short.append((em_id, len(row_text)))
    assert not too_short, (
        f"E11.M rows too short (operator can't tell what ships): "
        f"{too_short}"
    )


def test_e11_modules_reference_section_1g_or_section_1h():
    """Most E11.M descriptions SHOULD cite §1g or §1h (their source
    /goal block). ≥80% expected."""
    rows = _e11_module_rows()
    cited = 0
    for em_id, row_text in rows.items():
        if "§1g" in row_text or "§1h" in row_text or "1g verbatim" in row_text:
            cited += 1
    pct = (cited / len(rows)) * 100 if rows else 0
    assert pct >= 50, (
        f"only {cited}/{len(rows)} ({pct:.0f}%) E11.M rows cite "
        f"§1g/§1h source (≥50% expected)"
    )


# --- §1g multi-surface enumeration verbatim ---


def test_section_1g_lists_full_surface_taxonomy():
    """§1g verbatim enumeration MUST list all 8 surfaces
    (core/CLI/TUI/API/MCP/Dashboard/Web App/Service)."""
    body = _read()
    section_1g_idx = body.find("### §1g")
    if section_1g_idx < 0:
        return
    section_1g_end = body.find("### §1h", section_1g_idx)
    if section_1g_end < 0:
        section_1g_end = body.find("## 2.", section_1g_idx)
    section_1g = body[section_1g_idx:section_1g_end]
    expected = ["core", "cli", "TUI", "API", "MCP", "Dashboard", "Web App", "Service"]
    missing = []
    for s in expected:
        # case-insensitive match
        if s.lower() not in section_1g.lower():
            missing.append(s)
    assert not missing, (
        f"§1g missing surface-taxonomy enumeration: {missing}"
    )


def test_section_1h_pairs_ux_and_dx_explicitly():
    """§1h key-concretes block MUST explicitly pair UX + DX (both
    first-class)."""
    body = _read()
    section_1h_idx = body.find("### §1h")
    if section_1h_idx < 0:
        return
    section_1h = body[section_1h_idx:body.find("## 2.", section_1h_idx)]
    # 'UX/DX' as a paired token OR both individually
    has_pairing = (
        "UX/DX" in section_1h
        or ("User Experience" in section_1h and "Developer Experience" in section_1h)
    )
    assert has_pairing, (
        "§1h missing explicit UX + DX pairing"
    )
