//! `sovereign-gatewayd` binary — runs the gateway service.
//!
//! Three transports over the same NDJSON serving core
//! ([`sovereign_gatewayd::GatewayServer::handle_line`]):
//!
//! ```text
//! sovereign-gatewayd                 # bind TCP (default 127.0.0.1:8787), NDJSON
//! sovereign-gatewayd --addr 0.0.0.0:9000
//! sovereign-gatewayd --http          # bind HTTP/1.1 (default 127.0.0.1:8787)
//! sovereign-gatewayd --stdio         # read NDJSON requests on stdin, reply on stdout
//! sovereign-gatewayd --selftest      # run the built-in demo session, print, exit
//! ```
//!
//! In `--http` mode the daemon answers the manifest's bind paths
//! (`GET /health`, `GET /manifest`, `GET /admin/ledger`,
//! `POST /v1/messages|/v1/infer|/mcp|/v1/simple|/v1/explain|/v1/deliberate|/v1/coat`) — see [`sovereign_gatewayd::http`].
//!
//! Wire protocol (one JSON object per line):
//!
//! ```text
//! {"op":"infer","request":{…cortex request…}}   -> {"kind":"decision",…}
//! {"op":"simple-infer","request":{"axes":{…},"expected_quality":0.8}} -> {"kind":"decision",…}
//! {"op":"explain","request":{…}}                 -> {"kind":"explanation",…}  (read-only)
//! {"op":"deliberate","request":{…},"candidates":[…],"tier":"…"} -> {"kind":"deliberation",…}
//! {"op":"coat","problem":"…","topic":15,"rung":"coat"} -> {"kind":"coat-trace",…}  (read-only)
//! {"op":"manifest"}                              -> {"kind":"manifest",…}
//! {"op":"health"}                                -> {"kind":"health",…}
//! {"op":"ledger"}                                -> {"kind":"ledger",…}
//! ```
//!
//! Set `SOVEREIGN_GATEWAY_ADDR` to override the default bind address.

use std::io::{BufRead, BufReader, Read, Write};
use std::net::{TcpListener, TcpStream};
use std::sync::Arc;
use std::sync::atomic::{AtomicUsize, Ordering};

use sovereign_cortex::demo_requests;
use sovereign_gatewayd::GatewayServer;
use sovereign_gatewayd::http;

const DEFAULT_ADDR: &str = "127.0.0.1:8787";

const USAGE: &str = "\
sovereign-gatewayd — the persistent gateway service over the sovereign-cortex engine

USAGE:
    sovereign-gatewayd [MODE] [--addr HOST:PORT]

MODES:
    (default)      bind TCP and speak NDJSON (one JSON request per line)
    --http         bind HTTP/1.1: GET /health /manifest /admin/ledger /metrics;
                   POST /v1/messages /v1/infer /mcp /v1/simple /v1/explain /v1/deliberate /v1/coat
    --stdio        read NDJSON requests on stdin, reply on stdout (MCP / claude-code)
    --selftest     run the built-in demo session, print, exit
    -h, --help     print this help and exit

ENVIRONMENT:
    SOVEREIGN_GATEWAY_ADDR         bind address (default 127.0.0.1:8787)
    SOVEREIGN_GATEWAY_MAX_CONN     max concurrent connections (default 256)
    SOVEREIGN_GATEWAY_TIMEOUT_SECS per-connection read/write deadline (default 30; 0 disables)
    SOVEREIGN_GATEWAY_TOKEN        require Authorization: Bearer <token> on the HTTP surface (unset = open)

  Safety spine (input screening + output redaction; all default on):
    SOVEREIGN_GATEWAY_GUARD                  master switch (0 disables the spine)
    SOVEREIGN_GATEWAY_GUARD_REDACT_SECRETS   redact secrets from generated output
    SOVEREIGN_GATEWAY_GUARD_REDACT_PII       redact PII from generated output
    SOVEREIGN_GATEWAY_GUARD_SCREEN_INJECTION screen prompts for injection
    SOVEREIGN_GATEWAY_GUARD_BLOCK_INJECTION  refuse flagged prompts (default off = log-only)
    SOVEREIGN_GATEWAY_GUARD_INJECTION_THRESHOLD  risk threshold in [0,1] (default 0.5)
    SOVEREIGN_GATEWAY_GUARD_TOXICITY         score output toxicity (flag-only, never censors)";

fn main() {
    let args: Vec<String> = std::env::args().collect();

    if args.iter().any(|a| a == "--help" || a == "-h") {
        println!("{USAGE}");
        return;
    }

    let server = Arc::new(GatewayServer::new());

    if args.iter().any(|a| a == "--selftest") {
        selftest(&server);
        return;
    }

    if args.iter().any(|a| a == "--stdio") {
        run_stdio(&server);
        return;
    }

    // Durable memory: periodically snapshot the learning Cortex to the store so
    // recall survives a restart. Opt-in via SOVEREIGN_GATEWAY_MEMORY (the systemd
    // unit sets it). ~10s cadence bounds worst-case loss on a hard kill; each
    // write is atomic (temp + rename), so a crash never leaves a torn file.
    if std::env::var_os("SOVEREIGN_GATEWAY_MEMORY").is_some() {
        let secs = std::env::var("SOVEREIGN_GATEWAY_MEMORY_SAVE_SECS")
            .ok()
            .and_then(|s| s.parse::<u64>().ok())
            .filter(|&n| n > 0)
            .unwrap_or(10);
        let saver = Arc::clone(&server);
        std::thread::spawn(move || {
            loop {
                std::thread::sleep(std::time::Duration::from_secs(secs));
                if let Err(e) = saver.persist_memory() {
                    eprintln!("sovereign-gatewayd: memory persist failed: {e}");
                }
            }
        });
    }

    let addr = arg_value(&args, "--addr")
        .or_else(|| std::env::var("SOVEREIGN_GATEWAY_ADDR").ok())
        .unwrap_or_else(|| DEFAULT_ADDR.to_string());

    let result = if args.iter().any(|a| a == "--http") {
        run_http(&server, &addr)
    } else {
        run_tcp(&server, &addr)
    };
    if let Err(e) = result {
        eprintln!("sovereign-gatewayd: fatal: {e}");
        std::process::exit(1);
    }
}

/// Pull the value following a `--flag` from the args, if present.
fn arg_value(args: &[String], flag: &str) -> Option<String> {
    args.iter()
        .position(|a| a == flag)
        .and_then(|i| args.get(i + 1))
        .cloned()
}

/// Run the built-in demo session through the serving core and print every
/// reply, then the ledger and health. No socket needed — proves the binary
/// assembles and runs end-to-end.
fn selftest(server: &GatewayServer) {
    eprintln!(
        "# sovereign-gatewayd selftest — {} demo request(s)",
        demo_requests().len()
    );
    for (i, req) in demo_requests().iter().enumerate() {
        let line = serde_json::json!({ "op": "infer", "request": req }).to_string();
        let reply = server.handle_line(&line);
        println!("{reply}");
        eprintln!("[{i}] handled");
    }
    println!("{}", server.handle_line(r#"{"op":"ledger"}"#));
    println!("{}", server.handle_line(r#"{"op":"health"}"#));
    let h = server.health();
    eprintln!(
        "# safety: never-cloud-spill = {}",
        if h.never_cloud_spill_holds {
            "HOLDS"
        } else {
            "VIOLATED"
        }
    );
    if !h.never_cloud_spill_holds {
        std::process::exit(2);
    }
}

/// Read NDJSON requests from stdin, write NDJSON replies to stdout — the shape
/// an MCP bridge or `claude-code` stdio integration speaks.
fn run_stdio(server: &GatewayServer) {
    let stdin = std::io::stdin();
    let mut stdout = std::io::stdout();
    for line in stdin.lock().lines() {
        let line = match line {
            Ok(l) => l,
            Err(_) => break,
        };
        if line.trim().is_empty() {
            continue;
        }
        let reply = server.handle_line(&line);
        if writeln!(stdout, "{reply}").is_err() {
            break;
        }
        let _ = stdout.flush();
    }
}

/// Default cap on concurrent connection-handler threads. Once reached, new
/// connections are accepted and closed immediately (back-pressure) rather than
/// spawning unbounded threads under a connection flood. Override with
/// `SOVEREIGN_GATEWAY_MAX_CONN`.
const DEFAULT_MAX_CONNECTIONS: usize = 256;

fn max_connections() -> usize {
    std::env::var("SOVEREIGN_GATEWAY_MAX_CONN")
        .ok()
        .and_then(|v| v.parse::<usize>().ok())
        .filter(|&n| n > 0)
        .unwrap_or(DEFAULT_MAX_CONNECTIONS)
}

/// Default per-connection read/write timeout. A client that opens a socket and
/// then dribbles (or never sends) bytes can otherwise pin a handler thread
/// forever; with the [`DEFAULT_MAX_CONNECTIONS`] cap, enough such clients wedge
/// the whole daemon (slow-loris). A deadline bounds each blocking read/write so
/// a stalled peer is dropped. Override with `SOVEREIGN_GATEWAY_TIMEOUT_SECS`;
/// `0` disables the deadline (legacy behaviour).
const DEFAULT_TIMEOUT_SECS: u64 = 30;

fn conn_timeout() -> Option<std::time::Duration> {
    let secs = std::env::var("SOVEREIGN_GATEWAY_TIMEOUT_SECS")
        .ok()
        .and_then(|v| v.trim().parse::<u64>().ok())
        .unwrap_or(DEFAULT_TIMEOUT_SECS);
    (secs > 0).then(|| std::time::Duration::from_secs(secs))
}

/// The shared secret required on the HTTP surface, from `SOVEREIGN_GATEWAY_TOKEN`.
/// Unset ⇒ no auth (loopback-default deployments). When set, every HTTP request
/// must carry `Authorization: Bearer <token>` or it is refused `401`. This is the
/// minimum gate that lets the daemon bind beyond loopback (`--addr 0.0.0.0:…`)
/// without exposing memory-mutating + ledger surfaces to any reachable client,
/// and matches what real OpenAI/Anthropic clients already send.
fn auth_token() -> Option<String> {
    std::env::var("SOVEREIGN_GATEWAY_TOKEN")
        .ok()
        .map(|t| t.trim().to_string())
        .filter(|t| !t.is_empty())
}

/// Whether the presented `Authorization` header carries the expected bearer
/// token. The scheme is matched case-insensitively (`Bearer`); the token is
/// compared in length-independent constant time so a matching prefix can't be
/// discovered by timing.
fn authorized(header: Option<&str>, expected: &str) -> bool {
    let Some(header) = header else {
        return false;
    };
    let Some(rest) = header.strip_prefix("Bearer ").or_else(|| {
        // Case-insensitive scheme without allocating the whole header lowercase.
        let (scheme, rest) = header.split_once(' ')?;
        scheme.eq_ignore_ascii_case("bearer").then_some(rest)
    }) else {
        return false;
    };
    constant_time_eq(rest.trim().as_bytes(), expected.as_bytes())
}

/// Constant-time byte-slice equality (no early-out on first mismatch). Folds the
/// length difference in so unequal-length inputs also take the full pass.
fn constant_time_eq(a: &[u8], b: &[u8]) -> bool {
    let mut diff = (a.len() ^ b.len()) as u8;
    let n = a.len().max(b.len());
    for i in 0..n {
        let x = a.get(i).copied().unwrap_or(0);
        let y = b.get(i).copied().unwrap_or(0);
        diff |= x ^ y;
    }
    diff == 0
}

/// Decrements the active-connection counter when its handler thread ends.
struct ConnGuard(Arc<AtomicUsize>);
impl Drop for ConnGuard {
    fn drop(&mut self) {
        self.0.fetch_sub(1, Ordering::Relaxed);
    }
}

/// Shared accept loop: bound concurrent handler threads, then dispatch each
/// connection to `handle` on its own thread. Pure std — no async runtime,
/// honoring the workspace `unsafe_code = forbid` discipline.
fn serve(
    listener: TcpListener,
    server: &Arc<GatewayServer>,
    handle: fn(&GatewayServer, TcpStream) -> std::io::Result<()>,
    reject: fn(TcpStream),
) -> std::io::Result<()> {
    let max = max_connections();
    let timeout = conn_timeout();
    let active = Arc::new(AtomicUsize::new(0));
    for stream in listener.incoming() {
        let stream = match stream {
            Ok(s) => s,
            Err(e) => {
                eprintln!("sovereign-gatewayd: accept failed: {e}");
                continue;
            }
        };
        // Bound every blocking read/write so a stalled peer can't pin a handler
        // thread indefinitely (slow-loris). Applied before the cap check so even
        // the rejection write can't hang.
        if let Some(t) = timeout {
            let _ = stream.set_read_timeout(Some(t));
            let _ = stream.set_write_timeout(Some(t));
        }
        if active.load(Ordering::Relaxed) >= max {
            // At capacity — send a protocol-appropriate rejection (HTTP 503 +
            // Retry-After / an NDJSON error line) so the client sees a
            // retryable status instead of a bare connection reset, then close.
            reject(stream);
            continue;
        }
        active.fetch_add(1, Ordering::Relaxed);
        let guard = ConnGuard(Arc::clone(&active));
        let server = Arc::clone(server);
        // Use a fallible spawn: under resource pressure a thread may fail to
        // start. Drop that one connection and keep serving rather than letting
        // the accept loop panic and take the whole daemon down. On the Err path
        // the closure (and its `guard`) is dropped, decrementing the counter.
        if let Err(e) = std::thread::Builder::new().spawn(move || {
            let _guard = guard; // decrements the counter on thread exit
            if let Err(e) = handle(&server, stream) {
                eprintln!("sovereign-gatewayd: connection ended: {e}");
            }
        }) {
            eprintln!("sovereign-gatewayd: could not spawn handler: {e}");
        }
    }
    Ok(())
}

/// Bind a TCP listener and serve NDJSON (one request per line, one reply per
/// line) over the shared capped accept loop.
fn run_tcp(server: &Arc<GatewayServer>, addr: &str) -> std::io::Result<()> {
    let listener = TcpListener::bind(addr)?;
    eprintln!(
        "sovereign-gatewayd: listening on {addr} (NDJSON; ops: infer/manifest/health/ledger)"
    );
    serve(listener, server, handle_conn, reject_ndjson_overloaded)
}

/// Over-capacity rejection for the NDJSON surface: one error line, then close.
fn reject_ndjson_overloaded(mut stream: TcpStream) {
    let _ = writeln!(
        stream,
        "{{\"kind\":\"error\",\"message\":\"gateway at capacity, retry shortly\"}}"
    );
    let _ = stream.flush();
}

/// Over-capacity rejection for the HTTP surface: `503 Service Unavailable` with
/// a `Retry-After` hint so clients back off instead of hot-looping, then close.
fn reject_http_overloaded(mut stream: TcpStream) {
    const BODY: &str = "{\"error\":\"gateway at capacity\"}";
    let head = format!(
        "HTTP/1.1 503 {}\r\nContent-Type: application/json\r\nContent-Length: {}\r\nRetry-After: 1\r\nConnection: close\r\n\r\n",
        http::reason(503),
        BODY.len()
    );
    let _ = stream.write_all(head.as_bytes());
    let _ = stream.write_all(BODY.as_bytes());
    let _ = stream.flush();
}

fn handle_conn(server: &GatewayServer, stream: TcpStream) -> std::io::Result<()> {
    let peer = stream.peer_addr().ok();
    let mut reader = BufReader::new(stream.try_clone()?);
    let mut writer = stream;
    loop {
        // Cap each NDJSON line so a client can't exhaust memory with one
        // unterminated line (the same DoS class the HTTP body cap covers). A
        // fresh `take` per line gives each its own byte budget.
        let mut line = String::new();
        let n = (&mut reader)
            .take(http::MAX_BODY_BYTES as u64 + 1)
            .read_line(&mut line)?;
        if n == 0 {
            break; // EOF
        }
        if line.len() > http::MAX_BODY_BYTES && !line.ends_with('\n') {
            writeln!(
                writer,
                "{{\"kind\":\"error\",\"message\":\"request line exceeds the {}-byte limit\"}}",
                http::MAX_BODY_BYTES
            )?;
            writer.flush()?;
            break;
        }
        if line.trim().is_empty() {
            continue;
        }
        let reply = server.handle_line(&line);
        writeln!(writer, "{reply}")?;
        writer.flush()?;
    }
    if let Some(peer) = peer {
        eprintln!("sovereign-gatewayd: {peer} disconnected");
    }
    Ok(())
}

/// Bind an HTTP/1.1 listener (thread-per-connection, `Connection: close`). Pure
/// std — request line + headers + `Content-Length` body parsed by hand; routing
/// delegated to [`http::respond`]. Honors the workspace `unsafe_code = forbid`.
fn run_http(server: &Arc<GatewayServer>, addr: &str) -> std::io::Result<()> {
    let listener = TcpListener::bind(addr)?;
    eprintln!(
        "sovereign-gatewayd: HTTP listening on {addr} \
         (GET /health /manifest /admin/ledger /metrics; POST /v1/messages /v1/infer /mcp /v1/simple /v1/explain /v1/deliberate /v1/coat)"
    );
    serve(listener, server, handle_http_conn, reject_http_overloaded)
}

/// Per request-line / header-line byte cap, and the maximum header count. An
/// unterminated line or a header flood is refused with `431` so neither can be
/// buffered without bound (the request-line/header analogue of the body cap).
const MAX_HEADER_LINE: usize = 8 * 1024;
const MAX_HEADERS: usize = 100;

/// Read one line capped at [`MAX_HEADER_LINE`]. Returns the byte count and
/// whether the line overran the cap without a terminating newline.
fn read_capped_line(
    reader: &mut BufReader<TcpStream>,
    buf: &mut String,
) -> std::io::Result<(usize, bool)> {
    let n = reader.take(MAX_HEADER_LINE as u64 + 1).read_line(buf)?;
    let overran = buf.len() > MAX_HEADER_LINE && !buf.ends_with('\n');
    Ok((n, overran))
}

/// Write one HTTP reply (status line + JSON/text body) and flush.
fn write_http(writer: &mut TcpStream, reply: &http::HttpReply) -> std::io::Result<()> {
    let bytes = reply.body.as_bytes();
    let head = format!(
        "HTTP/1.1 {} {}\r\nContent-Type: {}\r\nContent-Length: {}\r\nConnection: close\r\n\r\n",
        reply.status,
        http::reason(reply.status),
        reply.content_type,
        bytes.len()
    );
    writer.write_all(head.as_bytes())?;
    writer.write_all(bytes)?;
    writer.flush()
}

fn handle_http_conn(server: &GatewayServer, stream: TcpStream) -> std::io::Result<()> {
    let mut reader = BufReader::new(stream.try_clone()?);
    let mut writer = stream;

    // Request line: `METHOD PATH HTTP/1.1` — capped so an endless line can't
    // be buffered without bound.
    let mut request_line = String::new();
    let (n, overran) = read_capped_line(&mut reader, &mut request_line)?;
    if n == 0 {
        return Ok(()); // client closed before sending anything
    }
    if overran {
        return write_http(&mut writer, &http::headers_too_large());
    }
    let mut parts = request_line.split_whitespace();
    let method = parts.next().unwrap_or("").to_string();
    let path = parts.next().unwrap_or("/").to_string();

    // Headers until the blank line. We act on Content-Length (body sizing) and
    // Authorization (bearer gate). Each line is capped and the count is bounded
    // (no unbounded header flood).
    let mut content_length = 0usize;
    let mut authorization: Option<String> = None;
    let mut header_count = 0usize;
    loop {
        header_count += 1;
        if header_count > MAX_HEADERS {
            return write_http(&mut writer, &http::headers_too_large());
        }
        let mut line = String::new();
        let (n, overran) = read_capped_line(&mut reader, &mut line)?;
        if n == 0 {
            break;
        }
        if overran {
            return write_http(&mut writer, &http::headers_too_large());
        }
        let trimmed = line.trim_end();
        if trimmed.is_empty() {
            break;
        }
        if let Some((k, v)) = trimmed.split_once(':') {
            let k = k.trim();
            if k.eq_ignore_ascii_case("content-length") {
                content_length = v.trim().parse().unwrap_or(0);
            } else if k.eq_ignore_ascii_case("authorization") {
                authorization = Some(v.trim().to_string());
            }
        }
    }

    // Bearer gate: when SOVEREIGN_GATEWAY_TOKEN is set, every HTTP request must
    // carry a matching `Authorization: Bearer <token>`. Checked after the header
    // loop (so the request is fully framed) and before any routing / generation.
    if let Some(expected) = auth_token()
        && !authorized(authorization.as_deref(), &expected)
    {
        return write_http(
            &mut writer,
            &http::err(401, "missing or invalid bearer token".to_string()),
        );
    }

    // Refuse an over-cap Content-Length BEFORE allocating, so a client can't
    // exhaust memory by claiming a huge body (the buffer is never sized to it).
    if content_length > http::MAX_BODY_BYTES {
        return write_http(&mut writer, &http::payload_too_large());
    }
    // Body of exactly Content-Length bytes (0 for GETs).
    let mut body_bytes = vec![0u8; content_length];
    if content_length > 0 {
        reader.read_exact(&mut body_bytes)?;
    }
    let body = String::from_utf8_lossy(&body_bytes);

    // The OpenAI chat shim streams SSE token-by-token, which the pure
    // request→reply `respond()` cannot express — special-case it here so the
    // cockpit chat console (scripts/inference/prompt.py) gets live deltas.
    let route = path
        .split('?')
        .next()
        .unwrap_or(&path)
        .trim_end_matches('/');
    if method == "POST" && route == "/v1/chat/completions" {
        return stream_chat_completions(server, &mut writer, &body);
    }
    // Anthropic Messages API: stream as SSE when the client asks; otherwise fall
    // through to the non-streaming JSON path in http::respond.
    if method == "POST" && route == "/v1/messages" {
        let wants_stream = serde_json::from_str::<serde_json::Value>(&body)
            .ok()
            .and_then(|v| v.get("stream").and_then(serde_json::Value::as_bool))
            .unwrap_or(false);
        if wants_stream {
            return stream_anthropic_messages(server, &mut writer, &body);
        }
    }

    let reply = http::respond(server, &method, &path, &body);
    write_http(&mut writer, &reply)
}

/// Write one SSE event (`data: {json}\n\n`) and flush.
fn write_sse(writer: &mut TcpStream, obj: &serde_json::Value) -> std::io::Result<()> {
    writer.write_all(format!("data: {obj}\n\n").as_bytes())?;
    writer.flush()
}

/// Write one NAMED SSE event (`event: X\ndata: {json}\n\n`) and flush — the
/// Anthropic stream uses named events (unlike the OpenAI shim's bare `data:`).
fn write_sse_event(
    writer: &mut TcpStream,
    event: &str,
    obj: &serde_json::Value,
) -> std::io::Result<()> {
    writer.write_all(format!("event: {event}\ndata: {obj}\n\n").as_bytes())?;
    writer.flush()
}

/// Serve `POST /v1/messages` with `stream:true` as Anthropic-compatible SSE:
/// `message_start` → `content_block_start` → `content_block_delta`* →
/// `content_block_stop` → `message_delta` → `message_stop`. Generation runs on
/// the locally-loaded model; a missing model is an honest Anthropic error.
fn stream_anthropic_messages(
    server: &GatewayServer,
    writer: &mut TcpStream,
    body: &str,
) -> std::io::Result<()> {
    let req: serde_json::Value = match serde_json::from_str(body) {
        Ok(v) => v,
        Err(e) => {
            return write_http(
                writer,
                &http::anthropic_err(
                    400,
                    "invalid_request_error",
                    format!("invalid messages request: {e}"),
                ),
            );
        }
    };
    let requested = req
        .get("model")
        .and_then(|m| m.as_str())
        .unwrap_or("sovereign-local")
        .to_string();
    // Expand the reserved "background" alias to the designated backend (Phase 2
    // inc.3) so a streamed background request targets the secondary, and the proxy
    // guard below sees the concrete id.
    let model = server.expand_alias(Some(&requested)).unwrap_or(requested);
    // A GPU proxy backend streams via the upstream serve-process (increment 2b):
    // transcode its SSE into the Anthropic event sequence, rather than substituting
    // the primary's stream for the requested proxy model.
    if let Some((endpoint, dialect)) = server.resolve_proxy(&model) {
        return stream_proxy_message(writer, &endpoint, &dialect, &model, &req, body);
    }
    if !server.has_generator() {
        return write_http(
            writer,
            &http::anthropic_err(
                503,
                "api_error",
                "no local model loaded — set SOVEREIGN_GATEWAY_MODEL to a model dir \
                 (config.json + *.safetensors + tokenizer.json)"
                    .to_string(),
            ),
        );
    }
    let prompt = http::anthropic_prompt(&req);
    let max_new = http::anthropic_max_tokens(&req);
    let input_tokens = http::approx_tokens(&prompt);
    let id = "msg_sovereign";

    // SSE head, then the Anthropic event sequence.
    writer.write_all(
        b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n\
          Cache-Control: no-store\r\nConnection: close\r\n\r\n",
    )?;
    writer.flush()?;

    write_sse_event(
        writer,
        "message_start",
        &serde_json::json!({
            "type": "message_start",
            "message": {
                "id": id, "type": "message", "role": "assistant", "model": model,
                "content": [], "stop_reason": serde_json::Value::Null, "stop_sequence": serde_json::Value::Null,
                "usage": { "input_tokens": input_tokens, "output_tokens": 0 },
            }
        }),
    )?;
    write_sse_event(
        writer,
        "content_block_start",
        &serde_json::json!({
            "type": "content_block_start", "index": 0,
            "content_block": { "type": "text", "text": "" }
        }),
    )?;

    let mut io_err: Option<std::io::Error> = None;
    let gen_res = server.generate_chat(Some(model.as_str()), &prompt, max_new, |chunk| {
        if io_err.is_some() {
            return;
        }
        let obj = serde_json::json!({
            "type": "content_block_delta", "index": 0,
            "delta": { "type": "text_delta", "text": chunk },
        });
        if let Err(e) = write_sse_event(writer, "content_block_delta", &obj) {
            io_err = Some(e);
        }
    });
    if let Some(e) = io_err {
        return Err(e); // client hung up mid-stream
    }

    // A generation error is surfaced honestly as a final text delta.
    let output_tokens = match gen_res {
        Ok(n) => n,
        Err(e) => {
            let _ = write_sse_event(
                writer,
                "content_block_delta",
                &serde_json::json!({
                    "type": "content_block_delta", "index": 0,
                    "delta": { "type": "text_delta", "text": format!("[gateway generation error: {e}]") },
                }),
            );
            0
        }
    };

    write_sse_event(
        writer,
        "content_block_stop",
        &serde_json::json!({
            "type": "content_block_stop", "index": 0
        }),
    )?;
    write_sse_event(
        writer,
        "message_delta",
        &serde_json::json!({
            "type": "message_delta",
            "delta": { "stop_reason": "end_turn", "stop_sequence": serde_json::Value::Null },
            "usage": { "output_tokens": output_tokens },
        }),
    )?;
    write_sse_event(
        writer,
        "message_stop",
        &serde_json::json!({ "type": "message_stop" }),
    )?;
    Ok(())
}

/// Read one decoded body block from a proxy upstream: the next dechunked chunk, or up
/// to 4 KiB of a raw (unchunked) body. An empty `Vec` signals end-of-stream.
fn next_proxy_block(reader: &mut BufReader<TcpStream>, chunked: bool) -> Vec<u8> {
    if chunked {
        let mut sz = String::new();
        if reader.read_line(&mut sz).unwrap_or(0) == 0 {
            return Vec::new();
        }
        let n = usize::from_str_radix(sz.trim(), 16).unwrap_or(0);
        if n == 0 {
            return Vec::new(); // terminal chunk
        }
        let mut buf = vec![0u8; n];
        if reader.read_exact(&mut buf).is_err() {
            return Vec::new();
        }
        let mut crlf = [0u8; 2];
        let _ = reader.read_exact(&mut crlf);
        buf
    } else {
        let mut buf = [0u8; 4096];
        match reader.read(&mut buf) {
            Ok(0) | Err(_) => Vec::new(),
            Ok(k) => buf[..k].to_vec(),
        }
    }
}

/// Connect to a proxy upstream, POST `path` + `body` (streaming), and read the
/// response head. Returns the reader positioned at the body plus `(status, chunked)`,
/// or an error string on a transport failure (connect / write / no response).
fn open_proxy_stream(
    endpoint: &str,
    path: &str,
    body: &str,
) -> Result<(BufReader<TcpStream>, u16, bool), String> {
    let mut up =
        TcpStream::connect(endpoint).map_err(|e| format!("proxy connect {endpoint}: {e}"))?;
    let _ = up.set_read_timeout(Some(std::time::Duration::from_secs(300)));
    let request = format!(
        "POST {path} HTTP/1.1\r\nHost: {endpoint}\r\nContent-Type: application/json\r\n\
         Accept: text/event-stream\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
        body.len()
    );
    up.write_all(request.as_bytes())
        .and_then(|()| up.flush())
        .map_err(|_| format!("proxy write to {endpoint} failed"))?;
    let mut reader = BufReader::new(up);
    let mut status_line = String::new();
    if reader.read_line(&mut status_line).unwrap_or(0) == 0 {
        return Err(format!("proxy {endpoint} sent no response"));
    }
    let status = status_line
        .split_whitespace()
        .nth(1)
        .and_then(|s| s.parse::<u16>().ok())
        .unwrap_or(502);
    let mut chunked = false;
    loop {
        let mut h = String::new();
        if reader.read_line(&mut h).unwrap_or(0) == 0 {
            break;
        }
        if h == "\r\n" || h == "\n" {
            break;
        }
        let lower = h.to_ascii_lowercase();
        if lower.starts_with("transfer-encoding:") && lower.contains("chunked") {
            chunked = true;
        }
    }
    Ok((reader, status, chunked))
}

/// Stream a proxy-backed model as Anthropic SSE (Phase 2 increment 2b). Opens a
/// streaming connection to the upstream serve-process: an `anthropic` backend's SSE
/// is relayed verbatim (it already speaks the Anthropic event sequence); an `openai`
/// backend (llama-server / vLLM) has its `/v1/chat/completions` deltas transcoded
/// into `message_start → content_block_delta* → message_stop` as they arrive.
/// Dechunks `Transfer-Encoding: chunked` upstreams. A pre-stream upstream failure is
/// an honest Anthropic error; a client hang-up mid-stream ends the relay cleanly.
fn stream_proxy_message(
    writer: &mut TcpStream,
    endpoint: &str,
    dialect: &str,
    model: &str,
    req: &serde_json::Value,
    body: &str,
) -> std::io::Result<()> {
    let (path, up_body) = if dialect == "anthropic" {
        ("/v1/messages", body.to_string())
    } else {
        let mut oai = http::anthropic_to_openai_chat(req);
        oai["stream"] = serde_json::Value::Bool(true);
        ("/v1/chat/completions", oai.to_string())
    };
    let (mut reader, up_status, chunked) = match open_proxy_stream(endpoint, path, &up_body) {
        Ok(t) => t,
        Err(e) => return write_http(writer, &http::anthropic_err(502, "api_error", e)),
    };
    if up_status != 200 {
        let mut errbody = String::new();
        let _ = reader.read_to_string(&mut errbody);
        return write_http(
            writer,
            &http::anthropic_err(
                502,
                "api_error",
                format!("proxy upstream {up_status}: {}", errbody.trim()),
            ),
        );
    }

    // ---- committed to streaming: send our SSE head ----
    writer.write_all(
        b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n\
          Cache-Control: no-store\r\nConnection: close\r\n\r\n",
    )?;
    writer.flush()?;

    // openai backends need the Anthropic envelope head; anthropic backends relay
    // their own message_start.
    let openai = dialect != "anthropic";
    if openai {
        write_sse_event(
            writer,
            "message_start",
            &serde_json::json!({
                "type": "message_start",
                "message": {
                    "id": "msg_sovereign_proxy", "type": "message", "role": "assistant", "model": model,
                    "content": [], "stop_reason": serde_json::Value::Null, "stop_sequence": serde_json::Value::Null,
                    "usage": { "input_tokens": 0, "output_tokens": 0 },
                }
            }),
        )?;
        write_sse_event(
            writer,
            "content_block_start",
            &serde_json::json!({
                "type": "content_block_start", "index": 0,
                "content_block": { "type": "text", "text": "" }
            }),
        )?;
    }

    // ---- stream the body: dechunk, and for openai transcode each delta ----
    let mut line_buf: Vec<u8> = Vec::new();
    let mut out_chars = 0usize;
    let mut stop_reason = "end_turn".to_string();
    'body: loop {
        let block = next_proxy_block(&mut reader, chunked);
        if block.is_empty() {
            break;
        }

        if !openai {
            // anthropic backend: its bytes ARE the Anthropic SSE — relay verbatim
            if writer
                .write_all(&block)
                .and_then(|()| writer.flush())
                .is_err()
            {
                break; // client hung up
            }
            continue;
        }

        // openai backend: accumulate + process complete `data:` lines
        line_buf.extend_from_slice(&block);
        while let Some(pos) = line_buf.iter().position(|&b| b == b'\n') {
            let line_bytes: Vec<u8> = line_buf.drain(..=pos).collect();
            let line = String::from_utf8_lossy(&line_bytes);
            let line = line.trim();
            let Some(payload) = line.strip_prefix("data:") else {
                continue;
            };
            let payload = payload.trim();
            if payload == "[DONE]" {
                break 'body;
            }
            let Ok(v) = serde_json::from_str::<serde_json::Value>(payload) else {
                continue;
            };
            if let Some(delta) = v
                .pointer("/choices/0/delta/content")
                .and_then(|c| c.as_str())
                && !delta.is_empty()
            {
                out_chars += delta.chars().count();
                if write_sse_event(
                    writer,
                    "content_block_delta",
                    &serde_json::json!({
                        "type": "content_block_delta", "index": 0,
                        "delta": { "type": "text_delta", "text": delta },
                    }),
                )
                .is_err()
                {
                    break 'body; // client hung up
                }
            }
            if let Some(r) = v
                .pointer("/choices/0/finish_reason")
                .and_then(|r| r.as_str())
            {
                stop_reason = match r {
                    "length" => "max_tokens",
                    "stop" => "end_turn",
                    o => o,
                }
                .to_string();
            }
        }
    }

    // ---- openai: close the Anthropic envelope ----
    if openai {
        write_sse_event(
            writer,
            "content_block_stop",
            &serde_json::json!({ "type": "content_block_stop", "index": 0 }),
        )?;
        write_sse_event(
            writer,
            "message_delta",
            &serde_json::json!({
                "type": "message_delta",
                "delta": { "stop_reason": stop_reason, "stop_sequence": serde_json::Value::Null },
                "usage": { "output_tokens": out_chars.div_ceil(4) },
            }),
        )?;
        write_sse_event(
            writer,
            "message_stop",
            &serde_json::json!({ "type": "message_stop" }),
        )?;
    }
    Ok(())
}

/// Stream a proxy-backed model through the OpenAI shim (`/v1/chat/completions`) —
/// the surface the Code Console chat (scripts/inference/prompt.py) rides. The
/// upstream is an `openai`-dialect serve-process, so its SSE (`data: {chunk}` …
/// `data: [DONE]`) is relayed to the client verbatim (dechunked). `anthropic`-dialect
/// proxies are reached via `/v1/messages` instead.
fn stream_proxy_chat_completions(
    writer: &mut TcpStream,
    endpoint: &str,
    req: &serde_json::Value,
) -> std::io::Result<()> {
    let mut oai = req.clone();
    oai["stream"] = serde_json::Value::Bool(true);
    let (mut reader, up_status, chunked) =
        match open_proxy_stream(endpoint, "/v1/chat/completions", &oai.to_string()) {
            Ok(t) => t,
            Err(e) => return write_http(writer, &http::err(502, e)),
        };
    if up_status != 200 {
        let mut errbody = String::new();
        let _ = reader.read_to_string(&mut errbody);
        return write_http(
            writer,
            &http::err(
                502,
                format!("proxy upstream {up_status}: {}", errbody.trim()),
            ),
        );
    }
    writer.write_all(
        b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n\
          Cache-Control: no-store\r\nConnection: close\r\n\r\n",
    )?;
    writer.flush()?;
    // relay the upstream's OpenAI SSE verbatim (already the shape prompt.py consumes)
    loop {
        let block = next_proxy_block(&mut reader, chunked);
        if block.is_empty() {
            break;
        }
        if writer
            .write_all(&block)
            .and_then(|()| writer.flush())
            .is_err()
        {
            break; // client hung up
        }
    }
    Ok(())
}

/// Flatten OpenAI `messages` into a single prompt for the base model (join each
/// turn's non-empty content with newlines; a base completion model continues it).
fn chat_prompt(req: &serde_json::Value) -> String {
    let mut parts: Vec<String> = Vec::new();
    if let Some(msgs) = req.get("messages").and_then(|m| m.as_array()) {
        for m in msgs {
            if let Some(c) = m.get("content").and_then(|c| c.as_str())
                && !c.trim().is_empty()
            {
                parts.push(c.to_string());
            }
        }
    }
    parts.join("\n")
}

/// Serve `POST /v1/chat/completions` as OpenAI-compatible SSE — the exact shape
/// `scripts/inference/prompt.py` consumes: `data: {chunk}` per decoded delta, a
/// final chunk carrying `finish_reason:"stop"` + `usage.completion_tokens`, then
/// `data: [DONE]`. Generation runs on the locally-loaded model; a missing model
/// is an honest 503 (never fabricated output).
fn stream_chat_completions(
    server: &GatewayServer,
    writer: &mut TcpStream,
    body: &str,
) -> std::io::Result<()> {
    let req: serde_json::Value = match serde_json::from_str(body) {
        Ok(v) => v,
        Err(e) => {
            return write_http(
                writer,
                &http::err(400, format!("invalid chat request: {e}")),
            );
        }
    };
    // Expand the "background" alias, then route a GPU proxy through the upstream
    // (Phase 2 inc.2b/UX-loop): the Console chat rides this shim, so it must reach
    // proxy + background-designated models instead of silently using the primary.
    let requested = req
        .get("model")
        .and_then(|m| m.as_str())
        .unwrap_or("sovereign-local")
        .to_string();
    let model = server.expand_alias(Some(&requested)).unwrap_or(requested);
    if let Some((endpoint, dialect)) = server.resolve_proxy(&model) {
        if dialect == "anthropic" {
            return write_http(
                writer,
                &http::err(
                    400,
                    format!(
                        "model '{model}' is an anthropic-dialect proxy — reach it via the \
                         /v1/messages surface, not the OpenAI shim"
                    ),
                ),
            );
        }
        return stream_proxy_chat_completions(writer, &endpoint, &req);
    }
    if !server.has_generator() {
        return write_http(
            writer,
            &http::err(
                503,
                "no local model loaded — set SOVEREIGN_GATEWAY_MODEL to a model dir \
                 (config.json + *.safetensors + tokenizer.json), e.g. via \
                 scripts/intelligence/fetch-model.sh"
                    .to_string(),
            ),
        );
    }
    let prompt = chat_prompt(&req);
    let max_new = req
        .get("max_tokens")
        .and_then(serde_json::Value::as_u64)
        .unwrap_or(96)
        .clamp(1, 1024) as usize;

    // SSE response head, then stream.
    writer.write_all(
        b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n\
          Cache-Control: no-store\r\nConnection: close\r\n\r\n",
    )?;
    writer.flush()?;

    let id = "chatcmpl-sovereign";
    let mut io_err: Option<std::io::Error> = None;
    let gen_res = server.generate_chat(Some(model.as_str()), &prompt, max_new, |chunk| {
        if io_err.is_some() {
            return;
        }
        let obj = serde_json::json!({
            "id": id, "object": "chat.completion.chunk",
            "choices": [{"index": 0, "delta": {"content": chunk}}],
        });
        if let Err(e) = write_sse(writer, &obj) {
            io_err = Some(e);
        }
    });
    if let Some(e) = io_err {
        return Err(e); // client hung up mid-stream
    }
    let final_obj = match gen_res {
        Ok(n) => serde_json::json!({
            "id": id, "object": "chat.completion.chunk",
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            "usage": {"completion_tokens": n, "prompt_tokens": 0, "total_tokens": n},
        }),
        Err(e) => serde_json::json!({
            "id": id, "object": "chat.completion.chunk",
            "choices": [{"index": 0,
                "delta": {"content": format!("[gateway generation error: {e}]")},
                "finish_reason": "stop"}],
        }),
    };
    let _ = write_sse(writer, &final_obj);
    let _ = writer.write_all(b"data: [DONE]\n\n");
    let _ = writer.flush();
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::{authorized, conn_timeout, constant_time_eq};

    #[test]
    fn constant_time_eq_matches_std_eq() {
        assert!(constant_time_eq(b"secret-token", b"secret-token"));
        assert!(!constant_time_eq(b"secret-token", b"secret-toke"));
        assert!(!constant_time_eq(b"secret-token", b"secret-tokeX"));
        assert!(!constant_time_eq(b"", b"x"));
        assert!(constant_time_eq(b"", b""));
    }

    #[test]
    fn authorized_accepts_the_expected_bearer_token() {
        assert!(authorized(Some("Bearer s3cr3t"), "s3cr3t"));
        // Scheme is case-insensitive; surrounding whitespace on the token trimmed.
        assert!(authorized(Some("bearer s3cr3t"), "s3cr3t"));
        assert!(authorized(Some("BEARER  s3cr3t "), "s3cr3t"));
    }

    #[test]
    fn authorized_rejects_wrong_missing_or_malformed() {
        assert!(!authorized(Some("Bearer wrong"), "s3cr3t"));
        assert!(!authorized(Some("s3cr3t"), "s3cr3t"), "no Bearer scheme");
        assert!(!authorized(Some("Basic s3cr3t"), "s3cr3t"), "wrong scheme");
        assert!(!authorized(None, "s3cr3t"), "no header at all");
    }

    #[test]
    fn conn_timeout_defaults_to_a_bounded_deadline() {
        // Unset ⇒ the 30s default (a finite deadline, not None).
        // (Env is process-global; we only assert the unset default here.)
        if std::env::var_os("SOVEREIGN_GATEWAY_TIMEOUT_SECS").is_none() {
            assert_eq!(conn_timeout(), Some(std::time::Duration::from_secs(30)));
        }
    }
}
