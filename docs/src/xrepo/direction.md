# Direction of dependency

Per SDD-001. Four repos, strict one-way flows:

```
sovereign-os  ──CONSUMES FROM──▶  info-hub  (architectural baseline)
selfdef       ──CONSUMES FROM──▶  info-hub + sovereign-os
info-hub      ──OBSERVES──────▶  sovereign-os + selfdef
root-ghostproxy  (dormant)
```

**Reverse flows are forbidden by default.** Exceptions go through info-hub's L0 directive log + a dedicated boundary-violation note.

## Per-repo authoritative surface

| Repo | Authoritative for | Non-authoritative |
|---|---|---|
| `cyberpunk042/sovereign-os` | OS-image generation; profile schema; whitelabel mechanism; TDD harness; lifecycle CLI; inference stack scripts | Architectural design (info-hub) · runtime security policy (selfdef) |
| `cyberpunk042/devops-solutions-information-hub` | Architectural design (L0/L1/L2/L3); SAIN-01 milestone + 11 epics; operator-directive verbatim; comparison matrices | Implementation artifacts |
| `cyberpunk042/selfdef` | Security daemon + agent-guard + 12 notifier channels + escalation engine; security threat model | OS construction; profile schema |
| `cyberpunk042/root-ghostproxy` | (dormant) | — |
