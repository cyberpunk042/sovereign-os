//! Pure-std HTTP/1.1 surface for the gateway daemon.
//!
//! This maps the [`crate::GatewayServer`] onto the bind paths the M048
//! [`sovereign_gateway`] manifest advertises, so a plain HTTP client (curl, an
//! MCP bridge, the cockpit) can reach the engine — not just the custom NDJSON
//! line protocol. Both transports route through [`GatewayServer::handle`], so
//! the HTTP surface and the line protocol can never diverge.
//!
//! Routes (v1):
//!
//! ```text
//! GET  /health         -> {"kind":"health", …}     liveness + never-cloud-spill
//! GET  /manifest       -> {"kind":"manifest", …}   the 6-surface contract
//! GET  /admin/ledger   -> {"kind":"ledger", …}     cost/route ledger (surface 6)
//! GET  /metrics        -> Prometheus text          ledger + health for the cockpit
//! POST /v1/messages    -> {"type":"message", …}    Anthropic Messages API (surface 1); stream:true = SSE
//! GET  /v1/models      -> {"data":[…],"architecture":…} Anthropic models list + primary-model arch (MoE shape)
//! POST /v1/messages/count_tokens -> {"input_tokens":N}  Anthropic token count (best-effort)
//! POST /v1/infer       -> {"kind":"decision", …}   raw engine alias (the routing DECISION)
//! POST /mcp            -> {"kind":"decision", …}   MCP-bridge bind (surface 3)
//! POST /v1/simple      -> {"kind":"decision", …}     simplified request (axes + quality)
//! POST /v1/explain     -> {"kind":"explanation",…} dry-run rationale (read-only)
//! POST /v1/deliberate  -> {"kind":"deliberation",…} best-of-N (read-only)
//! POST /v1/control-word/round -> {"kind":"control-word-round",…} M002 round engine (reads the live avx-mode switch)
//! GET  /v1/control-word/config -> {"kind":"control-word-config",…} live resolved avx-mode + round/control-word knobs
//! POST /v1/branch-scheduler/tick -> {"kind":"branch-scheduler-tick",…} M007 8-step branch loop (M002+M007+M008 capstone)
//! POST /v1/branch-scheduler/tick-v2 -> {"kind":"branch-scheduler-tick-v2",…} v2 tick (predictor + rule-table + recall + microcode; session_id = stateful learning)
//! POST /v1/math/dot-i8 -> {"kind":"math-dot-i8",…} M085 T1 VNNI INT8 dot (VPDPBUSD)
//! POST /v1/math/attention-fuse -> {"kind":"math-attention-fuse",…} M085 T2 VPTERNLOG attention-mask fuse
//! POST /v1/token-law/allowed-mask -> {"kind":"token-law-allowed-mask",…} M008 token-law bitset combine (F00623)
//! POST /v1/microcode/decode -> {"kind":"microcode-decode",…} M008 control word as executable micro-op program (M00113)
//! ```
//!
//! A `POST` body is one JSON [`CortexRequest`]; the reply is the tagged
//! [`crate::GatewayResponse`] the rest of the daemon speaks. The full Anthropic
//! Messages content-block schema is a later layer — this v1 carries the typed
//! cortex request/decision over HTTP.
//!
//! The HTTP *parsing* (sockets, headers, `Content-Length`) lives in the binary;
//! this module is the pure request→response routing, unit-tested without a
//! socket.

use crate::{GatewayRequest, GatewayResponse, GatewayServer, SimpleRequest};
use sovereign_cortex::CortexRequest;
use sovereign_value_plane::{IntelligenceTier, RewardVector};

/// The `POST /v1/deliberate` body: the shared request, the candidate reward
/// vectors (the N of best-of-N), and the compute tier.
#[derive(serde::Deserialize)]
struct DeliberateBody {
    request: Box<CortexRequest>,
    candidates: Vec<RewardVector>,
    tier: IntelligenceTier,
}

/// The `POST /v1/coat` body: the problem to deliberate about, optional recall
/// sketches (topic/entity), the ladder rung (`cot`/`tot`/`dfs`/`mcts`/`cmcts`/
/// `coat`), and the caller's freshness clock (`now`/`half_life`).
#[derive(serde::Deserialize)]
struct CoatBody {
    problem: String,
    #[serde(default)]
    topic: u64,
    #[serde(default)]
    entity: u64,
    #[serde(default)]
    rung: String,
    now: Option<u64>,
    half_life: Option<u64>,
    /// Which model expands the reasoning (Phase 2 increment 3): `"background"`
    /// routes to the designated secondary (a background deliberation keeps the
    /// primary free); omitted uses the primary.
    #[serde(default)]
    model: Option<String>,
}

/// Maximum request-body size the daemon will read. A `Content-Length` larger
/// than this is refused with `413` *before* any buffer is allocated, so a
/// client cannot exhaust memory by claiming a huge body. Cortex requests are a
/// few KB; 1 MiB is generous headroom.
pub const MAX_BODY_BYTES: usize = 1 << 20;

/// A rendered HTTP reply: status code + content type + body.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct HttpReply {
    /// HTTP status code.
    pub status: u16,
    /// MIME type of the body (`application/json`, or text for `/metrics`).
    pub content_type: &'static str,
    /// Response body.
    pub body: String,
}

/// Reason phrase for the small set of status codes this surface emits.
pub fn reason(status: u16) -> &'static str {
    match status {
        200 => "OK",
        400 => "Bad Request",
        404 => "Not Found",
        401 => "Unauthorized",
        405 => "Method Not Allowed",
        413 => "Payload Too Large",
        429 => "Too Many Requests",
        422 => "Unprocessable Entity",
        431 => "Request Header Fields Too Large",
        503 => "Service Unavailable",
        _ => "Internal Server Error",
    }
}

/// The `413` reply for an over-cap `Content-Length` — emitted by the transport
/// before the body is read, so the oversized payload is never buffered.
pub fn payload_too_large() -> HttpReply {
    err(
        413,
        format!("request body exceeds the {MAX_BODY_BYTES}-byte limit"),
    )
}

/// The `431` reply for an over-long request line / header, or too many headers —
/// emitted by the transport so an unterminated header can't be buffered forever.
pub fn headers_too_large() -> HttpReply {
    err(431, "request line or headers too large".to_string())
}

/// Route one parsed HTTP request (method + path + body) to a reply. Pure: no
/// I/O, no panics — every path returns a JSON body, so a client always gets a
/// structured answer.
pub fn respond(server: &GatewayServer, method: &str, path: &str, body: &str) -> HttpReply {
    // Drop any query string / trailing slash so `/health?x=1` and `/health/`
    // route like `/health`.
    let route = path.split('?').next().unwrap_or(path);
    let route = route.strip_suffix('/').unwrap_or(route);
    let route = if route.is_empty() { "/" } else { route };

    match (method, route) {
        ("GET", "/health") => ok(server.handle(GatewayRequest::Health)),
        ("GET", "/manifest") => ok(server.handle(GatewayRequest::Manifest)),
        ("GET", "/admin/ledger") => ok(server.handle(GatewayRequest::Ledger)),
        ("GET", "/metrics") => HttpReply {
            status: 200,
            content_type: "text/plain; version=0.0.4; charset=utf-8",
            body: server.metrics_prometheus(),
        },

        // The Anthropic Messages API over the locally-loaded model — VS Code
        // (Cline / Claude Dev), Claude Code (ANTHROPIC_BASE_URL), and anything
        // else that speaks Anthropic point here. Non-streaming; `stream:true` is
        // served as SSE in main.rs. The sovereign routing DECISION is /v1/infer.
        ("POST", "/v1/messages") => anthropic_message(server, body),
        ("GET", "/v1/models") => anthropic_models(server),
        ("GET", "/v1/events") => events(server),
        ("POST", "/v1/control-word/round") => control_word_round(body),
        ("GET", "/v1/control-word/config") => control_word_config(),
        ("POST", "/v1/branch-scheduler/tick") => branch_scheduler_tick(body),
        ("POST", "/v1/branch-scheduler/tick-v2") => branch_scheduler_tick_v2(body),
        ("POST", "/v1/token-law/allowed-mask") => token_law_allowed_mask(body),
        ("POST", "/v1/data-plane/token-law/fuse") => token_law_fuse(server, body),
        ("POST", "/v1/math/dot-i8") => math_dot_i8(body),
        ("POST", "/v1/math/attention-fuse") => math_attention_fuse(body),
        ("POST", "/v1/microcode/decode") => microcode_decode(body),
        ("POST", "/v1/models/load") => models_load(server, body),
        ("POST", "/v1/models/unload") => models_unload(server, body),
        ("POST", "/v1/models/register") => models_register(server, body),
        ("POST", "/v1/models/background") => models_background(server, body),
        ("POST", "/v1/corpus/reload") => corpus_reload(server),
        ("POST", "/v1/cache/clear") => cache_clear(server),
        ("POST", "/v1/messages/count_tokens") => anthropic_count_tokens(body),

        ("POST", "/v1/infer") | ("POST", "/mcp") | ("POST", "/v1/explain") => {
            match serde_json::from_str::<CortexRequest>(body) {
                Ok(request) => {
                    // `/v1/explain` is the read-only dry-run; the rest run the
                    // engine. Both share the request shape.
                    let gw_req = if route == "/v1/explain" {
                        GatewayRequest::Explain {
                            request: Box::new(request),
                        }
                    } else {
                        GatewayRequest::Infer {
                            request: Box::new(request),
                        }
                    };
                    let resp = server.handle(gw_req);
                    // An engine refusal is a request-level problem (422); a
                    // genuine decision/explanation is 200.
                    let status = match resp {
                        GatewayResponse::Error { .. } => 422,
                        _ => 200,
                    };
                    render(status, &resp)
                }
                Err(e) => err(400, format!("invalid request body: {e}")),
            }
        }

        ("POST", "/v1/simple") => match serde_json::from_str::<SimpleRequest>(body) {
            Ok(request) => {
                let resp = server.handle(GatewayRequest::SimpleInfer { request });
                let status = match resp {
                    GatewayResponse::Error { .. } => 422,
                    _ => 200,
                };
                render(status, &resp)
            }
            Err(e) => err(400, format!("invalid simple request body: {e}")),
        },

        // Read-only sibling of /v1/simple: decide + return the full decision, but
        // DO NOT learn (the observatory routing probe — no memory pollution).
        ("POST", "/v1/simple-explain") => match serde_json::from_str::<SimpleRequest>(body) {
            Ok(request) => {
                let resp = server.handle(GatewayRequest::SimpleExplain { request });
                let status = match resp {
                    GatewayResponse::Error { .. } => 422,
                    _ => 200,
                };
                render(status, &resp)
            }
            Err(e) => err(400, format!("invalid simple request body: {e}")),
        },

        ("POST", "/v1/deliberate") => match serde_json::from_str::<DeliberateBody>(body) {
            Ok(b) => {
                let resp = server.handle(GatewayRequest::Deliberate {
                    request: b.request,
                    candidates: b.candidates,
                    tier: b.tier,
                });
                let status = match resp {
                    GatewayResponse::Error { .. } => 422,
                    _ => 200,
                };
                render(status, &resp)
            }
            Err(e) => err(400, format!("invalid deliberate body: {e}")),
        },

        ("POST", "/v1/coat") => match serde_json::from_str::<CoatBody>(body) {
            Ok(b) => {
                let resp = server.handle(GatewayRequest::Coat {
                    problem: b.problem,
                    topic: b.topic,
                    entity: b.entity,
                    rung: b.rung,
                    now: b.now.unwrap_or(100),
                    half_life: b.half_life.unwrap_or(1000),
                    model: b.model,
                });
                let status = match resp {
                    GatewayResponse::Error { .. } => 422,
                    _ => 200,
                };
                render(status, &resp)
            }
            Err(e) => err(400, format!("invalid coat body: {e}")),
        },

        // A known resource with the wrong verb is 405; anything else is 404.
        (_, "/health") | (_, "/manifest") | (_, "/admin/ledger") | (_, "/metrics") => {
            err(405, format!("method {method} not allowed on {route}"))
        }
        (_, "/v1/messages")
        | (_, "/v1/messages/count_tokens")
        | (_, "/v1/models")
        | (_, "/v1/models/load")
        | (_, "/v1/models/unload")
        | (_, "/v1/models/register")
        | (_, "/v1/models/background")
        | (_, "/v1/corpus/reload")
        | (_, "/v1/cache/clear")
        | (_, "/v1/infer")
        | (_, "/mcp")
        | (_, "/v1/explain")
        | (_, "/v1/deliberate")
        | (_, "/v1/coat")
        | (_, "/v1/simple")
        | (_, "/v1/simple-explain") => err(405, format!("method {method} not allowed on {route}")),
        _ => err(404, format!("no route for {method} {route}")),
    }
}

/// Render a successful tagged response at 200.
fn ok(resp: GatewayResponse) -> HttpReply {
    render(200, &resp)
}

/// Serialize a tagged response at an explicit status.
fn render(status: u16, resp: &GatewayResponse) -> HttpReply {
    let body = serde_json::to_string(resp).unwrap_or_else(|e| {
        format!("{{\"kind\":\"error\",\"message\":\"response serialize failed: {e}\"}}")
    });
    HttpReply {
        status,
        content_type: "application/json",
        body,
    }
}

/// Build an error reply with a JSON body matching the daemon's error shape.
pub fn err(status: u16, message: String) -> HttpReply {
    render(status, &GatewayResponse::Error { message })
}

// ── the Anthropic Messages API (surface 1) ──────────────────────────────────

/// Render an arbitrary JSON value at a status (not the tagged GatewayResponse).
fn json_reply(status: u16, v: &serde_json::Value) -> HttpReply {
    HttpReply {
        status,
        content_type: "application/json",
        body: v.to_string(),
    }
}

/// The Anthropic error envelope: `{"type":"error","error":{"type","message"}}`.
pub fn anthropic_err(status: u16, kind: &str, message: String) -> HttpReply {
    json_reply(
        status,
        &serde_json::json!({
            "type": "error", "error": { "type": kind, "message": message }
        }),
    )
}

/// A rough token count (~4 chars/token). Usage is best-effort on a base model
/// (the generator does not surface the exact prompt-token count).
pub fn approx_tokens(s: &str) -> u64 {
    ((s.chars().count() as u64) / 4).max(1)
}

/// The text of an Anthropic content value: a plain string, or the concatenation
/// of the `text` blocks in a content-block array (non-text blocks are skipped —
/// the base model is text-only).
fn block_text(v: &serde_json::Value) -> String {
    if let Some(s) = v.as_str() {
        return s.to_string();
    }
    if let Some(arr) = v.as_array() {
        let mut out = String::new();
        for b in arr {
            if b.get("type").and_then(|t| t.as_str()) == Some("text")
                && let Some(t) = b.get("text").and_then(|t| t.as_str())
            {
                if !out.is_empty() {
                    out.push('\n');
                }
                out.push_str(t);
            }
        }
        return out;
    }
    String::new()
}

/// Flatten an Anthropic Messages request (optional `system` + `messages`, each
/// content a string OR an array of `{type:"text",text}` blocks) into one chat
/// prompt for the base model — Claude-style role tags, ending with `Assistant:`
/// so a base completion model continues as the assistant.
pub fn anthropic_prompt(req: &serde_json::Value) -> String {
    let mut parts: Vec<String> = Vec::new();
    if let Some(sys) = req.get("system") {
        let s = block_text(sys);
        if !s.trim().is_empty() {
            parts.push(format!("System: {s}"));
        }
    }
    if let Some(msgs) = req.get("messages").and_then(|m| m.as_array()) {
        for m in msgs {
            let role = m.get("role").and_then(|r| r.as_str()).unwrap_or("user");
            let text = m.get("content").map(block_text).unwrap_or_default();
            if text.trim().is_empty() {
                continue;
            }
            let tag = if role == "assistant" {
                "Assistant"
            } else {
                "Human"
            };
            parts.push(format!("{tag}: {text}"));
        }
    }
    parts.push("Assistant:".to_string());
    parts.join("\n\n")
}

/// The `max_tokens` a Messages request asks for, clamped. Anthropic requires it;
/// default generously if a client omits it.
pub fn anthropic_max_tokens(req: &serde_json::Value) -> usize {
    req.get("max_tokens")
        .and_then(serde_json::Value::as_u64)
        .unwrap_or(256)
        .clamp(1, 4096) as usize
}

/// `GET /v1/models` — the Anthropic models-list shape, listing the LOADED local
/// models (the primary + any secondaries loaded via `/v1/models/load`). Tools
/// (VS Code) query this to populate a model picker.
fn anthropic_models(server: &GatewayServer) -> HttpReply {
    let loaded = server.list_models();
    let data: Vec<serde_json::Value> = if loaded.is_empty() {
        // no model loaded: still answer with the sovereign placeholder id so a
        // client's picker isn't empty (a generate then returns an honest 503).
        vec![serde_json::json!({
            "type": "model", "id": "sovereign-local",
            "display_name": "Sovereign Local (no model loaded)",
            "created_at": "2026-01-01T00:00:00Z",
        })]
    } else {
        loaded
            .iter()
            .map(|(id, kind, device, vram)| {
                serde_json::json!({
                    "type": "model", "id": id,
                    "display_name": format!("Sovereign {id} ({kind})"),
                    "device": device, "vram_gb": vram,
                    "created_at": "2026-01-01T00:00:00Z",
                })
            })
            .collect()
    };
    let first = data
        .first()
        .and_then(|m| m["id"].as_str())
        .unwrap_or("")
        .to_string();
    let last = data
        .last()
        .and_then(|m| m["id"].as_str())
        .unwrap_or("")
        .to_string();
    // Architecture of the primary in-process model (layers / vocab / model_dim,
    // and the MoE shape when it is a mixture of experts) so a UI can show whether
    // the loaded model is dense or an N-expert MoE. `null` when nothing is loaded.
    let architecture = server.primary_model_arch().map(|a| {
        serde_json::json!({
            "layers": a.layers,
            "vocab": a.vocab,
            "model_dim": a.model_dim,
            "mixture_of_experts": a.moe.map(|(moe_layers, num_experts, experts_per_tok)| {
                serde_json::json!({
                    "moe_layers": moe_layers,
                    "total_layers": a.layers,
                    "num_experts": num_experts,
                    "experts_per_tok": experts_per_tok,
                })
            }),
        })
    });
    json_reply(
        200,
        &serde_json::json!({
            "data": data, "has_more": false, "first_id": first, "last_id": last,
            // the model the "background" alias resolves to (null = none designated /
            // designated-but-unloaded → the primary), so a UI can show it (inc.3/UX loop)
            "background": server.background_id(),
            "architecture": architecture,
        }),
    )
}

/// `GET /v1/events` — the recent runtime observability spans (one `model_call` per
/// local generation; the `sovereign-observability-events` 13-field taxonomy), newest
/// last. Read-only; a bounded ring, so this is the last N, not a full history.
fn events(server: &GatewayServer) -> HttpReply {
    let events = server.recent_events();
    json_reply(
        200,
        &serde_json::json!({ "count": events.len(), "events": events }),
    )
}

/// `POST /v1/control-word/round` — run the M002 round engine over the daemon.
/// Body: `{ "state": RoundState, "config"?: RoundConfig, "rounds"?: u64,
/// "avx_mode"?: "custom"|"builtin"|"hybrid"|"off" }`.
///
/// The runtime switch is READ here, per request — the last hop. When the body
/// omits `avx_mode`, the daemon reads the live `avx-mode.active` state file (the
/// hot-swap: write the file, the next request sees it). The M002 bit-machine
/// only runs under `custom`/`hybrid`; the default `builtin` and `off` return an
/// honest engine-off envelope instead of a fabricated result. When the body
/// omits `config`, the round knobs come from `RoundConfig::from_env()` (the
/// `SOVEREIGN_CTRL_*` env), so the daemon's configured defaults drive the round.
fn control_word_round(body: &str) -> HttpReply {
    use sovereign_control_word_service::{
        AvxMode, avx_mode_live, diversity_index, metrics_from, round_fingerprints,
        round_with_events,
    };
    use sovereign_simd::round::{RoundConfig, RoundState};

    #[derive(serde::Deserialize)]
    struct Req {
        state: RoundState,
        config: Option<RoundConfig>,
        #[serde(default = "one_round")]
        rounds: u64,
        avx_mode: Option<String>,
    }
    fn one_round() -> u64 {
        1
    }

    let req: Req = match serde_json::from_str(body) {
        Ok(r) => r,
        Err(e) => return err(400, format!("invalid control-word round request: {e}")),
    };
    if req.rounds > 100_000 {
        return err(400, "rounds capped at 100000 per request".to_string());
    }
    // The runtime switch: an explicit body override, else the live state file.
    let avx = req
        .avx_mode
        .as_deref()
        .map(AvxMode::parse)
        .unwrap_or_else(avx_mode_live);
    // The round knobs: an explicit body config, else the env-resolved defaults.
    let config = req.config.unwrap_or_else(RoundConfig::from_env);

    // The M002 bit-machine is opt-in — only custom/hybrid run it. builtin/off
    // return an honest engine-off envelope, never a fabricated result.
    if !avx.runs_bit_machine() {
        return json_reply(
            200,
            &serde_json::json!({
                "kind": "control-word-round",
                "avx_mode": avx.as_str(),
                "engine_active": false,
                "note": format!(
                    "avx-mode is '{}' — the M002 control-word bit-machine is not the \
                     active path; set avx-mode to 'custom' or 'hybrid' to run it \
                     (avx-mode set custom)",
                    avx.as_str()
                ),
            }),
        );
    }

    // Run rounds-1 plain, then the final round with lifecycle events — timed
    // with a real clock so steps/sec (F00145) is a live measurement at this
    // daemon call site, not a fabricated 0.
    let t0 = std::time::Instant::now();
    let mut cur = req.state;
    for _ in 1..req.rounds {
        cur = sovereign_simd::round::round_update(&cur, config);
    }
    let (result, events) = if req.rounds == 0 {
        (cur, Vec::new())
    } else {
        round_with_events(&cur, config)
    };
    let elapsed = t0.elapsed().as_secs_f64();
    let fps = round_fingerprints(&result);
    let metrics = metrics_from(&result, req.rounds, elapsed, 1.0);
    json_reply(
        200,
        &serde_json::json!({
            "kind": "control-word-round",
            "avx_mode": avx.as_str(),
            "engine_active": true,
            "config": config,
            "rounds": req.rounds,
            "result": result,
            "fingerprints": fps.iter().map(|f| format!("{f:#018x}")).collect::<Vec<_>>(),
            "diversity_index": diversity_index(&fps),
            "events": events,
            "metrics": metrics,
        }),
    )
}

/// `POST /v1/branch-scheduler/tick` — run one tick of the M007 8-step branch
/// loop over an 8-branch SoA batch (the capstone tying M002 + M007 + M008). The
/// Commit gate reads each branch's M002 control-word permissions; Filter/Verify
/// short-circuit via the M008 speculative-accept cheat; survivors are packed
/// dense via VPCOMPRESS. Body: `{ "batch": BranchBatch, "verify_min_score"?: u32 }`.
fn branch_scheduler_tick(body: &str) -> HttpReply {
    use sovereign_branch_scheduler::{BranchBatch, tick};

    #[derive(serde::Deserialize)]
    struct Req {
        batch: BranchBatch,
        #[serde(default = "default_min_score")]
        verify_min_score: u32,
    }
    fn default_min_score() -> u32 {
        1
    }

    let req: Req = match serde_json::from_str(body) {
        Ok(r) => r,
        Err(e) => return err(400, format!("invalid branch-scheduler tick request: {e}")),
    };
    let result = tick(&req.batch, req.verify_min_score);
    json_reply(
        200,
        &serde_json::json!({ "kind": "branch-scheduler-tick", "result": result }),
    )
}

/// `POST /v1/branch-scheduler/tick-v2` — the richer M007 tick that consumes the
/// M008 building blocks: memory recall (bloom), the branch predictor (M00121),
/// the two-level rule table (M00119) for Verify, and microcode (M00113) for
/// Commit. Body: `{ "batch": BranchBatch, "rule_table": [[u8,…],…],
/// "event_class": [usize;8], "memory_bank": [u64,…], "verify_min_score"?: u32 }`.
/// The predictor starts fresh per request (stateless HTTP); its learn happens
/// within the tick, so `predictor_accuracy` reflects this tick's retirement.
fn branch_scheduler_tick_v2(body: &str) -> HttpReply {
    use sovereign_bit_cheats::{BranchPredictor, TwoLevelTable};
    use sovereign_branch_scheduler::{BranchBatch, SchedulerContext, tick_v2};

    #[derive(serde::Deserialize)]
    struct Req {
        batch: BranchBatch,
        #[serde(default)]
        rule_table: Vec<Vec<u8>>,
        #[serde(default)]
        event_class: [usize; 8],
        #[serde(default)]
        memory_bank: Vec<u64>,
        #[serde(default = "default_min_score_v2")]
        verify_min_score: u32,
        /// When present, the branch predictor persists under this key across
        /// requests, so M00121 prediction *learns across ticks* (stateful).
        session_id: Option<String>,
    }
    fn default_min_score_v2() -> u32 {
        1
    }

    let req: Req = match serde_json::from_str(body) {
        Ok(r) => r,
        Err(e) => {
            return err(
                400,
                format!("invalid branch-scheduler tick-v2 request: {e}"),
            );
        }
    };

    // Reject an over-long session_id up front: the key is stored process-global,
    // so an unbounded key is a memory-amplification lever (a 1 MiB key ×N ticks).
    if let Some(id) = &req.session_id {
        if id.len() > MAX_SESSION_ID_LEN {
            return err(
                400,
                format!(
                    "session_id too long ({} bytes; max {MAX_SESSION_ID_LEN})",
                    id.len()
                ),
            );
        }
    }

    // Load the session's predictor (or a fresh one) so learning continues.
    // F-2026-065: recover a poisoned lock (the guarded state is a predictor cache,
    // nothing torn worth declining an already-parsed request over).
    let predictor = match &req.session_id {
        Some(id) => scheduler_sessions()
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .get(id)
            .unwrap_or_else(|| BranchPredictor::new(8)),
        None => BranchPredictor::new(8),
    };
    let mut ctx = SchedulerContext::with_predictor(
        predictor,
        TwoLevelTable::new(req.rule_table),
        req.event_class,
        req.memory_bank,
    );
    let result = tick_v2(&req.batch, &mut ctx, req.verify_min_score);
    // Persist the learned predictor back under the session key. The store is a
    // bounded LRU (MAX_SESSIONS): unique-session_id floods can no longer grow it
    // without bound (was an unbounded HashMap → OOM lever).
    if let Some(id) = &req.session_id {
        scheduler_sessions()
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .insert(id.clone(), ctx.predictor.clone());
    }
    json_reply(
        200,
        &serde_json::json!({
            "kind": "branch-scheduler-tick-v2",
            "session_id": req.session_id,
            "result": result,
        }),
    )
}

/// Max predictor sessions retained; the store is an LRU past this. A tick-v2
/// predictor is tiny, so this bounds the store to a few MB even when full.
const MAX_SESSIONS: usize = 4096;
/// Max accepted `session_id` byte length (a stored key must not be a memory lever).
const MAX_SESSION_ID_LEN: usize = 256;

/// Bounded LRU predictor session store (M00121 cross-request learning). Keyed by
/// `session_id`; holds only the predictor (the state worth persisting). Past
/// MAX_SESSIONS the least-recently-used session is evicted — so a flood of unique
/// session_ids can no longer grow the process without bound (the prior unbounded
/// HashMap was an OOM lever on an unauthenticated endpoint).
struct SessionStore {
    map: std::collections::HashMap<String, sovereign_bit_cheats::BranchPredictor>,
    /// recency queue, front = least-recently-used, back = most-recent.
    order: std::collections::VecDeque<String>,
}

impl SessionStore {
    fn new() -> Self {
        Self {
            map: std::collections::HashMap::new(),
            order: std::collections::VecDeque::new(),
        }
    }

    fn touch(&mut self, id: &str) {
        if let Some(pos) = self.order.iter().position(|k| k == id) {
            self.order.remove(pos);
        }
        self.order.push_back(id.to_string());
    }

    /// A clone of the session's predictor, marking it most-recently-used.
    fn get(&mut self, id: &str) -> Option<sovereign_bit_cheats::BranchPredictor> {
        let p = self.map.get(id).cloned();
        if p.is_some() {
            self.touch(id);
        }
        p
    }

    /// Insert/update a session, evicting the LRU entry when over capacity.
    fn insert(&mut self, id: String, predictor: sovereign_bit_cheats::BranchPredictor) {
        if !self.map.contains_key(&id) {
            while self.map.len() >= MAX_SESSIONS {
                match self.order.pop_front() {
                    Some(lru) => {
                        self.map.remove(&lru);
                    }
                    None => break,
                }
            }
        }
        self.touch(&id);
        self.map.insert(id, predictor);
    }

    #[cfg(test)]
    fn len(&self) -> usize {
        self.map.len()
    }
}

fn scheduler_sessions() -> &'static std::sync::Mutex<SessionStore> {
    use std::sync::{Mutex, OnceLock};
    static SESSIONS: OnceLock<Mutex<SessionStore>> = OnceLock::new();
    SESSIONS.get_or_init(|| Mutex::new(SessionStore::new()))
}

/// `POST /v1/math/dot-i8` — M085 T1 VNNI INT8 dot product (`Σ a[i]·b[i]`),
/// dispatching to `_mm512_dpbusd_epi32` (VPDPBUSD) when the host has `avx512vnni`
/// else the scalar reference. Body: `{ "a": [u8,…], "b": [i8,…] }`.
fn math_dot_i8(body: &str) -> HttpReply {
    #[derive(serde::Deserialize)]
    struct Req {
        a: Vec<u8>,
        b: Vec<i8>,
    }
    let req: Req = match serde_json::from_str(body) {
        Ok(r) => r,
        Err(e) => return err(400, format!("invalid dot-i8 request: {e}")),
    };
    json_reply(
        200,
        &serde_json::json!({
            "kind": "math-dot-i8",
            "dot": sovereign_simd::lift::dot_i8(&req.a, &req.b),
            "avx512vnni": cfg!(target_arch = "x86_64")
                && std::is_x86_feature_detected!("avx512vnni"),
        }),
    )
}

/// `POST /v1/math/attention-fuse` — M085 T2 VPTERNLOG attention-mask fusion
/// (`query ∧ key ∧ causal`), a single-instruction fuse per 8 words on any
/// `avx512f` host. Body: `{ "query": [u64,…], "key": [u64,…], "causal": [u64,…] }`.
fn math_attention_fuse(body: &str) -> HttpReply {
    #[derive(serde::Deserialize)]
    struct Req {
        query: Vec<u64>,
        key: Vec<u64>,
        causal: Vec<u64>,
    }
    let req: Req = match serde_json::from_str(body) {
        Ok(r) => r,
        Err(e) => return err(400, format!("invalid attention-fuse request: {e}")),
    };
    let allow = sovereign_simd::lift::attention_mask_fuse(&req.query, &req.key, &req.causal);
    json_reply(
        200,
        &serde_json::json!({ "kind": "math-attention-fuse", "allow": allow }),
    )
}

/// `POST /v1/token-law/allowed-mask` (F00623) — combine the M008 token-law
/// planes (grammar / schema / tool / safety / route), each a vocab bitset, into
/// one allowed-token mask (M00117). Body: `{ "laws": [[u64,…],…], "combine"?:
/// "and"|"or" }`. Reply: the combined mask + allowed-token count (F00624).
fn token_law_allowed_mask(body: &str) -> HttpReply {
    use sovereign_simd::cheats::{LawCombine, allowed_token_count, token_law_combine};

    #[derive(serde::Deserialize)]
    struct Req {
        laws: Vec<Vec<u64>>,
        #[serde(default)]
        combine: String,
    }
    let req: Req = match serde_json::from_str(body) {
        Ok(r) => r,
        Err(e) => return err(400, format!("invalid token-law request: {e}")),
    };
    let combine = if req.combine == "or" {
        LawCombine::Or
    } else {
        LawCombine::And
    };
    let law_refs: Vec<&[u64]> = req.laws.iter().map(|l| l.as_slice()).collect();
    let mask = token_law_combine(&law_refs, combine);
    json_reply(
        200,
        &serde_json::json!({
            "kind": "token-law-allowed-mask",
            "combine": if req.combine == "or" { "or" } else { "and" },
            "mask": mask,
            "allowed_tokens": allowed_token_count(&mask),
        }),
    )
}

/// `POST /v1/data-plane/token-law/fuse` (M00155 F00792/F00797, SDD-507) — the
/// operator surface over the M00117 engine: fuse the NAMED laws
/// (grammar/regex/denylist/negated-regex/policy) at a generated prefix into one
/// vocab allow-mask. Unlike `/v1/token-law/allowed-mask` (which combines
/// pre-packed bitsets), this *derives* each layer's bitset from a real source,
/// so the caller sends sources, not bitsets. Checkpoint-free: the mask depends
/// only on the sources + the supplied `vocab`, never on a loaded model — the
/// deterministic-cortex DECISION exposed for inspection. Body: a
/// [`sovereign_token_law_fuse::FuseRequest`] `{ schema?, regex?, denylist?,
/// regex_denylist?, policy_planes?, generated?, vocab }`. Reply: the fused mask,
/// its allowed-token count, per-layer coverage, the active layer names, and a
/// `stop` flag (the prefix admits no continuation under these laws).
fn token_law_fuse(server: &GatewayServer, body: &str) -> HttpReply {
    let mut req: sovereign_token_law_fuse::FuseRequest = match serde_json::from_str(body) {
        Ok(r) => r,
        Err(e) => return err(400, format!("invalid token-law fuse request: {e}")),
    };
    if req.vocab.is_empty() {
        return err(400, "token-law fuse: `vocab` must be non-empty".into());
    }
    // F00793/F00794: when the request doesn't pin the mask layers itself, the
    // operator's `SOVEREIGN_TOKEN_LAW_MASK_LAYERS` selection (else all layers)
    // applies. The request always wins — an explicit `mask_layers` is honored
    // verbatim.
    if req.mask_layers.is_none() {
        let names: Vec<String> = sovereign_token_law_fuse::MaskLayerSet::from_env_or_all()
            .names()
            .iter()
            .map(|s| s.to_string())
            .collect();
        req.mask_layers = Some(names);
    }
    let layers_active = req.layers_active();
    let fused = match req.fuse() {
        Ok(f) => f,
        Err(e) => return err(400, e.to_string()),
    };
    server.record_token_law_fuse(layers_active.len());
    json_reply(
        200,
        &serde_json::json!({
            "kind": "token-law-fuse",
            "mask": fused.mask,
            "allowed_tokens": fused.allowed,
            "per_layer": fused.per_layer,
            "layers_active": layers_active,
            "stop": fused.stop,
        }),
    )
}

/// `POST /v1/microcode/decode` (M00113) — decode a control word's bitfields as
/// an executable micro-op program and run it to a policy outcome. Body:
/// `{ "control_word": u64 }`. The control word isn't data the policy reads —
/// it's a program the policy runs.
fn microcode_decode(body: &str) -> HttpReply {
    use sovereign_bit_cheats::{decode_microcode, execute_microcode};

    #[derive(serde::Deserialize)]
    struct Req {
        control_word: u64,
    }
    let req: Req = match serde_json::from_str(body) {
        Ok(r) => r,
        Err(e) => return err(400, format!("invalid microcode request: {e}")),
    };
    let ops = decode_microcode(req.control_word);
    let outcome = execute_microcode(&ops);
    json_reply(
        200,
        &serde_json::json!({
            "kind": "microcode-decode",
            "control_word": format!("{:#018x}", req.control_word),
            "program": ops,
            "outcome": outcome,
        }),
    )
}

/// `GET /v1/control-word/config` — the live resolved M002 runtime config an
/// operator can curl to confirm a hot-swap took effect: the current `avx-mode`
/// (read from the state file), whether the bit-machine is active, and the
/// env-resolved round + control-word knobs.
fn control_word_config() -> HttpReply {
    use sovereign_control_word::m00013::ControlWordConfig;
    use sovereign_control_word_service::avx_mode_live;
    use sovereign_simd::round::RoundConfig;

    let avx = avx_mode_live();
    json_reply(
        200,
        &serde_json::json!({
            "kind": "control-word-config",
            "avx_mode": avx.as_str(),
            "engine_active": avx.runs_bit_machine(),
            "round_config": RoundConfig::from_env(),
            "control_word_config": ControlWordConfig::from_env(),
        }),
    )
}

/// Reject a proxy `endpoint` that targets **link-local / cloud-metadata** space
/// (169.254.0.0/16 — incl. 169.254.169.254 — and `fe80::/10`): the classic SSRF
/// pivot, since `/v1/models/register` lets a caller point the daemon's outbound
/// connections anywhere. When `SOVEREIGN_GATEWAY_PROXY_ALLOW` is set (comma-
/// separated `host` / `host:port` prefixes) the endpoint must additionally match
/// it. Loopback + LAN stay allowed — the GPU serve tiers live there.
fn proxy_endpoint_allowed(endpoint: &str) -> Result<(), String> {
    use std::net::IpAddr;
    let host = match endpoint.rsplit_once(':') {
        Some((h, _)) => h,
        None => endpoint,
    }
    .trim_start_matches('[')
    .trim_end_matches(']');
    if let Ok(ip) = host.parse::<IpAddr>() {
        let link_local = match ip {
            IpAddr::V4(v4) => v4.is_link_local(),
            IpAddr::V6(v6) => (v6.segments()[0] & 0xffc0) == 0xfe80, // fe80::/10
        };
        if link_local {
            return Err(format!(
                "endpoint {endpoint} targets link-local/metadata space (SSRF-blocked)"
            ));
        }
    }
    if let Ok(allow) = std::env::var("SOVEREIGN_GATEWAY_PROXY_ALLOW") {
        let permitted = allow
            .split(',')
            .map(str::trim)
            .filter(|s| !s.is_empty())
            .any(|entry| endpoint == entry || host == entry || endpoint.starts_with(entry));
        if !permitted {
            return Err(format!(
                "endpoint {endpoint} not in SOVEREIGN_GATEWAY_PROXY_ALLOW"
            ));
        }
    }
    Ok(())
}

/// Reject a model-load `dir` that escapes the allowed tree: any parent-dir (`..`)
/// component is refused outright, and when `SOVEREIGN_GATEWAY_MODEL_ROOT` is set
/// the (canonicalized) dir must live inside it — so an authenticated caller can't
/// turn `/v1/models/load` into an arbitrary-directory read.
fn model_load_dir_allowed(dir: &str) -> Result<(), String> {
    use std::path::{Component, Path};
    if Path::new(dir)
        .components()
        .any(|c| matches!(c, Component::ParentDir))
    {
        return Err(format!(
            "model dir {dir} contains a parent-dir (..) component"
        ));
    }
    if let Ok(root) = std::env::var("SOVEREIGN_GATEWAY_MODEL_ROOT") {
        let root = root.trim();
        if !root.is_empty() {
            let canon_root =
                std::fs::canonicalize(root).unwrap_or_else(|_| Path::new(root).to_path_buf());
            let canon_dir =
                std::fs::canonicalize(dir).unwrap_or_else(|_| Path::new(dir).to_path_buf());
            if !canon_dir.starts_with(&canon_root) {
                return Err(format!(
                    "model dir {dir} is outside SOVEREIGN_GATEWAY_MODEL_ROOT"
                ));
            }
        }
    }
    Ok(())
}

/// `POST /v1/models/load` — load a SECONDARY in-process CPU model (Phase 2
/// multi-model): `{id, dir}`. Loopback-trust; an operator action.
fn models_load(server: &GatewayServer, body: &str) -> HttpReply {
    let req: serde_json::Value = match serde_json::from_str(body) {
        Ok(v) => v,
        Err(e) => {
            return anthropic_err(
                400,
                "invalid_request_error",
                format!("invalid load body: {e}"),
            );
        }
    };
    let (Some(id), Some(dir)) = (
        req.get("id").and_then(|v| v.as_str()),
        req.get("dir").and_then(|v| v.as_str()),
    ) else {
        return anthropic_err(
            400,
            "invalid_request_error",
            "load needs {id, dir}".to_string(),
        );
    };
    if let Err(e) = model_load_dir_allowed(dir) {
        return anthropic_err(403, "permission_error", e);
    }
    match server.load_model(id, dir) {
        Ok(()) => json_reply(200, &serde_json::json!({"loaded": id, "dir": dir})),
        Err(e) => anthropic_err(422, "api_error", format!("load failed: {e}")),
    }
}

/// `POST /v1/models/unload` — unload a secondary model: `{id}`.
fn models_unload(server: &GatewayServer, body: &str) -> HttpReply {
    let req: serde_json::Value = serde_json::from_str(body).unwrap_or(serde_json::Value::Null);
    let Some(id) = req.get("id").and_then(|v| v.as_str()) else {
        return anthropic_err(
            400,
            "invalid_request_error",
            "unload needs {id}".to_string(),
        );
    };
    json_reply(
        200,
        &serde_json::json!({"unloaded": server.unload_model(id)}),
    )
}

/// `POST /v1/corpus/reload` — re-index the RAG corpus from
/// `SOVEREIGN_GATEWAY_CORPUS` and swap it in without a daemon restart, so an
/// operator who edits the corpus dir picks up the change live. Takes no body:
/// the corpus dir is operator-fixed (env), not client-supplied, so there is no
/// path/SSRF surface here. Returns the new passage count.
fn corpus_reload(server: &GatewayServer) -> HttpReply {
    match server.reload_corpus() {
        Ok(n) => json_reply(
            200,
            &serde_json::json!({"reloaded": true, "corpus_docs": n}),
        ),
        Err(e) => err(500, e),
    }
}

/// `POST /v1/cache/clear` — flush the opt-in completion cache without a daemon
/// restart (a no-op returning `0` when caching is disabled). No body; returns how
/// many entries were dropped.
fn cache_clear(server: &GatewayServer) -> HttpReply {
    json_reply(
        200,
        &serde_json::json!({"cleared": true, "entries_dropped": server.clear_cache()}),
    )
}

/// `POST /v1/models/register` — a `model-serve` job registers a GPU serve-process
/// backend: `{id, endpoint, device?, vram_gb?}`. Future `{model: id}` requests are
/// proxied to `endpoint`. Loopback-trust.
fn models_register(server: &GatewayServer, body: &str) -> HttpReply {
    let req: serde_json::Value = match serde_json::from_str(body) {
        Ok(v) => v,
        Err(e) => {
            return anthropic_err(
                400,
                "invalid_request_error",
                format!("invalid register body: {e}"),
            );
        }
    };
    let (Some(id), Some(endpoint)) = (
        req.get("id").and_then(|v| v.as_str()),
        req.get("endpoint").and_then(|v| v.as_str()),
    ) else {
        return anthropic_err(
            400,
            "invalid_request_error",
            "register needs {id, endpoint}".to_string(),
        );
    };
    if let Err(e) = proxy_endpoint_allowed(endpoint) {
        return anthropic_err(403, "permission_error", e);
    }
    let device = req.get("device").and_then(|v| v.as_str()).unwrap_or("gpu");
    let vram = req
        .get("vram_gb")
        .and_then(serde_json::Value::as_f64)
        .unwrap_or(0.0);
    let dialect = req
        .get("dialect")
        .and_then(|v| v.as_str())
        .unwrap_or("openai");
    match server.register_proxy(id, endpoint, device, vram, dialect) {
        Ok(()) => json_reply(
            200,
            &serde_json::json!({"registered": id, "endpoint": endpoint, "dialect": dialect}),
        ),
        Err(e) => anthropic_err(422, "api_error", format!("register failed: {e}")),
    }
}

/// `POST /v1/models/background` — designate the model the reserved `"background"`
/// alias routes to (Phase 2 increment 3): `{id}` to set, `{id: null}` or `{}` to
/// clear. Background work (deliberation jobs, the Code Console background tab) sends
/// `model:"background"` so it runs on the secondary and the primary stays free.
/// `active` reports whether the designated id is currently loaded (else the alias
/// falls back to the primary). Loopback-trust.
fn models_background(server: &GatewayServer, body: &str) -> HttpReply {
    let req: serde_json::Value = match serde_json::from_str(body) {
        Ok(v) => v,
        Err(e) => {
            return anthropic_err(
                400,
                "invalid_request_error",
                format!("invalid background body: {e}"),
            );
        }
    };
    let id = req.get("id").and_then(|v| v.as_str());
    server.set_background(id);
    json_reply(
        200,
        &serde_json::json!({
            "background": id,
            "active": server.background_id(),
        }),
    )
}

/// A minimal blocking HTTP POST to an upstream (`host:port`) — forwards a request
/// to a GPU serve-process backend and returns `(status, body)`. Non-streaming; the
/// streaming forward is a follow-up (increment 2b).
fn proxy_forward(endpoint: &str, path: &str, body: &str) -> Result<(u16, String), String> {
    use std::io::{Read, Write};
    let mut stream =
        std::net::TcpStream::connect(endpoint).map_err(|e| format!("connect {endpoint}: {e}"))?;
    let _ = stream.set_read_timeout(Some(std::time::Duration::from_secs(120)));
    let request = format!(
        "POST {path} HTTP/1.1\r\nHost: {endpoint}\r\nContent-Type: application/json\r\n\
         Content-Length: {}\r\nConnection: close\r\n\r\n{body}",
        body.len()
    );
    stream
        .write_all(request.as_bytes())
        .map_err(|e| e.to_string())?;
    // Bound the read so a runaway upstream can't exhaust memory (F2). 16 MiB is far
    // beyond any real non-streaming message; past it the reply is truncated + parsed.
    let mut resp = String::new();
    (&mut stream)
        .take(16 * 1024 * 1024)
        .read_to_string(&mut resp)
        .map_err(|e| e.to_string())?;
    let status = resp
        .lines()
        .next()
        .and_then(|l| l.split_whitespace().nth(1))
        .and_then(|s| s.parse::<u16>().ok())
        .unwrap_or(502);
    let reply_body = resp
        .split_once("\r\n\r\n")
        .map(|(_, b)| b)
        .unwrap_or("")
        .to_string();
    Ok((status, reply_body))
}

/// Forward an Anthropic `/v1/messages` request to a proxy backend, translating for
/// its dialect. An `anthropic` backend is forwarded verbatim; an `openai` backend
/// (llama-server / vLLM) has the request translated to `/v1/chat/completions` and
/// its reply translated back to the Anthropic message shape.
fn proxy_message(
    endpoint: &str,
    dialect: &str,
    model: &str,
    req: &serde_json::Value,
    body: &str,
) -> HttpReply {
    if dialect == "anthropic" {
        return match proxy_forward(endpoint, "/v1/messages", body) {
            Ok((status, resp)) => HttpReply {
                status,
                content_type: "application/json",
                body: resp,
            },
            Err(e) => anthropic_err(502, "api_error", format!("proxy to {endpoint} failed: {e}")),
        };
    }
    let oai_req = anthropic_to_openai_chat(req);
    match proxy_forward(endpoint, "/v1/chat/completions", &oai_req.to_string()) {
        Ok((200, resp)) => match serde_json::from_str::<serde_json::Value>(&resp) {
            Ok(oai) => json_reply(200, &openai_to_anthropic_message(&oai, model)),
            Err(e) => anthropic_err(
                502,
                "api_error",
                format!("proxy {endpoint} sent non-JSON: {e}"),
            ),
        },
        Ok((status, resp)) => HttpReply {
            status,
            content_type: "application/json",
            body: resp,
        },
        Err(e) => anthropic_err(502, "api_error", format!("proxy to {endpoint} failed: {e}")),
    }
}

/// Flatten an Anthropic message `content` (a string or an array of blocks) to a plain
/// OpenAI string. Only `type == "text"` blocks are included — a non-text block that
/// happens to carry a `text` field must not leak into the prompt (F10), matching
/// `block_text`'s filter for the local path.
fn flatten_content(content: Option<&serde_json::Value>) -> String {
    match content {
        Some(serde_json::Value::String(s)) => s.clone(),
        Some(serde_json::Value::Array(blocks)) => blocks
            .iter()
            .filter(|b| b.get("type").and_then(|t| t.as_str()) == Some("text"))
            .filter_map(|b| b.get("text").and_then(|t| t.as_str()))
            .collect::<Vec<_>>()
            .join("\n"),
        _ => String::new(),
    }
}

/// Translate an Anthropic `/v1/messages` request into an OpenAI
/// `/v1/chat/completions` request (system + messages, max_tokens, temperature).
/// `pub` so the streaming proxy (the binary, increment 2b) reuses it.
pub fn anthropic_to_openai_chat(req: &serde_json::Value) -> serde_json::Value {
    let mut messages = Vec::new();
    match req.get("system") {
        Some(serde_json::Value::String(s)) if !s.is_empty() => {
            messages.push(serde_json::json!({"role": "system", "content": s}));
        }
        Some(serde_json::Value::Array(blocks)) => {
            let sys = blocks
                .iter()
                .filter_map(|b| b.get("text").and_then(|t| t.as_str()))
                .collect::<Vec<_>>()
                .join("\n");
            if !sys.is_empty() {
                messages.push(serde_json::json!({"role": "system", "content": sys}));
            }
        }
        _ => {}
    }
    for m in req
        .get("messages")
        .and_then(|v| v.as_array())
        .into_iter()
        .flatten()
    {
        let role = m.get("role").and_then(|r| r.as_str()).unwrap_or("user");
        messages
            .push(serde_json::json!({"role": role, "content": flatten_content(m.get("content"))}));
    }
    // Forward the requested max_tokens to the upstream WITHOUT the local base-model
    // clamp (F5): a capable GPU backend can serve far more than 4096, and it enforces
    // its own limits. Only a sane floor default when the client omits it.
    let max_tokens = req
        .get("max_tokens")
        .and_then(serde_json::Value::as_u64)
        .filter(|&n| n > 0)
        .unwrap_or(1024);
    let mut out = serde_json::json!({
        "model": req.get("model").cloned().unwrap_or(serde_json::Value::String("local".into())),
        "messages": messages,
        "max_tokens": max_tokens,
        "stream": false,
    });
    if let Some(t) = req.get("temperature") {
        out["temperature"] = t.clone();
    }
    out
}

/// Map an OpenAI `finish_reason` to a VALID Anthropic `stop_reason` — never a
/// pass-through of an OpenAI-only value (e.g. `tool_calls`/`content_filter`), which
/// isn't a legal Anthropic value. `pub` so the streaming transcoder shares it (F9).
pub fn map_openai_finish(finish: &str) -> &'static str {
    match finish {
        "length" => "max_tokens",
        "tool_calls" | "function_call" => "tool_use",
        // "stop", "content_filter", or anything unknown → the safe Anthropic default
        _ => "end_turn",
    }
}

/// Translate an OpenAI `/v1/chat/completions` response into the Anthropic message
/// shape the local client expects.
fn openai_to_anthropic_message(oai: &serde_json::Value, model: &str) -> serde_json::Value {
    let text = oai
        .pointer("/choices/0/message/content")
        .and_then(|v| v.as_str())
        .unwrap_or("");
    let finish = oai
        .pointer("/choices/0/finish_reason")
        .and_then(|v| v.as_str())
        .unwrap_or("stop");
    let stop_reason = map_openai_finish(finish);
    let input = oai
        .pointer("/usage/prompt_tokens")
        .and_then(serde_json::Value::as_u64)
        .unwrap_or(0);
    let output = oai
        .pointer("/usage/completion_tokens")
        .and_then(serde_json::Value::as_u64)
        .unwrap_or(0);
    serde_json::json!({
        "id": "msg_sovereign_proxy",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": [{"type": "text", "text": text}],
        "stop_reason": stop_reason,
        "stop_sequence": serde_json::Value::Null,
        "usage": {"input_tokens": input, "output_tokens": output},
    })
}

/// `POST /v1/messages/count_tokens` — the Anthropic token-count shape. Best-effort
/// (~4 chars/token) over the flattened prompt.
fn anthropic_count_tokens(body: &str) -> HttpReply {
    match serde_json::from_str::<serde_json::Value>(body) {
        Ok(req) => json_reply(
            200,
            &serde_json::json!({
                "input_tokens": approx_tokens(&anthropic_prompt(&req))
            }),
        ),
        Err(e) => anthropic_err(
            400,
            "invalid_request_error",
            format!("invalid request: {e}"),
        ),
    }
}

/// `POST /v1/messages` (non-streaming): generate from the local model and return
/// the Anthropic message shape. Streaming (`stream:true`) is intercepted in
/// main.rs; a missing model is an honest Anthropic error (never fabricated).
fn anthropic_message(server: &GatewayServer, body: &str) -> HttpReply {
    let req: serde_json::Value = match serde_json::from_str(body) {
        Ok(v) => v,
        Err(e) => {
            return anthropic_err(
                400,
                "invalid_request_error",
                format!("invalid messages request: {e}"),
            );
        }
    };
    // SDD-512 CONNECT: an optional `token_law` object constrains live decoding by
    // the M00117 laws (grammar/regex/denylist/regex_denylist/policy + mask_layers)
    // — the SAME planes the `/v1/data-plane/token-law/fuse` route inspects. Absent
    // ⇒ unconstrained, byte-identical to the pre-CONNECT path.
    let token_law: Option<crate::ServingTokenLaw> = match req.get("token_law") {
        Some(v) => match serde_json::from_value::<crate::ServingTokenLaw>(v.clone()) {
            Ok(s) => Some(s),
            Err(e) => {
                return anthropic_err(
                    400,
                    "invalid_request_error",
                    format!("invalid token_law constraint: {e}"),
                );
            }
        },
        None => None,
    };
    let law_active = token_law.as_ref().filter(|s| !s.is_unconstrained());
    let requested = req
        .get("model")
        .and_then(|m| m.as_str())
        .unwrap_or("sovereign-local")
        .to_string();
    // Expand the reserved "background" alias to the designated backend (a CPU
    // secondary or a GPU proxy), so background work routes off the primary (Phase 2
    // inc.3). A non-alias id passes through; an undesignated alias falls to primary.
    let model = server.expand_alias(Some(&requested)).unwrap_or(requested);
    // GPU serve-process backend (Phase 2 inc.2): a proxy-backed model forwards to the
    // upstream llama-server / vLLM instead of generating locally. An `openai` backend
    // (the llama-server/vLLM default) has the request translated to
    // `/v1/chat/completions` and its reply translated back to the Anthropic shape; an
    // `anthropic` backend (another sovereign-gatewayd) is forwarded verbatim.
    if let Some((endpoint, dialect)) = server.resolve_proxy(&model) {
        // SDD-512: token-law can only bite where the box holds the logits. A
        // proxy backend generates OUT-OF-PROCESS (no logit access), so a
        // law-carrying request against it is REFUSED — never forwarded and
        // silently served unconstrained. The no-logit-access boundary honored,
        // not faked: constrain a local model, or drop `token_law`.
        if law_active.is_some() {
            return anthropic_err(
                422,
                "invalid_request_error",
                format!(
                    "token_law constraints cannot be enforced on proxy-backed model \
                     `{model}` (generates out-of-process — no logit access); route to a \
                     local model or omit token_law"
                ),
            );
        }
        let t0 = std::time::Instant::now();
        let mut reply = proxy_message(&endpoint, &dialect, &model, &req, body);
        // Close the redaction bypass: proxy-relayed output never passes through
        // the local generate path's safety spine, so redact secrets/PII from the
        // relayed body here. No-op when the spine (or both passes) is off.
        let guard = crate::GuardConfig::from_env();
        if guard.redacts_output() {
            reply.body = guard.redact_full(&reply.body);
        }
        // Record a proxy observability span so a proxy-backed model's calls show
        // up on /v1/events (tokens approximated from the relayed body length; the
        // local generate path that records local spans is never touched here).
        server.record_proxy_call(
            &model,
            (reply.body.len() / 4) as u64,
            t0.elapsed().as_millis() as u64,
        );
        return reply;
    }
    if !server.has_generator() {
        return anthropic_err(
            503,
            "api_error",
            "no local model loaded — set SOVEREIGN_GATEWAY_MODEL to a model dir \
             (config.json + *.safetensors + tokenizer.json)"
                .to_string(),
        );
    }
    // Ground the prompt in the RAG corpus (no-op when none is loaded) BEFORE
    // generation, so the model answers from retrieved facts, not just the prompt.
    let prompt = server.rag_augment(&anthropic_prompt(&req));
    let max_new = anthropic_max_tokens(&req);
    let mut out = String::new();
    // SDD-512: drive the constrained decode when `token_law` carries active laws
    // (local model only — the proxy path already refused above); else the static
    // empty-mask path, unchanged.
    let generated = server.generate_chat_with_sampler_law(
        Some(&model),
        &prompt,
        max_new,
        sovereign_safetensors_loader::SamplerConfig::greedy(),
        law_active,
        &[],
        |c| out.push_str(c),
    );
    match generated {
        Ok(n) => {
            let mut msg = serde_json::json!({
                "id": "msg_sovereign",
                "type": "message",
                "role": "assistant",
                "model": model,
                "content": [{ "type": "text", "text": out }],
                "stop_reason": "end_turn",
                "stop_sequence": serde_json::Value::Null,
                "usage": { "input_tokens": approx_tokens(&prompt), "output_tokens": n },
            });
            // Surface which laws actually bit, so a caller can confirm the mask
            // was enforced (parallels the fuse route's `layers_active`).
            if let Some(spec) = law_active {
                msg["token_law"] = serde_json::json!({
                    "enforced": true,
                    "layers_active": spec.layers_active(),
                });
            }
            json_reply(200, &msg)
        }
        Err(e) => anthropic_err(500, "api_error", format!("generation error: {e}")),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use sovereign_bit_cheats::BranchPredictor;
    use sovereign_cortex::demo_requests;

    fn srv() -> GatewayServer {
        GatewayServer::new()
    }

    fn body_of(reply: &HttpReply) -> serde_json::Value {
        serde_json::from_str(&reply.body).unwrap()
    }

    #[test]
    fn token_law_fuse_route_derives_named_layers_and_counts_them() {
        let server = srv();
        // grammar-free: positive regex [a-z]+ ∧ negated regex [xyz] over a
        // 4-token vocab {a,x,q,z} → only a,q survive. Two active layers.
        let body = r#"{ "regex": "[a-z]+", "regex_denylist": ["[xyz]"],
                        "vocab": ["a","x","q","z"] }"#;
        let reply = respond(&server, "POST", "/v1/data-plane/token-law/fuse", body);
        assert_eq!(reply.status, 200);
        let v = body_of(&reply);
        assert_eq!(v["kind"], "token-law-fuse");
        assert_eq!(v["allowed_tokens"], 2);
        assert_eq!(
            v["layers_active"],
            serde_json::json!(["regex", "regex_denylist"])
        );
        assert_eq!(v["stop"], false);
        // The metric recorded both fused layers.
        assert_eq!(server.token_law_mask_layers_count(), 2);
        assert!(
            server
                .metrics_prometheus()
                .contains("sovereign_data_plane_token_law_mask_layers 2")
        );
    }

    #[test]
    fn token_law_fuse_route_rejects_empty_vocab_and_bad_regex() {
        let server = srv();
        let empty = respond(
            &server,
            "POST",
            "/v1/data-plane/token-law/fuse",
            r#"{ "vocab": [] }"#,
        );
        assert_eq!(empty.status, 400);
        let bad = respond(
            &server,
            "POST",
            "/v1/data-plane/token-law/fuse",
            r#"{ "regex": "[unterminated", "vocab": ["a"] }"#,
        );
        assert_eq!(bad.status, 400);
    }

    // ── SDD-512 CONNECT: /v1/messages token-law serving boundary ──

    #[test]
    fn messages_rejects_a_malformed_token_law_constraint() {
        // A `token_law` present but ill-typed (regex must be a string) is a 400,
        // never silently dropped — the constraint is load-bearing.
        let s = srv();
        let r = respond(
            &s,
            "POST",
            "/v1/messages",
            r#"{ "messages": [{"role":"user","content":"hi"}], "token_law": { "regex": 123 } }"#,
        );
        assert_eq!(r.status, 400);
        assert!(
            body_of(&r)["error"]["message"]
                .as_str()
                .unwrap()
                .contains("token_law")
        );
    }

    #[test]
    fn messages_refuses_token_law_on_a_proxy_backend_no_logit_access() {
        // The honesty boundary: a proxy model generates out-of-process (no logit
        // access), so a law-carrying request against it is REFUSED (422) — never
        // forwarded and silently served unconstrained.
        let s = srv();
        s.register_proxy("gpu-x", "127.0.0.1:9", "logic", 18.0, "openai")
            .unwrap();
        let r = respond(
            &s,
            "POST",
            "/v1/messages",
            r#"{ "model": "gpu-x", "messages": [{"role":"user","content":"hi"}],
                 "token_law": { "regex": "[a-z]+" } }"#,
        );
        assert_eq!(r.status, 422);
        let msg = body_of(&r)["error"]["message"]
            .as_str()
            .unwrap()
            .to_string();
        assert!(msg.contains("proxy") && msg.contains("logit"), "{msg}");
    }

    #[test]
    fn messages_enforces_token_law_on_a_local_model_and_reports_layers() {
        // End-to-end on a REAL loaded model: the request's regex law compiles
        // against the model's own vocab and confines every decoded token, and the
        // response reports which laws bit. (Per-step confinement is proven
        // rigorously at the QuantModel primitive; this proves the serving wiring:
        // parse → compile → constrained decode → report.)
        let dir = crate::model_fixture::TinyModelDir::new().expect("materialize fixture");
        let mut s = srv();
        s.inject_worker_from_dir(&dir.path_str())
            .expect("fixture must load");
        let r = respond(
            &s,
            "POST",
            "/v1/messages",
            r#"{ "model": "primary", "messages": [{"role":"user","content":"hi"}], "max_tokens": 8, "token_law": { "regex": "[a-z]+" } }"#,
        );
        assert_eq!(r.status, 200);
        let v = body_of(&r);
        assert_eq!(v["token_law"]["enforced"], true);
        assert_eq!(
            v["token_law"]["layers_active"],
            serde_json::json!(["regex"])
        );
        // Every emitted character is confined to the [a-z] law (empty is vacuously
        // fine — an all-masked row stops rather than escaping the constraint).
        let out = v["content"][0]["text"].as_str().unwrap();
        assert!(
            out.chars().all(|c| c.is_ascii_lowercase()),
            "regex [a-z]+ law must confine the live output, got {out:?}"
        );
    }

    #[test]
    fn messages_without_token_law_is_unchanged_on_a_local_model() {
        // Absent token_law ⇒ the static path, no `token_law` field in the reply
        // (byte-identical contract to the pre-CONNECT serving path).
        let dir = crate::model_fixture::TinyModelDir::new().expect("materialize fixture");
        let mut s = srv();
        s.inject_worker_from_dir(&dir.path_str())
            .expect("fixture must load");
        let r = respond(
            &s,
            "POST",
            "/v1/messages",
            r#"{ "model": "primary", "messages": [{"role":"user","content":"hi"}], "max_tokens": 6 }"#,
        );
        assert_eq!(r.status, 200);
        assert!(body_of(&r).get("token_law").is_none());
    }

    #[test]
    fn proxy_endpoint_blocks_link_local_and_metadata() {
        // SSRF pivots: cloud-metadata + link-local are refused regardless of allowlist.
        assert!(proxy_endpoint_allowed("169.254.169.254:80").is_err());
        assert!(proxy_endpoint_allowed("169.254.1.1:8080").is_err());
        assert!(proxy_endpoint_allowed("[fe80::1]:80").is_err());
        // loopback + LAN are the legitimate GPU serve tiers → allowed.
        assert!(proxy_endpoint_allowed("127.0.0.1:8081").is_ok());
        assert!(proxy_endpoint_allowed("192.168.1.5:8000").is_ok());
        assert!(proxy_endpoint_allowed("10.0.0.2:9000").is_ok());
    }

    #[test]
    fn corpus_reload_route_returns_the_passage_count() {
        // No SOVEREIGN_GATEWAY_CORPUS in test ⇒ reload yields an empty corpus, but
        // the route must dispatch and report the count (the wiring contract). The
        // in-place re-index behaviour is covered by the lib-crate reload test.
        let s = srv();
        let r = respond(&s, "POST", "/v1/corpus/reload", "");
        assert_eq!(r.status, 200);
        let v = body_of(&r);
        assert_eq!(v["reloaded"], true);
        assert_eq!(v["corpus_docs"], 0);
        // wrong verb on the resource is a clean 405, not a 404.
        assert_eq!(respond(&s, "GET", "/v1/corpus/reload", "").status, 405);
    }

    #[test]
    fn cache_clear_route_reports_entries_dropped() {
        // Caching disabled in a fresh test server ⇒ 0 entries dropped, but the
        // route must dispatch and report the count (the wiring contract).
        let s = srv();
        let r = respond(&s, "POST", "/v1/cache/clear", "");
        assert_eq!(r.status, 200);
        let v = body_of(&r);
        assert_eq!(v["cleared"], true);
        assert_eq!(v["entries_dropped"], 0);
        assert_eq!(respond(&s, "GET", "/v1/cache/clear", "").status, 405);
    }

    #[test]
    fn model_load_dir_rejects_parent_traversal() {
        assert!(model_load_dir_allowed("../../etc").is_err());
        assert!(model_load_dir_allowed("models/../../../etc/shadow").is_err());
        assert!(model_load_dir_allowed("/var/lib/sovereign-os/models/foo").is_ok());
    }

    #[test]
    fn get_health_is_200_and_invariant_holds() {
        let r = respond(&srv(), "GET", "/health", "");
        assert_eq!(r.status, 200);
        assert_eq!(body_of(&r)["kind"], "health");
        assert_eq!(body_of(&r)["health"]["never_cloud_spill_holds"], true);
    }

    #[test]
    fn post_control_word_round_reads_the_avx_mode_switch() {
        // The M002 round engine over HTTP, with the runtime switch READ per
        // request. avx_mode="custom" runs the bit-machine: 3 rounds from the
        // fixed seed → the same parity constant the crate + Python pin, plus
        // fingerprints, lifecycle events, and metrics.
        let mk = |avx: Option<&str>| {
            let mut b = serde_json::json!({
                "state": {
                    "state": [1, 2, 3, 4, 5, 6, 7, 8],
                    "memory": [1, 2, 3, 4, 5, 6, 7, 8],
                    "rule": [1, 2, 3, 4, 5, 6, 7, 8],
                    "random": [1, 2, 3, 4, 5, 6, 7, 8]
                },
                "rounds": 3
            });
            if let Some(m) = avx {
                b["avx_mode"] = serde_json::json!(m);
            }
            b.to_string()
        };
        // custom → active, runs the bit-machine, parity constant reproduced
        let v = body_of(&respond(
            &srv(),
            "POST",
            "/v1/control-word/round",
            &mk(Some("custom")),
        ));
        assert_eq!(v["kind"], "control-word-round");
        assert_eq!(v["avx_mode"], "custom");
        assert_eq!(v["engine_active"], true);
        assert_eq!(v["result"]["state"][0], 0x8);
        assert_eq!(v["result"]["state"][7], 0x40);
        assert_eq!(v["events"].as_array().unwrap().len(), 4);
        assert_eq!(v["fingerprints"].as_array().unwrap().len(), 8);
        // hybrid → also active
        assert_eq!(
            body_of(&respond(
                &srv(),
                "POST",
                "/v1/control-word/round",
                &mk(Some("hybrid"))
            ))["engine_active"],
            true
        );
        // off / builtin → the bit-machine is NOT run; honest engine-off envelope,
        // no fabricated result.
        for m in ["off", "builtin"] {
            let v = body_of(&respond(
                &srv(),
                "POST",
                "/v1/control-word/round",
                &mk(Some(m)),
            ));
            assert_eq!(v["avx_mode"], m);
            assert_eq!(v["engine_active"], false);
            assert!(v["result"].is_null(), "{m} must not fabricate a result");
            assert!(v["note"].as_str().unwrap().contains("set avx-mode"));
        }
        // a malformed body is a clean 400, never a panic
        assert_eq!(
            respond(&srv(), "POST", "/v1/control-word/round", "{").status,
            400
        );
    }

    #[test]
    fn post_branch_scheduler_tick_runs_the_loop() {
        // committed control word: mode=1 (bits 0..4). paramB flags = 0 → not
        // speculative/sandboxed → shell_allowed → passes the Commit gate.
        let committed: u64 = 1;
        let batch = serde_json::json!({
            "id": [0,1,2,3,4,5,6,7],
            "control": [committed,committed,committed,committed,0,0,0,0],
            "budget": [1,1,1,1,1,1,1,1],
            "score": [100,100,100,100,100,100,100,100],
            "grammar": [1,1,1,1,1,1,1,1],
            "memory": [0,0,0,0,0,0,0,0],
            "route": [0,0,0,0,0,0,0,0]
        });
        let body = serde_json::json!({ "batch": batch, "verify_min_score": 50 }).to_string();
        let v = body_of(&respond(&srv(), "POST", "/v1/branch-scheduler/tick", &body));
        assert_eq!(v["kind"], "branch-scheduler-tick");
        assert_eq!(v["result"]["steps"].as_array().unwrap().len(), 8);
        // lanes 0-3 committed (mode=1), 4-7 draft (mode=0) → committed mask 0b1111
        assert_eq!(v["result"]["committed"], 0b0000_1111);
        assert_eq!(v["result"]["survivors"], 4);
        // survivors packed dense, order preserved
        let ids = v["result"]["committed_ids"].as_array().unwrap();
        assert_eq!(ids[0], 0);
        assert_eq!(ids[3], 3);
        // malformed → clean 400
        assert_eq!(
            respond(&srv(), "POST", "/v1/branch-scheduler/tick", "{").status,
            400
        );
    }

    #[test]
    fn post_branch_scheduler_tick_v2_consumes_the_building_blocks() {
        // route 0 → rule deny, route 1 → rule allow; committed control words (mode=1).
        let batch = serde_json::json!({
            "id": [0,1,2,3,4,5,6,7],
            "control": [1,1,1,1,1,1,1,1],
            "budget": [1,1,1,1,1,1,1,1],
            "score": [100,100,100,100,100,100,100,100],
            "grammar": [1,1,1,1,1,1,1,1],
            "memory": [0xF,0,0xFF,0,0,0,0,0],
            "route": [0,0,1,1,0,1,0,1]
        });
        let body = serde_json::json!({
            "batch": batch,
            "rule_table": [[0],[1]],   // rule 0 deny, rule 1 allow
            "event_class": [0,0,0,0,0,0,0,0],
            "memory_bank": [0xFF],
            "verify_min_score": 50
        })
        .to_string();
        let v = body_of(&respond(
            &srv(),
            "POST",
            "/v1/branch-scheduler/tick-v2",
            &body,
        ));
        assert_eq!(v["kind"], "branch-scheduler-tick-v2");
        // rule table pruned route-0 lanes → only route-1 (2,3,5,7) commit
        assert_eq!(v["result"]["rule_verified"], 0b1010_1100);
        assert_eq!(v["result"]["base"]["committed"], 0b1010_1100);
        // memory recall (bloom) surfaced
        assert_eq!(v["result"]["recall"][0], 4); // popcount(0xF & 0xFF)
        assert_eq!(v["result"]["recall"][2], 8);
        assert_eq!(
            respond(&srv(), "POST", "/v1/branch-scheduler/tick-v2", "{").status,
            400
        );
    }

    #[test]
    fn tick_v2_session_predictor_learns_across_requests() {
        // all 8 branches commit every tick; with a session_id the predictor
        // persists, so predicted_commit climbs from 0 (fresh) toward 0xFF.
        let body = serde_json::json!({
            "batch": {
                "id": [0,1,2,3,4,5,6,7],
                "control": [1,1,1,1,1,1,1,1],
                "budget": [1,1,1,1,1,1,1,1],
                "score": [100,100,100,100,100,100,100,100],
                "grammar": [1,1,1,1,1,1,1,1],
                "memory": [0,0,0,0,0,0,0,0],
                "route": [0,0,0,0,0,0,0,0]
            },
            "verify_min_score": 50,
            "session_id": "sess-learn"
        })
        .to_string();
        let first = body_of(&respond(
            &srv(),
            "POST",
            "/v1/branch-scheduler/tick-v2",
            &body,
        ));
        // fresh predictor predicts nothing at the first draft
        assert_eq!(first["result"]["predicted_commit"], 0);
        // drive several ticks under the same session
        let mut last = first;
        for _ in 0..4 {
            last = body_of(&respond(
                &srv(),
                "POST",
                "/v1/branch-scheduler/tick-v2",
                &body,
            ));
        }
        assert_eq!(last["session_id"], "sess-learn");
        assert_eq!(
            last["result"]["predicted_commit"], 0xFF,
            "predictor learned across requests"
        );
        // a DIFFERENT session starts fresh (isolation)
        let other = body.replace("sess-learn", "sess-other");
        let o = body_of(&respond(
            &srv(),
            "POST",
            "/v1/branch-scheduler/tick-v2",
            &other,
        ));
        assert_eq!(o["result"]["predicted_commit"], 0, "sessions are isolated");
    }

    #[test]
    fn session_store_is_bounded_lru() {
        // Inserting MAX_SESSIONS+extra distinct sessions never grows past the cap;
        // the least-recently-used entries are evicted (OOM-lever closed).
        let mut s = SessionStore::new();
        for i in 0..(MAX_SESSIONS + 100) {
            s.insert(format!("sess-{i}"), BranchPredictor::new(8));
        }
        assert_eq!(s.len(), MAX_SESSIONS, "store must not exceed MAX_SESSIONS");
        // the earliest inserted (LRU) are gone; the latest survive.
        assert!(s.get("sess-0").is_none(), "LRU entry should be evicted");
        assert!(
            s.get(&format!("sess-{}", MAX_SESSIONS + 99)).is_some(),
            "most-recent entry must survive"
        );
    }

    #[test]
    fn session_store_lru_keeps_recently_used() {
        let mut s = SessionStore::new();
        s.insert("keep".into(), BranchPredictor::new(8));
        // fill to capacity with fresh sessions, touching "keep" each round so it
        // stays most-recently-used and is never the eviction victim.
        for i in 0..(MAX_SESSIONS + 50) {
            s.insert(format!("f-{i}"), BranchPredictor::new(8));
            let _ = s.get("keep"); // mark recently used
        }
        assert!(
            s.get("keep").is_some(),
            "a continuously-used session must survive"
        );
        assert_eq!(s.len(), MAX_SESSIONS);
    }

    #[test]
    fn tick_v2_rejects_overlong_session_id() {
        let long = "x".repeat(MAX_SESSION_ID_LEN + 1);
        let body = serde_json::json!({
            "batch": {"id":[0],"control":[1],"budget":[1],"score":[100],
                      "grammar":[1],"memory":[0],"route":[0]},
            "verify_min_score": 50,
            "session_id": long,
        })
        .to_string();
        let r = respond(&srv(), "POST", "/v1/branch-scheduler/tick-v2", &body);
        assert_eq!(r.status, 400, "an over-long session_id must be rejected");
    }

    #[test]
    fn post_math_dot_i8_and_attention_fuse() {
        // VNNI INT8 dot: [1,2,3,4]·[1,1,1,1] = 10
        let v = body_of(&respond(
            &srv(),
            "POST",
            "/v1/math/dot-i8",
            &serde_json::json!({ "a": [1,2,3,4], "b": [1,1,1,1] }).to_string(),
        ));
        assert_eq!(v["kind"], "math-dot-i8");
        assert_eq!(v["dot"], 10);
        // VPTERNLOG attention fuse: query ∧ key ∧ causal
        let a = body_of(&respond(
            &srv(),
            "POST",
            "/v1/math/attention-fuse",
            &serde_json::json!({ "query": [0xFF], "key": [0x3C], "causal": [0x0F] }).to_string(),
        ));
        assert_eq!(a["allow"][0], 0x0C); // 0xFF & 0x3C & 0x0F
        assert_eq!(respond(&srv(), "POST", "/v1/math/dot-i8", "{").status, 400);
    }

    #[test]
    fn post_token_law_allowed_mask_combines_planes() {
        // grammar ∧ schema ∧ tool ∧ safety ∧ route over a 1-word vocab bitset.
        let body = serde_json::json!({
            "laws": [[0b1111_1111u64], [0b0111_1111u64], [0b1111_1110u64],
                     [0b1011_1111u64], [0b1111_1100u64]],
            "combine": "and"
        })
        .to_string();
        let v = body_of(&respond(
            &srv(),
            "POST",
            "/v1/token-law/allowed-mask",
            &body,
        ));
        assert_eq!(v["kind"], "token-law-allowed-mask");
        assert_eq!(v["mask"][0], 0b0011_1100);
        assert_eq!(v["allowed_tokens"], 4);
        // OR admits more
        let orbody =
            serde_json::json!({ "laws": [[0b1u64],[0b10u64]], "combine": "or" }).to_string();
        assert_eq!(
            body_of(&respond(
                &srv(),
                "POST",
                "/v1/token-law/allowed-mask",
                &orbody
            ))["mask"][0],
            0b11
        );
        assert_eq!(
            respond(&srv(), "POST", "/v1/token-law/allowed-mask", "{").status,
            400
        );
    }

    #[test]
    fn post_microcode_decode_runs_the_program() {
        // committed (mode=1) + audit flag (bit 3 of paramB at bits 48..64).
        let committed_audited: u64 = 1 | ((8u64) << 48);
        let body = serde_json::json!({ "control_word": committed_audited }).to_string();
        let v = body_of(&respond(&srv(), "POST", "/v1/microcode/decode", &body));
        assert_eq!(v["kind"], "microcode-decode");
        assert_eq!(v["outcome"]["commit"], true);
        assert_eq!(v["outcome"]["audited"], true);
        let prog = v["program"].as_array().unwrap();
        assert!(prog.iter().any(|o| o == "commit"));
        assert!(prog.iter().any(|o| o == "audit"));
        // sandboxed → cannot durably commit
        let sandboxed: u64 = 1 | ((2u64) << 48);
        let v = body_of(&respond(
            &srv(),
            "POST",
            "/v1/microcode/decode",
            &serde_json::json!({ "control_word": sandboxed }).to_string(),
        ));
        assert_eq!(v["outcome"]["commit"], false);
        assert_eq!(
            respond(&srv(), "POST", "/v1/microcode/decode", "{").status,
            400
        );
    }

    #[test]
    fn round_route_reports_live_steps_per_sec() {
        // the metric is now measured with a real clock (not a fabricated 0).
        let body = serde_json::json!({
            "state": { "state": [1,2,3,4,5,6,7,8], "memory": [1,2,3,4,5,6,7,8],
                       "rule": [1,2,3,4,5,6,7,8], "random": [1,2,3,4,5,6,7,8] },
            "rounds": 500, "avx_mode": "custom"
        })
        .to_string();
        let v = body_of(&respond(&srv(), "POST", "/v1/control-word/round", &body));
        let sps = v["metrics"]["round_update_steps_per_sec"].as_f64().unwrap();
        assert!(
            sps.is_finite() && sps > 0.0,
            "live steps/sec should be > 0, got {sps}"
        );
    }

    #[test]
    fn get_control_word_config_reports_live_runtime_state() {
        let v = body_of(&respond(&srv(), "GET", "/v1/control-word/config", ""));
        assert_eq!(v["kind"], "control-word-config");
        // no state file at the default path in the test env → honest 'builtin'
        assert_eq!(v["avx_mode"], "builtin");
        assert_eq!(v["engine_active"], false);
        // the env-resolved knobs are present + at their defaults
        assert_eq!(v["round_config"]["masked_op"], "branchless");
        assert_eq!(v["round_config"]["per_lane_dna"], false);
        assert_eq!(v["control_word_config"]["overflow_mode"], "abort");
    }

    #[test]
    fn get_manifest_lists_six_surfaces() {
        let r = respond(&srv(), "GET", "/manifest", "");
        assert_eq!(r.status, 200);
        assert_eq!(
            body_of(&r)["manifest"]["surfaces"]
                .as_array()
                .unwrap()
                .len(),
            6
        );
    }

    #[test]
    fn query_string_and_trailing_slash_route_the_same() {
        assert_eq!(respond(&srv(), "GET", "/health/", "").status, 200);
        assert_eq!(respond(&srv(), "GET", "/health?verbose=1", "").status, 200);
    }

    #[test]
    fn post_messages_speaks_the_anthropic_api() {
        let s = srv();
        // /v1/messages is now the Anthropic Messages API. A bare server has no
        // model → an honest Anthropic ERROR envelope (503), never a fabricated
        // message. VS Code / Claude Code / Cline point ANTHROPIC_BASE_URL here.
        let body = serde_json::json!({
            "model": "claude-3-5-sonnet", "max_tokens": 64,
            "system": "be terse",
            "messages": [{"role": "user", "content": "hi"}],
        })
        .to_string();
        let r = respond(&s, "POST", "/v1/messages", &body);
        assert_eq!(r.status, 503);
        let v = body_of(&r);
        assert_eq!(v["type"], "error");
        assert_eq!(v["error"]["type"], "api_error");
        // The sovereign DECISION moved to /v1/infer, which still runs the engine.
        let dec = respond(
            &s,
            "POST",
            "/v1/infer",
            &serde_json::to_string(&demo_requests()[0]).unwrap(),
        );
        assert_eq!(dec.status, 200);
        assert_eq!(body_of(&dec)["kind"], "decision");
        let led = body_of(&respond(&s, "GET", "/admin/ledger", ""));
        assert_eq!(led["ledger"]["total_requests"], 1);
        assert_eq!(led["ledger"]["cloud_spills"], 0);
    }

    #[test]
    fn anthropic_prompt_flattens_system_roles_and_content_blocks() {
        let req = serde_json::json!({
            "system": "S",
            "messages": [
                {"role": "user", "content": "u1"},
                {"role": "assistant", "content": [{"type": "text", "text": "a1"}, {"type": "image", "source": {}}]},
                {"role": "user", "content": [{"type": "text", "text": "u2"}]},
            ],
        });
        let p = anthropic_prompt(&req);
        assert!(p.contains("System: S"));
        assert!(p.contains("Human: u1"));
        assert!(
            p.contains("Assistant: a1"),
            "assistant text block flattened"
        );
        assert!(
            p.contains("Human: u2"),
            "user content-block array flattened"
        );
        assert!(
            p.trim_end().ends_with("Assistant:"),
            "ends open for the assistant to continue"
        );
        assert!(!p.contains("image"), "non-text blocks are skipped");
        assert_eq!(
            anthropic_max_tokens(&serde_json::json!({"max_tokens": 5})),
            5
        );
    }

    #[test]
    fn v1_models_surfaces_model_architecture() {
        use crate::model_fixture::TinyModelDir;

        // No model loaded → architecture is null.
        let empty = GatewayServer::new();
        let m = body_of(&respond(&empty, "GET", "/v1/models", ""));
        assert!(m["architecture"].is_null(), "no model → null architecture");

        // A dense model → architecture present, no MoE block.
        let dense = TinyModelDir::new().expect("dense fixture");
        let mut s = GatewayServer::new();
        s.inject_worker_from_dir(&dense.path_str())
            .expect("load dense");
        let m = body_of(&respond(&s, "GET", "/v1/models", ""));
        assert_eq!(m["architecture"]["layers"], 2);
        assert_eq!(m["architecture"]["vocab"], 256);
        assert!(
            m["architecture"]["mixture_of_experts"].is_null(),
            "a dense model has no MoE block"
        );

        // A MoE model → the mixture_of_experts shape is surfaced for a panel.
        let moe = TinyModelDir::new_moe().expect("moe fixture");
        let mut s2 = GatewayServer::new();
        s2.inject_worker_from_dir(&moe.path_str())
            .expect("load moe");
        let m2 = body_of(&respond(&s2, "GET", "/v1/models", ""));
        let x = &m2["architecture"]["mixture_of_experts"];
        assert_eq!(x["num_experts"], 4);
        assert_eq!(x["experts_per_tok"], 2);
        assert_eq!(x["moe_layers"], 2);
        assert_eq!(x["total_layers"], 2);
    }

    #[test]
    fn multi_model_load_unload_and_list() {
        let s = srv(); // bare server, no model loaded
        // /v1/models lists the placeholder when nothing is loaded
        let m = body_of(&respond(&s, "GET", "/v1/models", ""));
        assert_eq!(m["data"][0]["type"], "model");
        // loading a secondary from a bad dir → 422 Anthropic error (never fabricated)
        let bad = serde_json::json!({"id": "fast", "dir": "/no/such/model/dir"}).to_string();
        let r = respond(&s, "POST", "/v1/models/load", &bad);
        assert_eq!(r.status, 422);
        assert_eq!(body_of(&r)["type"], "error");
        // load needs {id, dir}
        assert_eq!(respond(&s, "POST", "/v1/models/load", "{}").status, 400);
        // unload of an absent model → false, 200
        let u = respond(
            &s,
            "POST",
            "/v1/models/unload",
            &serde_json::json!({"id": "nope"}).to_string(),
        );
        assert_eq!(u.status, 200);
        assert_eq!(body_of(&u)["unloaded"], false);
        // wrong method on the model routes → 405
        assert_eq!(respond(&s, "GET", "/v1/models/load", "").status, 405);
    }

    #[test]
    fn proxy_backend_forwards_to_upstream() {
        use std::io::{Read, Write};
        // a mock GPU serve-process that returns a fixed Anthropic message
        let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
        let addr = listener.local_addr().unwrap();
        let handle = std::thread::spawn(move || {
            if let Ok((mut sock, _)) = listener.accept() {
                let mut buf = [0u8; 2048];
                let _ = sock.read(&mut buf);
                let payload = r#"{"type":"message","role":"assistant","model":"upstream","content":[{"type":"text","text":"from the GPU backend"}],"stop_reason":"end_turn"}"#;
                let resp = format!(
                    "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{payload}",
                    payload.len()
                );
                let _ = sock.write_all(resp.as_bytes());
            }
        });
        let s = srv();
        // register the mock as an anthropic-dialect proxy on the oracle device
        s.register_proxy("big", &addr.to_string(), "oracle", 40.0, "anthropic")
            .unwrap();
        // a request for model "big" is PROXIED to the upstream + its response returned
        let body = serde_json::json!({
            "model": "big", "max_tokens": 8,
            "messages": [{"role": "user", "content": "hi"}],
        })
        .to_string();
        let r = respond(&s, "POST", "/v1/messages", &body);
        handle.join().unwrap();
        assert_eq!(r.status, 200);
        let v = body_of(&r);
        assert_eq!(v["type"], "message");
        assert_eq!(
            v["content"][0]["text"], "from the GPU backend",
            "the gateway forwarded to the backend"
        );
        // and it lists as a proxy on its placed device
        let models = body_of(&respond(&s, "GET", "/v1/models", ""));
        let big = models["data"]
            .as_array()
            .unwrap()
            .iter()
            .find(|m| m["id"] == "big")
            .unwrap();
        assert_eq!(big["device"], "oracle");
        // register needs {id, endpoint}; unload removes the proxy
        assert_eq!(respond(&s, "POST", "/v1/models/register", "{}").status, 400);
        assert_eq!(
            body_of(&respond(
                &s,
                "POST",
                "/v1/models/unload",
                &serde_json::json!({"id":"big"}).to_string()
            ))["unloaded"],
            true
        );
    }

    #[test]
    fn proxy_backend_translates_openai_dialect() {
        use std::io::{Read, Write};
        // a mock llama-server / vLLM upstream: OpenAI /v1/chat/completions shape
        let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
        let addr = listener.local_addr().unwrap();
        let handle = std::thread::spawn(move || {
            if let Ok((mut sock, _)) = listener.accept() {
                let mut buf = [0u8; 4096];
                let _ = sock.read(&mut buf);
                let seen = String::from_utf8_lossy(&buf).to_string();
                let payload = r#"{"choices":[{"message":{"role":"assistant","content":"translated OpenAI reply"},"finish_reason":"stop"}],"usage":{"prompt_tokens":7,"completion_tokens":3}}"#;
                let resp = format!(
                    "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{payload}",
                    payload.len()
                );
                let _ = sock.write_all(resp.as_bytes());
                seen
            } else {
                String::new()
            }
        });
        let s = srv();
        // register through the HTTP surface with dialect "openai" (the default too)
        let reg = serde_json::json!({"id":"gpu-llama","endpoint":addr.to_string(),"device":"logic","vram_gb":18.0,"dialect":"openai"}).to_string();
        assert_eq!(
            body_of(&respond(&s, "POST", "/v1/models/register", &reg))["dialect"],
            "openai"
        );
        // an Anthropic request (with a system prompt) → translated → OpenAI upstream → Anthropic reply
        let body = serde_json::json!({
            "model": "gpu-llama", "max_tokens": 16, "system": "be terse",
            "messages": [{"role": "user", "content": [{"type":"text","text":"hi there"}]}],
        })
        .to_string();
        let r = respond(&s, "POST", "/v1/messages", &body);
        let seen = handle.join().unwrap();
        assert_eq!(r.status, 200);
        // the upstream saw an OpenAI chat request (translated), not the Anthropic body
        assert!(
            seen.contains("/v1/chat/completions"),
            "request must be translated to the OpenAI path"
        );
        assert!(
            seen.contains("\"role\":\"system\"") && seen.contains("be terse"),
            "system prompt must carry over"
        );
        // the reply is translated back to the Anthropic message shape
        let v = body_of(&r);
        assert_eq!(v["type"], "message");
        assert_eq!(v["content"][0]["text"], "translated OpenAI reply");
        assert_eq!(
            v["stop_reason"], "end_turn",
            "openai finish_reason stop → anthropic end_turn"
        );
        assert_eq!(v["usage"]["input_tokens"], 7);
        assert_eq!(v["usage"]["output_tokens"], 3);
    }

    #[test]
    fn background_alias_routes_to_the_designated_proxy() {
        use std::io::{Read, Write};
        // a mock OpenAI upstream (the designated background backend)
        let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
        let addr = listener.local_addr().unwrap();
        let handle = std::thread::spawn(move || {
            if let Ok((mut sock, _)) = listener.accept() {
                let mut buf = [0u8; 2048];
                let _ = sock.read(&mut buf);
                let payload = r#"{"choices":[{"message":{"role":"assistant","content":"from the background model"},"finish_reason":"stop"}],"usage":{"prompt_tokens":4,"completion_tokens":5}}"#;
                let resp = format!(
                    "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{payload}",
                    payload.len()
                );
                let _ = sock.write_all(resp.as_bytes());
            }
        });
        let s = srv();
        // register the backend, then designate it as the "background" target
        s.register_proxy("bg-gpu", &addr.to_string(), "logic", 18.0, "openai")
            .unwrap();
        let set = respond(
            &s,
            "POST",
            "/v1/models/background",
            &serde_json::json!({"id":"bg-gpu"}).to_string(),
        );
        assert_eq!(
            body_of(&set)["active"],
            "bg-gpu",
            "the designated model is loaded → active"
        );
        // GET /v1/models surfaces the background target (so a UI can show it)
        assert_eq!(
            body_of(&respond(&s, "GET", "/v1/models", ""))["background"],
            "bg-gpu",
            "the models list reports the designated background model"
        );
        // a request for the reserved alias "background" reaches that backend
        let body = serde_json::json!({
            "model": "background", "max_tokens": 8,
            "messages": [{"role": "user", "content": "hi"}],
        })
        .to_string();
        let r = respond(&s, "POST", "/v1/messages", &body);
        handle.join().unwrap();
        assert_eq!(r.status, 200);
        assert_eq!(
            body_of(&r)["content"][0]["text"],
            "from the background model"
        );
        // clearing the designation → the alias no longer resolves to a backend
        let clear = respond(&s, "POST", "/v1/models/background", "{}");
        assert!(
            body_of(&clear)["active"].is_null(),
            "cleared → no active background model"
        );
    }

    #[test]
    fn openai_finish_maps_to_valid_anthropic_stop_reasons() {
        // F9 — never pass an OpenAI-only value through as an Anthropic stop_reason.
        assert_eq!(map_openai_finish("length"), "max_tokens");
        assert_eq!(map_openai_finish("stop"), "end_turn");
        assert_eq!(map_openai_finish("tool_calls"), "tool_use");
        assert_eq!(map_openai_finish("content_filter"), "end_turn");
        assert_eq!(map_openai_finish("something_new"), "end_turn");
    }

    #[test]
    fn proxy_translation_is_unclamped_and_text_only() {
        // F5 — a capable GPU backend gets the requested max_tokens, not the local 4096 clamp.
        let req = serde_json::json!({"max_tokens": 16000, "messages": [{"role": "user", "content": "hi"}]});
        let oai = anthropic_to_openai_chat(&req);
        assert_eq!(
            oai["max_tokens"], 16000,
            "the proxy must not clamp to the local 4096"
        );
        // F10 — a non-text block carrying a stray `text` field must NOT leak into the prompt.
        let req2 = serde_json::json!({"messages": [{"role": "user", "content": [
            {"type": "image", "text": "SECRET"}, {"type": "text", "text": "hello"}]}]});
        let content = anthropic_to_openai_chat(&req2)["messages"][0]["content"]
            .as_str()
            .unwrap()
            .to_string();
        assert!(
            content.contains("hello") && !content.contains("SECRET"),
            "non-text block leaked: {content}"
        );
    }

    #[test]
    fn events_endpoint_returns_the_observability_span_ring() {
        let s = srv();
        // empty ring initially
        let v = body_of(&respond(&s, "GET", "/v1/events", ""));
        assert_eq!(v["count"], 0);
        assert!(v["events"].as_array().unwrap().is_empty());
        // a recorded model call surfaces on the endpoint (snake_case event kind)
        s.record_model_call("primary", 5, 10);
        let v = body_of(&respond(&s, "GET", "/v1/events", ""));
        assert_eq!(v["count"], 1);
        assert_eq!(v["events"][0]["kind"], "model_call");
        assert_eq!(v["events"][0]["model"], "primary");
        assert_eq!(v["events"][0]["tokens"], 5);
        assert_eq!(v["events"][0]["provider"], "local");
    }

    #[test]
    fn anthropic_models_and_count_tokens_endpoints() {
        let s = srv();
        let m = respond(&s, "GET", "/v1/models", "");
        assert_eq!(m.status, 200);
        let mv = body_of(&m);
        assert_eq!(mv["data"][0]["type"], "model");
        assert!(mv["data"][0]["id"].is_string());
        assert_eq!(mv["has_more"], false);
        // count_tokens flattens the prompt and returns a positive count
        let body = serde_json::json!({"messages": [{"role": "user", "content": "hello world"}]})
            .to_string();
        let c = respond(&s, "POST", "/v1/messages/count_tokens", &body);
        assert_eq!(c.status, 200);
        assert!(body_of(&c)["input_tokens"].as_u64().unwrap() >= 1);
        // wrong method → 405
        assert_eq!(respond(&s, "POST", "/v1/models", "").status, 405);
        assert_eq!(
            respond(&s, "GET", "/v1/messages/count_tokens", "").status,
            405
        );
    }

    #[test]
    fn post_infer_and_mcp_are_engine_aliases() {
        let s = srv();
        let body = serde_json::to_string(&demo_requests()[0]).unwrap();
        for path in ["/v1/infer", "/mcp"] {
            let r = respond(&s, "POST", path, &body);
            assert_eq!(r.status, 200, "{path}");
            assert_eq!(body_of(&r)["kind"], "decision", "{path}");
        }
    }

    #[test]
    fn malformed_body_is_400() {
        // /v1/messages returns the Anthropic error envelope; /v1/infer the daemon's.
        let a = respond(&srv(), "POST", "/v1/messages", "{not json");
        assert_eq!(a.status, 400);
        assert_eq!(body_of(&a)["type"], "error");
        let d = respond(&srv(), "POST", "/v1/infer", "{not json");
        assert_eq!(d.status, 400);
        assert_eq!(body_of(&d)["kind"], "error");
    }

    #[test]
    fn wrong_method_on_known_route_is_405() {
        assert_eq!(respond(&srv(), "POST", "/health", "").status, 405);
        assert_eq!(respond(&srv(), "GET", "/v1/messages", "").status, 405);
    }

    #[test]
    fn unknown_route_is_404() {
        let r = respond(&srv(), "GET", "/nope", "");
        assert_eq!(r.status, 404);
        assert_eq!(body_of(&r)["kind"], "error");
    }

    #[test]
    fn post_explain_returns_rationale_and_is_read_only() {
        let s = srv();
        let body = serde_json::to_string(&demo_requests()[0]).unwrap();
        let r = respond(&s, "POST", "/v1/explain", &body);
        assert_eq!(r.status, 200);
        let v = body_of(&r);
        assert_eq!(v["kind"], "explanation");
        assert!(v["explanation"].as_str().unwrap().contains("Routed to"));
        // Read-only: a dry-run must not move the ledger.
        let led = body_of(&respond(&s, "GET", "/admin/ledger", ""));
        assert_eq!(led["ledger"]["total_requests"], 0);
    }

    #[test]
    fn get_explain_is_405() {
        assert_eq!(respond(&srv(), "GET", "/v1/explain", "").status, 405);
    }

    #[test]
    fn post_simple_runs_the_engine_from_minimal_input() {
        let s = srv();
        let demo = demo_requests()[0].clone();
        let body = serde_json::json!({ "axes": demo.axes, "expected_quality": 0.8 }).to_string();
        let r = respond(&s, "POST", "/v1/simple", &body);
        assert_eq!(r.status, 200);
        assert_eq!(body_of(&r)["kind"], "decision");
    }

    #[test]
    fn simple_bad_body_is_400_and_get_is_405() {
        assert_eq!(
            respond(&srv(), "POST", "/v1/simple", "{not valid}").status,
            400
        );
        assert_eq!(respond(&srv(), "GET", "/v1/simple", "").status, 405);
    }

    #[test]
    fn engine_refusal_is_422() {
        // An unknown value-plane profile is refused by the engine (not a parse
        // error) — exercises the 422 path, distinct from 400 (bad body).
        let s = srv();
        let demo = demo_requests()[0].clone();
        let body = serde_json::json!({
            "axes": demo.axes,
            "profile": "definitely-not-a-real-profile",
            "expected_quality": 0.5,
        })
        .to_string();
        let r = respond(&s, "POST", "/v1/simple", &body);
        assert_eq!(r.status, 422, "unknown profile is an engine refusal");
        assert_eq!(body_of(&r)["kind"], "error");
    }

    #[test]
    fn post_deliberate_is_best_of_n_read_only() {
        let s = srv();
        let req = demo_requests()[0].clone();
        let body = serde_json::json!({
            "request": req,
            "candidates": [req.reward.clone(), req.reward.clone()],
            "tier": "normal",
        })
        .to_string();
        let r = respond(&s, "POST", "/v1/deliberate", &body);
        assert_eq!(r.status, 200);
        let v = body_of(&r);
        assert_eq!(v["kind"], "deliberation");
        assert_eq!(v["deliberation"]["candidates_considered"], 2);
        // Read-only: ledger unchanged.
        let led = body_of(&respond(&s, "GET", "/admin/ledger", ""));
        assert_eq!(led["ledger"]["total_requests"], 0);
    }

    #[test]
    fn deliberate_bad_body_is_400_and_get_is_405() {
        assert_eq!(
            respond(&srv(), "POST", "/v1/deliberate", "{not valid}").status,
            400
        );
        assert_eq!(respond(&srv(), "GET", "/v1/deliberate", "").status, 405);
    }

    #[test]
    fn post_coat_deliberates_with_associative_recall_read_only() {
        let s = srv();
        // topic 0b1111 overlaps the seeded memory → the CoAT engine recalls real
        // associative evidence at expansion (its defining mechanism).
        let body = serde_json::json!({
            "problem": "prove the routing invariant holds",
            "topic": 15,
            "rung": "coat",
        })
        .to_string();
        let r = respond(&s, "POST", "/v1/coat", &body);
        assert_eq!(r.status, 200);
        let v = body_of(&r);
        assert_eq!(v["kind"], "coat-trace");
        assert_eq!(v["trace"]["rung"], "CoAT");
        assert!(!v["trace"]["best_path"].as_array().unwrap().is_empty());
        assert!(
            v["trace"]["recalled_total"].as_u64().unwrap() >= 1,
            "CoAT must recall associative memory from the live Cortex"
        );
        // No model loaded → thoughts are honestly flagged heuristic.
        assert_eq!(v["trace"]["thought_source"], "heuristic");
        // Read-only invariant: the request ledger + learned state are untouched;
        // ONLY the dry-run counter moves.
        let led = body_of(&respond(&s, "GET", "/admin/ledger", ""));
        assert_eq!(
            led["ledger"]["total_requests"], 0,
            "coat must not inflate requests"
        );
        assert_eq!(
            led["ledger"]["learned"], 0,
            "coat must not learn into memory"
        );
        assert!(
            led["ledger"]["dry_runs"].as_u64().unwrap() >= 1,
            "coat must count as a dry-run"
        );
    }

    #[test]
    fn coat_rungs_and_errors() {
        let s = srv();
        // the CoT rung yields a linear chain, no recall.
        let cot = serde_json::json!({"problem": "x", "rung": "cot"}).to_string();
        let v = body_of(&respond(&s, "POST", "/v1/coat", &cot));
        assert_eq!(v["trace"]["rung"], "CoT");
        assert_eq!(v["trace"]["recalled_total"], 0, "CoT must recall no memory");
        // the C-MCTS + DFS rungs are reachable and behaviourally labelled.
        let cm = body_of(&respond(
            &s,
            "POST",
            "/v1/coat",
            &serde_json::json!({"problem":"x","rung":"cmcts"}).to_string(),
        ));
        assert_eq!(cm["trace"]["rung"], "C-MCTS");
        let df = body_of(&respond(
            &s,
            "POST",
            "/v1/coat",
            &serde_json::json!({"problem":"x","rung":"dfs"}).to_string(),
        ));
        assert_eq!(df["trace"]["strategy"], "dfs");
        // an unknown rung is an engine refusal (422), a bad body is 400, GET is 405.
        let bad = serde_json::json!({"problem": "x", "rung": "bogus"}).to_string();
        assert_eq!(respond(&s, "POST", "/v1/coat", &bad).status, 422);
        assert_eq!(respond(&s, "POST", "/v1/coat", "{nope}").status, 400);
        assert_eq!(respond(&s, "GET", "/v1/coat", "").status, 405);
    }

    #[test]
    fn metrics_is_prometheus_text_and_reflects_the_engine() {
        let s = srv();
        let body = serde_json::to_string(&demo_requests()[0]).unwrap();
        let _ = respond(&s, "POST", "/v1/infer", &body); // one committed decision

        let r = respond(&s, "GET", "/metrics", "");
        assert_eq!(r.status, 200);
        assert!(r.content_type.starts_with("text/plain"));
        // Prometheus exposition: HELP/TYPE headers + the engine's counters.
        assert!(
            r.body
                .contains("# TYPE sovereign_gateway_requests_total counter")
        );
        assert!(r.body.contains("sovereign_gateway_requests_total 1"));
        assert!(
            r.body
                .contains("sovereign_gateway_never_cloud_spill_holds 1")
        );
        assert!(
            r.body
                .contains("sovereign_gateway_route_total{role=\"conductor\"} 1")
        );
    }

    #[test]
    fn reason_phrases_cover_emitted_codes() {
        for code in [200, 400, 404, 405, 413, 422, 431] {
            assert_ne!(reason(code), "Internal Server Error");
        }
    }

    #[test]
    fn payload_too_large_is_413_error() {
        let r = payload_too_large();
        assert_eq!(r.status, 413);
        assert_eq!(reason(413), "Payload Too Large");
        let v = body_of(&r);
        assert_eq!(v["kind"], "error");
        assert!(v["message"].as_str().unwrap().contains("limit"));
    }

    #[test]
    fn headers_too_large_is_431_error() {
        let r = headers_too_large();
        assert_eq!(r.status, 431);
        assert_eq!(reason(431), "Request Header Fields Too Large");
        assert_eq!(body_of(&r)["kind"], "error");
    }
}
