# First-run pending tasks — operator checklist

> The operator-side actions pending from the 2026-07-19 work arc
> (oracle-alternatives evaluation → compat module → notifykit + wikiops
> → overlay panel → methodology respect → compat integration). Every
> repo-side item from that arc is merged; **each item below needs the
> operator or the physical SAIN-01 box** — an agent session cannot do
> them. Check items off (or delete their section) as they land; this
> page is a living checklist, not doctrine.
>
> Pair with [Post-install (first boot + assistant)](./post-install.md)
> (the generic first-boot flow) — this page is the delta specific to
> the newly-landed surfaces.

## A · Notifications go-live (notifykit)

The library, gates, CLI, overlay panel, and R228 bridge are merged and
tested against mock/file channels. Real delivery needs real credentials
on the box.

1. **Base config** — copy and adapt (channels ship disabled except
   `file`):

   ```
   sudo install -m 0644 config/notifykit.toml.example /etc/sovereign-os/notifykit.toml
   ```

2. **Secrets env file** — values NEVER go in the TOML (it carries
   `env:VAR` names only; see
   [Operator env files & secrets](../operator-env-files.md)):

   ```
   sudo install -m 0600 -o root -g root config/notify.env.example /etc/sovereign-os/notify.env
   sudoedit /etc/sovereign-os/notify.env    # fill RESEND_API_KEY, TWILIO_*, ntfy topic/token
   ```

   The systemd units already load it via `EnvironmentFile=-`.

3. **Enable channels + verify the verbatim gates** — SMS requires
   high priority + high urgency by default; with no SMS at all, Resend
   starts at urgent + high priority:

   ```
   sovereign-osctl notifykit set ntfy enabled on
   sovereign-osctl notifykit show
   set -a; . /etc/sovereign-os/notify.env; set +a
   sovereign-osctl notifykit test --priority high --urgency high
   ```

4. **R228 bridge live check** — health events flow through the gated
   channels once the config exists:

   ```
   scripts/notify/dispatch.py test --channel notifykit --severity attention
   ```

5. **Overlay live check** — with `sovereign-control-exec-api` running,
   open the header ⚙ → 🔔 Notifications: every row should render a
   muted `live: …` line and the selects should prefill from the box's
   actual state (blank selects = the exec API is not up).

## B · Exec rail live flip (R10274)

Everything the cockpit "executes" is a DRY-RUN until the operator opts
in. Two gates, in order:

1. **Sudoers review** — `config/sudoers.d/sovereign-os-cockpit` is
   DRAFT/preview. Per its header, fold it as a second `Cmnd_Alias`
   bucket into the canonical generator
   (`scripts/operator/operator-sudoers.sh` on `main`), then install +
   validate:

   ```
   visudo -cf config/sudoers.d/sovereign-os-cockpit
   ```

   Note: `privileged: false` controls (oracle-hybrid bench,
   dflash wrapper) are deliberately ABSENT — they run as the operator
   user and must never gain NOPASSWD root (guarded both ways by
   `tests/lint/test_cockpit_action_exec_sudoers.py`).

2. **The live flag** — only after the sudoers review:

   ```
   # on the control-exec-api unit / environment
   SOVEREIGN_OS_ACTION_EXEC_LIVE=1
   ```

   Until then every panel Apply returns `dry-run ✓ would run: …`,
   which is safe to exercise freely.

## C · Big-MoE oracle-alternative benches (SAIN-01 hardware required)

The trial pipeline is merged end-to-end; the numbers need the real
box (RTX PRO 6000 96 GB + RTX 5090 32 GB + 256 GB DDR5).

1. **Pull a candidate** (bench-gate bypass — candidates stay
   non-default until promoted):

   ```
   scripts/models/pull.sh GLM-4.7 --allow-candidate
   ```

2. **Stop the pure-VRAM tiers first** — the hybrid claims BOTH internal
   GPUs (compat rule C006 will warn you exactly here):

   ```
   sovereign-osctl inference stop oracle
   sovereign-osctl inference stop logic
   scripts/inference/start-oracle-hybrid.sh          # port 8086, bench endpoint
   ```

3. **Throughput promotion gate** (the operator-decision input — NOT an
   auto-promotion):

   ```
   sovereign-osctl models eval run GLM-4.7 --benchmark throughput \
       --endpoint http://127.0.0.1:8086/v1 --min-tok-s 10
   ```

4. **MiniMax-M3 watch** — the IQ3 quant (~159 GB) is the second
   candidate; re-run the same pipeline when its GGUF is confirmed.

## D · Compat-gate calibration

The pre-change gate ships ON with the merged severities: C001 `force`,
C002–C007 `warn`/`suggest`. Per the registry's own rule, growing or
hardening rules is per-rule operator review:

```
sovereign-osctl compat list
sovereign-osctl compat explain C006-oracle-hybrid-conflicts-vram-tiers
sovereign-osctl compat check --current --set oracle-hybrid=start
```

- Promote C006/C007 to `force` only after living with the warnings.
- Escape hatch if the gate ever misfires: `SOVEREIGN_OS_COMPAT_GATE=off`
  (and report the misfire — the gate degrading open is by design).

## E · DRAFT brain promotion

[AGENTS.md](https://github.com/cyberpunk042/sovereign-os/blob/main/AGENTS.md)
and
[CLAUDE.md](https://github.com/cyberpunk042/sovereign-os/blob/main/CLAUDE.md)
are **DRAFT v1, agent-authored 2026-07-19** routers over existing canon.
Operator revises/promotes (or strikes) — until then agents treat them as
binding but provisional.

## F · Wikiops target registry

`tools/wikiops.py` reads `config/wikis.toml` (default target:
the info-hub). Copy + adapt the example if the info-hub lives at a
non-default path on this box, and pick the `gate_policy`
(`warn` | `block` | `off`) per wiki:

```
cp config/wikis.toml.example config/wikis.toml
tools/wikiops.py targets
```

## G · Pending operator decision — notifykit extraction

The shared notification library (`tools/notifykit/`) is a candidate for
extraction into its own repo so sister projects (selfdef, the info-hub,
continuity-orchestrator) can consume it without vendoring sovereign-os.
**Blocked on the operator**: create the target repository (e.g.
`cyberpunk042/notifykit`), grant the working session access to it, and
direct the extraction — sovereign-os keeps a consumption shim either
way.
