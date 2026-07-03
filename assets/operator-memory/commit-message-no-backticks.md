---
name: commit-message-no-backticks
description: ALWAYS commit with -F <file> (or -m with zero backticks) — backticks in a git commit -m string run as shell command substitution and mangle the message
metadata: 
  node_type: memory
  type: feedback
  originSessionId: acc85078-f2fe-4d01-8f1c-ef8d2e8fb04d
---

Hit three times in this repo: `git commit -m "…`cmd`…"` — the backticks
inside the double-quoted message are evaluated by bash as command
substitution BEFORE git sees them, so the message gets corrupted (the
backtick span replaced by the command's stdout) and stray errors print
("unknown command: selfdef", "syntax error near ||").

**Why:** commit messages naturally contain `code`, `make x`, `|| echo`,
`set -e` — all of which bash tries to run inside a double-quoted -m arg.

**How to apply:** For ANY non-trivial commit message, write it to a temp
file and `git commit -F /tmp/msg.txt` (then rm it). Never put backticks —
or `$(...)`, unescaped `!`, `||` — in a `git commit -m "…"` string. If a
message already committed mangled, fix with `git commit --amend -F file`.
Same rule for the pre-commit path being slow etc. — see
[[test-before-handover]].
