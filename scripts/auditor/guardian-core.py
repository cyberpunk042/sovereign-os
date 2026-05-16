#!/usr/bin/env python3
"""
scripts/auditor/guardian-core.py — The Native Guardian Event Loop.

Master spec § 10 (verbatim):

  "To replace the legacy Windows-centric SecureToast.ps1 concept without
   introducing visual or network bloat, we introduce a lightweight,
   native Linux event supervisor. This daemon listens to the local
   Tetragon eBPF UNIX socket and acts as an autonomous circuit breaker."

Master spec § 17 names this The Auditor (Immutable Gatekeeper) within
The Genesis Trinity — always-on, kernel-driven, podman-kill-armed.

The script:
  1. Tails /var/run/tetragon/tetragon.events (JSON line stream from
     the kernel eBPF filter)
  2. Parses each event; on policy trigger labeled SIGKILL or any
     process-action match, immediately runs `podman kill <container>`
  3. Appends a structured line to /mnt/vault/context/security_audit.log
     (the master spec § 7.1 atomic append-only path)
  4. Emits Layer B counters per neutralization

Master spec § 21.1 dictates atomic-append semantics for security_audit
.log — we honor that here via O_APPEND on a single file descriptor; the
log file lives on tank/context with sync=always per master spec § 7.2.

Env vars (all overridable):
  GUARDIAN_SOCKET_PATH       (default: /var/run/tetragon/tetragon.events)
  GUARDIAN_AUDIT_LOG         (default: /mnt/vault/context/security_audit.log)
  GUARDIAN_PODMAN_BIN        (default: podman)
  GUARDIAN_DRY_RUN           (default: unset; set to 1 = parse only,
                              do not kill, do not write)
  SOVEREIGN_OS_METRICS_DIR   (default: /var/lib/node_exporter/textfile_collector)

Layer B metrics:
  sovereign_os_auditor_neutralization_total{result}
  sovereign_os_auditor_event_parse_total{outcome}
  sovereign_os_auditor_last_neutralization_timestamp
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time

SOCKET_PATH = os.environ.get(
    "GUARDIAN_SOCKET_PATH", "/var/run/tetragon/tetragon.events"
)
AUDIT_LOG = os.environ.get(
    "GUARDIAN_AUDIT_LOG", "/mnt/vault/context/security_audit.log"
)
PODMAN_BIN = os.environ.get("GUARDIAN_PODMAN_BIN", "podman")
DRY_RUN = bool(os.environ.get("GUARDIAN_DRY_RUN"))

METRICS_DIR = os.environ.get(
    "SOVEREIGN_OS_METRICS_DIR",
    "/var/lib/node_exporter/textfile_collector",
)


def _emit_metric(name: str, value: float, labels: str = "") -> None:
    """Best-effort textfile-collector emit (Layer B per SDD-016)."""
    if DRY_RUN:
        sys.stderr.write(f"  would emit: {name}{{{labels}}} {value}\n")
        return
    try:
        os.makedirs(METRICS_DIR, exist_ok=True)
        prom_path = os.path.join(METRICS_DIR, "sovereign-os-auditor.prom")
        line = (
            f"{name}{{{labels}}} {value}\n" if labels else f"{name} {value}\n"
        )
        with open(prom_path, "a") as f:
            f.write(line)
    except OSError:
        pass


def alert_and_neutralize(
    container_id: str, process_name: str, violated_syscall: str
) -> None:
    """Master spec § 10.1 verbatim hot path with operator-facing
    observability extensions."""
    msg = (
        f"[CRITICAL] PERIMETER VIOLATION: Container {container_id} "
        f"executed {violated_syscall} via {process_name}"
    )
    print(msg, flush=True)

    if DRY_RUN:
        sys.stderr.write(
            f"  DRY-RUN: would `{PODMAN_BIN} kill {container_id}` "
            f"and append to {AUDIT_LOG}\n"
        )
        _emit_metric(
            "sovereign_os_auditor_neutralization_total", 1,
            'result="dry-run"',
        )
        return

    # 1. Immediate Native Kill Sequence (master spec § 10.1 verbatim)
    kill_result = "success"
    if container_id:
        try:
            subprocess.run(
                [PODMAN_BIN, "kill", container_id],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            kill_result = "kill-failed"
    else:
        kill_result = "no-container-id"

    # 2. Append to Atomic Sovereign Logs (master spec § 10.1 verbatim
    # path; tank/context sync=always per master spec § 7.2)
    try:
        os.makedirs(os.path.dirname(AUDIT_LOG), exist_ok=True)
        # O_APPEND guarantees atomic concatenation on POSIX for writes
        # smaller than PIPE_BUF — our line is well under that.
        fd = os.open(AUDIT_LOG, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            ts = time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime())
            line = (
                f"{ts} [VIOLATION] Neutralized {process_name} "
                f"({container_id}) attempting {violated_syscall} "
                f"[kill={kill_result}]\n"
            )
            os.write(fd, line.encode("utf-8"))
        finally:
            os.close(fd)
    except OSError as e:
        sys.stderr.write(f"  audit log append failed: {e}\n")
        kill_result = f"{kill_result}+audit-log-fail"

    _emit_metric(
        "sovereign_os_auditor_neutralization_total", 1,
        f'result="{kill_result}"',
    )
    _emit_metric(
        "sovereign_os_auditor_last_neutralization_timestamp",
        int(time.time()),
        "",
    )


def parse_event(line: str) -> tuple[bool, dict]:
    """Returns (is_trigger, parsed_event). False + {} on bad JSON.

    Master spec § 10.1 verbatim trigger predicate:
      event.get('action') == 'SIGKILL' or 'process' in
      event.get('action', '').lower()
    """
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        return False, {}
    action = event.get("action", "")
    if action == "SIGKILL" or "process" in action.lower():
        return True, event
    return False, event


def neutralize_from_event(event: dict) -> None:
    """Master spec § 10.1 verbatim field extraction."""
    container_id = event.get("process", {}).get("docker", "")
    process_name = event.get("process", {}).get("binary", "")
    violated_syscall = event.get("syscall", {}).get("name", "sys_execve")
    alert_and_neutralize(container_id, process_name, violated_syscall)


def main() -> int:
    print("[*] Guardian Native Event Loop Active. "
          "Monitoring Sovereign Perimeter...", flush=True)
    print(f"  socket:    {SOCKET_PATH}", flush=True)
    print(f"  audit log: {AUDIT_LOG}", flush=True)
    print(f"  podman:    {PODMAN_BIN}", flush=True)
    if DRY_RUN:
        print("  DRY-RUN:   neutralize is logged but not executed",
              flush=True)

    if not os.path.exists(SOCKET_PATH):
        sys.stderr.write(
            f"[FATAL STRUCTURAL FRICTION] tetragon event stream not "
            f"found at {SOCKET_PATH}\n"
            f"  start tetragon.service first (master spec § 10.2 unit "
            f"declares After=tetragon.service Requires=tetragon.service)\n"
        )
        return 1

    try:
        with open(SOCKET_PATH, "r") as stream:
            for line in stream:
                line = line.strip()
                if not line:
                    continue
                is_trigger, event = parse_event(line)
                if not event:
                    _emit_metric(
                        "sovereign_os_auditor_event_parse_total", 1,
                        'outcome="bad-json"',
                    )
                    continue
                if is_trigger:
                    _emit_metric(
                        "sovereign_os_auditor_event_parse_total", 1,
                        'outcome="trigger"',
                    )
                    neutralize_from_event(event)
                else:
                    _emit_metric(
                        "sovereign_os_auditor_event_parse_total", 1,
                        'outcome="benign"',
                    )
    except KeyboardInterrupt:
        print("\n[*] Guardian shutdown requested.", flush=True)
        return 0
    except OSError as e:
        sys.stderr.write(f"[FATAL STRUCTURAL FRICTION] {e}\n")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
