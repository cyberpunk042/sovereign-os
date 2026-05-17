#!/usr/bin/env python3
"""scripts/models/lifecycle.py — R290 (E5.M6).

Operator-named (§1b mandate row, verbatim): "End-to-end fine-tune
lifecycle (operator triggers training → eval → register)". Closes
E5.M6 of the mandate.

The lifecycle threads the existing fine_tune.py + eval.py + selfdef
model-registry surfaces into ONE operator-pull workflow:

  download? → fine-tune (R244) → eval (R232) → register (SD-R34 / R182)
                                                       ↳ run / use

For each operator-supplied "lifecycle profile" (TOML), the verb
emits the planned stages, the next pending action, and (when
authorized) executes the next stage. Read-only by default —
state-mutating stages stay gated behind the existing per-tool
authorization flags (e.g. fine-tune `--dry-run` default).

Operator-overlay (R283 / SDD-030 adoption): the profile file lives
at `/etc/sovereign-os/lifecycle-profiles.toml` (or
`SOVEREIGN_OS_OVERLAY_LIFECYCLE_PROFILES=<path>`, or
`--config <path>`). Operator declares ≥1 profile under
`[[profiles]]`. The script's DEFAULT_PROFILES seed two reference
profiles so a fresh install has something to point at.

CLI:
  lifecycle.py list [--config P] [--json|--human]
                            List declared profiles.

  lifecycle.py plan <profile> [--config P] [--json|--human]
                            Render the lifecycle stages for one
                            profile + per-stage status verdict.

  lifecycle.py next-step <profile> [--config P] [--json|--human]
                            Identify the next pending stage —
                            returns the exact command the operator
                            would run for that stage.

Exit codes:
  0  rendered (any verdict — operator inspects the JSON)
  1  declared profile is missing entirely
  2  usage error
"""
from __future__ import annotations

import argparse
import json
import shutil
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
ROUND = "R290"
SDD_VECTOR = "E5.M6 / composes R244 (fine-tune) + R232 (eval) + R182 (registry)"


# ── Lifecycle stage catalogue ───────────────────────────────────────
#
# Each stage is a (name, summary, command-template, status-probe)
# tuple. The command-template is rendered with the profile's vars and
# emitted to the operator; the status-probe answers "has this stage
# completed yet on the local host?" without running the stage. The
# status-probe NEVER mutates.
LIFECYCLE_STAGES = [
    {
        "stage": "download",
        "summary": "Fetch the base model into the local model store.",
        "command": "sovereign-osctl models pull {base}",
        "probe_kind": "models-list-contains",
        "probe_arg": "{base}",
    },
    {
        "stage": "fine-tune",
        "summary": "Train the operator-named adapter atop the base "
                   "model using R244 fine_tune.py.",
        "command": ("sovereign-osctl models fine-tune plan {base} "
                    "--method {method} --dataset {dataset} "
                    "--adapter-id {adapter_id}"),
        "probe_kind": "fine-tune-history-contains",
        "probe_arg": "{adapter_id}",
    },
    {
        "stage": "eval",
        "summary": "Evaluate the trained adapter against R232 lm-eval "
                   "harness on the operator-named eval set.",
        "command": ("sovereign-osctl models eval plan {adapter_id} "
                    "--task {eval_task}"),
        "probe_kind": "eval-history-contains",
        "probe_arg": "{adapter_id}",
    },
    {
        "stage": "register",
        "summary": "Register the adapter in the selfdef SD-R34 model "
                   "registry so it's discoverable + LoRA-attachable.",
        "command": ("selfdefctl lora attach {adapter_id} {base} "
                    "--status candidate"),
        "probe_kind": "selfdef-lora-list-contains",
        "probe_arg": "{adapter_id}",
    },
    {
        "stage": "run",
        "summary": "Hot-swap-attach the registered adapter; backend "
                   "router picks it up on next inference request.",
        "command": ("selfdefctl lora set-status {adapter_id} active"),
        "probe_kind": "selfdef-lora-status-active",
        "probe_arg": "{adapter_id}",
    },
]


# ── Default profiles (operator-overlay can replace) ─────────────────
DEFAULT_PROFILES: list[dict[str, Any]] = [
    {
        "name": "qwen2-7b-sft-helpdesk",
        "base": "Qwen/Qwen2-7B-Instruct",
        "method": "sft-trl",
        "dataset": "operator-helpdesk-v1",
        "adapter_id": "qwen2-helpdesk-v1",
        "eval_task": "operator-helpdesk-eval",
        "notes": "Reference SFT lifecycle on Zen5 + RTX PRO 6000.",
    },
    {
        "name": "llama3-1b-ternary-bench",
        "base": "meta-llama/Llama-3.2-1B",
        "method": "lora-unsloth",
        "dataset": "operator-bench-v1",
        "adapter_id": "llama3-1b-ternary-bench",
        "eval_task": "lm-eval-harness-mmlu-mini",
        "notes": "Small-model ternary-fast-path workload baseline.",
    },
]


# ── Probes (read-only, never mutate) ────────────────────────────────
def _which(bin_name: str) -> str | None:
    return shutil.which(bin_name)


def probe_stage(stage: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    """Run the stage's read-only probe and return a status dict."""
    arg = stage["probe_arg"].format(**profile)
    kind = stage["probe_kind"]
    if kind == "models-list-contains":
        return _probe_models_list(arg)
    if kind == "fine-tune-history-contains":
        return _probe_fine_tune_history(arg)
    if kind == "eval-history-contains":
        return _probe_eval_history(arg)
    if kind == "selfdef-lora-list-contains":
        return _probe_selfdef_lora_list(arg)
    if kind == "selfdef-lora-status-active":
        return _probe_selfdef_lora_status(arg, "active")
    return {"complete": None, "detail": f"unknown probe kind: {kind}"}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    try:
        body = path.read_text(encoding="utf-8")
    except OSError:
        return []
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _probe_models_list(base: str) -> dict[str, Any]:
    catalog = REPO_ROOT / "models" / "catalog.yaml"
    if not catalog.is_file():
        return {"complete": False,
                "detail": f"catalog not found at {catalog}"}
    try:
        body = catalog.read_text(encoding="utf-8")
    except OSError as e:
        return {"complete": None, "detail": f"catalog read error: {e}"}
    return {"complete": base in body,
            "detail": f"scanned {catalog} for `{base}`"}


def _probe_fine_tune_history(adapter_id: str) -> dict[str, Any]:
    p = Path("/var/lib/sovereign-os/fine-tune.jsonl")
    rows = _read_jsonl(p)
    hits = [r for r in rows if r.get("adapter_id") == adapter_id]
    return {
        "complete": bool(hits),
        "detail": (f"fine-tune state {p} has {len(hits)} row(s) "
                   f"for adapter `{adapter_id}`"),
    }


def _probe_eval_history(adapter_id: str) -> dict[str, Any]:
    p = Path("/var/lib/sovereign-os/eval-history.jsonl")
    rows = _read_jsonl(p)
    hits = [r for r in rows if r.get("adapter_id") == adapter_id]
    return {
        "complete": bool(hits),
        "detail": (f"eval state {p} has {len(hits)} row(s) "
                   f"for adapter `{adapter_id}`"),
    }


def _probe_selfdef_lora_list(adapter_id: str) -> dict[str, Any]:
    sd = _which("selfdefctl")
    if not sd:
        return {"complete": None,
                "detail": "selfdefctl not on PATH; cannot verify registry"}
    import subprocess as _sp
    try:
        r = _sp.run([sd, "lora", "list", "--json"],
                    capture_output=True, text=True, timeout=10, check=False)
    except (OSError, _sp.TimeoutExpired) as e:
        return {"complete": None, "detail": f"selfdefctl lora list: {e}"}
    if r.returncode != 0:
        return {"complete": None,
                "detail": f"selfdefctl rc={r.returncode}: "
                          f"{(r.stderr or r.stdout or '').splitlines()[:1]}"}
    try:
        doc = json.loads(r.stdout)
    except json.JSONDecodeError as e:
        return {"complete": None, "detail": f"json parse: {e}"}
    adapters = doc.get("adapters") if isinstance(doc, dict) else None
    if not isinstance(adapters, list):
        return {"complete": False,
                "detail": "selfdefctl lora list returned no `adapters[]`"}
    hit = any(
        isinstance(a, dict) and a.get("adapter_id") == adapter_id
        for a in adapters
    )
    return {"complete": hit,
            "detail": f"selfdefctl lora list — `{adapter_id}` "
                      f"{'found' if hit else 'absent'} "
                      f"({len(adapters)} total)"}


def _probe_selfdef_lora_status(adapter_id: str, want: str) -> dict[str, Any]:
    base = _probe_selfdef_lora_list(adapter_id)
    if base.get("complete") is not True:
        # Either not found or selfdefctl unavailable — propagate.
        return base
    sd = _which("selfdefctl")
    import subprocess as _sp
    try:
        r = _sp.run([sd, "lora", "list", "--json"],
                    capture_output=True, text=True, timeout=10, check=False)
        doc = json.loads(r.stdout)
    except (OSError, _sp.TimeoutExpired, json.JSONDecodeError) as e:
        return {"complete": None, "detail": f"status probe: {e}"}
    for a in doc.get("adapters", []):
        if isinstance(a, dict) and a.get("adapter_id") == adapter_id:
            status = a.get("status")
            return {
                "complete": status == want,
                "detail": (f"selfdefctl lora list — `{adapter_id}` "
                           f"status={status!r}, want={want!r}"),
            }
    return {"complete": False, "detail": f"adapter `{adapter_id}` not in list"}


# ── Manifest assembly ───────────────────────────────────────────────
def render_command(stage: dict[str, Any], profile: dict[str, Any]) -> str:
    return stage["command"].format(**profile)


def assemble_plan(profile: dict[str, Any]) -> dict[str, Any]:
    stages: list[dict[str, Any]] = []
    for s in LIFECYCLE_STAGES:
        probe = probe_stage(s, profile)
        stages.append({
            "stage": s["stage"],
            "summary": s["summary"],
            "command": render_command(s, profile),
            "probe": probe,
        })
    next_stage = None
    for s in stages:
        if s["probe"].get("complete") is not True:
            next_stage = s["stage"]
            break
    return {
        "schema_version": SCHEMA_VERSION,
        "round": ROUND,
        "sdd_vector": SDD_VECTOR,
        "profile": profile,
        "stages": stages,
        "next_stage": next_stage,
        "all_complete": next_stage is None,
    }


def resolve_profile(profiles: list[dict], name: str) -> dict | None:
    for p in profiles:
        if isinstance(p, dict) and p.get("name") == name:
            return p
    return None


def load_profiles(overlay_path: Path | None) -> tuple[list[dict], dict]:
    meta = {"_source": "(defaults)", "_overlay_keys": []}
    profiles = list(DEFAULT_PROFILES)
    if load_with_overlay is not None:
        cfg = load_with_overlay(
            "lifecycle-profiles",
            {"profiles": []},
            explicit_path=overlay_path,
        )
        meta["_source"] = cfg.get("_source", meta["_source"])
        meta["_overlay_keys"] = cfg.get("_overlay_keys", [])
        if cfg.get("_parse_error"):
            meta["_parse_error"] = cfg["_parse_error"]
        if cfg.get("profiles"):
            profiles = list(cfg["profiles"])
    return profiles, meta


# ── Human rendering ─────────────────────────────────────────────────
def render_list_human(profiles: list[dict], meta: dict) -> str:
    lines = ["── R290 sovereign-os fine-tune lifecycle profiles (E5.M6) ──"]
    lines.append(f"  source:   {meta.get('_source')}")
    lines.append(f"  profiles: {len(profiles)}")
    lines.append("")
    for p in profiles:
        if not isinstance(p, dict):
            continue
        lines.append(f"  • {p.get('name', '<unnamed>')}")
        lines.append(f"      base:       {p.get('base', '?')}")
        lines.append(f"      method:     {p.get('method', '?')}")
        lines.append(f"      dataset:    {p.get('dataset', '?')}")
        lines.append(f"      adapter_id: {p.get('adapter_id', '?')}")
        lines.append(f"      eval_task:  {p.get('eval_task', '?')}")
        if p.get("notes"):
            lines.append(f"      notes:      {p['notes']}")
        lines.append("")
    return "\n".join(lines)


def render_plan_human(doc: dict) -> str:
    p = doc["profile"]
    lines = [f"── R290 lifecycle plan for `{p.get('name', '?')}` (E5.M6) ──"]
    lines.append(f"  base:       {p.get('base', '?')}")
    lines.append(f"  adapter_id: {p.get('adapter_id', '?')}")
    lines.append(f"  next-stage: {doc.get('next_stage') or '(all complete)'}")
    lines.append("")
    for s in doc["stages"]:
        complete = s["probe"].get("complete")
        mark = {
            True: "OK ",
            False: "-- ",
            None: "?? ",
        }.get(complete, "?? ")
        lines.append(f"  [{mark}] {s['stage']:12s} — {s['summary']}")
        lines.append(f"           cmd:   {s['command']}")
        lines.append(f"           probe: {s['probe'].get('detail', '')}")
        lines.append("")
    return "\n".join(lines)


# ── Main ────────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lifecycle.py")
    sub = p.add_subparsers(dest="verb", required=True)

    pl = sub.add_parser("list", help="list declared lifecycle profiles")
    pl.add_argument("--config", type=Path)
    pl_fmt = pl.add_mutually_exclusive_group()
    pl_fmt.add_argument("--json", dest="fmt", action="store_const", const="json")
    pl_fmt.add_argument("--human", dest="fmt", action="store_const", const="human")
    pl.set_defaults(fmt="json")

    pp = sub.add_parser("plan", help="render lifecycle stages for one profile")
    pp.add_argument("profile")
    pp.add_argument("--config", type=Path)
    pp_fmt = pp.add_mutually_exclusive_group()
    pp_fmt.add_argument("--json", dest="fmt", action="store_const", const="json")
    pp_fmt.add_argument("--human", dest="fmt", action="store_const", const="human")
    pp.set_defaults(fmt="json")

    pn = sub.add_parser("next-step", help="next pending stage for one profile")
    pn.add_argument("profile")
    pn.add_argument("--config", type=Path)
    pn_fmt = pn.add_mutually_exclusive_group()
    pn_fmt.add_argument("--json", dest="fmt", action="store_const", const="json")
    pn_fmt.add_argument("--human", dest="fmt", action="store_const", const="human")
    pn.set_defaults(fmt="json")

    args = p.parse_args(argv)
    profiles, meta = load_profiles(getattr(args, "config", None))

    if args.verb == "list":
        if args.fmt == "json":
            doc = {
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "profile_count": len(profiles),
                "profiles": profiles,
                "overlay": meta,
            }
            print(json.dumps(doc, indent=2))
        else:
            print(render_list_human(profiles, meta), end="")
        return 0

    profile = resolve_profile(profiles, args.profile)
    if profile is None:
        print(json.dumps({
            "error": f"unknown profile: {args.profile}",
            "known": [p.get("name") for p in profiles if isinstance(p, dict)],
            "round": ROUND,
        }, indent=2), file=sys.stderr)
        return 1

    doc = assemble_plan(profile)
    doc["overlay"] = meta

    if args.verb == "plan":
        if args.fmt == "json":
            print(json.dumps(doc, indent=2))
        else:
            print(render_plan_human(doc), end="")
        return 0

    if args.verb == "next-step":
        out = {
            "schema_version": SCHEMA_VERSION,
            "round": ROUND,
            "sdd_vector": SDD_VECTOR,
            "profile_name": profile.get("name"),
            "next_stage": doc["next_stage"],
            "next_command": None,
            "all_complete": doc["all_complete"],
        }
        if doc["next_stage"] is not None:
            for s in doc["stages"]:
                if s["stage"] == doc["next_stage"]:
                    out["next_command"] = s["command"]
                    break
        if args.fmt == "json":
            print(json.dumps(out, indent=2))
        else:
            if out["next_stage"]:
                print(f"next: {out['next_stage']}")
                print(f"run:  {out['next_command']}")
            else:
                print(f"profile `{profile.get('name')}` lifecycle complete")
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
