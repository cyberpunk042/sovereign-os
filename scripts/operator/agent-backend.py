#!/usr/bin/env python3
"""scripts/operator/agent-backend.py — hotswap an agent runtime's model backend
between the LOCAL sovereign model and the hosted Claude/Anthropic API (SDD-707).

Operator directive 2026-07-14 (verbatim): *"there should be a hotswap for [the]
anthropic local ai API vs the claude ai anthropic API for both. and it should be
clear and easy how to swap this"*.

Two runtimes, one swap model:
  * OpenClaw (native Anthropic) — config `~/.openclaw/openclaw.json` (JSON5) carries TWO
    coexisting providers: `local` (api=anthropic-messages → the on-box safety-spine
    gateway at :8787) and `anthropic` (the built-in https://api.anthropic.com). Swapping
    just flips `agents.defaults.model.primary` between `local/<model>` and
    `anthropic/<model>`.
  * open-computer (OpenAI-format only) — env `OPENAI_BASE_URL`/`OPENAI_MODEL`/
    `OPENAI_API_KEY`. Swapping flips those between the local gateway shim (:8787/v1) and
    Anthropic's OpenAI-compat endpoint (https://api.anthropic.com/v1/).

The cloud key is NEVER baked: `backend anthropic` reads ANTHROPIC_API_KEY from a root-only
`/etc/sovereign-os/anthropic-key.env` (set it with `--key`, or drop it there yourself);
`backend anthropic` warns if it's absent. The local side uses a non-secret placeholder.

Sovereignty: stdlib-only. This is the single renderer of both runtimes' config — the
install hooks `provision` it, the `sovereign-osctl <rt> backend` verb swaps it.
SOVEREIGN_OS_BACKEND_DRYRUN=1 prints the plan (no systemctl / real writes go to tmp via
the env-overridable paths) for the contract lint + rehearsal.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

RUNTIMES = ("openclaw", "open-computer")
BACKENDS = ("local", "anthropic")
UNIT = {"openclaw": "sovereign-openclaw.service", "open-computer": "sovereign-open-computer.service"}

DRYRUN = os.environ.get("SOVEREIGN_OS_BACKEND_DRYRUN") == "1"
ETC = Path(os.environ.get("SOVEREIGN_OS_ETC", "/etc/sovereign-os"))
KEY_FILE = Path(os.environ.get("SOVEREIGN_OS_ANTHROPIC_KEY_ENV", str(ETC / "anthropic-key.env")))
OPENCLAW_HOME = Path(os.environ.get("SOVEREIGN_OS_OPENCLAW_HOME", "/var/lib/sovereign-os/openclaw"))
OC_ROOT = Path(os.environ.get("SOVEREIGN_OS_OPEN_COMPUTER_ROOT", "/var/lib/sovereign-os/open-computer"))
OC_ENV = Path(os.environ.get("SOVEREIGN_OS_OPEN_COMPUTER_ENV", str(ETC / "open-computer.env")))


def _desc_path(runtime: str) -> Path:
    return ETC / f"{runtime}-backends.json"


def _load_desc(runtime: str) -> dict[str, Any]:
    p = _desc_path(runtime)
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_desc(runtime: str, d: dict[str, Any]) -> None:
    p = _desc_path(runtime)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, indent=2) + "\n", encoding="utf-8")


def _anthropic_key() -> str:
    if not KEY_FILE.is_file():
        return ""
    try:
        for line in KEY_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("ANTHROPIC_API_KEY="):
                return line.split("=", 1)[1].strip()
    except OSError:
        pass
    return ""


def _write_key(key: str) -> None:
    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    body = (
        "# /etc/sovereign-os/anthropic-key.env — hosted Claude API key (SDD-707).\n"
        "# Root-only (0600). Injected into the agent runtimes when backend=anthropic.\n"
        f"ANTHROPIC_API_KEY={key}\n"
    )
    KEY_FILE.write_text(body, encoding="utf-8")
    try:
        os.chmod(KEY_FILE, 0o600)
    except OSError:
        pass


def _restart_if_active(runtime: str) -> None:
    unit = UNIT[runtime]
    if DRYRUN or not shutil.which("systemctl"):
        print(f"  [dry-run] systemctl try-restart {unit}", file=sys.stderr)
        return
    try:
        # try-restart: restart only if it's currently running (a swap while off just
        # updates the config, which the runtime reads on next start).
        subprocess.run(["systemctl", "try-restart", unit], capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        pass


# ---------- renderers (the single source of each runtime's config) ----------

def render_openclaw(desc: dict[str, Any]) -> str:
    """Write ~/.openclaw/openclaw.json (JSON5) with BOTH providers; primary per backend."""
    backend = desc.get("backend", "local")
    local = desc.get("local", {})
    anth = desc.get("anthropic", {})
    port = desc.get("gateway_port", 18789)
    lm = local.get("model", "local-oracle")
    am = anth.get("model", "claude-sonnet-4-6")
    primary = f"local/{lm}" if backend == "local" else f"anthropic/{am}"
    cfg = f"""{{
  // sovereign-os SDD-707 — two coexisting providers; hotswap flips the primary.
  // local  = the on-box safety-spine gateway (Anthropic Messages API).
  // anthropic = hosted Claude (real ANTHROPIC_API_KEY, operator-supplied, never baked).
  models: {{
    mode: "merge",
    providers: {{
      local: {{
        baseUrl: "{local.get('endpoint', 'http://127.0.0.1:8787')}",
        api: "anthropic-messages",
        apiKey: "sovereign-local",
        models: [{{ id: "{lm}", name: "Local (sovereign)", contextWindow: 128000 }}],
      }},
      anthropic: {{
        baseUrl: "{anth.get('endpoint', 'https://api.anthropic.com')}",
        api: "anthropic-messages",
        apiKey: "${{ANTHROPIC_API_KEY}}",
        models: [{{ id: "{am}", name: "Cloud Claude" }}],
      }},
    }},
  }},
  agents: {{ defaults: {{ model: {{ primary: "{primary}" }}, models: {{ "local/*": {{}}, "anthropic/*": {{}} }} }} }},
  gateway: {{ mode: "local", bind: "loopback", port: {port} }},
}}
"""
    dst = OPENCLAW_HOME / ".openclaw" / "openclaw.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(cfg, encoding="utf-8")
    return str(dst)


def render_open_computer(desc: dict[str, Any]) -> str:
    """Write /etc/sovereign-os/open-computer.env with the active backend's OpenAI env."""
    backend = desc.get("backend", "local")
    sel = desc.get(backend, {})
    key = _anthropic_key() if backend == "anthropic" else ""
    port = desc.get("web_port", 9800)
    env = (
        f"# /etc/sovereign-os/open-computer.env — open-computer LLM backend (SDD-707). backend={backend}.\n"
        f"# Rewritten by `sovereign-osctl open-computer backend`. 127.0.0.1 is auto-rewritten to\n"
        f"# the QEMU host gateway 10.0.2.2 for the guest.\n"
        f"HOME={OC_ROOT}\n"
        f"OPENAI_BASE_URL={sel.get('endpoint', 'http://127.0.0.1:8787/v1')}\n"
        f"OPENAI_MODEL={sel.get('model', 'local-oracle')}\n"
        f"OPENAI_API_KEY={key}\n"
        f"PORT={port}\n"
        f"OPEN_COMPUTER_BASE_DIR={OC_ROOT}/base_image\n"
        f"OPEN_COMPUTER_AGENTS_DIR={OC_ROOT}/agents\n"
    )
    OC_ENV.parent.mkdir(parents=True, exist_ok=True)
    OC_ENV.write_text(env, encoding="utf-8")
    return str(OC_ENV)


def _render(runtime: str, desc: dict[str, Any]) -> str:
    return render_openclaw(desc) if runtime == "openclaw" else render_open_computer(desc)


# ---------- operations ----------

def provision(runtime: str, args: argparse.Namespace) -> dict[str, Any]:
    """Called by the install hook: persist the backend descriptor + render the config."""
    desc = {
        "backend": args.backend,
        "local": {"endpoint": args.local_endpoint, "model": args.local_model},
        "anthropic": {"endpoint": args.anthropic_endpoint, "model": args.anthropic_model},
    }
    if args.gateway_port is not None:
        desc["gateway_port"] = args.gateway_port
    if args.web_port is not None:
        desc["web_port"] = args.web_port
    _save_desc(runtime, desc)
    path = _render(runtime, desc)
    return {"ok": True, "runtime": runtime, "backend": args.backend, "config": path}


def swap(runtime: str, backend: str, key: str | None) -> dict[str, Any]:
    if key:
        _write_key(key)
    desc = _load_desc(runtime)
    if not desc:
        return {"ok": False, "error": f"{runtime} not provisioned — run: sovereign-osctl {runtime} install"}
    desc["backend"] = backend
    _save_desc(runtime, desc)
    path = _render(runtime, desc)
    notes: list[str] = []
    if backend == "anthropic" and not _anthropic_key():
        notes.append(f"no ANTHROPIC_API_KEY set — provide it: sovereign-osctl {runtime} backend anthropic --key <k> "
                     f"(or edit {KEY_FILE}). Cloud calls will 401 until then.")
    _restart_if_active(runtime)
    return {"ok": True, "runtime": runtime, "backend": backend, "config": path, "notes": notes}


def show(runtime: str) -> dict[str, Any]:
    desc = _load_desc(runtime)
    backend = desc.get("backend", "unknown")
    sel = desc.get(backend, {}) if backend in BACKENDS else {}
    return {
        "runtime": runtime,
        "backend": backend,
        "endpoint": sel.get("endpoint", ""),
        "model": sel.get("model", ""),
        "anthropic_key_present": bool(_anthropic_key()),
        "provisioned": bool(desc),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="agent-runtime model-backend hotswap (SDD-707)")
    p.add_argument("runtime", choices=RUNTIMES)
    sub = p.add_subparsers(dest="cmd")

    sp = sub.add_parser("provision", help="(install hook) persist descriptor + render config")
    sp.add_argument("--backend", choices=BACKENDS, default="local")
    sp.add_argument("--local-endpoint", required=True)
    sp.add_argument("--local-model", required=True)
    sp.add_argument("--anthropic-endpoint", required=True)
    sp.add_argument("--anthropic-model", required=True)
    sp.add_argument("--gateway-port", type=int, default=None)
    sp.add_argument("--web-port", type=int, default=None)

    for b in BACKENDS:
        spb = sub.add_parser(b, help=f"swap to the {b} backend")
        spb.add_argument("--key", default=None, help="(anthropic) set ANTHROPIC_API_KEY")
        spb.add_argument("--json", action="store_true")
    sp_show = sub.add_parser("show", help="print the active backend")
    sp_show.add_argument("--json", action="store_true")

    args = p.parse_args(argv)
    cmd = args.cmd or "show"

    if cmd == "provision":
        r = provision(args.runtime, args)
        print(json.dumps(r, indent=2))
        return 0 if r.get("ok") else 2
    if cmd in BACKENDS:
        r = swap(args.runtime, cmd, getattr(args, "key", None))
        if getattr(args, "json", False):
            print(json.dumps(r, indent=2))
        elif r.get("ok"):
            print(f"{args.runtime} backend → {cmd}" + (" (dry-run)" if DRYRUN else ""))
            for n in r.get("notes", []):
                print(f"  · {n}")
        else:
            print(f"error: {r.get('error')}", file=sys.stderr)
        return 0 if r.get("ok") else 2
    # show
    s = show(args.runtime)
    if getattr(args, "json", False):
        print(json.dumps(s, indent=2))
    else:
        print(f"{s['runtime']} backend: {s['backend']}")
        print(f"  endpoint: {s['endpoint'] or '(unprovisioned)'}")
        print(f"  model:    {s['model'] or '(unset)'}")
        print(f"  cloud key: {'present' if s['anthropic_key_present'] else 'absent'}")
        print(f"  swap: sovereign-osctl {s['runtime']} backend {{local|anthropic}}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
