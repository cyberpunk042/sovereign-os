"""R393 (E10.M37) — Weaver atomic-state operator-verbatim §21 content lint.

Extends R387-R392 operational-artifact pinning to the Trinity Weaver
side: `scripts/weaver/atomic-state.py` (master spec §21 Atomic State
Transition Protocol Python primitive).

Master spec §21.1 verbatim:
  - def commit_state_atomically(mutated_payload: str)
  - fd = os.open(TMP_CONTEXT_PATH,
                 os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_DIRECT | os.O_SYNC)
  - 4K boundary alignment for NVMe
  - os.rename(TMP_CONTEXT_PATH, CONTEXT_PATH) (atomic rename)
  - tmp + rename pattern guarantees no reader sees partial file

If a future agent silently changes the O_DIRECT|O_SYNC flag combo
or removes the tmp+rename pattern, atomic state transitions break
silently (multi-agent race conditions per operator §13 Q-02 verbatim).
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ATOMIC = REPO_ROOT / "scripts" / "weaver" / "atomic-state.py"


def _read_atomic() -> str:
    assert ATOMIC.is_file(), f"missing {ATOMIC}"
    return ATOMIC.read_text(encoding="utf-8")


def test_atomic_state_file_exists():
    assert ATOMIC.is_file(), f"missing {ATOMIC}"


def test_commit_state_atomically_function_present():
    """§21.1 verbatim function name: commit_state_atomically."""
    body = _read_atomic()
    assert "def commit_state_atomically" in body, (
        "atomic-state.py missing operator-verbatim §21.1 function name "
        "'commit_state_atomically'"
    )


def test_o_direct_flag_present():
    """§21.1 verbatim: 'Direct I/O to bypass volatile OS page caches'
    via O_DIRECT flag."""
    body = _read_atomic()
    assert "O_DIRECT" in body, (
        "atomic-state.py missing O_DIRECT flag (§21.1 verbatim — bypass "
        "page cache for atomic NVMe commit)"
    )


def test_o_sync_flag_present():
    """§21.1 verbatim: O_SYNC flag (synchronous write guarantees
    physical block commit before return)."""
    body = _read_atomic()
    assert "O_SYNC" in body, (
        "atomic-state.py missing O_SYNC flag (§21.1 verbatim — sync "
        "write to guarantee physical NVMe commit before return)"
    )


def test_o_wronly_o_creat_o_trunc_flags():
    """§21.1 verbatim full os.open flag combo:
       O_WRONLY | O_CREAT | O_TRUNC | O_DIRECT | O_SYNC"""
    body = _read_atomic()
    for flag in ("O_WRONLY", "O_CREAT", "O_TRUNC"):
        assert flag in body, (
            f"atomic-state.py missing {flag} flag (§21.1 verbatim full "
            f"flag combo)"
        )


def test_atomic_rename_pattern():
    """§21.1 verbatim: 'Atomic rename guarantees that no reader ever
    views a partially written file' — os.rename(TMP, FINAL) pattern."""
    body = _read_atomic()
    has_rename = "os.rename" in body or "Path" in body and "rename" in body
    assert has_rename, (
        "atomic-state.py missing os.rename atomic-rename pattern "
        "(§21.1 — 'no reader ever views a partially written file')"
    )


def test_4k_boundary_alignment_mentioned():
    """§21.1 verbatim: 'Memory-aligned encoding adjustment for NVMe
    physical block alignment (4K boundary)'."""
    body = _read_atomic()
    body_lower = body.lower()
    has_4k = "4k" in body_lower or "4096" in body
    assert has_4k, (
        "atomic-state.py missing 4K boundary alignment reference (§21.1 "
        "verbatim 'NVMe physical block alignment (4K boundary)')"
    )


def test_tmp_path_pattern():
    """§21.1 verbatim shows TMP_CONTEXT_PATH = '/mnt/vault/context/
    CLAUDE.md.tmp' — temp file then rename pattern."""
    body = _read_atomic()
    has_tmp = "tmp" in body.lower() or ".tmp" in body
    assert has_tmp, (
        "atomic-state.py missing tmp file pattern (§21.1 'TMP_CONTEXT_"
        "PATH' temp-file-then-rename)"
    )


def test_context_path_or_mount_vault_referenced():
    """§21.1 verbatim CONTEXT_PATH = '/mnt/vault/context/CLAUDE.md'.
    The /mnt/vault/context path family (or equivalent state-fabric
    path) MUST be referenced — operator's verbatim state-fabric mount
    point per §7.1."""
    body = _read_atomic()
    # Either /mnt/vault/context or some configurable equivalent
    has_path = ("/mnt/vault/context" in body
                 or "context" in body.lower()
                 or "STATE" in body)
    assert has_path, (
        "atomic-state.py missing /mnt/vault/context path reference "
        "(§21.1 + §7.1 state-fabric mount)"
    )


def test_no_silent_fsync_replacement():
    """Catches: agent silently replaces O_SYNC + O_DIRECT with
    fsync()-only — that's a WEAKER guarantee (page cache could still
    have stale data when fsync returns). §21.1 contract specifies
    O_DIRECT + O_SYNC flag combo, not fsync post-write."""
    body = _read_atomic()
    # If fsync appears WITHOUT O_DIRECT, that's a guarantee weakening
    if "fsync" in body.lower() and "O_DIRECT" not in body:
        raise AssertionError(
            "atomic-state.py uses fsync without O_DIRECT — §21.1 "
            "contract requires O_DIRECT|O_SYNC for direct page-cache "
            "bypass, not fsync post-write"
        )
