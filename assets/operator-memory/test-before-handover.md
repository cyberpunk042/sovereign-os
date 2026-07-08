---
name: test-before-handover
description: "Feedback 2026-06-12: every YOU-RUN block failed until Claude started simulating the privileged context first — mandatory process for all root/systemd/installed-path commands"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: acc85078-f2fe-4d01-8f1c-ef8d2e8fb04d
---

2026-06-12: Four consecutive ⚡ YOU RUN blocks failed in the operator's
terminal (installed-layout /usr bug, ERR-trap noise, 226/NAMESPACE bare
ReadWritePaths, git dubious-ownership as root). Operator: "everything you
give me doesn't work. can you work more seriously?" The fifth block worked
first try — the only one where Claude reproduced the failure mode and
proved the fix before handover.

**Why:** Claude's sandbox cannot sudo / run systemd / be root, so the first
real execution of privileged commands lands in the operator's terminal.
Validating only the unprivileged slice (in-repo run + lint green) made the
operator the integration test. Also: piping checks through `head` masked a
trailing error line once (SIGPIPE) — don't truncate verification output.

**How to apply:** Before handing ANY privileged/installed-context command
to the operator ([[single-os-pivot]]):
1. Trace the full execution chain (install layout → unit sandbox → process
   user → external tools like git) and check each layer's assumptions.
2. Simulate everything simulatable: fake installed tree under /tmp;
   `systemd-analyze verify`; `GIT_TEST_ASSUME_DIFFERENT_OWNER=1` for
   root-vs-owner git; run hooks end-to-end via the real /opt path.
3. If a step is genuinely un-simulatable first contact, SAY SO in the
   block so a failure there is expected territory.
4. Fix at root cause in the repo, never as a host-only workaround.
