#!/usr/bin/env python3
"""Mirror the active orchestration profile's per-tier models into OpenClaw's
sovereign model catalog.

WHY: sovereign-os owns the *placement* (which model runs on which card, at what
context window) via the orchestration profiles. OpenClaw is a *consumer* of the
sovereign inference endpoint (models.providers.sovereign in openclaw.json) and
has its own copy of each model's advertised name / contextWindow / maxTokens /
reasoning flag. When an operator switches profiles (e.g. Coding Focus swaps the
logic tier to Qwen3-Coder-32B — a 1M-context model), OpenClaw kept showing the
stale 131072 window and the old model name. This script closes that gap: after a
`trinity profile switch`, the two GPU-tier entries OpenClaw exposes are rewritten
from the profile's allocations + the model catalog's ground-truth attributes.

SCOPE (deliberately narrow):
  * Touches ONLY the managed GPU-tier entries: gpu-oracle <- oracle tier,
    gpu-logic <- logic tier, plus the Qwythos RTX 4090 worker while the
    Qwythos three-card profile is active. local-oracle and any
    operator-custom entries are left byte-for-byte alone.
  * Reads facts, writes facts. contextWindow is the lower of the catalog
    capability and the profile's actual per-card launch budget; reasoning comes
    from models/catalog.yaml. maxTokens is a derived output budget (min(32768,
    ctx//4), floored at 4096); name is composed from the model + card.
  * Soft dependency: if OpenClaw is not installed (no openclaw.json), this is a
    clean no-op (exit 0) — a sovereign-os box without OpenClaw is normal.

When it changes the catalog it reloads the operator's OpenClaw gateway itself.
Profile application must be a complete transaction: leaving a user to restart
or reapply manually is how OpenClaw can keep an obsolete model list.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pwd
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG = REPO_ROOT / "models" / "catalog.yaml"

# OpenClaw sovereign-model id  ->  orchestration-profile tier it mirrors.
TIER_FOR_MODEL_ID = {
    "gpu-oracle": "oracle",
    "gpu-logic": "logic",
    "gpu-qwythos-worker": "router",
}
QWYTHOS_WORKER_ID = "gpu-qwythos-worker"
QWYTHOS_WORKER_PROFILE = "qwythos-three-card"
QWYTHOS_DUAL_MEMORY_PROFILE = "qwythos-dual-memory"

# SAIN-01 card layout — target_hardware -> human label for the model name.
# Falls back to the raw target_hardware string on any other machine, so the
# name stays informative even when the layout differs.
CARD_LABEL = {
    # PCI-bus ordering on the live SAIN-01 host.  This is the same explicit
    # CUDA_DEVICE_ORDER=PCI_BUS_ID mapping used by the Qwythos launcher.
    "cuda:0": "RTX PRO 6000",
    "cuda:1": "RTX 5090",
    "cuda:2": "RTX 4090",
    "cpu": "CPU",
}
TIER_LABEL = {"oracle": "Oracle", "logic": "Logic", "router": "Qwythos Worker"}

MAXTOK_CAP = 32768
MAXTOK_FLOOR = 4096
CATALOG_REVISION_PATH = Path(
    os.environ.get(
        "SOVEREIGN_OS_OPENCLAW_CATALOG_REVISION",
        "/etc/sovereign-os/openclaw-catalog-revision.json",
    )
)


def _log(msg: str) -> None:
    print(f"  [openclaw-sync] {msg}")


def _resolve_profile_yaml(profile_id: str) -> Path | None:
    """Find <profile_id>.yaml across the runtime / orchestration / user dirs —
    the same search order sovereign-osctl's _resolve_profile uses."""
    home = Path(os.environ.get("HOME", "/root"))
    user_dir = Path(
        os.environ.get(
            "SOVEREIGN_OS_USER_PROFILES_DIR",
            str(home / ".sovereign-os" / "profiles" / "orchestration"),
        )
    )
    for d in (
        REPO_ROOT / "profiles" / "runtime",
        REPO_ROOT / "profiles" / "orchestration",
        user_dir,
    ):
        cand = d / f"{profile_id}.yaml"
        if cand.is_file():
            return cand
    return None


def _active_profile_id() -> str | None:
    for cand in (
        Path("/etc/sovereign-os/active-runtime-profile"),
        Path(os.environ.get("HOME", "/root")) / ".sovereign-os" / "active-runtime-profile",
    ):
        try:
            v = cand.read_text(encoding="utf-8").strip()
            if v:
                return v
        except OSError:
            continue
    return None


def _catalog_index() -> dict[str, dict]:
    data = yaml.safe_load(CATALOG.read_text(encoding="utf-8")) or {}
    idx: dict[str, dict] = {}
    # catalog groups models under tier sections; walk any list of dicts with an id.
    def walk(o):
        if isinstance(o, dict):
            if "id" in o and ("context_window_tokens" in o or "purpose" in o):
                idx[str(o["id"])] = o
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(data)
    return idx


def _profile_allocations(profile_yaml: Path) -> dict[str, dict]:
    data = yaml.safe_load(profile_yaml.read_text(encoding="utf-8")) or {}
    rp = data.get("runtime_profile") or data.get("orchestration_profile") or {}
    context_budget = (rp.get("context_budget") or {}).get("initial_tokens") or {}
    out: dict[str, dict] = {}
    for a in rp.get("allocations") or []:
        tier = a.get("tier")
        if tier:
            # Do not advertise a model's catalogue maximum as though it were
            # loaded on this card. Qwythos advertises 1M tokens but this
            # profile intentionally launches 12K / 16K / 64K residents.
            alloc = dict(a)
            actual_ctx = context_budget.get(a.get("target_hardware"))
            if actual_ctx is not None:
                alloc["context_tokens"] = int(actual_ctx)
            out[tier] = alloc
    return out


def _derive_entry(alloc: dict, cat: dict[str, dict], oc_id: str) -> dict:
    """Return the fields to overwrite on the OpenClaw model entry."""
    model = alloc.get("model") or "?"
    hw = alloc.get("target_hardware") or "?"
    tier = alloc.get("tier") or "?"
    active = alloc.get("active", True)

    meta = cat.get(model, {})
    catalog_ctx = int(meta.get("context_window_tokens") or 0) or None
    launch_ctx = int(alloc.get("context_tokens") or 0) or None
    ctx = min(v for v in (catalog_ctx, launch_ctx) if v is not None) if (catalog_ctx or launch_ctx) else None
    purpose = meta.get("purpose") or []
    reasoning = "reasoning" in [str(p) for p in purpose]

    card = CARD_LABEL.get(hw, hw)
    tlabel = TIER_LABEL.get(tier, tier.title())
    name = f"Sovereign {tlabel} ({model}, {card})"
    if not active:
        name += " [idle]"

    entry: dict = {"name": name, "reasoning": reasoning}
    if ctx:
        entry["contextWindow"] = ctx
        profile_output_cap = int(alloc.get("max_output_tokens") or 0) or None
        entry["maxTokens"] = min(
            MAXTOK_CAP,
            ctx // 4,
            profile_output_cap if profile_output_cap is not None else MAXTOK_CAP,
        )
    return entry


def _openclaw_config_path() -> Path:
    if os.environ.get("OPENCLAW_CONFIG"):
        return Path(os.environ["OPENCLAW_CONFIG"]).expanduser()
    # When invoked via sudo from the signed rail, target the real operator's
    # config, not root's.
    sudo_user = os.environ.get("SUDO_USER")
    if sudo_user and os.geteuid() == 0:
        try:
            home = Path(pwd.getpwnam(sudo_user).pw_dir)
            return home / ".openclaw" / "openclaw.json"
        except KeyError:
            pass
    return Path(os.environ.get("HOME", "/root")) / ".openclaw" / "openclaw.json"


def _chown_like(target: Path, ref_uid: int, ref_gid: int) -> None:
    try:
        os.chown(target, ref_uid, ref_gid)
    except OSError:
        pass


def _atomic_json(path: Path, value: dict) -> None:
    """Write the safe consumer witness without ever exposing openclaw.json.

    The real config includes provider credentials, so the runtime-state reader
    must consume a deliberately small, secret-free projection instead.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".openclaw-catalog-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(value, fh, indent=2, sort_keys=True)
            fh.write("\n")
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _catalog_revision(profile_id: str, profile_yaml: Path, cfg_path: Path,
                      models: list[dict]) -> dict:
    """Return the attestation-safe part of OpenClaw's sovereign catalog."""
    managed_ids = set(TIER_FOR_MODEL_ID)
    entries = []
    for entry in models:
        model_id = entry.get("id")
        if model_id not in managed_ids:
            continue
        entries.append({
            "id": model_id,
            "name": entry.get("name"),
            "context_window_tokens": entry.get("contextWindow"),
            "max_output_tokens": entry.get("maxTokens"),
        })
    # Digest the serialized projection rather than the full config: provider
    # keys must neither enter model state nor affect a consumer revision.
    projection = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()
    return {
        "profile_id": profile_id,
        "profile_revision_sha256": hashlib.sha256(profile_yaml.read_bytes()).hexdigest(),
        "consumer_revision_sha256": hashlib.sha256(projection).hexdigest(),
        "config_path": str(cfg_path),
        "published_at": datetime.now(timezone.utc).isoformat(),
        "models": entries,
    }


def _publish_catalog_revision(profile_id: str, profile_yaml: Path, cfg_path: Path,
                              models: list[dict]) -> None:
    # A direct, unprivileged sync owns the user's config but deliberately does
    # not try to create a root-owned global state file.  The profile rail runs
    # this as root and publishes the witness atomically as part of the same
    # successful profile transaction.
    if os.geteuid() != 0 and "SOVEREIGN_OS_OPENCLAW_CATALOG_REVISION" not in os.environ:
        _log("catalog revision not published (unprivileged direct sync)")
        return
    try:
        _atomic_json(CATALOG_REVISION_PATH, _catalog_revision(
            profile_id, profile_yaml, cfg_path, models
        ))
        _log(f"published OpenClaw catalog revision to {CATALOG_REVISION_PATH}")
    except OSError as exc:
        _log(f"could not publish OpenClaw catalog revision: {exc}")


def _restart_openclaw_gateway(config_owner_uid: int) -> None:
    """Reload the user service which consumes openclaw.json."""
    try:
        user = pwd.getpwuid(config_owner_uid)
    except KeyError:
        _log("could not resolve OpenClaw config owner; gateway reload skipped")
        return
    if os.geteuid() == 0:
        cmd = ["runuser", "-u", user.pw_name, "--", "env",
               f"XDG_RUNTIME_DIR=/run/user/{config_owner_uid}",
               f"DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/{config_owner_uid}/bus",
               "systemctl", "--user", "restart", "openclaw-gateway.service"]
    else:
        cmd = ["systemctl", "--user", "restart", "openclaw-gateway.service"]
    result = subprocess.run(cmd, text=True, capture_output=True, check=False)
    if result.returncode:
        detail = (result.stderr or result.stdout).strip().splitlines()
        _log(f"OpenClaw catalog changed but gateway reload failed: {detail[-1] if detail else result.returncode}")
    else:
        _log("restarted OpenClaw gateway so the updated model list is live")


def _ensure_qwythos_worker(cfg: dict, models: list[dict], allocs: dict[str, dict],
                           cat: dict[str, dict], profile_id: str, changes: list[str]) -> None:
    """Add/remove the one profile-owned third-card model without touching user models."""
    found = next((m for m in models if m.get("id") == QWYTHOS_WORKER_ID), None)
    wants_worker = profile_id == QWYTHOS_WORKER_PROFILE and bool(allocs.get("router"))
    defaults = cfg.setdefault("agents", {}).setdefault("defaults", {})
    model_ref = f"sovereign/{QWYTHOS_WORKER_ID}"
    policy = defaults.setdefault("modelPolicy", {}).setdefault("allow", [])
    configured = defaults.setdefault("models", {})
    if wants_worker:
        if found is None:
            found = {"id": QWYTHOS_WORKER_ID, "input": ["text"],
                     "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0}}
            models.append(found)
            changes.append(f"added {QWYTHOS_WORKER_ID} (RTX 4090 Qwythos worker)")
        derived = _derive_entry(allocs["router"], cat, QWYTHOS_WORKER_ID)
        for key, value in derived.items():
            if found.get(key) != value:
                changes.append(f"{QWYTHOS_WORKER_ID}.{key}: {found.get(key)!r} -> {value!r}")
                found[key] = value
        if model_ref not in configured:
            configured[model_ref] = {}
            changes.append(f"enabled {model_ref} in OpenClaw defaults")
        if model_ref not in policy:
            policy.append(model_ref)
            changes.append(f"allowed {model_ref} in OpenClaw policy")
        return
    if found is not None:
        models.remove(found)
        changes.append(f"removed inactive profile-owned {QWYTHOS_WORKER_ID}")
    if model_ref in configured:
        del configured[model_ref]
        changes.append(f"removed inactive default {model_ref}")
    if model_ref in policy:
        policy.remove(model_ref)
        changes.append(f"removed inactive allow rule {model_ref}")


def _ensure_local_memory(cfg: dict, profile_id: str, changes: list[str]) -> None:
    """Keep memory local when the 4090 is assigned to the BGE stack."""
    if profile_id != QWYTHOS_DUAL_MEMORY_PROFILE:
        return
    search = cfg.setdefault("memory", {}).setdefault("search", {})
    desired = {
        "provider": "openai-compatible",
        # vLLM serves the local BGE model under this OpenAI-compatible alias;
        # the catalog id is a disk/model identity, not the API model field.
        "model": "gpu-embed",
        "fallback": "none",
        "remote": {"baseUrl": "http://127.0.0.1:8084/v1", "apiKey": "sovereign-local", "batch": {"enabled": False}},
    }
    for key, value in desired.items():
        if search.get(key) != value:
            search[key] = value
            changes.append(f"memory.search.{key}: configured for local RTX 4090 BGE-M3")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--profile", help="profile id (default: active-runtime-profile)")
    ap.add_argument("--config", help="path to openclaw.json (default: auto-detect)")
    ap.add_argument("--dry-run", action="store_true", help="print changes, write nothing")
    args = ap.parse_args(argv)

    profile_id = args.profile or _active_profile_id()
    if not profile_id:
        _log("no profile id given and no active-runtime-profile set — nothing to sync")
        return 0

    profile_yaml = _resolve_profile_yaml(profile_id)
    if not profile_yaml:
        _log(f"profile {profile_id!r} not found on disk (generated combo?) — skipping OpenClaw sync")
        return 0

    cfg_path = Path(args.config).expanduser() if args.config else _openclaw_config_path()
    if not cfg_path.is_file():
        _log(f"OpenClaw config not found at {cfg_path} — OpenClaw not installed here; skipping (ok)")
        return 0

    allocs = _profile_allocations(profile_yaml)
    cat = _catalog_index()

    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        _log(f"could not read {cfg_path}: {e} — skipping (non-fatal)")
        return 0

    models = (
        cfg.get("models", {})
        .get("providers", {})
        .get("sovereign", {})
        .get("models")
    )
    if not isinstance(models, list):
        # NOT "skipping (ok)". A present openclaw.json with no sovereign provider
        # is a BROKEN install, not an absent one — the absent case is handled
        # above (no config file ⇒ clean no-op, a box without OpenClaw is normal).
        #
        # This branch is what a full-file rewrite of openclaw.json produces. The
        # SDD-707 renderer used to template over the file, which erased the
        # sovereign provider; this script then found nothing, reported "(ok)",
        # and the profile mirroring stopped happening for good. Silent and
        # permanent, and it read as success in every log.
        _log(
            f"BROKEN: {cfg_path} exists but has no models.providers.sovereign.models "
            "list — the profile's per-tier models cannot be mirrored, so OpenClaw "
            "will keep advertising whatever it last had. Re-render it with "
            "`sovereign-osctl openclaw backend local`."
        )
        return 2

    changes: list[str] = []
    for entry in models:
        oc_id = entry.get("id")
        tier = TIER_FOR_MODEL_ID.get(oc_id)
        if not tier or oc_id == QWYTHOS_WORKER_ID:
            continue  # local-oracle / custom entries: never touched
        alloc = allocs.get(tier)
        if not alloc:
            _log(f"profile {profile_id!r} has no {tier} tier — leaving {oc_id} unchanged")
            continue
        derived = _derive_entry(alloc, cat, oc_id)
        for k, v in derived.items():
            if entry.get(k) != v:
                changes.append(f"{oc_id}.{k}: {entry.get(k)!r} -> {v!r}")
                entry[k] = v

    _ensure_qwythos_worker(cfg, models, allocs, cat, profile_id, changes)
    _ensure_local_memory(cfg, profile_id, changes)

    if not changes:
        _log(f"OpenClaw already in sync with profile {profile_id!r} — no change")
        if not args.dry_run:
            _publish_catalog_revision(profile_id, profile_yaml, cfg_path, models)
        return 0

    for c in changes:
        _log(c)

    if args.dry_run:
        _log("--dry-run: no file written")
        return 0

    # Backup then write, preserving ownership (important when run as root via sudo).
    st = cfg_path.stat()
    backup = cfg_path.with_suffix(cfg_path.suffix + ".bak")
    backup.write_text(cfg_path.read_text(encoding="utf-8"), encoding="utf-8")
    _chown_like(backup, st.st_uid, st.st_gid)

    cfg_path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    _chown_like(cfg_path, st.st_uid, st.st_gid)

    _log(f"wrote {len(changes)} change(s) to {cfg_path} (backup: {backup.name})")
    _publish_catalog_revision(profile_id, profile_yaml, cfg_path, models)
    _restart_openclaw_gateway(st.st_uid)
    return 0


if __name__ == "__main__":
    sys.exit(main())
