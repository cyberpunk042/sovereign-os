#!/usr/bin/env python3
"""
scripts/operator/flash-api.py — HTTP API + webapp for the FLASH surface:
write a built sovereign-os image onto a target USB block device, from the
panel, with a device picker, safety gates, and live `dd` progress.

This is the operable sibling of the build-configurator: where that page
BUILDS the image, this one FLASHES it. It never re-implements `dd` — every
byte-writing path shells out to the already-gated CLI:

    sovereign-osctl install image [--plan] <image> --to <device>

which enforces six gates (image sane · target is a whole block device ·
not a partition · not the running root or its parent · SOVEREIGN_OS_-
CONFIRM_DESTROY=YES · interactive/typed confirm). The panel supplies
SOVEREIGN_OS_CONFIRM_DESTROY=YES + SOVEREIGN_OS_NONINTERACTIVE=1 only after
the operator has explicitly ARMED the device in the UI (type-to-confirm),
so the arming moves from the terminal into the panel — the gates do not
weaken, they relocate.

Sovereignty / safety:
  - Loopback-bind by default (127.0.0.1); stdlib-only, zero added deps.
  - The device picker offers ONLY removable/hot-plug disks and never the
    system disks; the server RE-VALIDATES the target before every run
    (defense in depth — the CLI is still the ultimate gate).
  - Real dd needs root; if this daemon is not root it elevates via pkexec
    exactly like the build button. raw `dd` is deliberately NOT in the
    operator sudoers allow-list — flashing stays the gated CLI path.

Endpoints:
  GET  /                    — the flash webapp (single file)
  GET  /flash.json          — images (build output) + block devices
                              (safety-classified) + defaults + root status
  GET  /version             — service version + module identity
  GET  /healthz             — liveness (always 200)
  POST /api/run             — EXECUTE a flash job and stream its log:
                                {"action":"plan"|"flash",
                                 "image":"build/…/sain-01.raw",
                                 "device":"/dev/sda"}
                              One job at a time (409 if busy). "flash"
                              needs root (pkexec when not root).
  POST /api/cancel          — kill the current job (process group)

Env vars:
  FLASH_API_BIND   (default: 127.0.0.1)
  FLASH_API_PORT   (default: 8126)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

API_BIND = os.environ.get("FLASH_API_BIND", "127.0.0.1")
API_PORT = int(os.environ.get("FLASH_API_PORT", "8126"))
VERSION = "0.1.0"

REPO = Path(__file__).resolve().parents[2]
WEBAPP_ROOT = REPO / "webapp"
WEBAPP = WEBAPP_ROOT / "flash" / "index.html"

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
import request_guard as _guard  # noqa: E402
OSCTL = REPO / "scripts" / "sovereign-osctl"

STATIC_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
}
ANSI_RE = re.compile(rb"\x1b\[[0-9;]*[A-Za-z]")

# A target path must look like exactly this before we ever hand it to the
# CLI — anchors the picker's output and blocks anything creative. The CLI
# re-checks it's a real whole-disk block device; this is the first gate.
DEVICE_RE = re.compile(r"^/dev/[a-z]+[0-9]*$|^/dev/nvme[0-9]+n[0-9]+$|^/dev/mmcblk[0-9]+$")


def _run(argv: list[str], timeout: int = 8) -> str:
    try:
        return subprocess.run(
            argv, capture_output=True, text=True, timeout=timeout, cwd=REPO
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def _basename(dev: str) -> str:
    return dev.rsplit("/", 1)[-1]


def _parent_disk(source: str) -> str:
    """Resolve a mount SOURCE (partition / dm / lvm / zfs member) to the
    whole-disk kernel name backing it (e.g. /dev/nvme0n1p2 → nvme0n1)."""
    pk = _run(["lsblk", "-no", "PKNAME", source]).strip().splitlines()
    if pk and pk[0].strip():
        return pk[0].strip()
    return _basename(source)


def protected_disks() -> set[str]:
    """The set of whole-disk kernel names that host anything the running
    system depends on — never offered as a flash target. Built from the
    live mount table + swap, resolved to parent disks."""
    disks: set[str] = set()
    for mp in ("/", "/boot", "/boot/efi", "/home", "/usr", "/var", "/etc"):
        src = _run(["findmnt", "-nr", "-o", "SOURCE", "--target", mp]).strip().splitlines()
        if src and src[0].strip():
            disks.add(_parent_disk(src[0].strip()))
    # active swap devices → parent disks
    for line in _run(["swapon", "--show=NAME", "--noheadings"]).splitlines():
        line = line.strip()
        if line.startswith("/dev/"):
            disks.add(_parent_disk(line))
    disks.discard("")
    return disks


def list_block_devices() -> list[dict]:
    """Whole disks with safety classification. A disk is `flashable` only
    when it is removable/hot-plug AND not a protected system disk."""
    raw = _run(["lsblk", "-J", "-d", "-b", "-o",
                "NAME,SIZE,MODEL,SERIAL,TYPE,RM,HOTPLUG,TRAN,MOUNTPOINTS"])
    try:
        data = json.loads(raw) if raw else {"blockdevices": []}
    except json.JSONDecodeError:
        data = {"blockdevices": []}
    protected = protected_disks()
    # mounts anywhere in each disk's subtree (whole tree, not just -d)
    tree_raw = _run(["lsblk", "-J", "-o", "NAME,MOUNTPOINTS"])
    mounts_by_disk: dict[str, list[str]] = {}
    try:
        for d in json.loads(tree_raw).get("blockdevices", []):
            mps: list[str] = []

            def _walk(node):
                for m in (node.get("mountpoints") or []):
                    if m:
                        mps.append(m)
                for ch in (node.get("children") or []):
                    _walk(ch)
            _walk(d)
            mounts_by_disk[d["name"]] = mps
    except (json.JSONDecodeError, KeyError, TypeError):
        pass

    devs = []
    for d in data.get("blockdevices", []):
        if d.get("type") != "disk":
            continue
        name = d["name"]
        path = f"/dev/{name}"
        removable = bool(d.get("rm")) or bool(d.get("hotplug")) or d.get("tran") == "usb"
        mounts = mounts_by_disk.get(name, [])
        is_protected = name in protected or path in protected
        flashable = removable and not is_protected
        reason = ""
        if not flashable:
            if is_protected:
                reason = "system disk — hosts a live mount; hard-protected"
            elif not removable:
                reason = "fixed (non-removable) disk — not a flash target"
        size_b = int(d.get("size") or 0)
        devs.append({
            "path": path,
            "name": name,
            "model": (d.get("model") or "").strip() or "unknown",
            "serial": (d.get("serial") or "").strip() or "unknown",
            "size_bytes": size_b,
            "size_human": _human(size_b),
            "tran": (d.get("tran") or "").strip() or "unknown",
            "removable": removable,
            "protected": is_protected,
            "flashable": flashable,
            "mounts": mounts,
            "reason": reason,
        })
    devs.sort(key=lambda x: (not x["flashable"], x["name"]))
    return devs


def _human(n: int) -> str:
    if n <= 0:
        return "unknown"
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    f = float(n)
    for u in units:
        if f < 1024 or u == units[-1]:
            return f"{f:.0f}{u}" if u == "B" else f"{f:.1f}{u}"
        f /= 1024
    return f"{n}B"


def list_images() -> list[dict]:
    """Built .raw images under build/*/output, newest first, with size +
    the sha256 recorded alongside (if any)."""
    out = []
    build_dir = REPO / "build"
    if not build_dir.is_dir():
        return out
    for raw in sorted(build_dir.glob("*/output/*.raw")):
        try:
            st = raw.stat()
        except OSError:
            continue
        sums = raw.parent / "sha256sums.txt"
        sha = ""
        if sums.is_file():
            try:
                for line in sums.read_text(errors="replace").splitlines():
                    parts = line.split()
                    if len(parts) == 2 and parts[1].lstrip("*") == raw.name:
                        sha = parts[0]
                        break
            except OSError:
                pass
        out.append({
            "path": str(raw.relative_to(REPO)),
            "abs": str(raw),
            "name": raw.name,
            "profile": raw.parent.parent.name,
            "size_bytes": st.st_size,
            "size_human": _human(st.st_size),
            "mtime": int(st.st_mtime),
            "sha256": sha,
        })
    out.sort(key=lambda x: x["mtime"], reverse=True)
    return out


def assemble_flash() -> dict:
    return {
        "images": list_images(),
        "devices": list_block_devices(),
        "running_as_root": os.geteuid() == 0,
        "pkexec": bool(shutil.which("pkexec")),
        "confirm_env": "SOVEREIGN_OS_CONFIRM_DESTROY=YES",
    }


def load_control_systems() -> dict:
    """Serve config/control-systems.yaml so the inlined control-surface renders
    on this panel's OWN origin (parity with build-configurator / master-
    dashboard). Degrades to an error the surface shows if PyYAML is absent."""
    try:
        import yaml
        data = yaml.safe_load((REPO / "config" / "control-systems.yaml").read_text(encoding="utf-8"))
        return data or {"systems": []}
    except Exception as e:  # read-only graceful degradation
        return {"error": f"control-systems unavailable: {e}"}


RUN_LOCK = threading.Lock()   # serialise STARTS (one flash/plan at a time)
# Detached run: the job writes straight to a log FILE (not the request socket),
# so a client that navigates away doesn't orphan it — /api/run/status +
# /api/run/attach let the panel RE-ATTACH and replay the log so far + follow
# live, exactly like the build console (a flash that survives navigation must
# stay visible + cancellable). start_new_session detaches it from this daemon.
FLASH_STATE_DIR = Path(os.environ.get(
    "SOVEREIGN_OS_FLASH_STATE_DIR",
    Path(tempfile.gettempdir()) / f"sovereign-os-flash-{os.getuid()}"))
FLASH_LOG = FLASH_STATE_DIR / "run.log"
FLASH_STATUS = FLASH_STATE_DIR / "run.json"


def _status_read() -> dict:
    try:
        return json.loads(FLASH_STATUS.read_text())
    except (OSError, ValueError):
        return {}


def _status_write(d: dict) -> None:
    try:
        FLASH_STATE_DIR.mkdir(parents=True, exist_ok=True)
        FLASH_STATUS.write_text(json.dumps(d))
    except OSError:
        pass


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def _run_active() -> bool:
    st = _status_read()
    pid = st.get("pid")
    return bool(st and not st.get("done") and pid and _pid_alive(int(pid)))


def _run_waiter(proc, action: str) -> None:
    """Background waiter — outlives the request. Appends the exit footer to the
    log + marks status done, then releases RUN_LOCK. One daemon thread per run."""
    try:
        rc = proc.wait()
    finally:
        try:
            with open(FLASH_LOG, "ab", buffering=0) as f:
                f.write(f"\n{'✓' if rc == 0 else '✗'} exit code {rc}\n".encode())
        except (OSError, NameError):
            rc = None
        st = _status_read()
        st.update(done=True, exit_code=rc)
        _status_write(st)
        try:
            RUN_LOCK.release()
        except RuntimeError:
            pass


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):  # quiet loopback daemon
        pass

    def do_GET(self):
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        if path == "/healthz":
            return self._send(200, json.dumps({"ok": True}))
        if path == "/version":
            return self._send(200, json.dumps(
                {"module": "flash-api", "version": VERSION}))
        if path in ("/flash.json", "/flash"):
            return self._send(200, json.dumps(assemble_flash(), indent=2))
        if path in ("/control-systems", "/control-systems.json"):
            return self._send(200, json.dumps(load_control_systems()))
        if path == "/api/run/status":
            st = _status_read()
            try:
                size = FLASH_LOG.stat().st_size
            except OSError:
                size = 0
            return self._send(200, json.dumps({
                "running": _run_active(), "action": st.get("action"),
                "device": st.get("device"), "image": st.get("image"),
                "done": st.get("done", not _run_active()),
                "exit_code": st.get("exit_code"), "log_bytes": size,
            }))
        if path == "/api/run/attach":
            return self._stream_log(0)
        if path == "/":
            if WEBAPP.exists():
                return self._send(200, WEBAPP.read_bytes(), "text/html; charset=utf-8")
            return self._send(404, json.dumps({"error": "webapp not found"}))
        try:
            target = (WEBAPP_ROOT / path.lstrip("/")).resolve()
            target.relative_to(WEBAPP_ROOT.resolve())
        except (ValueError, OSError):
            return self._send(404, json.dumps({"error": "not found", "path": path}))
        if target.is_dir():
            target = target / "index.html"
        if target.is_file():
            ctype = STATIC_TYPES.get(target.suffix.lower())
            if ctype:
                return self._send(200, target.read_bytes(), ctype)
        return self._send(404, json.dumps({"error": "not found", "path": path}))

    def _read_json_body(self) -> dict | None:
        try:
            n = int(self.headers.get("Content-Length", "0"))
            return json.loads(self.rfile.read(n) or b"{}")
        except (ValueError, OSError):
            return None

    def _stream_log(self, from_offset: int):
        """Replay FLASH_LOG from `from_offset`, then follow it live until the job
        finishes. Read-only tail — a client disconnect just ends THIS stream and
        never touches the job. Shared by POST /api/run + GET /api/run/attach, so
        the flash console re-attaches to a running job after navigation."""
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        try:
            with open(FLASH_LOG, "rb") as f:
                f.seek(max(0, from_offset))
                dead_since = None
                while True:
                    chunk = f.read(65536)
                    if chunk:
                        self.wfile.write(ANSI_RE.sub(b"", chunk))
                        self.wfile.flush()
                        dead_since = None
                        continue
                    st = _status_read()
                    if st.get("done"):
                        tail = f.read()          # footer written before done=True
                        if tail:
                            self.wfile.write(ANSI_RE.sub(b"", tail))
                            self.wfile.flush()
                        break
                    if not _run_active():
                        if dead_since is None:
                            dead_since = time.time()
                        elif time.time() - dead_since > 3.0:
                            self.wfile.write(b"\n(job ended)\n")
                            self.wfile.flush()
                            break
                    else:
                        dead_since = None
                    time.sleep(0.3)
        except FileNotFoundError:
            try:
                self.wfile.write(b"(no flash job in progress)\n")
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass  # client disconnected — the detached job keeps running

    def do_POST(self):
        path = self.path.split("?", 1)[0].rstrip("/")
        if path == "/api/cancel":
            reject = _guard.guard(self.headers, self.client_address[0],
                                  require_json=False)
            if reject:
                return self._send(reject[0], json.dumps({"error": reject[1]}))
            # Kill via the status-file pid (not an in-memory handle) so cancel
            # works even for a run this request never streamed — a re-attached
            # console, or a job started before a daemon restart.
            st = _status_read()
            pid = st.get("pid")
            if pid and not st.get("done") and _pid_alive(int(pid)):
                try:
                    os.killpg(os.getpgid(int(pid)), 15)
                except (OSError, ProcessLookupError):
                    pass
                return self._send(200, json.dumps({"cancelled": st.get("action")}))
            return self._send(200, json.dumps({"cancelled": None}))
        if path == "/api/run":
            # /api/run writes a physical USB device — refuse browser-driven /
            # non-loopback callers (CSRF) before any device write. The flash
            # console posts application/json from the same origin.
            reject = _guard.guard(self.headers, self.client_address[0])
            if reject:
                return self._send(reject[0], json.dumps({"error": reject[1]}))
            return self._run_action()
        return self._send(404, json.dumps({"error": "not found", "path": path}))

    def _validate(self, body) -> tuple[str, str, str] | None:
        """Return (action, image_abs, device) or None (after sending the
        error). Re-validates every input server-side — never trusts the
        picker. The CLI re-checks too; this is the first gate."""
        action = body.get("action")
        if action not in ("plan", "flash"):
            self._send(400, json.dumps(
                {"error": f"unknown action {action!r}", "allowed": ["plan", "flash"]}))
            return None
        image = body.get("image") or ""
        # image must resolve to a real .raw inside build/ (no traversal)
        try:
            img_abs = (REPO / image).resolve()
            img_abs.relative_to((REPO / "build").resolve())
        except (ValueError, OSError):
            self._send(400, json.dumps({"error": f"image must be a build/ artifact: {image!r}"}))
            return None
        if img_abs.suffix != ".raw" or not img_abs.is_file():
            self._send(400, json.dumps({"error": f"image not found / not a .raw: {image!r}"}))
            return None
        device = body.get("device") or ""
        if not DEVICE_RE.match(device):
            self._send(400, json.dumps({"error": f"bad device path {device!r}"}))
            return None
        # The device must currently be classified flashable (removable +
        # not a protected system disk). Recompute live — the picker's view
        # can be stale, and a system disk must NEVER be a target.
        match = next((d for d in list_block_devices() if d["path"] == device), None)
        if match is None:
            self._send(400, json.dumps({"error": f"device not present: {device}"}))
            return None
        if action == "flash" and not match["flashable"]:
            self._send(403, json.dumps({
                "error": f"REFUSED: {device} is not a safe flash target",
                "detail": match["reason"] or "not removable / protected",
                "hint": "only removable USB/SD disks that host no live mount can be flashed",
            }))
            return None
        return action, str(img_abs), device

    def _run_action(self):
        body = self._read_json_body()
        if body is None:
            return self._send(400, json.dumps({"error": "bad JSON body"}))
        parsed = self._validate(body)
        if parsed is None:
            return
        action, image_abs, device = parsed

        argv = [str(OSCTL), "install", "image"]
        if action == "plan":
            argv += ["--plan", image_abs, "--to", device]
            needs_root = False
        else:
            argv += [image_abs, "--to", device]
            needs_root = True  # the CLI's internal `sudo dd` needs real root

        elevation_note = ""
        if needs_root and os.geteuid() != 0:
            pkexec = shutil.which("pkexec")
            if not pkexec:
                return self._send(403, json.dumps({
                    "error": "flashing needs root and pkexec is unavailable",
                    "fix": "stop this panel, then:  sudo -E scripts/operator/panel.sh "
                           "— the FLASH button works when the server runs as root. "
                           "'plan' works right now without it.",
                }))
            argv = [pkexec, "env",
                    "SOVEREIGN_OS_CONFIRM_DESTROY=YES",
                    "SOVEREIGN_OS_NONINTERACTIVE=1",
                    f"PATH={os.environ.get('PATH', '/usr/sbin:/usr/bin:/sbin:/bin')}",
                    *argv]
            elevation_note = ("  (look for the system password prompt on your "
                              "desktop — polkit/pkexec)\n")

        # Serialise starts; the background waiter releases the lock when the job
        # ends (so a job that outlives this request still holds it).
        if not RUN_LOCK.acquire(blocking=False):
            st = _status_read()
            return self._send(409, json.dumps(
                {"error": f"a flash job is already running: {st.get('action')}",
                 "hint": "re-attach to it via GET /api/run/attach"}))
        try:
            env = dict(os.environ)
            if action == "flash":
                # gate 5 + 6 relocate from terminal → armed panel action
                env["SOVEREIGN_OS_CONFIRM_DESTROY"] = "YES"
                env["SOVEREIGN_OS_NONINTERACTIVE"] = "1"
            FLASH_STATE_DIR.mkdir(parents=True, exist_ok=True)
            verb = "PLAN" if action == "plan" else "FLASH"
            # DETACHED: the job writes to a fresh log FILE (not this socket), so a
            # client disconnect never orphans it — the panel re-attaches via
            # /api/run/attach. start_new_session outlives this daemon too.
            logf = open(FLASH_LOG, "wb", buffering=0)
            logf.write(f"▶ {verb} · {Path(image_abs).name} → {device}\n"
                       f"{elevation_note}\n".encode())
            proc = subprocess.Popen(
                argv, cwd=REPO, env=env, stdout=logf,
                stderr=subprocess.STDOUT, start_new_session=True)
            logf.close()   # the child holds its own dup'd fd now
        except OSError as e:
            try:
                RUN_LOCK.release()
            except RuntimeError:
                pass
            return self._send(500, json.dumps(
                {"error": f"failed to start flash job: {e}"}))
        _status_write({"pid": proc.pid, "action": action, "device": device,
                       "image": Path(image_abs).name, "done": False,
                       "exit_code": None})
        threading.Thread(target=_run_waiter, args=(proc, action),
                         daemon=True).start()
        # Stream THIS client from the top of the fresh log (replay + follow); a
        # disconnect just ends this stream, the detached job keeps writing.
        self._stream_log(0)


def main():
    if "--self-check" in sys.argv:
        data = assemble_flash()
        print(json.dumps({
            "module": "flash-api", "version": VERSION,
            "images": len(data["images"]),
            "devices": len(data["devices"]),
            "flashable": sum(1 for d in data["devices"] if d["flashable"]),
            "running_as_root": data["running_as_root"],
        }, indent=2))
        return
    httpd = ThreadingHTTPServer((API_BIND, API_PORT), Handler)
    root = " · running as ROOT (FLASH armed)" if os.geteuid() == 0 else ""
    print(f"flash-api on http://{API_BIND}:{API_PORT}/ "
          f"(webapp at /, data at /flash.json, run at POST /api/run){root} "
          f"— Ctrl-C to stop", file=sys.stderr)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
