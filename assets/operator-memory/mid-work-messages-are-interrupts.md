---
name: mid-work-messages-are-interrupts
description: "A message that arrives while I'm working is a PRIORITY INTERRUPT, not a queued 'address-after' item — halt the current trajectory and process it first"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: acc85078-f2fe-4d01-8f1c-ef8d2e8fb04d
---

A message from the operator that arrives while I'm working — the "user sent a new message while you were working" injection — is a PRIORITY INTERRUPT, not a queued "address-after" item. At the next tool-boundary: STOP the current trajectory, start NO new tool calls on the old task, re-read the new message as the current directive, and process it FIRST. Resume prior work only if the new message says to.

**Why:** New rule from the operator on 2026-07-03, from a real find. The harness injects mid-work messages with "After completing your current task, you MUST address…" — which queues them BEHIND my in-flight action ("soft signal"), while only `[Request interrupted by user]` preempts ("hard signal"). Combined with my habit of finishing whatever I started, the operator's steering kept landing too late and they had to hard-cancel repeatedly and repeat themselves 5+ times. The "finish first" framing must NOT be used as license to complete a wrong trajectory.

**How to apply:** On any such injection, halt and pivot immediately at the next boundary — do not finish the batch out of momentum. In auto mode especially, keep tool batches SMALL so these boundaries come often and the operator can steer without a hard cancel. Treat short/emphatic mid-work messages as likely STOP/redirect signals. See [[operator-is-always-the-driver]], [[drive-the-direction-with-momentum]].
