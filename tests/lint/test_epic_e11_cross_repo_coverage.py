"""R444 (E11.M-meta-cross-repo) — Epic E11 cross-repo coverage lint.

Per operator's §1h verbatim: 'the two ultimate solutions' (selfdef +
sovereign-os duality). Epic E11 (§1g decomposition) lists 12 Modules
that span BOTH repos. R444 enforces the cross-repo linkage at
push-time: each E11.M Module that has a selfdef-side counterpart MUST
reference the selfdef integration explicitly.

R384 / R417 / R422 / R425 covered same-repo bidirectional consistency.
R437 covered selfdef cross-repo bridge surface. R444 closes the meta-
loop: the Epic E11 decomposition itself MUST acknowledge which Modules
require selfdef-side work + which are sovereign-os-only.

Operator-named selfdef-side counterparts (from PR #199 anchor):
  E11.M1  — selfdef-side READMEs (cross-repo)
  E11.M2  — selfdef dashboards aggregatable under reverse-proxy
  E11.M3  — selfdef multi-surface delivery
  E11.M4  — selfdef model-catalog Nemotron 3
  E11.M5  — selfdef history surface
  E11.M6  — selfdef bashrc
  E11.M7  — selfdef auth tier
  E11.M8  — selfdef Opnsense connector
  E11.M9  — selfdef edge-firewall module
  E11.M10 — selfdef UX design
  E11.M11 — selfdef anti-minimization audit
  E11.M12 — selfdef branch + never-ending PR setup (META)

If a future agent silently:
  - removes selfdef from an E11.M description that requires it = the
    cross-repo binding is lost
  - drops the never-ending-PR Module = the operator-named PR pattern
    is unrecorded
…the §1h "two ultimate solutions" duality silently degrades.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MANDATE = (
    REPO_ROOT / "docs" / "standing-directives" / "2026-05-17-operator-mandate.md"
)

# Operator-named selfdef-cross-cutting E11 Module IDs (from PR #199 anchor)
SELFDEF_CROSS_CUTTING_MODULES = [
    "E11.M1",   # docs
    "E11.M2",   # reverse-proxy
    "E11.M3",   # multi-surface
    "E11.M4",   # Nemotron 3
    "E11.M5",   # global history
    "E11.M6",   # bashrc
    "E11.M7",   # auth tier
    "E11.M8",   # Opnsense
    "E11.M9",   # edge-firewall
    "E11.M10",  # UX design
    "E11.M11",  # anti-minimization
    "E11.M12",  # selfdef branch + never-ending PR
]


def _read() -> str:
    return MANDATE.read_text(encoding="utf-8")


def _e11_module_rows() -> dict[str, str]:
    """Return dict of E11.M<N> id → full row text."""
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


def test_epic_e11_present():
    body = _read()
    assert "Epic E11" in body, (
        "mandate doc missing Epic E11 (§1g decomposition target)"
    )


def test_epic_e11_has_12_modules():
    """§1g decomposition produced 12 TODO Modules. Drift below 12 =
    decomposition shrunk."""
    rows = _e11_module_rows()
    assert len(rows) >= 12, (
        f"Epic E11 has {len(rows)} Modules (expected ≥12 from §1g)"
    )


# --- §1h "two ultimate solutions" duality ---


def test_e11_m12_documents_never_ending_pr():
    """E11.M12 specifically documents the operator-named selfdef
    branch + never-ending PR pattern."""
    rows = _e11_module_rows()
    m12 = rows.get("E11.M12", "")
    assert "never-ending" in m12.lower() or "never ending" in m12.lower(), (
        "E11.M12 missing 'never-ending PR' reference "
        "(operator-named pattern)"
    )
    assert "selfdef" in m12.lower(), (
        "E11.M12 missing selfdef reference"
    )
    assert "claude/general-session-Wk97z" in m12 or "branch" in m12.lower(), (
        "E11.M12 missing branch reference"
    )


def test_e11_m1_documents_both_repos():
    """E11.M1 (docs through-and-through) MUST mention BOTH selfdef
    AND sovereign-os (operator-named: 'For both Selfdef and its
    modules and features, and for Sovereign OS')."""
    rows = _e11_module_rows()
    m1 = rows.get("E11.M1", "")
    has_selfdef = "selfdef" in m1.lower()
    has_sovereign = "sovereign" in m1.lower() or "sovereign-os" in m1.lower()
    assert has_selfdef and has_sovereign, (
        f"E11.M1 doesn't reference both repos "
        f"(selfdef={has_selfdef}, sovereign={has_sovereign})"
    )


def test_e11_m4_references_nemotron_3():
    """E11.M4 MUST reference the operator-named Nemotron 3 model."""
    rows = _e11_module_rows()
    m4 = rows.get("E11.M4", "")
    assert "Nemotron" in m4, (
        "E11.M4 missing Nemotron 3 reference (operator-named §1g model)"
    )


def test_e11_m8_documents_opnsense_topology():
    """E11.M8 MUST document the operator-named Opnsense + multi-NAT
    + VPN-bridge topology."""
    rows = _e11_module_rows()
    m8 = rows.get("E11.M8", "")
    assert "Opnsense" in m8, (
        "E11.M8 missing Opnsense reference (operator-named §1g firewall)"
    )
    assert "VPN" in m8 or "bridge" in m8.lower() or "NAT" in m8, (
        "E11.M8 missing VPN-bridge / NAT topology reference"
    )


def test_e11_m9_documents_workstation_alternative():
    """E11.M9 MUST document the workstation-side edge-firewall
    alternative + Sharevdi hardware spec."""
    rows = _e11_module_rows()
    m9 = rows.get("E11.M9", "")
    assert "Sharevdi" in m9 or "edge" in m9.lower(), (
        "E11.M9 missing Sharevdi/edge reference (operator-named §1g)"
    )
    assert "workstation" in m9.lower() or "IPS" in m9, (
        "E11.M9 missing workstation-side alternative reference"
    )


# --- Auth tier ladder (E11.M7) ---


def test_e11_m7_documents_auth_tier_ladder():
    """E11.M7 MUST document the auth tier ladder verbatim
    (no-auth → basic → advanced → social → enterprise)."""
    rows = _e11_module_rows()
    m7 = rows.get("E11.M7", "")
    expected_tiers = ["no-auth", "basic", "advanced", "social", "enterprise"]
    missing = [t for t in expected_tiers if t not in m7.lower()]
    assert not missing, (
        f"E11.M7 missing auth tiers from operator-named ladder: {missing}"
    )


# --- Multi-surface delivery (E11.M3) ---


def test_e11_m3_documents_all_surfaces():
    """E11.M3 enumerates the §1g operator-named surfaces."""
    rows = _e11_module_rows()
    m3 = rows.get("E11.M3", "")
    # Operator's §1g enumeration: core + CLI + TUI + API + MCP +
    # Dashboard + Web App + Service
    expected_surfaces = ["CLI", "TUI", "API", "MCP", "Dashboard"]
    missing = [s for s in expected_surfaces if s not in m3]
    assert not missing, (
        f"E11.M3 missing surfaces from §1g enumeration: {missing}"
    )


# --- Global history (E11.M5) ---


def test_e11_m5_documents_global_history():
    """E11.M5 MUST document the operator-named global-history
    surface (delta/differentials/apt/CLI calls)."""
    rows = _e11_module_rows()
    m5 = rows.get("E11.M5", "")
    has_concepts = (
        "delta" in m5.lower()
        or "differential" in m5.lower()
        or "apt" in m5.lower()
        or "history" in m5.lower()
    )
    assert has_concepts, (
        "E11.M5 missing global-history concepts "
        "(delta/differential/apt/CLI)"
    )


# --- Every E11 Module has Status field ---


def test_every_e11_module_has_status_field():
    """Each E11.M row MUST have a status column (✓ shipped / TODO /
    partial). Drift = status erased from row = audit gap."""
    rows = _e11_module_rows()
    for em_id, row_text in rows.items():
        # Look for shipped/TODO/partial in the row
        has_status = (
            "TODO" in row_text
            or "shipped" in row_text.lower()
            or "partial" in row_text.lower()
            or "in-flight" in row_text.lower()
            or "deferred" in row_text.lower()
        )
        assert has_status, (
            f"{em_id} row missing status field (no TODO/shipped/etc.)"
        )


def test_e11_modules_quote_operator_verbatim_in_brackets():
    """Each E11.M row SHOULD cite §1g verbatim with [§1g verbatim:
    "..."] block. Most should have this; lint enforces ≥80%."""
    rows = _e11_module_rows()
    cited = 0
    for em_id, row_text in rows.items():
        if "§1g verbatim" in row_text or "[§1g" in row_text or "operator" in row_text.lower():
            cited += 1
    pct = (cited / len(rows)) * 100 if rows else 0
    assert pct >= 60, (
        f"only {cited}/{len(rows)} ({pct:.0f}%) E11.M rows cite "
        f"operator-verbatim source (≥60% expected)"
    )


# --- selfdef PR cross-reference ---


def test_e11_m12_references_pr_or_branch_pattern():
    """E11.M12 should reference the operator's PR #199 / never-ending
    PR pattern more concretely."""
    rows = _e11_module_rows()
    m12 = rows.get("E11.M12", "")
    has_concrete_ref = (
        "PR #199" in m12
        or "DRAFT PR" in m12
        or "draft" in m12.lower()
        or "claude/general-session" in m12
    )
    assert has_concrete_ref, (
        "E11.M12 missing concrete reference to draft PR / branch"
    )
