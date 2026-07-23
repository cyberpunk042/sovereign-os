#!/usr/bin/env python3
"""scripts/operator/setup.py — the integration/secret collector + first-run flag.

Answers the operator gap: "we have so many needed env vars now and nothing asks
for them." Driven by config/integrations.yaml (the registry), this is the ONE
place that COLLECTS and EDITS the credentials/config every integration needs —
ntfy / Resend / Twilio / webhook / HuggingFace / dashboard-auth / jobs / OPNsense
— and tracks whether first-run setup has happened, for both the CLI and the panel.

Doctrine (docs/src/operator-env-files.md): values live root-owned 0600 in the
named /etc/sovereign-os/<env_file>; the registry + configs carry only NAMES. This
tool writes those files; it NEVER prints a secret's value (status shows set/unset).

Surfaces:
  setup status [--json]     per-integration configured-vs-not + first_setup_done
  setup list                the integrations + fields (names only)
  setup set <NAME> <VALUE>  write a value to its 0600 env file (root)
  setup unset <NAME>        blank a value (root)
  setup wizard              walk the required-but-unset fields interactively (root)
  setup complete            mark first_setup_done=true (root)

Sovereignty: stdlib + yaml only. Read paths need no root; writes need root (they
touch /etc). SOVEREIGN_OS_SETUP_DRYRUN=1 prints the write plan instead of writing
(used by the contract lint + safe rehearsal). SOVEREIGN_OS_ETC overrides /etc/
sovereign-os and SOVEREIGN_OS_INTEGRATIONS overrides the registry path (tests).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    print("setup: python3-yaml not installed", file=sys.stderr)
    sys.exit(2)

SCHEMA_VERSION = "1.0.0"

_REPO = Path(__file__).resolve().parents[2]
REGISTRY = Path(os.environ.get(
    "SOVEREIGN_OS_INTEGRATIONS", str(_REPO / "config" / "integrations.yaml")))
ETC = Path(os.environ.get("SOVEREIGN_OS_ETC", "/etc/sovereign-os"))
STATE_FILE = ETC / "setup.state.json"
DRYRUN = os.environ.get("SOVEREIGN_OS_SETUP_DRYRUN") == "1"


# ── registry ────────────────────────────────────────────────────────
def _registry() -> dict[str, Any]:
    try:
        return yaml.safe_load(REGISTRY.read_text(encoding="utf-8")) or {}
    except OSError as e:
        print(f"setup: cannot read registry {REGISTRY}: {e}", file=sys.stderr)
        raise SystemExit(2)


def _integrations() -> list[dict[str, Any]]:
    return _registry().get("integrations", []) or []


def _field_index() -> dict[str, tuple[dict, dict]]:
    """NAME → (integration, field)."""
    idx: dict[str, tuple[dict, dict]] = {}
    for it in _integrations():
        for f in it.get("fields", []) or []:
            idx[f["name"]] = (it, f)
    return idx


# ── env-file IO ─────────────────────────────────────────────────────
def _env_path(env_file: str) -> Path:
    return ETC / env_file


def _parse_env(path: Path) -> dict[str, str]:
    """KEY=VALUE lines → dict. Tolerant of comments/blanks; strips one layer of
    surrounding quotes. Missing file → {}."""
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            k, v = s.split("=", 1)
            k = k.strip()
            v = v.strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
                v = v[1:-1]
            out[k] = v
    except OSError:
        pass
    return out


def _resolve(name: str, env_file: str, _cache: dict[str, dict[str, str]]) -> str:
    """A field's effective value: the named env file first (the canonical home),
    then the live process env as a fallback. '' when unset."""
    if env_file not in _cache:
        _cache[env_file] = _parse_env(_env_path(env_file))
    v = _cache[env_file].get(name, "")
    if v:
        return v
    return os.environ.get(name, "")


# ── status ──────────────────────────────────────────────────────────
def _integration_status(it: dict, cache: dict) -> dict[str, Any]:
    env_file = it.get("env_file", "")
    fields_out = []
    all_required_set = True
    any_set = False
    for f in it.get("fields", []) or []:
        val = _resolve(f["name"], env_file, cache)
        is_set = bool(val)
        any_set = any_set or is_set
        if f.get("required") and not is_set:
            all_required_set = False
        fields_out.append({
            "name": f["name"],
            "label": f.get("label", f["name"]),
            "kind": f.get("kind", "config"),
            "required": bool(f.get("required")),
            "readonly": bool(f.get("readonly")),
            "set": is_set,
            # NEVER echo a secret; a config value is shown so the panel can prefill.
            "value": (val if f.get("kind") == "config" and not f.get("readonly") else ""),
        })
    has_required = any(f.get("required") for f in it.get("fields", []) or [])
    # "configured": every required field present. An integration with no required
    # fields counts as configured once ANY field is set (operator engaged it).
    configured = all_required_set if has_required else any_set
    return {
        "id": it["id"],
        "label": it.get("label", it["id"]),
        "feature": it.get("feature", ""),
        "summary": it.get("summary", ""),
        "env_file": env_file,
        "doc": it.get("doc", ""),
        "managed_by": it.get("managed_by", ""),
        "configured": configured,
        "fields": fields_out,
    }


def _read_flag() -> dict[str, Any]:
    if STATE_FILE.is_file():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    return {}


def status() -> dict[str, Any]:
    cache: dict[str, dict[str, str]] = {}
    rows = [_integration_status(it, cache) for it in _integrations()]
    flag = _read_flag()
    return {
        "schema_version": SCHEMA_VERSION,
        "first_setup_done": bool(flag.get("first_setup_done")),
        "completed_at": flag.get("completed_at", ""),
        "configured_count": sum(1 for r in rows if r["configured"]),
        "integration_count": len(rows),
        "integrations": rows,
    }


# ── writes (root) ───────────────────────────────────────────────────
def _require_writable() -> None:
    """Writes need a writable ETC. The real /etc/sovereign-os is root-only, so this
    is effectively 'needs root' in production; an operator/test that points
    SOVEREIGN_OS_ETC at a writable dir (or is root) passes without the euid check."""
    if DRYRUN:
        return
    probe = ETC if ETC.exists() else ETC.parent
    if not os.access(probe, os.W_OK):
        print("setup: this write needs root (it edits /etc/sovereign-os/*.env)",
              file=sys.stderr)
        raise SystemExit(2)


def _write_env(env_file: str, updates: dict[str, str]) -> None:
    """Upsert KEY=VALUE into the 0600 /etc/sovereign-os/<env_file>, preserving all
    other lines/comments. Creates the file (with a header) if absent. Atomic."""
    path = _env_path(env_file)
    if DRYRUN:
        for k, v in updates.items():
            shown = "<secret>" if v else "<cleared>"
            print(f"  [dry-run] {path}: {k}={shown}", file=sys.stderr)
        return
    existing_lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    remaining = dict(updates)
    out_lines: list[str] = []
    if not existing_lines:
        out_lines.append(f"# /etc/sovereign-os/{env_file} — sovereign-os integration secrets/config.")
        out_lines.append("# 0600 root-owned. Written by `sovereign-osctl setup set`. Never commit a filled copy.")
    for line in existing_lines:
        s = line.strip()
        if s and not s.startswith("#") and "=" in s:
            k = s.split("=", 1)[0].strip()
            if k in remaining:
                out_lines.append(f"{k}={remaining.pop(k)}")
                continue
        out_lines.append(line)
    for k, v in remaining.items():
        out_lines.append(f"{k}={v}")
    body = "\n".join(out_lines) + "\n"
    ETC.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(ETC), prefix=f".{env_file}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(body)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def set_value(name: str, value: str) -> dict[str, Any]:
    idx = _field_index()
    if name not in idx:
        return {"ok": False, "error": f"unknown variable {name!r}",
                "hint": "sovereign-osctl setup list"}
    it, f = idx[name]
    if f.get("readonly") or it.get("managed_by"):
        return {"ok": False, "error": f"{name} is managed elsewhere",
                "hint": it.get("managed_by") or "not settable via setup"}
    _require_writable()
    _write_env(it["env_file"], {name: value})
    return {"ok": True, "name": name, "integration": it["id"],
            "env_file": it["env_file"], "dryrun": DRYRUN,
            "kind": f.get("kind", "config")}


def unset_value(name: str) -> dict[str, Any]:
    return set_value(name, "")


def _write_flag(done: bool) -> None:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "first_setup_done": done,
        "completed_at": datetime.now(timezone.utc).isoformat(timespec="seconds") if done else "",
    }
    if DRYRUN:
        print(f"  [dry-run] {STATE_FILE}: first_setup_done={done}", file=sys.stderr)
        return
    ETC.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.chmod(STATE_FILE, 0o644)


def complete(done: bool = True) -> dict[str, Any]:
    _require_writable()
    _write_flag(done)
    return {"ok": True, "first_setup_done": done, "dryrun": DRYRUN}


def wizard() -> int:
    """Walk every required-but-unset, settable field and prompt for it."""
    _require_writable()
    cache: dict[str, dict[str, str]] = {}
    todo = []
    for it in _integrations():
        for f in it.get("fields", []) or []:
            if f.get("readonly") or it.get("managed_by"):
                continue
            if f.get("required") and not _resolve(f["name"], it["env_file"], cache):
                todo.append((it, f))
    if not todo:
        print("setup wizard: all required integration values are already set. ✓")
        return 0
    print(f"setup wizard: {len(todo)} required value(s) to fill "
          "(blank = skip; secrets are not echoed)\n")
    for it, f in todo:
        kind = f.get("kind", "config")
        eg = f" (e.g. {f['example']})" if f.get("example") else ""
        prompt = f"  [{it['label']}] {f['label']}{eg}: "
        try:
            if kind == "secret":
                import getpass
                val = getpass.getpass(prompt)
            else:
                val = input(prompt)
        except (EOFError, KeyboardInterrupt):
            print("\nsetup wizard: aborted (nothing further written).")
            return 1
        if val.strip():
            r = set_value(f["name"], val.strip())
            print(f"    → {'set' if r.get('ok') else 'ERROR: ' + str(r.get('error'))}")
    print("\nsetup wizard: done. Run `sovereign-osctl setup status` to review, then "
          "`sovereign-osctl setup complete` to mark first-run setup done.")
    return 0


# ── presentation ────────────────────────────────────────────────────
def _human_status(s: dict[str, Any]) -> None:
    done = s["first_setup_done"]
    print("integration setup")
    print("=================")
    print()
    mark = "✓ done" if done else "✗ not yet"
    extra = f" ({s['completed_at']})" if s.get("completed_at") else ""
    print(f"  first setup: {mark}{extra}")
    print(f"  configured : {s['configured_count']}/{s['integration_count']} integrations")
    print()
    for r in s["integrations"]:
        badge = "✓" if r["configured"] else ("·" if r.get("managed_by") else "✗")
        mgd = "  (managed: " + r["managed_by"] + ")" if r.get("managed_by") else ""
        print(f"  {badge} {r['label']:<34} [{r['feature']}]{mgd}")
        for f in r["fields"]:
            if f["kind"] == "secret":
                state = "set" if f["set"] else ("—" if not f["required"] else "MISSING")
            else:
                state = (f["value"] or ("—" if not f["required"] else "MISSING")) if f["set"] or not f["required"] else "MISSING"
            req = "*" if f["required"] else " "
            print(f"      {req} {f['name']:<38} {state}")
    print()
    print("  set a value:  sudo sovereign-osctl setup set <NAME> <VALUE>")
    print("  guided:       sudo sovereign-osctl setup wizard")
    if not done:
        print("  when ready:   sudo sovereign-osctl setup complete")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="integration credential collector + first-run flag")
    sub = p.add_subparsers(dest="cmd")
    sp = sub.add_parser("status", help="per-integration configured-vs-not + first_setup_done")
    sp.add_argument("--json", action="store_true")
    sub.add_parser("list", help="the integrations + their variable names")
    ss = sub.add_parser("set", help="write a value to its 0600 env file (root)")
    ss.add_argument("name")
    ss.add_argument("value")
    ss.add_argument("--json", action="store_true")
    su = sub.add_parser("unset", help="blank a value (root)")
    su.add_argument("name")
    su.add_argument("--json", action="store_true")
    sub.add_parser("wizard", help="walk the required-but-unset fields interactively (root)")
    sc = sub.add_parser("complete", help="mark first_setup_done=true (root)")
    sc.add_argument("--undo", action="store_true", help="clear the flag instead")
    sc.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    cmd = args.cmd or "status"

    if cmd == "status":
        s = status()
        print(json.dumps(s, indent=2)) if getattr(args, "json", False) else _human_status(s)
        return 0
    if cmd == "list":
        for it in _integrations():
            print(f"{it['id']:<16} {it.get('label','')}  → /etc/sovereign-os/{it.get('env_file','')}")
            for f in it.get("fields", []) or []:
                tag = "secret" if f.get("kind") == "secret" else "config"
                req = "required" if f.get("required") else "optional"
                ro = " [managed elsewhere]" if (f.get("readonly") or it.get("managed_by")) else ""
                print(f"    {f['name']:<40} {tag} · {req}{ro}")
        return 0
    if cmd == "set":
        r = set_value(args.name, args.value)
        if getattr(args, "json", False):
            print(json.dumps(r, indent=2))
        elif r.get("ok"):
            print(f"setup: {args.name} → {r['env_file']}" + (" (dry-run)" if r.get("dryrun") else ""))
        else:
            print(f"setup: error: {r.get('error')} — {r.get('hint','')}", file=sys.stderr)
        return 0 if r.get("ok") else 2
    if cmd == "unset":
        r = unset_value(args.name)
        print(json.dumps(r, indent=2)) if getattr(args, "json", False) else print(
            f"setup: {args.name} cleared" if r.get("ok") else f"setup: {r.get('error')}")
        return 0 if r.get("ok") else 2
    if cmd == "wizard":
        return wizard()
    if cmd == "complete":
        r = complete(done=not getattr(args, "undo", False))
        print(json.dumps(r, indent=2)) if getattr(args, "json", False) else print(
            f"setup: first_setup_done={r['first_setup_done']}" + (" (dry-run)" if r.get("dryrun") else ""))
        return 0 if r.get("ok") else 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
