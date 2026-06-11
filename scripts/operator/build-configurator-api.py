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
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

API_BIND = os.environ.get("BUILD_CONFIGURATOR_API_BIND", "127.0.0.1")
API_PORT = int(os.environ.get("BUILD_CONFIGURATOR_API_PORT", "8100"))
DRY_RUN = bool(os.environ.get("BUILD_CONFIGURATOR_DRY_RUN"))
VERSION = "0.1.0"

REPO = Path(__file__).resolve().parents[2]
PROFILES_DIR = REPO / "profiles"
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
    ("old-workstation", "old-workstation", False, "constrained dev box (single 3090, ext4)."),
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


def panels_index_html() -> str:
    """Generated index page for /panels/ — every panel, honestly labeled."""
    rows = "\n".join(
        f'<li><a href="{p["path"]}">{html_mod.escape(p["id"])}</a>'
        f'<span class="t">{html_mod.escape(p["title"])}</span></li>'
        for p in list_panels()
    )
    n = len(list_panels())
    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>sovereign-os · panel index</title>
<style>
 body{{font:14px/1.5 system-ui,sans-serif;background:#10131a;color:#cdd3e0;max-width:780px;margin:2rem auto;padding:0 1rem}}
 h1{{font-size:1.2rem}} a{{color:#7fb3ff;text-decoration:none}} a:hover{{text-decoration:underline}}
 li{{margin:.25rem 0;list-style:none}} .t{{color:#7d8597;margin-left:.8rem;font-size:.85em}}
 .note{{background:#1a2030;border:1px solid #2a3350;border-radius:6px;padding:.7rem .9rem;margin:1rem 0}}
 ul{{padding:0}}
</style></head><body>
<h1>sovereign-os · all {n} panels</h1>
<div class="note">Served statically from <code>webapp/</code>. Panels are
seeded with baked snapshots; ones backed by a <code>sovereign-*-api</code>
service show LIVE data only once that service is installed and running
(<code>docs/src/ops/run-on-host.md</code> § 2 — same flow as the hook
timers). The <a href="/">build configurator</a> and its
<a href="/host.json">host probe</a> are live right now.</div>
<ul>{rows}</ul>
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
RUN_LOCK = threading.Lock()
CURRENT_JOB: dict = {"proc": None, "action": None}

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
        if path == "/api/cancel":
            proc = CURRENT_JOB.get("proc")
            if proc and proc.poll() is None:
                try:
                    os.killpg(os.getpgid(proc.pid), 15)
                except (OSError, ProcessLookupError):
                    pass
                return self._send(200, json.dumps(
                    {"cancelled": CURRENT_JOB.get("action")}))
            return self._send(200, json.dumps({"cancelled": None}))
        if path == "/api/run":
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
                    *[f"{k}={v}" for k, v in operator_key_env().items()],
                    str(REPO / argv[0]), *argv[1:]]
            elevation_note = ("  (look for the system password prompt on "
                              "your desktop — polkit/pkexec)\n")
        if not RUN_LOCK.acquire(blocking=False):
            return self._send(409, json.dumps(
                {"error": f"a job is already running: {CURRENT_JOB.get('action')}"}))
        try:
            env = dict(os.environ, SOVEREIGN_OS_PROFILE=profile,
                       **operator_key_env())
            proc = subprocess.Popen(
                argv, cwd=REPO, env=env, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, start_new_session=True,
            )
            CURRENT_JOB.update(proc=proc, action=action)
            # Stream: HTTP/1.0-style close-delimited plain text, line-buffered.
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
            key_note = ("  signing: operator MOK auto-injected from "
                        f"{OPERATOR_KEY_DIR}\n" if operator_key_env() else "")
            self.wfile.write(
                f"▶ {action} · profile {profile} · pid {proc.pid}\n"
                f"{elevation_note}{key_note}\n".encode())
            self.wfile.flush()
            try:
                for raw in proc.stdout:
                    self.wfile.write(ANSI_RE.sub(b"", raw))
                    self.wfile.flush()
                rc = proc.wait()
                self.wfile.write(
                    f"\n{'✓' if rc == 0 else '✗'} exit code {rc}\n".encode())
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                # client went away — stop the job rather than orphan it
                if proc.poll() is None:
                    try:
                        os.killpg(os.getpgid(proc.pid), 15)
                    except (OSError, ProcessLookupError):
                        pass
        finally:
            CURRENT_JOB.update(proc=None, action=None)
            RUN_LOCK.release()


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
