#!/usr/bin/env python3
"""
scripts/operator/emulate-api.py — HTTP API + webapp for the EMULATE surface:
boot a built sovereign-os image in QEMU, from the panel, with a fully
interactive serial console, VM lifecycle controls, and configurable QEMU
options — a pre-flight cockpit so a broken image is caught in a VM, never
on the USB key.

Modeled on scripts/build/09-image-verify.sh's QEMU invocation (OVMF pflash
pair for the signed UEFI chain · KVM when /dev/kvm is reachable, -cpu max
TCG otherwise · the znver5 kernel needs one of the two). The image itself
stays PRISTINE: the guest drive is attached with `-snapshot`, so all writes
land in a throwaway overlay and the .raw you will flash is never touched.

Interactivity, the stdlib way (this repo has no websocket/xterm and every
API advertises "stdlib-only, zero added deps"): a single background thread
owns the QEMU serial (`-serial stdio`), draining it into a capped scrollback
ring. The console is streamed to the browser one-directionally (chunked
text/plain, live-follow) and keystrokes flow back through POST
/api/emulate/input. The VM lives independently of any console connection —
refresh the page, the VM keeps running; Stop is an explicit action.

Endpoints:
  GET  /                     — the emulate webapp (single file)
  GET  /emulate.json         — images (+ direct-boot artifacts) · host caps
                               (qemu/kvm/ovmf) · defaults · live VM status
  GET  /api/emulate/status   — live VM status (json)
  GET  /api/emulate/console  — the serial console (chunked, live-follow;
                               disconnect does NOT stop the VM)
  GET  /version              — service version + module identity
  GET  /healthz              — liveness (always 200)
  POST /api/emulate/start    — launch the VM with the given options
                               (409 if one is already running)
  POST /api/emulate/input    — send keystrokes: {"data":"ls\n"} or a named
                               key {"key":"enter"|"ctrl-c"|"tab"|…}
  POST /api/emulate/login    — server-side auto-login driver:
                               {"user":"root","password":"…"} — watches the
                               console for the login/password prompt and types
  POST /api/emulate/stop     — stop the VM (kill process group, clean up)

Env vars:
  EMULATE_API_BIND   (default: 127.0.0.1)
  EMULATE_API_PORT   (default: 8123)
"""
from __future__ import annotations

import json
import os
import pty
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

API_BIND = os.environ.get("EMULATE_API_BIND", "127.0.0.1")
API_PORT = int(os.environ.get("EMULATE_API_PORT", "8123"))
VERSION = "0.1.0"

REPO = Path(__file__).resolve().parents[2]
WEBAPP_ROOT = REPO / "webapp"
WEBAPP = WEBAPP_ROOT / "emulate" / "index.html"

STATIC_TYPES = {
    ".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8", ".json": "application/json",
    ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon",
    ".woff2": "font/woff2",
}

# Strip CSI + OSC + lone control bytes so the console pane stays readable
# text (the browser is not a full terminal). Keep \n, \r, \t.
ANSI_RE = re.compile(
    rb"\x1b\[[0-9;?=!]*[A-Za-z]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)?|\x1b[()][AB0]|\x1b[=>]"
)
CTRL_RE = re.compile(rb"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

MEM_RE = re.compile(r"^\d{1,6}[MG]$")
CMDLINE_RE = re.compile(r"^[A-Za-z0-9 _=.,:/@+-]*$")

# Named keys → the bytes a serial console expects.
KEYS = {
    "enter": b"\r", "tab": b"\t", "esc": b"\x1b", "space": b" ",
    "backspace": b"\x7f", "ctrl-c": b"\x03", "ctrl-d": b"\x04",
    "ctrl-a": b"\x01", "ctrl-z": b"\x1a", "ctrl-l": b"\x0c",
    "up": b"\x1b[A", "down": b"\x1b[B", "right": b"\x1b[C", "left": b"\x1b[D",
}


def _run(argv, timeout=6):
    try:
        return subprocess.run(argv, capture_output=True, text=True,
                              timeout=timeout, cwd=REPO).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def _human(n: int) -> str:
    if n <= 0:
        return "unknown"
    f = float(n)
    for u in ["B", "KiB", "MiB", "GiB", "TiB"]:
        if f < 1024 or u == "TiB":
            return f"{f:.0f}{u}" if u == "B" else f"{f:.1f}{u}"
        f /= 1024
    return f"{n}B"


def ovmf_pair():
    """(code, vars_src) for the split OVMF pflash pair, or (None, None).
    Plain variant deliberately (no MS keys → SB off → the operator-signed
    chain still boots) — same choice as 09-image-verify.sh."""
    for code in ("/usr/share/OVMF/OVMF_CODE_4M.fd", "/usr/share/OVMF/OVMF_CODE.fd"):
        if os.path.isfile(code):
            return code, code.replace("CODE", "VARS")
    return None, None


def host_caps() -> dict:
    qemu = shutil.which("qemu-system-x86_64")
    qver = ""
    if qemu:
        out = _run([qemu, "--version"])
        m = re.search(r"version ([0-9.]+)", out)
        qver = m.group(1) if m else "present"
    code, _ = ovmf_pair()
    kvm = os.path.exists("/dev/kvm") and os.access("/dev/kvm", os.W_OK)
    return {
        "qemu": bool(qemu), "qemu_version": qver,
        "kvm": kvm, "ovmf": bool(code), "ovmf_code": code or "",
        "accel_default": "kvm" if kvm else "tcg",
    }


def list_images() -> list[dict]:
    out = []
    bd = REPO / "build"
    if not bd.is_dir():
        return out
    for raw in bd.glob("*/output/*.raw"):
        try:
            st = raw.stat()
        except OSError:
            continue
        outdir = raw.parent
        vmlinuz = next(iter(outdir.glob("*.vmlinuz")), None)
        initrd = next(iter(outdir.glob("*.initrd")), None)
        out.append({
            "path": str(raw.relative_to(REPO)), "abs": str(raw), "name": raw.name,
            "profile": outdir.parent.name, "size_human": _human(st.st_size),
            "mtime": int(st.st_mtime),
            "direct_boot": bool(vmlinuz and initrd),
            "vmlinuz": str(vmlinuz.relative_to(REPO)) if vmlinuz else "",
            "initrd": str(initrd.relative_to(REPO)) if initrd else "",
        })
    out.sort(key=lambda x: x["mtime"], reverse=True)
    return out


DEFAULTS = {
    "mem": "4G", "smp": 2, "accel": "auto", "snapshot": True,
    "no_reboot": True, "boot": "uefi", "cmdline": "",
}


# ─────────────────────────── the VM manager ───────────────────────────
class VM:
    CAP = 2 * 1024 * 1024  # 2 MiB console scrollback

    def __init__(self):
        self.lock = threading.Lock()
        self.cond = threading.Condition(self.lock)
        self.proc: subprocess.Popen | None = None
        self.opts: dict | None = None
        self.argv: list[str] | None = None
        self.started_at: float | None = None
        self.exit_code: int | None = None
        self.log = bytearray()
        self.total = 0            # monotonic count of all bytes ever produced
        self.vars_file: str | None = None
        self.reader: threading.Thread | None = None
        self.master: int | None = None   # PTY master fd bridging the guest serial
        # auto-login driver state, surfaced to the panel so it can show what the
        # login attempt is doing: idle / waiting / sent-username / sent-password
        # / success / incorrect / timeout / no-login-driver
        self.login_status = "idle"

    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def status(self) -> dict:
        with self.lock:
            run = self.running()
            return {
                "running": run,
                "pid": self.proc.pid if self.proc else None,
                "uptime_s": round(time.time() - self.started_at, 1) if (run and self.started_at) else 0,
                "exit_code": self.exit_code,
                "opts": self.opts,
                "console_bytes": self.total,
                "login_status": self.login_status,
            }

    def build_argv(self, opts: dict) -> tuple[list[str], str | None]:
        """(argv, vars_file). Raises ValueError on a bad option. vars_file is
        a throwaway OVMF VARS copy to delete on stop (None for direct boot)."""
        img = opts["_image_abs"]
        mem = opts.get("mem", DEFAULTS["mem"])
        if not MEM_RE.match(mem):
            raise ValueError(f"bad mem {mem!r} (want e.g. 4G / 2048M)")
        try:
            smp = int(opts.get("smp", DEFAULTS["smp"]))
        except (TypeError, ValueError):
            raise ValueError("smp must be an integer")
        if not 1 <= smp <= 64:
            raise ValueError("smp out of range (1-64)")
        accel = opts.get("accel", DEFAULTS["accel"])
        if accel not in ("auto", "kvm", "tcg"):
            raise ValueError("accel must be auto|kvm|tcg")
        boot = opts.get("boot", DEFAULTS["boot"])
        if boot not in ("uefi", "direct"):
            raise ValueError("boot must be uefi|direct")
        cmdline = opts.get("cmdline", "") or ""
        if len(cmdline) > 512 or not CMDLINE_RE.match(cmdline):
            raise ValueError("cmdline has invalid characters or is too long")

        argv = ["qemu-system-x86_64", "-machine", "q35", "-m", mem,
                "-smp", str(smp), "-display", "none",
                "-serial", "stdio", "-monitor", "none"]
        if opts.get("snapshot", True):
            argv.append("-snapshot")
        if opts.get("no_reboot", True):
            argv.append("-no-reboot")
        use_kvm = accel == "kvm" or (accel == "auto" and os.access("/dev/kvm", os.W_OK))
        argv += (["-enable-kvm", "-cpu", "host"] if use_kvm else ["-cpu", "max"])
        argv += ["-drive", f"file={img},format=raw,if=virtio"]

        vars_file = None
        if boot == "direct":
            outdir = Path(img).parent
            vmlinuz = next(iter(outdir.glob("*.vmlinuz")), None)
            initrd = next(iter(outdir.glob("*.initrd")), None)
            if not (vmlinuz and initrd):
                raise ValueError("direct boot needs *.vmlinuz + *.initrd beside the image")
            append = ("root=/dev/vda2 rw console=ttyS0,115200 "
                      "systemd.show_status=1 loglevel=6 " + cmdline).strip()
            argv += ["-kernel", str(vmlinuz), "-initrd", str(initrd), "-append", append]
        else:
            code, vars_src = ovmf_pair()
            if not code:
                raise ValueError("OVMF firmware not found (apt install ovmf) — "
                                 "use direct boot, or install ovmf")
            fd, vars_file = tempfile.mkstemp(prefix="sain-ovmf-vars-", suffix=".fd")
            os.close(fd)
            shutil.copyfile(vars_src, vars_file)
            argv += ["-drive", f"if=pflash,format=raw,readonly=on,file={code}",
                     "-drive", f"if=pflash,format=raw,file={vars_file}"]
        return argv, vars_file

    def start(self, opts: dict):
        with self.lock:
            if self.running():
                raise RuntimeError("a VM is already running — stop it first")
            argv, vars_file = self.build_argv(opts)
            # Back the guest serial with a real PTY, not a plain pipe. QEMU's
            # `-serial stdio` then gets a genuine terminal, so the guest's
            # agetty/login see proper tty semantics — the password prompt (echo
            # off, termios) works and interactive input is delivered. A plain
            # pipe left login stuck at the prompt (verified: pipe boot froze at
            # 'localhost login:', PTY boot reaches a root shell). We drive the
            # master fd for both read (console) and write (keystrokes).
            master, slave = pty.openpty()
            try:
                proc = subprocess.Popen(
                    argv, cwd=REPO, stdin=slave, stdout=slave, stderr=slave,
                    start_new_session=True, close_fds=True)
            finally:
                os.close(slave)
            self.master = master
            self.proc = proc
            self.argv = argv
            self.opts = {k: v for k, v in opts.items() if not k.startswith("_")}
            self.opts["accel_effective"] = "kvm" if "-enable-kvm" in argv else "tcg"
            self.started_at = time.time()
            self.exit_code = None
            self.vars_file = vars_file
            self.log = bytearray()
            self.total = 0
            self.login_status = "idle"
            self.reader = threading.Thread(target=self._read_loop, args=(proc,), daemon=True)
            self.reader.start()
            return proc.pid

    def _read_loop(self, proc):
        master = self.master
        while True:
            try:
                chunk = os.read(master, 65536)
            except OSError:
                # PTY master returns EIO once the slave (QEMU) closes — normal exit
                break
            if not chunk:
                break
            with self.cond:
                self.log += chunk
                if len(self.log) > self.CAP:
                    del self.log[:len(self.log) - self.CAP]
                self.total += len(chunk)
                self.cond.notify_all()
        rc = proc.wait()
        with self.cond:
            self.exit_code = rc
            self.cond.notify_all()
        try:
            os.close(master)
        except OSError:
            pass
        if self.vars_file:
            try:
                os.unlink(self.vars_file)
            except OSError:
                pass

    def write(self, data: bytes) -> bool:
        with self.lock:
            if not self.running() or self.master is None:
                return False
            try:
                os.write(self.master, data)
                return True
            except OSError:
                return False

    def stop(self) -> bool:
        with self.lock:
            proc = self.proc
            if not proc or proc.poll() is not None:
                return False
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except (OSError, ProcessLookupError):
            pass
        return True


VMGR = VM()


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


def assemble_emulate() -> dict:
    return {
        "images": list_images(),
        "caps": host_caps(),
        "defaults": DEFAULTS,
        "vm": VMGR.status(),
    }


# ─────────────────────────── HTTP handler ───────────────────────────
class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass

    def _clean(self, b: bytes) -> bytes:
        return CTRL_RE.sub(b"", ANSI_RE.sub(b"", b))

    def do_GET(self):
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        if path == "/healthz":
            return self._send(200, json.dumps({"ok": True}))
        if path == "/version":
            return self._send(200, json.dumps({"module": "emulate-api", "version": VERSION}))
        if path in ("/emulate.json", "/emulate"):
            return self._send(200, json.dumps(assemble_emulate(), indent=2))
        if path in ("/control-systems", "/control-systems.json"):
            return self._send(200, json.dumps(load_control_systems()))
        if path == "/api/emulate/status":
            return self._send(200, json.dumps(VMGR.status()))
        if path == "/api/emulate/console":
            return self._stream_console()
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

    def _stream_console(self):
        # Send the guest serial bytes RAW (ANSI and all). Cleaning here, per
        # network chunk, split escape sequences across chunk boundaries and
        # leaked garbage like '[01;01H' (the ESC byte stripped, the tail left).
        # The browser strips/renders statefully instead, which never splits a
        # sequence. (Fixes the console garbage reported 2026-07-08.)
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        with VMGR.cond:
            start_offset = VMGR.total - len(VMGR.log)
            tail = bytes(VMGR.log)
            sent = VMGR.total
        try:
            if tail:
                self.wfile.write(tail)
                self.wfile.flush()
            while True:
                with VMGR.cond:
                    while VMGR.total == sent and VMGR.running():
                        VMGR.cond.wait(timeout=2.0)
                    start_offset = VMGR.total - len(VMGR.log)
                    chunk = b""
                    note = b""
                    if VMGR.total > sent:
                        if sent < start_offset:
                            note = (f"\n[… {start_offset - sent} console bytes "
                                    f"elided (scrollback cap) …]\n").encode()
                            chunk = bytes(VMGR.log)
                        else:
                            chunk = bytes(VMGR.log[sent - start_offset:])
                        sent = VMGR.total
                    done = not VMGR.running()
                    ec = VMGR.exit_code
                if note:
                    self.wfile.write(note)
                if chunk:
                    self.wfile.write(chunk)
                    self.wfile.flush()
                if done and VMGR.total == sent:
                    self.wfile.write(f"\n■ VM exited (code {ec})\n".encode())
                    self.wfile.flush()
                    return
        except (BrokenPipeError, ConnectionResetError):
            # client left; the VM keeps running (lifecycle is independent)
            return

    def _read_json_body(self) -> dict | None:
        try:
            n = int(self.headers.get("Content-Length", "0"))
            return json.loads(self.rfile.read(n) or b"{}")
        except (ValueError, OSError):
            return None

    def do_POST(self):
        path = self.path.split("?", 1)[0].rstrip("/")
        if path == "/api/emulate/start":
            return self._start()
        if path == "/api/emulate/input":
            return self._input()
        if path == "/api/emulate/login":
            return self._login()
        if path == "/api/emulate/stop":
            ok = VMGR.stop()
            return self._send(200, json.dumps({"stopped": ok}))
        return self._send(404, json.dumps({"error": "not found", "path": path}))

    def _resolve_image(self, image: str) -> str | None:
        try:
            img_abs = (REPO / image).resolve()
            img_abs.relative_to((REPO / "build").resolve())
        except (ValueError, OSError):
            return None
        if img_abs.suffix != ".raw" or not img_abs.is_file():
            return None
        return str(img_abs)

    def _start(self):
        body = self._read_json_body()
        if body is None:
            return self._send(400, json.dumps({"error": "bad JSON body"}))
        if not shutil.which("qemu-system-x86_64"):
            return self._send(503, json.dumps({
                "error": "qemu-system-x86_64 not installed",
                "fix": "apt install qemu-system-x86 ovmf"}))
        img_abs = self._resolve_image(body.get("image") or "")
        if not img_abs:
            return self._send(400, json.dumps(
                {"error": f"image must be a build/ .raw artifact: {body.get('image')!r}"}))
        opts = dict(DEFAULTS)
        for k in ("mem", "smp", "accel", "snapshot", "no_reboot", "boot", "cmdline"):
            if k in body:
                opts[k] = body[k]
        opts["_image_abs"] = img_abs
        try:
            pid = VMGR.start(opts)
        except ValueError as e:
            return self._send(400, json.dumps({"error": str(e)}))
        except RuntimeError as e:
            return self._send(409, json.dumps({"error": str(e)}))
        except (OSError, subprocess.SubprocessError) as e:
            return self._send(500, json.dumps({"error": f"QEMU launch failed: {e}"}))
        return self._send(200, json.dumps({
            "started": True, "pid": pid, "accel": VMGR.opts.get("accel_effective"),
            "boot": opts.get("boot"),
        }))

    def _input(self):
        body = self._read_json_body()
        if body is None:
            return self._send(400, json.dumps({"error": "bad JSON body"}))
        if "key" in body:
            data = KEYS.get(str(body["key"]).lower())
            if data is None:
                return self._send(400, json.dumps(
                    {"error": f"unknown key {body['key']!r}", "known": sorted(KEYS)}))
        else:
            data = str(body.get("data", "")).encode("utf-8", "replace")
        if not VMGR.running():
            return self._send(409, json.dumps({"error": "no VM is running"}))
        ok = VMGR.write(data)
        return self._send(200 if ok else 500, json.dumps({"sent": ok, "bytes": len(data)}))

    def _login(self):
        """Server-side auto-login: watch the console for the login prompt, type
        the user, then the password when prompted, and REPORT the outcome via
        VMGR.login_status (waiting → sent-username → sent-password → success |
        incorrect | timeout) so the panel can show exactly what happened. The
        password comes from the request (the panel's field) — never baked in."""
        body = self._read_json_body() or {}
        user = str(body.get("user", "root"))
        password = str(body.get("password", ""))
        if not re.fullmatch(r"[a-z_][a-z0-9_-]*", user):
            return self._send(400, json.dumps({"error": f"bad username {user!r}"}))
        if not VMGR.running():
            return self._send(409, json.dumps({"error": "no VM is running"}))

        def strip(b):
            return CTRL_RE.sub(b"", ANSI_RE.sub(b"", b)).decode("utf-8", "replace")

        def driver():
            deadline = time.time() + 150
            # seen=-1 so the FIRST pass inspects the CURRENT buffer without
            # waiting: the login prompt is usually already sitting idle (no new
            # bytes are coming until we type), so blocking on "new output" would
            # hang forever. Only after we've consumed the current state do we
            # wait for the guest's reply (echo + Password:).
            seen = -1
            sent_user = sent_pass = False
            VMGR.login_status = "waiting-for-prompt"
            while time.time() < deadline and VMGR.running():
                with VMGR.cond:
                    while VMGR.total == seen and VMGR.running():
                        VMGR.cond.wait(timeout=1.0)
                    seen = VMGR.total
                    full = strip(bytes(VMGR.log))
                    tail, recent = full[-240:], full[-500:]
                # outcomes take priority over re-prompting
                if sent_pass and re.search(r"(?im)login incorrect", recent):
                    VMGR.login_status = "incorrect"
                    return
                if sent_pass and re.search(r"(?m)(\S+@\S+:.*[#$]|~[#$])\s*$", tail):
                    VMGR.login_status = "success"
                    return
                if not sent_user and re.search(r"login:\s*$", tail):
                    time.sleep(0.4)
                    VMGR.write((user + "\r").encode())
                    sent_user = True
                    VMGR.login_status = "sent-username"
                    time.sleep(0.7)
                elif sent_user and not sent_pass and re.search(r"(?i)password:\s*$", tail):
                    time.sleep(0.4)
                    VMGR.write((password + "\r").encode())
                    sent_pass = True
                    VMGR.login_status = "sent-password"
                    time.sleep(0.7)
            if VMGR.login_status not in ("success", "incorrect"):
                VMGR.login_status = "timeout"

        VMGR.login_status = "starting"
        threading.Thread(target=driver, daemon=True).start()
        return self._send(200, json.dumps({"login_driver": "started", "user": user}))


def main():
    if "--self-check" in sys.argv:
        d = assemble_emulate()
        print(json.dumps({
            "module": "emulate-api", "version": VERSION,
            "images": len(d["images"]),
            "direct_boot_ready": sum(1 for i in d["images"] if i["direct_boot"]),
            "caps": d["caps"], "vm_running": d["vm"]["running"],
        }, indent=2))
        return
    httpd = ThreadingHTTPServer((API_BIND, API_PORT), Handler)
    print(f"emulate-api on http://{API_BIND}:{API_PORT}/ "
          f"(webapp at /, data at /emulate.json, console at "
          f"/api/emulate/console) — Ctrl-C to stop", file=sys.stderr)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        VMGR.stop()


if __name__ == "__main__":
    main()
