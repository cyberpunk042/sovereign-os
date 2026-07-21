"""The avx-modes panel carries all 9 M002 dashboard surfaces (bucket 4).

The milestone lists 9 `dashboard`-type features (F00090/095/108/118/128/137/144/
153/162). Each has an operator-facing surface on the /avx-modes cockpit panel.
This pins that none can be silently dropped, and that the compute mirrors
(round engine + FNV-1a fingerprint) are wired into the page.
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PANEL = REPO / "webapp" / "avx-modes" / "index.html"

# (feature id, a stable marker that must appear in the panel)
SURFACES = [
    ("F00090", "Lane fields (M00012"),
    ("F00095", "cw-fields"),                 # control-word bit-layout inspector
    ("F00108", "per-lane heatmap (M00015"),
    ("F00118", "cw-lut"),                    # 64-entry LUT inspector
    ("F00128", "DNA visualizer (M00018"),
    ("F00137", "ZMM layout assignment (M00019"),
    ("F00144", "step timeline (M00020"),
    ("F00153", "Shift-cost comparison (M00021"),
    ("F00162", "Rule-word width comparison (M00022"),
]


def test_panel_present():
    assert PANEL.is_file(), f"missing {PANEL}"


def test_all_nine_m002_dashboard_surfaces_present():
    html = PANEL.read_text(encoding="utf-8")
    missing = [f"{fid} ({marker!r})" for fid, marker in SURFACES if marker not in html]
    assert not missing, (
        "avx-modes panel is missing M002 dashboard surface(s): " + ", ".join(missing)
    )


def test_compute_mirrors_are_wired():
    html = PANEL.read_text(encoding="utf-8")
    # the round engine + fingerprint mirrors must be inline (the surfaces compute
    # live from the same bit-logic as the crate/CLI, not static mockups)
    for marker in ("function roundUpdate", "function laneFingerprint",
                   "function extractFeatures", "function advanceRng"):
        assert marker in html, f"panel lost its compute mirror: {marker}"


def test_no_aggressive_word_break():
    # cousin of test_text_wrap_contract — the new viz uses overflow-wrap:anywhere
    html = PANEL.read_text(encoding="utf-8")
    assert "word-break:break-all" not in html.replace(" ", "")


# M007 + M008 surfaces (the branch scheduler + AVX-512 cheats)
M78_SURFACES = [
    ("F00605", "VPTERNLOG fuse-policy (M00114"),
    ("F00615", "VPCOMPRESS sparse→dense (M00116"),
    ("M007", "M007 8-step branch loop (E0052"),
    ("F00623", "Token-law bitset (M00117"),
    ("M00122", "Bloom overlap (M00122"),
    ("M00113", "Bitfields-as-microcode (M00113"),
    ("M085-T1", "T1 VNNI INT8 dot (M085"),
    ("M085-T2", "T2 attention-mask fuse (M085"),
]


def test_m007_m008_surfaces_present():
    html = PANEL.read_text(encoding="utf-8")
    missing = [f"{fid} ({marker!r})" for fid, marker in M78_SURFACES if marker not in html]
    assert not missing, "avx-modes panel is missing M007/M008 surface(s): " + ", ".join(missing)


# ── Live active-mode prefill (2026-07-21) ──────────────────────────────────
# The settings-pane AVX select (shared app-shell snippet, on every adopted
# panel) defaulted to the first option ('custom') regardless of the box's real
# mode — the notifykit-class blank-select gap. It now prefills from the
# read-only GET /api/control/avx-mode inventory (same truth as
# `sovereign-osctl avx-mode inventory`) and surfaces which mode is engaged.

SHARED_SHELL = REPO / "webapp" / "_shared" / "app-shell-snippet.html"
EXEC_API = REPO / "scripts" / "operator" / "control-exec-api.py"


def test_avx_select_prefills_from_live_state():
    shell = SHARED_SHELL.read_text(encoding="utf-8")
    # the read-only inventory fetch + the prefill assignment + the live indicator
    assert "fetch('/api/control/avx-mode'" in shell
    assert "function soAvxLive(" in shell
    assert "avxSel.value=p.active" in shell
    assert "avxLiveActive" in shell
    assert "Active on the box:" in shell
    # prefill actually runs on init (not just defined)
    assert "avxBackingRefresh(); soAvxLive();" in shell


def test_exec_api_serves_the_avx_mode_inventory():
    api = EXEC_API.read_text(encoding="utf-8")
    assert '/api/control/avx-mode' in api, "control-exec-api must serve the avx-mode route"
    assert "_avx_mode.inventory()" in api
    # the bit-machine engagement is the custom/hybrid gate (matches the crate)
    assert 'in ("custom", "hybrid")' in api
    # degrades honestly when the module is absent (never kills the rail)
    assert "avx-mode module unavailable" in api


# ── health-scan probe #8: the AVX-mode execution posture (2026-07-21) ───────
# avx-mode is a live mode like cpu_mode (which has a probe) but had none. The
# probe surfaces which execution path is active AND — when the bit-machine
# (custom/hybrid) is engaged — whether the host actually carries the AVX-512 F
# floor; if not, the ZMM kernels fall back to scalar (a grounded attention).

import importlib.util as _ilu


def _load_health_scan():
    spec = _ilu.spec_from_file_location(
        "health_scan", REPO / "scripts" / "hardware" / "health-scan.py")
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _probe_with(monkeypatch, avx_json, advisor_json="{}"):
    hs = _load_health_scan()

    def fake(script, args):
        if script == "avx-mode.py":
            return (0, avx_json, "")
        if script == "avx512-advisor.py":
            return (0, advisor_json, "")
        return (0, "{}", "")

    hs._run_probe = fake
    return hs.probe_avx_mode()


def test_avx_probe_registered_as_eighth():
    hs = _load_health_scan()
    assert "avx_mode" in hs.PROBES
    assert len(hs.PROBES) == 8


def test_avx_probe_math_path_is_informational(monkeypatch):
    r = _probe_with(monkeypatch, '{"active":"builtin"}')
    assert r["probe"] == "avx_mode" and r["severity"] == "informational"
    assert "not engaged" in r["detail"]


def test_avx_probe_engaged_with_avx512_is_ok(monkeypatch):
    r = _probe_with(monkeypatch, '{"active":"custom"}', '{"avx512_supported":true}')
    assert r["severity"] == "ok" and "bit-machine engaged" in r["detail"]


def test_avx_probe_engaged_without_avx512_is_attention(monkeypatch):
    r = _probe_with(monkeypatch, '{"active":"hybrid"}', '{"avx512_supported":false}')
    assert r["severity"] == "attention" and r["rc"] == 1
    assert "fall back to scalar" in r["detail"]
    assert r["flagged_items"] == [{"id": "avx512f", "present": False}]


def test_avx_probe_unreadable_degrades_informational(monkeypatch):
    r = _probe_with(monkeypatch, "not json")
    assert r["severity"] == "informational" and "unreadable" in r["detail"]


# ── compute posture in `sovereign-osctl status` + notify fan-out (2026-07-21) ──
import json as _json
import subprocess as _sp
import sys as _sys

STATUS_SH = REPO / "scripts" / "osctl.d" / "status.sh"
DISPATCH = REPO / "scripts" / "notify" / "dispatch.py"


def test_status_surfaces_compute_posture():
    """`sovereign-osctl status` gained a [Compute posture] section surfacing
    the avx_mode + cpu_mode + compat health-scan verdicts where the operator
    reads status (previously they only lived in the machine-readable scan)."""
    sh = STATUS_SH.read_text(encoding="utf-8")
    assert "[Compute posture]" in sh
    assert "for _probe in avx_mode cpu_mode compat" in sh
    assert "health-scan.py" in sh
    # attention is marked, and a probe rc=1 (attention) must not fail status
    assert "[!] " in sh and "|| true" in sh


def test_avx_attention_flows_through_notify_dispatch(tmp_path):
    """R228 fan-out is generic over probes — a NEW probe reaching attention
    notifies with zero per-probe wiring. Prove it for avx_mode via a synthetic
    scan (the hardware attention — custom bit-machine on a non-AVX-512 host —
    cannot be forced by env, so feed the scan through --from-file)."""
    scan = tmp_path / "scan.json"
    scan.write_text(_json.dumps({
        "round": "R226", "vector": "SDD-026 Z-6 (scan layer)",
        "started_at": "2026-07-21T00:00:00Z",
        "probes": [{
            "probe": "avx_mode", "round": "R226+", "vector": "Z-4",
            "rc": 1, "severity": "attention",
            "detail": "custom: bit-machine engaged but this host lacks the AVX-512 F floor",
            "flagged_items": [{"id": "avx512f", "present": False}],
        }],
        "summary": {"total": 1, "ok": 0, "attention": 1, "informational": 0},
        "needs_attention": True,
    }), encoding="utf-8")
    sink = tmp_path / "sink.jsonl"
    cfg = tmp_path / "notifykit.toml"
    cfg.write_text(
        f'[channels.file]\nkind = "file"\nenabled = true\npath = "{sink}"\n',
        encoding="utf-8")
    env = dict(**{k: v for k, v in __import__("os").environ.items()})
    env["SOVEREIGN_OS_NOTIFYKIT_CONFIG"] = str(cfg)
    env["SOVEREIGN_OS_NOTIFYKIT_OVERRIDES"] = str(tmp_path / "ov.json")
    env["SOVEREIGN_OS_NOTIFY_STATE"] = str(tmp_path / "state.json")
    env["SOVEREIGN_OS_NOTIFY_CONFIG"] = str(tmp_path / "absent-notify.toml")
    r = _sp.run([_sys.executable, str(DISPATCH), "dispatch",
                 "--from-file", str(scan), "--json"],
                capture_output=True, text=True, env=env)
    out = _json.loads(r.stdout)
    events = {e["probe"] for e in out.get("events", [])}
    assert "avx_mode" in events, out
    rows = [_json.loads(x) for x in sink.read_text().splitlines()] if sink.exists() else []
    assert any("avx_mode" in x.get("title", "") for x in rows), rows
