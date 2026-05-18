"""R407 (E10.M51) — whitelabel render engine operator-verbatim SDD-007 lint.

Extends R387-R406 operational-artifact pinning to:
  scripts/whitelabel/render.py

The whitelabel render engine implements SDD-007's Layer 1: translates
profile YAML + whitelabel YAML → substrate-agnostic file-tree changeset,
then emits substrate-specific overlay (mkosi.skeleton/ + mkosi.extra/
or live-build's config/includes.chroot/).

SDD-007 + SDD-006 verbatim invariants:
  1. 7-strategy taxonomy — all 7 strategies MUST be handled:
       template-substitution / file-overlay / package-replacement /
       build-time-flag / install-time-substitution / first-boot-script /
       must-not-touch
  2. Legal-floor guard (SDD-006 § Legal floor) — render MUST refuse to
     overwrite /etc/debian_version, debian-logo*, /usr/share/doc/*/copyright,
     /usr/share/man/*. Drift = whitelabel can erase Debian legal attribution.
  3. compliance_target validation: profile.whitelabel.legal_compliance
     MUST match whitelabel.compliance_target (operator's sovereignty
     compliance contract — drift silently mismatches sovereignty intent
     between profile and whitelabel).
  4. Substrate-emit duality: both emit_for_mkosi() and emit_for_live_build()
     MUST handle the same Changeset → drift = whitelabel-output differs
     between substrates from same input.
  5. yaml.safe_load (security: yaml.load = RCE on untrusted YAML).
  6. Exit codes: 2 (yaml import), 3 (compliance mismatch), 4 (legal floor
     violation), 5 (substrate not implemented) — operator-discoverable
     failure modes.

If a future agent silently:
  - drops the legal-floor list = whitelabel can erase Debian credit
  - drops a strategy from the 7-taxonomy = surfaces silently dropped
  - relaxes compliance_target check = profile/whitelabel mismatch slips
  - changes emit_for_mkosi without same change to emit_for_live_build
    = substrate-dependent whitelabel output
…SDD-007 + SDD-006 contracts silently break.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RENDER = REPO_ROOT / "scripts" / "whitelabel" / "render.py"

STRATEGIES_EXPECTED = [
    "template-substitution",
    "file-overlay",
    "package-replacement",
    "build-time-flag",
    "install-time-substitution",
    "first-boot-script",
    "must-not-touch",
]

LEGAL_FLOOR_EXPECTED = [
    "/etc/debian_version",
    "/usr/share/doc/*/copyright",
    "/usr/share/man/*",
    "*/debian-logo*",
    "*/debian-swirl*",
]


def _read() -> str:
    assert RENDER.is_file(), f"missing {RENDER}"
    return RENDER.read_text(encoding="utf-8")


def test_render_file_exists():
    assert RENDER.is_file(), f"missing {RENDER}"


def test_render_python_syntactically_valid():
    """render.py MUST parse as valid Python (drift to syntax error
    breaks every substrate build)."""
    try:
        ast.parse(_read())
    except SyntaxError as e:
        raise AssertionError(f"render.py has syntax error: {e}")


# --- SDD-007 7-strategy taxonomy ---


def test_all_seven_strategies_handled():
    """SDD-007 verbatim: render MUST handle all 7 strategies. Drift
    losing any strategy silently drops every surface declared under it."""
    body = _read()
    for strategy in STRATEGIES_EXPECTED:
        assert f'"{strategy}"' in body, (
            f"render.py missing strategy {strategy!r} "
            f"(SDD-007 verbatim 7-strategy taxonomy)"
        )


def test_strategy_count_in_docstring():
    """render.py header docstring SHOULD reference '7-strategy taxonomy'
    (operator-discovery: reader sees the contract count)."""
    body = _read()
    has_count = "7-strategy" in body or "7 strategies" in body or "seven strategies" in body.lower()
    assert has_count, (
        "render.py docstring missing '7-strategy taxonomy' reference "
        "(SDD-007 verbatim — operator-discovery surface)"
    )


# --- SDD-006 § Legal floor ---


def test_legal_floor_patterns_present():
    """SDD-006 § Legal floor: render MUST list /etc/debian_version,
    debian-logo*, /usr/share/doc/*/copyright, /usr/share/man/* as
    must-not-touch paths. Drift = whitelabel can erase Debian attribution
    = SDD-006 Debian-credit violation."""
    body = _read()
    for pattern in LEGAL_FLOOR_EXPECTED:
        assert f'"{pattern}"' in body, (
            f"render.py LEGAL_FLOOR_PATTERNS missing {pattern!r} "
            f"(SDD-006 § Legal floor verbatim — Debian attribution "
            f"erasure protection)"
        )


def test_violates_legal_floor_function_defined():
    """The check function MUST exist (drift = removed without
    removing the patterns; patterns become inert)."""
    body = _read()
    assert "def violates_legal_floor(" in body, (
        "render.py missing violates_legal_floor() check function "
        "(SDD-006 § Legal floor enforcement entry point)"
    )


def test_legal_floor_uses_fnmatch():
    """Patterns include wildcards (e.g. 'debian-logo*') so glob match
    is required. Drift to bare string equality silently lets
    'debian-logo.svg' through (only literal 'debian-logo' would match)."""
    body = _read()
    assert "fnmatch" in body, (
        "render.py missing fnmatch glob-pattern matching for legal "
        "floor (drift to bare equality silently lets logo files through)"
    )


def test_legal_floor_violation_exits_nonzero():
    """SDD-006 § Legal floor: violation MUST exit non-zero (drift to
    warn-only silently lets whitelabel proceed past legal floor)."""
    body = _read()
    # Look for the legal-floor error block: should call sys.exit(N)
    # where N != 0 and the error message references legal-floor / legal floor
    has_exit = re.search(
        r"legal[ -]floor.*\n.*sys\.exit\(\s*[1-9]",
        body, re.IGNORECASE | re.DOTALL
    )
    assert has_exit, (
        "render.py legal-floor violation doesn't exit non-zero "
        "(SDD-006 — drift to warn-only lets violations through)"
    )


# --- compliance_target sovereignty contract ---


def test_compliance_target_check():
    """SDD-007: profile.whitelabel.legal_compliance MUST match
    whitelabel.compliance_target. Mismatch = sovereignty intent
    diverges between profile and whitelabel = render exits with error."""
    body = _read()
    has_check = (
        "compliance_target" in body
        and "legal_compliance" in body
    )
    assert has_check, (
        "render.py missing compliance_target ↔ legal_compliance match "
        "(SDD-007 verbatim — sovereignty contract between profile + whitelabel)"
    )


def test_compliance_mismatch_exits_3():
    """Operator-discoverable failure: exit code 3 for compliance mismatch
    (separate from legal-floor exit 4, yaml-import exit 2, substrate-not-
    implemented exit 5)."""
    body = _read()
    has_exit_3 = re.search(
        r"compliance.*mismatch.*\n.*sys\.exit\(\s*3",
        body, re.IGNORECASE | re.DOTALL
    )
    assert has_exit_3, (
        "render.py compliance-mismatch path doesn't exit with code 3 "
        "(operator-discoverable failure-code contract)"
    )


# --- Substrate-emit duality ---


def test_emit_for_mkosi_defined():
    body = _read()
    assert "def emit_for_mkosi(" in body, (
        "render.py missing emit_for_mkosi() function "
        "(SDD-007 Layer 2 substrate adapter — primary substrate)"
    )


def test_emit_for_live_build_defined():
    body = _read()
    assert "def emit_for_live_build(" in body, (
        "render.py missing emit_for_live_build() function "
        "(SDD-007 Layer 2 substrate adapter — Alt-A substrate)"
    )


def test_mkosi_emits_skeleton_and_extra():
    """mkosi emit MUST populate BOTH mkosi.skeleton (early overlay)
    AND mkosi.extra (late overlay). Drift losing either silently drops
    those changeset entries from the substrate output."""
    body = _read()
    assert "mkosi.skeleton" in body, (
        "render.py missing mkosi.skeleton overlay output "
        "(SDD-007 — pre_build_files lands here)"
    )
    assert "mkosi.extra" in body, (
        "render.py missing mkosi.extra overlay output "
        "(SDD-007 — pre_build_overlays lands here)"
    )


def test_live_build_emits_includes_chroot():
    """live-build emit MUST populate config/includes.chroot/ (the
    substrate-parallel of mkosi.skeleton + mkosi.extra)."""
    body = _read()
    assert "includes.chroot" in body, (
        "render.py missing config/includes.chroot output "
        "(SDD-007 — live-build substrate-parallel of mkosi.skeleton+extra)"
    )


def test_emit_functions_emit_manifest():
    """Both emit functions MUST write whitelabel-manifest.json
    (install-time + first-boot-script + package-actions live there;
    install hooks read this manifest)."""
    body = _read()
    assert "whitelabel-manifest.json" in body, (
        "render.py emit functions missing whitelabel-manifest.json "
        "(operator-discoverable manifest for install-time + first-boot)"
    )
    # Both functions should write the manifest — count occurrences
    occurrences = body.count("whitelabel-manifest.json")
    assert occurrences >= 2, (
        f"render.py writes whitelabel-manifest.json only "
        f"{occurrences} times — both mkosi + live-build emit MUST "
        f"produce the manifest"
    )


# --- Security: yaml.safe_load ---


def test_uses_yaml_safe_load():
    body = _read()
    assert "yaml.safe_load" in body, (
        "render.py missing yaml.safe_load (security: yaml.load is "
        "an RCE risk on operator-controlled but untrusted YAML)"
    )


def test_no_bare_yaml_load():
    """Belt-and-suspenders: no bare 'yaml.load(' (without 'safe_')."""
    body = _read()
    bare_load = re.findall(r"\byaml\.load\s*\(", body)
    # Each match must actually be yaml.safe_load (which contains the same
    # regex match offset — recheck preceding context)
    for m in re.finditer(r"yaml\.load\s*\(", body):
        # Check the 5 preceding chars don't contain 'safe_'
        preceding = body[max(0, m.start() - 5):m.start()]
        assert "safe_" in preceding, (
            f"render.py bare yaml.load() at offset {m.start()} "
            f"(security CVE — RCE on untrusted YAML)"
        )


# --- Substrate CLI contract ---


def test_substrate_cli_choices_include_mkosi_and_live_build():
    """argparse 'substrate' option MUST include mkosi + live-build
    (the 2 implemented substrates). rpm-ostree + nixos may appear as
    'not yet implemented' choices for future expansion."""
    body = _read()
    has_mkosi_choice = '"mkosi"' in body or "'mkosi'" in body
    has_lb_choice = '"live-build"' in body or "'live-build'" in body
    assert has_mkosi_choice and has_lb_choice, (
        "render.py --substrate argparse choices missing mkosi or "
        "live-build (SDD-003 + SDD-007 — both substrates implemented)"
    )


def test_required_cli_args():
    """CLI MUST accept --profile + --whitelabel + --out (operator
    contract — orchestrator invokes with these 3)."""
    body = _read()
    for arg in ("--profile", "--whitelabel", "--out"):
        assert f'"{arg}"' in body, (
            f"render.py argparse missing {arg!r} option "
            f"(operator orchestrator invocation contract)"
        )


def test_substrate_not_implemented_exits_5():
    """Drift to other substrates (rpm-ostree / nixos) MUST exit 5
    (operator-discoverable: 'this substrate is not yet implemented')."""
    body = _read()
    has_exit_5 = re.search(
        r"not yet implemented.*\n.*return\s+5",
        body, re.IGNORECASE | re.DOTALL
    )
    assert has_exit_5, (
        "render.py substrate-not-implemented path doesn't return 5 "
        "(operator-discoverable failure-code contract)"
    )


# --- Changeset dataclass invariants ---


def test_changeset_has_all_six_fields():
    """The Changeset dataclass MUST have 6 fields matching the 7
    strategies (must-not-touch is captured under package_actions
    as a tracking entry; the other 6 each have a dedicated bucket)."""
    body = _read()
    expected_fields = [
        "pre_build_files",
        "pre_build_overlays",
        "package_actions",
        "build_time_env",
        "install_time",
        "first_boot_scripts",
    ]
    for field_name in expected_fields:
        assert field_name in body, (
            f"render.py Changeset dataclass missing field {field_name!r} "
            f"(SDD-007 changeset shape — drift drops the bucket for "
            f"that strategy's output)"
        )


def test_changeset_summary_method():
    """Operator-discovery: Changeset.summary() returns the human-
    readable count of changes per bucket. Drift removes the
    --out-of-band visibility into what render did."""
    body = _read()
    assert "def summary(" in body, (
        "render.py Changeset missing summary() method "
        "(operator-discovery — human-readable changeset count)"
    )
