# SDD-994 — the inference router bounds the request body instead of crashing / over-allocating (F-2026-097)

> Status: draft
> Owner: operator-directed 2026-07-14 (phase-1 audit continuation, "we continue"); agent-authored.
> Closes: **F-2026-097** (LOW) — the router front-door body-parse.
> Mandate module: **E11.M994**.
> Number band: **950–999 (phase-1 audit session)** per SDD-100.

## The bug

`scripts/inference/router.py` is the OpenAI-compatible HTTP front door for the
direct stack (Pulse / Logic Engine / Oracle Core). Its POST body read was:

```python
def _do_post_inner(self) -> None:
    length = int(self.headers.get("Content-Length", 0))
    raw = self.rfile.read(length)
```

Two defects on an untrusted request path:

1. **Crash on a malformed header.** `int(self.headers.get("Content-Length", 0))`
   raises an uncaught `ValueError` when a client sends a non-numeric
   `Content-Length` (`Content-Length: abc`). The exception propagates out of the
   handler — `BaseHTTPRequestHandler` logs a traceback and drops the connection;
   a client can spam malformed headers to churn the daemon. The default `0` only
   covers the *absent* header, not a *present-but-garbage* one.
2. **Unbounded read.** `self.rfile.read(length)` trusts the client-declared
   length with no cap. A client claiming `Content-Length: 1099511627776` forces
   the handler to attempt a 1 TiB allocation — a trivial memory-DoS on the
   front door.

Every sibling operator daemon already guards both — `control-exec-api.py`
(`_MAX_BODY = 64 * 1024`; `if length <= 0 or length > _MAX_BODY: 400`),
`code-console-api.py` (`if length <= 0 or length > 64_000`), `brain-api.py`
(`try: … except (ValueError, OSError)`). The router was the outlier.

## The fix — one testable helper, matched to what the router serves

The tiny-control APIs cap at 64 KB, but the router proxies *inference* requests —
a long-context chat completion is legitimately large. So the cap is generous
(16 MiB) rather than tiny, and the parse is pulled into a pure function so the
boundary is unit-testable without a live socket:

```python
_MAX_BODY = 16 * 1024 * 1024  # 16 MiB — long prompts fit; the read stays bounded

def parse_content_length(raw, max_body=_MAX_BODY):
    """→ (length, error). error is None on success, else an (http_status, msg)."""
    if raw is None or raw == "":
        return 0, None                                   # no body → {}
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return None, (400, "malformed Content-Length header")   # was a crash
    if n < 0:
        return None, (400, "negative Content-Length")
    if n > max_body:
        return None, (413, f"request body exceeds {max_body} bytes")  # was unbounded
    return n, None
```

`_do_post_inner` now rejects cleanly before reading:

```python
length, err = parse_content_length(self.headers.get("Content-Length"))
if err is not None:
    self.send_error(*err)
    return
raw = self.rfile.read(length)
```

- a **malformed** header → `400 malformed Content-Length header` (not a traceback)
- a **negative** length → `400`
- an **oversize** length → `413 request body exceeds …` (before any allocation)
- absent / empty / valid ≤ cap → unchanged (`0` → `json.loads(b"{}")`, or the real body)

The routing logic (`classify` / `classify_task_type` / `classify_model_class` /
`_scheduler_advisory`), the metrics, and every response header are untouched — this
only bounds how the raw bytes are obtained.

## Verification (real, observed)

New `tests/unit/test_router_body_bounds.py` — 11 tests over `parse_content_length`:
absent/empty → `(0, None)`; valid + at-cap pass; non-numeric / whitespace-garbage /
negative → `400`; cap+1 and a 1 TiB claim → `413` (rejected before any read); a
custom `max_body` boundary honored.

`python3 -m pytest tests/unit/test_router_body_bounds.py tests/unit/test_router_classify.py tests/unit/test_router_scheduler_advisory.py`
— **42 passed** (11 new + 31 existing router tests, unchanged). `ruff check
scripts/inference/router.py tests/unit/test_router_body_bounds.py` — clean.

## Scope / safety

`scripts/inference/router.py` only (1 constant + 1 pure helper + a 2-line call-site
change) + 1 new `tests/unit/` file + this SDD + registries. No cockpit, no webapp, no
crate, no other `scripts/operator` daemon, no new dependency. Collision-safe.
R10212 (selfdef boundary) / MS043 (offline survivability) untouched. MS003
`unsigned-pending-MS003`.

## Non-goals

- A shared `BaseOperatorHandler` unifying the ~58 hand-rolled body-read handlers
  (a broader refactor; each daemon already guards its own body — this fix brings
  the one outlier up to that bar). Tracked separately (F-2026-093 island theme).
- Streaming / chunked-transfer bodies (the router is request/response JSON;
  `Transfer-Encoding: chunked` is out of scope here).
- Tuning the 16 MiB cap per deployment (a constant now; env-configurable later if
  a real prompt approaches it).

## Cross-references

- `scripts/inference/router.py` — `parse_content_length` + `_MAX_BODY` + the guarded `_do_post_inner`
- `scripts/operator/control-exec-api.py`, `code-console-api.py`, `brain-api.py` — the sibling body-guard idiom this brings the router up to
- `tests/unit/test_router_body_bounds.py` — the boundary regression
- `docs/review/phase-1/99-findings-ledger.md` — F-2026-097 (closed here)
