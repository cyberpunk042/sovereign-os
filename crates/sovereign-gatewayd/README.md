# sovereign-gatewayd

The first persistent runnable **service** in sovereign-os: it promotes the
one-shot `sovereign-cortex` engine into a long-lived daemon behind the M048
Module 4 gateway contract.

> Doctrine (from `sovereign-gateway`):
> *"Instead of tools owning provider keys: client → Sovereign Gateway → local/cloud/model router"*

## Why a daemon and not a CLI

- **Stateful memory that learns across requests.** One process-wide `Cortex`;
  every committed decision is admitted back into Memory-OS (M016 — learning
  without retraining), so recall grows and later requests on the same topic are
  judged more confidently. A fresh CLI invocation starts cold every time.
- **Long-running hygiene.** Stale memory is aged out (M028 decay).
- **A process-lifetime cost/route ledger** and the **never-cloud-spill** safety
  invariant tracked as a process-level tripwire.

## Running it

```sh
sovereign-gatewayd                 # NDJSON over TCP (default 127.0.0.1:8787)
sovereign-gatewayd --addr 0.0.0.0:9000
sovereign-gatewayd --http          # HTTP/1.1 over the same address
sovereign-gatewayd --stdio         # NDJSON on stdin/stdout (MCP / claude-code shape)
sovereign-gatewayd --selftest      # run the built-in demo session, print, exit
```

`SOVEREIGN_GATEWAY_ADDR` overrides the bind address. The daemon is **local-first
by default** (`force_local`): every request is forced `allow_cloud = false`
before it reaches the router, so a client can never push work off-node.

## Wire protocols

Both transports route through the same `GatewayServer::handle`, so they can
never diverge.

### NDJSON line protocol (TCP / stdio)

One JSON object per line in, one per line out:

```text
{"op":"infer","request":{ …cortex request… }}  -> {"kind":"decision", …}
{"op":"manifest"}                               -> {"kind":"manifest", …}
{"op":"health"}                                 -> {"kind":"health", …}
{"op":"ledger"}                                 -> {"kind":"ledger", …}
```

### HTTP (`--http`)

| Method · Path | Returns |
|---|---|
| `GET /health` | liveness + the never-cloud-spill invariant |
| `GET /manifest` | the 6-surface gateway contract |
| `GET /admin/ledger` | the cost/route ledger (surface 6) |
| `GET /metrics` | Prometheus text-exposition (see below) |
| `POST /v1/messages` | Anthropic-path bind (surface 1) → decision |
| `POST /v1/infer` | raw engine alias → decision |
| `POST /mcp` | MCP-bridge bind (surface 3) → decision |

A `POST` body is one JSON `CortexRequest`; the reply is the tagged
`GatewayResponse`. Wrong verb on a known route → `405`; unknown → `404`;
malformed body → `400`; engine refusal → `422`.

```sh
curl -s localhost:8787/health
curl -s -X POST --data-binary @request.json localhost:8787/v1/messages
```

> The full Anthropic Messages **content-block** schema (message arrays,
> streaming SSE) is a deliberate later layer. This v1 carries the typed
> `CortexRequest`/`CortexDecision` over HTTP.

## Metrics

`GET /metrics` renders the live ledger + health as Prometheus text-exposition
so the existing node_exporter → Grafana cockpit can chart the daemon with no
new pipeline:

| Metric | Type | Meaning |
|---|---|---|
| `sovereign_gateway_requests_total` | counter | inference requests handled |
| `sovereign_gateway_decisions_total{disposition}` | counter | `committed` / `refused` / `learned` |
| `sovereign_gateway_route_total{role}` | counter | decisions per SRP role |
| `sovereign_gateway_cloud_spills_total` | counter | spills to the cloud plane (must stay 0) |
| `sovereign_gateway_never_cloud_spill_holds` | gauge | `1` while the invariant holds |
| `sovereign_gateway_live_surfaces` | gauge | gateway surfaces currently Live |
| `sovereign_gateway_prediction_total` | counter | decisions carrying a World-Model prior (M030) |
| `sovereign_gateway_prediction_agreements_total` | counter | priors that agreed with the live verdict |

The `prediction_agreements / prediction` ratio is how well the engine is
learning its own routing-outcome dynamics over the process lifetime.

## Deployment

```sh
make bins              # build + install sovereign-gatewayd to PREFIX/bin
systemctl enable --now sovereign-gatewayd.service
```

`systemd/system/sovereign-gatewayd.service` runs `--http`, loopback-by-default,
`Restart=on-failure`, under the full R171 defense-in-depth posture. To expose
beyond loopback, drop an override:

```ini
# /etc/systemd/system/sovereign-gatewayd.service.d/bind.conf
[Service]
Environment=SOVEREIGN_GATEWAY_ADDR=0.0.0.0:8787
```

## Tests

- Unit tests cover the pure serving core (`handle_line`, `http::respond`).
- `tests/transports.rs` spins the real binary on an ephemeral port and exercises
  both transports over actual sockets.

```sh
cargo test -p sovereign-gatewayd
```
