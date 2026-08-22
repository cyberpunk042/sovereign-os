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
  * Touches ONLY the two GPU-tier entries: gpu-oracle <- oracle tier,
    gpu-logic <- logic tier. local-oracle and any operator-custom entries are
    left byte-for-byte alone.
  * Reads facts, writes facts. contextWindow / reasoning come straight from
    models/catalog.yaml; maxTokens is a derived output budget (min(32768,
    ctx//4), floored at 4096); name is composed from the model + card.
  * Soft dependency: if OpenClaw is not installed (no openclaw.json), this is a
    clean no-op (exit 0) — a sovereign-os box without OpenClaw is normal.

It never restarts OpenClaw (that would kill a live agent session); it prints a
one-line reminder that the gateway must reload to pick up the change.
"""
from __future__ import annotations

import argparse
import json
import os
import pwd
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG = REPO_ROOT / "models" / "catalog.yaml"

# OpenClaw sovereign-model id  ->  orchestration-profile tier it mirrors.
TIER_FOR_MODEL_ID = {"gpu-oracle": "oracle", "gpu-logic": "logic"}

# SAIN-01 card layout — target_hardware -> human label for the model name.
# Falls back to the raw target_hardware string on any other machine, so the
# name stays informative even when the layout differs.
CARD_LABEL = {
    "cuda:0": "RTX 5090",
    "cuda:1": "RTX PRO 6000",
    "cuda:2": "RTX 4090",
    "cpu": "CPU",
}
TIER_LABEL = {"oracle": "Oracle", "logic": "Logic"}

MAXTOK_CAP = 32768
MAXTOK_FLOOR = 4096


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
    out: dict[str, dict] = {}
    for a in rp.get("allocations") or []:
        tier = a.get("tier")
        if tier:
            out[tier] = a
    return out


def _derive_entry(alloc: dict, cat: dict[str, dict], oc_id: str) -> dict:
    """Return the fields to overwrite on the OpenClaw model entry."""
    model = alloc.get("model") or "?"
    hw = alloc.get("target_hardware") or "?"
    tier = alloc.get("tier") or "?"
    active = alloc.get("active", True)

    meta = cat.get(model, {})
    ctx = int(meta.get("context_window_tokens") or 0) or None
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
        entry["maxTokens"] = max(MAXTOK_FLOOR, min(MAXTOK_CAP, ctx // 4))
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
        _log("openclaw.json has no models.providers.sovereign.models list — skipping (ok)")
        return 0

    changes: list[str] = []
    for entry in models:
        oc_id = entry.get("id")
        tier = TIER_FOR_MODEL_ID.get(oc_id)
        if not tier:
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

    if not changes:
        _log(f"OpenClaw already in sync with profile {profile_id!r} — no change")
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
    _log("reload the OpenClaw gateway to pick up the new model attributes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
