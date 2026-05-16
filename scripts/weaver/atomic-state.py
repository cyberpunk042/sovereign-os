#!/usr/bin/env python3
"""
scripts/weaver/atomic-state.py — Atomic State Transition Protocol.

Master spec § 21 (The Weaver Execution) verbatim:

  "To ensure that state adjustments across CLAUDE.md, SOUL.md, and
   IDENTITY.md happen without filesystem lag or concurrent write
   collisions, The Weaver executes a strict, lockless loopback write
   sequence on the ZFS layer."

This implements the master spec § 21.1 Python blueprint expanded to:
  - Handle ALL 4 state-fabric files (IDENTITY/SOUL/AGENTS/CLAUDE)
  - Use O_DIRECT + O_SYNC + O_TRUNC + atomic rename per the verbatim
    blueprint
  - Respect the master spec § 7.2 ZFS settings (caller's job; this
    primitive assumes tank/context has sync=always already)
  - 4K-aligned memory buffer for the O_DIRECT path

CLI interface (operator-runnable; also imported by other tools):
  atomic-state.py write <name> [--from-stdin | --from-file <path>]
    Atomically commit a payload to /mnt/vault/context/<name>.md
  atomic-state.py read <name>
    Read the current state file content
  atomic-state.py list
    Enumerate the 4 state-fabric files + their sizes + last-modified

Layer B metrics:
  sovereign_os_weaver_atomic_write_total{file,result}
  sovereign_os_weaver_atomic_write_bytes
  sovereign_os_weaver_atomic_write_last_timestamp{file}

Env vars (all overridable):
  WEAVER_CONTEXT_DIR     (default: /mnt/vault/context)
  WEAVER_DRY_RUN         (default: unset; set to 1 for dry-run)
"""

from __future__ import annotations

import argparse
import os
import sys
import time

CONTEXT_DIR = os.environ.get("WEAVER_CONTEXT_DIR", "/mnt/vault/context")
STATE_FILES = ("IDENTITY.md", "SOUL.md", "AGENTS.md", "CLAUDE.md")
DRY_RUN = bool(os.environ.get("WEAVER_DRY_RUN"))

# Layer B metric helpers (best-effort; lib unavailable in pure-python tests)
METRICS_DIR = os.environ.get(
    "SOVEREIGN_OS_METRICS_DIR",
    "/var/lib/node_exporter/textfile_collector",
)


def _emit_metric(name: str, value: float, labels: str = "") -> None:
    """Best-effort emit; ignore failures (this is a Layer B nicety,
    not a load-bearing path)."""
    if DRY_RUN:
        sys.stderr.write(f"  would emit: {name}{{{labels}}} {value}\n")
        return
    try:
        os.makedirs(METRICS_DIR, exist_ok=True)
        prom_path = os.path.join(METRICS_DIR, "sovereign-os-weaver-atomic-state.prom")
        line = f"{name}{{{labels}}} {value}\n" if labels else f"{name} {value}\n"
        tmp_path = prom_path + ".tmp"
        with open(tmp_path, "a") as f:
            f.write(line)
        # Atomic-ish append: in practice we just append; the .prom format
        # tolerates duplicates with the last value winning per scrape window.
        os.rename(tmp_path, prom_path) if not os.path.exists(prom_path) else None
        # If prom_path exists, we want to APPEND not replace:
        with open(prom_path, "a") as f:
            pass  # already done above via tmp; this is the fallback
    except OSError:
        pass


def commit_state_atomically(file_name: str, payload: bytes) -> None:
    """
    Master spec § 21.1 verbatim with operator-facing extensions:
      - Direct I/O bypasses volatile OS page caches (O_DIRECT)
      - Synchronous write guarantees physical block commit (O_SYNC)
      - 4K-aligned encoding for NVMe physical block alignment
      - Atomic rename guarantees no reader ever sees partial state
    """
    if file_name not in STATE_FILES:
        raise ValueError(
            f"unknown state file: {file_name!r}. "
            f"Allowed (master spec § 7.1): {', '.join(STATE_FILES)}"
        )

    context_path = os.path.join(CONTEXT_DIR, file_name)
    tmp_path = context_path + ".tmp"

    if DRY_RUN:
        sys.stderr.write(
            f"  DRY-RUN: would atomically write {len(payload)} bytes to {context_path}\n"
            f"           (via {tmp_path}, O_DIRECT|O_SYNC|O_TRUNC, atomic rename)\n"
        )
        _emit_metric(
            "sovereign_os_weaver_atomic_write_total", 1,
            f'file="{file_name}",result="dry-run"',
        )
        return

    os.makedirs(CONTEXT_DIR, exist_ok=True)

    # Pad payload to a 4K boundary for O_DIRECT alignment. Some filesystems
    # (notably ZFS with recordsize=16k) accept unaligned writes; some don't.
    # Master spec § 21.1 says "Memory-aligned encoding adjustment for NVMe
    # physical block alignment (4K boundary)" — implement that.
    BLOCK = 4096
    if len(payload) % BLOCK != 0:
        pad = BLOCK - (len(payload) % BLOCK)
        # Don't pad with null bytes inside markdown — keep content valid
        # by appending whitespace, then trim on read. Master spec is silent
        # on this detail; we choose markdown-safe trailing newlines.
        payload = payload + (b"\n" * pad)

    # Try O_DIRECT path; fall back to plain O_SYNC if the filesystem
    # rejects it (tmpfs / overlayfs in containers don't support O_DIRECT).
    # Master spec § 21.1 names O_DIRECT to bypass page cache; the spec's
    # intent (atomic commit) is preserved by the O_SYNC + atomic rename
    # regardless of whether O_DIRECT applies.
    def _write_direct() -> None:
        fd = os.open(
            tmp_path,
            os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_DIRECT | os.O_SYNC,
            0o600,
        )
        try:
            import mmap
            buf = mmap.mmap(-1, len(payload))
            try:
                buf.write(payload)
                os.write(fd, buf)
            finally:
                buf.close()
        finally:
            os.close(fd)

    def _write_sync() -> None:
        fd = os.open(
            tmp_path,
            os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_SYNC,
            0o600,
        )
        try:
            os.write(fd, payload)
        finally:
            os.close(fd)

    try:
        _write_direct()
    except (OSError, AttributeError):
        # O_DIRECT unsupported (tmpfs/overlayfs) or alignment rejected.
        # Clean up any zero-byte tmp_path left by a failed open before
        # falling back to the O_SYNC-only path.
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        _write_sync()

    # Atomic rename: master spec § 21.1's load-bearing guarantee
    os.rename(tmp_path, context_path)

    _emit_metric(
        "sovereign_os_weaver_atomic_write_total", 1,
        f'file="{file_name}",result="success"',
    )
    _emit_metric(
        "sovereign_os_weaver_atomic_write_bytes", len(payload),
        f'file="{file_name}"',
    )
    _emit_metric(
        "sovereign_os_weaver_atomic_write_last_timestamp", int(time.time()),
        f'file="{file_name}"',
    )


def read_state(file_name: str) -> bytes:
    if file_name not in STATE_FILES:
        raise ValueError(f"unknown state file: {file_name!r}")
    path = os.path.join(CONTEXT_DIR, file_name)
    if not os.path.exists(path):
        return b""
    with open(path, "rb") as f:
        # Strip the trailing padding we added on write
        data = f.read().rstrip(b"\n") + b"\n" if f else b""
    return data


def list_state() -> None:
    print(f"  context dir: {CONTEXT_DIR}")
    print()
    print(f"  {'FILE':<14} {'SIZE':>10}  {'MODIFIED'}")
    for name in STATE_FILES:
        path = os.path.join(CONTEXT_DIR, name)
        if os.path.exists(path):
            st = os.stat(path)
            size = st.st_size
            mtime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime))
            print(f"  {name:<14} {size:>10}  {mtime}")
        else:
            print(f"  {name:<14} {'(absent)':>10}  -")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Weaver atomic state transition (master spec § 21)",
    )
    sub = parser.add_subparsers(dest="cmd")

    p_write = sub.add_parser("write", help="atomic-commit a state file")
    p_write.add_argument("name", choices=STATE_FILES,
                         help="state file name (master spec § 7.1)")
    src = p_write.add_mutually_exclusive_group(required=True)
    src.add_argument("--from-stdin", action="store_true")
    src.add_argument("--from-file", type=str)

    p_read = sub.add_parser("read", help="read current state")
    p_read.add_argument("name", choices=STATE_FILES)

    sub.add_parser("list", help="enumerate state files")

    args = parser.parse_args()

    if args.cmd == "write":
        if args.from_stdin:
            payload = sys.stdin.buffer.read()
        else:
            with open(args.from_file, "rb") as f:
                payload = f.read()
        try:
            commit_state_atomically(args.name, payload)
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        except Exception as e:
            print(f"[FATAL STRUCTURAL FRICTION] {e}", file=sys.stderr)
            return 1
        if not DRY_RUN:
            print(f"committed {len(payload)} bytes → {CONTEXT_DIR}/{args.name}")
        return 0

    if args.cmd == "read":
        try:
            data = read_state(args.name)
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        sys.stdout.buffer.write(data)
        return 0

    if args.cmd == "list":
        list_state()
        return 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
