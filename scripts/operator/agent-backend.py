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
import pwd
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

RUNTIMES = ("openclaw", "open-computer", "claude-code", "vscode")
BACKENDS = ("local", "anthropic")
# Only service-backed runtimes have a unit to restart on swap. Claude Code (a
# CLI) and VSCode (an editor extension) read their config on next launch — no
# unit to bounce (SDD-600 Part 2).
UNIT = {"openclaw": "sovereign-openclaw.service", "open-computer": "sovereign-open-computer.service"}

DRYRUN = os.environ.get("SOVEREIGN_OS_BACKEND_DRYRUN") == "1"
ETC = Path(os.environ.get("SOVEREIGN_OS_ETC", "/etc/sovereign-os"))
KEY_FILE = Path(os.environ.get("SOVEREIGN_OS_ANTHROPIC_KEY_ENV", str(ETC / "anthropic-key.env")))
OPENCLAW_HOME_DEFAULT = Path("/var/lib/sovereign-os/openclaw")


def _openclaw_home() -> Path:
    """Where OpenClaw ACTUALLY reads its config.

    The default assumed a managed install under /var/lib/sovereign-os/openclaw.
    A real box does not necessarily have one: OpenClaw is an `npm install -g`
    that its own `onboard` wizard configures, and on this machine that put the
    config in the operator's home while /var/lib/sovereign-os/openclaw does not
    exist at all. Writing the managed path would have produced a perfectly
    correct config that nothing reads — a swap that appears to work and changes
    nothing, which is worse than one that fails.

    So: an explicit override wins, otherwise PREFER A CONFIG THAT EXISTS. Only
    when none is found does this fall back to the managed path (a fresh box,
    where creating it there is right).
    """
    env = os.environ.get("SOVEREIGN_OS_OPENCLAW_HOME")
    if env:
        return Path(env)
    candidates = [OPENCLAW_HOME_DEFAULT]
    # The invoking operator, sudo-aware — `sudo sovereign-osctl` must still find
    # the config of the human who ran it, not root's.
    for name in (os.environ.get("SUDO_USER"), os.environ.get("USER")):
        if not name:
            continue
        try:
            candidates.append(Path(pwd.getpwnam(name).pw_dir))
        except KeyError:
            pass
    try:
        candidates.append(Path.home())
    except RuntimeError:
        pass
    for c in candidates:
        if (c / ".openclaw" / "openclaw.json").is_file():
            return c
    return OPENCLAW_HOME_DEFAULT


OPENCLAW_HOME = _openclaw_home()
OC_ROOT = Path(os.environ.get("SOVEREIGN_OS_OPEN_COMPUTER_ROOT", "/var/lib/sovereign-os/open-computer"))
OC_ENV = Path(os.environ.get("SOVEREIGN_OS_OPEN_COMPUTER_ENV", str(ETC / "open-computer.env")))
# Claude Code reads ANTHROPIC_BASE_URL/ANTHROPIC_API_KEY from the environment;
# we render a managed env file the operator sources (or the launcher unit reads).
CC_ENV = Path(os.environ.get("SOVEREIGN_OS_CLAUDE_CODE_ENV", str(ETC / "claude-code.env")))
# VSCode's Cline / Claude Dev extension is configured in the user's VSCode
# settings — we can't reach into a live editor profile, so we render the exact
# settings fragment to apply (honest-degrade: the swap flips the Base URL here).
VSCODE_CFG = Path(os.environ.get("SOVEREIGN_OS_VSCODE_CLINE_JSON", str(ETC / "vscode-cline-settings.json")))


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
    """Cache the descriptor under /etc. BEST EFFORT.

    This is a convenience record of what was last provisioned; the artifact that
    matters is the runtime's own config. It lives under /etc, so a non-root
    operator cannot write it — and because the save ran BEFORE the render, an
    unwritable cache aborted the whole swap with a PermissionError traceback,
    leaving the config untouched. Failing the work because the note about the
    work could not be filed is the wrong order of priorities.

    A failure warns and continues; the render is what the operator asked for.
    """
    p = _desc_path(runtime)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(d, indent=2) + "\n", encoding="utf-8")
    except OSError as e:
        sys.stderr.write(
            f"[warn] could not record the backend descriptor at {p}: {e}\n"
            f"[warn] the swap itself still applied; re-run as root to persist it\n"
        )


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
    unit = UNIT.get(runtime)
    if unit is None:
        # Claude Code / VSCode have no service to bounce — config is read on
        # the tool's next launch.
        return
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

def _load_openclaw_config(path: Path) -> tuple[dict[str, Any], str | None]:
    """Parse an existing openclaw.json, tolerating the JSON5 the old renderer wrote.

    Returns `(config, warning)`. A file that cannot be parsed at all is BACKED UP
    and reported — never silently discarded, because it holds the gateway auth
    token and the operator's channel setup.
    """
    if not path.is_file():
        return {}, None
    raw = path.read_text(encoding="utf-8")
    try:
        return json.loads(raw), None
    except json.JSONDecodeError:
        pass
    # JSON5-lite: strip // line comments and trailing commas. Enough for the
    # shape the previous renderer emitted; not a general JSON5 parser.
    stripped = re.sub(r"(?m)^\s*//.*$", "", raw)
    stripped = re.sub(r",(\s*[}\]])", r"\1", stripped)
    try:
        return json.loads(stripped), None
    except json.JSONDecodeError as e:
        bak = path.with_suffix(".json.unparseable")
        try:
            bak.write_text(raw, encoding="utf-8")
        except OSError:
            pass
        return {}, f"could not parse {path} ({e}); previous contents saved to {bak}"


def render_openclaw(desc: dict[str, Any]) -> str:
    """MERGE the two providers into ~/.openclaw/openclaw.json — never template over it.

    SDD-707 always specified two coexisting providers with the hotswap flipping
    the primary. The implementation wrote the whole file from a template, which
    on a live box would have destroyed:

      * `models.providers.sovereign` and its per-tier models — the entries
        scripts/inference/sync-openclaw-models.py rewrites on every
        `trinity profile switch`, so the D-21 profile mirroring would have
        stopped working;
      * `gateway.auth.token` — the credential the Control UI authenticates with;
      * `session`, `tools`, `wizard` and any channel the operator had onboarded.

    Worse than the loss: sync-openclaw-models.py looks up
    `models.providers.sovereign.models`, would not find it, and logs
    "skipping (ok)". The breakage would have been silent and permanent.

    So this merges. It also uses the provider name the rest of the system
    already uses — `sovereign`, not `local` — so the renderer and the profile
    sync finally agree on one shape.

    MERGE RULE: an EXISTING sovereign provider keeps its `baseUrl`/`api`. The
    live box speaks `openai-completions` at `/v1` and works; re-asserting
    `anthropic-messages` from a default would break a working setup to satisfy a
    template. Those fields are written only when the provider is created.
    """
    backend = desc.get("backend", "local")
    local = desc.get("local", {})
    anth = desc.get("anthropic", {})
    port = desc.get("gateway_port", 18789)
    lm = local.get("model", "auto")   # "you choose" — not the CPU primary
    am = anth.get("model", "claude-sonnet-4-6")

    dst = _openclaw_home() / ".openclaw" / "openclaw.json"
    cfg, warning = _load_openclaw_config(dst)
    if warning:
        sys.stderr.write(f"[warn] {warning}\n")

    providers = cfg.setdefault("models", {}).setdefault("providers", {})

    # ── sovereign (on-box, through the safety spine) ──────────────────────────
    sov = providers.setdefault("sovereign", {})
    created = "baseUrl" not in sov
    if created:
        sov["baseUrl"] = local.get("endpoint", "http://127.0.0.1:8787")
        sov["api"] = "anthropic-messages"
        sov["timeoutSeconds"] = 300
    sov["apiKey"] = "sovereign-local"
    # The models list is OWNED by sync-openclaw-models.py (it mirrors the active
    # orchestration profile). Seed it only when there is nothing there at all.
    if not isinstance(sov.get("models"), list) or not sov["models"]:
        sov["models"] = [{"id": lm, "name": "Sovereign (local)", "contextWindow": 128000}]

    # ── anthropic (hosted Claude, outside the spine) ──────────────────────────
    # ONLY when a key is actually resolvable. An `apiKey: "${ANTHROPIC_API_KEY}"`
    # secret-ref with no such variable is NOT a warning to OpenClaw — it is a
    # HARD STARTUP FAILURE:
    #
    #   [secrets] [SECRETS_RELOADER_DEGRADED] SecretRefResolutionError:
    #   Environment variable "ANTHROPIC_API_KEY" is missing or empty.
    #   openclaw-gateway.service: Main process exited, code=exited, status=1
    #
    # Declaring the provider on a box without the key crash-looped the gateway
    # until systemd's start limit stopped it. `openclaw gateway status` reports
    # the same condition as a mere "feature will be unavailable", which is what
    # made it look safe. It is not: a provider that cannot authenticate must not
    # be declared at all.
    #
    # NOTE: `claude-cli/*` reaches the same Claude models through the operator's
    # already-authenticated CLI and needs NO key — that is the keyless route to a
    # second provider, and it is unaffected by any of this.
    have_key = bool(_anthropic_key() or os.environ.get("ANTHROPIC_API_KEY"))
    if have_key:
        a = providers.setdefault("anthropic", {})
        a["baseUrl"] = anth.get("endpoint", "https://api.anthropic.com")
        a["api"] = "anthropic-messages"
        a["apiKey"] = "${ANTHROPIC_API_KEY}"
        if not isinstance(a.get("models"), list) or not a["models"]:
            a["models"] = [{"id": am, "name": "Cloud Claude"}]
    else:
        # Remove any previously-written block, so a config that currently breaks
        # startup is REPAIRED by re-rendering rather than preserved by the merge.
        providers.pop("anthropic", None)
        sys.stderr.write(
            "[warn] no ANTHROPIC_API_KEY (checked "
            f"{KEY_FILE} and the environment) — the `anthropic` provider is NOT\n"
            "[warn] declared, because an unresolvable secret-ref stops the OpenClaw\n"
            "[warn] gateway from starting at all. Add the key and re-run, or use\n"
            "[warn] `claude-cli/*`, which needs no key.\n"
        )

    # ── the swap is a CHOICE OF PRIMARY, nothing more ─────────────────────────
    prefix = "sovereign" if backend == "local" else "anthropic"
    model_sel = (
        cfg.setdefault("agents", {}).setdefault("defaults", {}).setdefault("model", {})
    )
    model_sel["primary"] = f"{prefix}/{lm if backend == 'local' else am}"

    # ── register both in the allow-list, or neither is SELECTABLE ─────────────
    # `agents.defaults.models` is what makes a model "configured" — it is the map
    # OpenClaw's picker and `openclaw models list` read. Declaring a provider is
    # NOT enough: the anthropic provider block was written correctly and
    # `openclaw models list` still showed only sovereign/* and the one
    # claude-cli entry, because only those appear in this map.
    allow = cfg["agents"]["defaults"].setdefault("models", {})
    allow.setdefault(f"sovereign/{lm}", {})
    if have_key:
        allow.setdefault(f"anthropic/{am}", {})
    else:
        for k in [k for k in allow if k.startswith("anthropic/")]:
            allow.pop(k)

    # ── cloud is SELECTABLE, never AUTOMATIC ──────────────────────────────────
    # An onboarding wizard had left `fallbacks: ["claude-cli/…"]`, so a sovereign
    # failure silently continued on the hosted API — cloud use at exactly the
    # moment nobody is watching, on a box whose headline invariant is
    # "never_cloud_spill". Switching provider is a deliberate act; falling back
    # to one is not. Opt back in with OPENCLAW_ALLOW_CLOUD_FALLBACK=1.
    if os.environ.get("OPENCLAW_ALLOW_CLOUD_FALLBACK", "") != "1":
        model_sel.pop("fallbacks", None)

    gw = cfg.setdefault("gateway", {})
    gw.setdefault("mode", "local")
    gw.setdefault("bind", "loopback")
    gw["port"] = port

    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
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
        f"OPENAI_MODEL={sel.get('model', 'auto')}\n"
        f"OPENAI_API_KEY={key}\n"
        f"PORT={port}\n"
        f"OPEN_COMPUTER_BASE_DIR={OC_ROOT}/base_image\n"
        f"OPEN_COMPUTER_AGENTS_DIR={OC_ROOT}/agents\n"
    )
    OC_ENV.parent.mkdir(parents=True, exist_ok=True)
    OC_ENV.write_text(env, encoding="utf-8")
    return str(OC_ENV)


def render_claude_code(desc: dict[str, Any]) -> str:
    """Write /etc/sovereign-os/claude-code.env — Claude Code honors
    ANTHROPIC_BASE_URL + ANTHROPIC_API_KEY (Anthropic Messages protocol).

    local     → the on-box safety-spine gateway (:8787, POSTs /v1/messages).
    anthropic → cloud default: unset ANTHROPIC_BASE_URL + the real key.
    """
    backend = desc.get("backend", "local")
    sel = desc.get(backend, {})
    if backend == "local":
        base = sel.get("endpoint", "http://127.0.0.1:8787")
        key = "sovereign-local"
        base_line = f"ANTHROPIC_BASE_URL={base}\n"
    else:
        # cloud: ANTHROPIC_BASE_URL is left empty so Claude Code uses its default
        # (https://api.anthropic.com); the real key is operator-supplied.
        key = _anthropic_key()
        base_line = "ANTHROPIC_BASE_URL=\n"
    env = (
        f"# /etc/sovereign-os/claude-code.env — Claude Code CLI backend (SDD-600 Part 2). backend={backend}.\n"
        f"# Source this before launching `claude`, or reference it from the launcher unit.\n"
        f"# Rewritten by `sovereign-osctl claude-code backend`.\n"
        f"{base_line}"
        f"ANTHROPIC_API_KEY={key}\n"
    )
    CC_ENV.parent.mkdir(parents=True, exist_ok=True)
    CC_ENV.write_text(env, encoding="utf-8")
    return str(CC_ENV)


def render_vscode(desc: dict[str, Any]) -> str:
    """Write /etc/sovereign-os/vscode-cline-settings.json — the settings fragment
    to apply to the VSCode Cline / Claude Dev extension (Anthropic protocol).

    We can't write a live editor profile, so this is the exact fragment the
    operator pastes into VSCode settings (honest-degrade). local → the on-box
    gateway; anthropic → the extension's cloud default.
    """
    backend = desc.get("backend", "local")
    sel = desc.get(backend, {})
    if backend == "local":
        base = sel.get("endpoint", "http://127.0.0.1:8787")
        key = "sovereign-local"
    else:
        base = sel.get("endpoint", "https://api.anthropic.com")
        key = _anthropic_key() or "${ANTHROPIC_API_KEY}"
    frag = {
        "_comment": "sovereign-os SDD-600 Part 2 — paste into VSCode settings.json "
                    "(Cline / Claude Dev). Rewritten by `sovereign-osctl vscode backend`.",
        "_backend": backend,
        "cline.apiProvider": "anthropic",
        "cline.anthropicBaseUrl": base,
        "cline.anthropicApiKey": key,
    }
    VSCODE_CFG.parent.mkdir(parents=True, exist_ok=True)
    VSCODE_CFG.write_text(json.dumps(frag, indent=2) + "\n", encoding="utf-8")
    return str(VSCODE_CFG)


_RENDERERS = {
    "openclaw": render_openclaw,
    "open-computer": render_open_computer,
    "claude-code": render_claude_code,
    "vscode": render_vscode,
}


def _render(runtime: str, desc: dict[str, Any]) -> str:
    return _RENDERERS[runtime](desc)


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


def _adopt_openclaw_desc() -> dict[str, Any]:
    """Derive a descriptor from an OpenClaw install this system did not provision.

    `swap` refused without a saved descriptor, which only `provision` writes. But
    OpenClaw is normally installed by its OWN `onboard` wizard — that is how it
    got onto this box — so a perfectly working install has no descriptor and
    `openclaw backend local` answered

        error: openclaw not provisioned — run: sovereign-osctl openclaw install

    while the gateway was up and serving. Telling an operator to install what
    they already have is not a useful refusal.

    So an existing config is ADOPTED: it already states the endpoint, the models
    and the port. Read from the install, not from an assumption about how it got
    there. Returns {} when there is genuinely nothing to adopt.
    """
    cfg, _ = _load_openclaw_config(_openclaw_home() / ".openclaw" / "openclaw.json")
    if not cfg:
        return {}
    provs = cfg.get("models", {}).get("providers", {})
    sov = provs.get("sovereign") or provs.get("local") or {}
    anth = provs.get("anthropic") or {}
    primary = (
        cfg.get("agents", {}).get("defaults", {}).get("model", {}).get("primary", "")
    )

    def _first(p: dict[str, Any], fallback: str) -> str:
        ms = p.get("models")
        if isinstance(ms, list) and ms and isinstance(ms[0], dict) and ms[0].get("id"):
            return str(ms[0]["id"])
        return fallback

    return {
        "backend": "anthropic" if primary.startswith("anthropic/") else "local",
        "local": {
            "endpoint": sov.get("baseUrl", "http://127.0.0.1:8787"),
            "model": primary.split("/", 1)[1] if primary.startswith(("sovereign/", "local/"))
                     else _first(sov, "auto"),
        },
        "anthropic": {
            "endpoint": anth.get("baseUrl", "https://api.anthropic.com"),
            "model": _first(anth, "claude-opus-4-8"),
        },
        "gateway_port": cfg.get("gateway", {}).get("port", 18789),
    }


def swap(runtime: str, backend: str, key: str | None) -> dict[str, Any]:
    if key:
        _write_key(key)
    desc = _load_desc(runtime)
    if not desc and runtime == "openclaw":
        desc = _adopt_openclaw_desc()
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
