# SDD-954 — auto-mode permission classifier: flag normalization + honest "best-effort UX, not a boundary" framing

> Status: draft
> Owner: operator-directed ("go" — Phase-1 audit); agent-authored
> Last updated: 2026-07-12
> Number band: **950–999 (general / audit session)** per SDD-100.
> Closes findings: **F-2026-092**. From `docs/review/phase-1/99-findings-ledger.md`.
> Derived from / extends: `scripts/operator/lib/permission_classifier.py` + the plan-mode/user-approval directive (`docs/standing-directives/2026-07-11-plan-mode-user-approval.md`).

## Mission

The Auto-mode safety classifier had two problems the audit named:

1. **An evadable `rm` pattern.** The destructive `rm` rule was a single combined-token regex (`\brm\s+(-\w*\s+)*-\w*[rf]\w*[rf]\w*`) that only matched when the recursive + force flags were written **together** (`rm -rf`). So `rm -r -f /x` (split flags) and `rm -R -f /x` (uppercase) **escaped the `destructive` verdict** and fell through to `confirm` — a footgun in Auto mode, which is supposed to auto-block the recursive-delete class.
2. **Mis-framed as a boundary.** The doctrine text read as if the classifier *were* the security control ("auto-BLOCKS destructive operations"). It is a heuristic denylist — quoting / `$IFS` / variable / base64 obfuscation evade it — so presenting it as a boundary invites a false sense of containment.

This SDD closes both: **flag normalization** for `rm`, and an **honest reframe** to "best-effort UX heuristic, not a security boundary."

## What this SDD builds

### 1. Flag-normalized `rm` classification

The two `rm` regexes are removed from `_DESTRUCTIVE` and replaced by `_rm_recursive_or_force(cmd)`, which finds any `rm` token (basename `rm`, so `sudo rm …` is covered) and scans its following option tokens — stopping flag-collection at `--` — accumulating recursive (`-r` / `-R` / `--recursive`) and force (`-f` / `--force`) semantics **across split, combined, reordered, uppercase, and long forms**. If either is present, the command is `destructive`. `classify()` calls it before the regex loop.

| Command | Old verdict | New verdict |
|---|---|---|
| `rm -rf /x` | destructive | destructive |
| `rm -r -f /x` | **confirm (escaped)** | **destructive** |
| `rm -R -f /x` | **confirm (escaped)** | **destructive** |
| `rm -fr /x` / `rm -Rf /x` | destructive | destructive |
| `rm --recursive --force /x` | destructive | destructive |
| `rm -r /x` (recursive alone) | confirm | **destructive** |
| `rm --force x` | destructive | destructive |
| `rm file.txt` (no flags) | unknown → confirm | unknown → confirm (unchanged — gated, not blocked, never silent-allowed) |

Fail-safe is preserved: anything unrecognized or obfuscated still lands in `unknown` → `confirm` under Auto, never a silent allow.

### 2. Honest framing — heuristic, not a boundary

The module docstring and the plan-mode directive now state plainly: the classifier is a **best-effort UX heuristic, not a security boundary**. It reduces footguns for a cooperative caller; it does not contain an adversary. The **actual boundary** is the allowlisted execute daemon (`control-exec-api`: allowlisted control-id + dry-run default + audit) plus the fs sandbox around the execution paths (F-2026-081). A `block` means "spared the operator a likely mistake", never "an attacker was stopped".

## Verification

- `python3 -m pytest tests/lint/test_plan_mode_contract.py` — 7 (2 new): every recursive/force `rm` arrangement (`-rf` / `-r -f` / `-R -f` / `-fr` / `-Rf` / `--recursive --force` / `-r` / `--force` / `sudo rm -r -f`) → `destructive` → `block` under Auto; plain `rm file.txt` → `unknown` → `confirm` (fail-safe, not fail-open); the module + directive are framed as best-effort-not-a-boundary.
- `ruff check scripts/operator/lib/permission_classifier.py` clean; full `tests/lint` + `tests/schema` green.

## Non-goals (tracked follow-ups)

- **Defeating obfuscation** (quoting / `$IFS` / variable / base64). A regex classifier can't, and shouldn't pretend to — the fail-safe direction (→ confirm) already prevents silent-allow. The real fix is the execution-path boundary below.
- **The real boundary: sandbox-profile / fs-boundary enforcement around the execution paths** — F-2026-081 (wire the Rust security crates + sandbox into the daemon). This SDD makes the classifier honest about being the UX layer on top of that boundary, not a substitute for it.
- Calling the classifier from `agent-loop` / the jobs subprocess runner — those execution paths are gated by the allowlisted daemon, not this advisory heuristic; unifying them is F-2026-081/088 territory.

## Safety invariants

The change only tightens the `destructive` set (more `rm` forms caught) and never loosens it — every previously-blocked command still blocks; the fail-safe `unknown → confirm` path is unchanged; no command that was `block`/`confirm` becomes `allow`. Docs-and-heuristic only; no execution path, contract yaml, or lifecycle change. R10212/SB-077 untouched. MS003 `unsigned-pending-MS003`.

## Cross-references

- `docs/review/phase-1/99-findings-ledger.md` — F-2026-092 (source); F-2026-081 (the real boundary this defers to)
- `scripts/operator/lib/permission_classifier.py` — `_rm_recursive_or_force` + the reframed docstring
- `docs/standing-directives/2026-07-11-plan-mode-user-approval.md` — the reframed `auto` doctrine
- `tests/lint/test_plan_mode_contract.py` — the regression + framing tests
- SDD-100 — the per-session number-band convention (this SDD is in the phase-1-audit 950–999 sub-band)
