"""sovereign-osctl --help surfaces every M060 mirror verb.

Discoverability gap: operators looking at `sovereign-osctl --help` should
see every available M060 cross-repo mirror verb (10 mirror readers + the
chain-health proxy + the m060-doctor smoke). Without this, the verbs
exist but operators learn about them only by reading the script source
or stumbling into runbooks.

This test locks the help text against drift: any verb that ships in the
sovereign-osctl dispatch table MUST appear in cmd_help, and the M060
section MUST surface the audit-mirror trace lookup (M013 E0112) along
with chain-walker semantics.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OSCTL_PATH = REPO_ROOT / "scripts" / "sovereign-osctl"


def _help_text() -> str:
    proc = subprocess.run(
        ["bash", str(OSCTL_PATH), "--help"],
        capture_output=True, text=True, timeout=10, check=False,
    )
    return proc.stdout


def test_help_text_exposes_m060_section_header():
    """The M060 section header must be discoverable so operators
    scanning --help see there IS a mirror chain surface."""
    body = _help_text()
    assert "M060" in body, (
        "sovereign-osctl --help missing the M060 cross-repo mirror section "
        "— operators won't discover the mirror verbs from --help"
    )
    assert "cross-repo" in body.lower() or "selfdef" in body.lower(), (
        "M060 section must explain it's a CROSS-REPO bridge — without "
        "this operators don't know WHY these verbs exist alongside the "
        "sovereign-os native ones"
    )


def test_help_lists_every_M060_mirror_reader_verb():
    """Every shipped mirror reader verb MUST appear in --help."""
    body = _help_text()
    for verb in (
        "profile-mirror",
        "rules-mirror",
        "grants-mirror",
        "capability-mirror",
        "sandbox-mirror",
        "audit-mirror",
        "quarantine-mirror",
        "trust-mirror",
        "tui-mirror",
        "cli-mirror",
    ):
        assert verb in body, (
            f"sovereign-osctl --help missing the `{verb}` verb — "
            f"operators won't discover it"
        )


def test_help_lists_m060_health_and_doctor_verbs():
    body = _help_text()
    assert "m060-doctor" in body, (
        "sovereign-osctl --help missing m060-doctor — load-bearing "
        "verb for incident-response triage"
    )
    assert "m060-health" in body, (
        "sovereign-osctl --help missing m060-health — load-bearing "
        "verb for chain-health probing"
    )


def test_help_m060_doctor_surfaces_doctor_observer_flags():
    """The m060-doctor verb wraps m060-smoke.py which (per sovereign-os
    commit 42c5e6c) now probes the selfdef-side doctor textfile
    observers via node_exporter. The help text MUST surface the
    --skip-doctor-observers and --node-exporter-url flags so
    operators discover them without reading the script source."""
    body = _help_text()
    # Find the m060-doctor block (next ~10 lines after the verb mention).
    idx = body.find("m060-doctor")
    assert idx >= 0, "m060-doctor not in --help"
    section = body[idx : idx + 600]
    assert "skip-doctor-observers" in section, (
        f"m060-doctor help missing --skip-doctor-observers flag "
        f"(load-bearing for hosts where node_exporter is unreachable):\n{section}"
    )
    assert "node-exporter-url" in section, (
        f"m060-doctor help missing --node-exporter-url flag (load-bearing "
        f"when node_exporter runs on a non-default URL):\n{section}"
    )
    # The help text also needs to surface WHY operators care: doctor
    # observers ARE part of the chain verification.
    assert "doctor" in section.lower() and (
        "observer" in section.lower() or "textfile" in section.lower()
    ), (
        f"m060-doctor help must mention doctor observers / textfile probe "
        f"so operators understand what the new flags do:\n{section}"
    )


def test_help_documents_audit_mirror_trace_verb():
    """The new `trace <id>` verb (shipped in 5e79218) MUST appear in
    the audit-mirror documentation line — without this operators
    investigating an incident won't know they can drill on a single
    trace_id without piping through jq."""
    body = _help_text()
    # The audit-mirror help line must list trace alongside snapshot +
    # integrity.
    audit_section = ""
    for line in body.splitlines():
        if "audit-mirror" in line:
            # Take this line + next 2 (description may wrap).
            idx = body.find(line)
            audit_section = body[idx : idx + 300]
            break
    assert "trace" in audit_section, (
        f"audit-mirror help missing `trace <id>` verb:\n{audit_section}"
    )
    # M013 E0112 catalog row reference.
    assert "M013 E0112" in body or "tracing is crucial" in body.lower(), (
        "help must reference the M013 E0112 catalog row that motivates "
        "the trace verb — provenance trail for the operator"
    )


def test_help_examples_section_includes_m060_invocation():
    """The EXAMPLES section MUST include at least one M060 invocation
    so operators see what a real call looks like (vs reading the verb
    enumeration and having to guess at flags)."""
    body = _help_text()
    examples_idx = body.find("EXAMPLES:")
    assert examples_idx > 0, "help missing EXAMPLES: section"
    examples = body[examples_idx:]
    assert "m060" in examples.lower() or "mirror" in examples.lower(), (
        "EXAMPLES section must include an M060 / mirror invocation"
    )


def test_dispatch_table_verbs_all_appear_in_help():
    """Drift catch: every verb the dispatch table (case statement)
    recognizes MUST appear in --help. Verbs that ship but aren't
    documented are silent operator-discovery gaps."""
    body = _help_text()
    osctl_text = OSCTL_PATH.read_text()
    # The case statement uses `verb)` markers. Look for the M060-relevant
    # verbs added in this batch.
    documented_verbs = (
        "profile-mirror",
        "rules-mirror",
        "grants-mirror",
        "capability-mirror",
        "sandbox-mirror",
        "audit-mirror",
        "quarantine-mirror",
        "trust-mirror",
        "tui-mirror",
        "cli-mirror",
        "m060-health",
        "m060-doctor",
    )
    for verb in documented_verbs:
        # Must exist in the dispatch table.
        assert f"  {verb})" in osctl_text, (
            f"verb `{verb}` not in sovereign-osctl dispatch table (does it "
            f"actually ship?)"
        )
        # AND must be in --help.
        assert verb in body, (
            f"verb `{verb}` ships but is undocumented in --help"
        )


def test_chain_walker_semantics_documented():
    """The trace verb's chain-walker semantics (prev/next trace_id)
    are non-obvious; help text should at least surface that trace
    LOOKS UP one span (not the full chain)."""
    body = _help_text()
    # `audit-mirror trace <id>` must surface the single-lookup nature
    # (any of: "ONE span", "single", "lookup") so operators don't expect
    # the full chain.
    keywords = ("one span", "single", "lookup")
    assert any(k in body.lower() for k in keywords), (
        f"audit-mirror trace description must surface single-lookup nature; "
        f"missing any of {keywords}"
    )
