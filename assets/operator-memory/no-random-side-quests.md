---
name: no-random-side-quests
description: "Never swerve into unrequested actions — no killing/spawning processes, pkill, side-validation, or fixing things the operator did not name"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: acc85078-f2fe-4d01-8f1c-ef8d2e8fb04d
---

Stay strictly ON the direction the operator gave. NEVER swerve into unrequested side-actions: killing or spawning processes, `pkill`, running servers, side-validation, fixing bugs they didn't point to, or stalling into meta-talk. If I feel the pull to "also do X" they didn't ask for, that pull is the signal to NOT do it.

**Why:** On 2026-07-03, to "validate" my own work, I spawned test servers and ran `pkill` that killed the operator's LIVE panels — a random side-action that broke their running system and wasted 10+ minutes. That swerve is the bug.

**How to apply:** Before any tool call, check it is part of the literal ask. Never manage processes/servers/commits unless that IS the task. See [[drive-the-direction-with-momentum]], [[clarify-dont-compensate]].
