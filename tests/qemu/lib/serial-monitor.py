#!/usr/bin/env python3
"""tests/qemu/lib/serial-monitor.py — QEMU serial-socket consumer (Q-014).

Connects to a QEMU chardev UNIX socket (created by QEMU with
-chardev socket,path=...,server=on,wait=off) and:

  1) Prints all guest serial output to stdout (so the operator can
     watch the boot in real time).
  2) Optionally writes lines from stdin back to the guest serial
     (for scripted interaction when a getty is present).
  3) Writes every byte received to an append-only log file for
     post-mortem analysis.

Usage:
  python3 serial-monitor.py /tmp/qemu-serial.sock /tmp/serial.log

Exit codes:
  0 — socket closed by QEMU (guest shut down or QEMU exited)
  1 — connection refused / socket not found
"""
from __future__ import annotations

import os
import select
import socket
import sys


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: serial-monitor.py <socket-path> [log-file]", file=sys.stderr)
        return 2

    sock_path = sys.argv[1]
    log_path = sys.argv[2] if len(sys.argv) > 2 else None

    # Wait for QEMU to create the socket (it may take a moment after launch).
    for _ in range(50):
        if os.path.exists(sock_path):
            break
        select.select([], [], [], 0.1)
    else:
        print(f"ERROR socket {sock_path} never appeared", file=sys.stderr)
        return 1

    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.connect(sock_path)
    except ConnectionRefusedError:
        print(f"ERROR connection refused on {sock_path}", file=sys.stderr)
        return 1

    sock.setblocking(False)

    log_fh = open(log_path, "ab") if log_path else None

    # Set stdin to non-blocking so we can forward operator keystrokes.
    if os.isatty(sys.stdin.fileno()):
        import termios, tty  # type: ignore
        tty.setcbreak(sys.stdin.fileno())
        old_settings = termios.tcgetattr(sys.stdin.fileno())
    else:
        old_settings = None

    try:
        while True:
            readable, _, _ = select.select([sock, sys.stdin], [], [], 0.5)
            for src in readable:
                if src is sock:
                    try:
                        data = sock.recv(4096)
                    except OSError:
                        data = b""
                    if not data:
                        return 0
                    sys.stdout.buffer.write(data)
                    sys.stdout.flush()
                    if log_fh:
                        log_fh.write(data)
                        log_fh.flush()
                elif src is sys.stdin:
                    try:
                        data = os.read(sys.stdin.fileno(), 4096)
                    except OSError:
                        data = b""
                    if data:
                        sock.sendall(data)
    except KeyboardInterrupt:
        return 0
    finally:
        if old_settings is not None:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_settings)
        if log_fh:
            log_fh.close()
        sock.close()


if __name__ == "__main__":
    sys.exit(main())
