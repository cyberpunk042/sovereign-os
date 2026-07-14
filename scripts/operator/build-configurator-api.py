#!/usr/bin/env python3
"""
scripts/operator/build-configurator-api.py — Read-only HTTP API + webapp
for the BUILD-TIME configurator surface.

This is the build-time sibling of the D-NN runtime cockpit. It serves the
single-file composer at webapp/build-configurator/index.html and a
`/data.json` assembled from the REAL repo files so the page reflects the
operator's actual options instead of the baked-in offline snapshot:

  - profiles/*.yaml          → profile list + per-profile kernel/cpu/
                               modules/packages detail
  - config/operator-deps.toml (or .example) → apt/pip/npm/curl_shell tools

Materializes the 2026-05-16 arc-opening directive (info-hub
raw/notes/2026-05-16-user-directive-sovereign-os-arc-opening.md:7):
"an assistant feeling as we are going through the building and all the
layer and/or chosing the flavor and options."

Sovereignty:
  - Read-only verbs ONLY. This daemon NEVER triggers a build; it reads
    spec files and renders choices. The operator copies the generated
    command and runs orchestrate.sh themselves (sudo + ~30 min).
  - Loopback-bind by default (127.0.0.1).
  - stdlib-first; PyYAML/tomllib used if present, with graceful fallback
    to the page's baked snapshot when a parser is unavailable.

Endpoints:
  GET /                 — the build-configurator webapp (single file)
  GET /data.json        — assembled real profile + operator-deps data
  GET /host.json        — LIVE host probe (manage-this-OS mode): kernel,
                          cmdline, kconfig, modules, packages, cpu flags,
                          sovereign-* unit states, GPUs, ZFS pools.
                          Read-only probes; never mutates the host.
  GET /<panel>/...      — any sibling webapp/ panel served statically
                          (master-dashboard, trinity, auditor, …) so the
                          cockpit links work from this one process. Pages
                          whose data APIs aren't running degrade to their
                          baked snapshots, same as this page does.
  GET /panels.json      — discovery: every webapp/ panel (id + title)
  GET /panels/          — generated HTML index of all panels
  GET /api/<svc>/...    — DEV GATEWAY: proxies to the local sovereign-*-api
                          process for that prefix (ports mirror the systemd
                          units). Lets statically-served panels reach their
                          live data without sovereign-gatewayd. 502 with a
                          JSON error when the backing API isn't running —
                          panels then fall back to their baked snapshots.
  GET /version          — service version + module identity
  GET /healthz          — liveness (always 200)

  POST /api/run         — EXECUTE a whitelisted repo action and stream its
                          log back (text/plain, line-buffered):
                            {"action": "dry-run"|"preflight"|"build",
                             "profile": "<id>"}
                          One job at a time (409 if busy). "build" requires
                          the server to run as root (start the panel with
                          sudo) — otherwise 403 with instructions. This is
                          the ONE deliberate exception to the read-only
                          rule, added on operator request 2026-06-12: the
                          builder page must be able to actually build.
  POST /api/cancel      — kill the currently-streaming job (process group)

Env vars:
  BUILD_CONFIGURATOR_API_BIND   (default: 127.0.0.1)
  BUILD_CONFIGURATOR_API_PORT   (default: 8100)
  BUILD_CONFIGURATOR_DRY_RUN    (set to 1 = print assembled data + exit)
"""
from __future__ import annotations

import html as html_mod
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

API_BIND = os.environ.get("BUILD_CONFIGURATOR_API_BIND", "127.0.0.1")
API_PORT = int(os.environ.get("BUILD_CONFIGURATOR_API_PORT", "8100"))
DRY_RUN = bool(os.environ.get("BUILD_CONFIGURATOR_DRY_RUN"))
VERSION = "0.1.0"

REPO = Path(__file__).resolve().parents[2]
PROFILES_DIR = REPO / "profiles"
# SDD-709: the frontend the built image boots into by default. Mirrors the
# canonical set in scripts/operator/frontend.py (FRONTENDS) — kept as a plain
# literal so the API stays import-light; the frontend-selector contract lint
# guards the two lists from drifting apart.
FRONTEND_CHOICES = frozenset({"gnome", "dashboards-kiosk", "open-computer-kiosk", "none"})
WEBAPP_ROOT = REPO / "webapp"
WEBAPP = WEBAPP_ROOT / "build-configurator" / "index.html"

STATIC_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
}

# Profiles surfaced in the picker, in display order, with one-liners.
PROFILE_META = [
    ("sain-01", "SAIN-01 AI Workstation", True,
     "Zen5 + dual-NVIDIA, ZFS-tiered, VFIO, Tetragon, SRP trinity."),
    ("developer", "developer", False, "polyglot dev workstation."),
    ("headless", "headless", False, "bare-metal server (auditd/fail2ban/chrony)."),
    ("minimal", "minimal", False, "VM baseline to try the pipeline."),
    ("old-workstation", "old-workstation", False, "constrained dev box (single 4090, ext4)."),
]

# AI assistants we offer as npm-global installs. Claude Code ships in the
# repo's operator-deps; OpenCode is offered here per the operator request
# (not yet in config/operator-deps.toml.example).
AI_TOOLS = [
    {"pkg": "@anthropic-ai/claude-code", "label": "Claude Code", "on": True,
     "note": "operator's primary AI assistant"},
    {"pkg": "opencode-ai", "label": "OpenCode", "on": False,
     "note": "open-source terminal agent", "isNew": True},
]


def _load_yaml(path: Path):
    try:
        import yaml  # PyYAML — declared build prerequisite
    except Exception:
        return None
    try:
        return yaml.safe_load(path.read_text())
    except Exception:
        return None


def _load_toml(path: Path):
    try:
        import tomllib  # py3.11+ stdlib
        return tomllib.loads(path.read_text())
    except Exception:
        pass
    try:
        import tomli
        return tomli.loads(path.read_text())
    except Exception:
        return None


def _profile_detail(doc: dict) -> dict | None:
    """Project a parsed profile YAML into the page's `detail` shape."""
    if not isinstance(doc, dict):
        return None
    k = doc.get("kernel", {}) or {}
    cfg = k.get("config", {}) or {}
    hw = doc.get("hardware", {}) or {}
    cpu = hw.get("cpu", {}) or {}
    feats = cpu.get("features", {}) or {}
    mods = k.get("modules", {}) or {}
    pkgs = doc.get("packages", {}) or {}
    cmdline = k.get("cmdline", {}) or {}
    storage = hw.get("storage", {}) or {}
    cflags = (k.get("compile_flags", {}) or {}).get("KCFLAGS", "")
    mc = cfg.get("require_microcode") or "amd"

    datasets = [
        {
            "name": d.get("name", "?"),
            "recordsize": str(d.get("recordsize", "128k")),
            "compression": str(d.get("compression", "lz4")),
            "extra": " ".join(
                f"{key}={d[key]}" for key in ("copies", "sync", "redundant_metadata")
                if key in d
            ),
            "purpose": (d.get("purpose", "") or "").split(";")[0],
        }
        for d in storage.get("datasets", []) or []
    ]
    network = [
        {
            "role": n.get("role", "?"),
            "nic": f"{n.get('vendor','?')} {n.get('model','?')} {n.get('speed_gbps','?')}GbE",
            "vlan": n.get("vlan", 0),
            "address": n.get("address", ""),
            "mtu": n.get("mtu", 1500),
            "default_gateway": bool(n.get("default_gateway")),
            "gateway": n.get("gateway", ""),
            "iface": n.get("iface_hint", ""),
        }
        for n in hw.get("network", []) or []
    ]
    hooks = {}
    for phase, entries in (doc.get("hooks", {}) or {}).items():
        hooks[phase] = [
            {
                "id": h.get("id", "?"),
                "type": h.get("type", ""),
                "mandatory": bool(h.get("mandatory")),
                **({"schedule": h["schedule"]} if "schedule" in h else {}),
            }
            for h in entries or []
        ]
    return {
        "mixins": doc.get("mixins", []) or [],
        "kernel": {
            "source": k.get("source", "kernel.org-stable"),
            "version_minimum": str(k.get("version_minimum", "6.12")),
            "march": (cpu.get("march") or "znver5"),
            "kcflags": cflags,
            "enable": cfg.get("enable", []) or [],
            "microcode": ["amd", "intel"],
            "microcode_default": mc,
            "cmdline_base": cmdline.get("base", []) or [],
            "cmdline_vfio": cmdline.get("vfio", []) or [],
        },
        "cpu": {
            "required": feats.get("required", []) or [],
            "preferred": feats.get("preferred", []) or [],
        },
        "modules": {
            "load": mods.get("load_at_boot", []) or [],
            "blacklist": mods.get("blacklist", []) or [],
        },
        "packages": {
            "base": pkgs.get("base", []) or [],
            "profile": pkgs.get("profile", []) or [],
            "deny": pkgs.get("deny", []) or [],
            # the sain-01 header marks these PLACEHOLDER until Stage 2+.
            "placeholder": True,
        },
        "storage": {
            "layout": storage.get("layout", ""),
            "datasets": datasets,
        },
        "network": network,
        "hooks": hooks,
    }


def _config_path(name: str) -> Path | None:
    """Prefer the operator's real config, fall back to the .example."""
    for cand in (REPO / "config" / name, REPO / "config" / f"{name}.example"):
        if cand.exists():
            return cand
    return None


def _hw_section() -> dict | None:
    """Assemble the hardware-preflight data from the R260/R292/R294 configs.

    Board advisories come from known-boards.toml; the structured BIOS
    checklist (what-to-set + why) stays curated in the webapp's snapshot —
    advisories here are appended as extra items so operator-added boards
    surface without a page edit. PSUs + power scalars parse live.
    """
    boards = _load_toml(_config_path("known-boards.toml") or Path("/nonexistent"))
    psu = _load_toml(_config_path("psu-oc.toml") or Path("/nonexistent"))
    headroom = _load_toml(_config_path("oc-headroom.toml") or Path("/nonexistent"))
    if not (boards or psu or headroom):
        return None

    psus = []
    for p in (psu or {}).get("known_psus", []) or []:
        psus.append({
            "model": p.get("model", "?"),
            "rated": p.get("rated_standard_watts", 0),
            "peak": p.get("brief_peak_watts", 0),
            "atx": str(p.get("atx_revision", "")),
            "eff": p.get("efficiency", ""),
            "oc": p.get("oc_mode_semantics", ""),
            "reference": "§1b" in (p.get("operator_notes", "") or ""),
        })

    power = {
        "cpu_tdp": (headroom or {}).get("cpu_tdp_watts", 170),
        "chassis": (headroom or {}).get("chassis_baseline_watts", 80),
        "dimm_base": (headroom or {}).get("memory_dimm_base_watts", 4),
        "mts_premium_per_1000": (headroom or {}).get("memory_mts_premium_per_1000", 1),
        "safety_margin_pct": (headroom or {}).get("safety_margin_pct", 20),
    }

    # Board advisories from known-boards.toml are already curated into the
    # webapp's structured BIOS checklist (what-to-set + why per item); we
    # don't re-emit them raw here or they would render twice.
    out = {"psus": psus or None, "power": power}
    return {k: v for k, v in out.items() if v}


def _tuning_section() -> list | None:
    doc = _load_toml(_config_path("kernel-tuning.toml") or Path("/nonexistent"))
    if not isinstance(doc, dict):
        return None
    out = []
    for name, p in (doc.get("presets", {}) or {}).items():
        hints = (p.get("cmdline_hints", {}) or {}).get("hints", []) or []
        out.append({
            "name": name,
            "summary": p.get("summary", ""),
            "sysctl": p.get("sysctl", {}) or {},
            "hints": hints,
        })
    return out or None


def _deps_tools() -> dict:
    """Read config/operator-deps.toml (or .example) into the tool bags."""
    src = REPO / "config" / "operator-deps.toml"
    if not src.exists():
        src = REPO / "config" / "operator-deps.toml.example"
    doc = _load_toml(src) if src.exists() else None

    apt = pip = []
    npm_global = []
    curl = []
    if isinstance(doc, dict):
        apt = (doc.get("apt", {}) or {}).get("install", []) or []
        pip = (doc.get("pip", {}) or {}).get("install", []) or []
        npm_global = (doc.get("npm", {}) or {}).get("global", []) or []
        curl = (doc.get("curl_shell", {}) or {}).get("installs", []) or []

    # Merge the repo's npm globals into the AI-tool offering so anything the
    # operator already declared shows as on; keep our OpenCode offer too.
    ai = [dict(t) for t in AI_TOOLS]
    known = {t["pkg"] for t in ai}
    for g in npm_global:
        if g in known:
            for t in ai:
                if t["pkg"] == g:
                    t["on"] = True
        else:
            ai.append({"pkg": g, "label": g, "on": True})

    return {
        "ai": ai,
        "apt": [{"pkg": p, "on": True} for p in apt],
        "pip": [{"pkg": p, "on": True} for p in pip],
        "curl": [
            {"pkg": c.get("name", "?"), "on": False, "url": c.get("url", "")}
            for c in curl if isinstance(c, dict)
        ] or [
            {"pkg": "tailscale", "on": False, "url": "https://tailscale.com/install.sh"},
            {"pkg": "ollama", "on": False, "url": "https://ollama.ai/install.sh"},
        ],
    }


def _run(cmd: list[str], timeout: int = 5) -> str | None:
    """Run a read-only probe command; None on any failure (absent tool,
    timeout, non-zero exit). The host probe NEVER mutates the system."""
    try:
        out = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
        )
        return out.stdout if out.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def _host_kconfig() -> dict[str, str]:
    """CONFIG_* symbols of the RUNNING kernel (y/m), from /boot/config-$(uname -r)."""
    cfg = Path(f"/boot/config-{platform.release()}")
    out: dict[str, str] = {}
    if not cfg.is_file():
        return out
    try:
        for line in cfg.read_text(encoding="utf-8", errors="replace").splitlines():
            m = re.match(r"^CONFIG_([A-Za-z0-9_]+)=([ym])$", line)
            if m:
                out[m.group(1)] = m.group(2)
    except OSError:
        pass
    return out


def _host_units() -> dict[str, dict]:
    """sovereign-* unit state on the running host: installed/enabled/active."""
    units: dict[str, dict] = {}
    listed = _run(["systemctl", "list-unit-files", "sovereign-*",
                   "--no-legend", "--plain", "--no-pager"]) or ""
    for line in listed.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            units[parts[0]] = {"installed": True, "enabled": parts[1],
                               "active": "inactive"}
    active = _run(["systemctl", "list-units", "sovereign-*", "--all",
                   "--no-legend", "--plain", "--no-pager"]) or ""
    for line in active.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0] in units:
            units[parts[0]]["active"] = parts[2]
    return units


def assemble_host() -> dict:
    """LIVE probe of the running OS — the 'manage this host' data source.
    Every probe is read-only and degrades to absent-key on failure."""
    host: dict = {
        "hostname": platform.node(),
        "kernel": platform.release(),
        "probed_from_repo": str(REPO),
    }
    try:
        host["cmdline"] = Path("/proc/cmdline").read_text().split()
    except OSError:
        host["cmdline"] = []
    try:
        cpuinfo = Path("/proc/cpuinfo").read_text()
        m = re.search(r"^flags\s*:\s*(.+)$", cpuinfo, re.M)
        host["cpu_flags"] = sorted(m.group(1).split()) if m else []
        m = re.search(r"^model name\s*:\s*(.+)$", cpuinfo, re.M)
        if m:
            host["cpu_model"] = m.group(1).strip()
    except OSError:
        host["cpu_flags"] = []
    try:
        host["modules"] = sorted(
            line.split()[0]
            for line in Path("/proc/modules").read_text().splitlines() if line
        )
    except OSError:
        host["modules"] = []
    host["kconfig"] = _host_kconfig()

    dpkg = _run(["dpkg-query", "-W", "-f", "${Package}\t${Status}\n"],
                timeout=15) or ""
    host["packages"] = sorted(
        line.split("\t")[0] for line in dpkg.splitlines()
        if line.endswith("install ok installed")
    )

    host["units"] = _host_units()
    host["osctl"] = (shutil.which("sovereign-osctl")
                     or (str(REPO / "scripts" / "sovereign-osctl")
                         if (REPO / "scripts" / "sovereign-osctl").exists()
                         else None))
    host["opt_symlink"] = os.path.realpath("/opt/sovereign-os") \
        if os.path.exists("/opt/sovereign-os") else None
    active = REPO / ".sovereign-os" / "active-profile"
    host["active_profile"] = (
        active.read_text().strip() if active.is_file() else None
    )

    smi = _run(["nvidia-smi", "--query-gpu=name,power.limit",
                "--format=csv,noheader"])
    if smi:
        host["gpus"] = [
            {"name": n.strip(), "power_limit": p.strip()}
            for n, _, p in (ln.partition(",") for ln in smi.splitlines() if ln)
        ]
    zpools = _run(["zpool", "list", "-H", "-o", "name"])
    if zpools is not None:
        host["zpools"] = [p for p in zpools.split() if p]
    host["tool_bins"] = {
        name: bool(shutil.which(name))
        for name in ("claude", "opencode", "tailscale", "ollama", "podman",
                     "nvidia-smi", "zpool", "tetragon", "prometheus", "git",
                     "rg", "jq", "fdfind", "sensors", "wasmtime")
    }
    return host


def list_panels() -> list[dict]:
    """Discovery: every webapp/<dir>/index.html, with its <title>."""
    panels = []
    for d in sorted(WEBAPP_ROOT.iterdir()):
        idx = d / "index.html"
        if not (d.is_dir() and idx.is_file()) or d.name.startswith("_"):
            continue
        title = d.name
        try:
            m = re.search(r"<title>(.*?)</title>",
                          idx.read_text(encoding="utf-8", errors="replace"),
                          re.S | re.I)
            if m:
                title = re.sub(r"\s+", " ", m.group(1)).strip() or d.name
        except OSError:
            pass
        panels.append({"id": d.name, "title": title, "path": f"/{d.name}/"})
    return panels


CATALOG_FILE = REPO / "config" / "dashboard-catalog.yaml"


def _load_catalog() -> dict | None:
    if not CATALOG_FILE.is_file():
        return None
    try:
        import yaml
        return yaml.safe_load(CATALOG_FILE.read_text())
    except Exception:
        return None


CONTROL_SYSTEMS_FILE = REPO / "config" / "control-systems.yaml"


def _load_control_systems() -> dict | None:
    """SDD-045 §4 — the 11 on/off + mode + profile systems the shared
    control-surface component renders (the operator's 'everything can be
    turned on and off + tons of modes and profiles')."""
    if not CONTROL_SYSTEMS_FILE.is_file():
        return None
    try:
        import yaml
        return yaml.safe_load(CONTROL_SYSTEMS_FILE.read_text())
    except Exception:
        return None


FEATURE_COVERAGE_FILE = REPO / "config" / "feature-coverage.yaml"


def _load_feature_coverage() -> dict | None:
    """SDD-045 §7 — the completeness ledger (every verb family → a dashboard
    or a cli-only waiver). Served so the master-dashboard can prove, live, that
    nothing is CLI-only-and-invisible."""
    if not FEATURE_COVERAGE_FILE.is_file():
        return None
    try:
        import yaml
        cov = yaml.safe_load(FEATURE_COVERAGE_FILE.read_text())
        mapped = sum(len(v) for v in (cov.get("coverage") or {}).values())
        waived = len(cov.get("cli_only") or [])
        return {
            "verb_families_total": mapped + waived,
            "mapped_to_dashboard": mapped,
            "cli_only_waived": waived,
            "dashboards_governing": len(cov.get("coverage") or {}),
            "coverage": cov.get("coverage") or {},
            "cli_only": cov.get("cli_only") or [],
        }
    except Exception:
        return None


MODELS_CATALOG_FILE = REPO / "models" / "catalog.yaml"


def _load_models_catalog() -> dict | None:
    """SDD-045 §5 — the 68-model catalog (models/catalog.yaml) the
    models-catalog dashboard browses (class / quant / tier / vram / purpose)."""
    if not MODELS_CATALOG_FILE.is_file():
        return None
    try:
        import yaml
        return yaml.safe_load(MODELS_CATALOG_FILE.read_text())
    except Exception:
        return None


AVX_ADVISOR = REPO / "scripts" / "hardware" / "avx512-advisor.py"


def _load_cpu_avx() -> dict:
    """SDD-045 §5 — the CPU / AVX-512 capability matrix the cpu-features
    dashboard renders. Runs the R272 avx512-advisor (read-only probe of THIS
    CPU) and aggregates probe (extensions) + workloads (per-workload fit) +
    advisory. Honest-degraded per verb if the advisor is unavailable."""
    import subprocess
    import sys as _sys
    out: dict = {}
    for verb in ("probe", "workloads", "advisory"):
        try:
            r = subprocess.run(
                [_sys.executable, str(AVX_ADVISOR), verb, "--json"],
                capture_output=True, text=True, timeout=10,
            )
            if r.returncode == 0 and r.stdout.strip():
                out[verb] = json.loads(r.stdout)
            else:
                out[verb] = {"error": (r.stderr or "no output").strip()[:200]}
        except Exception as e:  # noqa: BLE001 — operator-visible degradation
            out[verb] = {"error": str(e)}
    return out


OSCTL = REPO / "scripts" / "sovereign-osctl"


def _osctl_json(args: list[str]) -> dict:
    """Run a read-only `sovereign-osctl ... --json` and parse it. Honest-
    degraded (returns {error} instead of raising) so a panel shows the gap."""
    import subprocess
    try:
        r = subprocess.run(
            [str(OSCTL), *args, "--json"],
            capture_output=True, text=True, timeout=12, cwd=str(REPO),
        )
        if r.returncode == 0 and r.stdout.strip():
            return json.loads(r.stdout)
        return {"error": (r.stderr or "no output").strip()[:200]}
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


def _load_orchestration() -> dict:
    """SDD-045 §5 — the thinking-router / orchestration view: the 7-axis
    routing rules (SDD-011) + live routing metrics (which tier/class/task-type
    requests landed on). Read-only via `router rules|metrics --json`."""
    return {
        "rules": _osctl_json(["router", "rules"]),
        "metrics": _osctl_json(["router", "metrics"]),
    }


def _load_profile_generation() -> dict:
    """SDD-045 §5 — the runtime-profile generator view: the strategies and the
    resolved runtime profiles they produce (allocations + tier_intent). Reads
    profiles/runtime/*.yaml (the '20+ combos' producer output)."""
    import yaml
    rd = REPO / "profiles" / "runtime"
    profiles = []
    if rd.is_dir():
        for p in sorted(rd.glob("*.yaml")):
            try:
                doc = yaml.safe_load(p.read_text()) or {}
                profiles.append({"id": p.stem, "runtime_profile": doc.get("runtime_profile", doc)})
            except Exception as e:  # noqa: BLE001
                profiles.append({"id": p.stem, "error": str(e)})
    return {"strategies": [p["id"] for p in profiles], "profiles": profiles}


def _load_selfdef() -> dict:
    """SDD-045 §5 — the selfdef (IPS) management view. `selfdef status` prints
    human text (no --json), so return it raw + a parsed on/off state. The
    actual controls (on/off/sync/doctor + perimeter) come from the inlined
    control surface (copy-command; web never mutates)."""
    import subprocess
    try:
        r = subprocess.run(
            [str(OSCTL), "selfdef", "status"],
            capture_output=True, text=True, timeout=12, cwd=str(REPO),
        )
        text = (r.stdout or "").strip()
        # `selfdef status` ends with an explicit "OFF — …" / "ON — …" verdict.
        if "OFF" in text.upper():
            state = "off"
        elif "ON —" in text or "ON -" in text:
            state = "on"
        else:
            state = "unknown"
        return {"text": text, "state": state, "returncode": r.returncode}
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


def panels_index_html() -> str:
    """The GLOBAL VIEW: every surface — panels AND un-paneled feature
    domains — grouped by category, each with a real description, rendered
    from config/dashboard-catalog.yaml. Falls back to a flat list if the
    catalog is absent."""
    cat = _load_catalog()
    esc = html_mod.escape
    if not cat:
        rows = "\n".join(f'<li><a href="{p["path"]}">{esc(p["id"])}</a> '
                         f'<span class="muted">{esc(p["title"])}</span></li>'
                         for p in list_panels())
        return (f"<!doctype html><meta charset=utf-8><title>panels</title>"
                f"<h1>{len(list_panels())} panels</h1><ul>{rows}</ul>")

    by_cat: dict[str, list] = {}
    for d in cat["dashboards"]:
        by_cat.setdefault(d["category"], []).append(d)
    n_live = sum(1 for d in cat["dashboards"] if d.get("status") == "live")
    n_planned = sum(1 for d in cat["dashboards"] if d.get("status") == "planned")

    sections = []
    for c in cat["categories"]:
        items = by_cat.get(c["id"], [])
        if not items:
            continue
        cards = []
        for d in items:
            status = d.get("status", "live")
            badge = {"live": '<span class="b live">live</span>',
                     "snapshot": '<span class="b snap">snapshot</span>',
                     "planned": '<span class="b plan">no panel yet</span>'}.get(status, "")
            if d.get("path"):
                head = f'<a href="{esc(d["path"])}">{esc(d["label"])}</a>'
            else:
                head = f'<span class="nolink">{esc(d["label"])}</span>'
            access = ""
            if d.get("cli"):
                access = f'<div class="cli">▶ {esc(d["cli"])}</div>'
            refs = f'<span class="refs">{esc(", ".join(d.get("refs") or []))}</span>' if d.get("refs") else ""
            cards.append(
                f'<div class="card {status}"><div class="ct">{head}{badge}</div>'
                f'<div class="cd">{esc(d["description"])}</div>{access}{refs}</div>')
        sections.append(
            f'<section><h2>{esc(c["label"])}</h2>'
            f'<p class="blurb">{esc(c["blurb"])}</p><div class="grid">{"".join(cards)}</div></section>')

    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>sovereign-os · global view</title>
<style>
 body{{font:14px/1.55 system-ui,sans-serif;background:#0e1117;color:#cdd3e0;max-width:1100px;margin:1.5rem auto;padding:0 1rem}}
 h1{{font-size:1.35rem;margin:.2rem 0}} h2{{font-size:1.02rem;margin:1.4rem 0 .2rem;color:#e6edf3}}
 a{{color:#7fb3ff;text-decoration:none;font-weight:600}} a:hover{{text-decoration:underline}}
 .muted{{color:#7d8597}} .blurb{{color:#8b97a8;margin:.1rem 0 .6rem;font-size:.9em}}
 .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:.6rem}}
 .card{{background:#161b22;border:1px solid #263041;border-left:3px solid #30475e;border-radius:7px;padding:.6rem .7rem}}
 .card.planned{{border-left-color:#e6c07b}} .card.snapshot{{border-left-color:#7d8597}} .card.live{{border-left-color:#7fd18a}}
 .ct{{display:flex;align-items:center;gap:.5rem;margin-bottom:.25rem}} .nolink{{color:#c9d3e0;font-weight:600}}
 .cd{{color:#a9b4c2;font-size:.87em}} .cli{{color:#7fd18a;font-family:ui-monospace,monospace;font-size:.8em;margin-top:.3rem;word-break:break-all}}
 .refs{{color:#5a6472;font-size:.72em}} .note{{background:#161b22;border:1px solid #263041;border-radius:7px;padding:.7rem .9rem;margin:.7rem 0}}
 .b{{font-size:.66em;padding:.05rem .4rem;border-radius:10px;border:1px solid}}
 .b.live{{color:#7fd18a;border-color:#2f5c3a}} .b.snap{{color:#7d8597;border-color:#3a424f}} .b.plan{{color:#e6c07b;border-color:#5c4f2f}}
</style></head><body>
<h1>sovereign-os · global view</h1>
<div class="note"><strong>{len(cat['dashboards'])} surfaces</strong> across {len(cat['categories'])} categories —
{n_live} live panels · {n_planned} feature domains with <em>no panel yet</em> (reachable via the CLI shown).
A <span class="b live">live</span> panel only shows data when its <code>sovereign-*-api</code> is running —
<code>make panel</code> now starts them all. <a href="/master-dashboard/">cockpit</a> · <a href="/">build configurator</a>.</div>
{"".join(sections)}
</body></html>"""


# ── /api/run — the one deliberate exception to read-only (operator
#    request 2026-06-12: "there is no even a way to build in the builder
#    page"). Whitelisted actions only; one at a time; logs stream back. ──

RUN_ACTIONS = {
    # action id → (argv builder, needs_root)
    "dry-run":   (lambda: ["scripts/build/orchestrate.sh", "run", "--dry-run"], False),
    "preflight": (lambda: ["scripts/build/orchestrate.sh", "preflight"], False),
    "build":     (lambda: ["scripts/build/orchestrate.sh", "run"], True),
}
# ── background runs: a build/dry-run/preflight OUTLIVES the client that started
# it. Its output streams to a state LOG FILE and its metadata to a STATUS FILE,
# so navigating away NEVER kills it (the browser can leave, the run keeps going)
# and any client re-attaches later — /api/run/attach replays the full log so far
# + follows it live. Survives a daemon restart too (the start_new_session child
# writes straight to the file, independent of this daemon). ──
_RUN_STATE_DIR = Path(os.environ.get(
    "SOVEREIGN_OS_BUILD_STATE_DIR",
    Path(tempfile.gettempdir()) / f"sovereign-os-build-{os.getuid()}"))
_RUN_LOG = _RUN_STATE_DIR / "run.log"
_RUN_STATUS = _RUN_STATE_DIR / "run.json"
_RUN_START_LOCK = threading.Lock()   # serialise STARTS (one run at a time)


def _run_status_read() -> dict:
    try:
        return json.loads(_RUN_STATUS.read_text())
    except (OSError, ValueError):
        return {}


def _run_status_write(d: dict) -> None:
    try:
        _RUN_STATE_DIR.mkdir(parents=True, exist_ok=True)
        _RUN_STATUS.write_text(json.dumps(d))
    except OSError:
        pass


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def _run_active() -> bool:
    st = _run_status_read()
    pid = st.get("pid")
    return bool(st and not st.get("done") and pid and _pid_alive(int(pid)))


def _run_waiter(proc, action: str) -> None:
    """Background waiter — outlives the request. Appends the exit footer to the
    log + marks the status done. Daemon thread, one per started run."""
    rc = proc.wait()
    try:
        with open(_RUN_LOG, "ab", buffering=0) as f:
            f.write(f"\n{'✓' if rc == 0 else '✗'} exit code {rc}\n".encode())
    except OSError:
        pass
    st = _run_status_read()
    st.update(done=True, exit_code=rc)
    _run_status_write(st)

# Operator MOK keys (SDD-015: keys live on the host, NEVER in the repo).
# The signed-posture build needs them in the env; the first Run-console
# build died at step 05 because only the terminal invocation ever passed
# them (caught 2026-06-12). Auto-inject from the canonical path when the
# operator hasn't set them explicitly.
OPERATOR_KEY_DIR = Path("/etc/sovereign-os/keys")


def operator_key_env() -> dict[str, str]:
    if "SOVEREIGN_OS_MOK_KEY" in os.environ or "SOVEREIGN_OS_PK_KEY" in os.environ:
        return {}
    key, crt = OPERATOR_KEY_DIR / "mok.key", OPERATOR_KEY_DIR / "mok.crt"
    if key.is_file() and crt.is_file():
        return {"SOVEREIGN_OS_MOK_KEY": str(key),
                "SOVEREIGN_OS_MOK_CERT": str(crt)}
    return {}
ANSI_RE = re.compile(rb"\x1b\[[0-9;]*[A-Za-z]")

# ── dev gateway: /api/<prefix>/ → local service port. Ports mirror the
#    Environment=*_PORT lines in systemd/system/sovereign-*-api.service;
#    services serve their full /api/... paths, so forwarding is verbatim.
#    sovereign-gatewayd (Rust, port 8000) replaces this in production. ──
DEV_GATEWAY_ROUTES = {
    "/api/m060/": 8160,            # sovereign-m060-health-api
    "/api/ms022/": 7711,           # sovereign-ms022-sse-quota-api
    "/api/four-watchdog/": 7712,   # sovereign-four-watchdog-api
    "/api/node-exporter/": 9100,   # node_exporter (path rewritten below)
}
# Exact paths the master-dashboard expects on ITS origin (it is designed
# to be served by master-dashboard-api at :8090). NOTE: this deliberately
# shadows this server's own /version — the cockpit's registry identity
# wins; use /healthz for this server's liveness.
DEV_GATEWAY_EXACT = {
    "/routes": 8090, "/collisions": 8090, "/discover": 8090,
    "/toggles": 8090, "/health": 8090, "/version": 8090,
    "/metrics": 9100,              # node_exporter direct fallback
}


def assemble_data() -> dict:
    profiles = [
        {"id": pid, "name": name, "default": is_def, "desc": desc}
        for (pid, name, is_def, desc) in PROFILE_META
    ]
    detail = {}
    for pid, *_ in PROFILE_META:
        doc = _load_yaml(PROFILES_DIR / f"{pid}.yaml")
        d = _profile_detail(doc) if doc else None
        if d:
            detail[pid] = d
    out = {"profiles": profiles, "detail": detail, "tools": _deps_tools()}
    hw = _hw_section()
    if hw:
        out["hw"] = hw
    tuning = _tuning_section()
    if tuning:
        out["tuning"] = tuning
    return out


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):  # quiet; loopback read-only daemon
        pass

    def do_GET(self):
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        if path == "/healthz":
            return self._send(200, json.dumps({"ok": True}))
        # Background-run status + re-attach (survive page navigation). Suffix-
        # matched so they work whether served at / or /build-configurator/.
        if path.endswith("/api/run/status"):
            st = _run_status_read()
            active = _run_active()
            try:
                size = _RUN_LOG.stat().st_size
            except OSError:
                size = 0
            return self._send(200, json.dumps({
                "running": active, "action": st.get("action"),
                "profile": st.get("profile"), "started_at": st.get("started_at"),
                "done": st.get("done", not active), "exit_code": st.get("exit_code"),
                "log_bytes": size,
            }))
        if path.endswith("/api/run/attach"):
            return self._stream_log(0)
        # Gateway routes come BEFORE this server's own /version — the
        # cockpit's registry identity deliberately shadows it (use
        # /healthz for this server's liveness).
        for prefix, port in DEV_GATEWAY_ROUTES.items():
            if path.startswith(prefix):
                return self._proxy(port, path)
        if path in DEV_GATEWAY_EXACT:
            return self._proxy(DEV_GATEWAY_EXACT[path], path)
        if path == "/version":
            return self._send(200, json.dumps(
                {"module": "build-configurator-api", "version": VERSION}))
        if path in ("/data.json", "/data"):
            return self._send(200, json.dumps(assemble_data(), indent=2))
        if path in ("/host.json", "/host"):
            return self._send(200, json.dumps(assemble_host(), indent=2))
        if path == "/panels.json":
            return self._send(200, json.dumps(list_panels(), indent=2))
        if path in ("/catalog.json", "/catalog"):
            cat = _load_catalog()
            return self._send(200, json.dumps(cat or {"error": "catalog absent"}, indent=2))
        if path in ("/control-systems.json", "/control-systems"):
            cs = _load_control_systems()
            return self._send(200, json.dumps(cs or {"error": "control-systems absent"}, indent=2))
        if path in ("/feature-coverage.json", "/feature-coverage"):
            fc = _load_feature_coverage()
            return self._send(200, json.dumps(fc or {"error": "feature-coverage absent"}, indent=2))
        if path in ("/models-catalog.json",):
            mc = _load_models_catalog()
            return self._send(200, json.dumps(mc or {"error": "models catalog absent"}, indent=2))
        if path in ("/cpu-avx.json",):
            return self._send(200, json.dumps(_load_cpu_avx(), indent=2))
        if path in ("/orchestration.json",):
            return self._send(200, json.dumps(_load_orchestration(), indent=2))
        if path in ("/profile-generation.json",):
            return self._send(200, json.dumps(_load_profile_generation(), indent=2))
        if path in ("/selfdef-management.json",):
            return self._send(200, json.dumps(_load_selfdef(), indent=2))
        if path == "/panels":
            return self._send(200, panels_index_html(), "text/html; charset=utf-8")
        if path == "/":
            if WEBAPP.exists():
                return self._send(200, WEBAPP.read_bytes(), "text/html; charset=utf-8")
            return self._send(404, json.dumps({"error": "webapp not found"}))
        # Static sibling panels: /<panel>/ → webapp/<panel>/index.html.
        # resolve() + relative_to guard keeps every read inside webapp/.
        try:
            target = (WEBAPP_ROOT / path.lstrip("/")).resolve()
            target.relative_to(WEBAPP_ROOT.resolve())
        except (ValueError, OSError):
            return self._send(404, json.dumps({"error": "not found", "path": path}))
        if target.is_dir():
            target = target / "index.html"
        if target.is_file():
            ctype = STATIC_TYPES.get(target.suffix.lower())
            if ctype:
                return self._send(200, target.read_bytes(), ctype)
        return self._send(404, json.dumps({"error": "not found", "path": path}))

    def _proxy(self, port: int, path: str):
        """Forward a GET to the local backing API verbatim (node_exporter
        is the one path-rewrite: /api/node-exporter/X → /X)."""
        import urllib.error
        import urllib.request
        if path.startswith("/api/node-exporter/"):
            path = path[len("/api/node-exporter"):]
        url = f"http://127.0.0.1:{port}{path}"
        try:
            with urllib.request.urlopen(url, timeout=5) as r:
                self._send(r.status, r.read(),
                           r.headers.get("Content-Type", "application/json"))
        except (urllib.error.URLError, OSError) as e:
            self._send(502, json.dumps({
                "error": f"backing API on :{port} not reachable",
                "detail": str(e),
                "hint": "make panel starts the dashboard tile APIs; "
                        "panels fall back to baked snapshots on 502",
            }))

    def _read_json_body(self) -> dict | None:
        try:
            n = int(self.headers.get("Content-Length", "0"))
            return json.loads(self.rfile.read(n) or b"{}")
        except (ValueError, OSError):
            return None

    def do_POST(self):
        path = self.path.split("?", 1)[0].rstrip("/")
        # The hub serves this page at BOTH / and /build-configurator/ (as a
        # sibling panel), so the Run console's relative POST can arrive prefixed
        # (/build-configurator/api/run). Match the endpoint by SUFFIX so it
        # routes identically from either path (and survives a stale cached page).
        if path.endswith("/api/cancel"):
            st = _run_status_read()
            pid = st.get("pid")
            if pid and _run_active():
                try:
                    os.killpg(os.getpgid(int(pid)), 15)
                except (OSError, ProcessLookupError):
                    pass
                return self._send(200, json.dumps({"cancelled": st.get("action")}))
            return self._send(200, json.dumps({"cancelled": None}))
        if path.endswith("/api/run"):
            return self._run_action()
        return self._send(404, json.dumps({"error": "not found", "path": path}))

    def _run_action(self):
        body = self._read_json_body()
        if body is None:
            return self._send(400, json.dumps({"error": "bad JSON body"}))
        action = body.get("action")
        profile = body.get("profile", "sain-01")
        if action not in RUN_ACTIONS:
            return self._send(400, json.dumps(
                {"error": f"unknown action {action!r}",
                 "allowed": sorted(RUN_ACTIONS)}))
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", profile or "") \
                or not (PROFILES_DIR / f"{profile}.yaml").is_file():
            return self._send(400, json.dumps({"error": f"unknown profile {profile!r}"}))
        snapshot = body.get("snapshot") or ""
        if snapshot and not re.fullmatch(r"\d{8}T\d{6}Z", snapshot):
            return self._send(400, json.dumps(
                {"error": f"bad snapshot {snapshot!r} (want YYYYMMDDTHHMMSSZ)"}))
        # SDD "ready after flash" bake knobs — the page can request a
        # self-contained image (dev tools + selfdef baked in). Only apply
        # to the real build (dry-run/preflight don't emit the image).
        bake_env: dict[str, str] = {}
        if action == "build":
            if body.get("bake_dev"):
                bake_env["SOVEREIGN_OS_BAKE_DEV_TOOLS"] = "1"
            if body.get("bake_selfdef"):
                bake_env["SOVEREIGN_OS_BAKE_SELFDEF"] = "1"
            # "UPS + graceful shutdown" defaults ON; unchecking forces it off
            # for this build (mkosi-emit honors SOVEREIGN_OS_POWER_FEATURE=0).
            if body.get("graceful_shutdown") is False:
                bake_env["SOVEREIGN_OS_POWER_FEATURE"] = "0"
            # SDD-709 agent layer — the page can bake the agent runtimes in and
            # pick the default frontend. Tri-state: present+true forces the bake
            # ON, present+false forces it OFF, absent inherits the profile.
            # mkosi-emit honors SOVEREIGN_OS_BAKE_OPENCLAW / _OPEN_COMPUTER ("1"/"0").
            if "bake_openclaw" in body:
                bake_env["SOVEREIGN_OS_BAKE_OPENCLAW"] = "1" if body.get("bake_openclaw") else "0"
            if "bake_open_computer" in body:
                bake_env["SOVEREIGN_OS_BAKE_OPEN_COMPUTER"] = "1" if body.get("bake_open_computer") else "0"
            frontend = body.get("frontend") or ""
            if frontend:
                if frontend not in FRONTEND_CHOICES:
                    return self._send(400, json.dumps(
                        {"error": f"unknown frontend {frontend!r}",
                         "allowed": sorted(FRONTEND_CHOICES)}))
                bake_env["SOVEREIGN_OS_FRONTEND"] = frontend
        argv_fn, needs_root = RUN_ACTIONS[action]
        argv = argv_fn()
        elevation_note = ""
        if needs_root and os.geteuid() != 0:
            pkexec = shutil.which("pkexec")
            if not pkexec:
                return self._send(403, json.dumps({
                    "error": "a real build needs root and pkexec is unavailable",
                    "fix": "stop this panel, then:  sudo -E scripts/operator/panel.sh "
                           "— the BUILD button works when the server runs as root. "
                           "dry-run + preflight work right now without it.",
                }))
            # GUI session: polkit pops the system password dialog on the
            # operator's desktop; the build then runs as root. pkexec
            # sanitizes env, so re-inject what orchestrate.sh needs.
            argv = [pkexec, "env",
                    f"SOVEREIGN_OS_PROFILE={profile}",
                    f"PATH={os.environ.get('PATH', '/usr/sbin:/usr/bin:/sbin:/bin')}",
                    *([f"DEBIAN_SNAPSHOT={snapshot}"] if snapshot else []),
                    *[f"{k}={v}" for k, v in bake_env.items()],
                    *[f"{k}={v}" for k, v in operator_key_env().items()],
                    str(REPO / argv[0]), *argv[1:]]
            elevation_note = ("  (look for the system password prompt on "
                              "your desktop — polkit/pkexec)\n")
        # One run at a time — but the run now OUTLIVES this request: it streams to
        # a state file (see _run_waiter), so a client navigating away never kills
        # it. Serialise only the START; then stream this client from the top.
        with _RUN_START_LOCK:
            if _run_active():
                return self._send(409, json.dumps(
                    {"error": "a run is already in progress",
                     "action": _run_status_read().get("action")}))
            key_note = ("  signing: operator MOK auto-injected from "
                        f"{OPERATOR_KEY_DIR}\n" if operator_key_env() else "")
            try:
                _RUN_STATE_DIR.mkdir(parents=True, exist_ok=True)
                logf = open(_RUN_LOG, "wb", buffering=0)
            except OSError as e:
                return self._send(500, json.dumps({"error": f"cannot open run log: {e}"}))
            logf.write(f"▶ {action} · profile {profile}\n{elevation_note}{key_note}\n".encode())
            env = dict(os.environ, SOVEREIGN_OS_PROFILE=profile,
                       **operator_key_env(), **bake_env)
            if snapshot:
                env["DEBIAN_SNAPSHOT"] = snapshot
            try:
                # stdout → the log FILE (not a pipe): the child keeps writing even
                # if this daemon or the client goes away — the run is detached.
                proc = subprocess.Popen(
                    argv, cwd=REPO, env=env, stdout=logf,
                    stderr=subprocess.STDOUT, start_new_session=True)
            except OSError as e:
                logf.close()
                return self._send(500, json.dumps(
                    {"error": f"failed to start {action}: {e}"}))
            logf.close()   # the child holds its own dup'd fd now
            _run_status_write({"pid": proc.pid, "action": action, "profile": profile,
                               "started_at": int(time.time()), "done": False})
            threading.Thread(target=_run_waiter, args=(proc, action),
                             daemon=True).start()
        # Stream from the top; a disconnect just DETACHES — the run lives on and
        # the operator re-attaches from any page via /api/run/attach.
        self._stream_log(0)

    def _stream_log(self, from_offset: int):
        """Replay _RUN_LOG from `from_offset`, then follow it live until the run
        finishes. Read-only tail — a client disconnect just ends THIS stream and
        never touches the run. Shared by POST /api/run + GET /api/run/attach."""
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        try:
            with open(_RUN_LOG, "rb") as f:
                f.seek(max(0, from_offset))
                dead_since = None
                while True:
                    chunk = f.read(65536)
                    if chunk:
                        self.wfile.write(ANSI_RE.sub(b"", chunk))
                        self.wfile.flush()
                        dead_since = None
                        continue
                    st = _run_status_read()
                    if st.get("done"):
                        tail = f.read()          # footer written before done=True
                        if tail:
                            self.wfile.write(ANSI_RE.sub(b"", tail))
                            self.wfile.flush()
                        break
                    if not _run_active():
                        # pid gone but not marked done — the waiter may be mid-write
                        # (short race) or was lost to a daemon restart (orphan).
                        if dead_since is None:
                            dead_since = time.time()
                        elif time.time() - dead_since > 3.0:
                            self.wfile.write(b"\n(run ended)\n")
                            self.wfile.flush()
                            break
                    else:
                        dead_since = None
                    time.sleep(0.3)
        except FileNotFoundError:
            try:
                self.wfile.write(b"(no run in progress)\n")
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass  # client detached — the run + its waiter continue unaffected


def main():
    if DRY_RUN:
        print(json.dumps(assemble_data(), indent=2))
        return
    httpd = ThreadingHTTPServer((API_BIND, API_PORT), Handler)
    root = " · running as ROOT (BUILD button armed)" if os.geteuid() == 0 else ""
    print(f"build-configurator-api on http://{API_BIND}:{API_PORT}/ "
          f"(webapp at /, panels at /panels/, data at /data.json, "
          f"run console at POST /api/run){root} — Ctrl-C to stop",
          file=sys.stderr)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
