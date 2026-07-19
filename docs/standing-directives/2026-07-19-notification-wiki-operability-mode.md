# Standing directive — wiki-operability AI mode + ntfy/Resend/Twilio notification layer

**Status**: ACTIVE (operator directive, 2026-07-19, verbatim — logged BEFORE acting)
**Audience**: every Claude Code session working this feature

## Verbatim operator statement (sacrosanct — do not paraphrase)

> "the ai will have a mode where it uses the wiki through python which calls
> make changes, insertions, deletions or whatever operability to the wiki
> aimed at or default one and it will allow to sent notifications of ntly and
> resend emails and even twillo, I think I have this in another
> project,devops-solutions-information-hub has some stuff but
> https://github.com/cyberpunk042/openfleet/tree/3d993f5c5c3ae78be41fa7040fc387f0dbe50c2e/fleet/infra
> has an example ntfy client anda gateway client and such.. and
> https://github.com/cyberpunk042/continuity-orchestrator has probably resend
> and twillio, for sms it will require a high priority, high urgency by
> default and it will be conifugrable and for if with no SMS at all then the
> starting point is resent require urgent and high priority. and the user
> will be able to use and play with those such as setting a global default
> override and only those set to static value modified remain as is. all my
> words matter, take the time to quote me sacrosanct and verbattim.
> Start with proper research"

## Reading (agent working notes — NOT a paraphrase replacement; the verbatim above governs)

1. An AI **mode** that operates the wiki **through python** — changes /
   insertions / deletions / "whatever operability" — against "the wiki aimed
   at **or default one**" (a target-wiki parameter with a default).
2. A notification layer: **ntfy** push, **Resend** email, **Twilio** SMS.
3. Prior art the operator names: `devops-solutions-information-hub` ("has
   some stuff"), `openfleet` `fleet/infra` at commit `3d993f5c` ("an example
   ntfy client and a gateway client and such"), `continuity-orchestrator`
   ("probably resend and twillio").
4. Gating defaults: **SMS requires high priority + high urgency by default,
   configurable**. **With no SMS at all: Resend requires urgent + high
   priority** as the starting point.
5. Config model: user can "use and play with those such as setting a
   **global default override** and **only those set to static value modified
   remain as is**" — i.e. a global override sweeps every channel setting
   EXCEPT items the user pinned to a static value.
6. Process order: "**Start with proper research**".
