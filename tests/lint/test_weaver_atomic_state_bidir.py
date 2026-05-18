"""R420 (E10.M64) — Weaver atomic-state ↔ profile tank/context dataset
10th bidirectional-consistency lint (path + sync mode + state-fabric files).

Extends R387-R419 + R393/R396 operational-artifact pinning to the
operator-named state-fabric durability chain:
  scripts/weaver/atomic-state.py  (the writer)
  profiles/sain-01.yaml           (declares tank/context ZFS dataset)

R393 covered atomic-state.py verbatim § 21.1 semantics (O_DIRECT + O_SYNC
+ atomic rename + 4 state-fabric files). R396 covered ZFS dataset
verbatim spec (recordsize + compression + copies). R420 closes the
bidirectional consistency between the WRITER and the STORAGE LAYER it
writes to.

Master spec § 21 + § 7.2 verbatim:
  - Writer = scripts/weaver/atomic-state.py
  - Target = /mnt/vault/context/{IDENTITY,SOUL,AGENTS,CLAUDE}.md
  - Storage = ZFS dataset tank/context with:
      - sync=always   (master spec § 21 'lockless loopback write sequence')
      - copies=2      (state-fabric durability — R393)
      - recordsize=16k

10th bidirectional-consistency lint:
  WRITER (atomic-state.py) assumes tank/context has sync=always
  STORAGE (sain-01.yaml) MUST declare sync=always on tank/context
  Drift between the two = writer assumes durability that storage
  doesn't actually provide = silent state-fabric corruption window
  on power loss / kernel panic.

The 4 state-fabric files (operator-named § 7.1):
  IDENTITY.md / SOUL.md / AGENTS.md / CLAUDE.md
This list MUST match between writer + storage layer.

If a future agent silently:
  - removes sync=always from sain-01.yaml = writer thinks every write
    is durable but ZFS may delay-flush = power-loss data loss
  - removes copies=2 from sain-01.yaml = writer thinks state-fabric
    has redundancy but it doesn't = single-bit-rot corrupts
  - renames a state-fabric file (e.g., AGENTS.md → AGENTS_v2.md) =
    writer rejects the new name; tank/context retains stale file
…the § 21 state-fabric durability chain silently breaks.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
ATOMIC_STATE = REPO_ROOT / "scripts" / "weaver" / "atomic-state.py"
SAIN01_PROFILE = REPO_ROOT / "profiles" / "sain-01.yaml"


def _read(p: Path) -> str:
    assert p.is_file(), f"missing {p}"
    return p.read_text(encoding="utf-8")


def _load_profile() -> dict:
    return yaml.safe_load(_read(SAIN01_PROFILE)) or {}


def _tank_context_dataset() -> dict | None:
    """Return the tank/context dataset declaration from the profile."""
    data = _load_profile()
    datasets = (
        (data.get("hardware") or {})
        .get("storage", {})
        .get("datasets") or []
    )
    return next(
        (d for d in datasets if d.get("name") == "tank/context"),
        None,
    )


# --- Structural ---


def test_atomic_state_file_exists():
    assert ATOMIC_STATE.is_file(), f"missing {ATOMIC_STATE}"


def test_sain01_has_tank_context_dataset():
    """Profile MUST declare tank/context dataset (operator-named
    state-fabric storage)."""
    ds = _tank_context_dataset()
    assert ds is not None, (
        "profiles/sain-01.yaml missing tank/context dataset declaration "
        "(operator-named state-fabric storage location)"
    )


# --- 10th bidirectional-consistency lint: sync=always ---


def test_bidirectional_sync_always():
    """10th bidirectional-consistency lint:
      WRITER (atomic-state.py) header says 'tank/context has sync=always'
      STORAGE (sain-01.yaml) MUST declare sync=always on tank/context

    Drift = writer assumes durability that storage doesn't actually
    provide = power-loss data loss window."""
    body = _read(ATOMIC_STATE)
    # The writer's HEADER references the expectation
    assert "sync=always" in body, (
        "atomic-state.py missing 'sync=always' reference in header "
        "(operator-discovery — drift loses the WHY of the storage "
        "expectation)"
    )
    # The storage declares it
    ds = _tank_context_dataset()
    assert ds is not None, "tank/context dataset missing in profile"
    assert ds.get("sync") == "always", (
        f"profiles/sain-01.yaml tank/context sync={ds.get('sync')!r} "
        f"!= 'always' (BIDIRECTIONAL CONSISTENCY VIOLATION: writer "
        f"assumes sync=always but storage doesn't provide it = silent "
        f"power-loss data loss window)"
    )


def test_bidirectional_copies_2():
    """State-fabric durability invariant: tank/context copies=2.
    Drift to copies=1 = single-bit-rot can corrupt state files."""
    ds = _tank_context_dataset()
    assert ds is not None, "tank/context dataset missing in profile"
    assert ds.get("copies") == 2, (
        f"profiles/sain-01.yaml tank/context copies={ds.get('copies')!r} "
        f"!= 2 (state-fabric durability violation — single bit rot "
        f"corrupts operator's state)"
    )


# --- Bidirectional consistency: 4 state-fabric files ---


def test_bidirectional_four_state_fabric_files():
    """The 4 operator-named state-fabric files MUST match between
    writer (STATE_FILES tuple) and master spec § 7.1 verbatim list.

    Drift adding a 5th file = writer can target the new file but
    storage layer + recordsize tuning was sized for 4 files only.
    Drift dropping one = writer rejects the operator-named file."""
    body = _read(ATOMIC_STATE)
    expected = ["IDENTITY.md", "SOUL.md", "AGENTS.md", "CLAUDE.md"]
    for name in expected:
        assert name in body, (
            f"atomic-state.py missing state-fabric file {name!r} "
            f"(operator-named § 7.1 verbatim 4-file set)"
        )
    # The STATE_FILES tuple MUST have exactly 4 entries
    tuple_match = re.search(
        r"STATE_FILES\s*=\s*\(([^)]+)\)",
        body,
    )
    assert tuple_match, "atomic-state.py missing STATE_FILES tuple"
    tuple_contents = tuple_match.group(1)
    # Count quoted strings in the tuple
    files = re.findall(r'"([^"]+\.md)"', tuple_contents)
    assert len(files) == 4, (
        f"atomic-state.py STATE_FILES has {len(files)} entries "
        f"(expected exactly 4 per § 7.1; got {files})"
    )


# --- § 21 verbatim writer semantics ---


def test_writer_uses_o_direct():
    """§ 21.1 verbatim: O_DIRECT bypasses volatile page cache.
    Drift to O_RDWR alone = writes can sit in page cache = power-loss
    data loss window even with sync=always at ZFS layer."""
    body = _read(ATOMIC_STATE)
    assert "O_DIRECT" in body, (
        "atomic-state.py missing O_DIRECT flag (§ 21.1 verbatim — "
        "drift = writes sit in volatile page cache)"
    )


def test_writer_uses_o_sync():
    """§ 21.1 verbatim: O_SYNC synchronous write commit."""
    body = _read(ATOMIC_STATE)
    assert "O_SYNC" in body, (
        "atomic-state.py missing O_SYNC flag (§ 21.1 verbatim)"
    )


def test_writer_uses_o_trunc():
    """§ 21.1 verbatim: O_TRUNC for atomic-rename source. Drift =
    partial overwrite if old content was longer than new."""
    body = _read(ATOMIC_STATE)
    assert "O_TRUNC" in body, (
        "atomic-state.py missing O_TRUNC flag (§ 21.1 verbatim — "
        "drift = partial overwrite on short writes)"
    )


def test_writer_uses_atomic_rename():
    """§ 21.1 LOAD-BEARING guarantee: os.rename() is the atomic-commit
    primitive. Drift to a copy-and-delete pattern = readers see partial
    state."""
    body = _read(ATOMIC_STATE)
    assert "os.rename" in body, (
        "atomic-state.py missing os.rename atomic commit "
        "(§ 21.1 verbatim — drift = readers see partial state)"
    )


def test_writer_4k_alignment_for_o_direct():
    """§ 21.1 verbatim: 'Memory-aligned encoding adjustment for NVMe
    physical block alignment (4K boundary)'. Drift to unaligned writes
    = O_DIRECT rejects with EINVAL on strict filesystems."""
    body = _read(ATOMIC_STATE)
    has_4k = "4096" in body or "4K" in body
    assert has_4k, (
        "atomic-state.py missing 4096/4K alignment (§ 21.1 verbatim "
        "NVMe physical block alignment)"
    )


def test_writer_handles_o_direct_fallback():
    """Defense-in-depth: tmpfs / overlayfs in containers don't support
    O_DIRECT. Writer MUST fall back to O_SYNC alone (operator-discovery:
    state-fabric works even in test containers)."""
    body = _read(ATOMIC_STATE)
    has_fallback = (
        "_write_sync" in body
        or "fall back" in body.lower()
        or "fallback" in body.lower()
    )
    assert has_fallback, (
        "atomic-state.py missing O_DIRECT fallback path "
        "(drift = tests/containers fail on every write attempt)"
    )


def test_writer_emits_atomic_write_total_metric():
    """SDD-016 verbatim: sovereign_os_weaver_atomic_write_total
    counter (operator-discovery: how many state writes per file)."""
    body = _read(ATOMIC_STATE)
    assert "sovereign_os_weaver_atomic_write_total" in body, (
        "atomic-state.py missing sovereign_os_weaver_atomic_write_total "
        "metric (SDD-016 — state-fabric write observability)"
    )


def test_writer_emits_last_timestamp_per_file():
    """SDD-016 verbatim: last_timestamp gauge per file (operator-
    discoverable: when was each state file last written)."""
    body = _read(ATOMIC_STATE)
    assert "sovereign_os_weaver_atomic_write_last_timestamp" in body, (
        "atomic-state.py missing last_timestamp gauge "
        "(operator-discovery — staleness detection)"
    )


def test_writer_documents_master_spec_section_21():
    """Operator-discovery: header MUST reference § 21 (master spec
    Weaver Execution section)."""
    body = _read(ATOMIC_STATE)
    assert "§ 21" in body or "section 21" in body.lower(), (
        "atomic-state.py missing master spec § 21 reference "
        "(operator-discovery context)"
    )


# --- /mnt/vault/context binding ---


def test_writer_default_context_dir():
    """Operator-named state-fabric mount: /mnt/vault/context. Drift =
    writes land somewhere other than the tank/context ZFS dataset."""
    body = _read(ATOMIC_STATE)
    assert "/mnt/vault/context" in body, (
        "atomic-state.py missing /mnt/vault/context default path "
        "(operator-named state-fabric mount; drift = writes land "
        "off the tank/context dataset = no sync=always benefit)"
    )


def test_dry_run_env_var_supported():
    """Operator-discoverable: WEAVER_DRY_RUN env var for previewing
    writes (parallel to SOVEREIGN_OS_DRY_RUN)."""
    body = _read(ATOMIC_STATE)
    assert "WEAVER_DRY_RUN" in body or "DRY_RUN" in body, (
        "atomic-state.py missing WEAVER_DRY_RUN env handling"
    )
