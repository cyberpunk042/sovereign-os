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
//! GET  /v1/models      -> {"data":[…]}             Anthropic models list (the local model)
//! POST /v1/messages/count_tokens -> {"input_tokens":N}  Anthropic token count (best-effort)
//! POST /v1/infer       -> {"kind":"decision", …}   raw engine alias (the routing DECISION)
//! POST /mcp            -> {"kind":"decision", …}   MCP-bridge bind (surface 3)
//! POST /v1/simple      -> {"kind":"decision", …}     simplified request (axes + quality)
//! POST /v1/explain     -> {"kind":"explanation",…} dry-run rationale (read-only)
//! POST /v1/deliberate  -> {"kind":"deliberation",…} best-of-N (read-only)
//! POST /v1/control-word/round -> {"kind":"control-word-round",…} M002 round engine (fingerprints + events + metrics)
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
        ("POST", "/v1/models/load") => models_load(server, body),
        ("POST", "/v1/models/unload") => models_unload(server, body),
        ("POST", "/v1/models/register") => models_register(server, body),
        ("POST", "/v1/models/background") => models_background(server, body),
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
    json_reply(
        200,
        &serde_json::json!({
            "data": data, "has_more": false, "first_id": first, "last_id": last,
            // the model the "background" alias resolves to (null = none designated /
            // designated-but-unloaded → the primary), so a UI can show it (inc.3/UX loop)
            "background": server.background_id(),
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
/// Body: `{ "state": RoundState, "config"?: RoundConfig, "rounds"?: u64 }`.
/// Reply: the resulting state, per-lane DNA fingerprints + diversity index,
/// the last round's lifecycle events, and the service metrics (the same shape
/// exposed to Prometheus). The kernel dispatches to AVX-512 when the host has
/// it — this route is how the cockpit / an operator drives the bit-machine.
fn control_word_round(body: &str) -> HttpReply {
    use sovereign_control_word_service::{
        diversity_index, metrics_from, round_fingerprints, round_with_events,
    };
    use sovereign_simd::round::{RoundConfig, RoundState};

    #[derive(serde::Deserialize)]
    struct Req {
        state: RoundState,
        #[serde(default)]
        config: RoundConfig,
        #[serde(default = "one_round")]
        rounds: u64,
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
    // Run rounds-1 plain, then the final round with lifecycle events.
    let mut cur = req.state;
    for _ in 1..req.rounds {
        cur = sovereign_simd::round::round_update(&cur, req.config);
    }
    let (result, events) = if req.rounds == 0 {
        (cur, Vec::new())
    } else {
        round_with_events(&cur, req.config)
    };
    let fps = round_fingerprints(&result);
    // steps/sec is a live measurement the daemon would fill; report 0 (no clock
    // in this pure handler) so the metric is honest, not fabricated.
    let metrics = metrics_from(&result, req.rounds, 0.0, 1.0);
    json_reply(
        200,
        &serde_json::json!({
            "kind": "control-word-round",
            "rounds": req.rounds,
            "result": result,
            "fingerprints": fps.iter().map(|f| format!("{f:#018x}")).collect::<Vec<_>>(),
            "diversity_index": diversity_index(&fps),
            "events": events,
            "metrics": metrics,
        }),
    )
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
        return proxy_message(&endpoint, &dialect, &model, &req, body);
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
    let prompt = anthropic_prompt(&req);
    let max_new = anthropic_max_tokens(&req);
    let mut out = String::new();
    let generated = server.generate_chat_with_sampler(
        Some(&model),
        &prompt,
        max_new,
        sovereign_safetensors_loader::SamplerConfig::greedy(),
        |c| out.push_str(c),
    );
    match generated {
        Ok(n) => json_reply(
            200,
            &serde_json::json!({
                "id": "msg_sovereign",
                "type": "message",
                "role": "assistant",
                "model": model,
                "content": [{ "type": "text", "text": out }],
                "stop_reason": "end_turn",
                "stop_sequence": serde_json::Value::Null,
                "usage": { "input_tokens": approx_tokens(&prompt), "output_tokens": n },
            }),
        ),
        Err(e) => anthropic_err(500, "api_error", format!("generation error: {e}")),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use sovereign_cortex::demo_requests;

    fn srv() -> GatewayServer {
        GatewayServer::new()
    }

    fn body_of(reply: &HttpReply) -> serde_json::Value {
        serde_json::from_str(&reply.body).unwrap()
    }

    #[test]
    fn get_health_is_200_and_invariant_holds() {
        let r = respond(&srv(), "GET", "/health", "");
        assert_eq!(r.status, 200);
        assert_eq!(body_of(&r)["kind"], "health");
        assert_eq!(body_of(&r)["health"]["never_cloud_spill_holds"], true);
    }

    #[test]
    fn post_control_word_round_runs_the_bit_machine() {
        // The M002 round engine over HTTP: 3 rounds from a fixed seed → the same
        // parity constant the crate + Python engine pin, plus fingerprints,
        // lifecycle events, and metrics.
        let body = serde_json::json!({
            "state": {
                "state": [1, 2, 3, 4, 5, 6, 7, 8],
                "memory": [1, 2, 3, 4, 5, 6, 7, 8],
                "rule": [1, 2, 3, 4, 5, 6, 7, 8],
                "random": [1, 2, 3, 4, 5, 6, 7, 8]
            },
            "rounds": 3
        })
        .to_string();
        let r = respond(&srv(), "POST", "/v1/control-word/round", &body);
        assert_eq!(r.status, 200);
        let v = body_of(&r);
        assert_eq!(v["kind"], "control-word-round");
        assert_eq!(v["result"]["state"][0], 0x8);
        assert_eq!(v["result"]["state"][7], 0x40);
        // 4 lifecycle events bracket the final round (pre/pre-dna/post-dna/post)
        assert_eq!(v["events"].as_array().unwrap().len(), 4);
        // fingerprints present + diversity in range
        assert_eq!(v["fingerprints"].as_array().unwrap().len(), 8);
        let d = v["diversity_index"].as_f64().unwrap();
        assert!((0.125..=1.0).contains(&d));
        // a malformed body is a clean 400, never a panic
        assert_eq!(
            respond(&srv(), "POST", "/v1/control-word/round", "{").status,
            400
        );
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
