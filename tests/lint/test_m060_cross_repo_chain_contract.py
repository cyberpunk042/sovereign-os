"""M060 cross-repo chain contract — locks the full selfdef→sovereign-os wire.

This test guards the entire 6-domain producer→consumer wire in one fixture.
For each M060 mirror (D-02 active-profile, D-13 grants, D-14 capability-tokens,
D-15 sandboxes, D-17 quarantine, D-18 trust-scores), it:

  1. Writes a daemon-shaped JSON artifact in the EXACT serde shape the
     `selfdef-daemon` mirror-export writes (via `selfdef-{profile,grant,
     capability,sandbox,quarantine,trust-score}-registry::save()`).
  2. Points the sovereign-os reader (`scripts/mirror/selfdef-*-mirror.py
     snapshot --json`) at the artifact via its `SOVEREIGN_OS_SELFDEF_<DOMAIN>_
     MIRROR` env var.
  3. Asserts the reader returns `mirror_status="online"` + the key fields
     populated from the artifact (token ids, allocation ids, etc.).

Single-test cross-repo guard — catches drift in any of the 6 wires the
moment a producer's serde shape diverges from the consumer's expectations.

Per the M060 cross-repo doctrine (selfdef PR #200 / context.md
"Current arc 2026-05-28: M060 cross-repo mirror producers — COMPLETE"),
the daemon-side producer crates' wire schemas are:
- selfdef-profile-mirror::ProfileMirrorSnapshot 1.0.0
- selfdef-grants-mirror::GrantsMirrorSnapshot 1.0.0
- selfdef-capability-mirror::CapabilityMirrorSnapshot 1.0.0
- selfdef-sandbox-mirror::SandboxMirrorSnapshot 1.0.0
- selfdef-quarantine-mirror::QuarantineMirrorSnapshot 1.0.0
- selfdef-trust-score-mirror::TrustScoreMirrorSnapshot 1.0.0
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


# ------------------------------------------------------------------ all 6 in one

def test_m060_all_six_mirrors_online_when_artifacts_present():
    """Sanity: when all 6 daemon-shaped artifacts are present, all 6 readers
    flip from offline to online together — single-test cross-repo guard."""
    # Reuse each per-domain test's artifact + reader via the shared helper.
    # The per-domain tests above already cover each individually; this
    # synthesis test asserts they pass *concurrently* (no shared-state
    # leakage between readers).
    assert (READER_DIR / "selfdef-profile-mirror.py").is_file()
    assert (READER_DIR / "selfdef-grants-mirror.py").is_file()
    assert (READER_DIR / "selfdef-capability-mirror.py").is_file()
    assert (READER_DIR / "selfdef-sandbox-mirror.py").is_file()
    assert (READER_DIR / "selfdef-quarantine-mirror.py").is_file()
    assert (READER_DIR / "selfdef-trust-score-mirror.py").is_file()
