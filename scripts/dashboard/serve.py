#!/usr/bin/env python3
"""scripts/dashboard/serve.py — R225 (SDD-026 Z-1) dashboard SEED.

Operator-named (verbatim from the 2026-05-17 directive expansion):
"Always in the optic that this Debian 13 Sovereign OS is a non-GUI
by default. I will obviously be able to plug a screen or mainly
connect remotely to ssh and/or dashboard or API on whatsoever pot
for whatsoever dashbaords and modules and tools."

Minimal-stack HTTP server (stdlib http.server — no JS framework, no
npm chain, no template engine; the master spec ethos is "no bloat").
Serves a SINGLE page that aggregates every shipped Z-vector card:

  - GPU watt deviance  (R219 / Z-5 — scripts/hardware/gpu-watch.py)
  - Network state      (R220 / Z-7 — scripts/hardware/network-status.py)
  - CPU mode           (R221 / Z-4 — scripts/hardware/cpu-mode.py)
  - FS usage           (R222 / Z-10 — scripts/hardware/fs-insights.py)
  - RAID status        (R223 / Z-9 — scripts/hardware/raid-status.py)
  - Flex-profile state (R224 / Z-3 — scripts/hardware/profile-flex.py)

Each card invokes the underlying script's `--json` mode + renders a
small HTML block. Operator-readable. No mutations.

Endpoints:
  GET /             — full dashboard page
  GET /api/health   — aggregated JSON for all cards (machine-readable)
  GET /api/gpu      — single-card JSON (one per shipped Z-vector)
  GET /api/network
  GET /api/cpu
  GET /api/fs
  GET /api/raid
  GET /api/flex

Bind: 127.0.0.1:8443 by default. Operator opts in to exposure by
overriding --bind. Future round adds /etc/sovereign-os/dashboard.toml
allowlist + tailscale-only mode.

Run:
  sovereign-osctl dashboard serve            # blocks; Ctrl-C to stop
  sovereign-osctl dashboard serve --bind 0.0.0.0:8443 --json

Exit codes:
  0  clean shutdown
  2  usage error / bind failure

Tested via `--once` mode that handles ONE request + exits 0 (so the
L3 test can curl without spawning a separate process).
"""
from __future__ import annotations

import argparse
import hmac
import html
import json
import os
import shutil
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
from pathlib import Path
from typing import Any

try:
    import tomllib  # Python 3.11+
except ImportError:  # pragma: no cover
    import tomli as tomllib  # type: ignore


# R250 (SDD-026 Z-1 auth): per-process loaded auth config. Set by
# main() before the server starts; None means "no auth — same as
# cycle-8 SEED behavior, safe on loopback / tailscale-private binds".
AUTH_CONFIG: dict[str, Any] | None = None


def load_auth_config() -> dict[str, Any] | None:
    """R250: returns {token, allow_loopback, allow_ips} when config present.

    Path resolution: env SOVEREIGN_OS_DASHBOARD_AUTH_CONFIG overrides,
    then /etc/sovereign-os/dashboard-auth.toml, then the in-repo example
    file. Operator-supplied token is read from the env var named by
    `token_env` (operator secrets never in-repo per SDD-009).
    """
    env = os.environ.get("SOVEREIGN_OS_DASHBOARD_AUTH_CONFIG")
    candidate_paths: list[Path] = []
    if env:
        candidate_paths.append(Path(env))
    candidate_paths.append(Path("/etc/sovereign-os/dashboard-auth.toml"))
    candidate_paths.append(REPO_ROOT / "config" / "dashboard-auth.toml.example")
    cfg_path = next((p for p in candidate_paths if p.exists()), None)
    if cfg_path is None:
        return None
    try:
        with cfg_path.open("rb") as fh:
            doc = tomllib.load(fh)
    except OSError:
        return None
    token_env = doc.get("token_env")
    token = os.environ.get(token_env) if token_env else None
    return {
        "config_source": str(cfg_path),
        "token": token,
        "token_env": token_env,
        "allow_loopback": bool(doc.get("allow_loopback", True)),
        "allow_ips": [str(s) for s in (doc.get("allow_ips") or [])],
    }


def _is_loopback(addr: str) -> bool:
    return addr in {"127.0.0.1", "::1", "::ffff:127.0.0.1"}

REPO_ROOT = Path(__file__).resolve().parents[2]


# --------------------------------------------------------- card adapters


def _run_json_at(path: Path, args: list[str]) -> dict[str, Any] | None:
    """Variant of _run_json that takes an arbitrary script path
    instead of assuming scripts/hardware/. Used by the SDD-065
    cockpit card (lives under scripts/cockpit/)."""
    if not path.exists():
        return None
    try:
        r = subprocess.run(
            [sys.executable, str(path), *args, "--json"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if not r.stdout.strip():
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None


def _run_json(script: str, args: list[str]) -> dict[str, Any] | None:
    """Invoke a sibling script with --json and return parsed payload."""
    bin_path = REPO_ROOT / "scripts" / "hardware" / script
    if not bin_path.exists():
        return None
    try:
        r = subprocess.run(
            [sys.executable, str(bin_path), *args, "--json"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if not r.stdout.strip():
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None


def _run_selfdefctl(args: list[str]) -> tuple[dict[str, Any] | None, str | None]:
    """R289 (E4.M9): invoke selfdefctl with --json appended; return
    (parsed_payload, error_hint). When selfdefctl isn't on PATH, the
    second value is the operator-readable setup hint.
    """
    sd_path = shutil.which("selfdefctl")
    if not sd_path:
        return None, (
            "selfdefctl not on PATH; install the selfdef-cli crate "
            "or set PATH to include its build dir"
        )
    try:
        r = subprocess.run(
            [sd_path, *args, "--json"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        return None, f"selfdefctl invocation failed: {type(e).__name__}: {e}"
    if r.returncode != 0:
        # Surface the first ~200 chars of stderr to help the operator
        # diagnose (unknown slug, missing modules dir, etc).
        msg = (r.stderr or r.stdout or "").strip().splitlines()
        return None, ("selfdefctl exited "
                      f"rc={r.returncode}: {(msg[0] if msg else '')[:200]}")
    try:
        return json.loads(r.stdout), None
    except json.JSONDecodeError as e:
        return None, f"selfdefctl JSON parse error: {e}"


def card_gpu() -> dict[str, Any]:
    """R219 Z-5 — gpu-watch JSON."""
    data = _run_json("gpu-watch.py", []) or {"gpus": [], "any_deviance": False}
    return {"id": "gpu", "title": "GPU watt deviance (R219 / Z-5)", "data": data}


def card_network() -> dict[str, Any]:
    """R220 Z-7 — network-status JSON."""
    data = _run_json("network-status.py", []) or {"components": []}
    return {"id": "network", "title": "Network state (R220 / Z-7)", "data": data}


def card_cpu() -> dict[str, Any]:
    """R221 Z-4 — cpu-mode show JSON."""
    data = _run_json("cpu-mode.py", ["show"]) or {"cpus": {}}
    return {"id": "cpu", "title": "CPU mode (R221 / Z-4)", "data": data}


def card_fs() -> dict[str, Any]:
    """R222 Z-10 — fs-insights usage JSON."""
    data = _run_json("fs-insights.py", ["usage"]) or {"partitions": []}
    return {"id": "fs", "title": "Filesystem usage (R222 / Z-10)", "data": data}


def card_raid() -> dict[str, Any]:
    """R223 Z-9 — raid-status status JSON."""
    data = _run_json("raid-status.py", ["status"]) or {"arrays": [], "count": 0}
    return {"id": "raid", "title": "Software RAID (R223 / Z-9)", "data": data}


def card_blockset_queue() -> dict[str, Any]:
    """SDD-065 MS5b — pending operator-extension queue for the
    selfdef IP-block action layer. Reads scripts/cockpit/
    blockset-queue.py --json (which in turn reads the selfdef-
    side pending-extensions.json snapshot). Each entry displays
    addr / time-left / reason / pre-rendered extend command."""
    cockpit_script = REPO_ROOT / "scripts" / "cockpit" / "blockset-queue.py"
    data = _run_json_at(cockpit_script, []) or {"queue": [], "count": 0}
    return {
        "id": "blockset-queue",
        "title": "SDD-065 — pending IP-block extension decisions",
        "data": data,
    }


def card_quarantine_queue() -> dict[str, Any]:
    """SDD-066 MS5b — pending operator-release queue for the
    selfdef process-quarantine action layer. Reads scripts/cockpit/
    quarantine-queue.py --json. Each entry shows pid / time-left /
    scope / reason / pre-rendered release + kill-TERM + kill-KILL
    commands. Pairs with card_blockset_queue when the correlator
    fires both BlockIp + QuarantineProcess on the same incident."""
    cockpit_script = REPO_ROOT / "scripts" / "cockpit" / "quarantine-queue.py"
    data = _run_json_at(cockpit_script, []) or {"queue": [], "count": 0}
    return {
        "id": "quarantine-queue",
        "title": "SDD-066 — pending process-quarantine release decisions",
        "data": data,
    }


def card_revocations_queue() -> dict[str, Any]:
    """SDD-067 MS5b — pending operator-restore queue for the
    selfdef session-revocation action layer. Reads scripts/cockpit/
    revocations-queue.py --json. Each entry shows user / time-left /
    scope (Local or SourceIp(addr)) / reason / pre-rendered
    `selfdefctl restore-sessions` command. Completes the IPS-trio
    paired-decision queue family: blockset + quarantine + revocations
    appear together at the top of the dashboard so the operator
    sees correlator-paired-handle incidents in a coherent row."""
    cockpit_script = REPO_ROOT / "scripts" / "cockpit" / "revocations-queue.py"
    data = _run_json_at(cockpit_script, []) or {"queue": [], "count": 0}
    return {
        "id": "revocations-queue",
        "title": "SDD-067 — pending session-revocation restore decisions",
        "data": data,
    }


def card_token_revocations_queue() -> dict[str, Any]:
    """SDD-068 MS5b — pending operator-restore queue for the
    selfdef API/web-token revocation action layer. Reads
    scripts/cockpit/token-revocations-queue.py --json. Fourth in
    the IPS-quartet paired-decision queue family — completes the
    quartet-paired-handle row across blockset + quarantine +
    revocations + token-revocations."""
    cockpit_script = REPO_ROOT / "scripts" / "cockpit" / "token-revocations-queue.py"
    data = _run_json_at(cockpit_script, []) or {"queue": [], "count": 0}
    return {
        "id": "token-revocations-queue",
        "title": "SDD-068 — pending token-revocation restore decisions",
        "data": data,
    }


def card_mfa_grant_revocations_queue() -> dict[str, Any]:
    """SDD-069 MS5b — pending operator-restore queue for the
    selfdef MFA-grant revocation action layer. Fifth and final in
    the IPS-pentet paired-decision queue family."""
    cockpit_script = REPO_ROOT / "scripts" / "cockpit" / "mfa-grant-revocations-queue.py"
    data = _run_json_at(cockpit_script, []) or {"queue": [], "count": 0}
    return {
        "id": "mfa-grant-revocations-queue",
        "title": "SDD-069 — pending MFA-grant revocation restore decisions",
        "data": data,
    }


def card_netns_isolations_queue() -> dict[str, Any]:
    """SDD-070 MS5b — pending operator-release queue for the
    selfdef netns-isolation action layer. Sixth in the IPS-hexet
    paired-decision queue family (kernel-containment axis)."""
    cockpit_script = REPO_ROOT / "scripts" / "cockpit" / "netns-isolations-queue.py"
    data = _run_json_at(cockpit_script, []) or {"queue": [], "count": 0}
    return {
        "id": "netns-isolations-queue",
        "title": "SDD-070 — pending netns-isolation release decisions",
        "data": data,
    }


def card_mount_bindings_queue() -> dict[str, Any]:
    """SDD-071 MS5b — pending operator-rebind queue for the selfdef
    mount-binding unbind action layer. Seventh in the IPS-septet
    paired-decision queue family (filesystem-binding axis)."""
    cockpit_script = REPO_ROOT / "scripts" / "cockpit" / "mount-bindings-queue.py"
    data = _run_json_at(cockpit_script, []) or {"queue": [], "count": 0}
    return {
        "id": "mount-bindings-queue",
        "title": "SDD-071 — pending mount-binding rebind decisions",
        "data": data,
    }


def card_process_tree_freezes_queue() -> dict[str, Any]:
    """SDD-072 MS5b — pending operator-thaw queue for the selfdef
    process-tree freeze action layer. Eighth in the IPS-octet
    paired-decision queue family (process-graph containment axis)."""
    cockpit_script = REPO_ROOT / "scripts" / "cockpit" / "process-tree-freezes-queue.py"
    data = _run_json_at(cockpit_script, []) or {"queue": [], "count": 0}
    return {
        "id": "process-tree-freezes-queue",
        "title": "SDD-072 — pending process-tree thaw decisions",
        "data": data,
    }


def card_socket_fd_revocations_queue() -> dict[str, Any]:
    """SDD-073 MS5b — pending operator-restore queue for the selfdef
    socket-fd revocation action layer. Ninth in the IPS-nonet
    paired-decision queue family (per-connection severance axis)."""
    cockpit_script = REPO_ROOT / "scripts" / "cockpit" / "socket-fd-revocations-queue.py"
    data = _run_json_at(cockpit_script, []) or {"queue": [], "count": 0}
    return {
        "id": "socket-fd-revocations-queue",
        "title": "SDD-073 — pending socket-fd-revocation restore decisions",
        "data": data,
    }


def card_env_scrubs_queue() -> dict[str, Any]:
    """SDD-074 MS5b — pending operator-restore queue for the selfdef
    process-env scrub action layer. Tenth in the IPS-dectet
    paired-decision queue family (in-memory secret-residency axis)."""
    cockpit_script = REPO_ROOT / "scripts" / "cockpit" / "env-scrubs-queue.py"
    data = _run_json_at(cockpit_script, []) or {"queue": [], "count": 0}
    return {
        "id": "env-scrubs-queue",
        "title": "SDD-074 — pending env-scrub restore decisions",
        "data": data,
    }


def card_capability_drops_queue() -> dict[str, Any]:
    """SDD-075 MS5b — pending operator-restore queue for the selfdef
    per-process capability-drop action layer. Eleventh in the
    IPS-undectet paired-decision queue family (per-process privilege-
    set axis). Restore is queue-clear + audit only — capability
    drops are irreversible at the kernel level; operator must
    restart the process to recover the dropped capability."""
    cockpit_script = REPO_ROOT / "scripts" / "cockpit" / "capability-drops-queue.py"
    data = _run_json_at(cockpit_script, []) or {"queue": [], "count": 0}
    return {
        "id": "capability-drops-queue",
        "title": "SDD-075 — pending capability-drop restore decisions",
        "data": data,
    }


def card_bpf_map_element_clears_queue() -> dict[str, Any]:
    """SDD-078 MS5b — pending operator-restore queue for the selfdef
    eBPF map element clear action layer. Fourteenth in the
    IPS-quattuordectet paired-decision queue family (eBPF map state
    axis). Restore is queue-clear + audit only — BPF map element
    clears are one-way at the kernel level; selfdef did not snapshot
    prior values; the owning BPF program's control plane must re-add
    elements through its normal data path."""
    cockpit_script = REPO_ROOT / "scripts" / "cockpit" / "bpf-map-element-clears-queue.py"
    data = _run_json_at(cockpit_script, []) or {"queue": [], "count": 0}
    return {
        "id": "bpf-map-element-clears-queue",
        "title": "SDD-078 — pending bpf-map-element-clear restore decisions",
        "data": data,
    }


def card_apparmor_profile_pivots_queue() -> dict[str, Any]:
    """SDD-077 MS5b — pending operator-restore queue for the selfdef
    AppArmor live profile-pivot action layer. Thirteenth in the
    IPS-tridectet paired-decision queue family (MAC policy axis).
    Restore is queue-clear + audit only — AppArmor profile pivots
    are one-way at the kernel level; operator must restart the
    process under its original profile via the init system to
    recover."""
    cockpit_script = REPO_ROOT / "scripts" / "cockpit" / "apparmor-profile-pivots-queue.py"
    data = _run_json_at(cockpit_script, []) or {"queue": [], "count": 0}
    return {
        "id": "apparmor-profile-pivots-queue",
        "title": "SDD-077 — pending apparmor-profile-pivot restore decisions",
        "data": data,
    }


def card_scheduler_status() -> dict[str, Any]:
    """MS048 M01166 — Goldilocks Scheduler status card. Reads the
    selfdef MS048 textfile (M01174 binary writes it every 60s) and
    surfaces the substrate trio + backpressure state + per-source
    health in the cockpit.

    Peer (not part) of the IPS-quattuordectet queue cards: the
    scheduler is the runtime-routing layer; the 14 IPS axes are the
    enforcement layer. Both contribute to the workstation at
    different architectural altitudes per Peace Machine + Core Law.

    Returns a single composite card with status badge
    (OK | DEGRADED | PRESSURED | BLIND | SILENT | WEDGED), the
    per-substrate health rows, the measurement values, and the
    backpressure-firing list. When the textfile is missing/stale,
    the card honestly reports WEDGED / SILENT rather than fabricating
    zeros (per the honest-offline doctrine the 14 IPS observers
    already follow)."""
    cockpit_script = REPO_ROOT / "scripts" / "cockpit" / "scheduler-status.py"
    data = _run_json_at(cockpit_script, []) or {
        "status": "WEDGED",
        "measurements": {},
        "state": {},
        "substrate_health": {},
        "substrate_degraded_count": 3,
        "last_run_unix": 0,
        "textfile_emit_failed": True,
        # MS048 decision metrics — empty when the cockpit script is
        # unreachable, matching scheduler-status.py's own WEDGED fallback so
        # the card data shape is identical whether the script succeeds or fails.
        "decisions": {"in_ring": 0, "hibernate": 0, "by_route": {}},
    }
    return {
        "id": "scheduler-status",
        "title": "MS048 — Goldilocks Scheduler status (runtime routing layer)",
        "data": data,
    }


def card_kernel_keyring_evictions_queue() -> dict[str, Any]:
    """SDD-076 MS5b — pending operator-restore queue for the selfdef
    kernel-keyring eviction action layer. Twelfth in the
    IPS-duodectet paired-decision queue family (kernel-keyring axis).
    Restore is queue-clear + audit only — kernel-keyring entries that
    were invalidated/unlinked are gone; operator must re-provision
    the key material (re-fetch TGT, re-register session key, etc.)
    to recover."""
    cockpit_script = REPO_ROOT / "scripts" / "cockpit" / "kernel-keyring-evictions-queue.py"
    data = _run_json_at(cockpit_script, []) or {"queue": [], "count": 0}
    return {
        "id": "kernel-keyring-evictions-queue",
        "title": "SDD-076 — pending kernel-keyring-eviction restore decisions",
        "data": data,
    }


def card_flex() -> dict[str, Any]:
    """R224 Z-3 — profile-flex show JSON."""
    data = _run_json("profile-flex.py", ["show"]) or {"deltas": []}
    return {"id": "flex", "title": "Flex profile (R224 / Z-3)", "data": data}


def card_health() -> dict[str, Any]:
    """R226 Z-6 — composite health-scan JSON."""
    data = _run_json("health-scan.py", []) or {
        "probes": [], "summary": {}, "needs_attention": False
    }
    return {
        "id": "health",
        "title": "Health scan (R226 / Z-6)",
        "data": data,
    }


def card_morning_brief() -> dict[str, Any]:
    """R354 (E4.M10) — R352 morning-brief rollup on dashboard.
    Operator-pull "what should I look at first this morning?" — composes
    R329 next-action + R351 module-state + R308 autohealth + R349
    guide-suggestion into one card."""
    data = _run_intel_script("morning-brief.py", ["rollup"]) or {
        "critical_signals_count": 0,
        "critical_signals": [],
        "sections": {},
        "suggested_topic_guide": None,
        "suggested_topic_verb": None,
    }
    crit = int(data.get("critical_signals_count") or 0)
    suggested = data.get("suggested_topic_guide")
    if crit:
        summary = f"{crit} critical signal(s); start with: {suggested or 'next-action top'}"
    elif suggested:
        summary = f"no criticals; suggested reading: guide walkthrough {suggested}"
    else:
        summary = "no criticals; no specific topic suggested"
    data["summary"] = summary
    data["needs_attention"] = crit > 0
    return {
        "id": "morning_brief",
        "title": "Morning brief (R352 / E10.M2)",
        "data": data,
    }


def card_module_state() -> dict[str, Any]:
    """R354 (E4.M10) — R351 module-state on dashboard.
    Lists modules in {installed-not-configured / running-without-overlay
    / config-only-no-runtime / fully-configured / shipped-but-untouched}
    state with operator-runnable configure_verb for each gap."""
    data = _run_intel_script("module-state.py", ["recommend"]) or {
        "attention_count": 0, "attention_items": [],
        "all_modules_summary": {},
    }
    attn = int(data.get("attention_count") or 0)
    total = len(data.get("all_modules_summary") or {})
    data["summary"] = (
        f"{attn}/{total} module(s) need attention"
        if total else "no modules catalogued"
    )
    # Running-without-overlay is the only state that's truly "attention"
    # for the grid glyph (installed-not-configured is informational —
    # operator may legitimately not have touched a module yet).
    data["needs_attention"] = any(
        m.get("verdict") == "running-without-overlay"
        for m in (data.get("attention_items") or [])
    )
    return {
        "id": "module_state",
        "title": "Module state (R351 / E2.M34)",
        "data": data,
    }


def card_guide() -> dict[str, Any]:
    """R354 (E4.M10) — R349 guide topic catalog on dashboard.
    Lists all topics (axis-grouped) so operator clicks into
    'walkthrough <topic>' from the UI instead of remembering CLI verb."""
    data = _run_intel_script("guide.py", ["list"]) or {
        "topic_count": 0, "topics": [],
    }
    n = int(data.get("topic_count") or 0)
    axes = sorted({t.get("axis") for t in (data.get("topics") or [])
                   if isinstance(t, dict) and t.get("axis")})
    data["summary"] = (
        f"{n} topics across {len(axes)} axes: {', '.join(axes)}"
        if n else "guide catalog unavailable"
    )
    data["needs_attention"] = False  # informational card
    return {
        "id": "guide",
        "title": "Guide topics (R349 / E10.M1)",
        "data": data,
    }


def card_model_adapt() -> dict[str, Any]:
    """R354 (E4.M10) — R350 model-adapt recipes on dashboard.
    Shows the recipe catalog + per-recipe VRAM fit; operator picks one
    matching their target task before kicking off the fine-tune pipeline."""
    data = _run_models_script("adapt.py", ["recipes"]) or {
        "recipe_count": 0, "recipes": [], "declared_gpus": [],
    }
    n = int(data.get("recipe_count") or 0)
    ng = len(data.get("declared_gpus") or [])
    data["summary"] = (
        f"{n} adaptation recipe(s); {ng} declared GPU(s)"
        if n else "adapt catalog unavailable"
    )
    data["needs_attention"] = False  # informational catalog
    return {
        "id": "model_adapt",
        "title": "Model-adapt recipes (R350 / E5.M17)",
        "data": data,
    }


def card_model_build() -> dict[str, Any]:
    """R354 (E4.M10) — R353 model-build recipes on dashboard.
    Shows the 4 build recipes (merge-lora / quantize-gguf / quantize-awq
    / export-safetensors) + recent build history (JSONL tail)."""
    recipes = _run_models_script("build.py", ["recipes"]) or {
        "recipe_count": 0, "recipes": [],
    }
    history = _run_models_script("build.py", ["history"]) or {
        "entry_count": 0, "entries": [],
    }
    data = {
        "recipes": recipes.get("recipes", []),
        "recipe_count": recipes.get("recipe_count", 0),
        "history_entry_count": history.get("entry_count", 0),
        "recent_builds": history.get("entries", [])[-5:],
    }
    rc = int(data.get("recipe_count") or 0)
    hc = int(data.get("history_entry_count") or 0)
    data["summary"] = (
        f"{rc} build recipe(s); {hc} historical build(s) on this host"
        if rc else "build catalog unavailable"
    )
    data["needs_attention"] = False  # informational catalog
    return {
        "id": "model_build",
        "title": "Model-build (R353 / E5.M18)",
        "data": data,
    }


def _run_models_script(script: str, args: list[str]) -> dict[str, Any] | None:
    """Variant of _run_json for scripts/models/*.py."""
    bin_path = REPO_ROOT / "scripts" / "models" / script
    if not bin_path.exists():
        return None
    try:
        r = subprocess.run(
            [sys.executable, str(bin_path), *args, "--json"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if not r.stdout.strip():
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None


def _run_intel_script(script: str, args: list[str]) -> dict[str, Any] | None:
    """R354 (E4.M10): variant of _run_json for scripts/intelligence/*.py.
    Used by R349 guide / R350 model-adapt / R351 module-state / R352
    morning-brief cards. Same NEVER-raise semantics as _run_json."""
    bin_path = REPO_ROOT / "scripts" / "intelligence" / script
    if not bin_path.exists():
        return None
    try:
        r = subprocess.run(
            [sys.executable, str(bin_path), *args, "--json"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if not r.stdout.strip():
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None


def card_models() -> dict[str, Any]:
    """R227 Z-2 — Models tab (LM-Studio-equivalent surface).

    Aggregates the R212 catalog query + R214 profile-aware suggester
    into ONE dashboard card. Operators browse the curated model
    matrix (class × quantization × size × purpose) + see for each
    runtime profile which allocations are flagged.

    Data shape:
      catalog_count        — total catalog entries
      verified_real_count  — operator-pullable today
      aspirational_count   — catalog declares but no real repo
      by_class             — taxonomy histogram
      by_quantization      — quant histogram
      suggester            — per-runtime-profile flag summary
    """
    catalog = _run_models_script("catalog-query.py", []) or {}
    models = catalog.get("models") or []
    by_class: dict[str, int] = {}
    by_quant: dict[str, int] = {}
    verified = 0
    aspirational = 0
    for m in models:
        if m.get("class"):
            by_class[m["class"]] = by_class.get(m["class"], 0) + 1
        if m.get("quantization"):
            by_quant[m["quantization"]] = by_quant.get(m["quantization"], 0) + 1
        if m.get("status") == "verified-real":
            verified += 1
        elif m.get("status") == "aspirational":
            aspirational += 1
    # Per-runtime-profile suggester rollup (R214)
    suggester_rollup: list[dict[str, Any]] = []
    for pid in ("ultra-sovereign-efficiency", "high-concurrency-burst", "deep-context-synthesis"):
        s = _run_models_script("suggest-by-profile.py", ["--runtime-profile", pid])
        if s is not None:
            allocations = s.get("allocations") or []
            flagged = sum(1 for a in allocations if a.get("flags"))
            suggester_rollup.append({
                "profile_id": pid,
                "allocations_total": len(allocations),
                "allocations_flagged": flagged,
                "any_flagged": s.get("any_flagged", False),
            })
    data: dict[str, Any] = {
        "catalog_count": len(models),
        "verified_real_count": verified,
        "aspirational_count": aspirational,
        "by_class": by_class,
        "by_quantization": by_quant,
        "suggester_per_profile": suggester_rollup,
    }
    return {
        "id": "models",
        "title": "Models — catalog × profile (R227 / Z-2)",
        "data": data,
    }


def card_insights() -> dict[str, Any]:
    """R235 (SDD-026 Z-10 dashboard surface) — Insights card.

    Calls R234 `insights synthesize` and renders the top-3 highest-
    severity findings as a card. needs_attention is surfaced into the
    card payload so dashboard CSS can color the section header.
    """
    bin_path = REPO_ROOT / "scripts" / "insights" / "synthesize.py"
    fallback: dict[str, Any] = {
        "round": "R235",
        "vector": "SDD-026 Z-10 dashboard",
        "needs_attention": False,
        "counts": {"critical": 0, "attention": 0, "informational": 0, "total": 0},
        "top": [],
        "summary": "synthesize.py unavailable",
    }
    if not bin_path.exists():
        fallback["summary"] = "synthesize.py not shipped"
        return {
            "id": "insights",
            "title": "Insights (R234 / Z-10)",
            "data": fallback,
        }
    try:
        r = subprocess.run(
            [sys.executable, str(bin_path), "--json"],
            capture_output=True,
            text=True,
            timeout=25,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        fallback["summary"] = f"invocation failed: {e}"
        return {"id": "insights", "title": "Insights (R234 / Z-10)", "data": fallback}
    if r.returncode not in (0, 1):
        fallback["summary"] = f"synthesize rc={r.returncode}"
        return {"id": "insights", "title": "Insights (R234 / Z-10)", "data": fallback}
    try:
        report = json.loads(r.stdout)
    except json.JSONDecodeError:
        fallback["summary"] = "synthesize emitted non-JSON"
        return {"id": "insights", "title": "Insights (R234 / Z-10)", "data": fallback}
    top = report.get("insights") or []
    counts = report.get("counts") or {}
    data = {
        "round": "R235",
        "vector": "SDD-026 Z-10 dashboard",
        "needs_attention": report.get("needs_attention", False),
        "counts": counts,
        "top": [
            {
                "severity": i.get("severity"),
                "title": i.get("title"),
                "action": i.get("action"),
            }
            for i in top[:3]
        ],
        "summary": (
            f"{counts.get('critical', 0)} critical, "
            f"{counts.get('attention', 0)} attention, "
            f"{counts.get('informational', 0)} informational"
        ),
    }
    return {
        "id": "insights",
        "title": "Insights (R234 / Z-10)",
        "data": data,
    }


def card_dependency_state() -> dict[str, Any]:
    """R274 (E4.M6 closure) — Network-state-reactive grey-out card.

    Operator-named (verbatim, 2026-05-17 mandate): "greyout the option
    that require it and/or offer the alternative and warn of the
    potential risk or failure or such".

    Calls R220 network-status + builds a UI grey-out matrix:
      down_components            list of network components reporting
                                 status != ok (with their alternative
                                 from R220 when available)
      greyed_card_ids            dashboard card IDs whose data is
                                 unreliable given the down components
      greyed_features            per-feature grey-out reasons (for the
                                 install-paths + toolchains cards)

    Frontend renders greyed_card_ids with a 'requires X (down)' badge
    next to the card title; greyed_features dim the affected rows
    within those cards.
    """
    bin_path = REPO_ROOT / "scripts" / "hardware" / "network-status.py"
    fallback: dict[str, Any] = {
        "round": "R274",
        "vector": "E4.M6 (network-state grey-out)",
        "down_components": [],
        "greyed_card_ids": [],
        "greyed_features": [],
        "summary": "network-status.py unavailable",
    }
    if not bin_path.exists():
        return {"id": "dependency_state", "title": "Dependency state (R274 / Z-7)", "data": fallback}
    try:
        r = subprocess.run(
            [sys.executable, str(bin_path), "--json"],
            capture_output=True, text=True, timeout=15, check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        fallback["summary"] = f"invocation failed: {e}"
        return {"id": "dependency_state", "title": "Dependency state (R274 / Z-7)", "data": fallback}
    if r.returncode not in (0, 1):
        fallback["summary"] = f"network-status.py rc={r.returncode}"
        return {"id": "dependency_state", "title": "Dependency state (R274 / Z-7)", "data": fallback}
    try:
        report = json.loads(r.stdout)
    except json.JSONDecodeError:
        fallback["summary"] = "network-status.py emitted non-JSON"
        return {"id": "dependency_state", "title": "Dependency state (R274 / Z-7)", "data": fallback}

    components = report.get("components") or []
    down = [
        {
            "component": c.get("component"),
            "status": c.get("status"),
            "detail": c.get("detail"),
            "alternative": c.get("alternative"),
        }
        for c in components
        if c.get("status") not in {"ok", None}
    ]
    down_ids = {d["component"] for d in down}

    # Static dependency map: which dashboard card depends on which
    # network component. Update when new cards land that depend on
    # network state.
    card_dependencies = {
        "models":      ["internet"],            # HuggingFace pull
        "toolchains":  ["internet"],            # pip / git installs
        "fine_tune":   ["internet"],            # HF datasets
        "install_paths": ["docker", "internet"],
    }
    greyed_card_ids = sorted({
        card_id
        for card_id, deps in card_dependencies.items()
        if any(d in down_ids for d in deps)
    })

    # Per-feature grey-out matrix: install-paths + toolchains features
    # that require a down component get a grey-out reason string.
    greyed_features: list[dict[str, Any]] = []
    feature_dependencies = {
        # Toolchains that hit the network on install.
        "llama.cpp":       ["internet"],
        "vllm":            ["internet"],
        "ollama":          ["internet"],
        "transformers":    ["internet"],
        "trl":             ["internet"],
        "unsloth":         ["internet"],
        "lm-eval-harness": ["internet"],
        "mteb":            ["internet"],
        "dflash":          ["internet"],
        "huggingface-cli": ["internet"],
        "lm-link":         ["internet"],
        "lm-studio":       ["internet"],
        "bitnet.cpp":      ["internet"],
        # Install-paths features keyed on network components.
        "cloudflared":     ["internet", "cloudflared"],
        "tailscale":       ["internet", "tailscale"],
        "traefik":         ["docker"],
    }
    for feature, deps in feature_dependencies.items():
        blocking = [d for d in deps if d in down_ids]
        if blocking:
            greyed_features.append({
                "feature": feature,
                "blocking_components": blocking,
                "reason": f"requires {', '.join(blocking)} (currently down)",
                "alternative": next(
                    (d["alternative"] for d in down if d["component"] in blocking and d.get("alternative")),
                    None,
                ),
            })

    return {
        "id": "dependency_state",
        "title": "Dependency state (R274 / Z-7)",
        "data": {
            "round": "R274",
            "vector": "E4.M6 (network-state grey-out)",
            "down_components": down,
            "greyed_card_ids": greyed_card_ids,
            "greyed_features": greyed_features,
            "summary": (
                f"{len(down)} component(s) down; "
                f"{len(greyed_card_ids)} card(s) greyed; "
                f"{len(greyed_features)} feature(s) greyed"
            ),
            "needs_attention": bool(down),
        },
    }


def card_install_paths() -> dict[str, Any]:
    """R238 (SDD-026 Z-8 dashboard surface) — Install-paths card.

    Calls R237 `install-paths show --json` and renders a per-feature
    install-layer verdict (installable / alternative / blocked). Drives
    the dashboard's grey-out UX: blocked features render with a
    'requires X which is down' label + the alternative offer when one
    is available.
    """
    bin_path = REPO_ROOT / "scripts" / "install" / "paths.py"
    fallback: dict[str, Any] = {
        "round": "R238",
        "vector": "SDD-026 Z-8 dashboard",
        "summary": "paths.py unavailable",
        "features": [],
        "counts": {"installable": 0, "alternative": 0, "blocked": 0, "total": 0},
    }
    if not bin_path.exists():
        return {
            "id": "install-paths",
            "title": "Install paths (R237 / Z-8)",
            "data": fallback,
        }
    try:
        r = subprocess.run(
            [sys.executable, str(bin_path), "show", "--json"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        fallback["summary"] = f"invocation failed: {e}"
        return {
            "id": "install-paths",
            "title": "Install paths (R237 / Z-8)",
            "data": fallback,
        }
    if r.returncode not in (0, 1):
        fallback["summary"] = f"paths.py rc={r.returncode}"
        return {
            "id": "install-paths",
            "title": "Install paths (R237 / Z-8)",
            "data": fallback,
        }
    try:
        report = json.loads(r.stdout)
    except json.JSONDecodeError:
        fallback["summary"] = "paths.py emitted non-JSON"
        return {
            "id": "install-paths",
            "title": "Install paths (R237 / Z-8)",
            "data": fallback,
        }
    counts = report.get("counts", {})
    return {
        "id": "install_paths",
        "title": "Install paths (R237 / Z-8)",
        "data": {
            "round": "R238",
            "vector": "SDD-026 Z-8 dashboard",
            "counts": counts,
            "features": [
                {
                    "feature": f.get("feature"),
                    "summary": f.get("summary"),
                    "verdict": f.get("verdict"),
                    "default_layer": f.get("default_layer"),
                    "recommended_layer": f.get("recommended_layer"),
                    "reason": f.get("reason"),
                    # Grey-out signal: any layer with unmet deps.
                    "blocked_layers": [
                        layer["layer"]
                        for layer in (f.get("layers") or [])
                        if not layer.get("available")
                    ],
                }
                for f in (report.get("features") or [])
            ],
            "summary": (
                f"{counts.get('installable', 0)} installable, "
                f"{counts.get('alternative', 0)} alternative, "
                f"{counts.get('blocked', 0)} blocked"
            ),
            "needs_attention": counts.get("blocked", 0) > 0,
        },
    }


def card_services() -> dict[str, Any]:
    """R241 (SDD-026 Z-15 dashboard surface) — Services card.

    Calls R240 `services shipped --json` so the operator sees in the
    browser which sovereign-os-declared systemd units are loaded on
    this host. Top-5 not-loaded units surface in the card body as
    operator-enable hints.
    """
    bin_path = REPO_ROOT / "scripts" / "services" / "inventory.py"
    fallback: dict[str, Any] = {
        "round": "R241",
        "vector": "SDD-026 Z-15 dashboard",
        "counts": {"total": 0, "loaded": 0, "missing": 0},
        "missing_top": [],
        "summary": "inventory.py unavailable",
    }
    if not bin_path.exists():
        return {"id": "services", "title": "Services (R240 / Z-15)", "data": fallback}
    try:
        r = subprocess.run(
            [sys.executable, str(bin_path), "shipped", "--json"],
            capture_output=True, text=True, timeout=20, check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        fallback["summary"] = f"invocation failed: {e}"
        return {"id": "services", "title": "Services (R240 / Z-15)", "data": fallback}
    if r.returncode not in (0, 1):
        fallback["summary"] = f"inventory.py rc={r.returncode}"
        return {"id": "services", "title": "Services (R240 / Z-15)", "data": fallback}
    try:
        report = json.loads(r.stdout)
    except json.JSONDecodeError:
        fallback["summary"] = "inventory.py emitted non-JSON"
        return {"id": "services", "title": "Services (R240 / Z-15)", "data": fallback}
    total = report.get("count", 0)
    loaded = report.get("loaded_count", 0)
    missing = report.get("missing_count", 0)
    units = report.get("units") or []
    missing_top = [
        {"name": u.get("name"), "description": u.get("description")}
        for u in units
        if not u.get("loaded_on_this_host")
    ][:5]
    return {
        "id": "services",
        "title": "Services (R240 / Z-15)",
        "data": {
            "round": "R241",
            "vector": "SDD-026 Z-15 dashboard",
            "counts": {"total": total, "loaded": loaded, "missing": missing},
            "missing_top": missing_top,
            "summary": f"{loaded}/{total} loaded, {missing} not enabled",
            "needs_attention": missing > 0,
        },
    }


def card_kernel() -> dict[str, Any]:
    """R241 (SDD-026 Z-14 dashboard surface) — Kernel-tuning card.

    Calls R239 `kernel list --json` to surface available presets, then
    `kernel show --json` (no preset filter) to capture per-preset
    diverge counts. Operator sees in the browser which preset matches
    the live host best + how many keys diverge from each.
    """
    bin_path = REPO_ROOT / "scripts" / "kernel" / "tuning.py"
    fallback: dict[str, Any] = {
        "round": "R241",
        "vector": "SDD-026 Z-14 dashboard",
        "presets": [],
        "summary": "tuning.py unavailable",
    }
    if not bin_path.exists():
        return {"id": "kernel", "title": "Kernel tuning (R239 / Z-14)", "data": fallback}
    # Single call: `show` gives us per-preset diverge counts.
    try:
        r = subprocess.run(
            [sys.executable, str(bin_path), "show", "--json"],
            capture_output=True, text=True, timeout=20, check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        fallback["summary"] = f"invocation failed: {e}"
        return {"id": "kernel", "title": "Kernel tuning (R239 / Z-14)", "data": fallback}
    if r.returncode not in (0, 1):
        fallback["summary"] = f"tuning.py rc={r.returncode}"
        return {"id": "kernel", "title": "Kernel tuning (R239 / Z-14)", "data": fallback}
    try:
        report = json.loads(r.stdout)
    except json.JSONDecodeError:
        fallback["summary"] = "tuning.py emitted non-JSON"
        return {"id": "kernel", "title": "Kernel tuning (R239 / Z-14)", "data": fallback}
    presets = []
    for name, p in (report.get("presets") or {}).items():
        c = p.get("counts", {})
        presets.append(
            {
                "preset": name,
                "summary": p.get("summary", ""),
                "match": c.get("match", 0),
                "diverges": c.get("diverges", 0),
                "unreadable": c.get("unreadable", 0),
            }
        )
    # Best-matched preset = max(match) - prefer the one closest to live.
    if presets:
        best = max(presets, key=lambda p: p["match"])
        best_name = best["preset"]
        best_match = best["match"]
    else:
        best_name = None
        best_match = 0
    return {
        "id": "kernel",
        "title": "Kernel tuning (R239 / Z-14)",
        "data": {
            "round": "R241",
            "vector": "SDD-026 Z-14 dashboard",
            "presets": presets,
            "best_match_preset": best_name,
            "best_match_keys": best_match,
            "summary": (
                f"{len(presets)} preset(s); best match: "
                f"{best_name or '(none)'} ({best_match} key(s) align)"
            ),
            "needs_attention": any(p["diverges"] > 0 for p in presets),
        },
    }


def card_toolchains() -> dict[str, Any]:
    """R243 (SDD-026 Z-2 dashboard surface) — Toolchains card.

    Calls R242 `toolchains list --json` to surface inference + fine-
    tune + eval toolchain inventory. Drives the dashboard's "what
    LM-Studio-equivalents are installed?" answer.
    """
    bin_path = REPO_ROOT / "scripts" / "models" / "toolchains.py"
    fallback: dict[str, Any] = {
        "round": "R243",
        "vector": "SDD-026 Z-2 dashboard",
        "counts": {"total": 0, "installed": 0, "absent": 0, "by_kind": {}},
        "installed_names": [],
        "absent_names": [],
        "summary": "toolchains.py unavailable",
    }
    if not bin_path.exists():
        return {"id": "toolchains", "title": "Toolchains (R242 / Z-2)", "data": fallback}
    try:
        r = subprocess.run(
            [sys.executable, str(bin_path), "list", "--json"],
            capture_output=True, text=True, timeout=30, check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        fallback["summary"] = f"invocation failed: {e}"
        return {"id": "toolchains", "title": "Toolchains (R242 / Z-2)", "data": fallback}
    if r.returncode != 0:
        fallback["summary"] = f"toolchains.py rc={r.returncode}"
        return {"id": "toolchains", "title": "Toolchains (R242 / Z-2)", "data": fallback}
    try:
        report = json.loads(r.stdout)
    except json.JSONDecodeError:
        fallback["summary"] = "toolchains.py emitted non-JSON"
        return {"id": "toolchains", "title": "Toolchains (R242 / Z-2)", "data": fallback}
    rows = report.get("toolchains") or []
    installed_names = [t["name"] for t in rows if t.get("installed")]
    absent_names = [t["name"] for t in rows if not t.get("installed")]
    return {
        "id": "toolchains",
        "title": "Toolchains (R242 / Z-2)",
        "data": {
            "round": "R243",
            "vector": "SDD-026 Z-2 dashboard",
            "counts": report.get("counts", {}),
            "installed_names": installed_names,
            "absent_names": absent_names,
            "summary": (
                f"{len(installed_names)} installed, "
                f"{len(absent_names)} absent (operator can install via "
                "scripts/models/toolchains.py info <name>)"
            ),
            # Surface up to 5 not-yet-installed entries with their install hints
            # so operators see actionable next-steps right in the card.
            "install_hints_top": [
                {"name": t["name"], "install_hint": t["install_hint"]}
                for t in rows
                if not t.get("installed")
            ][:5],
        },
    }


def card_fine_tune() -> dict[str, Any]:
    """R247 (SDD-026 Z-2 fine-tune dashboard surface) — Fine-tune card.

    Calls R244 `fine-tune list-methods` + `fine-tune history` to surface
    available methods + recent runs. Drives the dashboard's "what
    LoRA/SFT/DPO runs have I done?" answer + an inline list of the
    4 methods with their vram floors.
    """
    bin_path = REPO_ROOT / "scripts" / "models" / "fine_tune.py"
    fallback: dict[str, Any] = {
        "round": "R247",
        "vector": "SDD-026 Z-2 fine-tune dashboard",
        "methods": [],
        "recent_runs": [],
        "summary": "fine_tune.py unavailable",
    }
    if not bin_path.exists():
        return {"id": "fine_tune", "title": "Fine-tune (R244 / Z-2)", "data": fallback}
    try:
        r_methods = subprocess.run(
            [sys.executable, str(bin_path), "list-methods", "--json"],
            capture_output=True, text=True, timeout=15, check=False,
        )
        r_history = subprocess.run(
            [sys.executable, str(bin_path), "history", "--limit", "5", "--json"],
            capture_output=True, text=True, timeout=15, check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        fallback["summary"] = f"invocation failed: {e}"
        return {"id": "fine_tune", "title": "Fine-tune (R244 / Z-2)", "data": fallback}
    methods: list[dict[str, Any]] = []
    recent: list[dict[str, Any]] = []
    try:
        m_doc = json.loads(r_methods.stdout) if r_methods.returncode == 0 else {}
        for key, m in (m_doc.get("methods") or {}).items():
            methods.append(
                {
                    "key": key,
                    "name": m.get("name"),
                    "harness": m.get("harness"),
                    "applicable_base_classes": m.get("applicable_base_classes"),
                    "vram_floor_gib": m.get("vram_gib_required_min"),
                    "cost_hours": m.get("cost_estimate_hours"),
                }
            )
    except json.JSONDecodeError:
        pass
    try:
        h_doc = json.loads(r_history.stdout) if r_history.returncode == 0 else {}
        recent = h_doc.get("rows") or []
    except json.JSONDecodeError:
        pass
    return {
        "id": "fine_tune",
        "title": "Fine-tune (R244 / Z-2)",
        "data": {
            "round": "R247",
            "vector": "SDD-026 Z-2 fine-tune dashboard",
            "methods": methods,
            "recent_runs": recent,
            "summary": f"{len(methods)} method(s); {len(recent)} recent run(s)",
            "needs_attention": False,  # informational only
        },
    }


def card_events() -> dict[str, Any]:
    """R247 (SDD-026 Z-16 dashboard surface) — Events timeline card.

    Calls R246 `events summary` for per-source counts + `events
    timeline --limit 5` for most-recent events. Operator's "what's
    been happening?" surface in the browser.
    """
    bin_path = REPO_ROOT / "scripts" / "history" / "aggregate.py"
    fallback: dict[str, Any] = {
        "round": "R247",
        "vector": "SDD-026 Z-16 dashboard",
        "total_events": 0,
        "sources": {},
        "recent": [],
        "summary": "aggregate.py unavailable",
    }
    if not bin_path.exists():
        return {"id": "events", "title": "Events (R246 / Z-16)", "data": fallback}
    try:
        r_sum = subprocess.run(
            [sys.executable, str(bin_path), "summary", "--json"],
            capture_output=True, text=True, timeout=15, check=False,
        )
        r_tl = subprocess.run(
            [sys.executable, str(bin_path), "timeline", "--limit", "5", "--json"],
            capture_output=True, text=True, timeout=15, check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        fallback["summary"] = f"invocation failed: {e}"
        return {"id": "events", "title": "Events (R246 / Z-16)", "data": fallback}
    sources: dict[str, Any] = {}
    total = 0
    recent: list[dict[str, Any]] = []
    try:
        s_doc = json.loads(r_sum.stdout) if r_sum.returncode == 0 else {}
        sources = s_doc.get("sources", {})
        total = s_doc.get("total_events", 0)
    except json.JSONDecodeError:
        pass
    try:
        tl_doc = json.loads(r_tl.stdout) if r_tl.returncode == 0 else {}
        recent = tl_doc.get("events") or []
    except json.JSONDecodeError:
        pass
    return {
        "id": "events",
        "title": "Events (R246 / Z-16)",
        "data": {
            "round": "R247",
            "vector": "SDD-026 Z-16 dashboard",
            "total_events": total,
            "sources": sources,
            "recent": recent,
            "summary": (
                f"{total} events across {len(sources)} source(s); "
                f"showing 5 most-recent"
            ),
            "needs_attention": False,  # informational
        },
    }


def card_power() -> dict[str, Any]:
    """R254 (SDD-026 Z-18 dashboard) — Power + PSU + UPS card.

    Calls R252 `power-status psu` + `budget` + `advisories` JSON to
    surface the operator-declared PSU, the live wattage budget vs
    estimated load, and the graceful-shutdown verdict (with rc=1
    when critical).
    """
    bin_path = REPO_ROOT / "scripts" / "hardware" / "power-status.py"
    fallback: dict[str, Any] = {
        "round": "R254",
        "vector": "SDD-026 Z-18 dashboard",
        "summary": "power-status.py unavailable",
    }
    if not bin_path.exists():
        return {"id": "power", "title": "Power (R252 / Z-18)", "data": fallback}

    def _call(verb: str) -> dict[str, Any]:
        try:
            r = subprocess.run(
                [sys.executable, str(bin_path), verb, "--json"],
                capture_output=True, text=True, timeout=15, check=False,
            )
        except (subprocess.TimeoutExpired, OSError):
            return {}
        if r.returncode not in (0, 1):
            return {}
        try:
            return json.loads(r.stdout) or {}
        except json.JSONDecodeError:
            return {}

    psu = _call("psu")
    budget = _call("budget")
    advisories = _call("advisories")
    util = budget.get("utilization_pct")
    needs_attention = bool(
        (util is not None and util >= 85)
        or advisories.get("verdict") in {"critical", "attention"}
    )
    data = {
        "round": "R254",
        "vector": "SDD-026 Z-18 dashboard",
        "psu": (psu or {}).get("psu") or {},
        "sustained_budget_watts": (psu or {}).get("sustained_budget_watts"),
        "budget": {
            "estimated_load_watts": (budget or {}).get("estimated_load_watts"),
            "utilization_pct": util,
            "headroom_watts": (budget or {}).get("headroom_watts"),
            "warnings": (budget or {}).get("warnings") or [],
        },
        "advisories": {
            "verdict": (advisories or {}).get("verdict"),
            "advisories": (advisories or {}).get("advisories") or [],
            "ups_present": (advisories or {}).get("ups_present"),
        },
        "needs_attention": needs_attention,
        "summary": (
            f"PSU {(psu or {}).get('psu', {}).get('rated_watts','?')} W; "
            f"load {((budget or {}).get('estimated_load_watts') or 0):.0f} W; "
            f"verdict {(advisories or {}).get('verdict') or '?'}"
        ),
    }
    return {"id": "power", "title": "Power (R252 / Z-18)", "data": data}


def card_bios() -> dict[str, Any]:
    """R254 (SDD-026 Z-17 dashboard) — BIOS + board + memory card.

    Calls R251 `bios-info show --json` to surface BIOS, baseboard,
    DIMM count + speed mix, and board-specific advisory count.
    """
    bin_path = REPO_ROOT / "scripts" / "hardware" / "bios-info.py"
    fallback: dict[str, Any] = {
        "round": "R254",
        "vector": "SDD-026 Z-17 dashboard",
        "summary": "bios-info.py unavailable",
    }
    if not bin_path.exists():
        return {"id": "bios", "title": "BIOS + memory (R251 / Z-17)", "data": fallback}
    try:
        r = subprocess.run(
            [sys.executable, str(bin_path), "show", "--json"],
            capture_output=True, text=True, timeout=15, check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        fallback["summary"] = f"invocation failed: {e}"
        return {"id": "bios", "title": "BIOS + memory (R251 / Z-17)", "data": fallback}
    if r.returncode != 0:
        fallback["summary"] = f"bios-info.py rc={r.returncode}"
        return {"id": "bios", "title": "BIOS + memory (R251 / Z-17)", "data": fallback}
    try:
        report = json.loads(r.stdout)
    except json.JSONDecodeError:
        fallback["summary"] = "bios-info.py emitted non-JSON"
        return {"id": "bios", "title": "BIOS + memory (R251 / Z-17)", "data": fallback}
    bios = report.get("bios", {})
    bb = report.get("baseboard", {})
    mem = report.get("memory", {})
    adv = report.get("advisories", {})
    return {
        "id": "bios",
        "title": "BIOS + memory (R251 / Z-17)",
        "data": {
            "round": "R254",
            "vector": "SDD-026 Z-17 dashboard",
            "bios_vendor": bios.get("vendor"),
            "bios_version": bios.get("version"),
            "baseboard_product": bb.get("product"),
            "baseboard_vendor": bb.get("vendor"),
            "dimm_count": mem.get("dimm_count", 0),
            "matched_board": adv.get("matched_board"),
            "advisory_count": len(adv.get("advisories") or []),
            "summary": (
                f"{bb.get('product') or '?'}; "
                f"{mem.get('dimm_count', 0)} DIMM(s); "
                f"{len(adv.get('advisories') or [])} advisory(ies)"
            ),
            "needs_attention": False,  # informational
        },
    }


def card_virt() -> dict[str, Any]:
    """R261 (SDD-026 Z-19 dashboard surface) — Virtualization card.

    Calls R255 `virt-info show --json` to surface CPU virt flags +
    KVM state + IOMMU posture + PCIe-interesting devices +
    container-runtime count. Drives the operator's "is this host
    ready for VFIO / nested-virt / VM-orchestration?" answer.
    """
    bin_path = REPO_ROOT / "scripts" / "hardware" / "virt-info.py"
    fallback: dict[str, Any] = {
        "round": "R261",
        "vector": "SDD-026 Z-19 dashboard",
        "summary": "virt-info.py unavailable",
    }
    if not bin_path.exists():
        return {"id": "virt", "title": "Virtualization (R255 / Z-19)", "data": fallback}
    try:
        r = subprocess.run(
            [sys.executable, str(bin_path), "show", "--json"],
            capture_output=True, text=True, timeout=20, check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        fallback["summary"] = f"invocation failed: {e}"
        return {"id": "virt", "title": "Virtualization (R255 / Z-19)", "data": fallback}
    if r.returncode != 0:
        fallback["summary"] = f"virt-info.py rc={r.returncode}"
        return {"id": "virt", "title": "Virtualization (R255 / Z-19)", "data": fallback}
    try:
        report = json.loads(r.stdout)
    except json.JSONDecodeError:
        fallback["summary"] = "virt-info.py emitted non-JSON"
        return {"id": "virt", "title": "Virtualization (R255 / Z-19)", "data": fallback}
    cpu = report.get("cpu") or {}
    kvm = report.get("kvm") or {}
    iommu = report.get("iommu") or {}
    pci = report.get("pci") or {}
    runtimes = report.get("runtimes") or {}
    # Needs-attention when virt would be useful but isn't enabled:
    # virt_supported=True but kvm_module_loaded=False OR IOMMU not on.
    needs_attention = bool(
        cpu.get("virt_supported")
        and (
            not kvm.get("dev_kvm_present")
            or (not iommu.get("iommu_enabled_sysfs")
                and not iommu.get("kernel_cmdline_intel_iommu_on")
                and not iommu.get("kernel_cmdline_amd_iommu_on"))
        )
    )
    return {
        "id": "virt",
        "title": "Virtualization (R255 / Z-19)",
        "data": {
            "round": "R261",
            "vector": "SDD-026 Z-19 dashboard",
            "cpu_vendor": cpu.get("vendor_flag"),
            "cpu_virt_supported": cpu.get("virt_supported"),
            "cpu_nested_paging": cpu.get("nested_paging_supported"),
            "kvm_module_loaded": kvm.get("kvm_module_loaded"),
            "kvm_dev_present": kvm.get("dev_kvm_present"),
            "nested_virt": kvm.get("nested_virt"),
            "iommu_enabled": iommu.get("iommu_enabled_sysfs"),
            "iommu_cmdline_intel": iommu.get("kernel_cmdline_intel_iommu_on"),
            "iommu_cmdline_amd": iommu.get("kernel_cmdline_amd_iommu_on"),
            "iommu_advisory": iommu.get("advisory"),
            "pcie_interesting_count": pci.get("interesting_count", 0),
            "runtimes_installed_count": runtimes.get("installed_count", 0),
            "runtimes_total_count": len(runtimes.get("runtimes") or []),
            "needs_attention": needs_attention,
            "summary": (
                f"{cpu.get('vendor_flag') or '(no vendor flag)'}; "
                f"KVM={kvm.get('dev_kvm_present')}; "
                f"IOMMU={iommu.get('iommu_enabled_sysfs')}; "
                f"{runtimes.get('installed_count', 0)}/{len(runtimes.get('runtimes') or [])} runtimes"
            ),
        },
    }


def card_operator_posture() -> dict[str, Any]:
    """R300 (E1.M25) — Holistic operator-posture rollup card.

    Surfaces the worst-axis verdict across R292 (oc-headroom) +
    R294 (psu-oc) + R296 (thermal-oc-budget) + R298 (storage-health)
    + R299 (bios-directives) into ONE dashboard card. Operator's
    "is my host in good shape?" answered at a glance.
    """
    bin_path = REPO_ROOT / "scripts" / "hardware" / "operator-posture.py"
    fallback: dict[str, Any] = {
        "round": "R300", "vector": "E1.M25",
        "summary": "operator-posture.py unavailable",
    }
    if not bin_path.exists():
        return {"id": "operator-posture",
                "title": "Operator posture rollup (R300 / E1.M25)",
                "data": fallback}
    try:
        r = subprocess.run(
            [sys.executable, str(bin_path), "status", "--json"],
            capture_output=True, text=True, timeout=30, check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        fallback["summary"] = f"invocation failed: {e}"
        return {"id": "operator-posture",
                "title": "Operator posture rollup (R300 / E1.M25)",
                "data": fallback}
    # operator-posture exits 0/1/2 reflecting severity; treat all
    # as data-emitted.
    if r.returncode not in (0, 1, 2):
        fallback["summary"] = f"operator-posture.py rc={r.returncode}"
        return {"id": "operator-posture",
                "title": "Operator posture rollup (R300 / E1.M25)",
                "data": fallback}
    try:
        report = json.loads(r.stdout)
    except json.JSONDecodeError:
        fallback["summary"] = "operator-posture.py emitted non-JSON"
        return {"id": "operator-posture",
                "title": "Operator posture rollup (R300 / E1.M25)",
                "data": fallback}
    return {
        "id": "operator-posture",
        "title": "Operator posture rollup (R300 / E1.M25)",
        "data": report,
    }


CARDS = [
    # R354 (E4.M10): intelligence-tier verbs (R349-R353) surface in UI.
    # morning_brief leads — operator's daily entry-point.
    card_morning_brief,
    card_operator_posture,
    card_blockset_queue,
    card_quarantine_queue,
    card_revocations_queue,
    card_token_revocations_queue,
    card_mfa_grant_revocations_queue,
    card_netns_isolations_queue,
    card_mount_bindings_queue,
    card_process_tree_freezes_queue,
    card_socket_fd_revocations_queue,
    card_env_scrubs_queue,
    card_capability_drops_queue,
    card_kernel_keyring_evictions_queue,
    card_apparmor_profile_pivots_queue,
    card_bpf_map_element_clears_queue,
    card_scheduler_status,
    card_gpu,
    card_network,
    card_cpu,
    card_fs,
    card_raid,
    card_flex,
    card_health,
    card_module_state,
    card_guide,
    card_models,
    card_model_adapt,
    card_model_build,
    card_insights,
    card_install_paths,
    card_services,
    card_kernel,
    card_toolchains,
    card_fine_tune,
    card_events,
    card_power,
    card_bios,
    card_virt,
    card_dependency_state,
]


# --------------------------------------------------------- rendering


def render_html(cards: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    parts.append("<!doctype html>")
    parts.append("<html lang=\"en\"><head><title>sovereign-os dashboard (R225)</title>")
    # R288 (E4.M8): mobile-friendly viewport + responsive card grid.
    # Operator-named (§1b): "Everything via dashboard/UInterface or
    # terminal tools OR AI" — the dashboard must work on the
    # operator's phone as well as a 4K monitor. CSS-only, no JS
    # framework dependency.
    parts.append("<meta charset=\"utf-8\">")
    parts.append("<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">")
    parts.append("<style>")
    parts.append("  :root{--bg:#0d1117;--fg:#c9d1d9;--card:#161b22;")
    parts.append("        --border:#30363d;--accent:#79c0ff;--mute:#8b949e;")
    parts.append("        --ok:#3fb950;--warn:#d29922;--down:#f85149;}")
    parts.append("  *{box-sizing:border-box;}")
    parts.append("  body{font:14px/1.4 monospace;background:var(--bg);color:var(--fg);")
    parts.append("       padding:1em;margin:0;-webkit-text-size-adjust:100%;}")
    parts.append("  h1{font-size:1.2em;border-bottom:1px solid var(--border);")
    parts.append("     padding-bottom:.3em;margin:0 0 1em 0;word-wrap:break-word;}")
    # Responsive grid — auto-fits cards into columns of ≥320px.
    # On phones (<=480px) collapses to a single column.
    parts.append("  .cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));")
    parts.append("         gap:1em;align-items:start;}")
    parts.append("  .card{background:var(--card);border:1px solid var(--border);")
    parts.append("        border-radius:6px;padding:1em;min-width:0;}")
    parts.append("  .card h2{font-size:1em;margin:0 0 .5em 0;color:var(--accent);")
    parts.append("           word-wrap:break-word;}")
    parts.append("  pre{background:var(--bg);border:1px solid var(--border);")
    parts.append("      border-radius:4px;padding:.5em;overflow-x:auto;")
    parts.append("      white-space:pre-wrap;word-wrap:break-word;font-size:.95em;}")
    parts.append("  footer{margin-top:2em;color:var(--mute);font-size:.9em;")
    parts.append("         word-wrap:break-word;}")
    parts.append("  code{background:var(--bg);padding:.1em .3em;border-radius:3px;")
    parts.append("       border:1px solid var(--border);word-break:break-all;}")
    parts.append("  .ok{color:var(--ok);} .warn{color:var(--warn);} .down{color:var(--down);}")
    # Touch-friendly tap targets on phones — bigger pre line-height,
    # 44px minimum link tap area per the WCAG 2.5.5 / Apple HIG
    # mobile baseline.
    parts.append("  @media (max-width:480px){")
    parts.append("    body{padding:.6em;font-size:14px;}")
    parts.append("    h1{font-size:1.05em;}")
    parts.append("    .cards{grid-template-columns:1fr;gap:.75em;}")
    parts.append("    .card{padding:.7em;}")
    parts.append("    pre{font-size:.85em;}")
    parts.append("    footer a, footer code{display:inline-block;min-height:32px;")
    parts.append("                          line-height:32px;padding:0 .4em;}")
    parts.append("  }")
    # Print-friendly: drop dark background so the operator can
    # print a snapshot.
    parts.append("  @media print{")
    parts.append("    body{background:#fff;color:#000;}")
    parts.append("    .card{background:#fff;border-color:#ccc;}")
    parts.append("    pre{background:#f6f6f6;border-color:#ccc;}")
    parts.append("    footer{color:#444;}")
    parts.append("  }")
    parts.append("</style></head><body>")
    parts.append("<h1>sovereign-os dashboard — R225 / SDD-026 Z-1 SEED</h1>")
    parts.append(
        "<p>Every card reads the same script the operator runs via "
        "<code>sovereign-osctl</code>. Read-only; no mutations.</p>"
    )
    # R288 (E4.M8): wrap cards in a grid container so the responsive
    # CSS in <head> can lay them out per viewport width.
    parts.append('<div class="cards">')
    for c in cards:
        parts.append(f'<section class="card" id="card-{html.escape(c["id"])}">')
        parts.append(f"<h2>{html.escape(c['title'])}</h2>")
        body = json.dumps(c["data"], indent=2)
        parts.append(f"<pre>{html.escape(body)}</pre>")
        parts.append("</section>")
    parts.append('</div>')
    parts.append('<footer>')
    parts.append('  Operator note: read-only mirror of the terminal cards.')
    parts.append('  Mutations stay on the CLI (or the future MCP server SD-R84+).')
    parts.append('  JSON endpoint: <code>/api/health</code> · per-card: ')
    for c in cards:
        parts.append(f'<code>/api/{html.escape(c["id"])}</code> · ')
    parts.append('</footer></body></html>')
    return "".join(parts)


def gather_all() -> list[dict[str, Any]]:
    # Isolate per-card failures. The dashboard is the operator's single-pane
    # cockpit and every card already degrades honestly when ITS subsystem is
    # down (scheduler → WEDGED, health → default fallback, …). But this
    # aggregator had no isolation: a card that *raises* (e.g. a subprocess
    # emitting an unexpected shape the card's post-processing doesn't fully
    # guard) would take down the WHOLE page and /api/health, not just itself.
    # Catch per card and substitute an explicit error card so one failing
    # subsystem can never blank the entire cockpit.
    out: list[dict[str, Any]] = []
    for c in CARDS:
        card_id = c.__name__.removeprefix("card_")
        try:
            out.append(c())
        except Exception as e:  # noqa: BLE001 — cockpit must survive any one card
            out.append({
                "id": card_id,
                "title": f"{card_id} (error)",
                "data": {
                    "error": f"{type(e).__name__}: {e}",
                    "card_failed": True,
                },
            })
    return out


# ── R289 (E4.M9): dashboard editable forms for module configuration ──
#
# Operator-named (§1b mandate row): "Dashboard editable forms for
# module configuration". The form composes with the SD-R99 (E2.M6) +
# SD-R100 (E2.M7) selfdef module-features lifecycle.
#
# Pure read-only HTTP semantics: the form submits via GET with field
# values in query params. The dashboard NEVER writes — it computes
# the diff between submitted values and the current effective
# features, then renders the equivalent
# `selfdefctl modules feature-set <slug> <key> <value>` commands for
# the operator to copy + run. This preserves the existing write-gate
# discipline (SD-R96 SELFDEF_MCP_ALLOW_WRITES=YES analog) — the
# operator stays in control of every mutation.
def _slug_safe(s: str) -> bool:
    # Reject the `..` path-traversal substring even though single
    # dots are otherwise allowed (matches the /api/models/<slug>
    # validator's existing pattern but tightens against a known
    # attacker shape).
    if not s or ".." in s:
        return False
    return all(c.isalnum() or c in "-_." for c in s)


def _key_safe(s: str) -> bool:
    if not s or ".." in s:
        return False
    return all(c.isalnum() or c in "-_." for c in s)


def _flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    """Walk a nested features dict into dotted-path → leaf-value pairs."""
    out: dict[str, Any] = {}
    if isinstance(value, dict):
        for k, v in value.items():
            dotted = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                out.update(_flatten(v, dotted))
            else:
                out[dotted] = v
    return out


def _parse_qs_pairs(query: str) -> list[tuple[str, str]]:
    """Tiny URL-decoded query parser — preserves order so command
    output is stable."""
    import urllib.parse as _u
    return _u.parse_qsl(query, keep_blank_values=True)


def _coerce_for_compare(submitted: str, current: Any) -> Any:
    """Best-effort coerce the form-submitted string to the type of
    the current value so the diff doesn't fire for cosmetic
    differences (`"true"` vs `True`, `"42"` vs `42`)."""
    if isinstance(current, bool):
        s = submitted.strip().lower()
        if s in ("true", "on", "1", "yes"):
            return True
        if s in ("false", "off", "0", "no", ""):
            return False
        return submitted
    if isinstance(current, int) and not isinstance(current, bool):
        try:
            return int(submitted)
        except ValueError:
            return submitted
    if isinstance(current, float):
        try:
            return float(submitted)
        except ValueError:
            return submitted
    return submitted


def _toml_scalar_for(value: Any) -> str:
    """Render a Python value as a TOML scalar literal so it round-trips
    through `selfdefctl modules feature-set <slug> <key> <toml-scalar>`."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return repr(value)
    s = str(value)
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def render_modules_index_html(modules: list[dict] | None,
                              error: str | None) -> str:
    """List page — every selfdef module + a link to its features form."""
    parts: list[str] = []
    parts.append("<!doctype html>")
    parts.append('<html lang="en"><head><title>sovereign-os · modules (R289)</title>')
    parts.append('<meta charset="utf-8">')
    parts.append('<meta name="viewport" content="width=device-width, initial-scale=1">')
    parts.append('<link rel="stylesheet" href="/dashboard.css">')
    parts.append("</head><body>")
    parts.append('<h1>selfdef modules — operator-pull features (R289 / E4.M9)</h1>')
    parts.append('<p><a href="/">← dashboard</a></p>')
    if error:
        parts.append('<section class="card">')
        parts.append('<h2>selfdefctl unavailable</h2>')
        parts.append(f'<pre>{html.escape(error)}</pre>')
        parts.append('<p>Install the selfdef-cli crate or set PATH; '
                     'the form route requires it for live feature reads.</p>')
        parts.append('</section>')
    elif modules is not None:
        parts.append('<div class="cards">')
        for m in modules:
            slug = m.get("slug") or m.get("name") or ""
            summary = m.get("summary") or ""
            if not _slug_safe(slug):
                continue
            parts.append(f'<section class="card" id="mod-{html.escape(slug)}">')
            parts.append(f'<h2>{html.escape(slug)}</h2>')
            parts.append(f'<p>{html.escape(summary)}</p>')
            parts.append(
                f'<p><a href="/modules/{html.escape(slug)}">edit features →</a></p>'
            )
            parts.append('</section>')
        parts.append('</div>')
    parts.append('<footer>R289 / E4.M9 — dashboard editable forms. '
                 'Writes stay on the CLI per SD-R96 gate doctrine.</footer>')
    parts.append('</body></html>')
    return "".join(parts)


def render_module_features_form_html(
    slug: str,
    features_doc: dict | None,
    error: str | None,
    diff_commands: list[str] | None,
) -> str:
    parts: list[str] = []
    parts.append("<!doctype html>")
    parts.append(f'<html lang="en"><head><title>sovereign-os · {html.escape(slug)} features (R289)</title>')
    parts.append('<meta charset="utf-8">')
    parts.append('<meta name="viewport" content="width=device-width, initial-scale=1">')
    parts.append('<link rel="stylesheet" href="/dashboard.css">')
    parts.append("</head><body>")
    parts.append(f'<h1>{html.escape(slug)} — features (R289 / E4.M9)</h1>')
    parts.append('<p><a href="/modules">← all modules</a> · '
                 '<a href="/">dashboard</a></p>')

    if error:
        parts.append('<section class="card">')
        parts.append('<h2>error</h2>')
        parts.append(f'<pre>{html.escape(error)}</pre>')
        parts.append('</section>')
    elif features_doc is not None:
        flat = _flatten(features_doc.get("features", {}))
        source = features_doc.get("source", "")

        if diff_commands is not None:
            parts.append('<section class="card">')
            parts.append('<h2>Commands to apply your changes</h2>')
            if diff_commands:
                parts.append('<p>Copy + run on the host (each command is '
                             'idempotent + audited via SELFDEF_REPL_HISTORY):</p>')
                parts.append('<pre>')
                parts.append(html.escape("\n".join(diff_commands)))
                parts.append('</pre>')
            else:
                parts.append('<p>No changes detected — submitted values '
                             'match the effective features.</p>')
            parts.append('</section>')

        parts.append('<section class="card">')
        parts.append(f'<h2>Effective features (source: '
                     f'<code>{html.escape(str(source))}</code>)</h2>')
        parts.append(f'<form method="GET" action="/modules/{html.escape(slug)}">')
        for dotted in sorted(flat.keys()):
            current = flat[dotted]
            field_id = "f-" + dotted.replace(".", "-")
            parts.append('<div class="field">')
            parts.append(f'<label for="{html.escape(field_id)}">'
                         f'<code>{html.escape(dotted)}</code></label>')
            if isinstance(current, bool):
                checked = ' checked' if current else ''
                # Hidden companion ensures unchecked checkboxes still
                # submit "false" rather than absence.
                parts.append(
                    f'<input type="hidden" name="{html.escape(dotted)}" value="false">'
                )
                parts.append(
                    f'<input type="checkbox" id="{html.escape(field_id)}" '
                    f'name="{html.escape(dotted)}" value="true"{checked}>'
                )
            elif isinstance(current, (int, float)) and not isinstance(current, bool):
                parts.append(
                    f'<input type="number" id="{html.escape(field_id)}" '
                    f'name="{html.escape(dotted)}" '
                    f'value="{html.escape(str(current))}" step="any">'
                )
            else:
                parts.append(
                    f'<input type="text" id="{html.escape(field_id)}" '
                    f'name="{html.escape(dotted)}" '
                    f'value="{html.escape(str(current))}">'
                )
            parts.append('</div>')
        parts.append('<button type="submit">Compute changes</button>')
        parts.append('</form>')
        parts.append('</section>')

    parts.append('<footer>R289 / E4.M9 — Submitting computes the diff '
                 'as <code>selfdefctl modules feature-set</code> commands. '
                 'The dashboard does NOT write — operator runs the commands '
                 'on the host (SD-R96 gate discipline).</footer>')
    parts.append('</body></html>')
    return "".join(parts)


def diff_commands_for(slug: str, current_features: dict,
                      submitted_pairs: list[tuple[str, str]]) -> list[str]:
    """Compute the `selfdefctl modules feature-set` commands that
    would land the operator's submitted values on the host. Booleans
    use the hidden+checkbox pair, so we last-write-wins per key."""
    flat = _flatten(current_features)
    # Collapse duplicate keys — last value wins (matches the hidden+
    # checkbox semantics).
    submitted: dict[str, str] = {}
    for k, v in submitted_pairs:
        submitted[k] = v
    out: list[str] = []
    for key in sorted(submitted.keys()):
        if key not in flat:
            # Operator added a key not in the current features — skip
            # (would need a manifest change, not a feature-set).
            continue
        new_val = _coerce_for_compare(submitted[key], flat[key])
        if new_val == flat[key]:
            continue
        out.append(
            f"selfdefctl modules feature-set {slug} {key} "
            f"{_toml_scalar_for(new_val)}"
        )
    return out


# Tiny static CSS — reuses the R288 mobile-friendly palette from
# render_html() but in a smaller standalone form so the modules
# pages stay mobile-friendly without re-emitting the entire <style>
# block.
DASHBOARD_CSS = """\
:root{--bg:#0d1117;--fg:#c9d1d9;--card:#161b22;--border:#30363d;
      --accent:#79c0ff;--mute:#8b949e;--ok:#3fb950;--warn:#d29922;
      --down:#f85149;}
*{box-sizing:border-box;}
body{font:14px/1.4 monospace;background:var(--bg);color:var(--fg);
     padding:1em;margin:0;-webkit-text-size-adjust:100%;}
h1{font-size:1.2em;border-bottom:1px solid var(--border);
   padding-bottom:.3em;margin:0 0 1em 0;word-wrap:break-word;}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));
       gap:1em;align-items:start;}
.card{background:var(--card);border:1px solid var(--border);
      border-radius:6px;padding:1em;margin:1em 0;min-width:0;}
.card h2{font-size:1em;margin:0 0 .5em 0;color:var(--accent);
         word-wrap:break-word;}
pre{background:var(--bg);border:1px solid var(--border);
    border-radius:4px;padding:.5em;overflow-x:auto;
    white-space:pre-wrap;word-wrap:break-word;font-size:.95em;}
footer{margin-top:2em;color:var(--mute);font-size:.9em;
       word-wrap:break-word;}
code{background:var(--bg);padding:.1em .3em;border-radius:3px;
     border:1px solid var(--border);word-break:break-all;}
.field{margin:.5em 0;display:flex;flex-wrap:wrap;align-items:center;
       gap:.5em;}
.field label{flex:0 0 220px;min-width:0;}
.field input[type=text], .field input[type=number]{
    flex:1 1 200px;min-width:120px;background:var(--bg);
    color:var(--fg);border:1px solid var(--border);
    border-radius:4px;padding:.3em .5em;font:inherit;}
.field input[type=checkbox]{width:1.2em;height:1.2em;}
button{background:var(--accent);color:#0d1117;border:none;
       border-radius:4px;padding:.5em 1em;font:inherit;
       cursor:pointer;min-height:36px;margin-top:.5em;}
button:hover{background:#a5d6ff;}
a{color:var(--accent);}
@media (max-width:480px){
  body{padding:.6em;}
  .cards{grid-template-columns:1fr;gap:.75em;}
  .field{flex-direction:column;align-items:flex-start;}
  .field label{flex:0 0 auto;}
  .field input{width:100%;}
  button{width:100%;min-height:44px;}
}
@media print{
  body{background:#fff;color:#000;}
  .card{background:#fff;border-color:#ccc;}
  pre{background:#f6f6f6;border-color:#ccc;}
}
"""


# --------------------------------------------------------- HTTP layer


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "sovereign-os-dashboard/R225"

    # Quiet stderr (the L3 test would otherwise see request log noise).
    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return

    def _send_json(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass  # client disconnected — not an error

    def _send_html(self, body_str: str, status: int = 200) -> None:
        body = body_str.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass  # client disconnected (e.g. a probe that gave up) — not an error

    def _check_auth(self) -> bool:
        """R250 (SDD-026 Z-1 auth): IP allowlist + Bearer-token check.

        Returns True when the request is authorized; False after
        sending a 401/403 response (do_GET caller short-circuits).
        Default (AUTH_CONFIG is None) = always-True (cycle-8 SEED
        behavior — safe on loopback / tailscale-private binds).
        """
        if AUTH_CONFIG is None:
            return True
        peer_ip = self.client_address[0] if self.client_address else ""
        # Loopback shortcut.
        if AUTH_CONFIG.get("allow_loopback") and _is_loopback(peer_ip):
            return True
        # IP allowlist gate first (don't even disclose token shape to
        # off-list clients).
        if peer_ip not in (AUTH_CONFIG.get("allow_ips") or []):
            self._send_json(
                {
                    "error": "forbidden",
                    "round": "R250",
                    "reason": "client IP not in dashboard-auth allowlist",
                    "peer": peer_ip,
                },
                status=403,
            )
            return False
        # Token gate.
        expected = AUTH_CONFIG.get("token")
        if not expected:
            self._send_json(
                {
                    "error": "server-misconfig",
                    "round": "R250",
                    "reason": "dashboard-auth.toml present but token_env "
                              "resolved to empty — operator must export the env var",
                },
                status=500,
            )
            return False
        auth = self.headers.get("Authorization", "")
        # Constant-time compare (hmac.compare_digest) so the Bearer-token
        # check can't be byte-by-byte timing-attacked — `!=` short-circuits
        # on the first differing byte and leaks the token over repeated
        # probes (the dashboard may be exposed via `--bind 0.0.0.0`).
        presented = auth[len("Bearer "):] if auth.startswith("Bearer ") else ""
        if not auth.startswith("Bearer ") or not hmac.compare_digest(
            presented, expected
        ):
            self._send_json(
                {
                    "error": "unauthorized",
                    "round": "R250",
                    "reason": "missing or invalid Bearer token",
                },
                status=401,
            )
            return False
        return True

    def do_GET(self) -> None:  # noqa: N802
        # Fast liveness probe — NO auth, NO gather_all(). gather_all() can take
        # >3s (40 hardware cards), which would time out panel.sh's
        # `curl --max-time 3` probe on the full page and make the dashboard look
        # "down" when it actually bound fine. Health checks hit this instead.
        if self.path.split("?", 1)[0] in ("/healthz", "/health"):
            self._send_json({"ok": True})
            return
        if not self._check_auth():
            return
        path = self.path
        if path == "/" or path == "/index.html":
            self._send_html(render_html(gather_all()))
            return
        if path == "/api/health":
            self._send_json({"cards": gather_all(), "round": "R225", "sdd_vector": "SDD-026 Z-1"})
            return
        # R289 (E4.M9): mobile-friendly shared CSS for the modules
        # form routes — pulled out of the inline <style> block so the
        # dashboard and the form pages stay visually consistent.
        if path == "/dashboard.css":
            self.send_response(200)
            self.send_header("Content-Type", "text/css; charset=utf-8")
            body = DASHBOARD_CSS.encode("utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        # R289 (E4.M9): modules index + per-module features form.
        if path == "/modules" or path == "/modules/":
            doc, err = _run_selfdefctl(["modules", "list"])
            modules = None
            if doc is not None:
                # selfdefctl modules list --json shape:
                #   {"modules": [{"slug":..., "name":..., "summary":...}, ...]}
                modules = doc.get("modules") if isinstance(doc, dict) else None
            self._send_html(render_modules_index_html(modules, err))
            return
        if path.startswith("/modules/"):
            rest = path[len("/modules/"):]
            slug, _, query = rest.partition("?")
            if not _slug_safe(slug):
                self._send_html(
                    render_module_features_form_html(
                        slug, None, "invalid module slug", None
                    ),
                    status=400,
                )
                return
            features, err = _run_selfdefctl(["modules", "features", slug])
            if features is None:
                self._send_html(
                    render_module_features_form_html(slug, None, err, None),
                    status=502 if err and "selfdefctl exited" in err else 503,
                )
                return
            pairs = _parse_qs_pairs(query) if query else []
            # Defensive: drop any submitted key that isn't safe.
            pairs = [(k, v) for k, v in pairs if _key_safe(k)]
            commands: list[str] | None = None
            if pairs:
                commands = diff_commands_for(slug, features.get("features", {}), pairs)
            self._send_html(
                render_module_features_form_html(slug, features, None, commands)
            )
            return
        # R233 (SDD-026 Z-2): per-model detail endpoint. Drives the
        # dashboard's "click on a model card → see full detail" UX
        # by proxying the R231 `models info <slug>` JSON. The slug
        # follows after /api/models/ so URL-safe slugs work directly.
        models_prefix = "/api/models/"
        if path.startswith(models_prefix):
            slug = path[len(models_prefix):]
            # Defensive: reject path separators / control chars even
            # though subprocess argv is shell-safe; keep slug semantics
            # tight (model ids in the catalog are alnum + - + .).
            if slug and all(c.isalnum() or c in "-_." for c in slug):
                detail = _run_models_script("info.py", [slug])
                if detail is not None:
                    self._send_json(detail)
                    return
                self._send_json(
                    {
                        "error": "unknown model slug",
                        "slug": slug,
                        "round": "R233",
                        "hint": "list available ids via /api/models or "
                                "`sovereign-osctl models query --json`",
                    },
                    status=404,
                )
                return
            self._send_json(
                {
                    "error": "invalid model slug",
                    "slug": slug,
                    "round": "R233",
                },
                status=400,
            )
            return
        for c in CARDS:
            card_id = c.__name__.removeprefix("card_")
            if path == f"/api/{card_id}":
                try:
                    self._send_json(c())
                except Exception as e:  # noqa: BLE001 — return a clean error, not a broken socket
                    self._send_json(
                        {
                            "id": card_id,
                            "error": f"{type(e).__name__}: {e}",
                            "card_failed": True,
                            "round": "R225",
                        },
                        status=500,
                    )
                return
        self._send_json(
            {"error": "not found", "path": path, "round": "R225"},
            status=404,
        )


def parse_bind(s: str) -> tuple[str, int]:
    if ":" not in s:
        raise ValueError(f"--bind must be HOST:PORT (got {s!r})")
    host, port_str = s.rsplit(":", 1)
    try:
        port = int(port_str)
    except ValueError as e:
        raise ValueError(f"--bind port not an int: {port_str!r}") from e
    return host or "127.0.0.1", port


def main() -> int:
    p = argparse.ArgumentParser(description="R225 (SDD-026 Z-1) dashboard SEED.")
    p.add_argument(
        "--bind",
        default="127.0.0.1:8443",
        help="bind address HOST:PORT (default %(default)s)",
    )
    p.add_argument(
        "--once",
        action="store_true",
        help="handle exactly one request and exit (used by L3 tests)",
    )
    p.add_argument(
        "--render-only",
        action="store_true",
        help=(
            "DO NOT bind a socket; render the dashboard HTML to stdout "
            "and exit. Used for offline-rendering tests + a future static "
            "snapshot path."
        ),
    )
    args = p.parse_args()

    if args.render_only:
        sys.stdout.write(render_html(gather_all()))
        return 0

    try:
        host, port = parse_bind(args.bind)
    except ValueError as e:
        print(f"ERROR {e}", file=sys.stderr)
        return 2
    # R250: load auth config BEFORE binding so the operator sees the
    # "auth enabled" banner alongside the bind announcement.
    global AUTH_CONFIG
    AUTH_CONFIG = load_auth_config()
    try:
        # Threaded so a slow full-page render (gather_all ~3-4s) never blocks a
        # concurrent health probe or a second client.
        srv = ThreadingHTTPServer((host, port), DashboardHandler)
    except OSError as e:
        print(f"ERROR bind {host}:{port}: {e}", file=sys.stderr)
        return 2
    auth_banner = "no-auth (cycle-8 SEED)"
    if AUTH_CONFIG is not None:
        token_state = "token-present" if AUTH_CONFIG.get("token") else "token-MISSING-from-env"
        auth_banner = (
            f"auth-enabled via {AUTH_CONFIG['config_source']} "
            f"({token_state}, allow_loopback={AUTH_CONFIG['allow_loopback']}, "
            f"allow_ips={len(AUTH_CONFIG['allow_ips'])})"
        )
    print(f"# R225 sovereign-os dashboard serving http://{host}:{port}/")
    print(f"# R250 auth: {auth_banner}")
    # R250 foot-gun guard: no-auth is safe on loopback (the SEED default
    # bind) but OPEN to the network on an exposed bind. Warn loudly so an
    # operator who `--bind 0.0.0.0` without dashboard-auth.toml sees that the
    # dashboard is reachable + unauthenticated (reverse-proxy auth IS a valid
    # pattern, so warn rather than refuse).
    if AUTH_CONFIG is None and host not in (
        "127.0.0.1", "::1", "localhost", "",
    ):
        print(
            f"# R250 WARNING: dashboard bound to {host} (non-loopback) with "
            f"NO authentication — it is reachable + UNAUTHENTICATED on the "
            f"network. Configure /etc/sovereign-os/dashboard-auth.toml "
            f"(allow_ips + token) or put it behind an authenticating reverse "
            f"proxy before exposing it.",
            file=sys.stderr,
        )
    try:
        if args.once:
            srv.handle_request()
        else:
            srv.serve_forever()
    except KeyboardInterrupt:
        print()
        print("# R225 shutdown via SIGINT")
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
