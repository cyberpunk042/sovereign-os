"""R437 (E10.M81) — selfdef cross-repo bridge surface lint.

Extends R387-R436 + R418/R433 operational-artifact pinning to the
operator-named selfdef cross-repo integration points:
  scripts/sovereign-osctl  (osctl surfaces selfdefctl state)
  scripts/build/lib/selfdef-tune.sh  (R433 covered already)
  scripts/models/selfdef-models.py  (R183 bridge)
  docs/sdd/031-mcp-aggregate.md  (SD-R94 MCP TCP transport doc)

Operator-named cross-repo SD-R<N> referenced rounds:
  SD-R10 — capabilities.json schema (selfdef hardware capabilities)
  SD-R14..R39 — cycle-2 module gate (operator-named)
  SD-R19 — selfdefctl hardware tune --format env-file
  SD-R34 — model-registry catalog
  SD-R57 — HTTP fetch + sha256 verify
  SD-R94 — selfdef MCP TCP transport
  SD-R98 — @selfdef_macro registry

If a future agent silently:
  - removes selfdefctl integration from sovereign-osctl = R184 selfdef
    cycle-2 module-gate state surface disappears
  - drops the conditional 'command -v selfdefctl >/dev/null 2>&1'
    guard = sovereign-os hosts WITHOUT selfdef installed crash
  - hardcodes a selfdef SD-R<N> round that doesn't exist = fabricated
    cross-repo reference
…the operator-named cross-repo binding silently breaks.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"
SELFDEF_MODELS_PY = REPO_ROOT / "scripts" / "models" / "selfdef-models.py"
MCP_AGGREGATE_SDD = REPO_ROOT / "docs" / "sdd" / "031-mcp-aggregate.md"


def _read(p: Path) -> str:
    assert p.is_file(), f"missing {p}"
    return p.read_text(encoding="utf-8")


# --- sovereign-osctl selfdef integration ---


def test_osctl_references_selfdefctl():
    """osctl MUST reference selfdefctl (operator-named cross-repo CLI)."""
    body = _read(OSCTL)
    assert "selfdefctl" in body, (
        "sovereign-osctl missing selfdefctl reference "
        "(operator-named cross-repo CLI integration)"
    )


def test_osctl_guards_selfdefctl_availability():
    """sovereign-os hosts MAY not have selfdef installed. osctl MUST
    guard with 'command -v selfdefctl' (drift = crash on hosts
    without selfdef)."""
    body = _read(OSCTL)
    has_guard = (
        "command -v selfdefctl" in body
        and ">/dev/null 2>&1" in body
    )
    assert has_guard, (
        "sovereign-osctl missing 'command -v selfdefctl' availability "
        "guard (drift = crash on hosts without selfdef installed)"
    )


def test_osctl_references_sd_r19_selfdefctl_hardware_tune():
    """SD-R19 is operator-named: 'selfdefctl hardware tune --format
    env-file'. osctl OR selfdef-tune.sh references this round."""
    osctl_body = _read(OSCTL)
    tune_body = _read(REPO_ROOT / "scripts" / "build" / "lib" / "selfdef-tune.sh")
    has_sd_r19 = "SD-R19" in osctl_body or "SD-R19" in tune_body
    assert has_sd_r19, (
        "missing SD-R19 round reference (selfdefctl hardware tune "
        "--format env-file) in osctl or selfdef-tune.sh"
    )


def test_osctl_references_sd_r94_mcp_tcp():
    """SD-R94 is operator-named: selfdef MCP TCP transport.
    Surfaced in mcp-aggregate manifest verb."""
    body = _read(OSCTL)
    assert "SD-R94" in body or "selfdef-mcp" in body.lower(), (
        "sovereign-osctl missing SD-R94 / selfdef-mcp reference "
        "(MCP TCP transport)"
    )


def test_osctl_supports_upstream_selfdef_flag():
    """mcp-aggregate manifest accepts --upstream-selfdef host:port."""
    body = _read(OSCTL)
    assert "--upstream-selfdef" in body, (
        "sovereign-osctl missing --upstream-selfdef flag "
        "(SD-R94 MCP TCP descriptor)"
    )


# --- selfdef-models.py bridge ---


def test_selfdef_models_py_exists():
    """R182/R183 bridge: scripts/models/selfdef-models.py provides
    selfdef SD-R34 model-registry surface."""
    assert SELFDEF_MODELS_PY.is_file(), (
        f"missing {SELFDEF_MODELS_PY} (R182/R183 selfdef SD-R34 bridge)"
    )


def test_selfdef_models_py_documents_sd_r34():
    body = _read(SELFDEF_MODELS_PY)
    has_sd_r34 = (
        "SD-R34" in body
        or "model-registry" in body.lower()
        or "model registry" in body.lower()
    )
    assert has_sd_r34, (
        "selfdef-models.py missing SD-R34 model-registry reference"
    )


def test_selfdef_models_supports_list_subcommand():
    body = _read(SELFDEF_MODELS_PY)
    assert '"list"' in body or "'list'" in body, (
        "selfdef-models.py missing 'list' subcommand"
    )


def test_selfdef_models_supports_check_hardware_subcommand():
    body = _read(SELFDEF_MODELS_PY)
    assert "check-hardware" in body or "check_hardware" in body, (
        "selfdef-models.py missing 'check-hardware' subcommand"
    )


# --- SDD-031 MCP aggregate doc ---


def test_mcp_aggregate_sdd_exists():
    assert MCP_AGGREGATE_SDD.is_file(), f"missing {MCP_AGGREGATE_SDD}"


def test_mcp_aggregate_documents_sd_r94():
    body = _read(MCP_AGGREGATE_SDD)
    assert "SD-R94" in body, (
        "SDD-031 missing SD-R94 (selfdef MCP TCP transport) "
        "reference (operator-named cross-repo binding)"
    )


def test_mcp_aggregate_documents_sd_r98():
    """SD-R98 @selfdef_macro registry (future cross-repo CoT routines)."""
    body = _read(MCP_AGGREGATE_SDD)
    has_sd_r98 = (
        "SD-R98" in body
        or "@selfdef_macro" in body
        or "selfdef_macro" in body
    )
    assert has_sd_r98, (
        "SDD-031 missing SD-R98 / @selfdef_macro reference"
    )


def test_mcp_aggregate_references_selfdef_namespace():
    """The aggregate manifest MUST surface selfdef tools under a
    distinct namespace (operator-named: 'selfdef' tools surface
    next to OS-level tools)."""
    body = _read(MCP_AGGREGATE_SDD)
    assert '"namespace": "selfdef"' in body or '"namespace":"selfdef"' in body, (
        "SDD-031 missing 'namespace: selfdef' tool surface "
        "(operator-named tool grouping)"
    )


# --- Cross-repo SD-R round well-formedness ---


def test_sd_r_round_references_well_formed():
    """SD-R<N> references in sovereign-os MUST follow operator-named
    format (SD-R followed by digits, optional letter suffix)."""
    bodies = [
        _read(OSCTL),
        _read(SELFDEF_MODELS_PY) if SELFDEF_MODELS_PY.is_file() else "",
        _read(MCP_AGGREGATE_SDD),
    ]
    pattern = re.compile(r"SD-R\d+")
    for body in bodies:
        for m in pattern.finditer(body):
            ref = m.group(0)
            # Should be SD-R followed by 1-3 digits
            assert re.match(r"^SD-R\d{1,3}$", ref), (
                f"malformed SD-R reference: {ref!r}"
            )


def test_no_fabricated_high_sd_r_numbers():
    """SD-R round numbers are operator-named — reasonable cap is
    SD-R200 (covering generous future expansion). Drift to SD-R9999
    = fabrication."""
    bodies = [
        _read(OSCTL),
        _read(SELFDEF_MODELS_PY) if SELFDEF_MODELS_PY.is_file() else "",
        _read(MCP_AGGREGATE_SDD),
    ]
    pattern = re.compile(r"SD-R(\d+)")
    for body in bodies:
        for m in pattern.finditer(body):
            n = int(m.group(1))
            assert n <= 200, (
                f"SD-R{n} out of plausible range "
                f"(operator-named selfdef rounds cap ~ SD-R200 today)"
            )


# --- Operator-discoverable surface ---


def test_osctl_help_documents_mcp_aggregate():
    """sovereign-osctl help text surfaces mcp-aggregate verb."""
    body = _read(OSCTL)
    assert "mcp-aggregate" in body, (
        "sovereign-osctl missing mcp-aggregate verb"
    )


def test_selfdef_bridge_files_use_relative_paths():
    """Cross-repo references MUST use relative paths within
    sovereign-os (sovereign-os doesn't assume selfdef is at any
    specific filesystem location — uses selfdefctl CLI on PATH)."""
    body = _read(OSCTL)
    # Forbidden: hardcoded clone-relative paths
    # (Allowed: /etc/selfdef, /var/lib/selfdef — these are system
    #  install paths, operator-named cross-repo conventions.)
    forbidden_patterns = [
        r"/cyberpunk042/selfdef",       # GitHub-org-relative clone path
        r"\.\./selfdef/",               # parent-relative clone
        r"\.\./\.\./selfdef/",
        r"/home/[a-z]+/selfdef/",       # operator-home-relative clone
    ]
    for pat in forbidden_patterns:
        m = re.search(pat, body)
        assert not m, (
            f"sovereign-osctl has hardcoded selfdef path matching "
            f"{pat!r}: {m.group()} (drift = breaks when operator "
            f"clones to different layout)"
        )
