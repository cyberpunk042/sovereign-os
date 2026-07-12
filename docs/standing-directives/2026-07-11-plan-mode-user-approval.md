# Standing directive — Plan Mode + User Approval (2026-07-11)

> **Why this file exists.** The operator's durable instruction (verbatim,
> sacrosanct):
>
> > "now in a similar fashion but for plan: … Plan Mode and User Approval work
> > together as a safety feature that prevents the AI from making unreviewed
> > edits. … Approve / Make changes-Reject / Approve with changes / Approve and
> > remember. … Manual Mode (Default) … Auto Mode … a built-in safety classifier
> > that automatically blocks destructive operations … Bypass Permissions …
> > removes manual review safeguards."
>
> Companion to the [QCFA + interactive-clarification](./2026-07-11-qcfa-interactive-clarification.md)
> directive: QCFA governs *aligning on intent before acting*; this governs
> *reviewing the plan before executing*. **One framework, two homes** — the local
> sovereign AI (agent-runtime + cockpit) and external agents/operators.

## The doctrine — never act unreviewed

The AI **explores + proposes a plan without altering anything**, PAUSES, and
presents the plan for approval. The operator controls how often it pauses via the
**permission mode**. This is not new to sovereign-os — it is the codification of
the box's existing approval doctrine.

## Plan Mode

On a request to write code / mutate state, the AI enters Plan Mode: it reads,
explores, and writes out a **step-by-step strategy** — touching no files, running
no mutating command. It then stops and presents the plan.

## The four approvals

At the plan/approval prompt the operator has:

- **Approve** — execute exactly as proposed.
- **Reject / make changes** — block execution; suggest an alternative or a
  different approach.
- **Approve with changes** — modify the input (args, paths, constraints) before
  executing.
- **Approve and remember** — echo a permission rule so matching calls skip the
  prompt next time.

## Permission modes

Set via `SOVEREIGN_OS_PERMISSION_MODE` (or `config/permission-modes.yaml`):

| Mode | routine (read-only) | unknown (mutating) | destructive |
|------|--------------------|--------------------|-------------|
| **manual** (default) | allow | confirm | confirm + **DANGER** |
| **auto** | allow | confirm | **block** |
| **bypass** | allow | allow | allow |

- **manual** — pause for explicit approval on anything that mutates. The
  sovereign default; maps onto the cockpit's dry-run-default + operator-key +
  type-to-confirm gate.
- **auto** — a **safety classifier**
  ([`scripts/operator/lib/permission_classifier.py`](../../scripts/operator/lib/permission_classifier.py))
  auto-BLOCKS destructive operations (rm -rf, dd of=/dev/*, mkfs/wipefs, nvme
  format, zpool/zfs destroy, force-push, git reset --hard, fork bomb, curl|sh,
  poweroff, …), lets routine actions proceed, and confirms the unknown middle.
  Extensible via `config/permission-modes.yaml` `destructive_extra`.
- **bypass** — skip all gates (the `--dangerously-skip-permissions` analogue).
  Removes the manual-review safeguard; trusted non-interactive runs only.

## How it is wired — the two homes

- **Local sovereign AI (enforcement point).** Every web-originated action already
  goes through the ONE sanctioned execute daemon
  (`scripts/operator/control-exec-api.py`): allowlisted control-id + dry-run
  default + confirm gate + audit. The permission mode + classifier layer onto it —
  the daemon `decide()`s each action, so **auto blocks destructive, manual
  confirms, bypass proceeds**. The plan itself is **presented for approval by
  reusing the interactive-clarification rendering**: the AI proposes a plan
  (summary + numbered steps) inside the same fenced ` ```askuserquestion `
  envelope, with the four approvals as the options — so every chat surface
  (code-console, the Sovereign Brain panel, lm-status) renders the plan with
  clickable Approve / Reject / Approve-with-changes / Approve-and-remember, no new
  UI. On approve, each step executes through the gated daemon per the active mode;
  a destructive step is auto-blocked by Auto regardless. The
  `sovereign-agent-runtime` ReAct loop is the same kind of consumer.
- **External agents / operators.** This file is the operating manual: propose a
  plan first, present it for approval, honor the permission mode. The AI adopts
  Plan Mode by default on any mutating / consequential request.

## References

- Classifier: `scripts/operator/lib/permission_classifier.py` (tested; CLI
  `permission_classifier.py --mode auto "<cmd>"`).
- Config: `config/permission-modes.yaml`.
- Enforcement: `scripts/operator/control-exec-api.py`.
- Sibling: [`2026-07-11-qcfa-interactive-clarification.md`](./2026-07-11-qcfa-interactive-clarification.md).
