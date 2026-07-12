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
    SOVEREIGN_GATEWAY_ADDR     bind address (default 127.0.0.1:8787)
    SOVEREIGN_GATEWAY_MAX_CONN max concurrent connections (default 256)";

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
) -> std::io::Result<()> {
    let max = max_connections();
    let active = Arc::new(AtomicUsize::new(0));
    for stream in listener.incoming() {
        let stream = match stream {
            Ok(s) => s,
            Err(e) => {
                eprintln!("sovereign-gatewayd: accept failed: {e}");
                continue;
            }
        };
        if active.load(Ordering::Relaxed) >= max {
            // At capacity — close immediately instead of spawning another
            // thread, applying back-pressure under a connection flood.
            drop(stream);
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
    serve(listener, server, handle_conn)
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
    serve(listener, server, handle_http_conn)
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

    // Headers until the blank line; the only one we act on is Content-Length.
    // Each line is capped and the count is bounded (no unbounded header flood).
    let mut content_length = 0usize;
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
        if let Some((k, v)) = trimmed.split_once(':')
            && k.trim().eq_ignore_ascii_case("content-length")
        {
            content_length = v.trim().parse().unwrap_or(0);
        }
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
    let route = path.split('?').next().unwrap_or(&path).trim_end_matches('/');
    if method == "POST" && route == "/v1/chat/completions" {
        return stream_chat_completions(server, &mut writer, &body);
    }

    let reply = http::respond(server, &method, &path, &body);
    write_http(&mut writer, &reply)
}

/// Write one SSE event (`data: {json}\n\n`) and flush.
fn write_sse(writer: &mut TcpStream, obj: &serde_json::Value) -> std::io::Result<()> {
    writer.write_all(format!("data: {obj}\n\n").as_bytes())?;
    writer.flush()
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
            return write_http(writer, &http::err(400, format!("invalid chat request: {e}")));
        }
    };
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
    let gen_res = server.generate_chat(&prompt, max_new, |chunk| {
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
