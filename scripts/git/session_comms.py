#!/usr/bin/env python3
"""
scripts/git/session_comms.py — the parallel-session communication protocol
(SDD-981): a message board so each session can talk to another session, to the
operator, and the operator back to any session.

WHY
---
SDD-980 gave sessions an identity (`docs/sdd/SESSIONS.md`) and a resolver that
leaves notes in an append-only ledger. This turns that seed into a real,
bidirectional channel: addressed messages, threads (reply/ack), and a derived
inbox — all collision-safe across the parallel branches.

DESIGN ("done right", collision-safe)
-------------------------------------
* **One message = one line.** The board `docs/sdd/MESSAGES.md` is a Markdown
  table; each row is a self-contained record. Two sessions on two branches both
  appending a row at EOF produce non-overlapping additions, so `.gitattributes
  merge=union` keeps BOTH with no conflict, order-independent.
* **Append-only, no mutation.** "Read"/"answered" is never a mutable flag (a
  flag edit would conflict under union). It is DERIVED by replaying the log: a
  message addressed to X is OPEN until X posts a reply whose `re` points at it.
* **Globally-unique ids without coordination.** `msg-id = <from>-<utcstamp>-<rand8>`
  so no two sessions can mint the same id.
* **Identity from the branch.** The current git branch is matched against the
  `branch` glob in `SESSIONS.md` to resolve `whoami` — the same registry the
  SDD-980 resolver trusts.

RECORD (7 columns, pipes in text escaped `\\|`, newlines flattened to ` / `):

    | msg-id | utc | from | to | re | subject | body |

`from` / `to` are a registered session-id, `operator`, or `all` (broadcast).
`re` is an in-reply-to msg-id or empty.

COMMANDS
--------
  whoami                                  resolve this branch → session-id
  post   --to WHO [--re ID] --subject S --body B [--from WHO]
  reply  ID --body B [--to WHO] [--from WHO]        (re defaults to ID)
  ack    ID [--from WHO]                            (a terse reply "ack")
  inbox  [--for WHO] [--all]              messages addressed to WHO (default:
                                          whoami), OPEN first; --all incl answered
  thread ID                               a message + its reply chain
  list   [--from WHO] [--to WHO]          filtered raw view

Stdlib only (argparse, re, uuid, datetime, fnmatch, pathlib).
"""
from __future__ import annotations

import argparse
import fnmatch
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SDD_DIR = REPO / "docs" / "sdd"
SESSIONS = SDD_DIR / "SESSIONS.md"
BOARD = SDD_DIR / "MESSAGES.md"

SPECIAL = ("operator", "all")

_SESSION_ROW_RE = re.compile(
    r"^\|\s*([a-z0-9-]+)\s*\|\s*\d+\s*[–-]\s*\d+\s*\|[^|]*\|\s*`?([^|`]+?)`?\s*\|", re.M
)
_MSG_ROW_RE = re.compile(r"^\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|"
                         r"\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|\s*(.*?)\s*\|\s*$")

BOARD_HEADER = """# Session message board (SDD-981)

> **Bidirectional communication between the parallel sessions and the operator.**
>
> Append-only, one message per row, `.gitattributes merge=union` — so any session
> on any branch (and the operator) can post, and every branch keeps every message
> across merges with no conflict. "Answered" is DERIVED (a message is open until
> its addressee posts a reply whose `re` points at it) — never a mutable flag.
>
> Post/read with `scripts/git/session_comms.py` (`post` / `reply` / `ack` /
> `inbox` / `thread` / `list` / `whoami`). `from`/`to` are a session-id from
> `docs/sdd/SESSIONS.md`, `operator`, or `all` (broadcast). Detail too long for
> one line lives in a referenced SDD/file; the body stays single-line.

| msg-id | utc | from | to | re | subject | body |
|---|---|---|---|---|---|---|
"""


# --- ansi -------------------------------------------------------------------
def _c(code: str) -> str:
    return f"\033[{code}m" if sys.stdout.isatty() else ""


BOLD, DIM, YLW, GRN, RST = _c("1"), _c("2"), _c("33"), _c("32"), _c("0")


# --- identity ---------------------------------------------------------------
def _session_branches() -> dict[str, str]:
    """session-id → branch glob, from SESSIONS.md."""
    if not SESSIONS.is_file():
        return {}
    out = {}
    for m in _SESSION_ROW_RE.finditer(SESSIONS.read_text(encoding="utf-8")):
        out[m.group(1)] = m.group(2).strip().strip("`")
    return out


def _current_branch() -> str:
    r = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--abbrev-ref", "HEAD"],
                       capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def whoami() -> str:
    branch = _current_branch()
    for sid, glob in _session_branches().items():
        if fnmatch.fnmatch(branch, glob) or fnmatch.fnmatch(branch, f"*{glob}*"):
            return sid
    return "unknown"


def _known_recipients() -> set[str]:
    return set(_session_branches()) | set(SPECIAL)


# --- board io ---------------------------------------------------------------
def _esc(s: str) -> str:
    # A literal `|` would break the table column split; encode it reversibly as
    # an HTML entity (Markdown renders it as `|`). Newlines flatten to ` / ` so a
    # message is always one row.
    return (s.replace("|", "&#124;")
             .replace("\r", " ").replace("\n", " / ").strip())


def _unesc(s: str) -> str:
    return s.replace("&#124;", "|")


class Msg:
    __slots__ = ("id", "utc", "frm", "to", "re", "subject", "body")

    def __init__(self, mid, utc, frm, to, re_, subject, body):
        self.id, self.utc, self.frm, self.to = mid, utc, frm, to
        self.re, self.subject, self.body = re_, subject, body


def _load() -> list[Msg]:
    if not BOARD.is_file():
        return []
    msgs = []
    for line in BOARD.read_text(encoding="utf-8").splitlines():
        m = _MSG_ROW_RE.match(line)
        if not m:
            continue
        cells = [c.strip() for c in m.groups()]
        if cells[0] in ("msg-id", "---") or set(cells[0]) <= {"-"}:
            continue
        msgs.append(Msg(cells[0], cells[1], cells[2], cells[3],
                        cells[4], _unesc(cells[5]), _unesc(cells[6])))
    return msgs


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _mint_id(frm: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"{frm}-{stamp}-{uuid.uuid4().hex[:8]}"


def _append(msg: Msg) -> None:
    if not BOARD.is_file():
        BOARD.write_text(BOARD_HEADER, encoding="utf-8")
    row = (f"| {msg.id} | {msg.utc} | {msg.frm} | {msg.to} | {msg.re} | "
           f"{_esc(msg.subject)} | {_esc(msg.body)} |\n")
    with BOARD.open("a", encoding="utf-8") as fh:
        fh.write(row)


# --- derived state ----------------------------------------------------------
def _addressed_to(msgs: list[Msg], who: str) -> list[Msg]:
    return [m for m in msgs if m.to == who or m.to == "all"]


def _is_answered(msgs: list[Msg], msg: Msg, who: str) -> bool:
    """Answered = `who` posted any message whose `re` points at msg.id."""
    return any(r.re == msg.id and r.frm == who for r in msgs)


# --- commands ---------------------------------------------------------------
def _resolve_from(arg_from: str | None) -> str:
    frm = arg_from or whoami()
    if frm == "unknown":
        sys.exit("error: could not resolve your session from the branch — pass --from "
                 "<session-id|operator> (see docs/sdd/SESSIONS.md).")
    return frm


def _validate_recipient(who: str) -> None:
    known = _known_recipients()
    if who not in known:
        sys.exit(f"error: unknown recipient '{who}'. Known: {', '.join(sorted(known))}. "
                 f"Register the session in docs/sdd/SESSIONS.md first.")


def cmd_post(a) -> int:
    frm = _resolve_from(a.from_)
    _validate_recipient(a.to)
    if a.re:
        if not any(m.id == a.re for m in _load()):
            sys.exit(f"error: --re {a.re} references no known message id.")
    msg = Msg(_mint_id(frm), _now(), frm, a.to, a.re or "", a.subject or "", a.body or "")
    _append(msg)
    print(f"{GRN}posted{RST} {msg.id}  ({frm} → {a.to})")
    return 0


def cmd_reply(a) -> int:
    msgs = _load()
    parent = next((m for m in msgs if m.id == a.id), None)
    if not parent:
        sys.exit(f"error: no message with id {a.id}.")
    frm = _resolve_from(a.from_)
    to = a.to or (parent.frm if parent.frm not in SPECIAL or parent.frm == "operator" else parent.frm)
    _validate_recipient(to)
    subject = a.subject or (f"Re: {parent.subject}" if parent.subject else "Re:")
    msg = Msg(_mint_id(frm), _now(), frm, to, a.id, subject, a.body or "")
    _append(msg)
    print(f"{GRN}replied{RST} {msg.id}  ({frm} → {to}, re {a.id})")
    return 0


def cmd_ack(a) -> int:
    a.to = None
    a.subject = "ACK"
    a.body = a.body or "acknowledged"
    return cmd_reply(a)


def cmd_inbox(a) -> int:
    msgs = _load()
    who = a.for_ or whoami()
    if who == "unknown":
        sys.exit("error: could not resolve your session — pass --for <session-id|operator>.")
    mine = _addressed_to(msgs, who)
    open_, answered = [], []
    for m in mine:
        (answered if _is_answered(msgs, m, who) else open_).append(m)
    print(f"{BOLD}inbox for {who}{RST} — {len(open_)} open, {len(answered)} answered")
    _print_list(open_, who, msgs, tag="OPEN")
    if a.all_:
        _print_list(answered, who, msgs, tag="answered")
    elif answered:
        print(f"{DIM}  … {len(answered)} answered (use --all to show){RST}")
    return 1 if open_ else 0


def cmd_thread(a) -> int:
    msgs = _load()
    root = next((m for m in msgs if m.id == a.id), None)
    if not root:
        sys.exit(f"error: no message with id {a.id}.")
    # walk up to the true root, then print the whole chain in time order
    by_id = {m.id: m for m in msgs}
    while root.re and root.re in by_id:
        root = by_id[root.re]
    chain = [m for m in msgs if _in_thread(m, root.id, by_id)]
    chain.sort(key=lambda m: m.utc)
    print(f"{BOLD}thread {root.id}{RST}")
    for m in chain:
        indent = "  " if m.id != root.id else ""
        print(f"{indent}{DIM}{m.utc}{RST} {BOLD}{m.frm} → {m.to}{RST}: "
              f"{m.subject}  {DIM}[{m.id}]{RST}")
        print(f"{indent}    {m.body}")
    return 0


def _in_thread(m: Msg, root_id: str, by_id: dict) -> bool:
    cur = m
    seen = set()
    while cur:
        if cur.id == root_id:
            return True
        if cur.id in seen or not cur.re:
            return False
        seen.add(cur.id)
        cur = by_id.get(cur.re)
    return False


def cmd_list(a) -> int:
    msgs = _load()
    if a.from_:
        msgs = [m for m in msgs if m.frm == a.from_]
    if a.to:
        msgs = [m for m in msgs if m.to == a.to]
    _print_list(msgs, None, _load())
    return 0


def cmd_whoami(a) -> int:
    print(whoami())
    return 0


def _print_list(msgs: list[Msg], who: str | None, all_msgs: list[Msg], tag: str = "") -> None:
    for m in sorted(msgs, key=lambda x: x.utc):
        mark = ""
        if who is not None and tag == "OPEN":
            mark = f"{YLW}●{RST} "
        rel = f" {DIM}re {m.re}{RST}" if m.re else ""
        print(f"  {mark}{DIM}{m.utc}{RST} {BOLD}{m.frm} → {m.to}{RST}: "
              f"{m.subject}{rel}  {DIM}[{m.id}]{RST}")
        if m.body:
            print(f"      {m.body}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("whoami")
    p.set_defaults(fn=cmd_whoami)

    p = sub.add_parser("post")
    p.set_defaults(fn=cmd_post)
    p.add_argument("--to", required=True)
    p.add_argument("--re", default="")
    p.add_argument("--subject", default="")
    p.add_argument("--body", default="")
    p.add_argument("--from", dest="from_", default=None)

    p = sub.add_parser("reply")
    p.set_defaults(fn=cmd_reply)
    p.add_argument("id")
    p.add_argument("--to", default=None)
    p.add_argument("--subject", default=None)
    p.add_argument("--body", default="")
    p.add_argument("--from", dest="from_", default=None)

    p = sub.add_parser("ack")
    p.set_defaults(fn=cmd_ack)
    p.add_argument("id")
    p.add_argument("--body", default="")
    p.add_argument("--from", dest="from_", default=None)

    p = sub.add_parser("inbox")
    p.set_defaults(fn=cmd_inbox)
    p.add_argument("--for", dest="for_", default=None)
    p.add_argument("--all", dest="all_", action="store_true")

    p = sub.add_parser("thread")
    p.set_defaults(fn=cmd_thread)
    p.add_argument("id")

    p = sub.add_parser("list")
    p.set_defaults(fn=cmd_list)
    p.add_argument("--from", dest="from_", default=None)
    p.add_argument("--to", default=None)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
