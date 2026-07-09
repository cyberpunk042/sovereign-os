"""R441 (E11.M-meta) — operator-mandate § 1 subsection coverage lint.

Extends R436 (mandate doc meta-pinning) with content-level coverage:
the operator-mandate doc's § 1 has accumulated subsections §1.0 → §1g
as each /goal block lands. R441 makes that chain explicit + enforced.

When the operator pastes a new /goal block, § 1 MUST gain a new
subsection that records it verbatim. Drift = operator-paste shipped
without being recorded in the SACROSANCT § 1 = mandate corruption.

Operator-named § 1 subsections (in chronological order):
  §1.0 — Re-instate directive (2026-05-17)
  §1a  — Branch + PR + ultimate-OS posture (2026-05-17)
  §1b  — Multi-mode functioning + grey-out UX + REPL tiers (2026-05-17)
  §1c, §1d, §1e — Hardware-stack expansion (2026-05-17, three times)
  §1f  — full operator paste reproduced verbatim (2026-05-17)
  §1g  — Documentation + master-dashboard + global history + auth
         tiers + firewall/VPN-bridge topology (2026-05-18)

Each subsection MUST quote operator-verbatim and contain a blockquote
indicating "(operator paste-record session)" or equivalent attribution.

Future additions: §1h, §1i, ... follow the same shape.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MANDATE = (
    REPO_ROOT / "docs" / "standing-directives" / "2026-05-17-operator-mandate.md"
)

EXPECTED_SUBSECTIONS = ["§1.0", "§1a", "§1b", "§1f", "§1g", "§1h"]
# §1c/§1d/§1e are grouped under a single header in the current doc;
# allow that variant.


def _read() -> str:
    return MANDATE.read_text(encoding="utf-8")


# --- Structural ---


def test_mandate_doc_exists():
    assert MANDATE.is_file(), f"missing {MANDATE}"


def test_section_1_present():
    body = _read()
    assert "## 1." in body, "mandate doc missing § 1"


def test_at_least_5_subsections():
    """§1 has accumulated 5+ subsections. Drift below 5 = subsection
    deleted (anti-corruption § 6 violation)."""
    body = _read()
    # Match ### §1.X or ### §1<letter>
    subs = re.findall(r"^### §1[\.\w]+", body, re.M)
    assert len(subs) >= 5, (
        f"§ 1 has only {len(subs)} subsections (expected ≥5; "
        f"drift = operator-paste subsection deleted)"
    )


def test_each_expected_subsection_present():
    """Each operator-named subsection MUST be present (by anchor text)."""
    body = _read()
    for anchor in EXPECTED_SUBSECTIONS:
        assert anchor in body, (
            f"§ 1 missing subsection {anchor} (operator-paste not "
            f"recorded; mandate § 6 anti-corruption violation)"
        )


def test_section_1g_documents_2026_05_18():
    """§1g landed 2026-05-18 per its header; drift = wrong date."""
    body = _read()
    section_1g_idx = body.find("### §1g")
    if section_1g_idx < 0:
        return
    section_1g = body[section_1g_idx:section_1g_idx + 2000]
    assert "2026-05-18" in section_1g, (
        "§1g header missing 2026-05-18 date stamp"
    )


# --- §1g content invariants (operator-verbatim concretes) ---


def test_section_1g_contains_operator_verbatim_quote():
    body = _read()
    section_1g_idx = body.find("### §1g")
    if section_1g_idx < 0:
        return
    section_1g = body[section_1g_idx:body.find("## 2.", section_1g_idx)]
    # Operator-verbatim phrases (split into per-line fragments to
    # tolerate markdown blockquote line-wrap on the operator-verbatim
    # paste; each fragment is short enough to live on a single line)
    expected_phrases = [
        "very clear and well defined",  # split from "...documentation"
        "proxy nginx",         # tolerates "reverse\n> proxy nginx" wrap
        "master dashboard",
        "300+ modules",
        "Nemotron 3",
        "global history",
        "bashrc",
        "Opnsense",
        "Sharevdi",
        "i226-V",
    ]
    for phrase in expected_phrases:
        assert phrase in section_1g, (
            f"§1g missing operator-verbatim phrase {phrase!r}"
        )


def test_section_1g_documents_hardware_specs():
    """§1g operator paste names specific hardware (Sharevdi mini PC
    spec). MUST be preserved exactly."""
    body = _read()
    section_1g_idx = body.find("### §1g")
    if section_1g_idx < 0:
        return
    section_1g = body[section_1g_idx:body.find("## 2.", section_1g_idx)]
    # Sharevdi PSU spec
    assert "J3710" in section_1g or "N3710" in section_1g, (
        "§1g missing Sharevdi Mini PC CPU (J3710/N3710 — operator-named)"
    )
    assert "2.5GbE" in section_1g, (
        "§1g missing 2.5GbE NIC spec (operator-named)"
    )


def test_section_1g_documents_auth_tier_ladder():
    body = _read()
    section_1g_idx = body.find("### §1g")
    if section_1g_idx < 0:
        return
    section_1g = body[section_1g_idx:body.find("## 2.", section_1g_idx)]
    # Operator-named auth tiers
    expected_tiers = ["no auth", "basic auth", "advanced auth",
                       "social auth", "enterprise auth"]
    missing = [t for t in expected_tiers if t.lower() not in section_1g.lower()]
    assert not missing, (
        f"§1g auth tier ladder missing tiers: {missing}"
    )


def test_section_1g_documents_multi_surface_delivery():
    body = _read()
    section_1g_idx = body.find("### §1g")
    if section_1g_idx < 0:
        return
    section_1g = body[section_1g_idx:body.find("## 2.", section_1g_idx)]
    # Operator-named surfaces
    for surface in ("CLI", "TUI", "API", "MCP", "Dashboard",
                    "Web App", "Service"):
        assert surface in section_1g, (
            f"§1g missing multi-surface mention of {surface!r}"
        )


# --- Cross-reference to Epic E11 ---


def test_epic_e11_section_present():
    """§1g decomposition lands in Epic E11. Drift = decomposition lost."""
    body = _read()
    has_e11 = (
        "### Epic E11" in body
        or "Epic E11" in body
    )
    assert has_e11, (
        "mandate doc missing Epic E11 (§1g decomposition target)"
    )


def test_e11_has_at_least_10_modules():
    """E11 should have ≥10 TODO Modules from §1g decomposition.
    Drift below 10 = decomposition shrunk."""
    body = _read()
    e11_rows = re.findall(r"^\| E11\.M\d+ \|", body, re.M)
    assert len(e11_rows) >= 10, (
        f"Epic E11 has only {len(e11_rows)} Modules "
        f"(expected ≥10 from §1g decomposition)"
    )


def test_e11_modules_well_formed():
    """E11.M ids match E11.M<N> pattern."""
    body = _read()
    e11_ids = re.findall(r"\| (E11\.M\d+) \|", body)
    pattern = re.compile(r"^E11\.M\d+$")
    for em in e11_ids:
        assert pattern.match(em), (
            f"malformed E11.M id: {em!r}"
        )


def test_e11_modules_unique():
    body = _read()
    e11_ids = re.findall(r"\| (E11\.M\d+) \|", body)
    duplicates = set(i for i in e11_ids if e11_ids.count(i) > 1)
    assert not duplicates, (
        f"duplicate E11.M ids: {duplicates}"
    )


def test_e11_modules_sequential():
    """WITHIN each E11.M number-band (a hundreds-block, per docs/sdd/README.md +
    SDD-100) the E11.M sequence has no INTERNAL gaps; band BOUNDARIES (e.g. M38 →
    M100 into the recover-projects band) are the intentional per-session gaps that
    keep the 3 parallel sessions from colliding on mandate-module numbers."""
    body = _read()
    e11_ids = re.findall(r"\| E11\.M(\d+) \|", body)
    if not e11_ids:
        return
    nums = sorted(int(i) for i in e11_ids)
    blocks: dict[int, list[int]] = {}
    for n in nums:
        blocks.setdefault(n // 100, []).append(n)
    for blk, members in blocks.items():
        lo, hi = min(members), max(members)
        missing = set(range(lo, hi + 1)) - set(members)
        assert not missing, (
            f"E11.M band {blk}xx has internal gaps: missing {sorted(missing)}"
        )


# --- §1g key concretes section ---


def test_section_1g_has_key_concretes():
    """§1g MUST have a key-concretes subsection (operator-discoverable
    decomposition surface — the bridge between verbatim paste and the
    E11 Module breakdown)."""
    body = _read()
    section_1g_idx = body.find("### §1g")
    if section_1g_idx < 0:
        return
    section_1g = body[section_1g_idx:body.find("## 2.", section_1g_idx)]
    has_concretes = (
        "key concretes" in section_1g.lower()
        or "Concretes" in section_1g
        or "NOT minimized" in section_1g
    )
    assert has_concretes, (
        "§1g missing key-concretes subsection (operator-discoverable "
        "decomposition surface)"
    )


def test_section_1h_present_with_2026_05_18():
    """§1h landed 2026-05-18 (6th /goal block — 'two ultimate
    solutions + perfectioning + high UX/DX')."""
    body = _read()
    section_1h_idx = body.find("### §1h")
    assert section_1h_idx > 0, "mandate doc missing §1h subsection"
    section_1h = body[section_1h_idx:body.find("## 2.", section_1h_idx)]
    assert "2026-05-18" in section_1h, (
        "§1h header missing 2026-05-18 date"
    )


def test_section_1h_operator_verbatim_phrases():
    """§1h key operator-verbatim phrases — SACROSANCT."""
    body = _read()
    section_1h_idx = body.find("### §1h")
    if section_1h_idx < 0:
        return
    section_1h = body[section_1h_idx:body.find("## 2.", section_1h_idx)]
    expected_phrases = [
        "two ultimate solutions",       # operator-named duality
        "perfectioning",                # operator-coined verb (NOT "perfecting")
        "high UX/DX",                   # User Experience + Developer Experience pairing
        "continue till you meet ALL",   # perpetual mandate phrase
        "REPROCESS",                    # raw-dump-reprocess directive
        "Continue Endlessly",           # endless framing
    ]
    for phrase in expected_phrases:
        assert phrase in section_1h, (
            f"§1h missing operator-verbatim phrase {phrase!r}"
        )


def test_section_1h_names_both_targets():
    """§1h key concretes MUST identify the 'two ultimate solutions'
    as selfdef + sovereign-os (operator-discoverable duality)."""
    body = _read()
    section_1h_idx = body.find("### §1h")
    if section_1h_idx < 0:
        return
    section_1h = body[section_1h_idx:body.find("## 2.", section_1h_idx)]
    assert "selfdef" in section_1h.lower(), (
        "§1h key-concretes missing selfdef target"
    )
    assert "sovereign-os" in section_1h.lower(), (
        "§1h key-concretes missing sovereign-os target"
    )


def test_section_1h_pairs_ux_with_dx():
    """'high UX/DX' explicitly pairs User Experience AND Developer
    Experience. Both first-class. Drift = prioritize one = mandate
    violation."""
    body = _read()
    section_1h_idx = body.find("### §1h")
    if section_1h_idx < 0:
        return
    section_1h = body[section_1h_idx:body.find("## 2.", section_1h_idx)]
    has_ux_dx_pairing = (
        ("User Experience" in section_1h and "Developer Experience" in section_1h)
        or "UX/DX" in section_1h
    )
    assert has_ux_dx_pairing, (
        "§1h key-concretes missing UX/DX pairing documentation"
    )


def test_section_1_subsection_chain_chronological():
    """Subsections in § 1 SHOULD appear in chronological order
    (§1.0 first, §1g latest at this point)."""
    body = _read()
    # Get positions of each expected anchor
    positions = {}
    for anchor in EXPECTED_SUBSECTIONS:
        pos = body.find(anchor)
        if pos > 0:
            positions[anchor] = pos
    # Expected order in EXPECTED_SUBSECTIONS list MUST match file order
    ordered_anchors = sorted(positions.keys(), key=lambda a: positions[a])
    expected_order_present = [a for a in EXPECTED_SUBSECTIONS if a in positions]
    assert ordered_anchors == expected_order_present, (
        f"§ 1 subsections out of chronological order:\n"
        f"  in file: {ordered_anchors}\n"
        f"  expected: {expected_order_present}"
    )
