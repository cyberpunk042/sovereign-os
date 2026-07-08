"""M071 Atomic-State-Transition-Protocol contract lint.

Locks `config/execution/m071-atomic-state-transition.yaml` to the M071 spec: the
4-step Weaver write sequence (E0678-E0682), the POSIX flags (E0684), the
memory-aligned encoding (E0685), the atomic rename (E0686), and lockless loopback
(E0687) — including the verbatim error string (typo preserved). No minimization.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "execution" / "m071-atomic-state-transition.yaml"
MILESTONE = (REPO_ROOT / "backlog" / "milestones" /
             "M071-atomic-state-transition-protocol-weaver-execution.md")


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M071"


def test_state_files_three():
    assert _c()["state_files"] == ["CLAUDE.md", "SOUL.md", "IDENTITY.md"]
    assert _c()["python_primitive"] == "commit_state_atomically(mutated_payload)"


def test_four_step_write_sequence():
    ws = _c()["write_sequence"]
    assert [x["step"] for x in ws] == [1, 2, 3, 4]
    names = [x["name"] for x in ws]
    assert names == ["Read Atomic Input", "Process State Mutation",
                     "Write via O_DIRECT / POSIX AIO", "Broadcast State Synced"]


def test_step2_avx512_pinned_and_signed():
    step2 = next(x for x in _c()["write_sequence"] if x["step"] == 2)
    assert "AVX-512 pinned" in step2["detail"] and "MS003" in step2["detail"]


def test_step3_targets_tank_context_sync_always():
    step3 = next(x for x in _c()["write_sequence"] if x["step"] == 3)
    assert "tank/context" in step3["detail"] and "sync=always" in step3["detail"]


def test_posix_flags_verbatim():
    assert _c()["posix_flags"]["flags"] == ["O_WRONLY", "O_CREAT", "O_TRUNC",
                                            "O_DIRECT", "O_SYNC"]


def test_atomic_rename_no_partial():
    ar = _c()["atomic_rename"]
    assert ar["call"] == "os.rename(TMP_CONTEXT_PATH, CONTEXT_PATH)"
    assert ar["guarantee"] == "no reader ever sees partial"


def test_lockless_loopback_zfs_ordering():
    assert "ZFS sync=always provides ordering" in _c()["lockless_loopback"]


def test_error_message_verbatim_typo_preserved():
    # The spec's error string contains the typo "STRUCURAL" (not STRUCTURAL);
    # per "no invention / verbatim" it is preserved exactly.
    assert _c()["error_message"]["fatal"] == "[FATAL STRUCURAL FRICTION] Atomic state transaction failed"


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M01173", "M01174", "M01176", "M01179", "M01180", "M01181", "M01185"):
        assert mod in body, f"{mod} not in the M071 milestone (must trace to spec)"
