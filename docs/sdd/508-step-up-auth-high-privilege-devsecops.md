# SDD-508 — Step-up authentication for high-privilege cockpit operations (devsecops MFA)

> Status: **design-lock draft** — design first, operator signs off, THEN build (E0634). Mandate: **E11.M508** (control-bits band 500–599, this session's band).
>
> Number band: **500–599**. Nothing here is built; this SDD specifies the architecture + phasing + the decisions that need the operator's call before any code.
>
> Operator directive 2026-07-22 (verbatim): *"imagine there is an attacker on my code console, for some commands in the claude settings that will be 2 Factor secured or even Multi Factore secure. A phone code and/or a google authenticator or email code. since its a high priviledge operabtions it will require me to have my phone for high level authority but the selfdef protected operation already covered in a sense. This will ve I guess the devsecops panels, we need to think about this properly and come up with the right engineered ways to achieve this level of support and experience."* + *"lets take the time to do this right. I know what I want. its the best solution that include what I said I wanted."*

## Mission

An attacker on the cockpit **code console** must not be able to run a **high-privilege** command without the operator's **physical second factor** (phone). High-privilege operations require the operator to *possess their phone for high-level authority*; the **selfdef/perimeter** ops are already covered (signed-proxy only). This SDD designs the missing step-up layer — TOTP (Google Authenticator) **and** email/SMS code **and** an ed25519 signed challenge — as the best engineered solution, gated where a real adversary cannot bypass it.

## Threat model (what we are actually defending)

| Adversary | Capability today | Must be defeated |
|---|---|---|
| **T1 — browser attacker** | Reaches the loopback cockpit, drives `control-surface.js`, POSTs `/api/control/execute` with `confirm=true` | Yes — the primary case the operator named |
| **T2 — shell + sudo attacker** | Has a shell on the box and the cockpit sudoers rights → runs `sudo -n sovereign-osctl <verb>` **directly**, bypassing the web daemon | Yes — the stronger case; a web-only gate does NOT stop this |
| **T3 — misused agent** | An AI agent (Plan-Mode footgun / prompt-injection) issues a privileged verb | Yes — same chokepoint as T1/T2 |

Out of scope: an attacker who has already stolen the operator's phone **and** the box's at-rest secrets (defense-in-depth caps here; see § Honesty).

## What the gate is TODAY (grounded 2026-07-22)

Every privileged op funnels through **one** server-side dispatch — `scripts/operator/_action_exec.py::execute()`, the `if privileged:` block (`scripts/operator/_action_exec.py:387-399`). It authorizes with exactly:

1. loopback bind `127.0.0.1` (`scripts/operator/control-exec-api.py:118`) — a network gate, not an identity gate;
2. `operator_key_loaded()` — checks a **key file exists**, never reads it, never verifies a signature (`_action_exec.py:166-178`);
3. `confirm=true` — a boolean **from the same web request the attacker controls**.

A T1 attacker clears all three trivially; T2 skips the daemon entirely. `permission_classifier` (`scripts/operator/lib/permission_classifier.py:18-33`) and loopback are **self-declared non-boundaries**. `control.privileged` in `config/control-systems.yaml` is the existing "this op is high-privilege" classifier (auth-tier classifies *surfaces*, not ops).

## What already exists to build on (reuse, don't reinvent)

- **`control.privileged`** (`config/control-systems.yaml`) — the per-control high-privilege flag, consumed at `_action_exec.py:387`. The tiering (below) grades it.
- **`scripts/lib/ms003.py`** — a real **ed25519 sign/verify + trust-anchor store** (`/etc/sovereign-os/ms003-trust-anchors/`), stdlib-only (shells to `openssl`). `sign(record) -> "ms003:ed25519:<keyid>:<sig>"`, `verify(record, sig, pub)`, `canonical_bytes`, `keyid`. Today only key *presence* is checked — generalizing to a real **signed challenge** is the natural upgrade (possession-of-key, no shared secret).
- **notifykit** (`tools/notifykit/channels.py`) — email (Resend), SMS (Twilio), push (ntfy) channels, already invoked from the exec path. One-time-code delivery is **config-away, not code-away** (secrets/enabled-flags pending go-live).
- **selfdef proxy-only** (`SELFDEF_OWNED = {selfdef, perimeter}`, `_action_exec.py:53`) — the "already covered" precedent; stays as-is.

**Greenfield:** TOTP/OTP verification. No native second factor exists (the `mfa-grant-revocations` code is unrelated selfdef IPS plumbing; auth-tier punts MFA to an external IdP). A **TOTP verifier is RFC 6238 over stdlib `hmac`/`hashlib`** — no new dependency (honors the repo invariant).

## The design — a step-up layer over the one chokepoint

```
 privileged op (web T1 / CLI T2 / agent T3)
        │
        ▼
 ┌─ enforcement: require a valid ELEVATION for this op's tier ──────────────┐
 │   absent/expired  → 401 step-up-required + challenge {tier, factors[]}    │
 │   present + valid → proceed to run                                        │
 └───────────────────────────────────────────────────────────────────────────┘
        ▲ elevation is MINTED only by a verified SECOND FACTOR:
        │   · TOTP 6-digit           (offline · Google Authenticator)     ← everyday step-up
        │   · notifykit OTP          (email / SMS / push one-time code)   ← out-of-band channel
        │   · MS003 signed challenge (ed25519, possession-of-key)         ← step-up-STRONG authority
        │   · WebAuthn/FIDO passkey  (hardware, phishing-resistant)       ← PHASE 2
```

### L1 — Tiering: grade `privileged` into an auth requirement

Extend each `config/control-systems.yaml` control from a boolean to a graded `auth:` level (backward-compatible — `privileged: true` with no `auth:` defaults to `step-up`):

| Tier | Meaning | Example controls |
|---|---|---|
| `none` | read-only / inspection | the mirror panels |
| `operator-present` | today's `confirm=true` type-to-confirm | low-risk toggles |
| `step-up` | **any one** second factor (TOTP / OTP) | `os-profile`, `runtime-mode` |
| `step-up-strong` | an **MS003 ed25519 signature** ("phone for high-level authority") | safety-policy edits, exec-rail live-flip, sudoers changes |
| `proxy-only` | signed request to the producer, never local | `selfdef`, `perimeter` (unchanged) |

### L2 — The factors

- **TOTP (primary, offline).** Enrollment once: generate a secret, emit the `otpauth://` provisioning URI as a QR in the enrollment panel; the operator adds it to Google Authenticator. Verify a 6-digit code against the box clock (±1 step skew). Secret stored **at-rest-protected** (§ Honesty — vault/TPM decision).
- **notifykit OTP (out-of-band).** Mint a random code, deliver via email (Resend) / SMS (Twilio) / push (ntfy), verify against a short-TTL store. The email/SMS leg the operator named; rides the existing notifykit rail.
- **MS003 signed challenge (step-up-strong).** The box issues a nonce challenge; the operator signs it with their ed25519 key (`ms003.sign`); the box verifies against the trust anchor (`ms003.verify`). Possession-of-key, **no shared secret** — the strongest software factor, and it generalizes the existing presence-only check into a real cryptographic one.
- **WebAuthn/FIDO passkey (phase 2).** Hardware-bound, phishing-resistant, no shared secret — the gold standard; a browser WebAuthn ceremony + resident-credential verifier. Deferred to keep phase 1 shippable.

### L3 — Elevation session (the UX balance)

A successful factor mints a **short-TTL elevation** bound to `(session, tier, expiry)`, so the operator steps up **once** and high-privilege ops in that window pass — not a code per keystroke. Re-prompt on expiry or on a tier escalation (`step-up` → `step-up-strong`). Default window + per-op-vs-windowed is an operator decision (§ Q-rows). Stored server-side (an elevation store the enforcement point consults); the client holds only an opaque handle.

### L4 — Enforcement locus (the load-bearing choice — resolved to STRONG)

To defeat **T2 (shell + sudo)**, the elevation check cannot live only in the web daemon. The design places it at **two lines**:

1. **Web daemon (first line):** `_action_exec.py:387-399` returns `401 step-up-required` when no valid elevation covers the op's tier — protects T1/T3 with the full cockpit UX.
2. **`sovereign-osctl` (real boundary):** the privileged verb execution itself consults the elevation store (or a sudo-invoked `sovereign-os-stepup-gate` wrapper the sudoers allowlist points at) — so a direct `sudo sovereign-osctl <verb>` (T2) hits the same gate. This is the difference between "stops a browser attacker" and "stops a console attacker with a shell."

### L5 — Cockpit UX

`control-surface.js` gains a **step-up modal**: on `401 step-up-required`, render the challenge's offered factors (TOTP entry / "check your phone" for OTP / "sign the challenge" for MS003), POST to an elevation endpoint, then retry the op with the elevation handle. A **devsecops enrollment panel** hosts one-time TOTP provisioning (QR) + factor management. Preserves R10212 (the surface copies/executes only through the sanctioned rail).

## Honesty ledger (what this does and does NOT buy)

- **TOTP has a shared secret at rest** — only as strong as the box's protection of it (vault / TPM). An attacker who can read the seed can mint codes. → MS003 (possession-of-key) and WebAuthn (hardware) have **no shared secret** and are strictly stronger; TOTP is the *convenience* factor, MS003/WebAuthn the *authority* factor.
- **Loopback + `permission_classifier` are not boundaries** (self-declared). The step-up gate sits **below** both.
- **Client-side checks are theater** — enforcement is server-side (L4), the client only renders the challenge.
- **notifykit email/SMS depends on go-live** (secrets/enabled-flags) — the OTP-channel factor is inert until notifykit is configured; TOTP + MS003 work offline day one.
- Defense-in-depth **caps** at a stolen-phone-plus-stolen-at-rest-secrets adversary.

## Non-goals

- An **external IdP** (Keycloak/Okta) — auth-tier already punts enterprise MFA there; this is **native**, offline-first.
- Replacing **selfdef/perimeter proxy-only** — it stays the model for producer-owned ops.
- Gating **read-only** panels — only mutating (`privileged`) controls.
- Phase-1 WebAuthn — named, deferred.

## Phasing (the milestone decomposition — each a follow-on build SDD)

| Phase | Scope | Depends on |
|---|---|---|
| **A** | Elevation-token substrate + `auth:` tiering in control-systems.yaml + web-daemon gate + **TOTP** verifier (greenfield, stdlib) + enrollment | — |
| **B** | **notifykit OTP** factor (email/SMS/push) + **MS003 signed-challenge** factor (generalize the presence check) | A; notifykit go-live for the OTP leg |
| **C** | **osctl-level enforcement** (T2 coverage) — the sudo-invoked step-up gate wrapper + sudoers allowlist line | A |
| **D** | **Cockpit UX** — step-up modal in control-surface.js + devsecops enrollment panel | A/B |
| **E** | **WebAuthn/FIDO** passkey factor (phase 2) | D |

## Open decisions — need the operator's sign-off before Phase A build

| Q | Decision | Proposed |
|---|---|---|
| Q-508-A | Factor set for phase 1 | TOTP + notifykit OTP + MS003 signed challenge (WebAuthn phase 2) — *the operator confirmed "all I said," best solution* |
| Q-508-B | Enforcement locus | **Both lines** — web daemon + osctl-level (defeats T2), per L4 |
| Q-508-C | Elevation window | Proposed: **5 min** windowed for `step-up`; **single-use per op** for `step-up-strong` |
| Q-508-D | TOTP secret at rest | vault vs TPM-sealed — needs the operator's storage call |
| Q-508-E | Tier→control mapping | Which controls are `step-up` vs `step-up-strong` (draft table above; operator curates) |
| Q-508-F | One milestone vs a formal `backlog/milestones/` entry | Propose a milestone once the design is signed |

## References

- Chokepoint: `scripts/operator/_action_exec.py:387-399` (the `if privileged:` block); `scripts/operator/control-exec-api.py` (`/api/control/execute`).
- Reuse: `scripts/lib/ms003.py` (ed25519 sign/verify + trust anchors), `tools/notifykit/channels.py` (email/SMS/push), `config/control-systems.yaml` (`privileged` classifier), `SELFDEF_OWNED` (`_action_exec.py:53`).
- Boundaries that are NOT boundaries: `scripts/operator/lib/permission_classifier.py:18-33`.
- Adjacent: `scripts/operator/auth-tier.py` (surface tiers; defers MFA to IdP), `scripts/lifecycle/approval-queue.py` (E0634 gate sign-off — the PR-time approval precedent).
- Standard: RFC 6238 (TOTP), RFC 4226 (HOTP), WebAuthn L2 (phase 2).
