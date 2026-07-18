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

mod agentic;

const DEFAULT_ADDR: &str = "127.0.0.1:8787";

/// Upper bound on a single dechunked block AND on the total buffered by a proxy
/// stream/read, so a malformed or runaway upstream (a bogus giant chunk-size line,
/// or a body with no newline) can't exhaust memory or abort the daemon on a
/// multi-gigabyte allocation. Upstreams are loopback serve-processes, but a buggy
/// one must degrade, not crash the whole gateway.
const MAX_PROXY_BYTES: usize = 16 << 20; // 16 MiB

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
    SOVEREIGN_GATEWAY_TOKEN        shared bearer secret. HTTP clients send `Authorization: Bearer <token>`;
                                   NDJSON clients send `{\"op\":\"auth\",\"token\":\"<token>\"}` as their first frame.
                                   REQUIRED to bind a non-loopback address (0.0.0.0/LAN); unset = keyless loopback-only.
    SOVEREIGN_GATEWAY_CORPUS       directory of .md/.txt docs to ground generation in (RAG); unset = off
    SOVEREIGN_GATEWAY_RAG_TOPK     documents prepended as Context: per prompt (default 3)
    SOVEREIGN_GATEWAY_RATE_CAPACITY  generation burst size — token-bucket capacity (default 60; 0 disables)
    SOVEREIGN_GATEWAY_RATE_PER_SEC   sustained generation rate — tokens/sec refill (default 20)
    SOVEREIGN_GATEWAY_AGENTIC        enable server-side agentic tool use (default OFF); when on, a
                                     /v1/chat/completions request with \"sovereign_agentic\":true runs the
                                     ReAct loop inside the daemon over the built-in pure tools (SDD-712)

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

    // M028 long-running hygiene: age out stale memories periodically.
    // The decay thread shares the unified monotonic clock with every request
    // (F-2026-084) so stale-memory detection is consistent.
    {
        let maintainer = Arc::clone(&server);
        let secs = std::env::var("SOVEREIGN_GATEWAY_MAINTAIN_SECS")
            .ok()
            .and_then(|s| s.parse::<u64>().ok())
            .filter(|&n| n > 0)
            .unwrap_or(60);
        let ttl = std::env::var("SOVEREIGN_GATEWAY_MEMORY_TTL")
            .ok()
            .and_then(|s| s.parse::<u64>().ok())
            .filter(|&n| n > 0)
            .unwrap_or(3600);
        std::thread::spawn(move || {
            loop {
                std::thread::sleep(std::time::Duration::from_secs(secs));
                let now = maintainer.clock_now();
                let aged = maintainer.maintain(now, ttl);
                if aged > 0 {
                    eprintln!(
                        "sovereign-gatewayd: memory decay aged {aged} stale memory(s) (ttl={ttl}s)"
                    );
                }
            }
        });
    }

    let addr = arg_value(&args, "--addr")
        .or_else(|| std::env::var("SOVEREIGN_GATEWAY_ADDR").ok())
        .unwrap_or_else(|| DEFAULT_ADDR.to_string());

    // Refuse to expose a KEYLESS daemon. A loopback bind (127.0.0.1) is reachable
    // only from this host, so keyless is fine for local dev; a non-loopback bind
    // (0.0.0.0, a LAN IP, ::) is reachable by other hosts and would leave the
    // memory-mutating /v1/infer, model load/register, and /admin/ledger surfaces
    // open to anyone who can reach the port. Require a token in that case rather
    // than silently coming up open.
    if !bind_is_loopback(&addr) && auth_token().is_none() {
        eprintln!(
            "sovereign-gatewayd: refusing to bind non-loopback address {addr} without \
             authentication.\n  Set SOVEREIGN_GATEWAY_TOKEN to a shared secret (clients then \
             send `Authorization: Bearer <token>`),\n  or bind a loopback address \
             (e.g. 127.0.0.1:8787) for keyless local-only use."
        );
        std::process::exit(2);
    }

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

/// The shared secret from `SOVEREIGN_GATEWAY_TOKEN`. Unset ⇒ no auth (keyless
/// loopback-only deployments; a non-loopback bind without it is refused at
/// startup — see `bind_is_loopback`). When set, every request must present it:
/// HTTP via `Authorization: Bearer <token>` (else `401`), NDJSON via an
/// `{"op":"auth","token":…}` handshake frame. Matches what real OpenAI/Anthropic
/// clients already send.
fn auth_token() -> Option<String> {
    std::env::var("SOVEREIGN_GATEWAY_TOKEN")
        .ok()
        .map(|t| t.trim().to_string())
        .filter(|t| !t.is_empty())
}

/// Whether `addr` (a `HOST:PORT` bind spec) is loopback-only — reachable solely
/// from this host. A loopback bind is safe to run keyless; a non-loopback bind
/// (`0.0.0.0`, `::`, a specific LAN/public IP) exposes the daemon to other hosts
/// and must carry a token. An unparseable / unresolved host is treated as
/// non-loopback (fail safe — require the token rather than assume local).
fn bind_is_loopback(addr: &str) -> bool {
    use std::net::{IpAddr, SocketAddr};
    // Literal socket address: 127.0.0.1:8787, [::1]:8787, 0.0.0.0:9000.
    if let Ok(sa) = addr.parse::<SocketAddr>() {
        return sa.ip().is_loopback();
    }
    // Otherwise split off the trailing :port and classify the host. `[::1]:p`
    // keeps the brackets until we strip them; a bare host has no colon.
    let host = match addr.rsplit_once(':') {
        Some((h, _)) => h,
        None => addr,
    }
    .trim_start_matches('[')
    .trim_end_matches(']');
    if host.eq_ignore_ascii_case("localhost") {
        return true;
    }
    match host.parse::<IpAddr>() {
        Ok(ip) => ip.is_loopback(), // 127.0.0.0/8, ::1 — but NOT 0.0.0.0 (unspecified)
        Err(_) => false,            // unknown host — require a token
    }
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

/// Parse a first-line NDJSON auth handshake `{"op":"auth","token":"<token>"}` and
/// check the token against `expected` in constant time. Returns true only for a
/// well-formed `op:auth` frame whose token matches. The NDJSON transport carries
/// no HTTP headers, so this frame is how a client presents the bearer secret.
fn ndjson_authenticate(line: &str, expected: &str) -> bool {
    let Ok(v) = serde_json::from_str::<serde_json::Value>(line) else {
        return false;
    };
    if v.get("op").and_then(serde_json::Value::as_str) != Some("auth") {
        return false;
    }
    match v.get("token").and_then(serde_json::Value::as_str) {
        Some(tok) => constant_time_eq(tok.as_bytes(), expected.as_bytes()),
        None => false,
    }
}

fn handle_conn(server: &GatewayServer, stream: TcpStream) -> std::io::Result<()> {
    let peer = stream.peer_addr().ok();
    let mut reader = BufReader::new(stream.try_clone()?);
    let mut writer = stream;
    // When a token is configured the NDJSON transport requires an auth handshake
    // as its first frame (it has no HTTP headers to carry a bearer). Unset token
    // ⇒ already authed (keyless loopback dev; a non-loopback bind can't reach
    // here without a token — see `bind_is_loopback` guard in `main`).
    let expected = auth_token();
    let mut authed = expected.is_none();
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
        // Until authenticated, the ONLY accepted frame is the auth handshake.
        // A bad/absent handshake gets one error line, then the connection closes
        // (no oracle for probing other ops).
        if !authed {
            if expected
                .as_deref()
                .is_some_and(|exp| ndjson_authenticate(&line, exp))
            {
                authed = true;
                writeln!(writer, "{{\"kind\":\"auth\",\"ok\":true}}")?;
                writer.flush()?;
                continue;
            }
            writeln!(
                writer,
                "{{\"kind\":\"error\",\"message\":\"authentication required: send {{\\\"op\\\":\\\"auth\\\",\\\"token\\\":\\\"<token>\\\"}} first\"}}"
            )?;
            writer.flush()?;
            break;
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
                // A malformed Content-Length was silently treated as 0 — the body
                // then read as empty and the request usually 400'd downstream for
                // the wrong reason. Reject the bad header explicitly.
                let raw = v.trim();
                match raw.parse::<usize>() {
                    Ok(n) => content_length = n,
                    Err(_) => {
                        return write_http(
                            &mut writer,
                            &http::err(400, format!("invalid Content-Length header: {raw:?}")),
                        );
                    }
                }
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

    // Admission control on the expensive generation endpoints: a token bucket bounds
    // how fast they are admitted so a runaway client can't peg the box. Refuse with
    // 429 in the requested API's error shape, BEFORE any generation work.
    let is_generation =
        method == "POST" && matches!(route, "/v1/messages" | "/v1/chat/completions");
    if is_generation && !server.admit_generation() {
        let reply = if route == "/v1/chat/completions" {
            http::err(
                429,
                "rate limit exceeded — too many generation requests".to_string(),
            )
        } else {
            http::anthropic_err(
                429,
                "rate_limit_error",
                "rate limit exceeded — too many generation requests".to_string(),
            )
        };
        return write_http(&mut writer, &reply);
    }

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

/// Generate a unique chat-completion id for each request so clients can
/// correlate chunks and detect replays.
fn chat_completion_id() -> String {
    use std::sync::atomic::{AtomicU64, Ordering};
    static COUNTER: AtomicU64 = AtomicU64::new(0);
    let n = COUNTER.fetch_add(1, Ordering::Relaxed);
    format!("chatcmpl-sovereign-{n:016x}")
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
    // Ground in the RAG corpus (no-op when none is loaded) before generation.
    let prompt = server.rag_augment(&http::anthropic_prompt(&req));
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
        // The chunk-size line may carry extensions ("1a;ext=v") — parse only the
        // size token. A `0` size is the terminal chunk; an unparseable or over-cap
        // size ends the stream rather than aborting on a huge allocation (F1/F7).
        let tok = sz.trim().split(';').next().unwrap_or("").trim();
        let n = match usize::from_str_radix(tok, 16) {
            Ok(0) => return Vec::new(), // terminal chunk
            Ok(n) if n <= MAX_PROXY_BYTES => n,
            _ => return Vec::new(), // unparseable / over-cap
        };
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
        let _ = (&mut reader).take(64 * 1024).read_to_string(&mut errbody);
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
    // Redact secrets/PII from relayed openai deltas (F-2026-082 proxy-relay gap):
    // the proxy path never passes through the local generate spine. `None` when
    // the spine is off ⇒ deltas relay untouched. (An `anthropic`-dialect upstream
    // is relayed verbatim below; the operator registered it as Anthropic-speaking.)
    let mut redactor =
        sovereign_gatewayd::ProxyRedactor::from_guard(&sovereign_gatewayd::GuardConfig::from_env());
    let mut line_buf: Vec<u8> = Vec::new();
    let mut out_chars = 0usize;
    let mut stop_reason = "end_turn".to_string();
    let mut saw_terminal = false; // did the upstream signal a clean end ([DONE]/finish_reason)?
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

        // openai backend: accumulate + process complete `data:` lines. Bound the
        // buffer so an upstream that streams without a newline can't grow it without
        // limit (F2).
        line_buf.extend_from_slice(&block);
        if line_buf.len() > MAX_PROXY_BYTES {
            break;
        }
        while let Some(pos) = line_buf.iter().position(|&b| b == b'\n') {
            let line_bytes: Vec<u8> = line_buf.drain(..=pos).collect();
            let line = String::from_utf8_lossy(&line_bytes);
            let line = line.trim();
            let Some(payload) = line.strip_prefix("data:") else {
                continue;
            };
            let payload = payload.trim();
            if payload == "[DONE]" {
                saw_terminal = true;
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
                // Redact across delta boundaries; `emit` is the safe-to-send span.
                let emit = match redactor.as_mut() {
                    Some(r) => r.push(delta),
                    None => delta.to_string(),
                };
                if !emit.is_empty()
                    && write_sse_event(
                        writer,
                        "content_block_delta",
                        &serde_json::json!({
                            "type": "content_block_delta", "index": 0,
                            "delta": { "type": "text_delta", "text": emit },
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
                saw_terminal = true;
                stop_reason = http::map_openai_finish(r).to_string();
            }
        }
    }

    // ---- openai: close the Anthropic envelope ----
    if openai {
        // Flush the redactor's held-back tail as a final delta before we close.
        if let Some(r) = redactor.take() {
            let tail = r.finish();
            if !tail.is_empty() {
                let _ = write_sse_event(
                    writer,
                    "content_block_delta",
                    &serde_json::json!({
                        "type": "content_block_delta", "index": 0,
                        "delta": { "type": "text_delta", "text": tail },
                    }),
                );
            }
        }
        // An upstream that died/timed out mid-stream ended WITHOUT a terminal marker;
        // surface that honestly rather than presenting a clean `end_turn` (F6).
        if !saw_terminal {
            let _ = write_sse_event(
                writer,
                "error",
                &serde_json::json!({
                    "type": "error",
                    "error": { "type": "api_error", "message": "upstream stream ended before completion" },
                }),
            );
        }
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
                "delta": {
                    "stop_reason": if saw_terminal { serde_json::Value::String(stop_reason) } else { serde_json::Value::Null },
                    "stop_sequence": serde_json::Value::Null,
                },
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
        let _ = (&mut reader).take(64 * 1024).read_to_string(&mut errbody);
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
    // Redact secrets/PII from relayed content deltas (F-2026-082 proxy-relay gap).
    // `None` when the spine is off ⇒ the upstream SSE is relayed VERBATIM (the
    // byte-for-byte shape prompt.py consumes; unchanged behavior).
    let mut redactor =
        sovereign_gatewayd::ProxyRedactor::from_guard(&sovereign_gatewayd::GuardConfig::from_env());
    let mut line_buf: Vec<u8> = Vec::new();
    'outer: loop {
        let block = next_proxy_block(&mut reader, chunked);
        if block.is_empty() {
            break;
        }
        // Fast path: no redaction ⇒ verbatim relay.
        if redactor.is_none() {
            if writer
                .write_all(&block)
                .and_then(|()| writer.flush())
                .is_err()
            {
                break;
            }
            continue;
        }
        // Redacting: process complete `data:` lines, rewriting content deltas.
        line_buf.extend_from_slice(&block);
        if line_buf.len() > MAX_PROXY_BYTES {
            break;
        }
        while let Some(pos) = line_buf.iter().position(|&b| b == b'\n') {
            let line_bytes: Vec<u8> = line_buf.drain(..=pos).collect();
            let line = String::from_utf8_lossy(&line_bytes);
            let Some(payload) = line.trim().strip_prefix("data:") else {
                // blank line / comment — pass through verbatim (SSE framing).
                if writer.write_all(&line_bytes).is_err() {
                    break 'outer;
                }
                continue;
            };
            let payload = payload.trim();
            if payload == "[DONE]" {
                // flush the held-back tail as one last content chunk, then close.
                if let Some(r) = redactor.take() {
                    let tail = r.finish();
                    if !tail.is_empty() {
                        let _ = write!(writer, "data: {}\n\n", openai_content_chunk(&tail));
                    }
                }
                let _ = writer.write_all(b"data: [DONE]\n\n");
                let _ = writer.flush();
                break 'outer;
            }
            let out = match redactor.as_mut() {
                Some(r) => redact_openai_sse_chunk(payload, r),
                None => payload.to_string(),
            };
            if write!(writer, "data: {out}\n\n")
                .and_then(|()| writer.flush())
                .is_err()
            {
                break 'outer;
            }
        }
    }
    Ok(())
}

/// A minimal OpenAI chat SSE chunk carrying only a content delta — used to emit
/// the redactor's flushed tail as a final `data:` event.
fn openai_content_chunk(text: &str) -> String {
    serde_json::json!({
        "object": "chat.completion.chunk",
        "choices": [{"index": 0, "delta": {"content": text}, "finish_reason": serde_json::Value::Null}],
    })
    .to_string()
}

/// Rewrite one OpenAI chat SSE `data:` payload, replacing `choices[0].delta.content`
/// with its redactor-processed span (secret/PII-safe across chunk boundaries). All
/// other fields (role, finish_reason, usage, …) are preserved. A non-JSON or
/// content-less payload is returned unchanged.
fn redact_openai_sse_chunk(payload: &str, r: &mut sovereign_gatewayd::ProxyRedactor) -> String {
    let Ok(mut v) = serde_json::from_str::<serde_json::Value>(payload) else {
        return payload.to_string();
    };
    if let Some(content) = v.pointer_mut("/choices/0/delta/content")
        && let Some(s) = content.as_str()
    {
        *content = serde_json::Value::String(r.push(s));
    }
    v.to_string()
}

/// Build the prompt from OpenAI `messages`. When the model ships a `chat_template`
/// we recognize (`template` = Some, F-2026-086), render the turns with the model's
/// real markers (ChatML / Llama-3 / Llama-2) so an instruction-tuned checkpoint
/// behaves. Otherwise — no template, or an exotic one — fall back to the original
/// newline-join of non-empty content (a base completion model continues it). The
/// fallback is byte-identical to the pre-F-2026-086 behavior.
fn chat_prompt(req: &serde_json::Value, template: Option<&str>) -> String {
    if let Some(tmpl) = template
        && let Some(fmt) = sovereign_chat_template::detect_format(tmpl)
        && let Some(msgs) = req.get("messages").and_then(|m| m.as_array())
    {
        let messages: Vec<sovereign_chat_template::Message> = msgs
            .iter()
            .filter_map(|m| {
                let role = m.get("role").and_then(|r| r.as_str()).unwrap_or("user");
                let content = m.get("content").and_then(|c| c.as_str())?;
                Some(sovereign_chat_template::Message::from_role(role, content))
            })
            .collect();
        if !messages.is_empty() {
            return sovereign_chat_template::render(&messages, &fmt, true);
        }
    }
    // Fallback: newline-join non-empty message content (unchanged base behavior).
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

/// Extract sampling parameters from an OpenAI-style request body.
/// Unspecified or out-of-range fields fall back to greedy-equivalent defaults.
fn extract_sampler_config(req: &serde_json::Value) -> sovereign_safetensors_loader::SamplerConfig {
    let temperature = req
        .get("temperature")
        .and_then(|v| v.as_f64())
        .map(|t| t.clamp(0.0, 2.0) as f32)
        .unwrap_or(0.0);
    let top_p = req
        .get("top_p")
        .and_then(|v| v.as_f64())
        .map(|p| {
            let c = p.clamp(0.0, 1.0) as f32;
            if c > 0.0 && c <= 1.0 { Some(c) } else { None }
        })
        .unwrap_or(None);
    let top_k = req
        .get("top_k")
        .and_then(|v| v.as_u64())
        .map(|k| if k > 0 { Some(k as usize) } else { None })
        .unwrap_or(None);
    sovereign_safetensors_loader::SamplerConfig {
        temperature,
        top_p,
        top_k,
        ..sovereign_safetensors_loader::SamplerConfig::default()
    }
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
    // Ground in the RAG corpus (no-op when none is loaded) before generation.
    let prompt = server.rag_augment(&chat_prompt(
        &req,
        server.chat_template_for(Some(&model)).as_deref(),
    ));
    let max_new = req
        .get("max_tokens")
        .and_then(serde_json::Value::as_u64)
        .unwrap_or(96)
        .clamp(1, 1024) as usize;
    let sampler_cfg = extract_sampler_config(&req);
    let stream = req.get("stream").and_then(|v| v.as_bool()).unwrap_or(true);

    // SDD-712 (F-2026-088): server-side agentic tool use. When the request opts
    // in (`sovereign_agentic: true`) AND the daemon enables the capability
    // (SOVEREIGN_GATEWAY_AGENTIC=1, default OFF), run the ReAct loop INSIDE the
    // daemon over the built-in tools (Option A: a Responder over the shared
    // Generator, no clone) and return the final answer. Otherwise fall through.
    if req
        .get("sovereign_agentic")
        .and_then(serde_json::Value::as_bool)
        == Some(true)
        && agentic::agentic_enabled()
    {
        let max_steps = req
            .get("max_steps")
            .and_then(serde_json::Value::as_u64)
            .unwrap_or(agentic::DEFAULT_MAX_STEPS as u64)
            .clamp(1, 16) as usize;
        return agentic_chat_completion(server, writer, &model, &prompt, max_new, max_steps);
    }

    // SDD-711 (F-2026-088): OpenAI-compatible tool use. When the request
    // advertises `tools`, take the tool-aware path — generate buffered, then
    // return a `tool_calls` response the CLIENT executes (standard client-driven
    // loop; the daemon does NOT run the tool). Absent/empty `tools` → the
    // existing token-streaming path below runs byte-identically.
    let tools_val = req.get("tools").cloned().unwrap_or(serde_json::Value::Null);
    let tool_specs = sovereign_tool_bridge::openai_tools_to_specs(&tools_val);
    if !tool_specs.is_empty() {
        return tool_aware_chat_completion(
            server,
            writer,
            &model,
            &prompt,
            max_new,
            &tool_specs,
            sampler_cfg,
        );
    }

    if stream {
        // SSE response head, then stream.
        writer.write_all(
            b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n\
              Cache-Control: no-store\r\nConnection: close\r\n\r\n",
        )?;
        writer.flush()?;

        // Heartbeat before first-token latency so client idle-timeouts don't fire.
        let _ = writer.write_all(b":keepalive\n\n");
        let _ = writer.flush();

        let id = chat_completion_id();
        let mut io_err: Option<std::io::Error> = None;
        let gen_res = server.generate_chat_with_sampler(
            Some(model.as_str()),
            &prompt,
            max_new,
            sampler_cfg,
            |chunk| {
                if io_err.is_some() {
                    return;
                }
                let obj = serde_json::json!({
                    "id": &id, "object": "chat.completion.chunk",
                    "choices": [{"index": 0, "delta": {"content": chunk}}],
                });
                if let Err(e) = write_sse(writer, &obj) {
                    io_err = Some(e);
                }
            },
        );
        if let Some(e) = io_err {
            return Err(e); // client hung up mid-stream
        }
        let final_obj = match gen_res {
            Ok(n) => serde_json::json!({
                "id": &id, "object": "chat.completion.chunk",
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                "usage": {"completion_tokens": n, "prompt_tokens": 0, "total_tokens": n},
            }),
            Err(e) => serde_json::json!({
                "id": &id, "object": "chat.completion.chunk",
                "choices": [{"index": 0,
                    "delta": {"content": format!("[gateway generation error: {e}]")},
                    "finish_reason": "error"}],
            }),
        };
        let _ = write_sse(writer, &final_obj);
        let _ = writer.write_all(b"data: [DONE]\n\n");
        let _ = writer.flush();
        Ok(())
    } else {
        // Non-streaming JSON shape (F-2026-086).
        let mut buf = String::new();
        let id = chat_completion_id();
        let gen_res = server.generate_chat_with_sampler(
            Some(model.as_str()),
            &prompt,
            max_new,
            sampler_cfg,
            |chunk| buf.push_str(chunk),
        );
        let body = match gen_res {
            Ok(n) => serde_json::json!({
                "id": &id,
                "object": "chat.completion",
                "choices": [{
                    "index": 0,
                    "message": {"role": "assistant", "content": buf},
                    "finish_reason": "stop"
                }],
                "usage": {"prompt_tokens": 0, "completion_tokens": n, "total_tokens": n},
            }),
            Err(e) => serde_json::json!({
                "id": &id,
                "object": "chat.completion",
                "choices": [{
                    "index": 0,
                    "message": {"role": "assistant", "content": format!("[gateway generation error: {e}]")},
                    "finish_reason": "error"
                }],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            }),
        };
        write_http(
            writer,
            &http::HttpReply {
                status: 200,
                content_type: "application/json",
                body: body.to_string(),
            },
        )
    }
}

/// SDD-711 (F-2026-088): shape the SSE payloads for a completed tool-aware turn.
/// Pure + model-free (so it is unit-tested without a model): given the full
/// buffered model output, the advertised tools, an id, and the token count,
/// returns `(delta_chunk, final_chunk)`. If the output contains a call to an
/// ADVERTISED tool, the delta carries an OpenAI `tool_calls` block and the final
/// chunk's `finish_reason` is `"tool_calls"` (the client runs the tool); else the
/// delta carries the plain content and the finish is `"stop"`.
fn shape_tool_completion(
    output: &str,
    specs: &[sovereign_tool_bridge::ToolSpec],
    id: &str,
    n: usize,
) -> (serde_json::Value, serde_json::Value) {
    match sovereign_tool_bridge::extract_advertised_call(output, specs) {
        Some(call) => {
            let delta = serde_json::json!({
                "id": id, "object": "chat.completion.chunk",
                "choices": [{"index": 0, "delta": {"role": "assistant", "tool_calls": [{
                    "index": 0, "id": "call_0", "type": "function",
                    "function": {"name": call.name, "arguments": call.args},
                }]}}],
            });
            let final_obj = serde_json::json!({
                "id": id, "object": "chat.completion.chunk",
                "choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}],
                "usage": {"completion_tokens": n, "prompt_tokens": 0, "total_tokens": n},
            });
            (delta, final_obj)
        }
        None => {
            let delta = serde_json::json!({
                "id": id, "object": "chat.completion.chunk",
                "choices": [{"index": 0, "delta": {"content": output}}],
            });
            let final_obj = serde_json::json!({
                "id": id, "object": "chat.completion.chunk",
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                "usage": {"completion_tokens": n, "prompt_tokens": 0, "total_tokens": n},
            });
            (delta, final_obj)
        }
    }
}

/// SDD-711 (F-2026-088): serve `/v1/chat/completions` when the request carries
/// `tools`. Teaches the model the bracket convention, generates the reply
/// BUFFERED (a tool call is only detectable once the whole reply is in hand),
/// then emits either a `tool_calls` response or plain content via
/// [`shape_tool_completion`]. Reuses `generate_chat` (safety spine intact); no
/// multi-step agent loop and no model-sharing change — the client executes the
/// tool and calls back, per the standard OpenAI tool loop.
fn tool_aware_chat_completion(
    server: &GatewayServer,
    writer: &mut TcpStream,
    model: &str,
    base_prompt: &str,
    max_new: usize,
    specs: &[sovereign_tool_bridge::ToolSpec],
    sampler_cfg: sovereign_safetensors_loader::SamplerConfig,
) -> std::io::Result<()> {
    let preamble = sovereign_tool_bridge::tool_specs_to_prompt(specs);
    let prompt = format!("{preamble}\n{base_prompt}");

    writer.write_all(
        b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n\
          Cache-Control: no-store\r\nConnection: close\r\n\r\n",
    )?;
    writer.flush()?;

    let id = chat_completion_id();
    let mut buf = String::new();
    let gen_res =
        server.generate_chat_with_sampler(Some(model), &prompt, max_new, sampler_cfg, |chunk| {
            buf.push_str(chunk)
        });
    let (delta, final_obj) = match gen_res {
        Ok(n) => shape_tool_completion(&buf, specs, &id, n),
        Err(e) => {
            // No delta on error; report it in the final chunk as content.
            let err = serde_json::json!({
                "id": &id, "object": "chat.completion.chunk",
                "choices": [{"index": 0,
                    "delta": {"content": format!("[gateway generation error: {e}]")},
                    "finish_reason": "error"}],
            });
            (serde_json::Value::Null, err)
        }
    };
    if !delta.is_null() {
        let _ = write_sse(writer, &delta);
    }
    let _ = write_sse(writer, &final_obj);
    let _ = writer.write_all(b"data: [DONE]\n\n");
    let _ = writer.flush();
    Ok(())
}

/// SDD-712 (F-2026-088): serve a server-side agentic turn. Runs the ReAct loop
/// inside the daemon over the built-in tools (Option A — a Responder over the
/// shared generator, no clone) and returns only the final answer as an ordinary
/// assistant message (`finish_reason:"stop"`); the tool calls happened
/// internally. The loop's per-step generation goes through `generate_chat`, so
/// the safety spine screens every step.
fn agentic_chat_completion(
    server: &GatewayServer,
    writer: &mut TcpStream,
    model: &str,
    prompt: &str,
    max_new: usize,
    max_steps: usize,
) -> std::io::Result<()> {
    // Deterministic seed: the daemon's generation is deterministic and the loop
    // breaks cycles with its repeat-guard, so a fixed seed keeps turns reproducible.
    let answer = agentic::run_agent(server, Some(model), prompt, max_new, max_steps, 0);

    writer.write_all(
        b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n\
          Cache-Control: no-store\r\nConnection: close\r\n\r\n",
    )?;
    writer.flush()?;

    let _ = writer.write_all(b":keepalive\n\n");
    let _ = writer.flush();

    let id = chat_completion_id();
    let content = serde_json::json!({
        "id": &id, "object": "chat.completion.chunk",
        "choices": [{"index": 0, "delta": {"role": "assistant", "content": answer}}],
    });
    let _ = write_sse(writer, &content);
    let final_obj = serde_json::json!({
        "id": &id, "object": "chat.completion.chunk",
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
    });
    let _ = write_sse(writer, &final_obj);
    let _ = writer.write_all(b"data: [DONE]\n\n");
    let _ = writer.flush();
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::{
        authorized, bind_is_loopback, chat_prompt, conn_timeout, constant_time_eq,
        ndjson_authenticate, shape_tool_completion,
    };
    use sovereign_tool_bridge::openai_tools_to_specs;

    #[test]
    fn bind_is_loopback_classifies_addrs() {
        // loopback → keyless allowed
        assert!(bind_is_loopback("127.0.0.1:8787"));
        assert!(bind_is_loopback("127.0.0.5:1"));
        assert!(bind_is_loopback("[::1]:8787"));
        assert!(bind_is_loopback("localhost:8787"));
        assert!(bind_is_loopback("LocalHost:9000"));
        // exposed → token required
        assert!(!bind_is_loopback("0.0.0.0:9000")); // unspecified = all interfaces
        assert!(!bind_is_loopback("[::]:9000"));
        assert!(!bind_is_loopback("192.168.1.10:8787"));
        assert!(!bind_is_loopback("10.0.0.2:8787"));
        // unparseable host → fail safe (require token)
        assert!(!bind_is_loopback("not-an-addr"));
        assert!(!bind_is_loopback("example.com:80"));
    }

    #[test]
    fn openai_sse_chunk_redaction_preserves_structure() {
        use super::{openai_content_chunk, redact_openai_sse_chunk};
        let mut r = sovereign_gatewayd::ProxyRedactor::from_guard(
            &sovereign_gatewayd::GuardConfig::default(),
        )
        .expect("redaction on by default");
        // A parseable chunk keeps id/index/finish_reason; content becomes a string
        // (held back inside the window ⇒ empty this chunk, flushed later).
        let chunk =
            r#"{"id":"abc","choices":[{"index":0,"delta":{"content":"hi"},"finish_reason":null}]}"#;
        let out = redact_openai_sse_chunk(chunk, &mut r);
        let v: serde_json::Value = serde_json::from_str(&out).unwrap();
        assert_eq!(v["id"], "abc");
        assert_eq!(v["choices"][0]["index"], 0);
        assert!(v["choices"][0]["delta"]["content"].is_string());
        // Non-JSON payload passes through unchanged.
        assert_eq!(redact_openai_sse_chunk("[weird]", &mut r), "[weird]");
        // The tail chunk is valid JSON carrying the flushed text.
        let tail = openai_content_chunk("bye");
        let tv: serde_json::Value = serde_json::from_str(&tail).unwrap();
        assert_eq!(tv["choices"][0]["delta"]["content"], "bye");
    }

    #[test]
    fn ndjson_auth_handshake() {
        // well-formed matching frame
        assert!(ndjson_authenticate(
            r#"{"op":"auth","token":"s3cr3t"}"#,
            "s3cr3t"
        ));
        // wrong token / wrong op / missing token / not-json / non-auth op
        assert!(!ndjson_authenticate(
            r#"{"op":"auth","token":"nope"}"#,
            "s3cr3t"
        ));
        assert!(!ndjson_authenticate(
            r#"{"op":"infer","token":"s3cr3t"}"#,
            "s3cr3t"
        ));
        assert!(!ndjson_authenticate(r#"{"op":"auth"}"#, "s3cr3t"));
        assert!(!ndjson_authenticate("not json", "s3cr3t"));
        assert!(!ndjson_authenticate(r#"{"op":"health"}"#, "s3cr3t"));
    }

    #[test]
    fn chat_prompt_falls_back_to_newline_join_without_template() {
        // F-2026-086: no template ⇒ byte-identical to the original newline-join.
        let req = serde_json::json!({"messages": [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hi"}
        ]});
        assert_eq!(chat_prompt(&req, None), "You are helpful.\nHi");
    }

    #[test]
    fn chat_prompt_renders_chatml_when_template_present() {
        // A ChatML template ⇒ the prompt carries the model's real turn markers.
        let req = serde_json::json!({"messages": [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hi"}
        ]});
        let tmpl = "{% for m in messages %}<|im_start|>{{ m.role }}\n{{ m.content }}<|im_end|>\n{% endfor %}";
        let out = chat_prompt(&req, Some(tmpl));
        assert!(out.contains("<|im_start|>system\nYou are helpful.<|im_end|>\n"));
        assert!(out.contains("<|im_start|>user\nHi<|im_end|>\n"));
        assert!(out.ends_with("<|im_start|>assistant\n")); // generation prompt
    }

    #[test]
    fn chat_prompt_llama3_template_uses_header_markers() {
        let req = serde_json::json!({"messages": [{"role": "user", "content": "Hi"}]});
        let tmpl = "{{ '<|start_header_id|>' + message['role'] + '<|end_header_id|>' }}";
        let out = chat_prompt(&req, Some(tmpl));
        assert!(out.starts_with("<|begin_of_text|>"));
        assert!(out.contains("<|start_header_id|>user<|end_header_id|>\n\nHi<|eot_id|>"));
    }

    #[test]
    fn chat_prompt_unknown_template_falls_back() {
        // An exotic template we can't detect ⇒ newline-join, never a wrong render.
        let req = serde_json::json!({"messages": [{"role": "user", "content": "Hi"}]});
        assert_eq!(chat_prompt(&req, Some("{{ exotic }}")), "Hi");
    }

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

    // SDD-711 (F-2026-088): tool-aware chat-completion response shaping.

    #[test]
    fn shape_tool_completion_emits_tool_calls_for_an_advertised_call() {
        let specs = openai_tools_to_specs(&serde_json::json!([
            {"function": {"name": "upper", "description": "uppercase"}}
        ]));
        let (delta, final_obj) =
            shape_tool_completion("sure: [[tool:upper|hi]]", &specs, "chatcmpl-x", 7);
        let tc = &delta["choices"][0]["delta"]["tool_calls"][0];
        assert_eq!(tc["type"], "function");
        assert_eq!(tc["function"]["name"], "upper");
        assert_eq!(tc["function"]["arguments"], "hi");
        assert_eq!(final_obj["choices"][0]["finish_reason"], "tool_calls");
        assert_eq!(final_obj["usage"]["completion_tokens"], 7);
    }

    #[test]
    fn shape_tool_completion_falls_back_to_content_for_plain_output() {
        let specs = openai_tools_to_specs(&serde_json::json!([{"function": {"name": "upper"}}]));
        let (delta, final_obj) = shape_tool_completion("just a plain answer", &specs, "id", 3);
        assert_eq!(
            delta["choices"][0]["delta"]["content"],
            "just a plain answer"
        );
        assert!(delta["choices"][0]["delta"].get("tool_calls").is_none());
        assert_eq!(final_obj["choices"][0]["finish_reason"], "stop");
    }

    #[test]
    fn shape_tool_completion_ignores_a_call_to_an_unadvertised_tool() {
        // A model emitting a tool the caller never offered must NOT produce a
        // tool_calls response — it's treated as ordinary text.
        let specs = openai_tools_to_specs(&serde_json::json!([{"function": {"name": "upper"}}]));
        let (delta, final_obj) = shape_tool_completion("[[tool:rm_rf|/]]", &specs, "id", 4);
        assert!(delta["choices"][0]["delta"].get("tool_calls").is_none());
        assert_eq!(final_obj["choices"][0]["finish_reason"], "stop");
    }
}
