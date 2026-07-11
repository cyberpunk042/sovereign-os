#!/usr/bin/env python3
"""scripts/operator/lib/reload-run.py — self-re-exec supervisor for the dev
panel daemons (SDD-203 live-reload, R559).

`make panel` launches every panel daemon THROUGH this wrapper. It runs the
target daemon in THIS process (runpy, so the daemon keeps its own PID and owns
its listening socket) and, when live-reload is enabled, watches the daemon's
OWN source file — plus any repo-local modules it imports — for edits. On a real
change it re-execs itself in place (os.execv: the same process image is
replaced), so the daemon comes back on fresh code with NO external kill, no
Ctrl-C, and no `make panel` rerun. The listening socket is closed by execv and
instantly re-bound by the fresh daemon (http.server sets allow_reuse_address),
so the port gap is a few milliseconds.

This wrapper deliberately covers ONLY the one case that genuinely needs new
code loaded into a running process: an edit to the daemon's own .py. Static
HTML/CSS/JS and shelled-out scripts need no reload at all — the daemons read
them fresh on every request — so those are handled by a browser refresh alone
(the live-reload broker notifies the page; nothing is restarted).

Disabled (SOVEREIGN_OS_LIVERELOAD unset / 0 / no / off) it is a transparent
pass-through — behaviourally identical to `python3 <target> [args…]` — so it is
always safe to route a daemon through it.

Usage:
  reload-run.py <target.py> [args passed verbatim to the target …]

Env:
  SOVEREIGN_OS_LIVERELOAD              1 = watch + self-re-exec; else pass-through
  SOVEREIGN_OS_LIVERELOAD_POLL_MS     mtime poll interval (default 400)
"""
from __future__ import annotations

import os
import runpy
import signal
import sys
import threading
import time
import traceback
from pathlib import Path

# scripts/operator/lib/reload-run.py → parents[3] == repo root.
REPO = Path(__file__).resolve().parents[3]


def _enabled() -> bool:
    return os.environ.get("SOVEREIGN_OS_LIVERELOAD", "").strip().lower() \
        not in ("", "0", "no", "off", "false")


def _watch_mtimes(target: Path) -> dict[Path, float]:
    """mtimes of the target daemon + every already-imported repo-local module.

    Recomputed each poll so modules imported lazily after startup are picked
    up. Cheap: most daemons are stdlib-only, so the set is a handful of files.
    """
    paths: set[Path] = {target}
    for mod in list(sys.modules.values()):
        f = getattr(mod, "__file__", None)
        if not f:
            continue
        p = Path(f)
        if p.suffix != ".py":
            continue
        try:
            p.relative_to(REPO)
        except ValueError:
            continue  # stdlib / site-packages — not ours, never watch
        paths.add(p)
    out: dict[Path, float] = {}
    for p in paths:
        try:
            out[p] = p.stat().st_mtime
        except OSError:
            pass
    return out


def _reexec(target: Path, argv: list[str], why: str) -> None:
    sys.stderr.write(f"[reload-run] {why} → reloading {target.name} in place\n")
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.flush()
        except Exception:
            pass
    # Replace THIS process image; env (incl. SOVEREIGN_OS_LIVERELOAD) is kept.
    os.execv(sys.executable,
             [sys.executable, os.path.abspath(__file__), str(target), *argv])


def _watcher(target: Path, argv: list[str], interval: float) -> None:
    # Let the daemon finish importing + bind before snapshotting the baseline,
    # so its own startup writes never look like an edit.
    time.sleep(1.0)
    base = _watch_mtimes(target)
    while True:
        time.sleep(interval)
        cur = _watch_mtimes(target)
        # Only an EDIT to an already-known file counts. A path we have not seen
        # before is a LAZY IMPORT settling in (e.g. the hub imports urllib inside
        # _proxy on first request) — absorb it silently, never re-exec on it, or
        # we would bounce the daemon mid-request the first time it imports.
        changed = [p for p, m in cur.items() if p in base and m > base[p] + 1e-6]
        for p, m in cur.items():
            base.setdefault(p, m)
        if changed:
            names = ", ".join(sorted({p.name for p in changed}))
            _reexec(target, argv, f"source changed ({names})")


def main() -> int:
    if len(sys.argv) < 2:
        sys.stderr.write("usage: reload-run.py <target.py> [args…]\n")
        return 2
    target = Path(sys.argv[1]).resolve()
    argv = sys.argv[2:]
    if not target.is_file():
        sys.stderr.write(f"[reload-run] target not found: {target}\n")
        return 2
    # Hand the daemon a clean argv, exactly as a direct `python3 <target>` would.
    sys.argv = [str(target), *argv]

    if not _enabled():
        # Transparent pass-through — no watcher, identical to a direct launch.
        runpy.run_path(str(target), run_name="__main__")
        return 0

    interval = max(0.15, int(os.environ.get(
        "SOVEREIGN_OS_LIVERELOAD_POLL_MS", "400")) / 1000.0)
    # A SIGHUP is an explicit "reload now" (the broker / operator may send it).
    try:
        signal.signal(signal.SIGHUP,
                      lambda *_: _reexec(target, argv, "SIGHUP"))
    except (ValueError, OSError):
        pass  # not the main thread on some platforms — non-fatal
    # NON-daemon watcher: it must outlive a crashed daemon so that saving a fix
    # still re-execs us back to life (a syntax error in the daemon must not
    # leave the panel dark forever).
    threading.Thread(target=_watcher, args=(target, argv, interval),
                     name="reload-run-watch", daemon=False).start()

    try:
        runpy.run_path(str(target), run_name="__main__")
    except SystemExit:
        raise  # honour the daemon's own exit code
    except BaseException:  # noqa: BLE001 — surface, then wait for a fix
        traceback.print_exc()
        sys.stderr.write(
            f"[reload-run] {target.name} crashed — waiting for a fix "
            f"(save the file to reload)\n")
        sys.stderr.flush()
        # Fall through: the non-daemon watcher keeps the process alive and will
        # re-exec on the next edit.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
