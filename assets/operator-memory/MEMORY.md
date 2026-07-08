# Memory index

- [First image build status](first-image-build-status.md) — first green pipeline 2026-06-10; DKMS/SB caveat; consolidation list; host IS the SAIN-01 hardware
- [Single-OS pivot](single-os-pivot.md) — dual-boot dropped 2026-06-10; test on running Debian GUI; sovereign-home LV IS /home (keep); sovereign-root LV idle
- [Test before handover](test-before-handover.md) — MANDATORY: simulate privileged context (fake install tree, systemd-analyze, git owner sim) before giving the operator any sudo/systemd command
- [Commit message no backticks](commit-message-no-backticks.md) — ALWAYS git commit -F file; backticks in -m run as shell substitution and mangle the message
- [Operator words are sacrosanct](operator-words-are-sacrosanct.md) — never delete/deform/paraphrase; on a request, quote the ask verbatim then proceed with the quoted ask
- [Operator is always the driver](operator-is-always-the-driver.md) — I am driven, never decide or take the lead; their instruction is the entire scope
- [Drive the direction with momentum](drive-the-direction-with-momentum.md) — execute the given direction fully; do NOT stop after every little action to ask permission
- [No random side-quests](no-random-side-quests.md) — never swerve into unrequested actions (no killing/spawning processes, pkill, side-validation, fixing unnamed things)
- [Clarify, don't compensate](clarify-dont-compensate.md) — if I don't understand, talk and clarify; never fill the gap with random actions
- [Ask questions when unclear](ask-questions-when-unclear.md) — ASK a direct question whenever I don't understand; never guess or assume the direction
- [Do not minimize](do-not-minimize.md) — deliver the full comprehensive scope; never reduce, sample, or ship a "good enough" subset
- [Mid-work messages are interrupts](mid-work-messages-are-interrupts.md) — a message arriving while I work is a priority interrupt; halt and process it first, keep batches small in auto mode
