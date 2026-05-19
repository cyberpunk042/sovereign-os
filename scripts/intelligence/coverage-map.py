#!/usr/bin/env python3
"""scripts/intelligence/coverage-map.py — R365 (E10.M10).

Operator-pull "what coverage do I have for axis X?" map. Each axis
is operator-stated (verbatim from a hook drop / mandate row / raw
dump) and bound to ≥1 implementing verb + ≥1 SDD reference + ≥1
mandate row. The map provides operator-auditable coverage of every
explicitly-named axis without forcing operator to scan the entire
mandate file.

Each axis carries:
  - id                short slug (A-NN)
  - axis_verbatim     operator-stated text (NO PARAPHRASING)
  - source            where operator stated it (hook drop date /
                       mandate row / raw dump section)
  - implementing_verbs list of sovereign-osctl verbs that cover it
  - sdd_refs           list of SDD numbers
  - mandate_rows       list of E-X.M-Y rows
  - status             ✓ shipped / partial / TODO
  - notes              operator-readable depth notes

CLI:
  coverage-map.py axes              [--status S] [--config P] [--json|--human]
                                     list all axes with status
  coverage-map.py show <id>         [--config P] [--json|--human]
                                     drill into one axis
  coverage-map.py audit             [--config P] [--json|--human]
                                     report TODO / partial axes;
                                     rc=1 if any TODO; rc=0 if all
                                     ✓ shipped or partial
  coverage-map.py search <substring>[--config P] [--json|--human]

Operator-overlay (R283/SDD-030): /etc/sovereign-os/coverage-map.toml
adds operator-authored axis rows for hook drops between sessions.

Exit codes:
  0  rendered / audit clean
  1  unknown id / audit has TODO axes
  2  usage error
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
ROUND = "R365"
SDD_VECTOR = "E10.M10"


# ── Operator-axis catalog (verbatim from hook drops + mandate) ────
#
# This is the operator's NARRATIVE coverage map. Each row binds an
# operator-verbatim axis to the verbs/SDDs/mandate-rows that
# implement it. R365 ships the initial 30 rows from the 2026-05-17
# operator-mandate hook drop. Operator-overlay extends per session.
DEFAULT_AXES: list[dict[str, Any]] = [
    {"id": "A-01",
     "axis_verbatim": ("a guide into the experiece, into the field, "
                        "into the kernel, into the hardware, into the "
                        "OS, into the modules, into the features, the "
                        "services, the configurations, the "
                        "personalisations, the customizations"),
     "source": "hook drop 2026-05-17 (opening sentence)",
     "implementing_verbs": [
         "sovereign-osctl guide topics",
         "sovereign-osctl guide show",
         "sovereign-osctl architecture-qa",
     ],
     "sdd_refs": [],
     "mandate_rows": ["E2.M22"],
     "status": "✓ shipped",
     "notes": ("R349 guide.py ships the operator-named topic catalog. "
                "Architecture-qa (R355+) adds verbatim Q&A + gotchas "
                "+ concepts across 23 master spec blocks.")},
    {"id": "A-02",
     "axis_verbatim": ("AI and the tools but also download, fine-tune, "
                        "parameters, build, run, use and train and "
                        "adapt and use and eval and etc."),
     "source": "hook drop 2026-05-17",
     "implementing_verbs": [
         "sovereign-osctl models adapt",
         "sovereign-osctl models build",
         "sovereign-osctl models lifecycle",
         "sovereign-osctl models fine-tune",
         "sovereign-osctl models eval",
         "sovereign-osctl models verify",
     ],
     "sdd_refs": ["011"],
     "mandate_rows": ["E5.M1", "E5.M6"],
     "status": "✓ shipped",
     "notes": ("Operator's full model lifecycle mapped: R290 lifecycle "
                "+ R244 fine-tune + R232 eval + R350 adapt + R353 build "
                "+ R182 verify-checksum.")},
    {"id": "A-03",
     "axis_verbatim": ("selfdef modules, modules features and advanced "
                        "features and profiles. Hotswap, CPU mode and "
                        "option(s)"),
     "source": "hook drop 2026-05-17",
     "implementing_verbs": [
         "sovereign-osctl cpu-hotswap",
         "sovereign-osctl workload-mode",
     ],
     "sdd_refs": ["035"],
     "mandate_rows": ["E2.M2", "E2.M27", "E2.M29"],
     "status": "✓ shipped",
     "notes": ("R307 cpu-hotswap pinned mode + R338 workload-mode "
                "coordinator + R340 adoption.")},
    {"id": "A-04",
     "axis_verbatim": ("GPU too, watts, RTX 3090 details and "
                        "possibilities established and non-established, "
                        "same for the RTX Pro 6000 and the CPU and "
                        "AVX512"),
     "source": "hook drop 2026-05-17",
     "implementing_verbs": [
         "sovereign-osctl gpu-card-advisor",
         "sovereign-osctl gpu-wattage",
         "sovereign-osctl psu-oc-mode",
         "sovereign-osctl avx512-advisor",
     ],
     "sdd_refs": [],
     "mandate_rows": ["E1.M19", "E1.M25", "E1.M26"],
     "status": "✓ shipped",
     "notes": ("R271 gpu-card-advisor + R272 avx512 + R294 psu-oc-mode "
                "+ R303 gpu-wattage; inventory-catalog R317 surfaces "
                "RTX 3090 / RTX PRO 6000 / Ryzen 9 9900X specifics.")},
    {"id": "A-05",
     "axis_verbatim": "autohealth and doctor",
     "source": "hook drop 2026-05-17",
     "implementing_verbs": [
         "sovereign-osctl autohealth",
         "sovereign-osctl doctor",
     ],
     "sdd_refs": [],
     "mandate_rows": ["E1.M28", "E2.M14"],
     "status": "✓ shipped",
     "notes": "R308 autohealth + R266 doctor."},
    {"id": "A-06",
     "axis_verbatim": "notification and messaging",
     "source": "hook drop 2026-05-17",
     "implementing_verbs": ["sovereign-osctl autohealth",
                             "sovereign-osctl doctor"],
     "sdd_refs": [],
     "mandate_rows": ["E2.M14"],
     "status": "✓ shipped",
     "notes": ("R254 notify-dispatch + R308 autohealth integration "
                "(notify-dispatch surfaces under autohealth tick + "
                "doctor advisory verdicts).")},
    {"id": "A-07",
     "axis_verbatim": ("networks and in and out, the DNS, the "
                        "Cloudflared ? the tailscale, Traefik"),
     "source": "hook drop 2026-05-17",
     "implementing_verbs": [
         "sovereign-osctl network",
         "sovereign-osctl network-stack",
         "sovereign-osctl network-topology",
         "sovereign-osctl dns-advisor",
     ],
     "sdd_refs": [],
     "mandate_rows": ["E3.M5", "E3.M8"],
     "status": "✓ shipped",
     "notes": ("R241 network + R287 network-stack (Cloudflared / "
                "Tailscale / Traefik comparison) + R359 network-topology "
                "(§8 asymmetric NIC verbatim) + dns-advisor.")},
    {"id": "A-08",
     "axis_verbatim": ("non docker vs docker install ? when possible ? "
                        "container level vs system level"),
     "source": "hook drop 2026-05-17",
     "implementing_verbs": ["sovereign-osctl install-mode"],
     "sdd_refs": [],
     "mandate_rows": ["E2.M16"],
     "status": "✓ shipped",
     "notes": ("R310 install-mode-advisor per-component recommendation "
                "(container / system / either) with operator-verbatim "
                "axis as the title.")},
    {"id": "A-09",
     "axis_verbatim": ("dashboard, installs, non-configured, modules "
                        "or features and how configure them"),
     "source": "hook drop 2026-05-17",
     "implementing_verbs": [
         "sovereign-osctl dashboard",
         "sovereign-osctl module-state",
     ],
     "sdd_refs": [],
     "mandate_rows": ["E2.M19", "E2.M20"],
     "status": "✓ shipped",
     "notes": ("R225 dashboard + R351 module-state (in-flight / "
                "configured / unconfigured detection).")},
    {"id": "A-10",
     "axis_verbatim": ("management of the softwares, the 'raid's, "
                        "observations and operatations and "
                        "configurations"),
     "source": "hook drop 2026-05-17",
     "implementing_verbs": [
         "sovereign-osctl raid",
     ],
     "sdd_refs": [],
     "mandate_rows": ["E2.M4"],
     "status": "✓ shipped",
     "notes": "R223 raid-status / operate / config (prior round)."},
    {"id": "A-11",
     "axis_verbatim": ("logs, log rotate, system usage, partitions and "
                        "global and such. insights"),
     "source": "hook drop 2026-05-17",
     "implementing_verbs": [
         "sovereign-osctl insights",
         "sovereign-osctl fs",
     ],
     "sdd_refs": [],
     "mandate_rows": ["E2.M5"],
     "status": "✓ shipped",
     "notes": "R222 logs + R234 insights + R298 storage-health."},
    {"id": "A-12",
     "axis_verbatim": "Interoperability, MCP, tools, deps",
     "source": "hook drop 2026-05-17",
     "implementing_verbs": [
         "sovereign-osctl mcp-aggregate manifest",
     ],
     "sdd_refs": ["031"],
     "mandate_rows": ["E7.M5"],
     "status": "✓ shipped",
     "notes": "R286 mcp-aggregate per SDD-031."},
    {"id": "A-13",
     "axis_verbatim": ("Debian 13 Base, Sovereign OS and vision, why "
                        "non-GUI by default. server, dashboard or API "
                        "and modules and tools vision"),
     "source": "hook drop 2026-05-17",
     "implementing_verbs": [
         "sovereign-osctl architecture-qa show C-22",
     ],
     "sdd_refs": ["000"],
     "mandate_rows": [],
     "status": "✓ shipped",
     "notes": ("SDD-000 charter + C-22 'Debian as Ark' framing "
                "(R364).")},
    {"id": "A-14",
     "axis_verbatim": ("Everything via dashboard/UInterface or terminal "
                        "tools OR AI. Python, System and GPU and LLM "
                        "and multiple level and REPL"),
     "source": "hook drop 2026-05-17",
     "implementing_verbs": [
         "sovereign-osctl repl modes",
         "sovereign-osctl repl show python",
         "sovereign-osctl repl show system",
         "sovereign-osctl repl show gpu",
         "sovereign-osctl repl show llm",
         "sovereign-osctl repl exec <mode> <cmd>",
         "sovereign-osctl repl shell <mode>",
     ],
     "sdd_refs": [],
     "mandate_rows": ["E2.M35"],
     "status": "✓ shipped",
     "notes": ("R366 multi-level REPL ships 4 operator-named modes "
                "(python / system / gpu / llm) with per-mode preamble "
                "+ reference commands + exec (one-shot) + shell "
                "(interactive). Closes A-14 partial → ✓.")},
    {"id": "A-15",
     "axis_verbatim": ("Programming, Proto-Programing, Proto-Proto-"
                        "Programming and CoT and custom CoT, integrated "
                        "intelligence modules, features and options"),
     "source": "hook drop 2026-05-17",
     "implementing_verbs": [
         "sovereign-osctl cot list",
         "sovereign-osctl cot show",
         "sovereign-osctl cot run",
     ],
     "sdd_refs": [],
     "mandate_rows": ["E2.M15"],
     "status": "✓ shipped",
     "notes": "R309 cot-registry (6 named CoT routines + custom CoT)."},
    {"id": "A-16",
     "axis_verbatim": ("Kernel optimisation, OS, Services, Modules, "
                        "Tools, Dashboards, Configurations, Options"),
     "source": "hook drop 2026-05-17 (axis list)",
     "implementing_verbs": [
         "sovereign-osctl kernel-cmdline",
         "sovereign-osctl bios-directives",
         "sovereign-osctl hardening-base",
     ],
     "sdd_refs": [],
     "mandate_rows": ["E1.M27", "E1.M34"],
     "status": "✓ shipped",
     "notes": "R305 kernel-cmdline + R299 bios-directives + R306 hardening."},
    {"id": "A-17",
     "axis_verbatim": "Network, App, & In between",
     "source": "hook drop 2026-05-17",
     "implementing_verbs": [
         "sovereign-osctl network",
         "sovereign-osctl service-deps",
         "sovereign-osctl perimeter",
     ],
     "sdd_refs": [],
     "mandate_rows": [],
     "status": "✓ shipped",
     "notes": ("R241 net-state + R277 service-deps + R254 tetragon-"
                "status close the in-between perimeter.")},
    {"id": "A-18",
     "axis_verbatim": ("Memory too I guess and bios settings directives "
                        "and admonition of things that might also not "
                        "be possible on some board, possibly detecting "
                        "the ASUS ProArt X870E-CREATOR WIFI and its "
                        "settings"),
     "source": "hook drop 2026-05-17",
     "implementing_verbs": [
         "sovereign-osctl memory-profile",
         "sovereign-osctl bios-directives",
         "sovereign-osctl bios-info",
     ],
     "sdd_refs": [],
     "mandate_rows": ["E1.M18"],
     "status": "✓ shipped",
     "notes": ("R257 memory-profile + R299 bios-directives + R312 "
                "bios-info per-board (ASUS ProArt X870E-Creator).")},
    {"id": "A-19",
     "axis_verbatim": ("pci lane splits and whatever like "
                        "virtualization or what we find relevant via "
                        "search online and such"),
     "source": "hook drop 2026-05-17",
     "implementing_verbs": [
         "sovereign-osctl pcie-policy",
         "sovereign-osctl pcie-policy",
         "sovereign-osctl pcie-lane-detect",
     ],
     "sdd_refs": [],
     "mandate_rows": ["E1.M14", "E1.M24"],
     "status": "✓ shipped",
     "notes": "R260 pcie-policy + R234 pcie-lane-detect + R234 vfio-bind."},
    {"id": "A-20",
     "axis_verbatim": ("Adapting / Considering the given PSU "
                        "(probably not detectable ?) wattage and "
                        "rating ? (me: be Quiet! Dark Power Pro 13 "
                        "1600W Power Supply | ATX 3.1 Compliant | "
                        "80 Plus Titanium)"),
     "source": "hook drop 2026-05-17",
     "implementing_verbs": [
         "sovereign-osctl power-status psu",
         "sovereign-osctl power-status budget",
         "sovereign-osctl psu-oc-mode",
     ],
     "sdd_refs": [],
     "mandate_rows": ["E1.M16", "E1.M26"],
     "status": "✓ shipped",
     "notes": ("R252 power-status (PSU + budget) + R294 psu-oc-mode "
                "+ R317 inventory-catalog enumerates the operator's "
                "be Quiet! Dark Power Pro 13 1600W.")},
    {"id": "A-21",
     "axis_verbatim": ("considering XMP profile and OC profile and "
                        "room for each and estimated at 100% usage and "
                        "then real time tracking and intelligence "
                        "around it. (Possibly heat too I guess) My PSU "
                        "even have an overclock mode which might be "
                        "important"),
     "source": "hook drop 2026-05-17",
     "implementing_verbs": [
         "sovereign-osctl xmp-oc-room",
         "sovereign-osctl psu-oc-mode",
         "sovereign-osctl thermal-oc-budget",
         "sovereign-osctl heat-oc-throttle",
     ],
     "sdd_refs": [],
     "mandate_rows": ["E1.M30", "E1.M35", "E1.M38"],
     "status": "✓ shipped",
     "notes": ("R296 thermal-oc-budget + R315 xmp-oc-room-advisor + "
                "R294 psu-oc-mode + R318 heat-oc-throttle (triple-"
                "gate apply ceremony).")},
    {"id": "A-22",
     "axis_verbatim": ("the PSU/APC integration with the power "
                        "mangement and the scheduled shutdown when "
                        "battery reach a certain point as one default "
                        "profile. (schedule/planifest/graceful on all "
                        "levels, orderly)"),
     "source": "hook drop 2026-05-17",
     "implementing_verbs": [
         "sovereign-osctl power-status ups",
         "sovereign-osctl power-shutdown plan",
         "sovereign-osctl power-shutdown apply",
         "sovereign-osctl power-profiles",
         "sovereign-osctl apc-profile",
         "sovereign-osctl battery-ladder",
     ],
     "sdd_refs": [],
     "mandate_rows": ["E1.M16", "E1.M21", "E1.M29"],
     "status": "✓ shipped",
     "notes": ("R252 power-status UPS + R253 graceful-shutdown timer "
                "+ R293 power-profiles + R314 apc-profile + R302 "
                "battery-ladder.")},
    {"id": "A-23",
     "axis_verbatim": ("Fan / cooling awareness advisor — is it also "
                        "going to be aware of my fans ? or my fan "
                        "settings? bios and such ? and what it should "
                        "be vs what it is and software side override?"),
     "source": "hook drop 2026-05-17 (§1b operator drop)",
     "implementing_verbs": [
         "sovereign-osctl fan-advisor",
     ],
     "sdd_refs": [],
     "mandate_rows": ["E1.M39"],
     "status": "✓ shipped",
     "notes": ("R337 fan-advisor with per-mode (idle / inference-"
                "ready / training / oc-burst) curves + BIOS gate "
                "detection (X870E-CREATOR WiFi Q-Fan + Allow Software "
                "Override + Manual profile).")},
    {"id": "A-24",
     "axis_verbatim": ("My APC: APC Smart-UPS 2200VA 1980W LCD Tower "
                        "SmartConnect 20A 120V SMT2200C"),
     "source": "hook drop 2026-05-17 (§1b hardware-spec drop)",
     "implementing_verbs": [
         "sovereign-osctl inventory",
         "sovereign-osctl inventory show ups-0",
         "sovereign-osctl power-status ups",
     ],
     "sdd_refs": [],
     "mandate_rows": ["E1.M37"],
     "status": "✓ shipped",
     "notes": ("R317 inventory-catalog ships ups-0 = SMT2200C with "
                "operator-verbatim spec + refurbished-1YR caveat that "
                "R252 power-status surfaces on OnBattery (via R348 "
                "inventory_consult helper).")},
    {"id": "A-25",
     "axis_verbatim": ("My RAM: 2x CORSAIR Vengeance DDR5 RAM 128GB "
                        "(2x64GB) Up to 6400MHz CL42-52-52-104 1.35V "
                        "Intel XMP 3.0 (CMK128GX5M2B6400C42)"),
     "source": "hook drop 2026-05-17 (§1b hardware-spec drop)",
     "implementing_verbs": [
         "sovereign-osctl inventory show ram-dimm-0",
         "sovereign-osctl xmp-oc-room status",
     ],
     "sdd_refs": [],
     "mandate_rows": ["E1.M37", "E1.M40"],
     "status": "✓ shipped",
     "notes": ("R317 inventory catalog ships 4 DIMM slots with exact "
                "SKU CMK128GX5M2B6400C42 + R347 xmp-oc-room-advisor "
                "surfaces the 4-DIMM XMP-stability caveat when "
                "xmp_enabled=true.")},
    {"id": "A-26",
     "axis_verbatim": ("Nvme: 2x Samsung 990 EVO Plus - 2TB PCIe Gen4. "
                        "X4 / Gen5. X2"),
     "source": "hook drop 2026-05-17 (§1b hardware-spec drop)",
     "implementing_verbs": [
         "sovereign-osctl inventory show nvme-m2-0",
         "sovereign-osctl storage-health",
         "sovereign-osctl pcie-policy",
     ],
     "sdd_refs": [],
     "mandate_rows": ["E1.M37"],
     "status": "✓ shipped",
     "notes": ("R317 catalog ships 2 NVMe slots; R298 storage-health "
                "+ R260 pcie-lanes cross-check.")},
    {"id": "A-27",
     "axis_verbatim": ("continue till you meet ALL MY REQUIREMENTS "
                        "without MINIMIZING or rephrasing or "
                        "compressing or conflating"),
     "source": "/goal directive 2026-05-18",
     "implementing_verbs": [
         "sovereign-osctl architecture-qa concepts",
         "sovereign-osctl ccd-pinning verify",
         "sovereign-osctl state-fabric verify",
         "sovereign-osctl network-topology verify",
     ],
     "sdd_refs": [],
     "mandate_rows": ["E10.M3", "E10.M4", "E10.M5", "E10.M6",
                       "E10.M7", "E10.M8", "E10.M9"],
     "status": "✓ shipped",
     "notes": ("R355-R364: 23-concept architecture-qa catalog + "
                "verbatim-preservation L3 across 24 master spec "
                "sections + ~352 operator-exact phrases mechanized "
                "at push-time. /goal contract mechanized.")},
    {"id": "A-28",
     "axis_verbatim": ("RETURN REREAD ALL THE RAW DUMP AND REPROCESS "
                        "IF YOU NEED or JUST ask me question if you "
                        "are lost"),
     "source": "/goal directive 2026-05-18",
     "implementing_verbs": [
         "sovereign-osctl architecture-qa search",
     ],
     "sdd_refs": [],
     "mandate_rows": ["E10.M3", "E10.M9"],
     "status": "✓ shipped",
     "notes": ("R355 + R364 re-process pattern: both raw dumps "
                "(1139-line SAIN-01 + 404-line macro-arc plan) "
                "now fully surfaced as discoverable verbs with "
                "verbatim-preservation L3.")},
    {"id": "A-29",
     "axis_verbatim": ("perpetual mandate — DO not stop after opening "
                        "or updating a PR. continue endlessly"),
     "source": "hook drop 2026-05-17",
     "implementing_verbs": [
         "sovereign-osctl coverage axes",
         "sovereign-osctl coverage audit",
     ],
     "sdd_refs": [],
     "mandate_rows": ["E10.M10"],
     "status": "✓ shipped",
     "notes": ("R365 coverage-map provides operator-pull audit of "
                "every named axis without forcing operator to scan "
                "the entire mandate file. The perpetual-mandate "
                "structure is now self-traversable.")},
    {"id": "A-30",
     "axis_verbatim": ("We do not minimize anything and we do proper "
                        "research online and processing of what I say "
                        "and what we find and what we think and we "
                        "move toward my solution endlessly"),
     "source": "hook drop 2026-05-17",
     "implementing_verbs": [
         "sovereign-osctl research-loop",
         "sovereign-osctl architecture-qa",
     ],
     "sdd_refs": [],
     "mandate_rows": [],
     "status": "✓ shipped",
     "notes": ("R236 research-loop + R355+ architecture-qa verbatim "
                "preservation. No-minimization contract mechanized "
                "via L3 verbatim-preservation assertions.")},
    {"id": "A-31",
     "axis_verbatim": ("Senior Architect DevOps Software Engineer "
                        "Fullstack Expert & Mindset. Always a strong "
                        "workflow and non-blocking but always toward "
                        "the goal(s). Apply what I said at scale and "
                        "you have for a very long time of work. Take "
                        "your time, do this right."),
     "source": "hook drop 2026-05-17",
     "implementing_verbs": [
         "sovereign-osctl architecture-qa show C-22",
         "sovereign-osctl coverage audit",
         "sovereign-osctl doctrine-status status",
         "sovereign-osctl quarterly-review snapshot",
     ],
     "sdd_refs": ["033", "037"],
     "mandate_rows": [],
     "status": "✓ shipped",
     "notes": ("Operator-stated MINDSET + WORKFLOW contract. "
                "Mechanized via SDD-033 perpetual-intake doctrine + "
                "SDD-037 verbatim-preservation doctrine + the "
                "fabrication-catch quintet (R368/R371/R372/R373/R374). "
                "Non-blocking: every round is independently substantive "
                "+ tested + commit-pushed without operator gate. "
                "Strong workflow: 23-round R355-R377 verbatim arc "
                "demonstrates 'at scale + very long time of work' + "
                "'take your time, do this right' = 78 catalogued "
                "items + 20 bugs caught + grade A quarterly state.")},
    {"id": "A-33",
     "axis_verbatim": ("everything is not just core, not just cli, "
                        "not just TUI, not just API, not just tool "
                        "and MCP but also Dashboards and Web Apps "
                        "and Services"),
     "source": "§1g 8-surface delivery contract (R453 anchor verbatim)",
     "implementing_verbs": [
         "sovereign-osctl surface-map coverage",
         "sovereign-osctl surface-map gaps",
         "sovereign-osctl surface-map watch",
         "sovereign-osctl surface-map milestone",
         "sovereign-osctl surface-map selfdef",
         "sovereign-osctl doc-coverage scan",
         "sovereign-osctl anti-minimization-audit scan",
         "sovereign-osctl ux-design-audit audit",
         "sovereign-osctl compliance status",
     ],
     "sdd_refs": ["037", "038", "039"],
     "mandate_rows": ["E10.M97", "E10.M105", "E10.M106", "E10.M110"],
     "status": "✓ shipped",
     "notes": ("Operator §1g 8-surface delivery contract VERBATIM "
                "anchor. Mechanized via SDD-039 doctrine (R548 "
                "codification of the R453-R547 implementation lattice) "
                "+ SDD-038 cross-repo binding (R462 SurfaceManifest) "
                "+ SDD-037 verbatim-preservation. Runtime instruments: "
                "R453 surface-map (8-surface taxonomy + coverage matrix "
                "+ gap detection + waiver registry) + R454 doc-coverage "
                "(doc-surface coverage scanner) + R456 "
                "anti-minimization-audit + R457 ux-design-audit + R458 "
                "compliance rollup. R539 historic milestone: ALL twelve "
                "§1g-named modules at structural ceiling, ZERO FUTURE "
                "waivers — way-forward vector is "
                "quality-of-existing-surfaces NOT surface-promotion "
                "churn. R540 milestone-rollup observable + R546 "
                "dashboard verb-coverage symmetry (milestone + selfdef "
                "stat cards) + R547 README doc-gap closure. Operator "
                "§1g STANDING RULE verbatim (R456-anchored, "
                "sacrosanct): 'If you think something is really already "
                "done, ask yourself if you covered all angles and "
                "levels and layers and even if then improve it. Do "
                "not minimize or settle for less.'")},
    {"id": "A-32",
     "axis_verbatim": ("I trust you to break down planify and continue "
                        "with the SDD and TDD and a Senior Architect "
                        "DevOps Software Engineer Fullstack Expert & "
                        "Mindset"),
     "source": "hook drop 2026-05-17",
     "implementing_verbs": [
         "sovereign-osctl architecture-qa show C-21",
         "sovereign-osctl bootstrap phases",
         "sovereign-osctl coverage axes --status partial",
     ],
     "sdd_refs": ["028", "033", "037"],
     "mandate_rows": [],
     "status": "✓ shipped",
     "notes": ("Operator delegation of break-down + planify contract. "
                "Mechanized via SDD-028 phases.yaml (5-phase bootstrap) "
                "+ SDD-033 perpetual-intake doctrine + SDD-037 "
                "verbatim-preservation. 'SDD and TDD' = every round "
                "has SDD doc + L3 test. Operator-pull break-down "
                "queryable via coverage-map axes verb.")},
]


# ── Loading + filtering ───────────────────────────────────────────
def load_state(overlay_path: Path | None) -> tuple[list[dict], dict]:
    meta = {"_source": "(defaults)", "_overlay_keys": []}
    axes = list(DEFAULT_AXES)
    if load_with_overlay is not None:
        loaded = load_with_overlay(
            "coverage-map", {"axes": []}, explicit_path=overlay_path,
        )
        meta["_source"] = loaded.get("_source", meta["_source"])
        meta["_overlay_keys"] = loaded.get("_overlay_keys", [])
        if loaded.get("_parse_error"):
            meta["_parse_error"] = loaded["_parse_error"]
        if loaded.get("axes"):
            axes = list(loaded["axes"])
    return axes, meta


def filter_status(axes: list[dict], status: str | None) -> list[dict]:
    if not status:
        return axes
    return [a for a in axes if isinstance(a, dict)
            and a.get("status") == status]


def resolve_by_id(axes: list[dict], aid: str) -> dict | None:
    for a in axes:
        if isinstance(a, dict) and a.get("id") == aid:
            return a
    return None


def search_axes(axes: list[dict], needle: str) -> list[dict]:
    n = needle.lower()
    return [a for a in axes if isinstance(a, dict) and (
        n in (a.get("axis_verbatim") or "").lower()
        or n in (a.get("notes") or "").lower()
        or any(n in v.lower() for v in (a.get("implementing_verbs") or []))
        or any(n in r.lower() for r in (a.get("mandate_rows") or []))
    )]


# ── Renderers ──────────────────────────────────────────────────────
def render_axes_human(axes: list[dict]) -> str:
    lines = [f"── R365 operator coverage axes ({len(axes)}) ──"]
    counts = {"✓ shipped": 0, "partial": 0, "TODO": 0}
    for a in axes:
        s = a.get("status", "?")
        counts[s] = counts.get(s, 0) + 1
    lines.append(f"  ✓ shipped: {counts.get('✓ shipped', 0)} | "
                  f"partial: {counts.get('partial', 0)} | "
                  f"TODO: {counts.get('TODO', 0)}")
    lines.append("")
    for a in axes:
        glyph = ({"✓ shipped": "✓", "partial": "·", "TODO": "○"}
                 .get(a.get("status", ""), "?"))
        lines.append(f"  {glyph} [{a.get('id')}] {a.get('axis_verbatim', '')[:70]}…")
        lines.append(f"      source: {a.get('source')}")
        verbs = a.get("implementing_verbs") or []
        if verbs:
            lines.append(f"      verbs:  {len(verbs)} ({verbs[0]}…)")
    return "\n".join(lines) + "\n"


def render_show_human(a: dict) -> str:
    lines = [f"── R365 axis {a.get('id')} (status: {a.get('status')}) ──"]
    lines.append("")
    lines.append("  OPERATOR VERBATIM:")
    body = a.get("axis_verbatim") or ""
    cur = "    "
    for word in body.split():
        if len(cur) + len(word) > 76 and cur.strip():
            lines.append(cur.rstrip())
            cur = "    "
        cur += word + " "
    if cur.strip():
        lines.append(cur.rstrip())
    lines.append("")
    lines.append(f"  source:        {a.get('source')}")
    lines.append(f"  status:        {a.get('status')}")
    lines.append(f"  mandate rows:  {', '.join(a.get('mandate_rows') or []) or '(none)'}")
    lines.append(f"  SDD refs:      {', '.join(a.get('sdd_refs') or []) or '(none)'}")
    lines.append("")
    lines.append("  Implementing verbs:")
    for v in (a.get("implementing_verbs") or []):
        lines.append(f"    $ {v}")
    lines.append("")
    lines.append("  Notes:")
    body = a.get("notes") or ""
    cur = "    "
    for word in body.split():
        if len(cur) + len(word) > 76 and cur.strip():
            lines.append(cur.rstrip())
            cur = "    "
        cur += word + " "
    if cur.strip():
        lines.append(cur.rstrip())
    return "\n".join(lines) + "\n"


# ── Main ──────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="coverage-map.py")
    sub = p.add_subparsers(dest="cmd", required=True)

    pa = sub.add_parser("axes")
    pa.add_argument("--status")
    pa.add_argument("--config", type=Path)
    pag = pa.add_mutually_exclusive_group()
    pag.add_argument("--json", dest="fmt", action="store_const", const="json")
    pag.add_argument("--human", dest="fmt", action="store_const", const="human")
    pa.set_defaults(fmt="json")

    ps = sub.add_parser("show")
    ps.add_argument("axis_id")
    ps.add_argument("--config", type=Path)
    psg = ps.add_mutually_exclusive_group()
    psg.add_argument("--json", dest="fmt", action="store_const", const="json")
    psg.add_argument("--human", dest="fmt", action="store_const", const="human")
    ps.set_defaults(fmt="json")

    pau = sub.add_parser("audit")
    pau.add_argument("--config", type=Path)
    paug = pau.add_mutually_exclusive_group()
    paug.add_argument("--json", dest="fmt", action="store_const", const="json")
    paug.add_argument("--human", dest="fmt", action="store_const", const="human")
    pau.set_defaults(fmt="json")

    psr = sub.add_parser("search")
    psr.add_argument("needle")
    psr.add_argument("--config", type=Path)
    psrg = psr.add_mutually_exclusive_group()
    psrg.add_argument("--json", dest="fmt", action="store_const", const="json")
    psrg.add_argument("--human", dest="fmt", action="store_const", const="human")
    psr.set_defaults(fmt="json")

    args = p.parse_args(argv)
    axes, meta = load_state(getattr(args, "config", None))

    if args.cmd == "axes":
        items = filter_status(axes, getattr(args, "status", None))
        if args.fmt == "json":
            shipped = sum(1 for a in items if a.get("status") == "✓ shipped")
            partial = sum(1 for a in items if a.get("status") == "partial")
            todo = sum(1 for a in items if a.get("status") == "TODO")
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "axis_count": len(items),
                "shipped_count": shipped,
                "partial_count": partial,
                "todo_count": todo,
                "axes": items,
                "overlay": meta,
            }, indent=2))
        else:
            print(render_axes_human(items), end="")
        return 0

    if args.cmd == "show":
        a = resolve_by_id(axes, args.axis_id)
        if a is None:
            print(json.dumps({
                "error": f"unknown axis: {args.axis_id}",
                "known_axes": [x.get("id") for x in axes if isinstance(x, dict)],
                "round": ROUND,
            }, indent=2), file=sys.stderr)
            return 1
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "axis": a,
                "overlay": meta,
            }, indent=2))
        else:
            print(render_show_human(a), end="")
        return 0

    if args.cmd == "audit":
        todo = [a for a in axes if a.get("status") == "TODO"]
        partial = [a for a in axes if a.get("status") == "partial"]
        shipped = [a for a in axes if a.get("status") == "✓ shipped"]
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "total_axes": len(axes),
                "shipped_count": len(shipped),
                "partial_count": len(partial),
                "todo_count": len(todo),
                "todo_axes": [{"id": a.get("id"),
                                "axis_verbatim": a.get("axis_verbatim"),
                                "source": a.get("source")} for a in todo],
                "partial_axes": [{"id": a.get("id"),
                                    "axis_verbatim": a.get("axis_verbatim"),
                                    "notes": a.get("notes")} for a in partial],
                "overlay": meta,
            }, indent=2))
        else:
            print(f"── R365 coverage audit ──")
            print(f"  total:   {len(axes)}")
            print(f"  shipped: {len(shipped)} ({100*len(shipped)//max(1,len(axes))}%)")
            print(f"  partial: {len(partial)}")
            print(f"  TODO:    {len(todo)}")
            print()
            if todo:
                print("  TODO axes (operator-stated, not yet implemented):")
                for a in todo:
                    print(f"    ○ [{a.get('id')}] {a.get('axis_verbatim', '')[:70]}…")
            if partial:
                print("  Partial axes (need more depth):")
                for a in partial:
                    print(f"    · [{a.get('id')}] {a.get('axis_verbatim', '')[:70]}…")
                    print(f"        {a.get('notes', '')[:70]}…")
        return 1 if todo else 0

    if args.cmd == "search":
        matches = search_axes(axes, args.needle)
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "needle": args.needle,
                "match_count": len(matches),
                "matched_axes": matches,
                "overlay": meta,
            }, indent=2))
        else:
            print(f"── R365 coverage search: '{args.needle}' ──")
            print(f"  {len(matches)} axis match(es)")
            for a in matches:
                print(f"    [{a.get('id')}] {a.get('axis_verbatim', '')[:65]}…")
        return 0 if matches else 1

    return 2


if __name__ == "__main__":
    sys.exit(main())
