# Infrastructure tier (PRs 9–10)

TDD harness + scaffold + first passing tests.

- **PR 9** — SDD-008 5-layer test harness specification
- **PR 10** — Harness bootstrap: Layer 1 schema + lint tests + CI workflow

Substantive Stage-2 content already landed on main: 9-step build pipeline + 19 hook scripts + render engine + sovereign-osctl + inference stack + selfdef integration design.

## 5-layer pyramid

| Layer | Stack | CI | Time |
|---|---|---|---|
| **1 — Schema/lint** | jsonschema + pytest | every PR (blocking) | <30s |
| **2 — Unit** | pytest + mocks | every PR (blocking) | <2 min |
| **3 — Stage acceptance** | chroot + nspawn | label / main | 2–10 min |
| **4 — Integration** | QEMU + OVMF | main + nightly | 10–30 min |
| **5 — Hardware** | bare-metal SAIN-01 | operator | hours |

Current status:
- **73 tests passing** (Layer 1 schema 16 + Layer 1 lint 6 + Layer 2 router 19 + Layer 2 render 14 + Layer 2 merger 18).
- Layer 3+ scaffolds present; substantive bodies land alongside their script counterparts.
