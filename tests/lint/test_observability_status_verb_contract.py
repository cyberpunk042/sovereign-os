"""sovereign-osctl observability-status verb — contract test.

Locks the NEW cross-vertical observability triage verb shipped this
commit. Operator runs `sovereign-osctl observability-status` to get
single-command status across all 6 verticals.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "diagnostics" / "observability-status.py"
SOVEREIGN_OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"

CANONICAL_VERTICALS = ("m060", "ms022", "four_watchdog",
                       "modules", "daemon_process", "apparmor",
                       "auth_events", "systemd_units",
                       "listening_sockets", "disk_usage", "time_sync",
                       "kernel_modules", "fail2ban", "nftables", "cron")


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "observability_status", SCRIPT_PATH,
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["observability_status"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_script_present_and_executable():
    assert SCRIPT_PATH.is_file()
    assert SCRIPT_PATH.stat().st_mode & 0o111


def test_canonical_verticals_locked():
    mod = _load_module()
    assert mod.VERTICALS == CANONICAL_VERTICALS, (
        f"VERTICALS drift: {mod.VERTICALS}"
    )


def test_default_endpoints_match_sibling_proxies():
    """Default URLs MUST match the 4 sovereign-os proxy daemons'
    systemd unit ports (8160 m060, 7711 MS022, 7712 four-watchdog)
    + node_exporter 9100."""
    mod = _load_module()
    assert "8160" in mod.DEFAULTS["m060_url"]
    assert "7711" in mod.DEFAULTS["ms022_url"]
    assert "7712" in mod.DEFAULTS["four_watchdog_url"]
    assert "9100" in mod.DEFAULTS["node_exporter_url"]


def test_observer_silent_threshold_locked_at_300s():
    """Locked across all observability arcs."""
    mod = _load_module()
    assert mod.OBSERVER_SILENT_THRESHOLD_SECS == 300


def test_probe_functions_exist():
    mod = _load_module()
    for fn in (
        "probe_m060", "probe_ms022", "probe_four_watchdog",
        "probe_modules_catalog", "probe_daemon_process", "probe_apparmor",
        "probe_auth_events", "probe_systemd_units", "probe_listening_sockets",
        "probe_disk_usage", "probe_time_sync", "probe_kernel_modules",
        "probe_fail2ban", "probe_nftables", "probe_cron",
    ):
        assert hasattr(mod, fn), f"missing probe function {fn}"


def test_time_sync_probe_detects_not_synced():
    mod = _load_module()
    import time as _t
    now = int(_t.time())
    fake = (
        "selfdef_time_sync_textfile_emit_failed 0\n"
        f"selfdef_time_sync_last_run_unix {now}\n"
        "selfdef_time_sync_synced 0\n"
        "selfdef_time_sync_ntp_active 1\n"
    )
    with patch.object(mod, "_fetch_metrics", return_value=fake):
        out = mod.probe_time_sync("http://localhost:9100/metrics")
    assert out["status"] == "FAIL"
    assert "synced" in out["summary"].lower()


def test_time_sync_probe_detects_drift_high():
    mod = _load_module()
    import time as _t
    now = int(_t.time())
    fake = (
        "selfdef_time_sync_textfile_emit_failed 0\n"
        f"selfdef_time_sync_last_run_unix {now}\n"
        "selfdef_time_sync_synced 1\n"
        "selfdef_time_sync_ntp_active 1\n"
        "selfdef_time_sync_drift_seconds 120\n"
    )
    with patch.object(mod, "_fetch_metrics", return_value=fake):
        out = mod.probe_time_sync("http://localhost:9100/metrics")
    assert out["status"] == "WARN"
    assert "drift" in out["summary"].lower()


def test_disk_usage_probe_detects_var_high():
    mod = _load_module()
    import time as _t
    now = int(_t.time())
    fake = (
        "selfdef_disk_usage_textfile_emit_failed 0\n"
        f"selfdef_disk_usage_last_run_unix {now}\n"
        "selfdef_disk_usage_var_used_percent 95\n"
    )
    with patch.object(mod, "_fetch_metrics", return_value=fake):
        out = mod.probe_disk_usage("http://localhost:9100/metrics")
    assert out["status"] == "FAIL"


def test_disk_usage_probe_detects_var_approaching():
    mod = _load_module()
    import time as _t
    now = int(_t.time())
    fake = (
        "selfdef_disk_usage_textfile_emit_failed 0\n"
        f"selfdef_disk_usage_last_run_unix {now}\n"
        "selfdef_disk_usage_var_used_percent 80\n"
    )
    with patch.object(mod, "_fetch_metrics", return_value=fake):
        out = mod.probe_disk_usage("http://localhost:9100/metrics")
    assert out["status"] == "WARN"


def test_listening_sockets_probe_detects_zero_tcp():
    mod = _load_module()
    import time as _t
    now = int(_t.time())
    fake = (
        "selfdef_listening_sockets_textfile_emit_failed 0\n"
        f"selfdef_listening_sockets_last_run_unix {now}\n"
        "selfdef_listening_sockets_tcp 0\n"
        "selfdef_listening_sockets_tcp6 0\n"
        "selfdef_listening_sockets_total 0\n"
    )
    with patch.object(mod, "_fetch_metrics", return_value=fake):
        out = mod.probe_listening_sockets("http://localhost:9100/metrics")
    assert out["status"] == "FAIL"
    assert "wedged" in out["summary"]


def test_listening_sockets_probe_detects_tcp_high():
    mod = _load_module()
    import time as _t
    now = int(_t.time())
    fake = (
        "selfdef_listening_sockets_textfile_emit_failed 0\n"
        f"selfdef_listening_sockets_last_run_unix {now}\n"
        "selfdef_listening_sockets_tcp 25\n"
        "selfdef_listening_sockets_tcp6 0\n"
        "selfdef_listening_sockets_total 25\n"
    )
    with patch.object(mod, "_fetch_metrics", return_value=fake):
        out = mod.probe_listening_sockets("http://localhost:9100/metrics")
    assert out["status"] == "WARN"
    assert "ss -ltn" in out["summary"]


def test_auth_events_probe_detects_brute_force():
    mod = _load_module()
    import time as _t
    now = int(_t.time())
    fake = (
        "selfdef_auth_events_textfile_emit_failed 0\n"
        f"selfdef_auth_events_last_run_unix {now}\n"
        'selfdef_auth_events_login_failures{window="5m"} 25\n'  # > 20
    )
    with patch.object(mod, "_fetch_metrics", return_value=fake):
        out = mod.probe_auth_events("http://localhost:9100/metrics")
    assert out["status"] == "FAIL"
    assert "BRUTE-FORCE" in out["summary"]


def test_systemd_units_probe_detects_failed_unit():
    mod = _load_module()
    import time as _t
    now = int(_t.time())
    fake = (
        "selfdef_systemd_units_textfile_emit_failed 0\n"
        f"selfdef_systemd_units_last_run_unix {now}\n"
        'selfdef_systemd_units_total{prefix="selfdef-"} 10\n'
        'selfdef_systemd_units_failed{prefix="selfdef-"} 1\n'
        'selfdef_systemd_units_active{prefix="selfdef-"} 9\n'
    )
    with patch.object(mod, "_fetch_metrics", return_value=fake):
        out = mod.probe_systemd_units("http://localhost:9100/metrics")
    assert out["status"] == "FAIL"
    assert "failed" in out["summary"]


def test_systemd_units_probe_detects_count_low():
    mod = _load_module()
    import time as _t
    now = int(_t.time())
    fake = (
        "selfdef_systemd_units_textfile_emit_failed 0\n"
        f"selfdef_systemd_units_last_run_unix {now}\n"
        'selfdef_systemd_units_total{prefix="selfdef-"} 5\n'
        'selfdef_systemd_units_failed{prefix="selfdef-"} 0\n'
        'selfdef_systemd_units_active{prefix="selfdef-"} 5\n'
    )
    with patch.object(mod, "_fetch_metrics", return_value=fake):
        out = mod.probe_systemd_units("http://localhost:9100/metrics")
    assert out["status"] == "WARN"


def test_textfile_observer_handles_emit_failed_sentinel():
    """The shared textfile-observer probe MUST treat emit_failed > 0
    as FAIL — drift would silently mask wedged observers."""
    mod = _load_module()
    metrics = (
        "selfdef_test_textfile_emit_failed 1\n"
        "selfdef_test_last_run_unix 0\n"
    )
    out = mod.probe_textfile_observer(metrics, "selfdef_test", "test")
    assert out["status"] == "FAIL"


def test_textfile_observer_detects_silent_observer():
    """When last_run_unix > 300s old, classify as FAIL."""
    mod = _load_module()
    metrics = (
        "selfdef_test_textfile_emit_failed 0\n"
        "selfdef_test_last_run_unix 100\n"  # ancient timestamp
    )
    out = mod.probe_textfile_observer(metrics, "selfdef_test", "test")
    assert out["status"] == "FAIL"


def test_textfile_observer_fresh_when_recent():
    import time as _t
    now = int(_t.time())
    mod = _load_module()
    metrics = (
        f"selfdef_test_textfile_emit_failed 0\n"
        f"selfdef_test_last_run_unix {now - 30}\n"
    )
    out = mod.probe_textfile_observer(metrics, "selfdef_test", "test")
    assert out["status"] == "OK"


def test_apparmor_probe_detects_complain_mode():
    mod = _load_module()
    import time as _t
    now = int(_t.time())
    fake_metrics = (
        "selfdef_apparmor_textfile_emit_failed 0\n"
        f"selfdef_apparmor_last_run_unix {now}\n"
        'selfdef_apparmor_profile_loaded{profile="/usr/bin/selfdefd"} 1\n'
        'selfdef_apparmor_profile_enforce{profile="/usr/bin/selfdefd"} 0\n'
        'selfdef_apparmor_profile_complain{profile="/usr/bin/selfdefd"} 1\n'
    )
    with patch.object(mod, "_fetch_metrics", return_value=fake_metrics):
        out = mod.probe_apparmor("http://localhost:9100/metrics")
    assert out["status"] == "FAIL"
    assert "COMPLAIN" in out["summary"] or "complain" in out["summary"].lower()


def test_daemon_process_probe_detects_fd_exhaustion():
    mod = _load_module()
    import time as _t
    now = int(_t.time())
    fake_metrics = (
        "selfdef_daemon_process_textfile_emit_failed 0\n"
        f"selfdef_daemon_process_last_run_unix {now}\n"
        "selfdef_daemon_process_memory_rss_bytes 500000000\n"
        "selfdef_daemon_process_open_fds 900\n"  # > 819
    )
    with patch.object(mod, "_fetch_metrics", return_value=fake_metrics):
        out = mod.probe_daemon_process("http://localhost:9100/metrics")
    assert out["status"] == "FAIL"


def test_kernel_modules_probe_detects_unsigned():
    """Unsigned kernel module loaded = rootkit signature, must FAIL."""
    mod = _load_module()
    import time as _t
    now = int(_t.time())
    fake = (
        "selfdef_kernel_modules_textfile_emit_failed 0\n"
        f"selfdef_kernel_modules_last_run_unix {now}\n"
        "selfdef_kernel_modules_total 150\n"
        "selfdef_kernel_tainted 4096\n"
        "selfdef_kernel_tainted_unsigned 1\n"
    )
    with patch.object(mod, "_fetch_metrics", return_value=fake):
        out = mod.probe_kernel_modules("http://localhost:9100/metrics")
    assert out["status"] == "FAIL"
    assert "UNSIGNED" in out["summary"] or "ROOTKIT" in out["summary"]


def test_kernel_modules_probe_detects_tainted():
    """Tainted (non-unsigned) bits = WARN."""
    mod = _load_module()
    import time as _t
    now = int(_t.time())
    fake = (
        "selfdef_kernel_modules_textfile_emit_failed 0\n"
        f"selfdef_kernel_modules_last_run_unix {now}\n"
        "selfdef_kernel_modules_total 150\n"
        "selfdef_kernel_tainted 1\n"
        "selfdef_kernel_tainted_unsigned 0\n"
    )
    with patch.object(mod, "_fetch_metrics", return_value=fake):
        out = mod.probe_kernel_modules("http://localhost:9100/metrics")
    assert out["status"] == "WARN"
    assert "tainted" in out["summary"].lower()


def test_fail2ban_probe_detects_server_down():
    """fail2ban-server alive=0 = defensive-tier outage, must FAIL."""
    mod = _load_module()
    import time as _t
    now = int(_t.time())
    fake = (
        "selfdef_fail2ban_textfile_emit_failed 0\n"
        f"selfdef_fail2ban_last_run_unix {now}\n"
        "selfdef_fail2ban_server_alive 0\n"
        "selfdef_fail2ban_jails_active 0\n"
        "selfdef_fail2ban_current_bans_sum 0\n"
    )
    with patch.object(mod, "_fetch_metrics", return_value=fake):
        out = mod.probe_fail2ban("http://localhost:9100/metrics")
    assert out["status"] == "FAIL"
    assert "DOWN" in out["summary"] or "defensive" in out["summary"].lower()


def test_fail2ban_probe_honest_offline_on_minus_one():
    """alive=-1 (fail2ban-client not installed) = honest-offline, OK."""
    mod = _load_module()
    import time as _t
    now = int(_t.time())
    fake = (
        "selfdef_fail2ban_textfile_emit_failed 0\n"
        f"selfdef_fail2ban_last_run_unix {now}\n"
        "selfdef_fail2ban_server_alive -1\n"
        "selfdef_fail2ban_jails_active 0\n"
    )
    with patch.object(mod, "_fetch_metrics", return_value=fake):
        out = mod.probe_fail2ban("http://localhost:9100/metrics")
    assert out["status"] == "OK"
    assert "honest-offline" in out["summary"] or "not installed" in out["summary"]


def test_fail2ban_probe_detects_active_ban_spike():
    """> 50 currently-banned IPs = WARN (sustained brute-force wave)."""
    mod = _load_module()
    import time as _t
    now = int(_t.time())
    fake = (
        "selfdef_fail2ban_textfile_emit_failed 0\n"
        f"selfdef_fail2ban_last_run_unix {now}\n"
        "selfdef_fail2ban_server_alive 1\n"
        "selfdef_fail2ban_jails_active 2\n"
        "selfdef_fail2ban_current_bans_sum 75\n"
    )
    with patch.object(mod, "_fetch_metrics", return_value=fake):
        out = mod.probe_fail2ban("http://localhost:9100/metrics")
    assert out["status"] == "WARN"
    assert "75" in out["summary"]


def test_nftables_probe_detects_empty_ruleset():
    """nft installed + ruleset empty = FAIL (perimeter outage)."""
    mod = _load_module()
    import time as _t
    now = int(_t.time())
    fake = (
        "selfdef_nftables_textfile_emit_failed 0\n"
        f"selfdef_nftables_last_run_unix {now}\n"
        "selfdef_nftables_present 1\n"
        "selfdef_nftables_rules_total 0\n"
        "selfdef_conntrack_used_percent 30\n"
    )
    with patch.object(mod, "_fetch_metrics", return_value=fake):
        out = mod.probe_nftables("http://localhost:9100/metrics")
    assert out["status"] == "FAIL"
    assert "EMPTY" in out["summary"] or "perimeter" in out["summary"].lower()


def test_nftables_probe_detects_conntrack_near_full():
    """conntrack > 90% = FAIL (kernel drops new connections)."""
    mod = _load_module()
    import time as _t
    now = int(_t.time())
    fake = (
        "selfdef_nftables_textfile_emit_failed 0\n"
        f"selfdef_nftables_last_run_unix {now}\n"
        "selfdef_nftables_present 1\n"
        "selfdef_nftables_rules_total 42\n"
        "selfdef_conntrack_used_percent 95\n"
    )
    with patch.object(mod, "_fetch_metrics", return_value=fake):
        out = mod.probe_nftables("http://localhost:9100/metrics")
    assert out["status"] == "FAIL"
    assert "DROPPING" in out["summary"] or "95" in out["summary"]


def test_nftables_probe_detects_conntrack_high():
    """conntrack > 75% = WARN."""
    mod = _load_module()
    import time as _t
    now = int(_t.time())
    fake = (
        "selfdef_nftables_textfile_emit_failed 0\n"
        f"selfdef_nftables_last_run_unix {now}\n"
        "selfdef_nftables_present 1\n"
        "selfdef_nftables_rules_total 42\n"
        "selfdef_conntrack_used_percent 80\n"
    )
    with patch.object(mod, "_fetch_metrics", return_value=fake):
        out = mod.probe_nftables("http://localhost:9100/metrics")
    assert out["status"] == "WARN"
    assert "80" in out["summary"]


def test_nftables_probe_honest_offline_when_nft_absent():
    """present=0 = OK (honest-offline)."""
    mod = _load_module()
    import time as _t
    now = int(_t.time())
    fake = (
        "selfdef_nftables_textfile_emit_failed 0\n"
        f"selfdef_nftables_last_run_unix {now}\n"
        "selfdef_nftables_present 0\n"
        "selfdef_nftables_rules_total 0\n"
        "selfdef_conntrack_used_percent 10\n"
    )
    with patch.object(mod, "_fetch_metrics", return_value=fake):
        out = mod.probe_nftables("http://localhost:9100/metrics")
    assert out["status"] == "OK"
    assert "not installed" in out["summary"] or "honest-offline" in out["summary"]


def test_cron_probe_summarizes_inventory():
    """Cron probe is observational — OK when wrapper is fresh.
    Summary must include the three key counts."""
    mod = _load_module()
    import time as _t
    now = int(_t.time())
    fake = (
        "selfdef_cron_textfile_emit_failed 0\n"
        f"selfdef_cron_last_run_unix {now}\n"
        "selfdef_cron_d_files 3\n"
        "selfdef_cron_total_entries 12\n"
        "selfdef_systemd_timers_total 7\n"
    )
    with patch.object(mod, "_fetch_metrics", return_value=fake):
        out = mod.probe_cron("http://localhost:9100/metrics")
    assert out["status"] == "OK"
    assert "3 cron.d" in out["summary"]
    assert "12 entries" in out["summary"]
    assert "7 timers" in out["summary"]


def test_cron_probe_detects_silent_observer():
    """When last_run_unix is ancient, probe must FAIL."""
    mod = _load_module()
    fake = (
        "selfdef_cron_textfile_emit_failed 0\n"
        "selfdef_cron_last_run_unix 100\n"  # ancient
        "selfdef_cron_d_files 0\n"
    )
    with patch.object(mod, "_fetch_metrics", return_value=fake):
        out = mod.probe_cron("http://localhost:9100/metrics")
    assert out["status"] == "FAIL"


def test_modules_catalog_probe_detects_count_low():
    mod = _load_module()
    import time as _t
    now = int(_t.time())
    fake_metrics = (
        "selfdef_modules_textfile_emit_failed 0\n"
        f"selfdef_modules_last_run_unix {now}\n"
        "selfdef_modules_total 50\n"  # < 100 floor
    )
    with patch.object(mod, "_fetch_metrics", return_value=fake_metrics):
        out = mod.probe_modules_catalog("http://localhost:9100/metrics")
    assert out["status"] == "WARN"


def test_main_exit_code_2_on_unreachable():
    """When every vertical is unreachable (proxies down), exit code 2."""
    mod = _load_module()
    out = mod.main(["--json"])
    # All probes unreachable -> exit 2 (no proxies, no node_exporter).
    assert out == 2


def test_main_json_output_shape():
    mod = _load_module()
    import io
    import contextlib
    import json as _json
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        mod.main(["--json"])
    body = _json.loads(buf.getvalue())
    assert "verticals" in body
    assert "summary" in body
    assert set(body["verticals"].keys()) == set(CANONICAL_VERTICALS)
    assert set(body["summary"].keys()) == {
        "ok", "warn", "fail", "unreachable", "total",
    }


def test_sovereign_osctl_dispatch_includes_verb():
    """The sovereign-osctl dispatcher MUST have the new verb arm."""
    body = SOVEREIGN_OSCTL.read_text()
    assert "observability-status|obs-status" in body, (
        "sovereign-osctl missing observability-status dispatch arm"
    )
    assert "scripts/diagnostics/observability-status.py" in body


def test_sovereign_osctl_help_documents_verb():
    """The sovereign-osctl --help MUST advertise the new verb so
    operators discover it without spelunking the dispatcher source."""
    body = SOVEREIGN_OSCTL.read_text()
    assert "observability-status [--strict] [--json]" in body
