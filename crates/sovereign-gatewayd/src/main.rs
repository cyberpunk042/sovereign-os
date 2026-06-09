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
//! `POST /v1/messages|/v1/infer|/mcp`) — see [`sovereign_gatewayd::http`].
//!
//! Wire protocol (one JSON object per line):
//!
//! ```text
//! {"op":"infer","request":{…cortex request…}}   -> {"kind":"decision",…}
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

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let server = Arc::new(GatewayServer::new());

    if args.iter().any(|a| a == "--selftest") {
        selftest(&server);
        return;
    }

    if args.iter().any(|a| a == "--stdio") {
        run_stdio(&server);
        return;
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
        std::thread::spawn(move || {
            let _guard = guard; // decrements the counter on thread exit
            if let Err(e) = handle(&server, stream) {
                eprintln!("sovereign-gatewayd: connection ended: {e}");
            }
        });
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
         (GET /health /manifest /admin/ledger /metrics; POST /v1/messages /v1/infer /mcp)"
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
    let reply = if content_length > http::MAX_BODY_BYTES {
        http::payload_too_large()
    } else {
        // Body of exactly Content-Length bytes (0 for GETs).
        let mut body = vec![0u8; content_length];
        if content_length > 0 {
            reader.read_exact(&mut body)?;
        }
        let body = String::from_utf8_lossy(&body);
        http::respond(server, &method, &path, &body)
    };
    write_http(&mut writer, &reply)
}
