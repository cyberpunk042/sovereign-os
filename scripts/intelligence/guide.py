#!/usr/bin/env python3
"""scripts/intelligence/guide.py — R349 (E10.M1).

Operator-named (§1b verbatim hook drop):
  "[it's] only a guide into the experience, into the field, into the
   kernel, into the hardware, into the OS, into the modules, into the
   features, the services, the configurations, the personalisations,
   the customizations"

The "AI as guide" axis. R329 next-action-advisor answers "what should
I do NOW?". R309 cot-registry answers "what's the decision flow for
<routine>?". R349 guide answers "what IS this system + how do I look
INTO it?". Topic-keyed operator-pull entry-point.

Each topic in the registry binds:
  - mission           plain-language description of what this axis IS
  - layers            ordered list of sub-aspects to "look into"
  - operator_verbs    sovereign-osctl verbs that surface this axis
  - thresholds        operator-meaningful numbers + their meaning
  - cross_refs        related guides / SDDs / advisors
  - bios_or_hw_caveats per-board / per-component gotchas

The `walkthrough` verb concatenates layer descriptions + verb suggestions
in narrative order — operator-readable as a single block of guidance.

CLI:
  guide.py list       [--axis X] [--config P] [--json|--human]
  guide.py topics                  [--json|--human]
  guide.py show <topic>            [--config P] [--json|--human]
  guide.py walkthrough <topic>     [--config P] [--json|--human]

Operator-overlay (R283/SDD-030): /etc/sovereign-os/guide.toml — operator
can add custom topics or extend an existing topic's layers via deep-merge.

Exit codes:
  0  rendered
  1  unknown topic
  2  usage
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))
try:
    from operator_overlay import load_with_overlay  # type: ignore
except Exception:  # pragma: no cover
    load_with_overlay = None


SCHEMA_VERSION = "1.0.0"
ROUND = "R349"
SDD_VECTOR = "E10.M1"


# ── Topic registry ─────────────────────────────────────────────────
#
# Each topic is operator-readable: a guided narrative into one axis of
# the workstation. Layer-by-layer "look INTO" — what's there, what
# verbs surface it, what thresholds matter, what the per-board caveats
# are.
DEFAULT_TOPICS: list[dict[str, Any]] = [
    {
        "topic": "kernel",
        "axis": "system",
        "mission": (
            "The Linux kernel running on SAIN-01 — its boot params, "
            "modules loaded, sysctl posture, security features (KASLR, "
            "SMEP/SMAP, IBRS), and the substrate-default vs custom-built "
            "decision. The operator's window INTO the kernel layer."
        ),
        "layers": [
            "1. Boot cmdline (R220 kernel-cmdline / /proc/cmdline)",
            "2. Loaded modules (R221 kernel-modules / lsmod)",
            "3. Sysctl posture (R225 sysctl-audit — net.* + kernel.* hardening)",
            "4. Tetragon perimeter (R254 tetragon-status — eBPF policies)",
            "5. Build provenance (R331 build-state — custom kernel? Debian-sub?)",
        ],
        "operator_verbs": [
            "sovereign-osctl kernel-cmdline --json",
            "sovereign-osctl kernel-modules --json",
            "sovereign-osctl sysctl-audit --json",
            "sovereign-osctl tetragon-status --json",
            "sovereign-osctl build-state --json",
        ],
        "thresholds": {
            "sysctl-fail-count":
                "ANY fail in sysctl-audit → review immediately",
            "tetragon-must-be":
                "active + policies≥1 loaded for inference-services-ready",
        },
        "cross_refs": ["SDD-019 reproducibility", "SDD-036 inference hardening"],
        "bios_or_hw_caveats": [
            "ASUS X870E-CREATOR WiFi: AGESA microcode is loaded via "
            "kernel `amd_ucode` blob — check `dmesg | grep microcode` for "
            "load-status; mismatch can disable AVX-512 path on Zen 5."
        ],
    },
    {
        "topic": "hardware",
        "axis": "hardware",
        "mission": (
            "The physical SAIN-01 reference rig — Ryzen 9 9900X + dual-GPU "
            "(RTX 3090 + RTX PRO 6000) + 4-DIMM CMK128GX5M2B6400C42 "
            "(256GB) + dual Samsung 990 EVO Plus + APC SMT2200C UPS. "
            "Inventory-catalog (R317) is the single source of truth; every "
            "hardware advisor cross-refs from it."
        ),
        "layers": [
            "1. Full inventory (R317 inventory-catalog list / audit)",
            "2. Per-component caveats (R348 inventory_consult helper)",
            "3. CPU specifics (R272 avx512-advisor; R307 cpu-hotswap)",
            "4. GPU specifics (R271 gpu-card-advisor; R303 gpu-wattage)",
            "5. PCIe topology (R260 pcie-lanes; bifurcation per ASUS BIOS)",
            "6. Memory specifics (R257 memory-profile; R304 memory-pressure)",
            "7. PSU + UPS state (R252 power-status; R313 psu-oc-mode)",
        ],
        "operator_verbs": [
            "sovereign-osctl inventory list --json",
            "sovereign-osctl inventory audit --json",
            "sovereign-osctl avx512 --json",
            "sovereign-osctl gpu-card-advisor --json",
            "sovereign-osctl pcie-lanes --json",
            "sovereign-osctl memory-profile --json",
            "sovereign-osctl power-status psu --json",
        ],
        "thresholds": {
            "4-dimm-xmp-stability":
                "256GB across 4 DIMMs may not train at 6400MHz — "
                "drop to 6000MHz if XMP fails (R317 operator_caveat on ram-dimm-2; "
                "surfaces in R315 xmp_stability_warnings)",
            "ups-vs-psu-rating":
                "UPS 1980W < PSU 1600W + headroom under sustained dual-GPU "
                "+ OC peak when on battery (R317 ups-0 caveat; R252 escalates)",
        },
        "cross_refs": ["SDD-035 workload-mode", "R317 inventory-catalog"],
        "bios_or_hw_caveats": [
            "ASUS ProArt X870E-CREATOR WiFi: PCIE_1 = primary Gen5 x16 "
            "(operator-pinned to RTX 3090 per R311); enabling dual-GPU may "
            "require BIOS 'PCIe Bifurcation = x8/x8' on PCIE_1+PCIE_2; "
            "fan headers gated by Q-Fan Tuning + Allow Software Override.",
            "be Quiet! Dark Power Pro 13 1600W: physical OC switch on rear "
            "face MUST be declared via R313 overlay — not detectable from OS.",
        ],
    },
    {
        "topic": "gpu",
        "axis": "hardware",
        "mission": (
            "Dual-GPU configuration: RTX 3090 (24 GiB, host-facing, "
            "VFIO-eligible) + RTX PRO 6000 Blackwell (98 GiB, native). "
            "How the operator interacts with each card — established VRAM, "
            "non-established overclock headroom, wattage budget, mode-pinning."
        ),
        "layers": [
            "1. Cards detected + driver state (R269 nvidia-smi rollup)",
            "2. Per-card capabilities (R271 gpu-card-advisor — model/VRAM/PCIe)",
            "3. Sustained wattage budget (R303 gpu-wattage)",
            "4. OC headroom under PSU rating (R292 oc-headroom; R315 xmp-oc-room)",
            "5. Mode pinning (R338 workload-mode — dual_gpu_active per mode)",
            "6. VFIO bind for 3090 (R234 vfio-bind state)",
        ],
        "operator_verbs": [
            "sovereign-osctl gpu-status --json",
            "sovereign-osctl gpu-card-advisor --json",
            "sovereign-osctl gpu-wattage --json",
            "sovereign-osctl oc-headroom advisory --json",
            "sovereign-osctl workload-mode status --json",
            "sovereign-osctl vfio-bind --json",
        ],
        "thresholds": {
            "rtx-3090-sustained-w":
                "~420W under sustained load; +10% per OC notch (R315 default)",
            "rtx-pro-6000-sustained-w":
                "~600W TGP — operator's high-VRAM workhorse for training",
            "single-gpu-idle":
                "R338 'idle' mode = PRO 6000 only (3090 in VFIO standby); "
                "drops estimated_total_w by ≥400W vs 'training'",
        },
        "cross_refs": ["SDD-035 workload-mode", "R315 xmp-oc-room",
                       "R234 vfio-bind"],
        "bios_or_hw_caveats": [
            "RTX 3090: established sustained 420W under PSU OC mode; "
            "non-established: shunt-mod could lift to 480W but voids warranty.",
            "RTX PRO 6000 Blackwell: 600W TGP confirmed; PCIe Gen5 x16 on "
            "PCIE_1 OR x8 if dual-GPU sharing — check ASUS BIOS lane split.",
        ],
    },
    {
        "topic": "psu",
        "axis": "hardware",
        "mission": (
            "be Quiet! Dark Power Pro 13 1600W ATX 3.1 Titanium with "
            "physical OC switch. The operator's understanding of when "
            "they have wattage headroom vs when they're approaching the "
            "rated W under sustained dual-GPU+OC load."
        ),
        "layers": [
            "1. PSU declared state (R252 power-status psu)",
            "2. OC switch + multiplier (R313 psu-oc-mode)",
            "3. Real-time wattage estimate at 100% (R315 xmp-oc-room status)",
            "4. Budget verdict (R292 oc-headroom advisory)",
            "5. UPS-side ceiling cross-check (R252 power-status ups)",
        ],
        "operator_verbs": [
            "sovereign-osctl power-status psu --json",
            "sovereign-osctl psu-oc-mode --json",
            "sovereign-osctl xmp-oc-room budget --json",
            "sovereign-osctl oc-headroom advisory --json",
            "sovereign-osctl power-status ups --json",
        ],
        "thresholds": {
            "psu-rated-w": "1600W rated; R315 derates to 1360W safety ceiling (-15%)",
            "psu-oc-multiplier-off": "1.10x rated bonus when OC switch on",
            "psu-oc-multiplier-on":  "1.25x rated bonus when OC switch on + declared",
            "verdict-tight":         "estimated_total_w > 1360W → 'tight'",
            "verdict-over-budget":   "estimated_total_w > 1600W → 'over-budget' (rc=2)",
        },
        "cross_refs": ["SDD-026 power-status", "R313 psu-oc-mode",
                       "R315 xmp-oc-room"],
        "bios_or_hw_caveats": [
            "Dark Power Pro 13 OC switch is PHYSICAL — set on rear face; "
            "OS cannot detect it. Operator declares state via R313 overlay "
            "/etc/sovereign-os/psu-oc-mode.toml.",
        ],
    },
    {
        "topic": "ups",
        "axis": "hardware",
        "mission": (
            "APC Smart-UPS SMT2200C (2200VA / 1980W) — the operator's "
            "shield against AC loss. Battery time-left + graceful-shutdown "
            "ladder + the 1980W < 1600W+headroom caveat under dual-GPU peak."
        ),
        "layers": [
            "1. UPS live state (R252 power-status ups; apcupsd / nut)",
            "2. Battery thresholds (R302 battery-ladder)",
            "3. APC profile + scheduled shutdown (R314 apc-profile)",
            "4. Default power-profiles (R293 power-profiles — "
            "battery-threshold-graceful-shutdown is default)",
            "5. On-battery caveat surfacing (R252 inventory_caveats since R348)",
        ],
        "operator_verbs": [
            "sovereign-osctl power-status ups --json",
            "sovereign-osctl power-status advisories --json",
            "sovereign-osctl battery-ladder --json",
            "sovereign-osctl apc-profile --json",
            "sovereign-osctl power-profiles list --json",
        ],
        "thresholds": {
            "battery-critical-pct":
                "default 15% → R252 advisories verdict=critical, rc=1",
            "shutdown-minutes":
                "default 2 min time-left → triggers shutdown ladder",
            "warn-minutes":
                "default 5 min time-left → operator-attention verdict",
        },
        "cross_refs": ["SDD-026 power-status", "R293 power-profiles",
                       "R302 battery-ladder", "R317 ups-0 catalog entry"],
        "bios_or_hw_caveats": [
            "SMT2200C is refurbished (1YR warranty); 1980W < 1600W PSU "
            "+ headroom — sustained dual-GPU peak on battery may exceed "
            "UPS budget. R252 escalates to 'attention' since R348.",
            "Default profile (battery-threshold-graceful-shutdown) chains "
            "R262 drain → R260 plan → confirm-required apply. Triple-gate.",
        ],
    },
    {
        "topic": "memory",
        "axis": "hardware",
        "mission": (
            "Operator's 4×64GB Corsair Vengeance DDR5 CMK128GX5M2B6400C42 "
            "kits (256GB total). XMP 3.0 6400MHz nominal — but two kits "
            "combined into 4-DIMM populated may fall back to 6000MHz."
        ),
        "layers": [
            "1. Detected DIMMs + capacity (R317 inventory ram-* entries)",
            "2. XMP/EXPO profile detection (R257 memory-profile)",
            "3. Live pressure (R304 memory-pressure-damper)",
            "4. XMP-stability caveat (R315 xmp_stability_warnings since R347)",
            "5. ZFS-ARC clamp posture (R268 zfs-arc-clamp)",
        ],
        "operator_verbs": [
            "sovereign-osctl inventory list --category ram --json",
            "sovereign-osctl memory-profile --json",
            "sovereign-osctl memory-pressure-damper status --json",
            "sovereign-osctl xmp-oc-room status --json  # inventory_caveats",
            "sovereign-osctl zfs-arc-clamp --json",
        ],
        "thresholds": {
            "xmp-rated-mhz":      "6400 MHz CL42-52-52-104 1.35V (per-DIMM)",
            "4-dimm-fallback":    "drop to 6000MHz if XMP fails to train",
            "memory-pressure-warn":
                "avg10 ≥ 30% (idle/inference-ready) OR 50% (training mode)",
        },
        "cross_refs": ["R257 memory-profile", "R304 memory-pressure-damper",
                       "R317 inventory-catalog"],
        "bios_or_hw_caveats": [
            "AMD AGESA on AM5 + Zen 5: 4-DIMM XMP training at 6400 is "
            "marginal — AMD's EXPO kit-compatibility lookup is the formal "
            "tool; expect 6000 fallback when 4-DIMM populated.",
            "ASUS X870E-CREATOR WiFi: enable 'Memory Context Restore' to "
            "speed POST after stable XMP train.",
        ],
    },
    {
        "topic": "workload-mode",
        "axis": "intelligence",
        "mission": (
            "R338 workload-mode coordinator — single source of truth for "
            "current operator-declared posture. 6 R338 adopters consume "
            "the canonical mode to modulate their per-mode action shape "
            "(fan curves, governor, margins, damper thresholds, runtime "
            "knobs, recommended power-profile)."
        ),
        "layers": [
            "1. Current canonical mode (R338 workload-mode status)",
            "2. Available modes (R338 workload-mode modes)",
            "3. Affected advisors registry (R338 affected-advisors)",
            "4. Per-adopter modulation (each adopter's status --json)",
            "5. Apply ceremony (R338 workload-mode set + triple-gate)",
        ],
        "operator_verbs": [
            "sovereign-osctl workload-mode status --json",
            "sovereign-osctl workload-mode modes --json",
            "sovereign-osctl workload-mode affected-advisors --json",
            "sovereign-osctl fan-advisor status --json  # any adopter for per-mode shape",
            "sovereign-osctl workload-mode set <mode> --apply --confirm-mode-set",
        ],
        "thresholds": {
            "modes":     "idle / inference-ready / training / oc-burst (4)",
            "adopters":  "6/6 known adopters complete (R337/R307/R296/R304/R315/R293)",
            "apply-gate": "triple-gate: --apply + --confirm-mode-set + "
                          "SOVEREIGN_OS_CONFIRM_DESTROY=YES",
        },
        "cross_refs": ["SDD-035 adoption doctrine", "R338 coordinator"],
        "bios_or_hw_caveats": [],
    },
    {
        "topic": "inference",
        "axis": "ai",
        "mission": (
            "The 4 inference daemons — pulse / logic-engine / oracle-core / "
            "router. How operator inspects which backend is on which GPU, "
            "current draw, hardening posture (SDD-036), startup sequence."
        ),
        "layers": [
            "1. Router state (R263 router-status)",
            "2. Backend processes (R230 inference-processes)",
            "3. Per-backend GPU pinning (R230 + nvidia-smi)",
            "4. systemd unit hardening posture (SDD-036 since R346)",
            "5. Backend start scripts (scripts/inference/start-*.sh)",
        ],
        "operator_verbs": [
            "sovereign-osctl router-status --json",
            "sovereign-osctl inference-processes --json",
            "nvidia-smi --query-gpu=index,name,memory.used --format=csv",
            "systemctl status sovereign-pulse sovereign-logic-engine sovereign-oracle-core sovereign-router",
            "cat /etc/systemd/system/sovereign-router.service  # hardening posture",
        ],
        "thresholds": {
            "pulse-on":         "bitnet.cpp on CPU (no GPU)",
            "logic-engine-on":  "vLLM on RTX 3090 (VFIO sandbox)",
            "oracle-core-on":   "vLLM + DFlash on RTX PRO 6000 (host)",
            "router-on":        "FastAPI proxy + admission control",
        },
        "cross_refs": ["SDD-011 inference backend stack",
                       "SDD-036 inference-service hardening"],
        "bios_or_hw_caveats": [
            "logic-engine on VFIO-bound RTX 3090: requires "
            "sovereign-vfio-bind.service ordering + tetragon perimeter; "
            "if VFIO bind fails, logic-engine won't start.",
        ],
    },
    {
        "topic": "autohealth",
        "axis": "intelligence",
        "mission": (
            "R308 autohealth / doctor — periodic synthesizer that "
            "composes 6 axes (health-scan + thermal-oc + storage-health "
            "+ operator-posture + memory-pressure + network) into ONE "
            "tick that persists state + emits notify-dispatch commands "
            "when severity crosses threshold. Operator-pull 'is anything "
            "asking for my attention right now?'."
        ),
        "layers": [
            "1. Latest doctor tick (R308 autohealth status)",
            "2. Doctor history (R308 autohealth recent)",
            "3. Quick one-shot probe (R226 doctor)",
            "4. Notification dispatch queue (R310 notify list)",
            "5. Operator-posture trend (R300 operator-posture)",
        ],
        "operator_verbs": [
            "sovereign-osctl autohealth status --json",
            "sovereign-osctl autohealth recent --json",
            "sovereign-osctl doctor --json",
            "sovereign-osctl notify list --json",
            "sovereign-osctl operator-posture --json",
        ],
        "thresholds": {
            "severity-attention":
                "any sub-axis verdict='attention' → doctor tick records",
            "severity-critical":
                "any sub-axis verdict='critical' → notify-dispatch fired",
            "tick-cadence":
                "default 5 min (systemd timer sovereign-autohealth-tick.timer)",
        },
        "cross_refs": ["SDD-022 doctor-axes", "R308 autohealth"],
        "bios_or_hw_caveats": [],
    },
    {
        "topic": "selfdef",
        "axis": "ai",
        "mission": (
            "Selfdef is the sister repo (cyberpunk042/selfdef) — the "
            "operator's REPL + module system + macro substrate. "
            "Sovereign-os surfaces selfdef cross-state via the "
            "mcp-aggregate manifest (R286): 31 read-only tools spanning "
            "hardware/gpu/cpu/psu/network/kernel/dashboard/health/etc., "
            "PLUS optional upstream selfdef MCP TCP descriptor (SD-R94)."
        ),
        "layers": [
            "1. Unified MCP manifest (R286 mcp-aggregate manifest)",
            "2. Probe upstream selfdef (R286 mcp-aggregate probe-upstream)",
            "3. Selfdef cycle-N module gate (cross-repo; see selfdef README)",
            "4. Selfdef macro / @selfdef_macro substrate (SD-R98; see selfdef)",
        ],
        "operator_verbs": [
            "sovereign-osctl mcp-aggregate manifest --json",
            "sovereign-osctl mcp-aggregate probe-upstream <host:port> --json",
            "# cross-repo: selfdefctl modules list",
            "# cross-repo: selfdef repl",
        ],
        "thresholds": {
            "manifest-tool-count":
                "31 sovereign-os tools (covers every §1b-named axis)",
            "upstream-required":
                "no — manifest stands alone; selfdef MCP is OPTIONAL upstream",
        },
        "cross_refs": ["SDD-031 mcp-aggregate", "SD-R98 selfdef_macro",
                       "SD-R94 selfdef MCP"],
        "bios_or_hw_caveats": [
            "Sovereign-os does NOT run its own MCP listener — manifest "
            "is the deliverable; clients wire both endpoints natively.",
            "Selfdef repo lives at cyberpunk042/selfdef — operations on "
            "it require a sovereign-osctl agent invocation with selfdef "
            "repo scope, not this scope.",
        ],
    },
    {
        "topic": "network",
        "axis": "network",
        "mission": (
            "DNS, VLANs, Tailscale, Cloudflared/Traefik posture — how "
            "operator reaches in and out of SAIN-01 + how external clients "
            "reach the inference router. Container-vs-system install "
            "decisions, dual-stack DNS, ingress hardening."
        ),
        "layers": [
            "1. Interface state (R226 net-state)",
            "2. Resolver chain (R227 dns-status)",
            "3. VLAN bindings (R235 network-vlan)",
            "4. Tailscale state (R244 tailscale-status — if installed)",
            "5. Ingress posture (R246 ingress-posture — Traefik / Cloudflared)",
        ],
        "operator_verbs": [
            "sovereign-osctl net-state --json",
            "sovereign-osctl dns-status --json",
            "sovereign-osctl network-vlan --json",
            "sovereign-osctl tailscale-status --json",
            "sovereign-osctl ingress-posture --json",
        ],
        "thresholds": {
            "dns-must-be":     "resolv.conf delegated to systemd-resolved OR "
                               "operator-pinned upstream — no stub fallback",
            "tailscale-must-be": "if installed: logged-in + magic-dns on",
        },
        "cross_refs": ["SDD-022 ingress posture"],
        "bios_or_hw_caveats": [
            "ASUS X870E-CREATOR WiFi: 2.5GbE Intel + WiFi 7 BE200 (Intel) "
            "— BE200 needs `iwlwifi` ≥6.7; check `dmesg | grep iwlwifi` if "
            "WiFi misbehaves under heavy network load.",
        ],
    },
]


# ── Lookup + load ──────────────────────────────────────────────────
def resolve_topic(topics: list[dict], name: str) -> dict | None:
    for t in topics:
        if isinstance(t, dict) and t.get("topic") == name:
            return t
    return None


def filter_axis(topics: list[dict], axis: str | None) -> list[dict]:
    if not axis:
        return topics
    return [t for t in topics if isinstance(t, dict) and t.get("axis") == axis]


def load_topics(overlay_path: Path | None) -> tuple[list[dict], dict]:
    meta = {"_source": "(defaults)", "_overlay_keys": []}
    topics = list(DEFAULT_TOPICS)
    if load_with_overlay is not None:
        loaded = load_with_overlay(
            "guide", {"topics": []}, explicit_path=overlay_path,
        )
        meta["_source"] = loaded.get("_source", meta["_source"])
        meta["_overlay_keys"] = loaded.get("_overlay_keys", [])
        if loaded.get("_parse_error"):
            meta["_parse_error"] = loaded["_parse_error"]
        if loaded.get("topics"):
            topics = list(loaded["topics"])
    return topics, meta


# ── Renderers ──────────────────────────────────────────────────────
def render_topics_human(topics: list[dict]) -> str:
    lines = ["── R349 sovereign-os guide topics (E10.M1) ──"]
    by_axis: dict[str, list[str]] = {}
    for t in topics:
        if not isinstance(t, dict):
            continue
        by_axis.setdefault(t.get("axis", "?"), []).append(t.get("topic", "?"))
    for axis in sorted(by_axis):
        lines.append(f"  {axis}:")
        for name in by_axis[axis]:
            lines.append(f"    - {name}")
    lines.append("")
    lines.append("  Run `sovereign-osctl guide show <topic>` for details.")
    return "\n".join(lines) + "\n"


def render_show_human(t: dict) -> str:
    lines = [f"── R349 guide: {t.get('topic')} ({t.get('axis')}) ──"]
    lines.append("")
    lines.append("  mission:")
    for line in (t.get("mission") or "").splitlines():
        lines.append(f"    {line}")
    lines.append("")
    lines.append("  layers:")
    for layer in t.get("layers") or []:
        lines.append(f"    {layer}")
    lines.append("")
    lines.append("  operator verbs:")
    for v in t.get("operator_verbs") or []:
        lines.append(f"    $ {v}")
    if t.get("thresholds"):
        lines.append("")
        lines.append("  thresholds:")
        for k, v in t["thresholds"].items():
            lines.append(f"    {k}:")
            for line in str(v).splitlines():
                lines.append(f"      {line}")
    if t.get("bios_or_hw_caveats"):
        lines.append("")
        lines.append("  BIOS/HW caveats:")
        for c in t["bios_or_hw_caveats"]:
            lines.append(f"    ⚠ {c}")
    if t.get("cross_refs"):
        lines.append("")
        lines.append(f"  cross-refs: {', '.join(t['cross_refs'])}")
    return "\n".join(lines) + "\n"


def render_walkthrough_human(t: dict) -> str:
    """Narrative walkthrough — concatenates layers + verbs + caveats
    into a single operator-readable block."""
    lines = [f"── R349 walkthrough: {t.get('topic')} ──"]
    lines.append("")
    lines.append((t.get("mission") or "").rstrip())
    lines.append("")
    lines.append(f"WALKTHROUGH — {len(t.get('layers') or [])} layers:")
    for layer, verb in zip(t.get("layers") or [],
                            t.get("operator_verbs") or []):
        lines.append("")
        lines.append(f"  {layer}")
        lines.append(f"    $ {verb}")
    if t.get("bios_or_hw_caveats"):
        lines.append("")
        lines.append("PER-BOARD / PER-COMPONENT CAVEATS:")
        for c in t["bios_or_hw_caveats"]:
            lines.append(f"  ⚠ {c}")
    if t.get("thresholds"):
        lines.append("")
        lines.append("OPERATOR-MEANINGFUL THRESHOLDS:")
        for k, v in t["thresholds"].items():
            lines.append(f"  {k} — {v}")
    return "\n".join(lines) + "\n"


# ── Main ───────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="guide.py")
    sub = p.add_subparsers(dest="cmd", required=True)

    pl = sub.add_parser("list")
    pl.add_argument("--axis")
    pl.add_argument("--config", type=Path)
    plg = pl.add_mutually_exclusive_group()
    plg.add_argument("--json", dest="fmt", action="store_const", const="json")
    plg.add_argument("--human", dest="fmt", action="store_const", const="human")
    pl.set_defaults(fmt="json")

    pt = sub.add_parser("topics")
    ptg = pt.add_mutually_exclusive_group()
    ptg.add_argument("--json", dest="fmt", action="store_const", const="json")
    ptg.add_argument("--human", dest="fmt", action="store_const", const="human")
    pt.set_defaults(fmt="json")

    for verb in ("show", "walkthrough"):
        sp = sub.add_parser(verb)
        sp.add_argument("topic")
        sp.add_argument("--config", type=Path)
        sfg = sp.add_mutually_exclusive_group()
        sfg.add_argument("--json", dest="fmt", action="store_const", const="json")
        sfg.add_argument("--human", dest="fmt", action="store_const", const="human")
        sp.set_defaults(fmt="json")

    args = p.parse_args(argv)
    topics, meta = load_topics(getattr(args, "config", None))

    if args.cmd == "list":
        filtered = filter_axis(topics, getattr(args, "axis", None))
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "axis_filter": getattr(args, "axis", None),
                "topic_count": len(filtered),
                "topics": filtered,
                "overlay": meta,
            }, indent=2))
        else:
            print(render_topics_human(filtered), end="")
        return 0

    if args.cmd == "topics":
        names = sorted({t.get("topic") for t in topics
                        if isinstance(t, dict) and t.get("topic")})
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "topic_names": names,
                "axes": sorted({t.get("axis") for t in topics
                                 if isinstance(t, dict) and t.get("axis")}),
                "overlay": meta,
            }, indent=2))
        else:
            print("── R349 guide topics (E10.M1) ──")
            for n in names:
                print(f"  - {n}")
        return 0

    t = resolve_topic(topics, args.topic)
    if t is None:
        print(json.dumps({
            "error": f"unknown topic: {args.topic}",
            "known": [x.get("topic") for x in topics if isinstance(x, dict)],
            "round": ROUND,
        }, indent=2), file=sys.stderr)
        return 1

    if args.cmd == "show":
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "topic": t,
                "overlay": meta,
            }, indent=2))
        else:
            print(render_show_human(t), end="")
        return 0

    if args.cmd == "walkthrough":
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "topic_name": t.get("topic"),
                "mission": t.get("mission"),
                "layer_count": len(t.get("layers") or []),
                "verb_count": len(t.get("operator_verbs") or []),
                "layers": t.get("layers") or [],
                "operator_verbs": t.get("operator_verbs") or [],
                "thresholds": t.get("thresholds") or {},
                "bios_or_hw_caveats": t.get("bios_or_hw_caveats") or [],
                "cross_refs": t.get("cross_refs") or [],
                "walkthrough_mode": True,
            }, indent=2))
        else:
            print(render_walkthrough_human(t), end="")
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
