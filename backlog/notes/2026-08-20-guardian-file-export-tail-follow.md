# Guardian Core — file-export tail-follow (supersedes the socket-EOF-restart mechanism) — 2026-08-20

Source: live bring-up of the Auditor perimeter on the SAIN-01 node (ai-workstation). Standing up `sovereign-guardian-core.service` for the first time surfaced a crash-loop that only appears once the Tetragon event stream actually exists — invisible to static lint.

## What broke

`guardian-core.py` opened `/var/run/tetragon/tetragon.events`, read to end-of-file, printed `[EOF] … perimeter blind; exiting for systemd restart`, and exited `1`. systemd restarted it; it drained again; exited; repeat — a permanent crash-loop (`Start request repeated too quickly` → unit latched `failed`).

## Root cause — a socket assumption meeting a file reality

The §10 design (and M084 / E0813–E0815) assumed guardian tails a **UNIX socket**, where EOF means the writer closed → restart. Verbatim (dump line 765, quoted in [M084](../milestones/M084-opnsense-sdwan-boundary-contract-tetragon-dropout-resilience.md)):

> "…include health checking routines that instantly restart the security loop if the local **UNIX socket** encounters an end-of-file (EOF) exception."

But the implementation consumes Tetragon's `--export-filename`, which is a **regular, rotated file**. Reaching its end is the normal *caught-up* state, not a dropped stream — so exit-on-EOF fires constantly.

### The unavoidable verbatim tension (surfaced, not conflated)

Two operator-verbatim statements cannot both hold under Tetragon's actual mechanisms:

1. **§10.1** pins the consumed path as `/var/run/tetragon/tetragon.events` — a **file** (lint: `test_guardian_core_verbatim.py`).
2. **M084/E0815** pins **UNIX-socket** EOF-restart semantics.

A file is not a socket; EOF-restart is wrong for a file. Resolving requires choosing which verbatim governs. Operator decision (this session): **keep the §10.1 file path; supersede the E0815 literal socket-EOF-restart mechanism**, because its *intent* — "never let the containment loop go blind / stall" — is better served by tailing the file than by exiting on every catch-up.

## The fix

- New `_follow_stream()` tails the export file: seek-to-END on first open (no history replay / no re-kill on restart), poll past EOF, re-open on genuine rotation/truncation (Tetragon rolls the export), read the fresh file from its start.
- `main()` consumes it; the exit-on-EOF fall-through is removed. Real tetragon stop is still handled by the unit's `BindsTo=tetragon.service`.
- Companion unit + hook fixes (separate commits): `StartLimitIntervalSec=0` + `ExecStartPre` wait on the guardian unit; `/etc` `export-filename → tetragon.events` drop-in wired into `tetragon-policy-load.sh` (the vendor ships `tetragon.log`).

## Intent preserved

The M084 gotcha (interface re-shuffle → guardian stalls/blinds) is *better* handled now: a network event doesn't affect a local file; guardian keeps following and resumes when Tetragon writes again. Genuine tetragon death → `BindsTo` stops guardian; tetragon return → unit restarts it.

## Follow-ups

- M084 "Shipped already" line (commit `47632d0`: "EOF fall-through exits nonzero") is now **superseded** for the file-export path — update M084 status if/when the milestone is next revised.
- Consider whether E0815 should be re-specified against the file-export reality (or guardian moved to the true gRPC stream `tetra getevents` off `tetragon.sock`, where socket-EOF semantics would again be literally correct) — an SDD-level decision, deferred.
