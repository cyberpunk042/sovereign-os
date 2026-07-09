# SDD-103 — D-22 multi-turn chat (bounded client-side conversation history)

> Status: draft
> Owner: operator-supervised; agent-authored
> Last updated: 2026-07-09
> Closes findings: SDD-062 Q-062-E (multi-turn conversation history)
> Derived from: operator goal "make the dashboards functional and god-tier"; chosen after SDD-102 found the "make-a-stubbed-panel-functional" thread complete — this is a depth feature on the working D-22 chat. Recover-projects band (SDD-103 / E11.M103).

## Mission

Give the cockpit's D-22 web chat a **real back-and-forth**. Today it is single-turn
(`_send_chat` reads `{prompt}`, `prompt.run(text)` wraps one user message), so each message is
context-free. Add **bounded multi-turn conversation** while keeping the server a **stateless
read-compute** (R10212) and honest-deferring the LM response exactly as today (SB-077). The
history mechanism is hardware-free-testable; only the model's reply needs a running backend
(unchanged honest-defer to 503).

## Problem

- `scripts/inference/prompt.py` `run(text, …)` builds `body = {"messages":[{"role":"user",
  "content":text}], …}` → the router's OpenAI-compatible `/v1/chat/completions`. The router
  **already accepts a full `messages` array**; single-turn is only because `run()` wraps one
  string.
- `scripts/operator/lm-status-operability-api.py` `_send_chat()` (the ONE sanctioned POST)
  reads `{prompt}` and calls `run(text)`; the webapp `sendChat()` POSTs `{prompt}` + renders
  one exchange. No conversation memory (SDD-062 Q-062-E, Stage-N).

## Grounded design — client-side history, stateless server

- **`prompt.py`** — `run()` gains an optional `messages: list[dict] | None`. When given, pass
  it straight to the router body (after `_bound_messages`); else keep `text` → single-user-
  message wrapping (**fully back-compatible** — the observe/janitor/navigator SLM callers pass
  `text`, unaffected). `_bound_messages(messages)`: trim to the last `MAX_CHAT_TURNS` (~8),
  enforce the `MAX_PROMPT_CHARS` total across contents, validate roles ∈ {user, assistant,
  system} (never injects a turn). `done`/`error`/telemetry contract unchanged.
- **`_send_chat()`** — accept `{messages:[…]}` in addition to `{prompt:text}` (a bare `prompt`
  becomes a one-message array). Bound via the existing ≤64 KB body cap + `_bound_messages`;
  400 on a malformed/oversize array. **The server holds NO conversation state** — the client
  sends the full bounded history each turn → the daemon stays a stateless read-compute (the ONE
  sanctioned POST stays the ONE sanctioned POST, just a richer body; all other methods 405).
  Honest-defer 503 / SSE `error` unchanged.
- **D-22 webapp** — the composer keeps a **client-side conversation buffer** (`[{role,
  content}]`): append the user turn, POST `{messages: <bounded buffer>}`, stream the assistant
  reply into the buffer, render the multi-turn thread; "new chat" clears it. Bounded client-
  side too. No server state, no persistence (in-page only — matches SDD-062 "no prompt
  persistence").

## Open questions

| Q | Question | Resolution |
|---|---|---|
| Q-103-A | History location. | **answered (operator, 2026-07-09): client-side — the webapp holds + sends the bounded buffer; the server stays stateless (R10212-clean; matches SDD-062 no-persistence).** |
| Q-103-B | Bound. | **answered: last ~8 turns + the `MAX_PROMPT_CHARS` total-char cap + the ≤64 KB body cap.** |
| Q-103-C | Persistence across reloads. | **proposed: Stage-N (a localStorage buffer) — this increment is in-page only.** |

## Non-goals (Stage N)

- Server-side / persisted conversation state (adds a mutation, against the read-compute posture).
- Cross-reload persistence (localStorage buffer).
- Per-device targeting / a conversation picker.

## Way forward

- **Stage 0 (this commit):** this SDD + INDEX row 103 + mandate E11.M103; flip SDD-062 Q-062-E.
- **Stage 1:** `prompt.run(messages=…)` + `_bound_messages` + `_send_chat` body + tests.
- **Stage 2:** the D-22 webapp client-side buffer + e2e.

## Safety invariants

The server stays a **stateless read-compute** — the client sends the bounded history each turn;
the daemon holds NO conversation state (R10212; the ONE sanctioned POST stays the ONE
sanctioned POST — every other method 405). **SB-077 honest-defer** — an unreachable LM streams
the honest `error`/503 as today; never fabricates a reply. **Bounded** (last N turns + char +
64 KB caps) — no unbounded context. Roles validated (never injects a system turn). No prompt
persistence (in-page buffer). `run(text)` is fully back-compatible. No contract yaml change.
MS003 `unsigned-pending-MS003`.

## Cross-references

- `scripts/inference/prompt.py` (SDD-062) — `run()` router body + SSE + honest-defer.
- `scripts/operator/lm-status-operability-api.py` (SDD-062) — `_send_chat` (the ONE sanctioned POST).
- `webapp/d-22-lm-status-operability/index.html` — the chat composer.
- `tests/lint/test_d22_lm_status_operability_webapp_contract.py` — the read-only contract + the
  one-sanctioned-POST lock (`_PERMITTED_POST`).
- SDD-062 (functional D-22 chat), R10212, SB-077.
