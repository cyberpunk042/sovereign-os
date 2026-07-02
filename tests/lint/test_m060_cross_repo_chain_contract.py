"""M060 cross-repo chain contract — locks the full selfdef→sovereign-os wire.

This test guards the entire 9-mirror producer→consumer wire in one fixture.
For each M060 mirror (D-02 active-profile, D-12 rules, D-13 grants, D-14
capability-tokens, D-15 sandboxes, D-16 audit-chain, D-17 quarantine,
D-18 trust-scores) plus the MS007 TUI-layout schema mirror, it:

  1. Writes a daemon-shaped JSON artifact in the EXACT serde shape the
     `selfdef-daemon` mirror-export writes (via `selfdef-{profile,grant,
     capability,sandbox,audit,quarantine,trust-score}-registry::save()`).
  2. Points the sovereign-os reader (`scripts/mirror/selfdef-*-mirror.py
     snapshot --json`) at the artifact via its `SOVEREIGN_OS_SELFDEF_<DOMAIN>_
     MIRROR` env var.
  3. Asserts the reader returns `mirror_status="online"` + the key fields
     populated from the artifact (token ids, allocation ids, etc.).

Single-test cross-repo guard — catches drift in any of the 7 wires the
moment a producer's serde shape diverges from the consumer's expectations.

Per the M060 cross-repo doctrine (selfdef PR #200 / context.md
"Current arc 2026-05-28: M060 cross-repo mirror producers — COMPLETE"),
the daemon-side producer crates' wire schemas are:
- selfdef-profile-mirror::ProfileMirrorSnapshot 1.0.0
- selfdef-rules-mirror::RulesMirrorSnapshot 1.0.0
- selfdef-grants-mirror::GrantsMirrorSnapshot 1.0.0
- selfdef-capability-mirror::CapabilityMirrorSnapshot 1.0.0
- selfdef-sandbox-mirror::SandboxMirrorSnapshot 1.0.0
- selfdef-audit-mirror::AuditMirrorSnapshot 1.0.0
- selfdef-quarantine-mirror::QuarantineMirrorSnapshot 1.0.0
- selfdef-trust-score-mirror::TrustScoreMirrorSnapshot 1.0.0
- selfdef-tui-mirror::TuiMirrorSnapshot 1.0.0 (canonical 4-panel layout)
- selfdef-cli-mirror::CliMirrorSnapshot 1.0.0 (selfdefctl clap-tree projection)
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
READER_DIR = REPO_ROOT / "scripts" / "mirror"


def _run_reader(script: str, env_var: str, artifact_path: str, cmd: str = "snapshot") -> dict:
    """Run a sovereign-os mirror reader script with its mirror-path env var
    pointing at our daemon-shaped artifact, return its JSON output."""
    env = {
        **os.environ,
        env_var: artifact_path,
        "PATH": "/usr/bin:/bin",
    }
    proc = subprocess.run(
        ["python3", str(READER_DIR / script), cmd, "--json"],
        env=env, capture_output=True, text=True, timeout=10, check=True,
    )
    return json.loads(proc.stdout)


# ------------------------------------------------------------------ D-02

def test_m060_d02_profile_producer_consumer_contract():
    """selfdef-profile-registry's save() output is consumed cleanly by
    sovereign-os selfdef-profile-mirror.py (D-02)."""
    artifact = {
        "schema_version": "1.0.0",
        "active": "autonomous",
        "since": "—",
        "actor": "unknown",
        "envelope": "max authority L5Commit · max trust Ring2",
        "history": [],
    }
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "active-profile.json")
        with open(p, "w") as f:
            json.dump(artifact, f)
        out = _run_reader(
            "selfdef-profile-mirror.py",
            "SOVEREIGN_OS_SELFDEF_PROFILE_MIRROR",
            p,
            cmd="show",
        )
    assert out["mirror_status"] == "online"
    assert out["active"] == "autonomous"
    assert "L5Commit" in out["envelope"]


# ------------------------------------------------------------------ D-13

def test_m060_d13_grants_producer_consumer_contract():
    """selfdef-grant-registry's save() output is consumed cleanly by
    sovereign-os selfdef-grants-mirror.py (D-13)."""
    artifact = {
        "schema_version": "1.0.0",
        "captured_at": "2027-01-15T08:00:00Z",
        "summaries": [
            {"kind": "filesystem", "active": 1, "pending": 1,
             "expired_24h": 0, "revoked_24h": 0, "quarantined": 0},
        ],
        "grants": [
            {"grant_id": "gr-1", "kind": "filesystem", "scope": "/w/**",
             "reason": "author", "issued_at": "2027-01-15T08:00:00Z",
             "expires_at": "2027-01-15T09:00:00Z", "ttl_seconds": 3600,
             "profile": "careful", "actor": "operator-fp",
             "state": "active", "trace_id": "t1", "signature": "sig"},
            {"grant_id": "gr-2", "kind": "filesystem", "scope": "/d/**",
             "reason": "ingest", "issued_at": "2027-01-15T08:05:00Z",
             "expires_at": "2027-01-15T09:05:00Z", "ttl_seconds": 3600,
             "profile": "careful", "actor": "agent-fp",
             "state": "pending", "trace_id": "t2", "signature": "sig2"},
        ],
        "signature": "",
    }
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "grants.json")
        with open(p, "w") as f:
            json.dump(artifact, f)
        out = _run_reader(
            "selfdef-grants-mirror.py",
            "SOVEREIGN_OS_SELFDEF_GRANTS_MIRROR",
            p,
        )
    assert out["mirror_status"] == "online"
    assert {g["grant_id"] for g in out["grants"]} == {"gr-1", "gr-2"}
    # The reader derives `pending` from grants[state=="pending"].
    assert [p["grant_id"] for p in out["pending"]] == ["gr-2"]
    assert out["pending"][0]["requester"] == "agent-fp"


# ------------------------------------------------------------------ D-14

def test_m060_d14_capability_producer_consumer_contract():
    """selfdef-capability-registry's save() output is consumed cleanly by
    sovereign-os selfdef-capability-mirror.py (D-14)."""
    artifact = {
        "schema_version": "1.0.0",
        "captured_at": "2027-01-15T08:00:00Z",
        "summaries": [{"ring": "ring2", "active": 1, "pending": 0,
                       "expired_24h": 0, "revoked_24h": 0, "quarantined": 0}],
        "tokens": [
            {"token_id": "tok-1", "capability_word": "0x0000020000000005",
             "actor": "operator-fp", "profile": "careful",
             "trust_ring": "ring2", "authority_level": "l4_execute",
             "allowed_tools": ["read-only-host", "tests"],
             "sandbox_tier": "A",
             "issued_at": "2027-01-15T08:00:00Z",
             "expires_at": "2027-01-15T09:00:00Z",
             "ttl_seconds": 3600, "state": "active", "trace_id": "t1",
             "parent_token_id": "", "signature": "sig"},
        ],
        "signature": "",
    }
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "capability-tokens.json")
        with open(p, "w") as f:
            json.dump(artifact, f)
        out = _run_reader(
            "selfdef-capability-mirror.py",
            "SOVEREIGN_OS_SELFDEF_CAPABILITY_MIRROR",
            p,
        )
    assert out["mirror_status"] == "online"
    assert [t["token_id"] for t in out["tokens"]] == ["tok-1"]
    assert out["tokens"][0]["allowed_tools"] == ["read-only-host", "tests"]
    assert out["tokens"][0]["trust_ring"] == "ring2"


# ------------------------------------------------------------------ D-15

def test_m060_d15_sandbox_producer_consumer_contract():
    """selfdef-sandbox-registry's save() output is consumed cleanly by
    sovereign-os selfdef-sandbox-mirror.py (D-15)."""
    artifact = {
        "schema_version": "1.0.0",
        "captured_at": "2027-01-15T08:00:00Z",
        "summaries": [{"tier": "tier-a", "running": 1, "pending": 0,
                       "checkpointed": 0, "idle": 0,
                       "released_24h": 0, "quarantined": 0}],
        "allocations": [
            {"allocation_id": "alloc-1", "tier": "tier-a", "ms032_tier": 1,
             "isolation": "host_seccomp", "tool": "rg",
             "capability_token_id": "tok-1", "profile": "careful",
             "actor": "operator-fp",
             "allocated_at": "2027-01-15T08:00:00Z",
             "release_at": "2027-01-15T09:00:00Z",
             "ttl_seconds": 3600, "resident_mb": 64, "cpu_percent": 12,
             "state": "running", "trace_id": "t1", "signature": "sig"},
        ],
        "signature": "",
    }
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "sandboxes.json")
        with open(p, "w") as f:
            json.dump(artifact, f)
        out = _run_reader(
            "selfdef-sandbox-mirror.py",
            "SOVEREIGN_OS_SELFDEF_SANDBOX_MIRROR",
            p,
        )
    assert out["mirror_status"] == "online"
    assert [a["allocation_id"] for a in out["allocations"]] == ["alloc-1"]
    assert out["allocations"][0]["state"] == "running"


# ------------------------------------------------------------------ D-17

def test_m060_d17_quarantine_producer_consumer_contract():
    """selfdef-quarantine-registry's save() output is consumed cleanly by
    sovereign-os selfdef-quarantine-mirror.py (D-17)."""
    artifact = {
        "schema_version": "1.0.0",
        "captured_at": "2027-01-15T08:00:00Z",
        "summaries": [{"severity": "critical", "quarantined": 1,
                       "released_24h": 0, "forfeited_24h": 0}],
        "entries": [
            {"quarantine_id": "q-1", "tool": "rg", "declarer": "operator-fp",
             "capability_token_id": "tok-1",
             "blocked_at": "2027-01-15T08:00:00Z",
             "updated_at": "2027-01-15T08:00:00Z",
             "state": "quarantined", "max_severity": "critical",
             "mismatches": [
                 {"field": "read_paths", "declared": "/safe",
                  "observed": "/etc/passwd",
                  "first_observed_at": "2027-01-15T07:59:00Z",
                  "severity": "critical"},
             ],
             "trace_id": "t1", "signature": ""},
        ],
        "signature": "",
    }
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "quarantine.json")
        with open(p, "w") as f:
            json.dump(artifact, f)
        out = _run_reader(
            "selfdef-quarantine-mirror.py",
            "SOVEREIGN_OS_SELFDEF_QUARANTINE_MIRROR",
            p,
        )
    assert out["mirror_status"] == "online"
    assert [e["quarantine_id"] for e in out["entries"]] == ["q-1"]
    assert out["entries"][0]["max_severity"] == "critical"


# ------------------------------------------------------------------ D-18

def test_m060_d18_trust_scores_producer_consumer_contract():
    """selfdef-trust-score-registry's save() output is consumed cleanly by
    sovereign-os selfdef-trust-score-mirror.py (D-18)."""
    artifact = {
        "schema_version": "1.0.0",
        "captured_at": "2027-01-15T08:00:00Z",
        "summaries": [{"band": "trusted", "count": 1,
                       "mean_score": 750, "trend": "stable"}],
        "tools": [
            {"tool": "rg", "declarer": "operator-fp",
             "current_score": 750, "band": "trusted",
             "first_admitted_at": "2027-01-15T08:00:00Z",
             "last_delta_at": "2027-01-15T08:00:00Z",
             "executions_total": 0, "mismatches_total": 0,
             "history": [], "last_trace_id": "", "signature": ""},
        ],
        "signature": "",
    }
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "trust-scores.json")
        with open(p, "w") as f:
            json.dump(artifact, f)
        out = _run_reader(
            "selfdef-trust-score-mirror.py",
            "SOVEREIGN_OS_SELFDEF_TRUST_MIRROR",
            p,
        )
    assert out["mirror_status"] == "online"
    assert [t["tool"] for t in out["tools"]] == ["rg"]
    assert out["tools"][0]["current_score"] == 750


# ------------------------------------------------------------------ D-16

def test_m060_d16_audit_producer_consumer_contract():
    """selfdef-audit-registry's save() output is consumed cleanly by
    sovereign-os selfdef-audit-mirror.py (D-16)."""
    artifact = {
        "schema_version": "1.0.0",
        "captured_at": "2027-01-15T08:00:00Z",
        "summaries": [
            {"category": "authority_decision", "total": 1,
             "allow": 1, "deny": 0, "ask": 0, "sandbox": 0},
        ],
        "integrity": {
            "head_hash": "a" * 64,
            "total_entries": 1,
            "continuous": True,
            "first_gap_at": None,
            "verified_at": "2027-01-15T08:00:00Z",
        },
        "spans": [
            {"trace_id": "t1", "profile": "careful",
             "model": "qwen3-coder-32b", "provider": "local-cuda",
             "hardware": "4090_logic", "tokens_prompt": 100,
             "tokens_completion": 50, "latency_ms": 1500,
             "cost_millicents": 5, "risk_score": 12,
             "memory_refs": [], "tool_refs": ["read-only-host"],
             "policy_result": "allow", "branch_id": "b1",
             "ocsf_category": "authority_decision",
             "closed_at": "2027-01-15T08:00:00Z",
             "prev_chain_hash": "", "chain_hash": "a" * 64,
             "signature": "sig"},
        ],
        "signature": "",
    }
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "audit.json")
        with open(p, "w") as f:
            json.dump(artifact, f)
        out = _run_reader(
            "selfdef-audit-mirror.py",
            "SOVEREIGN_OS_SELFDEF_AUDIT_MIRROR",
            p,
        )
    assert out["mirror_status"] == "online"
    assert [s["trace_id"] for s in out["spans"]] == ["t1"]
    assert out["integrity"]["continuous"] is True
    assert out["integrity"]["total_entries"] == 1


# ------------------------------------------------------------------ D-12

def test_m060_d12_rules_producer_consumer_contract():
    """selfdef-rules-registry's save() output is consumed cleanly by
    sovereign-os selfdef-rules-mirror.py (D-12)."""
    artifact = {
        "schema_version": "1.0.0",
        "captured_at": "2027-01-15T08:00:00Z",
        "summaries": [
            {"ring": "sovereign_kernel", "rule_count": 1,
             "total_bytes": 640, "total_packets": 10, "pending_l3": 0},
        ],
        "rules": [
            {"handle": 1, "rule_id": "rule-001",
             "ring": "sovereign_kernel", "table": "inet",
             "chain": "selfdef-ring0",
             "match_expr": "ip protocol tcp",
             "disposition": "accept", "priority": 100,
             "packets": 10, "bytes": 640,
             "installed_at": "2027-01-15T08:00:00Z",
             "installed_by": "operator-fp",
             "signature": "sig"},
        ],
        "signature": "",
    }
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "rules.json")
        with open(p, "w") as f:
            json.dump(artifact, f)
        out = _run_reader(
            "selfdef-rules-mirror.py",
            "SOVEREIGN_OS_SELFDEF_RULES_MIRROR",
            p,
        )
    assert out["mirror_status"] == "online"
    assert [r["rule_id"] for r in out["rules"]] == ["rule-001"]
    assert out["rules"][0]["ring"] == "sovereign_kernel"
    assert out["rules"][0]["disposition"] == "accept"
    assert out["summaries"][0]["rule_count"] == 1


# ------------------------------------------------------------------ TUI layout

def test_m060_tui_layout_producer_consumer_contract():
    """selfdef-tui-mirror's canonical_snapshot() output is consumed
    cleanly by sovereign-os selfdef-tui-mirror.py (MS007 typed-mirror
    crate, R10141 4-panel layout, R10298 doctrine verbatim)."""
    artifact = {
        "schema_version": "1.0.0",
        "tui_build_version": "0.1.0",
        "doctrine": "A dashboard should not show vanity graphs",
        "captured_at": "2027-01-15T08:00:00Z",
        "panels": [
            {
                "kind": "rules", "quadrant": "top_left",
                "title": "Rules · Ring 0..4 · selfdef-rules-mirror",
                "source_mirror": "selfdef-rules-mirror",
                "columns": [
                    {"header": "ring", "field": "ring", "width": 12, "right_align": False},
                ],
                "key_bindings": [
                    {"key": "j/k", "action": "cursor down/up", "mutating": False},
                ],
                "min_authority": "l0_observe",
                "refresh_ms": 30000,
                "signature": "",
            },
            {
                "kind": "grants", "quadrant": "top_right",
                "title": "Grants · selfdef-grants-mirror",
                "source_mirror": "selfdef-grants-mirror",
                "columns": [
                    {"header": "grant_id", "field": "grant_id", "width": 14, "right_align": False},
                ],
                "key_bindings": [
                    {"key": "i", "action": "copy issue cmd", "mutating": False},
                ],
                "min_authority": "l0_observe",
                "refresh_ms": 5000,
                "signature": "",
            },
            {
                "kind": "quarantine", "quadrant": "bottom_left",
                "title": "Quarantine · selfdef-quarantine-mirror",
                "source_mirror": "selfdef-quarantine-mirror",
                "columns": [
                    {"header": "quarantine_id", "field": "quarantine_id", "width": 16, "right_align": False},
                ],
                "key_bindings": [
                    {"key": "R", "action": "copy release cmd", "mutating": False},
                ],
                "min_authority": "l0_observe",
                "refresh_ms": 5000,
                "signature": "",
            },
            {
                "kind": "authority", "quadrant": "bottom_right",
                "title": "Authority · selfdef-profile-mirror",
                "source_mirror": "selfdef-profile-mirror",
                "columns": [
                    {"header": "field", "field": "field", "width": 20, "right_align": False},
                ],
                "key_bindings": [
                    {"key": "p", "action": "copy profile switch", "mutating": False},
                ],
                "min_authority": "l0_observe",
                "refresh_ms": 30000,
                "signature": "",
            },
        ],
        "global_keys": [
            {"key": "Tab", "action": "focus next panel", "mutating": False},
            {"key": "?", "action": "help overlay", "mutating": False},
            {"key": "q", "action": "quit", "mutating": False},
        ],
        "signature": "",
    }
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "tui.json")
        with open(p, "w") as f:
            json.dump(artifact, f)
        out = _run_reader(
            "selfdef-tui-mirror.py",
            "SOVEREIGN_OS_SELFDEF_TUI_MIRROR",
            p,
        )
    assert out["mirror_status"] == "online"
    assert out["doctrine"] == "A dashboard should not show vanity graphs"
    assert [p["kind"] for p in out["panels"]] == ["rules", "grants", "quarantine", "authority"]
    # R10212: no panel keybinding may be mutating.
    for panel in out["panels"]:
        for kb in panel["key_bindings"]:
            assert kb["mutating"] is False, (
                f"panel {panel['kind']} kb {kb['key']} must not be mutating"
            )
    # Global keys ship help + quit at minimum.
    global_keys = {kb["key"] for kb in out["global_keys"]}
    assert "?" in global_keys
    assert "q" in global_keys


# ------------------------------------------------------------------ CLI schema

def test_m060_cli_schema_producer_consumer_contract():
    """selfdef-cli-mirror's CliMirrorSnapshot is consumed cleanly by
    sovereign-os selfdef-cli-mirror.py (MS007 typed-mirror crate,
    R10281 + R10297 doctrine verbatim 'Fullstack at the edges')."""
    artifact = {
        "schema_version": "1.0.0",
        "cli_build_version": "0.1.0",
        "doctrine": "Fullstack at the edges",
        "captured_at": "2027-01-15T08:00:00Z",
        "summaries": [
            {"effect": "read_only", "count": 120},
            {"effect": "diagnostic", "count": 6},
            {"effect": "commit", "count": 11},
            {"effect": "destructive", "count": 2},
        ],
        "subcommands": [
            {
                "path": "grants.show",
                "help_summary": "Show active grants",
                "help_long": "Show active grants (read-only).",
                "effect_class": "read_only",
                "min_authority": "l0_observe",
                "args": [
                    {"name": "json", "kind": "flag", "required": False,
                     "help": "", "default": None, "allowed_values": []},
                ],
                "mirror": "selfdef-grants-mirror",
                "requires_signature": False,
                "p95_target_ms": 250,
                "signature": "",
            },
            {
                "path": "grants.issue",
                "help_summary": "Issue a grant (MS003 signed)",
                "help_long": "Issue a grant. Requires MS003 signature.",
                "effect_class": "commit",
                "min_authority": "l5_commit",
                "args": [
                    {"name": "scope", "kind": "option", "required": True,
                     "help": "", "default": None, "allowed_values": []},
                ],
                "mirror": "selfdef-grants-mirror",
                "requires_signature": True,
                "p95_target_ms": 1500,
                "signature": "",
            },
            {
                "path": "quarantine.forfeit",
                "help_summary": "Forfeit a quarantined item (DESTRUCTIVE)",
                "help_long": "Forfeit + purge. Irreversible.",
                "effect_class": "destructive",
                "min_authority": "l5_commit",
                "args": [],
                "mirror": "selfdef-quarantine-mirror",
                "requires_signature": True,
                "p95_target_ms": 5000,
                "signature": "",
            },
        ],
        "signature": "",
    }
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "cli.json")
        with open(p, "w") as f:
            json.dump(artifact, f)
        out = _run_reader(
            "selfdef-cli-mirror.py",
            "SOVEREIGN_OS_SELFDEF_CLI_MIRROR",
            p,
        )
        # `mutating` filter verb returns only the signature-required.
        # MUST run inside the with-block — the tempdir is gone after it.
        out_mut = _run_reader(
            "selfdef-cli-mirror.py",
            "SOVEREIGN_OS_SELFDEF_CLI_MIRROR",
            p,
            cmd="mutating",
        )
    assert out["mirror_status"] == "online"
    assert out["doctrine"] == "Fullstack at the edges"
    paths = {s["path"] for s in out["subcommands"]}
    assert paths == {"grants.show", "grants.issue", "quarantine.forfeit"}
    # Effect-class wire-fidelity: each verb projected with its
    # canonical effect_class.
    by_path = {s["path"]: s for s in out["subcommands"]}
    assert by_path["grants.show"]["effect_class"] == "read_only"
    assert by_path["grants.issue"]["effect_class"] == "commit"
    assert by_path["quarantine.forfeit"]["effect_class"] == "destructive"
    # requires_signature lock — the 2 mutation verbs must carry it.
    assert by_path["grants.show"]["requires_signature"] is False
    assert by_path["grants.issue"]["requires_signature"] is True
    assert by_path["quarantine.forfeit"]["requires_signature"] is True
    # `mutating` filter verb returned only the signature-required.
    mut_paths = {s["path"] for s in out_mut}
    assert mut_paths == {"grants.issue", "quarantine.forfeit"}


# ------------------------------------------------------------------ all 10 in one

def test_m060_all_ten_mirrors_online_when_artifacts_present():
    """Sanity: all 10 reader scripts (D-02/12/13/14/15/16/17/18 plus the
    MS007 TUI-layout + CLI-schema) ship in `scripts/mirror/` and form
    the complete cross-repo consumer set."""
    assert (READER_DIR / "selfdef-profile-mirror.py").is_file()
    assert (READER_DIR / "selfdef-rules-mirror.py").is_file()
    assert (READER_DIR / "selfdef-grants-mirror.py").is_file()
    assert (READER_DIR / "selfdef-capability-mirror.py").is_file()
    assert (READER_DIR / "selfdef-sandbox-mirror.py").is_file()
    assert (READER_DIR / "selfdef-audit-mirror.py").is_file()
    assert (READER_DIR / "selfdef-quarantine-mirror.py").is_file()
    assert (READER_DIR / "selfdef-trust-score-mirror.py").is_file()
    assert (READER_DIR / "selfdef-tui-mirror.py").is_file()
    assert (READER_DIR / "selfdef-cli-mirror.py").is_file()
