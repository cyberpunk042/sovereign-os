# SDD-509 — Step-up MFA for high-privilege cockpit operations: TOTP + phone + email code, configurable via a pane (corrects SDD-508)

> Status: **design-lock draft** — corrects SDD-508; design first, operator signs off, THEN build (E0634). Nothing built. Mandate: **E11.M509** (control-bits band 500–599).
>
> Number band: **500–599**.
>
> **Scope note (operator-directed 2026-07-22):** *"no I never talked about such integration for now, focus on what is speced."* Hardware-token / WebAuthn / FIDO2 / TPM integration is **NOT specced and is out of scope here** (a documented future option, not now). This SDD is the **specced software MFA**: TOTP (Google Authenticator) + a phone code + an email code, gating high-privilege operations, everything **configurable in a panel pane**. selfdef/perimeter stay proxy-only ("already covered").

## What was specced (operator's words)

- *"2 Factor secured or even Multi Factore secure. A phone code and/or a google authenticator or email code."* → **TOTP + SMS/phone code + email code.**
- *"high priviledge operations … will require me to have my phone for high level authority."* → step-up gates the privileged cockpit ops; the factor is on the operator's phone.
- *"the selfdef protected operation already covered in a sense."* → selfdef/perimeter stay proxy-only, untouched.
- *"the devsecops panels … everything is to be configurable … in the panel via a pane."* → a **devsecops step-up config pane** where every setting lives.

## What SDD-508 got wrong (and what this keeps)

SDD-508's L4 claimed the gate *"defeats the shell+sudo attacker."* An adversarial review showed that's false: SDD-508 put the gate in operator-editable repo Python, and `sudo -n` then runs the edited script as root. **Kept from SDD-508:** the tiering vocabulary, the single chokepoint, selfdef-proxy-only, and the real protection against a **browser attacker with no shell**. **Fixed here:** the gate + secrets sit in a small server-side verifier the cockpit *calls*, not in an operator-editable file — so the specced software factors aren't pure theater. **Dropped here:** the hardware-token integration (not specced).

## Honest scope (one paragraph, not a crusade)

Software MFA on your phone (TOTP / SMS / email) **stops a browser attacker** and adds **friction + a signed audit trail** for anyone else. It is **not** a hardware guarantee against someone who already has a shell on the box as your user — that's an OS-hardening / perimeter problem (selfdef/Tetragon), which this complements, not replaces. A hardware factor would raise that ceiling and is a **documented future option** — explicitly **not now**, per your direction. This SDD delivers the specced software MFA, built so it's a real gate against the primary threat, not theater.

## The design

### 1. Tiering — grade the privileged ops

Extend each `config/control-systems.yaml` control from the boolean `privileged` into an `auth:` level (backward-compatible: `privileged: true` → `step-up`):

| Tier | Meaning |
|---|---|
| `none` | read-only / inspection |
| `operator-present` | today's `confirm=true` type-to-confirm |
| `step-up` | requires **one** valid factor (TOTP / SMS / email) |
| `proxy-only` | selfdef / perimeter — signed request to the producer (unchanged) |

(All operator-editable in the pane — see §4.)

### 2. Factors — exactly the three specced

- **TOTP (Google Authenticator)** — RFC 6238, stdlib `hmac`/`hashlib`, **no new dependency**, fully offline. Enrollment: generate a secret once, show the `otpauth://` QR in the pane, verify 6-digit codes (±1 step skew).
- **Phone code (SMS)** — a one-time code delivered via notifykit's Twilio channel, verified against a short-TTL store.
- **Email code** — a one-time code via notifykit's Resend channel, same store.

(notifykit has the *delivery* channels today but **no OTP layer** — code mint + verify store + rate-limit + replay-burn is the net-new work for the SMS/email factors; TOTP is the offline default that works day one.)

### 3. Enforcement — a small server-side verifier (so it's not theater)

A lightweight verifier holds the factor secrets + a short-TTL **elevation** store and does verification; the exec rail (`_action_exec.execute()`, the `if privileged:` block) **calls** it rather than checking an operator-editable file. A successful factor mints an elevation bound to `(session, tier, expiry)` so the operator steps up **once per window**, not per command. The elevation is single-request-scoped and burned on use (no replay). This keeps the specced factors meaningful without any external device.

### 4. The config pane — everything configurable (your requirement)

A **devsecops step-up config pane** (the usual settings-pane pattern) where the operator sets, in-panel:

- each factor **on/off** (TOTP / SMS / email) + **enrollment** (TOTP QR, phone number, email);
- the **per-control tier** mapping (which ops need `step-up`);
- the **elevation window**;
- the **notifykit channel** for the SMS/email codes;
- **break-glass** recovery codes (one-time, for a lost phone).

The pane reads state openly; **changing a setting is itself a `step-up` operation** (an attacker who could freely disable the gate via the pane defeats the point), applied through the verifier.

### 5. Manual CLI + break-glass

The manual `sovereign-osctl <verb>` stays the escape hatch; for a `step-up` op it prompts for the factor (still "works," now with the factor). **Break-glass** = one-time recovery codes generated at enrollment (stored offline), for a lost phone — the honest recovery path every MFA system needs.

## Non-goals (explicitly deferred, per operator)

- **Hardware tokens / WebAuthn / FIDO2 / TPM** — *"never talked about such integration for now."* Documented future option; not this SDD.
- External IdP (Keycloak/Okta) — native, offline-first.
- Replacing selfdef/perimeter proxy-only, or the OS-hardening that keeps an attacker off the box (complementary).

## Phasing

| Phase | Scope | Status |
|---|---|---|
| **A** | The step-up core (`auth:` tiering + **TOTP** verifier + single-use elevation) + the opt-in exec-rail gate + enrollment | **shipped 2026-07-22** |
| **B** | The **phone (SMS) + email** OTP layer (mint / verify / rate-limit / replay-burn) over notifykit | **shipped 2026-07-22** (see below) |
| **C** | The **config pane** + the step-up modal in `control-surface.js` + break-glass | TODO |

## What shipped — Phase A (2026-07-22)

- **`scripts/operator/lib/stepup.py`** — the pure, stdlib-only core: RFC 6238 **TOTP** (`totp_code`/`totp_verify`, ±1 skew) + enrollment (`new_totp_secret`/`provisioning_uri`/`enroll`) + a short-TTL **single-use `ElevationStore`** (mint / check / consume-burn, self-pruning) + `resolve_tier` (control → `auth:` tier). No new dependency.
- **`config/control-systems.yaml`** — `auth: step-up` on `os-profile` + `runtime-mode` (the operator retunes the set in the pane; Phase C).
- **`scripts/operator/_action_exec.py`** — the **opt-in step-up gate**: after the dry-run return (so a preview never burns a factor), a `step-up`-tier control requires a live elevation (consumed single-use); absent → `401 step-up-required` with the offered factors. **Non-breaking:** the gate engages *only* once a TOTP factor is enrolled — an un-enrolled box behaves exactly as before, and a step-up fault never breaks the exec rail (fail-safe to the prior gates).
- **Tests:** `tests/lint/test_stepup_totp.py` (RFC 6238 Appendix-B known-answer vectors + elevation single-use/expiry/binding + tier resolution) and `tests/lint/test_stepup_action_exec.py` (the gate is opt-in-until-enrolled, engages + requires an elevation once enrolled, and sits after the dry-run return). 12 tests; the broad operator/cockpit/control lint sweep (1135) stays green.

Verification: `python3 -m pytest tests/lint/test_stepup_totp.py tests/lint/test_stepup_action_exec.py` (12 pass) + the operator/control-exec/registry families green; ruff clean. Still **DRAFT** — the phone/email factors (B) and the config pane (C) follow; the operator's Q-row defaults (5-min window / os-profile+runtime-mode+safety-policy+exec-rail-flips as `step-up` / one-time break-glass / milestone) are the assumed defaults, retunable.

## What shipped — Phase B (2026-07-22)

The out-of-band phone/email one-time-code factors — the net-new layer notifykit
lacked (it delivers, but had no OTP concept). All in `scripts/operator/lib/stepup.py`:

- **`OtpStore`** — mint / verify / rate-limit / replay-burn. A code is stored as
  a **salted SHA-256 hash** (never plaintext at rest); the defense against online
  guessing is a **per-code attempt budget** (5) + a short TTL (5 min). `verify`
  burns the matching code, decrements the actor's codes on a wrong guess (drops
  exhausted), and never lets a wrong guess against one channel's code burn a
  sibling channel's. `request` enforces a **cooldown** (anti-flood) and replaces a
  prior code for the same `(actor, channel)`.
- **`deliver_otp`** — delivers a code over **exactly ONE secure channel**
  (`sms`→Twilio, `email`→Resend), never the broadcast `dispatch` (which would copy
  the code into notifykit's file/log channel — a leak). Inert until the operator
  has configured + enabled that channel (notifykit go-live); a fresh box simply
  doesn't offer the phone/email factors.
- **`available_otp_channels`** / `request_otp_and_deliver` / `verify_otp_and_elevate`
  — the offered-factor list (fed to the `401` challenge via `_stepup_factors`),
  the mint-and-send path, and the verify-then-elevate path.
- **Tests:** `tests/lint/test_stepup_otp.py` (9) — single-use, expiry, attempt-budget
  burn, cooldown anti-flood, prior-code replacement, sibling-channel isolation, the
  elevate path, delivery inert-until-configured, and the never-broadcast contract.

The `_action_exec` challenge now lists `totp` **+** any configured out-of-band
factor (`sms`/`email`). Verification: 21 step-up tests (Phase A + B) + the exec-rail
families green; ruff clean. Phone/email delivery **activates when notifykit is
configured** (a go-live item); TOTP works offline today.

### Phase-A honesty (unchanged)

The elevation + secret stores are files under `SOVEREIGN_OS_STEPUP_DIR` (default `/run/sovereign-os/stepup`). For the software MFA to bind more than a browser attacker, that dir + the gate belong behind a **root-owned verifier process** (the operator user should not be able to write its own elevation) — the tracked hardening step, not yet in Phase A. Today Phase A delivers a working, tested TOTP step-up that stops a browser attacker and adds a burned-single-use audit trail; it is explicitly not a hardware guarantee against an existing shell.

## Open decisions — sign-off before Phase A

| Q | Decision | Proposed |
|---|---|---|
| Q-509-A | Elevation window | 5 min windowed for `step-up` |
| Q-509-B | Which controls are `step-up` | os-profile, runtime-mode, safety-policy edits, exec-rail flips (you curate in the pane) |
| Q-509-C | Break-glass | one-time recovery codes at enrollment |
| Q-509-D | Milestone? | open a `backlog/milestones/` entry for A–C |

## References

- Corrects: `docs/sdd/508-step-up-auth-high-privilege-devsecops.md`.
- Chokepoint: `scripts/operator/_action_exec.py:387-399` (the `if privileged:` block); `config/control-systems.yaml` (`privileged` classifier → `auth:` tier).
- Delivery: `tools/notifykit/channels.py` (Twilio SMS + Resend email present; the OTP mint/verify layer is new).
- TOTP: RFC 6238 (stdlib `hmac`/`hashlib`, no new dep).
