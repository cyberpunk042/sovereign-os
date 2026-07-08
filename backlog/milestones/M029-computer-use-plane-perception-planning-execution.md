# M029 — Computer-Use plane — perception + planning + execution

> Parent: `backlog/milestones/INDEX.md` row M029 (dump 8475–8804).
> Source: `raw/dumps/2026-05-18-the-ultimate-exploitation-of-the-tech-stack-AVX-plus-plus.md` lines 8475–8804.
> All entries below are extracted from the dump line range. No invention.

## Epics (E0268–E0277)

| Epic ID | Phrase | Dump line |
|---|---|---|
| E0268 | Computer-use intelligence — bridge from "thinking system" to "acting system"; the station grows hands and eyes | 8490–8492 |
| E0269 | Research substrate — Microsoft Fara-7B agentic SLM (145K trajectories / 1M steps) / OmniParser V2 (screenshots → structured interactable elements) / ActionEngine (state-machine memory; 95% on Reddit WebArena; 1 LLM call; 11.8x cost reduction; 2x latency reduction) / GUI-R1 + ShowUI VLA models / OSWorld+WebArena+ScreenSpot benchmarks | 8494–8501 |
| E0270 | The Computer-Use Plane — 3 layers (Perception screenshot→UI-elements→bboxes→semantic-labels; Planning task→current-UI→action-plan/state-machine; Execution click/type/scroll/hotkey/file/browser under policy) | 8502–8533 |
| E0271 | Hardware placement — 4090 eyes/reflexes (Fara-7B/OmniParser/GUI-SLM/vision-action scout); Blackwell strategic judgment (task reasoning / recovery / final verification); CPU AVX-512 motor control law (state machine / action policy / bbox filter / permission checks / replay / dup-state detection); RAM/ZFS UI maps + trajectories + screenshots + action logs + learned workflows | 8535–8557 |
| E0272 | GUI State As Data + typed Action — JSON schema (window/url/elements[].{id,type,text,bbox,interactable,risk}); typed actions (action/target_id/reason/requires_confirmation); 6 runtime checks (target exists / interactable / action allowed / risk acceptable / credential-payment-destructive state / human gate needed) | 8559–8601 |
| E0273 | State-Machine Memory — repeated workflows learned (login→credentials→dashboard→search-results→detail→export-dialog→downloaded-file); each state has 5 attributes (recognition features / allowed actions / expected transitions / failure handlers / risk flags); intelligence crystallizing into procedure | 8602–8629 |
| E0274 | Computer-Use Profiles — 6-tier (observe_only / assistive / supervised / sandbox / autonomous_low_risk / high_risk); "profiles matter deeply here. A GUI agent can do real harm" | 8631–8653 |
| E0275 | Action Policy Bits — 64-bit capability word (bits 0..7 action type / 8..15 target class / 16..23 risk / 24..31 environment / 32..39 confidence / 40..47 step budget / 48..55 human gate state / 56..63 audit flags) + AVX-512 batch evaluation (allowed = confidence_ok & target_valid & permission_ok & not_high_risk_without_gate) | 8654–8677 |
| E0276 | RLM for GUI + Reward Plane for GUI + GUI verifier — RLM stores UI environment (screenshots / parsed elements / DOM-a11y tree / action history / state machine / observations); recursively inspects (which screen had export / what changed after settings / which path led to dialog / shortest safe path); 8-metric trajectory scoring; Fara CUAVerifierBench; GUI verifier scores 5 questions (valid / toward-goal / safe / efficient / consent) | 8678–8729 |
| E0277 | Replay Mandatory + The Proper Exploit + new architecture component "Computer-Use Plane" (8-item) + key line "Computer-use intelligence is not clicking. It is converting visual chaos into typed state transitions under policy" + 7-component plug map (SLM reflexes / RLM long-horizon nav / PRM-RM trajectory value / AVX-512 action law + scheduling / Blackwell judgment / 4090 perception-action scout / ZFS replay+learning) | 8731–8802 |

## Modules (M00476–M00492)

| Mod ID | Phrase | Dump line | Parent epic |
|---|---|---|---|
| M00476 | Perception layer — screenshot → UI elements → bounding boxes → semantic labels | 8509–8510 | E0270 |
| M00477 | Planning layer — task → current UI state → action plan / state machine | 8512–8513 | E0270 |
| M00478 | Execution layer — click / type / scroll / hotkey / upload / download / browser actions under policy | 8515–8516 | E0270 |
| M00479 | Perceive-once doctrine — build UI state machine; act programmatically; only re-query model on state change or rising uncertainty (per ActionEngine) | 8523–8532 | E0270 |
| M00480 | GUI State JSON — `{window, url, elements: [{id, type, text, bbox, interactable, risk}]}` | 8563–8578 | E0272 |
| M00481 | Typed Action JSON — `{action, target_id, reason, requires_confirmation}` | 8580–8589 | E0272 |
| M00482 | Runtime checks — 6 gate predicates (target exists / target interactable / action allowed / risk acceptable / credential-payment-destructive state / human gate needed) | 8591–8600 | E0272 |
| M00483 | State-Machine Memory — repeated-workflow learner; example login→credentials→dashboard→search→detail→export→downloaded sequence | 8606–8615 | E0273 |
| M00484 | State attributes — recognition features / allowed actions / expected transitions / failure handlers / risk flags | 8617–8624 | E0273 |
| M00485 | Profile observe_only — screenshot/parse, no actions | 8633–8634 | E0274 |
| M00486 | Profile assistive — suggest actions, user clicks | 8636–8637 | E0274 |
| M00487 | Profile supervised — agent acts, asks before risky steps | 8639–8640 | E0274 |
| M00488 | Profile sandbox — agent acts freely in VM/browser sandbox | 8642–8643 | E0274 |
| M00489 | Profile autonomous_low_risk — allowed for repetitive non-sensitive tasks | 8645–8646 | E0274 |
| M00490 | Profile high_risk — human gate for credentials / purchases / deletes / sends | 8648–8649 | E0274 |
| M00491 | Action Policy Bits 64-bit word — 8 fields × 8 bits each | 8657–8666 | E0275 |
| M00492 | Computer-Use Plane architecture component — 8 sub-parts (screen parser / GUI state model / action planner / policy gate / executor / trajectory memory / GUI verifier / state-machine learner) | 8771–8781 | E0277 |

## Features (F02381–F02465)

| F ID | Phrase | Dump line | Parent | Category | Opt-in |
|---|---|---|---|---|---|
| F02381 | Computer-use intelligence — bridge from thinking system to acting system | 8490–8492 | E0268 | composite | false |
| F02382 | Station grows hands and eyes | 8490 | E0268 | composite | false |
| F02383 | Research is moving fast — substrate enumerated | 8494 | E0269 | composite | false |
| F02384 | Microsoft Fara-7B — agentic SLM for computer use; visually perceives webpages; acts by scrolling/typing/clicking predicted coordinates | 8496 | E0269 | composite | true |
| F02385 | Fara-7B training data — 145K trajectories + 1M steps | 8496 | E0269 | composite | false |
| F02386 | OmniParser V2 — turns screenshots into structured interactable elements with bounding boxes + captions | 8497 | E0269 | composite | true |
| F02387 | OmniParser lets ordinary LLMs become GUI agents | 8497 | E0269 | composite | false |
| F02388 | ActionEngine — moves GUI agents from reactive screenshot-step loops to programmatic agents with state-machine memory | 8498 | E0269 | composite | true |
| F02389 | ActionEngine result — 95% success on Reddit WebArena tasks | 8498 | E0269 | composite | false |
| F02390 | ActionEngine result — about one LLM call per task | 8498 | E0269 | composite | false |
| F02391 | ActionEngine result — 11.8x cost reduction vs vision-only baseline | 8498 | E0269 | composite | false |
| F02392 | ActionEngine result — 2x latency reduction vs vision-only baseline | 8498 | E0269 | composite | false |
| F02393 | GUI-R1 + ShowUI — vision-language-action models trained for GUI actions with RL-style improvements + unified action spaces | 8499 | E0269 | composite | true |
| F02394 | OSWorld / WebArena / ScreenSpot — proving-ground benchmarks for whether agents can actually use computers, not just talk | 8500 | E0269 | composite | false |
| F02395 | "Add a Computer-Use Plane" | 8502 | E0270 | composite | false |
| F02396 | Computer-Use Plane has 3 layers | 8506 | E0270 | composite | false |
| F02397 | Layer Perception — screenshot → UI elements → bounding boxes → semantic labels | 8509–8510 | M00476 | composite | false |
| F02398 | Layer Planning — task → current UI state → action plan / state machine | 8512–8513 | M00477 | composite | false |
| F02399 | Layer Execution — click / type / scroll / hotkey / file / browser actions under policy | 8515–8516 | M00478 | composite | false |
| F02400 | "The serious move is not 'take screenshot, ask big model, click, repeat' — that is expensive and brittle" | 8519–8521 | E0270 | composite | false |
| F02401 | Better move step 1 — perceive once | 8526 | M00479 | composite | false |
| F02402 | Better move step 2 — build UI state machine | 8527 | M00479 | composite | false |
| F02403 | Better move step 3 — act programmatically | 8528 | M00479 | composite | false |
| F02404 | Better move step 4 — only re-query model when state changes or uncertainty rises | 8529 | M00479 | composite | false |
| F02405 | "That is what ActionEngine is pointing toward" | 8532 | M00479 | composite | false |
| F02406 | Hardware — 4090 runs Fara-7B / OmniParser / GUI SLM / vision-action scout | 8537–8538 | E0271 | composite | true |
| F02407 | Hardware — Blackwell does high-level task reasoning / recovery / final verification | 8540–8541 | E0271 | composite | true |
| F02408 | Hardware — CPU AVX-512 does UI state machine / action policy / bounding-box filtering / permission checks / replay / duplicate state detection | 8543–8549 | E0271 | composite | true |
| F02409 | Hardware — RAM/ZFS stores UI maps / trajectories / screenshots / action logs / learned workflows | 8551–8552 | E0271 | composite | true |
| F02410 | "4090 becomes the eyes and reflexes" | 8555 | E0271 | composite | false |
| F02411 | "CPU becomes motor control law" | 8556 | E0271 | composite | false |
| F02412 | "Blackwell becomes strategic judgment" | 8557 | E0271 | composite | false |
| F02413 | GUI state field — window | 8565 | M00480 | composite | false |
| F02414 | GUI state field — url | 8566 | M00480 | composite | false |
| F02415 | GUI state element field — id (integer) | 8569 | M00480 | composite | false |
| F02416 | GUI state element field — type (e.g. button) | 8570 | M00480 | composite | false |
| F02417 | GUI state element field — text (e.g. "Submit") | 8571 | M00480 | composite | false |
| F02418 | GUI state element field — bbox `[x1, y1, x2, y2]` | 8572 | M00480 | composite | false |
| F02419 | GUI state element field — interactable (bool) | 8573 | M00480 | composite | false |
| F02420 | GUI state element field — risk (low / medium / high) | 8574 | M00480 | composite | false |
| F02421 | Typed action — actions not free-form | 8580 | M00481 | composite | false |
| F02422 | Typed action field — action (e.g. click) | 8584 | M00481 | composite | false |
| F02423 | Typed action field — target_id (references element.id) | 8585 | M00481 | composite | false |
| F02424 | Typed action field — reason (e.g. "submit completed form") | 8586 | M00481 | composite | false |
| F02425 | Typed action field — requires_confirmation (bool) | 8587 | M00481 | composite | false |
| F02426 | Runtime check — target exists | 8594 | M00482 | composite | false |
| F02427 | Runtime check — target is interactable | 8595 | M00482 | composite | false |
| F02428 | Runtime check — action allowed | 8596 | M00482 | composite | false |
| F02429 | Runtime check — risk acceptable | 8597 | M00482 | composite | false |
| F02430 | Runtime check — credential / payment / destructive state | 8598 | M00482 | composite | false |
| F02431 | Runtime check — human gate needed | 8599 | M00482 | composite | false |
| F02432 | State machine — for repeated workflows, learn state machines | 8604 | M00483 | composite | false |
| F02433 | State machine example — login_page → credentials_page → dashboard → search_results → detail_page → export_dialog → downloaded_file | 8607–8613 | M00483 | composite | false |
| F02434 | State attribute — recognition features | 8619 | M00484 | composite | false |
| F02435 | State attribute — allowed actions | 8620 | M00484 | composite | false |
| F02436 | State attribute — expected transitions | 8621 | M00484 | composite | false |
| F02437 | State attribute — failure handlers | 8622 | M00484 | composite | false |
| F02438 | State attribute — risk flags | 8623 | M00484 | composite | false |
| F02439 | "Agent does not need to reason from scratch every time" | 8626 | M00483 | composite | false |
| F02440 | "This is intelligence crystallizing into procedure" | 8628 | M00483 | composite | false |
| F02441 | Profile observe_only — screenshot / parse, no actions | 8633–8634 | M00485 | composite | true |
| F02442 | Profile assistive — suggest actions, user clicks | 8636–8637 | M00486 | composite | true |
| F02443 | Profile supervised — agent acts, asks before risky steps | 8639–8640 | M00487 | composite | true |
| F02444 | Profile sandbox — agent acts freely in VM/browser sandbox | 8642–8643 | M00488 | composite | true |
| F02445 | Profile autonomous_low_risk — allowed for repetitive non-sensitive tasks | 8645–8646 | M00489 | composite | true |
| F02446 | Profile high_risk — human gate for credentials / purchases / deletes / sends | 8648–8649 | M00490 | composite | true |
| F02447 | "Profiles matter deeply here. A GUI agent can do real harm." | 8652 | E0274 | composite | false |
| F02448 | Action Policy Bits — bits 0..7 action type (click/type/scroll/hotkey/upload/download) | 8659 | M00491 | composite | false |
| F02449 | Action Policy Bits — bits 8..15 target class (button/input/menu/file/payment) | 8660 | M00491 | composite | false |
| F02450 | Action Policy Bits — bits 16..23 risk (credential/payment/delete/send/external) | 8661 | M00491 | composite | false |
| F02451 | Action Policy Bits — bits 24..31 environment (host/vm/browser/sandbox) | 8662 | M00491 | composite | false |
| F02452 | Action Policy Bits — bits 32..39 confidence | 8663 | M00491 | composite | false |
| F02453 | Action Policy Bits — bits 40..47 step budget | 8664 | M00491 | composite | false |
| F02454 | Action Policy Bits — bits 48..55 human gate state | 8665 | M00491 | composite | false |
| F02455 | Action Policy Bits — bits 56..63 audit flags | 8666 | M00491 | composite | false |
| F02456 | AVX-512 batch action validation — `allowed = confidence_ok & target_valid & permission_ok & not_high_risk_without_gate` | 8670–8676 | E0275 | composite | false |
| F02457 | RLM stores UI environment — screenshots / parsed elements / DOM-a11y tree / action history / state machine / observations | 8684–8691 | E0276 | composite | false |
| F02458 | RLM recursive inspect — which earlier screen had the export button | 8696 | E0276 | composite | false |
| F02459 | RLM recursive inspect — what changed after clicking settings | 8697 | E0276 | composite | false |
| F02460 | RLM recursive inspect — which path led to this dialog | 8698 | E0276 | composite | false |
| F02461 | RLM recursive inspect — what is the shortest safe path to finish | 8699 | E0276 | composite | false |
| F02462 | "This is long-horizon computer use" | 8702 | E0276 | composite | false |
| F02463 | Reward — trajectory scoring metric: task progress | 8709 | E0276 | composite | false |
| F02464 | Reward — wrong click penalty | 8710 | E0276 | composite | false |
| F02465 | Composite — Computer-Use Plane architecture component (8 sub-parts: screen parser / GUI state model / action planner / policy gate / executor / trajectory memory / GUI verifier / state-machine learner) + key line "Computer-use intelligence is not clicking. It is converting visual chaos into typed state transitions under policy" + 7-component plug map (SLM reflexes / RLM long-horizon UI history nav / PRM-RM trajectory value / AVX-512 action law + scheduling / Blackwell judgment / 4090 perception-action scout / ZFS replay+learning) — station has eyes, hands, memory, law, and judgment | 8771–8802 | E0277 | composite | false |

## Requirements (R04761–R04930)

| R ID | Phrase | Dump line | Parent | Class | Opt-in | Sub-reqs |
|---|---|---|---|---|---|---|
| R04761 | Computer-use intelligence is the bridge from "thinking system" to "acting system" | 8490–8492 | E0268 | non-negotiable | false | 10 |
| R04762 | The station grows hands and eyes | 8490 | E0268 | non-negotiable | false | 10 |
| R04763 | Research substrate — Microsoft Fara-7B cited (agentic SLM, 145K trajectories, 1M steps) | 8496 | F02384 + F02385 | non-negotiable | true | 10 |
| R04764 | Research substrate — OmniParser V2 cited (screenshots → structured interactable elements) | 8497 | F02386 | non-negotiable | true | 10 |
| R04765 | Research substrate — ActionEngine cited (state-machine memory; 95% on Reddit WebArena; 1 LLM call; 11.8x cost reduction; 2x latency reduction) | 8498 | F02388–F02392 | non-negotiable | true | 10 |
| R04766 | Research substrate — GUI-R1 + ShowUI cited (VLA models for GUI actions, RL-style, unified action spaces) | 8499 | F02393 | non-negotiable | true | 10 |
| R04767 | Research substrate — OSWorld + WebArena + ScreenSpot cited as benchmarks | 8500 | F02394 | non-negotiable | true | 10 |
| R04768 | Add a Computer-Use Plane | 8502 | E0270 | non-negotiable | false | 10 |
| R04769 | Computer-Use Plane has 3 layers | 8506 | E0270 | non-negotiable | false | 10 |
| R04770 | Layer Perception — screenshot → UI elements → bounding boxes → semantic labels | 8509 | M00476 | non-negotiable | false | 10 |
| R04771 | Layer Planning — task → current UI state → action plan / state machine | 8512 | M00477 | non-negotiable | false | 10 |
| R04772 | Layer Execution — click / type / scroll / hotkey / file / browser actions under policy | 8515 | M00478 | non-negotiable | false | 10 |
| R04773 | "Take screenshot, ask big model, click, repeat" is expensive and brittle (non-pattern) | 8519–8521 | E0270 | non-negotiable | false | 10 |
| R04774 | Better-move step 1 — perceive once | 8526 | F02401 | non-negotiable | false | 10 |
| R04775 | Better-move step 2 — build UI state machine | 8527 | F02402 | non-negotiable | false | 10 |
| R04776 | Better-move step 3 — act programmatically | 8528 | F02403 | non-negotiable | false | 10 |
| R04777 | Better-move step 4 — only re-query model when state changes or uncertainty rises | 8529 | F02404 | non-negotiable | false | 10 |
| R04778 | Better-move pattern is what ActionEngine is pointing toward | 8532 | M00479 | non-negotiable | false | 10 |
| R04779 | Hardware mapping — 4090 runs Fara-7B / OmniParser / GUI SLM / vision-action scout | 8537–8538 | F02406 | non-negotiable | true | 10 |
| R04780 | Hardware mapping — Blackwell runs high-level task reasoning / recovery / final verification | 8540–8541 | F02407 | non-negotiable | true | 10 |
| R04781 | Hardware mapping — CPU AVX-512 runs UI state machine | 8544 | F02408 | non-negotiable | true | 10 |
| R04782 | Hardware mapping — CPU AVX-512 runs action policy | 8545 | F02408 | non-negotiable | true | 10 |
| R04783 | Hardware mapping — CPU AVX-512 runs bounding-box filtering | 8546 | F02408 | non-negotiable | true | 10 |
| R04784 | Hardware mapping — CPU AVX-512 runs permission checks | 8547 | F02408 | non-negotiable | true | 10 |
| R04785 | Hardware mapping — CPU AVX-512 runs replay | 8548 | F02408 | non-negotiable | true | 10 |
| R04786 | Hardware mapping — CPU AVX-512 runs duplicate state detection | 8549 | F02408 | non-negotiable | true | 10 |
| R04787 | Hardware mapping — RAM/ZFS stores UI maps / trajectories / screenshots / action logs / learned workflows | 8551–8552 | F02409 | non-negotiable | true | 10 |
| R04788 | 4090 = eyes and reflexes | 8555 | F02410 | non-negotiable | false | 10 |
| R04789 | CPU = motor control law | 8556 | F02411 | non-negotiable | false | 10 |
| R04790 | Blackwell = strategic judgment | 8557 | F02412 | non-negotiable | false | 10 |
| R04791 | A screen should become structured state | 8561 | M00480 | non-negotiable | false | 10 |
| R04792 | GUI state JSON field — window | 8565 | F02413 | non-negotiable | true | 10 |
| R04793 | GUI state JSON field — url | 8566 | F02414 | non-negotiable | true | 10 |
| R04794 | GUI state JSON field — elements array | 8567 | M00480 | non-negotiable | false | 10 |
| R04795 | GUI element field — id (integer) | 8569 | F02415 | non-negotiable | true | 10 |
| R04796 | GUI element field — type (e.g. button) | 8570 | F02416 | non-negotiable | true | 10 |
| R04797 | GUI element field — text (e.g. "Submit") | 8571 | F02417 | non-negotiable | true | 10 |
| R04798 | GUI element field — bbox `[x1, y1, x2, y2]` | 8572 | F02418 | non-negotiable | true | 10 |
| R04799 | GUI element field — interactable (bool) | 8573 | F02419 | non-negotiable | true | 10 |
| R04800 | GUI element field — risk (low / medium / high) | 8574 | F02420 | non-negotiable | true | 10 |
| R04801 | Actions are NOT free-form (typed) | 8580 | M00481 | non-negotiable | false | 10 |
| R04802 | Typed action field — action (e.g. click) | 8584 | F02422 | non-negotiable | true | 10 |
| R04803 | Typed action field — target_id (references element.id) | 8585 | F02423 | non-negotiable | true | 10 |
| R04804 | Typed action field — reason (e.g. "submit completed form") | 8586 | F02424 | non-negotiable | true | 10 |
| R04805 | Typed action field — requires_confirmation (bool) | 8587 | F02425 | non-negotiable | true | 10 |
| R04806 | Runtime check — target exists | 8594 | F02426 | non-negotiable | true | 10 |
| R04807 | Runtime check — target is interactable | 8595 | F02427 | non-negotiable | true | 10 |
| R04808 | Runtime check — action allowed | 8596 | F02428 | non-negotiable | true | 10 |
| R04809 | Runtime check — risk acceptable | 8597 | F02429 | non-negotiable | true | 10 |
| R04810 | Runtime check — credential / payment / destructive state | 8598 | F02430 | non-negotiable | true | 10 |
| R04811 | Runtime check — human gate needed | 8599 | F02431 | non-negotiable | true | 10 |
| R04812 | State-machine memory — for repeated workflows, learn state machines | 8604 | M00483 | non-negotiable | false | 10 |
| R04813 | State-machine example — login_page → credentials_page | 8608 | F02433 | non-negotiable | true | 10 |
| R04814 | State-machine example — credentials_page → dashboard | 8609 | F02433 | non-negotiable | true | 10 |
| R04815 | State-machine example — dashboard → search_results | 8610 | F02433 | non-negotiable | true | 10 |
| R04816 | State-machine example — search_results → detail_page | 8611 | F02433 | non-negotiable | true | 10 |
| R04817 | State-machine example — detail_page → export_dialog | 8612 | F02433 | non-negotiable | true | 10 |
| R04818 | State-machine example — export_dialog → downloaded_file | 8613 | F02433 | non-negotiable | true | 10 |
| R04819 | State attribute — recognition features | 8619 | F02434 | non-negotiable | true | 10 |
| R04820 | State attribute — allowed actions | 8620 | F02435 | non-negotiable | true | 10 |
| R04821 | State attribute — expected transitions | 8621 | F02436 | non-negotiable | true | 10 |
| R04822 | State attribute — failure handlers | 8622 | F02437 | non-negotiable | true | 10 |
| R04823 | State attribute — risk flags | 8623 | F02438 | non-negotiable | true | 10 |
| R04824 | "Agent does not need to reason from scratch every time" | 8626 | M00483 | non-negotiable | false | 10 |
| R04825 | "This is intelligence crystallizing into procedure" | 8628 | M00483 | non-negotiable | false | 10 |
| R04826 | Profile observe_only — screenshot / parse, no actions | 8633–8634 | M00485 | non-negotiable | true | 10 |
| R04827 | Profile assistive — suggest actions, user clicks | 8636–8637 | M00486 | non-negotiable | true | 10 |
| R04828 | Profile supervised — agent acts, asks before risky steps | 8639–8640 | M00487 | non-negotiable | true | 10 |
| R04829 | Profile sandbox — agent acts freely in VM/browser sandbox | 8642–8643 | M00488 | non-negotiable | true | 10 |
| R04830 | Profile autonomous_low_risk — allowed for repetitive non-sensitive tasks | 8645–8646 | M00489 | non-negotiable | true | 10 |
| R04831 | Profile high_risk — human gate for credentials / purchases / deletes / sends | 8648–8649 | M00490 | non-negotiable | true | 10 |
| R04832 | "Profiles matter deeply here. A GUI agent can do real harm." | 8652 | E0274 | non-negotiable | false | 10 |
| R04833 | Action Policy Bits — 64-bit capability word per GUI action | 8657 | M00491 | non-negotiable | false | 10 |
| R04834 | APB bits 0..7 — action type (click/type/scroll/hotkey/upload/download) | 8659 | F02448 | non-negotiable | true | 10 |
| R04835 | APB bits 8..15 — target class (button/input/menu/file/payment) | 8660 | F02449 | non-negotiable | true | 10 |
| R04836 | APB bits 16..23 — risk (credential/payment/delete/send/external) | 8661 | F02450 | non-negotiable | true | 10 |
| R04837 | APB bits 24..31 — environment (host/vm/browser/sandbox) | 8662 | F02451 | non-negotiable | true | 10 |
| R04838 | APB bits 32..39 — confidence | 8663 | F02452 | non-negotiable | true | 10 |
| R04839 | APB bits 40..47 — step budget | 8664 | F02453 | non-negotiable | true | 10 |
| R04840 | APB bits 48..55 — human gate state | 8665 | F02454 | non-negotiable | true | 10 |
| R04841 | APB bits 56..63 — audit flags | 8666 | F02455 | non-negotiable | true | 10 |
| R04842 | AVX-512 evaluates batches of candidate actions | 8669 | E0275 | non-negotiable | false | 10 |
| R04843 | AVX-512 mask — `allowed = confidence_ok & target_valid & permission_ok & not_high_risk_without_gate` | 8672–8676 | F02456 | non-negotiable | false | 10 |
| R04844 | RLM stores UI environment (not just screenshots) | 8683 | E0276 | non-negotiable | false | 10 |
| R04845 | RLM stores — screenshots | 8685 | F02457 | non-negotiable | true | 10 |
| R04846 | RLM stores — parsed elements | 8686 | F02457 | non-negotiable | true | 10 |
| R04847 | RLM stores — DOM/accessibility tree if available | 8687 | F02457 | non-negotiable | true | 10 |
| R04848 | RLM stores — action history | 8688 | F02457 | non-negotiable | true | 10 |
| R04849 | RLM stores — state machine | 8689 | F02457 | non-negotiable | true | 10 |
| R04850 | RLM stores — observations | 8690 | F02457 | non-negotiable | true | 10 |
| R04851 | RLM recursively inspects — which earlier screen had the export button | 8696 | F02458 | non-negotiable | true | 10 |
| R04852 | RLM recursively inspects — what changed after clicking settings | 8697 | F02459 | non-negotiable | true | 10 |
| R04853 | RLM recursively inspects — which path led to this dialog | 8698 | F02460 | non-negotiable | true | 10 |
| R04854 | RLM recursively inspects — what is the shortest safe path to finish | 8699 | F02461 | non-negotiable | true | 10 |
| R04855 | "This is long-horizon computer use" | 8702 | E0276 | non-negotiable | false | 10 |
| R04856 | Computer-use agents need trajectory scoring | 8706 | E0276 | non-negotiable | false | 10 |
| R04857 | Trajectory score — task progress | 8709 | F02463 | non-negotiable | true | 10 |
| R04858 | Trajectory score — wrong click penalty | 8710 | F02464 | non-negotiable | true | 10 |
| R04859 | Trajectory score — loop detection | 8711 | E0276 | non-negotiable | true | 10 |
| R04860 | Trajectory score — sensitive field penalty | 8712 | E0276 | non-negotiable | true | 10 |
| R04861 | Trajectory score — success state reached | 8713 | E0276 | non-negotiable | true | 10 |
| R04862 | Trajectory score — human correction | 8714 | E0276 | non-negotiable | true | 10 |
| R04863 | Trajectory score — latency | 8715 | E0276 | non-negotiable | true | 10 |
| R04864 | Trajectory score — number of steps | 8716 | E0276 | non-negotiable | true | 10 |
| R04865 | Fara repo mentions CUAVerifierBench for judging trajectories — fits Value-Plane idea | 8719 | E0276 | non-negotiable | false | 10 |
| R04866 | GUI verifier scores — was the action valid? | 8724 | E0276 | non-negotiable | true | 10 |
| R04867 | GUI verifier scores — did it move toward goal? | 8725 | E0276 | non-negotiable | true | 10 |
| R04868 | GUI verifier scores — was it safe? | 8726 | E0276 | non-negotiable | true | 10 |
| R04869 | GUI verifier scores — was it efficient? | 8727 | E0276 | non-negotiable | true | 10 |
| R04870 | GUI verifier scores — did it require user consent? | 8728 | E0276 | non-negotiable | true | 10 |
| R04871 | Replay is MANDATORY — every GUI action logs | 8733 | E0277 | non-negotiable | false | 10 |
| R04872 | Replay log entry — screenshot before | 8736 | E0277 | non-negotiable | true | 10 |
| R04873 | Replay log entry — parsed UI state | 8737 | E0277 | non-negotiable | true | 10 |
| R04874 | Replay log entry — proposed action | 8738 | E0277 | non-negotiable | true | 10 |
| R04875 | Replay log entry — policy decision | 8739 | E0277 | non-negotiable | true | 10 |
| R04876 | Replay log entry — actual action | 8740 | E0277 | non-negotiable | true | 10 |
| R04877 | Replay log entry — screenshot after | 8741 | E0277 | non-negotiable | true | 10 |
| R04878 | Replay log entry — state transition | 8742 | E0277 | non-negotiable | true | 10 |
| R04879 | Replay log entry — result | 8743 | E0277 | non-negotiable | true | 10 |
| R04880 | Replay makes computer use auditable and trainable | 8746 | E0277 | non-negotiable | false | 10 |
| R04881 | The proper exploit — do not make the GUI agent a magical cursor | 8750 | E0277 | non-negotiable | false | 10 |
| R04882 | The proper exploit — make it a typed action system | 8752 | E0277 | non-negotiable | false | 10 |
| R04883 | Typed action system step — perception model proposes state | 8755 | E0277 | non-negotiable | true | 10 |
| R04884 | Typed action system step — planner proposes transition | 8756 | E0277 | non-negotiable | true | 10 |
| R04885 | Typed action system step — policy approves action | 8757 | E0277 | non-negotiable | true | 10 |
| R04886 | Typed action system step — executor performs action | 8758 | E0277 | non-negotiable | true | 10 |
| R04887 | Typed action system step — observer validates transition | 8759 | E0277 | non-negotiable | true | 10 |
| R04888 | Typed action system step — memory stores trajectory | 8760 | E0277 | non-negotiable | true | 10 |
| R04889 | Typed action system step — reward model scores it | 8761 | E0277 | non-negotiable | true | 10 |
| R04890 | Typed action system step — state machine improves | 8762 | E0277 | non-negotiable | true | 10 |
| R04891 | "That is how computer use becomes reliable" | 8765 | E0277 | non-negotiable | false | 10 |
| R04892 | New architecture component — Computer-Use Plane | 8771 | M00492 | non-negotiable | false | 10 |
| R04893 | Computer-Use Plane sub-part — screen parser | 8773 | M00492 | non-negotiable | true | 10 |
| R04894 | Computer-Use Plane sub-part — GUI state model | 8774 | M00492 | non-negotiable | true | 10 |
| R04895 | Computer-Use Plane sub-part — action planner | 8775 | M00492 | non-negotiable | true | 10 |
| R04896 | Computer-Use Plane sub-part — policy gate | 8776 | M00492 | non-negotiable | true | 10 |
| R04897 | Computer-Use Plane sub-part — executor | 8777 | M00492 | non-negotiable | true | 10 |
| R04898 | Computer-Use Plane sub-part — trajectory memory | 8778 | M00492 | non-negotiable | true | 10 |
| R04899 | Computer-Use Plane sub-part — GUI verifier | 8779 | M00492 | non-negotiable | true | 10 |
| R04900 | Computer-Use Plane sub-part — state-machine learner | 8780 | M00492 | non-negotiable | true | 10 |
| R04901 | Key line — "Computer-use intelligence is not clicking" | 8786 | E0277 | non-negotiable | false | 10 |
| R04902 | Key line — "It is converting visual chaos into typed state transitions under policy" | 8787 | E0277 | non-negotiable | false | 10 |
| R04903 | Plug map — SLM = local reflexes | 8793 | E0277 | non-negotiable | false | 10 |
| R04904 | Plug map — RLM = long-horizon UI history navigation | 8794 | E0277 | non-negotiable | false | 10 |
| R04905 | Plug map — PRM/RM = trajectory value | 8795 | E0277 | non-negotiable | false | 10 |
| R04906 | Plug map — AVX-512 = action law and scheduling | 8796 | E0277 | non-negotiable | false | 10 |
| R04907 | Plug map — Blackwell = high-level judgment | 8797 | E0277 | non-negotiable | false | 10 |
| R04908 | Plug map — 4090 = perception/action scout | 8798 | E0277 | non-negotiable | false | 10 |
| R04909 | Plug map — ZFS = replay and learning | 8799 | E0277 | non-negotiable | false | 10 |
| R04910 | "Now the station has eyes, hands, memory, law, and judgment" | 8802 | E0277 | non-negotiable | false | 10 |
| R04911 | Computer-Use Plane integrates with Value Plane (M027) — trajectory scoring + reward | 8704–8717 | E0276 | non-negotiable | false | 10 |
| R04912 | Computer-Use Plane integrates with Memory Plane (M028) — trajectory memory + state-machine memory | 8602–8628 + 8760 | E0273 + E0277 | non-negotiable | false | 10 |
| R04913 | Computer-Use Plane integrates with SLM swarm (M026) — Fara-7B is the SLM tier; 4090-resident | 8537–8538 + 8793 | E0271 | non-negotiable | false | 10 |
| R04914 | Computer-Use Plane integrates with RLM engine (M026) — RLM is the long-horizon UI history navigator | 8794 | E0276 | non-negotiable | false | 10 |
| R04915 | Computer-Use Plane integrates with RM/PRM judges (M026) — PRM/RM trajectory scoring | 8795 | E0276 | non-negotiable | false | 10 |
| R04916 | Computer-Use Plane integrates with AVX-512 reward scheduling (M027 E0255) — APB bit evaluation | 8669–8676 | E0275 | non-negotiable | false | 10 |
| R04917 | Project boundary — IPS-side computer-use policy enforcement (e.g. agent-guard policies for GUI agents) flows via MS007 typed-mirror crates + MS006 functional modules, NOT direct sovereign-os crate import | architecture | E0277 | non-negotiable | false | 10 |
| R04918 | Project boundary — Computer-Use Plane is sovereign-os runtime; selfdef may observe GUI action events via selfdef-collector-eventstream | architecture | E0277 | non-negotiable | false | 10 |
| R04919 | Project boundary — selfdef-responder ZFS rollback on Computer-Use Plane high-risk Malicious verdict (via MS003 + Oracle-Triage MS004 E0036) | MS003 + MS004 E0036 | E0274 | non-negotiable | false | 10 |
| R04920 | Profile high_risk requires human-gate-state APB bits != 0 before executor performs action | 8648 + 8665 | M00490 + F02454 | non-negotiable | false | 10 |
| R04921 | Profile observe_only forbids any action.action != observe (executor refuses) | 8633 | M00485 | non-negotiable | false | 10 |
| R04922 | Profile sandbox restricts environment APB bits to vm/browser/sandbox (host forbidden) | 8642 + 8662 | M00488 + F02451 | non-negotiable | false | 10 |
| R04923 | Profile autonomous_low_risk requires risk APB bits 16..23 != credential|payment|delete|send|external | 8645 + 8661 | M00489 + F02450 | non-negotiable | false | 10 |
| R04924 | Replay log is the trainable corpus for state-machine learner | 8746 + 8780 | E0277 | non-negotiable | false | 10 |
| R04925 | Replay log is the audit corpus for the GUI verifier + trajectory scoring | 8746 + 8779 | E0277 | non-negotiable | false | 10 |
| R04926 | UI state machine prevents reasoning-from-scratch on repeated workflows (CPU efficiency claim) | 8626 | M00483 | non-negotiable | false | 10 |
| R04927 | Action Policy Bit confidence (bits 32..39) feeds into AVX-512 mask `confidence_ok` predicate | 8663 + 8673 | F02452 + F02456 | non-negotiable | false | 10 |
| R04928 | Action Policy Bit human_gate_state (bits 48..55) feeds into AVX-512 mask `not_high_risk_without_gate` predicate | 8665 + 8675 | F02454 + F02456 | non-negotiable | false | 10 |
| R04929 | Computer-Use Plane is the 9th plane (extending the 8-plane full stack from M027 R04590; M028 added Memory OS as a refinement; M029 adds Computer-Use Plane as the actuator extension) | 8771–8781 + cross-ref M027 R04590 | E0277 | non-negotiable | false | 10 |
| R04930 | Composite — Computer-Use Plane converts visual chaos into typed state transitions under policy; integrates with M025 cognitive compiler (intent → DAG → GUI plan) + M026 SLM swarm / RLM engine / RM-PRM judges + M027 Value Plane (trajectory scoring) + M028 Memory OS (trajectory memory + state-machine memory) | 8475–8804 | E0277 | non-negotiable | false | 10 |

## Cross-references

- Adjacent dump-range milestones: M028 Memory OS (8121–8475) / M030 World Model plane (8804–9151)
- Plane integration: M025 cognitive compiler / M026 SLM swarm + RLM engine + RM/PRM judges / M027 Value Plane / M028 Memory OS / M030 World Model
- Selfdef boundary: any IPS-side computer-use policy enforcement flows via MS006 functional modules + MS007 typed-mirror crates; Oracle-Triage MS004 E0036 carries Malicious verdicts that trigger selfdef-responder ZFS rollback
- Hardware exploit doctrine (sovereign-os repo) — SDD parallel for action-bit AVX-512 mask evaluation patterns
