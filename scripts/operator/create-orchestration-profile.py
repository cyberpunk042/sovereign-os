#!/usr/bin/env python3
"""scripts/operator/create-orchestration-profile.py — D21-3 composer backend.

Build a NEW orchestration-intent profile from the operator's per-device model
choices (the D-21 composer), validate it against the real catalog + the
orchestration-profile schema shape, and write it either as a DRAFT (the
operator's user dir, outside the repo) or into the REPO
(profiles/orchestration/<id>.yaml).

Grounded (SB-077 — no invention): every chosen model MUST be a real
models/catalog.yaml id whose declared tier matches the device it's placed on
(a conductor pick must be a pulse-tier model, logic → logic, oracle → oracle).
A device left as `none` is an inactive allocation.

Safety (the sanctioned R10274 pattern, mirrors scripts/models/load.py):
  - DRY-RUN by default: prints the YAML it WOULD write + the target path.
    --confirm actually writes (the cockpit path adds operator-key presence +
    type-to-confirm via the exec daemon).
  - never clobbers an existing profile (refuse unless --force); the 5 verbatim
    orchestration names + the 3 §18 runtime names are hard-refused regardless.
  - id is validated (^[a-z][a-z0-9-]*$); the file is written atomically.

Exit: 0 ok/dry-run · 2 usage/validation (bad id, unknown/mistiered model,
no active allocation, would-clobber) · 1 write error.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, NoReturn

REPO_ROOT = Path(__file__).resolve().parents[2]
REPO_ORCH_DIR = REPO_ROOT / "profiles" / "orchestration"
USER_ORCH_DIR = Path(os.environ.get(
    "SOVEREIGN_OS_USER_PROFILES_DIR",
    str(Path.home() / ".sovereign-os" / "profiles" / "orchestration")))

_ID_RE = re.compile(r"^[a-z][a-z0-9-]*$")
# The verbatim-locked names the composer must never overwrite.
_LOCKED_ORCH = {
    "full-orchestration", "coding-focus", "thinking-focus",
    "hybrid-coding-thinking", "full-hybrid",
}
_LOCKED_RUNTIME = {
    "ultra-sovereign-efficiency", "high-concurrency-burst", "deep-context-synthesis",
}

# device → (agent_id, tier, role, target_hardware, engine, extra)
_DEVICE = {
    "conductor": ("conductor_01", "pulse", "conductor", "cpu", "bitnet.cpp", {"core_mask": "0-7"}),
    "logic":     ("logic_01", "logic", "logic", "cuda:0", "vllm", {}),
    "oracle":    ("oracle_01", "oracle", "oracle", "cuda:1", "vllm", {}),
}


def _load_catalog() -> dict[str, dict]:
    """Return {id: model} from the shared model-health catalog reader."""
    mh_path = REPO_ROOT / "scripts" / "inference" / "model-health.py"
    spec = importlib.util.spec_from_file_location("_mh_reader", mh_path)
    mh = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mh)  # type: ignore[union-attr]
    return {str(m.get("id")): m for m in mh.load_catalog()}


def _fail(msg: str, code: int = 2) -> NoReturn:
    print(f"error: {msg}", file=sys.stderr)
    raise SystemExit(code)


def build(args: argparse.Namespace) -> dict[str, Any]:
    """Compose + validate the orchestration_profile dict (raises SystemExit on
    any invalid input). Pure — writes nothing."""
    pid = args.id
    if not _ID_RE.match(pid):
        _fail(f"bad id {pid!r} — must match ^[a-z][a-z0-9-]*$")
    catalog = _load_catalog()

    allocations: list[dict[str, Any]] = []
    picks = {"conductor": args.conductor, "logic": args.logic, "oracle": args.oracle}
    for device, model in picks.items():
        if not model or model.lower() == "none":
            continue
        m = catalog.get(model)
        if m is None:
            _fail(f"{device}: model {model!r} is not in models/catalog.yaml")
        agent_id, tier, role, target_hw, engine, extra = _DEVICE[device]
        if str(m.get("tier", "")).lower() != tier:
            _fail(f"{device}: {model!r} is a {m.get('tier')}-tier model, "
                  f"not {tier} — it cannot run on the {role} device")
        alloc = {"agent_id": agent_id, "tier": tier, "role": role,
                 "target_hardware": target_hw, "engine": engine,
                 "model": model, "active": True, **extra}
        allocations.append(alloc)
    if not allocations:
        _fail("no active allocation — pick a model for at least one device")

    active = ", ".join(f"{a['model']} on {a['role']}" for a in allocations)
    name = args.name or (pid.replace("-", " ").title())
    description = (
        f"Operator-composed orchestration profile ({pid}). "
        f"Active allocations: {active}. Composed in the D-21 cockpit and "
        f"applied through the signed control-exec rail."
    )
    return {
        "schema_version": "1.0.0",
        "orchestration_profile": {
            "id": pid,
            "name": name,
            "description": description,
            "intent": args.intent,
            "hardware_profile_compat": ["sain-01"],
            "allocations": allocations,
            "observability": {"primary_metric": "sovereign_os_inference_route_total"},
        },
    }


def _to_yaml(profile: dict[str, Any]) -> str:
    """Serialize with a header comment matching the family's convention. Uses
    PyYAML when present, else a tiny hand-emitter (the profile shape is fixed)."""
    header = (
        "# yaml-language-server: $schema=../../schemas/orchestration-profile.schema.yaml\n"
        "#\n# Orchestration-intent profile (D-21) — operator-composed via the cockpit.\n"
    )
    try:
        import yaml
        return header + yaml.safe_dump(profile, sort_keys=False, default_flow_style=False)
    except ImportError:
        pass
    op = profile["orchestration_profile"]
    lines = [header.rstrip("\n"), 'schema_version: "1.0.0"', "orchestration_profile:",
             f"  id: {op['id']}", f"  name: \"{op['name']}\"",
             f"  description: \"{op['description']}\"", f"  intent: {op['intent']}",
             "  hardware_profile_compat: [sain-01]", "  allocations:"]
    for a in op["allocations"]:
        parts = [f"agent_id: {a['agent_id']}", f"tier: {a['tier']}", f"role: {a['role']}",
                 f"target_hardware: \"{a['target_hardware']}\""]
        if a.get("core_mask"):
            parts.append(f"core_mask: \"{a['core_mask']}\"")
        parts += [f"engine: {a['engine']}", f"model: {a['model']}", "active: true"]
        lines.append("    - {" + ", ".join(parts) + "}")
    lines.append("  observability:")
    lines.append("    primary_metric: sovereign_os_inference_route_total")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Compose a D-21 orchestration profile")
    p.add_argument("id", help="profile id (positional; filename stem)")
    p.add_argument("--intent", default="custom")
    p.add_argument("--name", default="")
    p.add_argument("--conductor", default="none")
    p.add_argument("--logic", default="none")
    p.add_argument("--oracle", default="none")
    p.add_argument("--target", choices=["draft", "repo"], default="draft")
    p.add_argument("--confirm", action="store_true")
    p.add_argument("--force", action="store_true")
    args = p.parse_args(argv)

    profile = build(args)
    pid = profile["orchestration_profile"]["id"]
    out_dir = REPO_ORCH_DIR if args.target == "repo" else USER_ORCH_DIR
    out_path = out_dir / f"{pid}.yaml"

    if pid in _LOCKED_ORCH or pid in _LOCKED_RUNTIME:
        _fail(f"{pid!r} is a verbatim-locked profile name — choose another id")
    if out_path.exists() and not args.force:
        _fail(f"{out_path} already exists — pass --force to overwrite", 2)

    body = _to_yaml(profile)
    if not args.confirm:
        print(f"# DRY-RUN — would write to {out_path}\n# (pass --confirm to write)\n")
        print(body)
        return 0
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(out_dir), suffix=".yaml.tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(body)
        os.replace(tmp, out_path)
    except OSError as e:
        _fail(f"write failed: {e}", 1)
    print(f"wrote {args.target} profile: {out_path}")
    if args.target == "repo":
        print("  (grows the orchestration family — commit it; the lint floor "
              "keeps the 5 named + schema-validates this one)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
