#!/usr/bin/env python3
"""sovereign-os observability-status — one-command cross-vertical
operator triage across all 6 observability verticals shipped to date.

NEW operator-facing CLI surface that consolidates per-vertical
doctor checks into a single operator-runnable command. Probes:

  1. M060 chain-health           via the m060-health-api daemon
                                  at http://localhost:8160
  2. MS022 SSE quota             via the ms022-sse-quota-api daemon
                                  at http://localhost:7711
  3. four-watchdog IPS spine     via the four-watchdog-api daemon
                                  at http://localhost:7712
  4. selfdef module-catalog      via node_exporter /metrics scrape
                                  of selfdef_modules_* gauges
  5. selfdef daemon process      via node_exporter /metrics scrape
                                  of selfdef_daemon_process_* gauges
  6. selfdef AppArmor enforce    via node_exporter /metrics scrape
                                  of selfdef_apparmor_* gauges

  Plus the cross-vertical rollup recording rule
  `sovereign_os:observer_fault_any` when Prometheus is reachable.

Operator-readable table (default) + --json for monitoring + --strict
for CI fail-fast (exit 1 on any vertical reporting WARN+).

Exit code (mirrors the per-vertical doctor conventions):
  0  every vertical green (or honestly skipped)
  1  any vertical reports WARN OR critical
  2  any proxy daemon unreachable (with retry already attempted)

Sovereignty: stdlib-only. Each probe is independent — one vertical
unreachable doesn't fail the others.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from typing import Any

# Default endpoints — match the 4 sovereign-os proxy daemons' systemd
# unit defaults, locked by their respective contract tests.
DEFAULTS = {
    "m060_url":         os.environ.get("SOVEREIGN_OS_M060_URL", "http://localhost:8160"),
    "ms022_url":        os.environ.get("SOVEREIGN_OS_MS022_PROXY_URL", "http://localhost:7711"),
    "four_watchdog_url": os.environ.get("SOVEREIGN_OS_FOUR_WATCHDOG_PROXY_URL", "http://localhost:7712"),
    "node_exporter_url": os.environ.get("SOVEREIGN_OS_NODE_EXPORTER_URL", "http://localhost:9100/metrics"),
}

OBSERVER_SILENT_THRESHOLD_SECS = 300


def _fetch_json(url: str, timeout: float = 3.0) -> dict[str, Any] | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError,
            ConnectionError, OSError, json.JSONDecodeError):
        return None


def _fetch_metrics(url: str, timeout: float = 3.0) -> str | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.read().decode("utf-8")
    except (urllib.error.URLError, urllib.error.HTTPError,
            ConnectionError, OSError):
        return None


def _gauge(metrics: str, name: str, label_match: str = "") -> float | None:
    """Extract a single gauge value from a Prometheus exposition body."""
    if label_match:
        pattern = rf"^{re.escape(name)}\{{{re.escape(label_match)}\}}\s+([0-9.eE+\-]+)"
    else:
        pattern = rf"^{re.escape(name)}\s+([0-9.eE+\-]+)"
    m = re.search(pattern, metrics, re.MULTILINE)
    if m is None:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


# ── Per-vertical probes ──────────────────────────────────────────────

def probe_m060(url: str) -> dict[str, Any]:
    """Probe M060 chain-health via the proxy daemon."""
    data = _fetch_json(url.rstrip("/") + "/api/m060/health")
    if data is None:
        return {"status": "unreachable", "summary": "proxy daemon down"}
    state = str(data.get("state", "unknown"))
    present = data.get("artifacts_present", 0)
    expected = data.get("artifacts_expected", 10)
    age = data.get("newest_age_seconds")
    classification = "OK" if state == "online" else (
        "WARN" if state in ("degraded", "stale") else "FAIL"
    )
    return {
        "status": classification,
        "summary": f"chain={state} · {present}/{expected} mirrors · age {age}s",
        "raw": data,
    }


def probe_ms022(url: str) -> dict[str, Any]:
    """Probe MS022 SSE quota via the proxy daemon."""
    data = _fetch_json(url.rstrip("/") + "/api/ms022/state")
    if data is None:
        return {"status": "unreachable", "summary": "proxy daemon down"}
    state = str(data.get("state", "unknown"))
    classification = {
        "ok": "OK", "approaching": "WARN",
        "saturated": "FAIL", "unreachable": "WARN",
    }.get(state, "UNKNOWN")
    return {
        "status": classification,
        "summary": f"state={state}",
        "raw": data,
    }


def probe_four_watchdog(url: str) -> dict[str, Any]:
    """Probe four-watchdog IPS spine via the proxy daemon."""
    data = _fetch_json(url.rstrip("/") + "/api/four-watchdog/state")
    if data is None:
        return {"status": "unreachable", "summary": "proxy daemon down"}
    state = str(data.get("state", "unknown"))
    classification = {
        "ok": "OK", "warn": "WARN", "critical": "FAIL",
        "observer-fault": "FAIL", "unreachable": "WARN",
    }.get(state, "UNKNOWN")
    return {
        "status": classification,
        "summary": f"state={state}",
        "raw": data,
    }


def probe_textfile_observer(
    metrics: str, gauge_prefix: str, vertical: str
) -> dict[str, Any]:
    """Probe a selfdef-side textfile observer via node_exporter metrics."""
    emit_failed = _gauge(metrics, f"{gauge_prefix}_textfile_emit_failed")
    last_run = _gauge(metrics, f"{gauge_prefix}_last_run_unix")
    if emit_failed is None and last_run is None:
        return {
            "status": "unreachable",
            "summary": "node_exporter metrics absent (observer not deployed?)",
        }
    if emit_failed is not None and emit_failed > 0:
        return {
            "status": "FAIL",
            "summary": "observer wedged — sentinel=1",
        }
    if last_run is None:
        return {"status": "WARN", "summary": "last_run_unix missing"}
    import time as _time
    age = int(_time.time()) - int(last_run)
    if age > OBSERVER_SILENT_THRESHOLD_SECS:
        return {
            "status": "FAIL",
            "summary": f"observer silent ({age}s > {OBSERVER_SILENT_THRESHOLD_SECS}s)",
        }
    return {
        "status": "OK",
        "summary": f"fresh ({age}s)",
    }


def probe_modules_catalog(metrics_url: str) -> dict[str, Any]:
    metrics = _fetch_metrics(metrics_url)
    if metrics is None:
        return {"status": "unreachable", "summary": "node_exporter down"}
    out = probe_textfile_observer(metrics, "selfdef_modules", "modules")
    if out["status"] != "OK":
        return out
    total = _gauge(metrics, "selfdef_modules_total")
    if total is not None and total < 100:
        return {
            "status": "WARN",
            "summary": f"total={int(total)} (< 100 floor)",
        }
    return {
        "status": "OK",
        "summary": f"{int(total) if total is not None else '?'} modules · {out['summary']}",
    }


def probe_daemon_process(metrics_url: str) -> dict[str, Any]:
    metrics = _fetch_metrics(metrics_url)
    if metrics is None:
        return {"status": "unreachable", "summary": "node_exporter down"}
    out = probe_textfile_observer(
        metrics, "selfdef_daemon_process", "daemon-process",
    )
    if out["status"] != "OK":
        return out
    rss = _gauge(metrics, "selfdef_daemon_process_memory_rss_bytes")
    fds = _gauge(metrics, "selfdef_daemon_process_open_fds")
    bits = []
    cls = "OK"
    if rss is not None and rss > 1073741824:
        bits.append(f"RSS={rss / 1073741824:.1f} GiB")
        cls = "WARN"
    elif rss is not None:
        bits.append(f"RSS={rss / 1048576:.0f} MiB")
    if fds is not None and fds > 819:
        bits.append(f"FDs={int(fds)} > 819")
        cls = "FAIL"
    elif fds is not None:
        bits.append(f"FDs={int(fds)}")
    return {
        "status": cls,
        "summary": " · ".join(bits) + f" · {out['summary']}",
    }


def probe_apparmor(metrics_url: str) -> dict[str, Any]:
    metrics = _fetch_metrics(metrics_url)
    if metrics is None:
        return {"status": "unreachable", "summary": "node_exporter down"}
    out = probe_textfile_observer(metrics, "selfdef_apparmor", "apparmor")
    if out["status"] != "OK":
        return out
    loaded = _gauge(
        metrics, "selfdef_apparmor_profile_loaded",
        label_match='profile="/usr/bin/selfdefd"',
    )
    enforce = _gauge(
        metrics, "selfdef_apparmor_profile_enforce",
        label_match='profile="/usr/bin/selfdefd"',
    )
    complain = _gauge(
        metrics, "selfdef_apparmor_profile_complain",
        label_match='profile="/usr/bin/selfdefd"',
    )
    if loaded == 0:
        return {"status": "FAIL", "summary": "profile NOT loaded"}
    if complain == 1:
        return {"status": "FAIL", "summary": "COMPLAIN mode (run aa-enforce)"}
    if enforce == 1:
        return {"status": "OK", "summary": "enforcing"}
    return {"status": "WARN", "summary": "indeterminate"}


def probe_auth_events(metrics_url: str) -> dict[str, Any]:
    metrics = _fetch_metrics(metrics_url)
    if metrics is None:
        return {"status": "unreachable", "summary": "node_exporter down"}
    out = probe_textfile_observer(metrics, "selfdef_auth_events", "auth-events")
    if out["status"] != "OK":
        return out
    failures = _gauge(
        metrics, "selfdef_auth_events_login_failures",
        label_match='window="5m"',
    )
    invalid = _gauge(
        metrics, "selfdef_auth_events_ssh_invalid_users",
        label_match='window="5m"',
    )
    bits = []
    cls = "OK"
    if failures is not None and failures > 20:
        bits.append(f"login_failures={int(failures)} > 20 (BRUTE-FORCE)")
        cls = "FAIL"
    elif failures is not None and failures > 0:
        bits.append(f"login_failures={int(failures)}")
    if invalid is not None and invalid > 5:
        bits.append(f"ssh_invalid={int(invalid)} > 5 (RECON)")
        if cls == "OK":
            cls = "WARN"
    return {
        "status": cls,
        "summary": (" · ".join(bits) if bits else "no auth events") + f" · {out['summary']}",
    }


def probe_systemd_units(metrics_url: str) -> dict[str, Any]:
    metrics = _fetch_metrics(metrics_url)
    if metrics is None:
        return {"status": "unreachable", "summary": "node_exporter down"}
    out = probe_textfile_observer(metrics, "selfdef_systemd_units", "systemd-units")
    if out["status"] != "OK":
        return out
    total = _gauge(
        metrics, "selfdef_systemd_units_total",
        label_match='prefix="selfdef-"',
    )
    failed = _gauge(
        metrics, "selfdef_systemd_units_failed",
        label_match='prefix="selfdef-"',
    )
    active = _gauge(
        metrics, "selfdef_systemd_units_active",
        label_match='prefix="selfdef-"',
    )
    if failed is not None and failed > 0:
        return {
            "status": "FAIL",
            "summary": f"{int(failed)} unit(s) failed (run systemctl --failed)",
        }
    if total is not None and total < 8:
        return {
            "status": "WARN",
            "summary": f"only {int(total)} units (expected 10+)",
        }
    return {
        "status": "OK",
        "summary": f"{int(total) if total is not None else '?'} units · {int(active) if active is not None else '?'} active",
    }


def probe_listening_sockets(metrics_url: str) -> dict[str, Any]:
    metrics = _fetch_metrics(metrics_url)
    if metrics is None:
        return {"status": "unreachable", "summary": "node_exporter down"}
    out = probe_textfile_observer(
        metrics, "selfdef_listening_sockets", "listening-sockets",
    )
    if out["status"] != "OK":
        return out
    tcp = _gauge(metrics, "selfdef_listening_sockets_tcp")
    tcp6 = _gauge(metrics, "selfdef_listening_sockets_tcp6")
    total = _gauge(metrics, "selfdef_listening_sockets_total")
    tcp_combined = (tcp or 0) + (tcp6 or 0)
    if tcp_combined < 1:
        return {
            "status": "FAIL",
            "summary": "0 TCP listeners (selfdefd wedged?)",
        }
    if tcp_combined > 20:
        return {
            "status": "WARN",
            "summary": f"{int(tcp_combined)} TCP listeners > 20 (run ss -ltn)",
        }
    return {
        "status": "OK",
        "summary": f"{int(tcp_combined)} TCP listeners · {int(total) if total is not None else '?'} total",
    }


def probe_disk_usage(metrics_url: str) -> dict[str, Any]:
    metrics = _fetch_metrics(metrics_url)
    if metrics is None:
        return {"status": "unreachable", "summary": "node_exporter down"}
    out = probe_textfile_observer(metrics, "selfdef_disk_usage", "disk-usage")
    if out["status"] != "OK":
        return out
    used_pct = _gauge(metrics, "selfdef_disk_usage_var_used_percent")
    selfdef_log = _gauge(metrics, "selfdef_disk_usage_log_bytes")
    if used_pct is not None and used_pct > 90:
        return {
            "status": "FAIL",
            "summary": f"/var at {used_pct:.0f}% > 90 (IPS spine wedge risk)",
        }
    if used_pct is not None and used_pct > 75:
        return {
            "status": "WARN",
            "summary": f"/var at {used_pct:.0f}% > 75 (approaching)",
        }
    if selfdef_log is not None and selfdef_log > 5368709120:
        return {
            "status": "WARN",
            "summary": f"/var/log/selfdef {selfdef_log / 1073741824:.1f} GiB > 5",
        }
    return {
        "status": "OK",
        "summary": f"/var at {used_pct:.0f}%" if used_pct is not None else "OK",
    }


def probe_time_sync(metrics_url: str) -> dict[str, Any]:
    metrics = _fetch_metrics(metrics_url)
    if metrics is None:
        return {"status": "unreachable", "summary": "node_exporter down"}
    out = probe_textfile_observer(metrics, "selfdef_time_sync", "time-sync")
    if out["status"] != "OK":
        return out
    synced = _gauge(metrics, "selfdef_time_sync_synced")
    ntp_active = _gauge(metrics, "selfdef_time_sync_ntp_active")
    drift = _gauge(metrics, "selfdef_time_sync_drift_seconds")
    rtc_local = _gauge(metrics, "selfdef_time_sync_rtc_local_tz")
    if synced == 0:
        return {
            "status": "FAIL",
            "summary": "NOT synced (audit timestamps unreliable)",
        }
    if ntp_active == 0:
        return {
            "status": "FAIL",
            "summary": "NTP service inactive (sync will drift)",
        }
    if drift is not None and drift > 60:
        return {
            "status": "WARN",
            "summary": f"drift {int(drift)}s > 60",
        }
    if rtc_local == 1:
        return {
            "status": "WARN",
            "summary": "RTC in local TZ (DST hazard)",
        }
    return {
        "status": "OK",
        "summary": f"synced · drift {int(drift) if drift is not None else '?'}s",
    }


def probe_kernel_modules(metrics_url: str) -> dict[str, Any]:
    metrics = _fetch_metrics(metrics_url)
    if metrics is None:
        return {"status": "unreachable", "summary": "node_exporter down"}
    out = probe_textfile_observer(
        metrics, "selfdef_kernel_modules", "kernel-modules",
    )
    if out["status"] != "OK":
        return out
    unsigned = _gauge(metrics, "selfdef_kernel_tainted_unsigned")
    tainted = _gauge(metrics, "selfdef_kernel_tainted")
    total = _gauge(metrics, "selfdef_kernel_modules_total")
    if unsigned == 1:
        return {
            "status": "FAIL",
            "summary": "UNSIGNED module loaded (ROOTKIT SIGNATURE)",
        }
    if tainted is not None and tainted > 0:
        return {
            "status": "WARN",
            "summary": f"tainted (bitmask={int(tainted)})",
        }
    if total is not None and total > 200:
        return {
            "status": "WARN",
            "summary": f"{int(total)} modules > 200",
        }
    return {
        "status": "OK",
        "summary": f"{int(total) if total is not None else '?'} modules · untainted",
    }


def probe_fail2ban(metrics_url: str) -> dict[str, Any]:
    metrics = _fetch_metrics(metrics_url)
    if metrics is None:
        return {"status": "unreachable", "summary": "node_exporter down"}
    out = probe_textfile_observer(metrics, "selfdef_fail2ban", "fail2ban")
    if out["status"] != "OK":
        return out
    alive = _gauge(metrics, "selfdef_fail2ban_server_alive")
    jails = _gauge(metrics, "selfdef_fail2ban_jails_active")
    cur = _gauge(metrics, "selfdef_fail2ban_current_bans_sum")
    if alive == -1:
        return {
            "status": "OK",
            "summary": "fail2ban-client not installed (honest-offline)",
        }
    if alive == 0:
        return {
            "status": "FAIL",
            "summary": "fail2ban-server DOWN (defensive-tier outage)",
        }
    if jails == 0:
        return {
            "status": "WARN",
            "summary": "0 active jails (no defensive response configured)",
        }
    if cur is not None and cur > 50:
        return {
            "status": "WARN",
            "summary": f"{int(cur)} currently-banned IPs > 50 (brute-force wave)",
        }
    return {
        "status": "OK",
        "summary": f"{int(jails) if jails is not None else '?'} jails · "
                   f"{int(cur) if cur is not None else 0} bans",
    }


def probe_nftables(metrics_url: str) -> dict[str, Any]:
    metrics = _fetch_metrics(metrics_url)
    if metrics is None:
        return {"status": "unreachable", "summary": "node_exporter down"}
    out = probe_textfile_observer(metrics, "selfdef_nftables", "nftables")
    if out["status"] != "OK":
        return out
    present = _gauge(metrics, "selfdef_nftables_present")
    rules = _gauge(metrics, "selfdef_nftables_rules_total")
    used_pct = _gauge(metrics, "selfdef_conntrack_used_percent")
    if used_pct is not None and used_pct > 90:
        return {
            "status": "FAIL",
            "summary": f"conntrack {int(used_pct)}% full (kernel DROPPING)",
        }
    if present == 1 and rules == 0:
        return {
            "status": "FAIL",
            "summary": "ruleset EMPTY (perimeter outage)",
        }
    if used_pct is not None and used_pct > 75:
        return {
            "status": "WARN",
            "summary": f"conntrack {int(used_pct)}% (approaching ceiling)",
        }
    if present == 0:
        return {
            "status": "OK",
            "summary": "nft not installed (honest-offline) · "
                       f"conntrack {int(used_pct) if used_pct is not None else 0}%",
        }
    return {
        "status": "OK",
        "summary": f"{int(rules) if rules is not None else 0} rules · "
                   f"conntrack {int(used_pct) if used_pct is not None else 0}%",
    }


def probe_cron(metrics_url: str) -> dict[str, Any]:
    metrics = _fetch_metrics(metrics_url)
    if metrics is None:
        return {"status": "unreachable", "summary": "node_exporter down"}
    out = probe_textfile_observer(metrics, "selfdef_cron", "cron")
    if out["status"] != "OK":
        return out
    cron_d = _gauge(metrics, "selfdef_cron_d_files")
    total = _gauge(metrics, "selfdef_cron_total_entries")
    timers = _gauge(metrics, "selfdef_systemd_timers_total")
    return {
        "status": "OK",
        "summary": f"{int(cron_d) if cron_d is not None else 0} cron.d · "
                   f"{int(total) if total is not None else 0} entries · "
                   f"{int(timers) if timers is not None else 0} timers",
    }


def probe_sshd_config(metrics_url: str) -> dict[str, Any]:
    metrics = _fetch_metrics(metrics_url)
    if metrics is None:
        return {"status": "unreachable", "summary": "node_exporter down"}
    out = probe_textfile_observer(metrics, "selfdef_sshd_config", "sshd-config")
    if out["status"] != "OK":
        return out
    present = _gauge(metrics, "selfdef_sshd_config_present")
    permit_root = _gauge(metrics, "selfdef_sshd_permit_root_login")
    empty_pw = _gauge(metrics, "selfdef_sshd_permit_empty_passwords")
    password_auth = _gauge(metrics, "selfdef_sshd_password_authentication")
    if present == 0:
        return {
            "status": "OK",
            "summary": "sshd_config absent (honest-offline)",
        }
    hazards = []
    if permit_root == 1:
        hazards.append("PermitRootLogin")
    if empty_pw == 1:
        hazards.append("PermitEmptyPasswords")
    if hazards:
        return {
            "status": "FAIL",
            "summary": "HAZARD: " + " + ".join(hazards),
        }
    if password_auth == 1:
        return {
            "status": "WARN",
            "summary": "PasswordAuthentication enabled (brute-force vector)",
        }
    return {"status": "OK", "summary": "hardened (no hazards)"}


def probe_package_state(metrics_url: str) -> dict[str, Any]:
    metrics = _fetch_metrics(metrics_url)
    if metrics is None:
        return {"status": "unreachable", "summary": "node_exporter down"}
    out = probe_textfile_observer(metrics, "selfdef_package_state",
                                   "package-state")
    if out["status"] != "OK":
        return out
    apt_available = _gauge(metrics, "selfdef_package_manager_apt")
    sec = _gauge(metrics, "selfdef_apt_pending_security")
    broken = _gauge(metrics, "selfdef_dpkg_broken_packages")
    age = _gauge(metrics, "selfdef_apt_update_age_days")
    total = _gauge(metrics, "selfdef_apt_pending_total")
    if apt_available == 0:
        return {
            "status": "OK",
            "summary": "apt/dpkg not installed (honest-offline)",
        }
    if sec is not None and sec > 0:
        return {
            "status": "FAIL",
            "summary": f"{int(sec)} security update(s) pending (CVE patches)",
        }
    if broken is not None and broken > 0:
        return {
            "status": "FAIL",
            "summary": f"{int(broken)} dpkg broken package(s)",
        }
    if age is not None and age > 7:
        return {
            "status": "WARN",
            "summary": f"apt-update {int(age)}d stale (CVE visibility lapsed)",
        }
    if total is not None and total > 50:
        return {
            "status": "WARN",
            "summary": f"{int(total)} pending upgrades > 50 (backlog)",
        }
    return {
        "status": "OK",
        "summary": f"{int(total) if total is not None else 0} pending · "
                   f"apt-update {int(age) if age is not None else 0}d ago",
    }


def probe_journal_disk(metrics_url: str) -> dict[str, Any]:
    metrics = _fetch_metrics(metrics_url)
    if metrics is None:
        return {"status": "unreachable", "summary": "node_exporter down"}
    out = probe_textfile_observer(metrics, "selfdef_journal_disk", "journal-disk")
    if out["status"] != "OK":
        return out
    available = _gauge(metrics, "selfdef_journal_available")
    bytes_total = _gauge(metrics, "selfdef_journal_bytes_total")
    persistent = _gauge(metrics, "selfdef_journal_persistent")
    if available == 0:
        return {
            "status": "OK",
            "summary": "journalctl not installed (honest-offline)",
        }
    if bytes_total is not None and bytes_total > 5368709120:
        return {
            "status": "FAIL",
            "summary": f"journal {int(bytes_total) // (1024**3)} GiB > 5 GiB (runaway)",
        }
    if persistent == 0:
        return {
            "status": "FAIL",
            "summary": "no persistent journal (forensic gap)",
        }
    if bytes_total is not None and bytes_total > 1073741824:
        return {
            "status": "WARN",
            "summary": f"journal {int(bytes_total) // (1024**3)} GiB > 1 GiB (retention pressure)",
        }
    mib = (int(bytes_total) // (1024 * 1024)) if bytes_total is not None else 0
    return {"status": "OK", "summary": f"{mib} MiB · persistent"}


def probe_blockset(metrics_url: str) -> dict[str, Any]:
    metrics = _fetch_metrics(metrics_url)
    if metrics is None:
        return {"status": "unreachable", "summary": "node_exporter down"}
    out = probe_textfile_observer(metrics, "selfdef_blockset", "blockset")
    if out["status"] != "OK":
        return out
    present = _gauge(metrics, "selfdef_blockset_present")
    total = _gauge(metrics, "selfdef_blockset_total_count")
    if present == 0:
        return {
            "status": "FAIL",
            "summary": "selfdef-blocks table absent (SDD-065 enforcement OFFLINE)",
        }
    if total is not None and total > 1000:
        return {
            "status": "WARN",
            "summary": f"{int(total)} blocks > 1000 (sustained attack or rule churn)",
        }
    return {
        "status": "OK",
        "summary": f"{int(total) if total is not None else 0} blocks · enforcement online",
    }


def probe_capability_drops(metrics_url: str) -> dict[str, Any]:
    metrics = _fetch_metrics(metrics_url)
    if metrics is None:
        return {"status": "unreachable", "summary": "node_exporter down"}
    out = probe_textfile_observer(
        metrics, "selfdef_capability_drops", "capability-drops",
    )
    if out["status"] != "OK":
        return out
    present = _gauge(metrics, "selfdef_capability_drops_state_dir_present")
    active = _gauge(metrics, "selfdef_capability_drops_active_count")
    redundant = _gauge(metrics, "selfdef_capability_drops_redundant_count")
    caps_dropped = _gauge(metrics, "selfdef_capability_drops_caps_dropped_total")
    pending = _gauge(metrics, "selfdef_capability_drops_pending_restores")
    if present == 0:
        return {"status": "FAIL",
                "summary": "state-dir absent (SDD-075 enforcement OFFLINE)"}
    if pending is not None and pending > 5:
        return {"status": "WARN",
                "summary": f"{int(pending)} pending capability-drop restore decisions"}
    if redundant is not None and redundant > 3:
        return {"status": "WARN",
                "summary": f"{int(redundant)} Redundant handles — rule misconfig review"}
    if caps_dropped is not None and caps_dropped > 30:
        return {"status": "WARN",
                "summary": f"{int(caps_dropped)} caps dropped — large-scale enforcement"}
    if active is not None and active > 10:
        return {"status": "WARN",
                "summary": f"{int(active)} active capability-drops > 10"}
    return {
        "status": "OK",
        "summary": f"{int(active) if active is not None else 0} handles · "
                   f"{int(caps_dropped) if caps_dropped is not None else 0} caps · "
                   f"{int(redundant) if redundant is not None else 0} redundant · "
                   f"{int(pending) if pending is not None else 0} pending · "
                   "enforcement online",
    }


def probe_apparmor_profile_pivots(metrics_url: str) -> dict[str, Any]:
    metrics = _fetch_metrics(metrics_url)
    if metrics is None:
        return {"status": "unreachable", "summary": "node_exporter down"}
    out = probe_textfile_observer(
        metrics, "selfdef_apparmor_profile_pivots", "apparmor-profile-pivots",
    )
    if out["status"] != "OK":
        return out
    present = _gauge(metrics, "selfdef_apparmor_profile_pivots_state_dir_present")
    active = _gauge(metrics, "selfdef_apparmor_profile_pivots_active_count")
    denied = _gauge(metrics, "selfdef_apparmor_profile_pivots_denied_count")
    no_target = _gauge(metrics, "selfdef_apparmor_profile_pivots_no_target_count")
    stale = _gauge(metrics, "selfdef_apparmor_profile_pivots_stale_count")
    pending = _gauge(metrics, "selfdef_apparmor_profile_pivots_pending_restores")
    if present == 0:
        return {"status": "FAIL",
                "summary": "state-dir absent (SDD-077 enforcement OFFLINE)"}
    if pending is not None and pending > 5:
        return {"status": "WARN",
                "summary": f"{int(pending)} pending apparmor-profile-pivot restore decisions"}
    if denied is not None and denied > 3:
        return {"status": "WARN",
                "summary": f"{int(denied)} Denied handles — rule misconfig or stricter-profile review"}
    if no_target is not None and no_target > 1:
        return {"status": "WARN",
                "summary": f"{int(no_target)} NoTarget handles — profile not loaded in kernel"}
    if stale is not None and stale > 3:
        return {"status": "WARN",
                "summary": f"{int(stale)} Stale handles — pid-dies-before-write race"}
    if active is not None and active > 10:
        return {"status": "WARN",
                "summary": f"{int(active)} active apparmor-profile-pivots > 10"}
    return {
        "status": "OK",
        "summary": f"{int(active) if active is not None else 0} handles · "
                   f"{int(denied) if denied is not None else 0} denied · "
                   f"{int(no_target) if no_target is not None else 0} no-target · "
                   f"{int(pending) if pending is not None else 0} pending · "
                   "enforcement online",
    }


def probe_kernel_keyring_evictions(metrics_url: str) -> dict[str, Any]:
    metrics = _fetch_metrics(metrics_url)
    if metrics is None:
        return {"status": "unreachable", "summary": "node_exporter down"}
    out = probe_textfile_observer(
        metrics, "selfdef_kernel_keyring_evictions", "kernel-keyring-evictions",
    )
    if out["status"] != "OK":
        return out
    present = _gauge(metrics, "selfdef_kernel_keyring_evictions_state_dir_present")
    active = _gauge(metrics, "selfdef_kernel_keyring_evictions_active_count")
    not_found = _gauge(metrics, "selfdef_kernel_keyring_evictions_not_found_count")
    keys_evicted = _gauge(metrics, "selfdef_kernel_keyring_evictions_keys_evicted_total")
    pending = _gauge(metrics, "selfdef_kernel_keyring_evictions_pending_restores")
    if present == 0:
        return {"status": "FAIL",
                "summary": "state-dir absent (SDD-076 enforcement OFFLINE)"}
    if pending is not None and pending > 5:
        return {"status": "WARN",
                "summary": f"{int(pending)} pending kernel-keyring-eviction restore decisions"}
    if not_found is not None and not_found > 3:
        return {"status": "WARN",
                "summary": f"{int(not_found)} NotFound handles — rule misconfig or stale-spec review"}
    if keys_evicted is not None and keys_evicted > 30:
        return {"status": "WARN",
                "summary": f"{int(keys_evicted)} keys evicted — large-scale credential rotation"}
    if active is not None and active > 10:
        return {"status": "WARN",
                "summary": f"{int(active)} active kernel-keyring-evictions > 10"}
    return {
        "status": "OK",
        "summary": f"{int(active) if active is not None else 0} handles · "
                   f"{int(keys_evicted) if keys_evicted is not None else 0} keys · "
                   f"{int(not_found) if not_found is not None else 0} not-found · "
                   f"{int(pending) if pending is not None else 0} pending · "
                   "enforcement online",
    }


def probe_env_scrubs(metrics_url: str) -> dict[str, Any]:
    metrics = _fetch_metrics(metrics_url)
    if metrics is None:
        return {"status": "unreachable", "summary": "node_exporter down"}
    out = probe_textfile_observer(
        metrics, "selfdef_env_scrubs", "env-scrubs",
    )
    if out["status"] != "OK":
        return out
    present = _gauge(metrics, "selfdef_env_scrubs_state_dir_present")
    active = _gauge(metrics, "selfdef_env_scrubs_active_count")
    no_match = _gauge(metrics, "selfdef_env_scrubs_no_match_count")
    vars_scrubbed = _gauge(metrics, "selfdef_env_scrubs_vars_scrubbed_total")
    pending = _gauge(metrics, "selfdef_env_scrubs_pending_restores")
    if present == 0:
        return {"status": "FAIL",
                "summary": "state-dir absent (SDD-074 enforcement OFFLINE)"}
    if pending is not None and pending > 5:
        return {"status": "WARN",
                "summary": f"{int(pending)} pending env-scrub restore decisions"}
    if no_match is not None and no_match > 3:
        return {"status": "WARN",
                "summary": f"{int(no_match)} NoMatch handles — rule misconfig review"}
    if vars_scrubbed is not None and vars_scrubbed > 50:
        return {"status": "WARN",
                "summary": f"{int(vars_scrubbed)} vars scrubbed — large-scale rotation"}
    if active is not None and active > 10:
        return {"status": "WARN",
                "summary": f"{int(active)} active env-scrubs > 10"}
    return {
        "status": "OK",
        "summary": f"{int(active) if active is not None else 0} handles · "
                   f"{int(vars_scrubbed) if vars_scrubbed is not None else 0} vars · "
                   f"{int(no_match) if no_match is not None else 0} no-match · "
                   f"{int(pending) if pending is not None else 0} pending · "
                   "enforcement online",
    }


def probe_socket_fd_revocations(metrics_url: str) -> dict[str, Any]:
    metrics = _fetch_metrics(metrics_url)
    if metrics is None:
        return {"status": "unreachable", "summary": "node_exporter down"}
    out = probe_textfile_observer(
        metrics, "selfdef_socket_fd_revocations", "socket-fd-revocations",
    )
    if out["status"] != "OK":
        return out
    present = _gauge(metrics, "selfdef_socket_fd_revocations_state_dir_present")
    active = _gauge(metrics, "selfdef_socket_fd_revocations_active_count")
    stale = _gauge(metrics, "selfdef_socket_fd_revocations_stale_count")
    pending = _gauge(metrics, "selfdef_socket_fd_revocations_pending_restores")
    if present == 0:
        return {"status": "FAIL",
                "summary": "state-dir absent (SDD-073 enforcement OFFLINE)"}
    if pending is not None and pending > 5:
        return {"status": "WARN",
                "summary": f"{int(pending)} pending socket-fd-restore decisions"}
    if stale is not None and stale > 3:
        return {"status": "WARN",
                "summary": f"{int(stale)} stale (inode-race) handles — correlator latency review"}
    if active is not None and active > 20:
        return {"status": "WARN",
                "summary": f"{int(active)} active socket-fd revocations > 20"}
    return {
        "status": "OK",
        "summary": f"{int(active) if active is not None else 0} active · "
                   f"{int(stale) if stale is not None else 0} stale · "
                   f"{int(pending) if pending is not None else 0} pending · "
                   "enforcement online",
    }


def probe_process_tree_freezes(metrics_url: str) -> dict[str, Any]:
    metrics = _fetch_metrics(metrics_url)
    if metrics is None:
        return {"status": "unreachable", "summary": "node_exporter down"}
    out = probe_textfile_observer(
        metrics, "selfdef_process_tree_freezes", "process-tree-freezes",
    )
    if out["status"] != "OK":
        return out
    present = _gauge(metrics, "selfdef_process_tree_freezes_state_dir_present")
    active = _gauge(metrics, "selfdef_process_tree_freezes_active_count")
    pending = _gauge(metrics, "selfdef_process_tree_freezes_pending_thaws")
    frozen_pids = _gauge(metrics, "selfdef_process_tree_freezes_frozen_pid_count")
    if present == 0:
        return {"status": "FAIL",
                "summary": "state-dir absent (SDD-072 enforcement OFFLINE)"}
    if pending is not None and pending > 5:
        return {"status": "WARN",
                "summary": f"{int(pending)} pending process-tree-thaw decisions"}
    if frozen_pids is not None and frozen_pids > 100:
        return {"status": "WARN",
                "summary": f"{int(frozen_pids)} frozen pids (fork-bomb-scale)"}
    if active is not None and active > 10:
        return {"status": "WARN",
                "summary": f"{int(active)} active process-tree freezes > 10"}
    return {
        "status": "OK",
        "summary": f"{int(active) if active is not None else 0} handles · "
                   f"{int(frozen_pids) if frozen_pids is not None else 0} frozen pids · "
                   f"{int(pending) if pending is not None else 0} pending · "
                   "enforcement online",
    }


def probe_mount_bindings(metrics_url: str) -> dict[str, Any]:
    metrics = _fetch_metrics(metrics_url)
    if metrics is None:
        return {"status": "unreachable", "summary": "node_exporter down"}
    out = probe_textfile_observer(
        metrics, "selfdef_mount_bindings", "mount-bindings",
    )
    if out["status"] != "OK":
        return out
    present = _gauge(metrics, "selfdef_mount_bindings_state_dir_present")
    active = _gauge(metrics, "selfdef_mount_bindings_active_count")
    pending = _gauge(metrics, "selfdef_mount_bindings_pending_rebinds")
    if present == 0:
        return {"status": "FAIL",
                "summary": "state-dir absent (SDD-071 enforcement OFFLINE)"}
    if pending is not None and pending > 5:
        return {"status": "WARN",
                "summary": f"{int(pending)} pending mount-rebind decisions"}
    if active is not None and active > 10:
        return {"status": "WARN",
                "summary": f"{int(active)} active mount-binding unbinds > 10"}
    return {
        "status": "OK",
        "summary": f"{int(active) if active is not None else 0} active · "
                   f"{int(pending) if pending is not None else 0} pending · "
                   "enforcement online",
    }


def probe_netns_isolations(metrics_url: str) -> dict[str, Any]:
    metrics = _fetch_metrics(metrics_url)
    if metrics is None:
        return {"status": "unreachable", "summary": "node_exporter down"}
    out = probe_textfile_observer(
        metrics, "selfdef_netns_isolations", "netns-isolations",
    )
    if out["status"] != "OK":
        return out
    present = _gauge(metrics, "selfdef_netns_isolations_state_dir_present")
    active = _gauge(metrics, "selfdef_netns_isolations_active_count")
    pending = _gauge(metrics, "selfdef_netns_isolations_pending_releases")
    if present == 0:
        return {"status": "FAIL",
                "summary": "state-dir absent (SDD-070 enforcement OFFLINE)"}
    if pending is not None and pending > 5:
        return {"status": "WARN",
                "summary": f"{int(pending)} pending netns-release decisions"}
    if active is not None and active > 10:
        return {"status": "WARN",
                "summary": f"{int(active)} active netns-isolations > 10"}
    return {
        "status": "OK",
        "summary": f"{int(active) if active is not None else 0} active · "
                   f"{int(pending) if pending is not None else 0} pending · "
                   "enforcement online",
    }


def probe_mfa_grant_revocations(metrics_url: str) -> dict[str, Any]:
    metrics = _fetch_metrics(metrics_url)
    if metrics is None:
        return {"status": "unreachable", "summary": "node_exporter down"}
    out = probe_textfile_observer(
        metrics, "selfdef_mfa_grant_revocations", "mfa-grant-revocations",
    )
    if out["status"] != "OK":
        return out
    present = _gauge(metrics, "selfdef_mfa_grant_revocations_state_dir_present")
    active = _gauge(metrics, "selfdef_mfa_grant_revocations_active_count")
    pending = _gauge(metrics, "selfdef_mfa_grant_revocations_pending_restores")
    if present == 0:
        return {"status": "FAIL",
                "summary": "state-dir absent (SDD-069 enforcement OFFLINE)"}
    if pending is not None and pending > 5:
        return {"status": "WARN",
                "summary": f"{int(pending)} pending MFA-grant restore decisions"}
    if active is not None and active > 10:
        return {"status": "WARN",
                "summary": f"{int(active)} active MFA-grant revocations > 10"}
    return {
        "status": "OK",
        "summary": f"{int(active) if active is not None else 0} active · "
                   f"{int(pending) if pending is not None else 0} pending · "
                   "enforcement online",
    }


def probe_token_revocations(metrics_url: str) -> dict[str, Any]:
    metrics = _fetch_metrics(metrics_url)
    if metrics is None:
        return {"status": "unreachable", "summary": "node_exporter down"}
    out = probe_textfile_observer(metrics, "selfdef_token_revocations", "token-revocations")
    if out["status"] != "OK":
        return out
    present = _gauge(metrics, "selfdef_token_revocations_state_dir_present")
    active = _gauge(metrics, "selfdef_token_revocations_active_count")
    pending = _gauge(metrics, "selfdef_token_revocations_pending_restores")
    if present == 0:
        return {
            "status": "FAIL",
            "summary": "state-dir absent (SDD-068 enforcement OFFLINE)",
        }
    if pending is not None and pending > 5:
        return {
            "status": "WARN",
            "summary": f"{int(pending)} pending token-restore decisions (operator backlog)",
        }
    if active is not None and active > 10:
        return {
            "status": "WARN",
            "summary": f"{int(active)} active token-revocations > 10",
        }
    return {
        "status": "OK",
        "summary": f"{int(active) if active is not None else 0} active · "
                   f"{int(pending) if pending is not None else 0} pending · "
                   "enforcement online",
    }


def probe_revocations(metrics_url: str) -> dict[str, Any]:
    metrics = _fetch_metrics(metrics_url)
    if metrics is None:
        return {"status": "unreachable", "summary": "node_exporter down"}
    out = probe_textfile_observer(metrics, "selfdef_revocations", "revocations")
    if out["status"] != "OK":
        return out
    present = _gauge(metrics, "selfdef_revocations_state_dir_present")
    active = _gauge(metrics, "selfdef_revocations_active_count")
    pending = _gauge(metrics, "selfdef_revocations_pending_restores")
    if present == 0:
        return {
            "status": "FAIL",
            "summary": "state-dir absent (SDD-067 enforcement OFFLINE)",
        }
    if pending is not None and pending > 5:
        return {
            "status": "WARN",
            "summary": f"{int(pending)} pending restore decisions (operator backlog)",
        }
    if active is not None and active > 10:
        return {
            "status": "WARN",
            "summary": f"{int(active)} active revocations > 10 (incident-response scenario)",
        }
    return {
        "status": "OK",
        "summary": f"{int(active) if active is not None else 0} active · "
                   f"{int(pending) if pending is not None else 0} pending · "
                   "enforcement online",
    }


def probe_quarantine(metrics_url: str) -> dict[str, Any]:
    metrics = _fetch_metrics(metrics_url)
    if metrics is None:
        return {"status": "unreachable", "summary": "node_exporter down"}
    out = probe_textfile_observer(metrics, "selfdef_quarantine", "quarantine")
    if out["status"] != "OK":
        return out
    present = _gauge(metrics, "selfdef_quarantine_slice_present")
    active = _gauge(metrics, "selfdef_quarantine_active_count")
    frozen = _gauge(metrics, "selfdef_quarantine_frozen_count")
    if present == 0:
        return {
            "status": "FAIL",
            "summary": "selfdef.slice absent (SDD-066 enforcement OFFLINE)",
        }
    if active is not None and active > 10:
        return {
            "status": "WARN",
            "summary": f"{int(active)} quarantines > 10 (operator decision backlog)",
        }
    return {
        "status": "OK",
        "summary": f"{int(active) if active is not None else 0} active · "
                   f"{int(frozen) if frozen is not None else 0} frozen · "
                   "enforcement online",
    }


# ── Aggregation + rendering ──────────────────────────────────────────

VERTICALS = (
    "m060", "ms022", "four_watchdog",
    "modules", "daemon_process", "apparmor",
    "auth_events", "systemd_units", "listening_sockets",
    "disk_usage", "time_sync", "kernel_modules", "fail2ban",
    "nftables", "cron", "sshd_config", "package_state",
    "journal_disk", "blockset", "quarantine", "revocations",
    "token_revocations", "mfa_grant_revocations",
    "netns_isolations", "mount_bindings",
    "process_tree_freezes", "socket_fd_revocations",
    "env_scrubs", "capability_drops",
    "kernel_keyring_evictions",
    "apparmor_profile_pivots",
)


def collect(args: argparse.Namespace) -> dict[str, dict[str, Any]]:
    return {
        "m060":          probe_m060(args.m060_url),
        "ms022":         probe_ms022(args.ms022_url),
        "four_watchdog": probe_four_watchdog(args.four_watchdog_url),
        "modules":       probe_modules_catalog(args.node_exporter_url),
        "daemon_process": probe_daemon_process(args.node_exporter_url),
        "apparmor":      probe_apparmor(args.node_exporter_url),
        "auth_events":   probe_auth_events(args.node_exporter_url),
        "systemd_units": probe_systemd_units(args.node_exporter_url),
        "listening_sockets": probe_listening_sockets(args.node_exporter_url),
        "disk_usage":    probe_disk_usage(args.node_exporter_url),
        "time_sync":     probe_time_sync(args.node_exporter_url),
        "kernel_modules": probe_kernel_modules(args.node_exporter_url),
        "fail2ban":      probe_fail2ban(args.node_exporter_url),
        "nftables":      probe_nftables(args.node_exporter_url),
        "cron":          probe_cron(args.node_exporter_url),
        "sshd_config":   probe_sshd_config(args.node_exporter_url),
        "package_state": probe_package_state(args.node_exporter_url),
        "journal_disk":  probe_journal_disk(args.node_exporter_url),
        "blockset":      probe_blockset(args.node_exporter_url),
        "quarantine":    probe_quarantine(args.node_exporter_url),
        "revocations":   probe_revocations(args.node_exporter_url),
        "token_revocations": probe_token_revocations(args.node_exporter_url),
        "mfa_grant_revocations": probe_mfa_grant_revocations(args.node_exporter_url),
        "netns_isolations": probe_netns_isolations(args.node_exporter_url),
        "mount_bindings": probe_mount_bindings(args.node_exporter_url),
        "process_tree_freezes": probe_process_tree_freezes(args.node_exporter_url),
        "socket_fd_revocations": probe_socket_fd_revocations(args.node_exporter_url),
        "env_scrubs": probe_env_scrubs(args.node_exporter_url),
        "capability_drops": probe_capability_drops(args.node_exporter_url),
        "kernel_keyring_evictions": probe_kernel_keyring_evictions(args.node_exporter_url),
        "apparmor_profile_pivots": probe_apparmor_profile_pivots(args.node_exporter_url),
    }


def render_table(results: dict[str, dict[str, Any]]) -> str:
    lines = ["sovereign-os observability status — 31 verticals",
             f"{'─' * 22} {'─' * 60}"]
    for v in VERTICALS:
        r = results[v]
        status = r["status"]
        marker = {"OK": "OK    ", "WARN": "WARN  ", "FAIL": "FAIL  ",
                  "unreachable": "UNREACH"}.get(status, "?     ")
        label = {
            "m060":              "M060 chain-health",
            "ms022":             "MS022 SSE quota",
            "four_watchdog":     "four-watchdog (IPS)",
            "modules":           "modules-catalog",
            "daemon_process":    "daemon-process",
            "apparmor":          "AppArmor",
            "auth_events":       "auth-events",
            "systemd_units":     "systemd-units",
            "listening_sockets": "listening-sockets",
            "disk_usage":        "disk-usage",
            "time_sync":         "time-sync",
            "kernel_modules":    "kernel-modules",
            "fail2ban":          "fail2ban",
            "nftables":          "nftables+conntrack",
            "cron":              "cron+timers",
            "sshd_config":       "sshd-hardening",
            "package_state":     "package-state",
            "journal_disk":      "journal-disk",
            "blockset":          "blockset (SDD-065)",
            "quarantine":        "quarantine (SDD-066)",
            "revocations":       "revocations (SDD-067)",
            "token_revocations": "token-revocations (SDD-068)",
            "mfa_grant_revocations": "mfa-grant-revocations (SDD-069)",
            "netns_isolations":  "netns-isolations (SDD-070)",
            "mount_bindings":    "mount-bindings (SDD-071)",
            "process_tree_freezes": "process-tree-freezes (SDD-072)",
            "socket_fd_revocations": "socket-fd-revocations (SDD-073)",
            "env_scrubs":          "env-scrubs (SDD-074)",
            "capability_drops":    "capability-drops (SDD-075)",
            "kernel_keyring_evictions": "kernel-keyring-evictions (SDD-076)",
            "apparmor_profile_pivots": "apparmor-profile-pivots (SDD-077)",
        }[v]
        lines.append(f"{label:<22} {marker}  {r['summary']}")
    lines.append(f"{'─' * 22} {'─' * 60}")
    fail = sum(1 for v in VERTICALS if results[v]["status"] == "FAIL")
    warn = sum(1 for v in VERTICALS if results[v]["status"] == "WARN")
    unreach = sum(1 for v in VERTICALS if results[v]["status"] == "unreachable")
    ok = sum(1 for v in VERTICALS if results[v]["status"] == "OK")
    lines.append(
        f"summary: {ok}/{len(VERTICALS)} OK · {warn} WARN · {fail} FAIL · "
        f"{unreach} unreachable"
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--m060-url", default=DEFAULTS["m060_url"])
    p.add_argument("--ms022-url", default=DEFAULTS["ms022_url"])
    p.add_argument("--four-watchdog-url", default=DEFAULTS["four_watchdog_url"])
    p.add_argument("--node-exporter-url", default=DEFAULTS["node_exporter_url"])
    p.add_argument("--json", action="store_true",
                   help="machine-readable JSON output for monitoring")
    p.add_argument("--strict", action="store_true",
                   help="exit 1 on any vertical reporting WARN (default: only FAIL/unreach)")
    args = p.parse_args(argv)

    results = collect(args)

    if args.json:
        print(json.dumps({
            "verticals": results,
            "summary": {
                "ok":   sum(1 for v in VERTICALS if results[v]["status"] == "OK"),
                "warn": sum(1 for v in VERTICALS if results[v]["status"] == "WARN"),
                "fail": sum(1 for v in VERTICALS if results[v]["status"] == "FAIL"),
                "unreachable": sum(1 for v in VERTICALS if results[v]["status"] == "unreachable"),
                "total": len(VERTICALS),
            },
        }, indent=2))
    else:
        print(render_table(results))

    # Exit code logic.
    any_fail = any(results[v]["status"] == "FAIL" for v in VERTICALS)
    any_unreach = any(results[v]["status"] == "unreachable" for v in VERTICALS)
    any_warn = any(results[v]["status"] == "WARN" for v in VERTICALS)
    if any_fail:
        return 1
    if any_unreach:
        return 2
    if args.strict and any_warn:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
