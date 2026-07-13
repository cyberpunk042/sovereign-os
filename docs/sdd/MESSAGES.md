# Session message board (SDD-981)

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
