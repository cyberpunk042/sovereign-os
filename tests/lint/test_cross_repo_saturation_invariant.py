"""R473 — Cross-repo typed-mirror SATURATION invariant lint.

Codifies the invariant established at R471: every sovereign-os
compliance instrument MUST have:
  (1) a `selfdef` verb defined in its script
  (2) a SOVEREIGN_OS_SELFDEF_<TAXONOMY>_DIR env-override or
      SOVEREIGN_OS_MODULES_LOG (for event-stream consumers)
  (3) a corresponding selfdef-side crate under `crates/` documented
      in the operator-mandate
  (4) a row in SDD-038 cross-repo-binding-doctrine's currently-bound
      taxonomies table

The intent: any future contributor who lands a NEW compliance
instrument on the sovereign-os side WITHOUT shipping its selfdef-side
typed mirror fails this lint at push-time. The saturation invariant
becomes structural, not aspirational.

Cross-repo doctrine: docs/sdd/038-cross-repo-binding-doctrine.md.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OP_DIR = REPO_ROOT / "scripts" / "operator"
SDD038 = REPO_ROOT / "docs" / "sdd" / "038-cross-repo-binding-doctrine.md"
MANDATE = (REPO_ROOT / "docs" / "standing-directives"
           / "2026-05-17-operator-mandate.md")

# The current 8-instrument compliance suite, each with:
#  - script: relative path inside scripts/operator/
#  - sd_round: cross-repo binding ID (per SDD-038 Way-forward table)
#  - selfdef_crate: expected selfdef-side crate name (informational —
#    NOT verified by these tests, since selfdef lives in a sibling
#    repo not always present at sovereign-os test time)
INSTRUMENTS = [
    {
        "script": "bashrc-install.sh",
        "sd_round": "SD-R-BASHRC-1",
        "verb_name": None,  # bashrc is operator-runtime; the R468
                            # `combo` verb is the cross-repo surface
        "combo_verb": True,
        "selfdef_crate": "selfdef-bashrc-install",
    },
    {
        "script": "global-history.py",
        "sd_round": "SD-R-EVENT-LOG-1",
        "verb_name": None,  # consumed via 'modules' source in any
                            # verb; env override is the binding
        "modules_env": "SOVEREIGN_OS_MODULES_LOG",
        "selfdef_crate": "selfdef-history-sink",
    },
    {
        "script": "auth-tier.py",
        "sd_round": "SD-R-AUTH-TIER-1",
        "verb_name": None,  # transitively bound via dashboard-manifest
        "selfdef_crate": "selfdef-auth-tier",
    },
    {
        "script": "master-dashboard.py",
        "sd_round": "SD-R-DASHBOARD-MANIFEST-1",
        "verb_name": "discover",
        "env_var": "SOVEREIGN_OS_SELFDEF_MANIFEST_DIR",
        "selfdef_crate": "selfdef-dashboard-manifest",
    },
    {
        "script": "surface-map.py",
        "sd_round": "SD-R-MULTI-SURFACE-AUDIT-1",
        "verb_name": "selfdef",
        "env_var": "SOVEREIGN_OS_SELFDEF_SURFACE_DIR",
        "selfdef_crate": "selfdef-surface-manifest",
    },
    {
        "script": "ux-design-audit.py",
        "sd_round": "SD-R-UX-CHECKLIST-1",
        "verb_name": "selfdef",
        "env_var": "SOVEREIGN_OS_SELFDEF_UX_DIR",
        "selfdef_crate": "selfdef-ux-checklist",
    },
    {
        "script": "anti-minimization-audit.py",
        "sd_round": "SD-R-AUDIT-1",
        "verb_name": "selfdef",
        "env_var": "SOVEREIGN_OS_SELFDEF_AUDIT_DIR",
        "selfdef_crate": "selfdef-audit-manifest",
    },
    {
        "script": "doc-coverage.py",
        "sd_round": "SD-R-DOC-MANIFEST-1",
        "verb_name": "selfdef",
        "env_var": "SOVEREIGN_OS_SELFDEF_DOC_DIR",
        "selfdef_crate": "selfdef-doc-manifest",
    },
]


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# --- Per-instrument verb presence ---


def test_each_instrument_script_exists():
    """SATURATION-A: every claimed instrument has its script."""
    missing = []
    for inst in INSTRUMENTS:
        if not (OP_DIR / inst["script"]).is_file():
            missing.append(inst["script"])
    assert not missing, (
        f"SATURATION-A break: scripts missing under scripts/operator/: "
        f"{missing}"
    )


def test_env_consumers_declare_selfdef_dir_env_var():
    """SATURATION-B: instruments with an env_var entry MUST declare
    it in their script. Drift catches: script renames env without
    updating the saturation invariant table."""
    missing = []
    for inst in INSTRUMENTS:
        env_var = inst.get("env_var")
        if not env_var:
            continue
        body = _read(OP_DIR / inst["script"])
        if env_var not in body:
            missing.append((inst["script"], env_var))
    assert not missing, (
        f"SATURATION-B break: scripts missing their declared "
        f"SOVEREIGN_OS_SELFDEF_*_DIR env var: {missing}"
    )


def test_verb_consumers_define_selfdef_or_discover_verb():
    """SATURATION-C: instruments with a verb_name entry MUST register
    that verb as a subcommand in their script."""
    missing = []
    for inst in INSTRUMENTS:
        verb = inst.get("verb_name")
        if not verb:
            continue
        body = _read(OP_DIR / inst["script"])
        # Argparse pattern: `sub.add_parser("<verb>"`
        # Dispatch dict pattern: `"<verb>": cmd_<verb>`
        pat = re.compile(
            rf'(sub\.add_parser\(\s*["\'`]{re.escape(verb)}["\'`])'
            rf'|(["\'`]{re.escape(verb)}["\'`]\s*:\s*cmd_)'
        )
        if not pat.search(body):
            missing.append((inst["script"], verb))
    assert not missing, (
        f"SATURATION-C break: scripts missing their {verb!r} "
        f"argparse/dispatch entry: {missing}"
    )


def test_modules_log_consumer_declares_modules_env():
    """SATURATION-D: the global-history-style consumer MUST declare
    SOVEREIGN_OS_MODULES_LOG (the cross-repo event-stream binding)."""
    missing = []
    for inst in INSTRUMENTS:
        env = inst.get("modules_env")
        if not env:
            continue
        body = _read(OP_DIR / inst["script"])
        if env not in body:
            missing.append((inst["script"], env))
    assert not missing, (
        f"SATURATION-D break: modules-log consumer missing env: {missing}"
    )


def test_combo_verb_consumer_chains_selfdef_installer():
    """SATURATION-E: bashrc-install combo verb MUST chain a selfdef
    installer (via SELFDEF_BASHRC_INSTALL_PATH or adjacent-checkout
    autodiscovery)."""
    missing = []
    for inst in INSTRUMENTS:
        if not inst.get("combo_verb"):
            continue
        body = _read(OP_DIR / inst["script"])
        if "combo)" not in body:
            missing.append((inst["script"], "combo) dispatcher missing"))
        if "SELFDEF_BASHRC_INSTALL_PATH" not in body:
            missing.append(
                (inst["script"], "SELFDEF_BASHRC_INSTALL_PATH missing")
            )
    assert not missing, (
        f"SATURATION-E break: combo verb consumer drift: {missing}"
    )


# --- Doctrine / mandate cross-refs ---


def test_sdd038_lists_every_instrument_sd_round():
    """SATURATION-F: SDD-038 currently-bound-taxonomies table MUST
    list every instrument's SD-R-* binding ID. Drift catches:
    new instrument added without updating the doctrine."""
    if not SDD038.is_file():
        # If the doctrine SDD isn't shipped yet (pre-R470), skip.
        return
    body = _read(SDD038)
    missing = []
    for inst in INSTRUMENTS:
        if inst["sd_round"] not in body:
            missing.append((inst["script"], inst["sd_round"]))
    assert not missing, (
        f"SATURATION-F break: SDD-038 missing instruments: {missing}"
    )


def test_mandate_cites_every_selfdef_crate_name():
    """SATURATION-G: operator-mandate MUST reference every
    selfdef-side crate name SOMEWHERE (typically in the E10.Mx
    row that landed the binding). Drift catches: crate created
    but not anchored in mandate."""
    body = _read(MANDATE)
    missing = []
    for inst in INSTRUMENTS:
        if inst["selfdef_crate"] not in body:
            missing.append((inst["script"], inst["selfdef_crate"]))
    assert not missing, (
        f"SATURATION-G break: mandate missing selfdef crate "
        f"references: {missing}"
    )


# --- Count invariants ---


def test_instrument_count_at_least_eight():
    """Saturation milestone: ≥8 instruments. Future additions push
    higher; this just floor-checks against accidental regression."""
    assert len(INSTRUMENTS) >= 8


def test_every_instrument_has_sd_round_set():
    missing = [
        inst["script"] for inst in INSTRUMENTS if not inst["sd_round"]
    ]
    assert not missing, (
        f"instruments missing sd_round binding ID: {missing}"
    )


def test_every_instrument_has_selfdef_crate_set():
    missing = [
        inst["script"] for inst in INSTRUMENTS
        if not inst["selfdef_crate"]
    ]
    assert not missing, (
        f"instruments missing selfdef_crate name: {missing}"
    )


def test_no_duplicate_sd_round_ids():
    seen: dict[str, str] = {}
    for inst in INSTRUMENTS:
        sd = inst["sd_round"]
        if sd in seen:
            raise AssertionError(
                f"duplicate SD-R binding {sd!r}: "
                f"{seen[sd]} and {inst['script']}"
            )
        seen[sd] = inst["script"]


def test_no_duplicate_selfdef_crate_names():
    seen: dict[str, str] = {}
    for inst in INSTRUMENTS:
        c = inst["selfdef_crate"]
        if c in seen:
            raise AssertionError(
                f"duplicate selfdef crate {c!r}: "
                f"{seen[c]} and {inst['script']}"
            )
        seen[c] = inst["script"]
