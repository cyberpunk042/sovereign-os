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

/// Bind a TCP listener and serve one thread per connection. Each connection is
/// an NDJSON stream: one request per line, one reply per line. Pure std — no
/// async runtime, honoring the workspace `unsafe_code = forbid` discipline.
fn run_tcp(server: &Arc<GatewayServer>, addr: &str) -> std::io::Result<()> {
    let listener = TcpListener::bind(addr)?;
    eprintln!(
        "sovereign-gatewayd: listening on {addr} (NDJSON; ops: infer/manifest/health/ledger)"
    );
    for stream in listener.incoming() {
        match stream {
            Ok(stream) => {
                let server = Arc::clone(server);
                std::thread::spawn(move || {
                    if let Err(e) = handle_conn(&server, stream) {
                        eprintln!("sovereign-gatewayd: connection ended: {e}");
                    }
                });
            }
            Err(e) => eprintln!("sovereign-gatewayd: accept failed: {e}"),
        }
    }
    Ok(())
}

fn handle_conn(server: &GatewayServer, stream: TcpStream) -> std::io::Result<()> {
    let peer = stream.peer_addr().ok();
    let reader = BufReader::new(stream.try_clone()?);
    let mut writer = stream;
    for line in reader.lines() {
        let line = line?;
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
    for stream in listener.incoming() {
        match stream {
            Ok(stream) => {
                let server = Arc::clone(server);
                std::thread::spawn(move || {
                    if let Err(e) = handle_http_conn(&server, stream) {
                        eprintln!("sovereign-gatewayd: http connection ended: {e}");
                    }
                });
            }
            Err(e) => eprintln!("sovereign-gatewayd: accept failed: {e}"),
        }
    }
    Ok(())
}

fn handle_http_conn(server: &GatewayServer, stream: TcpStream) -> std::io::Result<()> {
    let mut reader = BufReader::new(stream.try_clone()?);
    let mut writer = stream;

    // Request line: `METHOD PATH HTTP/1.1`.
    let mut request_line = String::new();
    if reader.read_line(&mut request_line)? == 0 {
        return Ok(()); // client closed before sending anything
    }
    let mut parts = request_line.split_whitespace();
    let method = parts.next().unwrap_or("").to_string();
    let path = parts.next().unwrap_or("/").to_string();

    // Headers until the blank line; the only one we act on is Content-Length.
    let mut content_length = 0usize;
    loop {
        let mut line = String::new();
        if reader.read_line(&mut line)? == 0 {
            break;
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

    // Body of exactly Content-Length bytes (0 for GETs).
    let mut body = vec![0u8; content_length];
    if content_length > 0 {
        reader.read_exact(&mut body)?;
    }
    let body = String::from_utf8_lossy(&body);

    let reply = http::respond(server, &method, &path, &body);
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
    writer.flush()?;
    Ok(())
}
