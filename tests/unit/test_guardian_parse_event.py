"""Guardian parse_event / neutralize_from_event against the REAL Tetragon shape.

Regression for the 2026-08-20 finding: guardian-core.py assumed a flat
{"action":"SIGKILL", "process":{...}} event, but Tetragon's --export-filename
emits nested process_kprobe with action="KPROBE_ACTION_SIGKILL". Guardian read
real violations as benign. These tests pin both shapes (nested + flat) so it
can't regress. The nested payload mirrors a sample captured live from
/var/run/tetragon/tetragon.events.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_G = Path(__file__).resolve().parents[2] / "scripts" / "auditor" / "guardian-core.py"
_spec = importlib.util.spec_from_file_location("guardian_core", _G)
gc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gc)  # top-level is side-effect free (main is __main__-guarded)

NESTED_SIGKILL = json.dumps({
    "process_kprobe": {
        "process": {"binary": "/bin/evil", "docker": "abc123def456", "exec_id": "x"},
        "function_name": "__x64_sys_execve",
        "action": "KPROBE_ACTION_SIGKILL",
        "policy_name": "sovereign-kernel-fence",
    },
    "node_name": "ai-workstation", "time": "2026-08-20T16:32:24Z",
})
NESTED_POST = json.dumps({
    "process_kprobe": {
        "process": {"binary": "/usr/bin/udevadm"},
        "action": "KPROBE_ACTION_POST",
    }, "time": "t",
})
FLAT_SIGKILL = json.dumps({
    "action": "SIGKILL",
    "process": {"docker": "cAAA", "binary": "/bin/evil"},
    "syscall": {"name": "sys_execve"},
})


def test_nested_sigkill_is_trigger():
    is_trig, _ = gc.parse_event(NESTED_SIGKILL)
    assert is_trig is True


def test_nested_monitor_post_is_benign():
    is_trig, _ = gc.parse_event(NESTED_POST)
    assert is_trig is False


def test_flat_sigkill_still_triggers():
    assert gc.parse_event(FLAT_SIGKILL)[0] is True


def test_bad_json_is_safe():
    is_trig, ev = gc.parse_event("}{ not json")
    assert is_trig is False and ev == {}


def test_neutralize_extracts_nested_fields(monkeypatch):
    seen = {}
    monkeypatch.setattr(gc, "alert_and_neutralize",
                        lambda c, p, s: seen.update(container=c, proc=p, sysc=s))
    _, ev = gc.parse_event(NESTED_SIGKILL)
    gc.neutralize_from_event(ev)
    assert seen == {"container": "abc123def456", "proc": "/bin/evil",
                    "sysc": "__x64_sys_execve"}


def test_neutralize_extracts_flat_fields(monkeypatch):
    seen = {}
    monkeypatch.setattr(gc, "alert_and_neutralize",
                        lambda c, p, s: seen.update(container=c, proc=p, sysc=s))
    _, ev = gc.parse_event(FLAT_SIGKILL)
    gc.neutralize_from_event(ev)
    assert seen == {"container": "cAAA", "proc": "/bin/evil", "sysc": "sys_execve"}
