#!/usr/bin/env python3
"""scripts/warp/warp_manage.py — SDD-300 Warp management operator CLI.

The stdlib-only (+ optional PyYAML) operator surface for the Warp management
panel: the warp-solar-system-shaders project (an NVIDIA-Warp procedural
rendering engine — a scene registry + lib packages + example runners).

Reads config/warp-catalog.yaml (the committed, generated catalog — the CI-safe
source of truth for listing + relations). A resident checkout (canonical home
/opt/warp-solar-system-shaders, installed by `warp sync`, SDD-303; or
WARP_SHADERS_ROOT) supplies execution: `render` / `bench` shell the project's
own runners WHEN one is present and degrade to an honest exit-3 banner when it
isn't — the same "never fail on a box without the tool" doctrine SDD-070 uses
for Warp. The committed catalog additionally carries `source_git_rev` so
`status` can report catalog-vs-checkout freshness.

This CLI is the gated verb the cockpit exec-rail (config/control-systems.yaml →
_action_exec.py → sudoers `sovereign-osctl warp render|bench *`) invokes. It
therefore validates every scene name against the catalog AND a strict token
regex, and NEVER builds a shell string (argv lists only).

CLI:
  warp list [--json] [--lib L] [--search Q]   scenes (optionally filtered)
  warp libs [--json]                          the lib packages (+ scene counts, deps)
  warp relations [--json] [--scene S] [--lib L]   the scene->lib / lib->lib graph
  warp info <scene> [--json]                  one scene's detail
  warp status [--json]                        catalog counts + checkout + warp-lang + freshness
  warp render <scene> [--json] [-- [--device D] [--quality Q] [--look L] [--time T] | ARGS...]
  warp bench <scene> [--json] [-- ARGS...]    benchmark a scene (shells bench.py)
  warp renders [--json] [--limit N]           saved cockpit renders (gallery metadata)
  warp sync [--json] [--dest DIR]             clone/pull the canonical checkout at
                                              /opt/warp-solar-system-shaders (SDD-303;
                                              privileged via the exec-rail)

Env (SDD-303):
  SOVEREIGN_WARP_RENDER_STORE  shared render store override; when unset the
                               machine store /var/lib/sovereign-os/warp-renders
                               is used if present, else per-user
                               ~/.local/state/sovereign-os/warp-renders. A fixed
                               machine path keeps the root warp-api daemon (which
                               never sees operator $HOME under ProtectHome) and
                               the user-level exec-rail looking at ONE store —
                               the panel tells the truth about saved renders.

Exit codes: 0 clean, 2 usage / unknown scene / bad option, 3 checkout absent (render/bench).
"""
from __future__ import annotations

import argparse
import base64
import uuid
from datetime import datetime, timezone
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG_FILE = REPO_ROOT / "config" / "warp-catalog.yaml"

# Strict scene-name token — mirrors _action_exec._SAFE_VALUE's spirit (no
# whitespace, no shell metacharacters, no path traversal). Scene names are
# [A-Za-z0-9][A-Za-z0-9_-]*.
_SAFE_SCENE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")

# The machine render store (SDD-303): a fixed, HOME-independent path so the
# root warp-api daemon and the user-level exec-rail resolve the SAME store.
# `warp sync` installs the canonical checkout under /opt too — ProtectHome
# makes anything under an operator $HOME invisible to the daemon.
MACHINE_RENDER_STORE = Path("/var/lib/sovereign-os/warp-renders")


def render_store() -> Path:
    env = os.environ.get("SOVEREIGN_WARP_RENDER_STORE")
    if env:
        return Path(env).expanduser()
    if MACHINE_RENDER_STORE.is_dir():
        return MACHINE_RENDER_STORE
    return Path.home() / '.local/state/sovereign-os/warp-renders'


def render_image(identity: str) -> bytes | None:
    """Read one saved render PNG by its 32-hex id. Never accept a path."""
    if not re.fullmatch(r'[0-9a-f]{32}', identity or ''):
        return None
    try:
        image = render_store() / (identity + '.png')
        if image.is_symlink() or not image.is_file() or image.stat().st_size > 16 * 1024 * 1024:
            return None
        data = image.read_bytes()
    except OSError:
        return None
    return data if data.startswith(b'\x89PNG\r\n\x1a\n') else None


def list_renders(limit: int = 48) -> list[dict]:
    """Gallery metadata for saved cockpit renders, newest first. Metadata only
    — image bytes are served separately (render_image) so listings stay light.
    Manifest-less PNGs (written before the per-render manifest existed) are
    recovered from the filename shape `<scene>-<id8>.png` — the scene name and
    id8 inside the name must agree with the id, else the entry is skipped."""
    out: list[dict] = []
    store = render_store()
    manifested: set[str] = set()
    try:
        manifests = list(store.glob('*.json'))
    except OSError:
        return out
    for jp in manifests:
        if jp.name == 'latest.json':
            continue
        try:
            m = json.loads(jp.read_text())
        except (OSError, ValueError):
            continue
        if not re.fullmatch(r'[0-9a-f]{32}', str(m.get('id', ''))):
            continue
        png = store / (m['id'] + '.png')
        try:
            if png.is_symlink() or not png.is_file():
                continue
            m['bytes'] = png.stat().st_size
        except OSError:
            continue
        m.setdefault('filename', str(m.get('scene', 'scene')) + '-' + m['id'][:8] + '.png')
        manifested.add(m['id'])
        out.append(m)
    # legacy recovery: PNGs with no manifest (pre-SDD-303 stores). Their
    # filename shape `<scene>-<id8>.png` carries the scene; these entries are
    # served by NAME (render_image_by_name), never by id — flagged id_partial.
    try:
        pngs = list(store.glob('*.png'))
    except OSError:
        pngs = []
    for png in pngs:
        if png.is_symlink():
            continue
        m = re.fullmatch(r'([A-Za-z0-9][A-Za-z0-9_-]*)-([0-9a-f]{8})\.png', png.name)
        stem = re.fullmatch(r'([0-9a-f]{32})\.png', png.name)
        if not m and not stem:
            continue
        try:
            st = png.stat()
        except OSError:
            continue
        if stem:
            if stem.group(1) in manifested:
                continue  # already listed with full metadata
            latest = _latest_meta(store)
            if latest and latest.get('id') == stem.group(1):
                # the featured render still carries its manifest — reuse it
                # instead of reporting "?"
                latest.setdefault('bytes', st.st_size)
                latest.setdefault('filename', png.name)
                out.append(latest)
            else:
                # pre-manifest store layout: file named by full id — addressable
                # by id, but the scene name lived only in the transient manifest.
                # Report the scene as "?" rather than guessing (SB-077).
                out.append({'id': stem.group(1), 'scene': '?',
                            'created_at': datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(),
                            'filename': png.name, 'bytes': st.st_size})
        else:
            out.append({'id': m.group(2), 'scene': m.group(1),
                        'created_at': datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(),
                        'filename': png.name, 'bytes': st.st_size, 'id_partial': True})
    out.sort(key=lambda m: str(m.get('created_at', '')), reverse=True)
    return out[:max(1, limit)]


def _latest_meta(store: Path) -> dict | None:
    """The still-current manifest (latest.json), if well-formed — used by
    list_renders so the featured render never shows as scene "?"."""
    try:
        info = json.loads((store / 'latest.json').read_text())
        if re.fullmatch(r'[0-9a-f]{32}', str(info.get('id', ''))):
            return info
    except (OSError, ValueError):
        pass
    return None


def render_image_by_name(filename: str) -> bytes | None:
    """Serve a legacy (manifest-less) render PNG by its gallery filename.
    Strict name regex + containment re-check + PNG magic; never a path."""
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*-[0-9a-f]{8}\.png', filename or ''):
        return None
    try:
        store = render_store().resolve()
        p = (store / filename)
        if p.resolve().parent != store or p.is_symlink() or not p.is_file() \
                or p.stat().st_size > 16 * 1024 * 1024:
            return None
        data = p.read_bytes()
    except OSError:
        return None
    return data if data.startswith(b'\x89PNG\r\n\x1a\n') else None


def latest_render() -> dict | None:
    """Read only our generated PNG; never accept a path from the manifest."""
    try:
        info = json.loads((render_store() / 'latest.json').read_text())
        if not re.fullmatch(r'[0-9a-f]{32}', info.get('id', '')):
            return None
        data = render_image(info['id'])
        if data is None:
            return None
        return {**info, 'image_url': 'data:image/png;base64,' + base64.b64encode(data).decode(),
                'bytes': len(data)}
    except (OSError, ValueError, TypeError, KeyError):
        return None

# Candidate checkout locations, in priority order. WARP_SHADERS_ROOT wins.
_DEFAULT_ROOTS = (
    "/opt/warp-solar-system-shaders",
    "/usr/local/share/warp-solar-system-shaders",
    str(Path.home() / "warp-solar-system-shaders"),
)


def load_catalog() -> dict[str, Any]:
    try:
        import yaml
    except ImportError:
        return {"error": "python3-yaml not installed", "scenes": [], "libs": []}
    try:
        with CATALOG_FILE.open(encoding="utf-8") as f:
            return (yaml.safe_load(f) or {}).get("catalog", {}) or {"scenes": [], "libs": []}
    except OSError as exc:
        return {"error": str(exc), "scenes": [], "libs": []}


def scenes() -> list[dict[str, Any]]:
    return load_catalog().get("scenes", []) or []


def libs() -> list[dict[str, Any]]:
    return load_catalog().get("libs", []) or []


def find_scene(name: str) -> dict[str, Any] | None:
    return next((s for s in scenes() if s["name"] == name), None)


def shaders_root() -> Path | None:
    """The resident warp-solar-system-shaders checkout, or None."""
    env = os.environ.get("WARP_SHADERS_ROOT")
    candidates = [env] if env else []
    candidates += list(_DEFAULT_ROOTS)
    for c in candidates:
        if not c:
            continue
        p = Path(c).expanduser()
        if (p / "render.py").is_file() and (p / "warp_shaders").is_dir():
            return p
    return None


def warp_installed() -> bool:
    try:
        import importlib.util
        return importlib.util.find_spec("warp") is not None
    except (ImportError, ValueError):
        return False


def checkout_rev(root: Path | None) -> str | None:
    """HEAD of the resident checkout — the live half of the freshness check
    (the committed catalog carries the rev it was generated from). None when
    unresolvable: the panel then reports UNKNOWN, never a guess."""
    if root is None:
        return None
    try:
        r = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                           capture_output=True, text=True, timeout=10, check=False)
        rev = r.stdout.strip()
        return rev if re.fullmatch(r"[0-9a-f]{40}", rev) else None
    except (OSError, subprocess.SubprocessError):
        return None


# ── read commands ──────────────────────────────────────────────────────────

def cmd_list(json_out: bool, lib: str | None, search: str | None) -> int:
    ss = scenes()
    if lib:
        ss = [s for s in ss if lib in s.get("libs", [])]
    if search:
        q = search.lower()
        ss = [s for s in ss if q in s["name"].lower() or q in s.get("summary", "").lower()]
    if json_out:
        print(json.dumps({"scenes": ss, "count": len(ss)}, indent=2))
        return 0
    filt = (f" · lib={lib}" if lib else "") + (f" · search={search!r}" if search else "")
    print(f"── SDD-300 warp scenes ({len(ss)}){filt} ──")
    for s in ss:
        print(f"  {s['name']:<22} [{','.join(s.get('libs', [])) or '-'}]  {s.get('summary', '')}")
    return 0


def cmd_libs(json_out: bool) -> int:
    ls = libs()
    if json_out:
        print(json.dumps({"libs": ls, "count": len(ls)}, indent=2))
        return 0
    print(f"── SDD-300 warp libs ({len(ls)}) ──")
    for lib in sorted(ls, key=lambda x: -x["scene_count"]):
        deps = ",".join(lib.get("depends_on", [])) or "-"
        print(f"  {lib['id']:<16} {lib['kind']:<8} scenes={lib['scene_count']:<4} "
              f"deps=[{deps}]  {lib.get('summary', '')}")
    return 0


def cmd_relations(json_out: bool, scene: str | None, lib: str | None) -> int:
    scene_edges = [{"from": s["name"], "to": s.get("libs", [])}
                   for s in scenes()
                   if (not scene or s["name"] == scene) and (not lib or lib in s.get("libs", []))]
    lib_edges = [{"from": lb["id"], "to": lb.get("depends_on", [])}
                 for lb in libs() if (not lib or lb["id"] == lib)]
    payload = {"scene_to_lib": scene_edges, "lib_to_lib": lib_edges}
    if json_out:
        print(json.dumps(payload, indent=2))
        return 0
    print("── SDD-300 warp relations · scene → lib ──")
    for e in scene_edges:
        print(f"  {e['from']:<22} → {', '.join(e['to']) or '-'}")
    print("\n── lib → lib ──")
    for e in lib_edges:
        print(f"  {e['from']:<16} → {', '.join(e['to']) or '-'}")
    return 0


def cmd_info(name: str, json_out: bool) -> int:
    s = find_scene(name)
    if s is None:
        print(f"error: unknown scene '{name}' (see `warp list`)", file=sys.stderr)
        return 2
    if json_out:
        print(json.dumps(s, indent=2))
        return 0
    print(f"── scene: {s['name']} ──")
    print(f"  file:    {s['file']}")
    print(f"  libs:    {', '.join(s.get('libs', [])) or '-'}")
    if s.get("multi"):
        print("  multi:   this module exposes several scenes (see render.py --list)")
    print(f"  summary: {s.get('summary', '')}")
    return 0


def cmd_status(json_out: bool) -> int:
    cat = load_catalog()
    root = shaders_root()
    cat_rev = cat.get("source_git_rev")
    chk_rev = checkout_rev(root)
    freshness = "unknown"
    if cat_rev and chk_rev:
        freshness = "fresh" if cat_rev == chk_rev else "stale"
    payload = {
        "scenes": len(cat.get("scenes", [])),
        "libs": len(cat.get("libs", [])),
        "project": cat.get("project"),
        "checkout_resident": root is not None,
        "checkout_path": str(root) if root else None,
        "warp_installed": warp_installed(),
        "catalog_git_rev": cat_rev,
        "checkout_git_rev": chk_rev,
        "catalog_freshness": freshness,
        "render_store": str(render_store()),
        "renders": len(list_renders(limit=200)),
        "latest_render": latest_render(),
    }
    if json_out:
        print(json.dumps(payload, indent=2))
        return 0
    print("── SDD-300 warp · status ──")
    print(f"  catalog:   {payload['scenes']} scenes · {payload['libs']} libs "
          f"({payload['project']}) · freshness={freshness}")
    if root:
        print(f"  checkout:  resident at {root}")
    else:
        print("  checkout:  NOT resident — `sovereign-osctl warp sync` installs "
              f"the canonical checkout at {_DEFAULT_ROOTS[0]}")
    print(f"  warp-lang: {'installed' if payload['warp_installed'] else 'NOT installed'}")
    print(f"  renders:   {payload['renders']} saved in {payload['render_store']}")
    return 0


# ── execute commands (the gated verbs) ──────────────────────────────────────

def _validate_scene(name: str) -> str | None:
    """Return an error string if the scene name is unsafe or unknown, else None."""
    if not _SAFE_SCENE.fullmatch(name):
        return f"scene name {name!r} rejected (unsafe token)"
    if find_scene(name) is None:
        return f"unknown scene {name!r} (see `warp list`)"
    return None


def _absent_banner(verb: str, scene: str, json_out: bool) -> int:
    src = load_catalog().get("source", "the warp-solar-system-shaders repo")
    msg = (f"warp {verb}: the warp-solar-system-shaders checkout is not resident on "
           f"this host — nothing to run. Obtain it (git clone {src}) and set "
           f"WARP_SHADERS_ROOT, or install it to one of {list(_DEFAULT_ROOTS)}.")
    if json_out:
        print(json.dumps({"verb": verb, "scene": scene, "ran": False,
                          "reason": "checkout-absent", "hint": msg}, indent=2))
    else:
        print(f"── warp {verb} · {scene} ──")
        print(f"  {msg}")
    return 3


def _run_runner(runner: str, argv: list[str], json_out: bool, verb: str, scene: str) -> int:
    root = shaders_root()
    if root is None:
        return _absent_banner(verb, scene, json_out)
    cmd = [sys.executable, str(root / runner), *argv]
    try:
        rc = subprocess.run(cmd, cwd=str(root), check=False).returncode
    except OSError as exc:
        print(f"error: cannot launch {runner}: {exc}", file=sys.stderr)
        return 1
    if json_out:
        print(json.dumps({"verb": verb, "scene": scene, "ran": True,
                          "runner": runner, "returncode": rc}, indent=2))
    return rc


# Structured render options (SDD-303 "real controls"): the cockpit render card
# sends these; they are validated HERE (whitelist + numeric) before reaching
# render.py — the same defense-in-depth posture as scene validation. Anything
# unrecognized falls through to the legacy `-- ARGS` passthrough semantics.
_RENDER_ENUMS = {
    "--device": {"auto", "cpu", "cuda"},
    "--quality": {"auto", "low", "medium", "high", "ultra"},
    "--look": {"clean", "cinematic", "film", "dreamy", "crisp"},
}


def _parse_render_opts(extra: list[str]) -> tuple[dict[str, str], list[str], str | None]:
    """Split runner extras into (validated structured opts, passthrough args,
    error). A recognized flag with a bad value is an ERROR (never silently
    passed through), so the exec-rail can't smuggle arbitrary argv."""
    opts: dict[str, str] = {}
    passthrough: list[str] = []
    i = 0
    while i < len(extra):
        tok = extra[i]
        if tok in _RENDER_ENUMS:
            if i + 1 >= len(extra) or extra[i + 1].startswith("-"):
                return {}, [], f"{tok} requires a value"
            val = extra[i + 1]
            if val not in _RENDER_ENUMS[tok]:
                return {}, [], f"{tok}={val!r} not in {sorted(_RENDER_ENUMS[tok])}"
            opts[tok] = val
            i += 2
            continue
        if tok == "--time":
            if i + 1 >= len(extra) or (extra[i + 1].startswith("-") and not re.fullmatch(r"-?[0-9.]+", extra[i + 1])):
                return {}, [], "--time requires a number"
            try:
                t = float(extra[i + 1])
            except ValueError:
                return {}, [], f"--time={extra[i + 1]!r} is not a number"
            if t < 0:
                return {}, [], "--time must be >= 0"
            opts[tok] = extra[i + 1]
            i += 2
            continue
        passthrough.append(tok)
        i += 1
    return opts, passthrough, None


def cmd_render(scene: str, json_out: bool, extra: list[str]) -> int:
    err = _validate_scene(scene)
    if err:
        print(f"error: {err}", file=sys.stderr)
        return 2
    opts, passthrough, err = _parse_render_opts(extra)
    if err:
        print(f"error: {err}", file=sys.stderr)
        return 2
    if passthrough:  # Explicit CLI outputs/animations retain their original semantics.
        return _run_runner("render.py", ["--scene", scene, *extra], json_out, "render", scene)
    if shaders_root() is None:
        return _absent_banner('render', scene, json_out)
    store = render_store()
    store.mkdir(parents=True, exist_ok=True, mode=0o770)
    try:
        os.chmod(store, 0o770)  # shared store: the daemon must read what the rail writes
    except OSError:
        pass
    identity = uuid.uuid4().hex
    output = store / (identity + '.png')
    runner_args = ['--scene', scene]
    for flag in ("--device", "--quality", "--look", "--time"):
        if flag in opts:
            runner_args += [flag, opts[flag]]
    runner_args += ['--out', str(output)]
    rc = _run_runner('render.py', runner_args, json_out, 'render', scene)
    if rc:
        return rc
    if not output.is_file() or not output.read_bytes().startswith(b'\x89PNG\r\n\x1a\n'):
        print('Render returned success but produced no valid PNG.', file=sys.stderr)
        return 4
    metadata = {'id': identity, 'scene': scene, 'created_at': datetime.now(timezone.utc).isoformat(),
                'filename': scene + '-' + identity[:8] + '.png'}
    if opts:  # so the gallery captions what produced each frame
        metadata['opts'] = {k.lstrip('-'): v for k, v in opts.items()}
    pending = store / (identity + '.json')
    pending.write_text(json.dumps(metadata))
    pending.replace(store / 'latest.json')
    print('Render saved; preview available in the Warp cockpit.')
    return 0


def cmd_bench(scene: str, json_out: bool, extra: list[str]) -> int:
    err = _validate_scene(scene)
    if err:
        print(f"error: {err}", file=sys.stderr)
        return 2
    return _run_runner("bench.py", [scene, *extra], json_out, "bench", scene)


# ── gallery + sync (SDD-303) ────────────────────────────────────────────

def cmd_renders(json_out: bool, limit: int) -> int:
    rs = list_renders(limit)
    if json_out:
        print(json.dumps({"renders": rs, "count": len(rs), "store": str(render_store())}, indent=2))
        return 0
    print(f"── SDD-303 warp renders ({len(rs)} · store {render_store()}) ──")
    for m in rs:
        opts = " · " + " ".join(f"{k}={v}" for k, v in (m.get("opts") or {}).items()) if m.get("opts") else ""
        print(f"  {m.get('created_at', '?')}  {m.get('scene', '?'):<22} "
              f"{round(m.get('bytes', 0) / 1024)} KB{opts}")
    if not rs:
        print("  none yet — `warp render <scene>` saves into the store above")
    return 0


def cmd_sync(dest: str | None, json_out: bool) -> int:
    """Clone (or ff-pull) the canonical shaders checkout at /opt/warp-solar-system-shaders
    — the ProtectHome-visible location both daemons and the exec-rail agree on
    (SDD-300 Q-300-D: vendor-by-checkout, not a git submodule). Privileged via
    the exec-rail's warp-sync control + sudoers; as an ordinary user this says
    so honestly instead of failing obscurely."""
    root = Path(dest).expanduser() if dest else Path(_DEFAULT_ROOTS[0])
    src = load_catalog().get("source") or "https://github.com/cyberpunk042/warp-solar-system-shaders"
    if not re.fullmatch(r"https://github\.com/[A-Za-z0-9._-]+/[A-Za-z0-9._-]+", src):
        print(f"error: refusing sync — catalog source {src!r} is not a https GitHub URL",
              file=sys.stderr)
        return 2
    if (root / ".git").is_dir():
        argv = ["git", "-C", str(root), "pull", "--ff-only"]
        verb = "pull"
    elif root.exists() and any(root.iterdir()):
        print(f"error: {root} exists but is not a git checkout — refusing to touch it",
              file=sys.stderr)
        return 2
    else:
        argv = ["git", "clone", src, str(root)]
        verb = "clone"
    try:
        rc = subprocess.run(argv, check=False).returncode
    except OSError as exc:
        print(f"error: cannot run git: {exc}", file=sys.stderr)
        return 1
    if rc != 0 and os.geteuid() != 0:
        print(f"hint: {root} usually needs elevation — the cockpit uses the "
              "warp-sync control (`sovereign-osctl warp sync` via sudo).", file=sys.stderr)
    if json_out:
        print(json.dumps({"verb": "sync", "action": verb, "dest": str(root),
                          "source": src, "returncode": rc}, indent=2))
    elif rc == 0:
        print(f"warp sync: checkout {verb} complete at {root} — regenerate the "
              "catalog with: WARP_SHADERS_ROOT=" + str(root) +
              " python3 scripts/warp/gen_catalog.py")
    return rc


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="SDD-300 Warp management operator CLI.")
    sub = p.add_subparsers(dest="cmd")

    sp = sub.add_parser("list")
    sp.add_argument("--json", action="store_true")
    sp.add_argument("--lib")
    sp.add_argument("--search")

    for name in ("libs", "status"):
        s = sub.add_parser(name)
        s.add_argument("--json", action="store_true")

    sr = sub.add_parser("relations")
    sr.add_argument("--json", action="store_true")
    sr.add_argument("--scene")
    sr.add_argument("--lib")

    si = sub.add_parser("info")
    si.add_argument("scene")
    si.add_argument("--json", action="store_true")

    for name in ("render", "bench"):
        se = sub.add_parser(name)
        se.add_argument("scene")
        se.add_argument("--json", action="store_true")
        se.add_argument("rest", nargs=argparse.REMAINDER,
                        help="structured opts (--device/--quality/--look/--time) or "
                             "extra args passed through to the runner")

    sd = sub.add_parser("renders")
    sd.add_argument("--json", action="store_true")
    sd.add_argument("--limit", type=int, default=48)

    ss = sub.add_parser("sync")
    ss.add_argument("--json", action="store_true")
    ss.add_argument("--dest",
                    help=f"checkout destination (default {_DEFAULT_ROOTS[0]})")

    args = p.parse_args(argv)
    cmd = args.cmd or "list"

    if cmd == "list":
        return cmd_list(args.json, args.lib, args.search)
    if cmd == "libs":
        return cmd_libs(args.json)
    if cmd == "relations":
        return cmd_relations(args.json, args.scene, args.lib)
    if cmd == "info":
        return cmd_info(args.scene, args.json)
    if cmd == "status":
        return cmd_status(args.json)
    if cmd == "render":
        return cmd_render(args.scene, args.json, args.rest or [])
    if cmd == "bench":
        return cmd_bench(args.scene, args.json, args.rest or [])
    if cmd == "renders":
        return cmd_renders(args.json, args.limit)
    if cmd == "sync":
        return cmd_sync(args.dest, args.json)
    p.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
