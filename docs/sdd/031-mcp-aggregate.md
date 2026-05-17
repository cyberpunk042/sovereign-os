# SDD-031 — Cross-repo MCP-tool aggregator (R286 / E7.M5)

> Status: **review**
> Owner: sovereign-os core
> Last updated: 2026-05-17
> Closes findings: E7.M5 (mandate), Q-019 (SDD-002 §Q-D)
> Derived from: §1b of operator mandate ("Cross-repo MCP-tool
> aggregator (sovereign-os surfaces selfdef tools too)"), §SDD-002
> §4 (MCP config template — sovereign-os entry was deferred to Q-019)

## Mission

The operator-mandate explicitly calls for a *unified interface*:
"Everything via dashboard/UInterface or terminal tools OR AI."
Today the operator has three disjoint surfaces — `sovereign-osctl
<verb>` for OS-level tools, `selfdefctl <verb>` for selfdef catalog,
and the SD-R94 selfdef MCP TCP transport for agent integration. An
AI agent (Claude Code, custom CoT, the operator's REPL) that wants
to drive the whole stack must hand-roll the bridge.

R286 closes that gap with a **manifest-first** aggregator:
`sovereign-osctl mcp-aggregate manifest --json` emits one document
describing every MCP-callable tool across both repos, plus optional
upstream selfdef MCP TCP endpoints. The manifest IS the deliverable
— consuming clients (Claude Code's MCP integration, the dashboard,
the SD-R98 `@selfdef_macro` registry, future cross-repo CoT routines)
wire themselves from this single document.

This stays out of the "proxy bytes between TCP MCP transports"
business deliberately — that's a separate SDD when operator
authorizes Stage-3+ wiring. The manifest is enough to let a client
talk to both endpoints natively.

## Surface

### `sovereign-osctl mcp-aggregate manifest [--upstream-selfdef HOST:PORT] [--config PATH] [--json|--human]`

Emits the unified MCP-tool manifest:

```json
{
  "schema_version": "1.0.0",
  "round": "R286",
  "sdd_vector": "E7.M5 / closes Q-019 referenced in SDD-002",
  "sources": [
    { "namespace": "sovereign-os", "transport": "exec", "tool_count": 31 },
    { "namespace": "selfdef", "transport": "tcp", "host": "...",
      "port": 4321, "protocol": "selfdef-mcp/SD-R94" }
  ],
  "tools": [
    { "name": "hardware", "namespace": "sovereign-os",
      "summary": "Host hardware probe (CPU + memory + GPU + storage).",
      "transport": "exec",
      "argv": ["sovereign-osctl", "hardware", "--json"],
      "categories": ["hardware", "cpu", "gpu", "memory"] },
    ...
  ],
  "tool_count": 31,
  "upstream_selfdef": { "host": "...", "port": 4321, ... },
  "overlay": { "_source": "...", "_overlay_keys": [...] }
}
```

`--human` switches to operator-readable form (1-line-per-tool grid).

### `sovereign-osctl mcp-aggregate probe-upstream HOST:PORT [--json] [--timeout SECS]`

TCP-connect probe — reports `reachable=true/false`, the host+port, and
any connection error. Exit code 0 when reachable, 1 otherwise. Used
by clients to verify the upstream selfdef MCP endpoint is alive
before they emit a `--upstream-selfdef` manifest reference.

## Tool selection — read-only by default

The default manifest exposes ONLY read-only sovereign-os verbs.
Mutating verbs (`*-apply`, `*-set`, `power-shutdown`, etc.) are
deliberately excluded: lifecycle-management surfaces require their
own triple-gate UX (`SOVEREIGN_OS_CONFIRM_DESTROY=YES`) that a vanilla
MCP tool call can't model safely without per-tool consent flow.
Future round (E7.M5 follow-on) can opt-in mutating tools behind an
explicit `--include-mutating` flag with `SELFDEF_MCP_ALLOW_WRITES=YES`-
analog gate semantics (per SD-R96).

The default 31 tools cover EVERY operator-named axis from the §1b
"all the angles" mandate:

- **Hardware / CPU / GPU / PSU / Memory** : `hardware`, `gpu-watch`,
  `gpu-card-advisor`, `cpu-mode`, `memory-profile`, `memory-pressure`,
  `ram-advisor`, `bios-info`, `power-status`, `wasm-aot`,
  `zmm-ternary`
- **Network / DNS / Reverse-proxy / Perimeter** : `network`, `net-perf`,
  `dns-advisor`, `reverse-proxy`, `perimeter`
- **Modules / install layer** : `install-paths`, `services-advisor`
- **Health / observability** : `health`, `severity`, `insights`, `fs`,
  `raid`, `service-deps`, `services`, `events`
- **Kernel / virt / pcie** : `kernel`, `virt-info`, `pcie-policy`
- **Dashboard / notify** : `dashboard-grid`, `notify-list`

The L3 test `tests/nspawn/test_mcp_aggregate.sh` enforces this
cross-axis coverage by category-set comparison. A future axis the
operator names becomes a new row in `LOCAL_TOOLS` and a new entry in
the `must_have` set in the test — the test FAILS until the axis lands.

## Operator overlay (R283 / SDD-030 adoption)

`/etc/sovereign-os/mcp-aggregate.toml` (or
`SOVEREIGN_OS_OVERLAY_MCP_AGGREGATE` env, or `--config <path>`):

```toml
exclude_tools = ["notify-list"]

[[extra_tools]]
name      = "my-bespoke-probe"
summary   = "Operator's own MCP tool, surfaced via overlay."
argv      = ["my-script", "--json"]
categories = ["operator-custom"]
```

`extra_tools` are appended after the built-ins; `exclude_tools`
removes built-ins by name. The overlay metadata (`_source`,
`_overlay_keys`, optional `_parse_error`) is surfaced in the
manifest under the `overlay` key so agents see which knobs are
active.

## Upstream selfdef proxy

`--upstream-selfdef host:port` registers a `selfdef` namespace in
the manifest's `sources[]` with `transport=tcp` +
`protocol=selfdef-mcp/SD-R94`. Tools in that namespace are NOT
inlined into the `tools[]` list (the selfdef MCP server enumerates
its own tools via `mcp_tools()` over the wire) — the manifest just
tells the client *where* to look. A consuming MCP client connects
to the host:port directly with the SD-R94 transport.

`SELFDEF_MCP_ALLOW_WRITES=YES` (SD-R96) gating remains on the
selfdef side; the aggregator does NOT relax it.

## What this SDD does NOT cover

- **Byte-proxy** between the aggregator and selfdef's TCP MCP
  endpoint. Future round if the operator wants a single front-door
  TCP listener. Today the client opens both endpoints.
- **Mutating-tool inclusion** — defer to a follow-on round with
  triple-gate UX (`SOVEREIGN_OS_CONFIRM_DESTROY=YES` analog).
- **TLS / mTLS** on the upstream-selfdef TCP transport — currently
  loopback or operator-managed VPN. Future-round SDD when the
  operator wants WAN-facing aggregation.
- **Schema versioning beyond 1.0.0** — when the schema changes
  incompatibly, bump the major version + ship a migration note
  in the next quarterly review.

## L3 test surface

`tests/nspawn/test_mcp_aggregate.sh` — 9 assertions:

1. Manifest envelope schema (round/schema_version/sources/tools).
2. Cross-axis coverage (every §1b-named axis has ≥1 MCP tool;
   future-axis forcing function).
3. All 24 named anchor tools present (rename-breaks-test guard).
4. `--upstream-selfdef` adds a `selfdef` namespace to `sources[]`.
5. `--upstream-selfdef` rejects malformed `host:port` / invalid port.
6. `probe-upstream` against a closed port → `reachable=false`, rc=1.
7. `probe-upstream` against a live listener → `reachable=true`, rc=0.
8. Operator overlay honoured (`extra_tools` + `exclude_tools`).
9. `sovereign-osctl mcp-aggregate` dispatches to the script.

Any future tool add / remove / rename / namespace change either lands
green or fails the test by name — no silent drift.

## Future-round candidates

- `--include-mutating` opt-in with the triple-gate UX.
- Byte-proxy TCP MCP front-door (single endpoint, both namespaces).
- mTLS on the upstream selfdef TCP transport.
- Cross-repo namespace expansion (devops-expert-local-ai,
  devops-solutions-information-hub) once those repos expose MCP
  surfaces.
