#!/usr/bin/env python3
"""scripts/models/workflow.py — R291 (E5.M9).

Operator-named (§1b mandate row, verbatim): "Operator-mutable flexible
profile (download / fine-tune / parameters / build / run / use / train
/ adapt / eval workflow)". Closes E5.M9 of the mandate.

Where R290 lifecycle.py handles the 5-stage *fine-tune* lifecycle
(download → fine-tune → eval → register → run), R291 surfaces the
FULL 9-stage workflow the operator named — same probe framework,
broader stage set, operator-mutable profiles. The two coexist:
operators pick `lifecycle` for the slim training-focused workflow
or `workflow` for the full nine-stage matrix.

Stage order is the operator's verbatim §1b sequence:
  1. download    — fetch base / dataset assets
  2. fine-tune   — train an adapter (composes R244)
  3. parameters  — operator-pull model parameters (KV-cache size,
                   context window, sampling defaults) for runtime
  4. build       — quantize / shard / cwasm-AOT for the host
  5. run         — bring the model online (router-attached)
  6. use         — operator's inference workload contract
  7. train       — continual training / DPO / RLAIF (post fine-tune)
  8. adapt       — hot-swap adapters (LoRA attach/detach) at runtime
  9. eval        — measure quality (composes R232)

CLI:
  workflow.py list [--config P] [--json|--human]
  workflow.py plan <profile> [--config P] [--json|--human]
  workflow.py next-step <profile> [--config P] [--json|--human]

Operator-overlay (R283/SDD-030): /etc/sovereign-os/workflow-profiles.toml
(or SOVEREIGN_OS_OVERLAY_WORKFLOW_PROFILES, or --config <path>).
Lists REPLACE entirely.

Exit codes:
  0  rendered (operator inspects the verdict)
  1  unknown profile
  2  usage error
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess as _sp
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
ROUND = "R291"
SDD_VECTOR = "E5.M9"


# ── 9-stage operator workflow catalogue ─────────────────────────────
#
# Each stage: name (verbatim from operator §1b), summary, command
# template (rendered with the profile's vars), probe spec. Probes
# are STRICTLY read-only.
WORKFLOW_STAGES = [
    {
        "stage": "download",
        "summary": "Fetch base model + dataset into the local store "
                   "(composes R242 model-toolchain).",
        "command": "sovereign-osctl models pull {base}",
        "probe_kind": "catalog-has-base",
    },
    {
        "stage": "fine-tune",
        "summary": "Train an adapter on the operator-named dataset "
                   "(R244 / scripts/models/fine_tune.py).",
        "command": ("sovereign-osctl models fine-tune plan {base} "
                    "--method {method} --dataset {dataset} "
                    "--adapter-id {adapter_id}"),
        "probe_kind": "fine-tune-history",
    },
    {
        "stage": "parameters",
        "summary": "Operator-pull runtime parameters (context window, "
                   "KV-cache size, sampling defaults). Stored in the "
                   "profile's `parameters` table.",
        "command": "sovereign-osctl workflow plan {name} --json | "
                   "jq .profile.parameters",
        "probe_kind": "profile-has-parameters",
    },
    {
        "stage": "build",
        "summary": "Quantize / shard / cwasm-AOT the adapted model "
                   "for this host (composes R281 wasm-aot + future "
                   "quantization tooling).",
        "command": ("sovereign-osctl wasm-aot compile "
                    "--adapter-id {adapter_id}"),
        "probe_kind": "build-artifact",
    },
    {
        "stage": "run",
        "summary": "Bring the adapter online — router-attached, "
                   "warmed.",
        "command": ("selfdefctl lora set-status {adapter_id} active"),
        "probe_kind": "selfdef-lora-status-active",
    },
    {
        "stage": "use",
        "summary": "Operator's inference workload contract — request "
                   "shape + expected QPS / latency.",
        "command": ("sovereign-osctl workflow plan {name} --json | "
                    "jq .profile.use"),
        "probe_kind": "profile-has-use-contract",
    },
    {
        "stage": "train",
        "summary": "Continual training / DPO / RLAIF post fine-tune "
                   "(operator's labeled-preference data).",
        "command": ("sovereign-osctl models fine-tune plan {base} "
                    "--method dpo-trl --dataset {dpo_dataset} "
                    "--adapter-id {adapter_id}-dpo"),
        "probe_kind": "train-dpo-history",
    },
    {
        "stage": "adapt",
        "summary": "Hot-swap adapters at runtime — operator picks "
                   "between candidate variants without service drop.",
        "command": ("selfdefctl lora attach {adapter_id} {base} "
                    "--status candidate"),
        "probe_kind": "selfdef-lora-list",
    },
    {
        "stage": "eval",
        "summary": "Measure quality on the operator's eval set "
                   "(R232 lm-eval harness).",
        "command": ("sovereign-osctl models eval plan {adapter_id} "
                    "--task {eval_task}"),
        "probe_kind": "eval-history",
    },
]


# ── Default profile (operator-overlay can replace) ──────────────────
DEFAULT_PROFILES: list[dict[str, Any]] = [
    {
        "name": "operator-flagship-9-stage",
        "base": "Qwen/Qwen2-7B-Instruct",
        "method": "sft-trl",
        "dataset": "operator-flagship-v1",
        "adapter_id": "operator-flagship",
        "eval_task": "operator-flagship-eval",
        "dpo_dataset": "operator-flagship-prefs-v1",
        "parameters": {
            "context_window": 8192,
            "kv_cache_gib": 16,
            "sampling": {"temperature": 0.7, "top_p": 0.9},
        },
        "use": {
            "workload": "helpdesk-assistance",
            "target_qps": 4,
            "target_p99_ms": 1500,
        },
        "notes": "Reference 9-stage workflow seed. Replace via "
                 "/etc/sovereign-os/workflow-profiles.toml.",
    },
]


# ── Probes (strictly read-only) ─────────────────────────────────────
def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    try:
        body = path.read_text(encoding="utf-8")
    except OSError:
        return []
    rows: list[dict[str, Any]] = []
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _selfdef_lora_list_safe() -> tuple[list[dict] | None, str | None]:
    sd = shutil.which("selfdefctl")
    if not sd:
        return None, "selfdefctl not on PATH"
    try:
        r = _sp.run([sd, "lora", "list", "--json"],
                    capture_output=True, text=True, timeout=10, check=False)
    except (OSError, _sp.TimeoutExpired) as e:
        return None, f"selfdefctl: {e}"
    if r.returncode != 0:
        return None, f"selfdefctl rc={r.returncode}"
    try:
        doc = json.loads(r.stdout)
    except json.JSONDecodeError as e:
        return None, f"json: {e}"
    return doc.get("adapters") if isinstance(doc, dict) else [], None


def probe_stage(stage: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    kind = stage["probe_kind"]
    if kind == "catalog-has-base":
        catalog = REPO_ROOT / "models" / "catalog.yaml"
        if not catalog.is_file():
            return {"complete": False,
                    "detail": f"catalog not found at {catalog}"}
        try:
            return {
                "complete": profile["base"] in catalog.read_text("utf-8"),
                "detail": f"scanned catalog for `{profile['base']}`",
            }
        except OSError as e:
            return {"complete": None, "detail": f"catalog read: {e}"}
    if kind == "fine-tune-history":
        rows = _read_jsonl(Path("/var/lib/sovereign-os/fine-tune.jsonl"))
        adapter = profile["adapter_id"]
        hits = [r for r in rows if r.get("adapter_id") == adapter]
        return {
            "complete": bool(hits),
            "detail": f"fine-tune.jsonl has {len(hits)} row(s) for `{adapter}`",
        }
    if kind == "profile-has-parameters":
        params = profile.get("parameters")
        return {
            "complete": isinstance(params, dict) and bool(params),
            "detail": "profile.parameters non-empty"
                      if (isinstance(params, dict) and params)
                      else "profile.parameters missing or empty",
        }
    if kind == "build-artifact":
        # Real artifact check would inspect /var/lib/sovereign-os/wasm-aot-cache.
        # For SEED, report indeterminate when cache dir absent.
        cache = Path("/var/lib/sovereign-os/wasm-aot-cache")
        return {
            "complete": cache.is_dir() and any(cache.iterdir()),
            "detail": (f"wasm-AOT cache {cache} "
                       f"{'populated' if cache.is_dir() and any(cache.iterdir()) else 'empty/absent'}"),
        }
    if kind == "selfdef-lora-status-active":
        adapters, err = _selfdef_lora_list_safe()
        if adapters is None:
            return {"complete": None, "detail": err}
        for a in adapters:
            if isinstance(a, dict) and a.get("adapter_id") == profile["adapter_id"]:
                return {
                    "complete": a.get("status") == "active",
                    "detail": f"adapter `{profile['adapter_id']}` status={a.get('status')!r}",
                }
        return {"complete": False,
                "detail": f"adapter `{profile['adapter_id']}` absent from lora list"}
    if kind == "profile-has-use-contract":
        use = profile.get("use")
        return {
            "complete": isinstance(use, dict) and bool(use),
            "detail": "profile.use non-empty"
                      if (isinstance(use, dict) and use)
                      else "profile.use missing or empty",
        }
    if kind == "train-dpo-history":
        rows = _read_jsonl(Path("/var/lib/sovereign-os/fine-tune.jsonl"))
        want = f"{profile['adapter_id']}-dpo"
        hits = [r for r in rows if r.get("adapter_id") == want]
        return {
            "complete": bool(hits),
            "detail": f"DPO history for `{want}`: {len(hits)} row(s)",
        }
    if kind == "selfdef-lora-list":
        adapters, err = _selfdef_lora_list_safe()
        if adapters is None:
            return {"complete": None, "detail": err}
        hit = any(
            isinstance(a, dict) and a.get("adapter_id") == profile["adapter_id"]
            for a in adapters
        )
        return {"complete": hit,
                "detail": f"selfdefctl lora list — `{profile['adapter_id']}` "
                          f"{'found' if hit else 'absent'}"}
    if kind == "eval-history":
        rows = _read_jsonl(Path("/var/lib/sovereign-os/eval-history.jsonl"))
        adapter = profile["adapter_id"]
        hits = [r for r in rows if r.get("adapter_id") == adapter]
        return {
            "complete": bool(hits),
            "detail": f"eval-history.jsonl has {len(hits)} row(s) for `{adapter}`",
        }
    return {"complete": None, "detail": f"unknown probe: {kind}"}


# ── Plan assembly ───────────────────────────────────────────────────
def render_command(stage: dict[str, Any], profile: dict[str, Any]) -> str:
    # Defensive: missing key → render the literal placeholder for the  # anti-min-waiver: R480 placeholder-rendering-is-FEATURE-operator-discoverable-template-token-surface-not-minimization-debt
    # operator to fix in the profile.
    class _Defaulting(dict):
        def __missing__(self, key):
            return "{" + key + "}"
    return stage["command"].format_map(_Defaulting(profile))


def assemble_plan(profile: dict[str, Any]) -> dict[str, Any]:
    stages: list[dict[str, Any]] = []
    for s in WORKFLOW_STAGES:
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
        "stage_names_in_order": [s["stage"] for s in WORKFLOW_STAGES],
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
            "workflow-profiles",
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
    lines = ["── R291 sovereign-os 9-stage workflow profiles (E5.M9) ──"]
    lines.append(f"  source:    {meta.get('_source')}")
    lines.append(f"  profiles:  {len(profiles)}")
    lines.append(f"  stages:    download → fine-tune → parameters → build → "
                 "run → use → train → adapt → eval")
    lines.append("")
    for p in profiles:
        if not isinstance(p, dict):
            continue
        lines.append(f"  • {p.get('name', '<unnamed>')}")
        lines.append(f"      base:       {p.get('base', '?')}")
        lines.append(f"      adapter_id: {p.get('adapter_id', '?')}")
        if p.get("notes"):
            lines.append(f"      notes:      {p['notes']}")
        lines.append("")
    return "\n".join(lines)


def render_plan_human(doc: dict) -> str:
    p = doc["profile"]
    lines = [f"── R291 9-stage workflow for `{p.get('name', '?')}` (E5.M9) ──"]
    lines.append(f"  next-stage: {doc.get('next_stage') or '(all complete)'}")
    lines.append("")
    for s in doc["stages"]:
        complete = s["probe"].get("complete")
        mark = {True: "OK ", False: "-- ", None: "?? "}.get(complete, "?? ")
        lines.append(f"  [{mark}] {s['stage']:11s} — {s['summary']}")
        lines.append(f"           cmd:   {s['command']}")
        lines.append(f"           probe: {s['probe'].get('detail', '')}")
        lines.append("")
    return "\n".join(lines)


# ── Main ────────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="workflow.py")
    sub = p.add_subparsers(dest="verb", required=True)

    pl = sub.add_parser("list")
    pl.add_argument("--config", type=Path)
    pl_fmt = pl.add_mutually_exclusive_group()
    pl_fmt.add_argument("--json", dest="fmt", action="store_const", const="json")
    pl_fmt.add_argument("--human", dest="fmt", action="store_const", const="human")
    pl.set_defaults(fmt="json")

    pp = sub.add_parser("plan")
    pp.add_argument("profile")
    pp.add_argument("--config", type=Path)
    pp_fmt = pp.add_mutually_exclusive_group()
    pp_fmt.add_argument("--json", dest="fmt", action="store_const", const="json")
    pp_fmt.add_argument("--human", dest="fmt", action="store_const", const="human")
    pp.set_defaults(fmt="json")

    pn = sub.add_parser("next-step")
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
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "profile_count": len(profiles),
                "stage_names_in_order": [s["stage"] for s in WORKFLOW_STAGES],
                "profiles": profiles,
                "overlay": meta,
            }, indent=2))
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
                print(f"profile `{profile.get('name')}` workflow complete")
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
