//! End-to-end transport tests: spin the real `sovereign-gatewayd` binary on an
//! ephemeral port and talk to it over actual sockets. The unit tests cover the
//! pure serving core (`handle_line` / `http::respond`); these lock the socket
//! plumbing in `main.rs` that unit tests can't reach — request framing, the
//! NDJSON line loop, and the hand-rolled HTTP/1.1 parser.

use std::io::{BufRead, BufReader, Read, Write};
use std::net::{TcpListener, TcpStream};
use std::process::{Child, Command};
use std::time::{Duration, Instant};

/// A spawned daemon on a free loopback port, killed on drop.
struct Daemon {
    child: Child,
    addr: String,
}

impl Drop for Daemon {
    fn drop(&mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

/// Grab a free loopback port by binding :0 and immediately dropping it.
fn free_port() -> u16 {
    TcpListener::bind("127.0.0.1:0")
        .unwrap()
        .local_addr()
        .unwrap()
        .port()
}

/// Spawn the binary in the given mode (`""` for NDJSON TCP, `"--http"`) and
/// wait until the port accepts connections.
///
/// `free_port()` drops its listener before the daemon binds, so under heavy
/// parallel test load another process can grab the port in that window and the
/// daemon exits. We detect the early exit (`try_wait`) and retry on a fresh
/// port, so the test is robust to that race rather than flaking.
// The child is reaped in `Daemon::drop` (kill + wait); clippy can't see across
// the returned struct's Drop, so the zombie-processes lint is a false positive.
#[allow(clippy::zombie_processes)]
fn spawn(mode: &str) -> Daemon {
    for attempt in 0..5 {
        let addr = format!("127.0.0.1:{}", free_port());
        let mut cmd = Command::new(env!("CARGO_BIN_EXE_sovereign-gatewayd"));
        cmd.env("SOVEREIGN_GATEWAY_ADDR", &addr);
        if !mode.is_empty() {
            cmd.arg(mode);
        }
        let mut child = cmd.spawn().expect("spawn sovereign-gatewayd");

        // Poll until the listener is up (bounded, so a broken binary fails fast).
        let deadline = Instant::now() + Duration::from_secs(10);
        loop {
            // Child exited during startup (lost the port race) → retry afresh.
            if matches!(child.try_wait(), Ok(Some(_))) {
                break;
            }
            if TcpStream::connect(&addr).is_ok() {
                return Daemon { child, addr };
            }
            if Instant::now() >= deadline {
                let _ = child.kill();
                let _ = child.wait();
                break;
            }
            std::thread::sleep(Duration::from_millis(50));
        }
        eprintln!("spawn attempt {attempt} on {addr} did not come up; retrying");
    }
    panic!("daemon did not start listening after 5 attempts");
}

/// One demo cortex request as a JSON string (the binary's own example payload).
fn demo_request_json() -> String {
    serde_json::to_string(&sovereign_cortex::demo_requests()[0]).unwrap()
}

/// Connect with a few retries. Under heavy parallel test load a transient
/// connect can fail even though the daemon is up and listening; a bare
/// `connect().unwrap()` would then flake the test.
fn connect_retry(addr: &str) -> TcpStream {
    for _ in 0..40 {
        if let Ok(s) = TcpStream::connect(addr) {
            return s;
        }
        std::thread::sleep(Duration::from_millis(25));
    }
    TcpStream::connect(addr).expect("connect to daemon after retries")
}

// ---------------------------------------------------------------------------
// NDJSON TCP transport
// ---------------------------------------------------------------------------

#[test]
fn ndjson_tcp_infer_then_ledger_across_one_connection() {
    let d = spawn("");
    let stream = connect_retry(&d.addr);
    let mut reader = BufReader::new(stream.try_clone().unwrap());
    let mut writer = stream;

    // infer
    let env = format!("{{\"op\":\"infer\",\"request\":{}}}", demo_request_json());
    writeln!(writer, "{env}").unwrap();
    writer.flush().unwrap();
    let mut line = String::new();
    reader.read_line(&mut line).unwrap();
    let v: serde_json::Value = serde_json::from_str(&line).unwrap();
    assert_eq!(v["kind"], "decision");
    assert_eq!(v["decision"]["placement"]["spilled_to_cloud"], false);

    // ledger reflects the inference on the same connection
    writeln!(writer, "{{\"op\":\"ledger\"}}").unwrap();
    writer.flush().unwrap();
    let mut line2 = String::new();
    reader.read_line(&mut line2).unwrap();
    let l: serde_json::Value = serde_json::from_str(&line2).unwrap();
    assert_eq!(l["ledger"]["total_requests"], 1);
}

#[test]
fn ndjson_tcp_oversized_line_is_refused() {
    // A single line larger than the cap with no newline must be refused, not
    // buffered unboundedly (the same DoS class as the HTTP body cap).
    let d = spawn("");
    let mut stream = connect_retry(&d.addr);
    let huge = "x".repeat((1 << 20) + 16);
    stream.write_all(huge.as_bytes()).unwrap();
    stream.shutdown(std::net::Shutdown::Write).unwrap();
    let mut raw = String::new();
    stream.read_to_string(&mut raw).unwrap();
    assert!(
        raw.contains("exceeds") && raw.contains("limit"),
        "expected an over-limit error, got: {raw}"
    );
}

#[test]
fn ndjson_tcp_malformed_line_yields_error_not_drop() {
    let d = spawn("");
    let stream = connect_retry(&d.addr);
    let mut reader = BufReader::new(stream.try_clone().unwrap());
    let mut writer = stream;
    writeln!(writer, "this is not json").unwrap();
    writer.flush().unwrap();
    let mut line = String::new();
    reader.read_line(&mut line).unwrap();
    let v: serde_json::Value = serde_json::from_str(&line).unwrap();
    assert_eq!(v["kind"], "error");
}

// ---------------------------------------------------------------------------
// HTTP transport
// ---------------------------------------------------------------------------

/// Minimal HTTP/1.1 client: send one request, read the whole response, split
/// head/body. Returns (status_line, body).
fn http_request(addr: &str, method: &str, path: &str, body: &str) -> (String, String) {
    let req = format!(
        "{method} {path} HTTP/1.1\r\nHost: localhost\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
        body.len()
    );
    let mut stream = connect_retry(addr);
    stream.write_all(req.as_bytes()).unwrap();
    stream.flush().unwrap();
    let mut raw = String::new();
    stream.read_to_string(&mut raw).unwrap();
    let (head, body) = raw.split_once("\r\n\r\n").unwrap_or((raw.as_str(), ""));
    let status = head.lines().next().unwrap_or("").to_string();
    (status, body.to_string())
}

#[test]
fn http_health_get_is_200_invariant_holds() {
    let d = spawn("--http");
    let (status, body) = http_request(&d.addr, "GET", "/health", "");
    assert!(status.starts_with("HTTP/1.1 200"), "status: {status}");
    let v: serde_json::Value = serde_json::from_str(&body).unwrap();
    assert_eq!(v["health"]["never_cloud_spill_holds"], true);
}

#[test]
fn http_post_messages_runs_engine_and_metrics_reflect_it() {
    let d = spawn("--http");

    let (status, body) = http_request(&d.addr, "POST", "/v1/messages", &demo_request_json());
    assert!(status.starts_with("HTTP/1.1 200"), "status: {status}");
    let v: serde_json::Value = serde_json::from_str(&body).unwrap();
    assert_eq!(v["kind"], "decision");

    // /metrics is Prometheus text and shows the request we just made.
    let (mstatus, mbody) = http_request(&d.addr, "GET", "/metrics", "");
    assert!(mstatus.starts_with("HTTP/1.1 200"), "status: {mstatus}");
    assert!(
        mbody.contains("sovereign_gateway_requests_total 1"),
        "metrics:\n{mbody}"
    );
    assert!(mbody.contains("sovereign_gateway_never_cloud_spill_holds 1"));
}

#[test]
fn http_unknown_route_is_404_and_bad_body_is_400() {
    let d = spawn("--http");
    let (s404, _) = http_request(&d.addr, "GET", "/nope", "");
    assert!(s404.starts_with("HTTP/1.1 404"), "status: {s404}");
    let (s400, _) = http_request(&d.addr, "POST", "/v1/messages", "{not json");
    assert!(s400.starts_with("HTTP/1.1 400"), "status: {s400}");
}

#[test]
fn http_oversized_content_length_is_413_without_allocating() {
    // Claim a 4 GiB body but send no payload: the daemon must refuse with 413
    // before reading/allocating, then still be responsive afterwards.
    let d = spawn("--http");
    let req = "POST /v1/messages HTTP/1.1\r\nHost: x\r\n\
               Content-Length: 4294967296\r\nConnection: close\r\n\r\n";
    let mut stream = connect_retry(&d.addr);
    stream.write_all(req.as_bytes()).unwrap();
    stream.flush().unwrap();
    let mut raw = String::new();
    stream.read_to_string(&mut raw).unwrap();
    assert!(
        raw.lines().next().unwrap_or("").starts_with("HTTP/1.1 413"),
        "expected 413, got: {}",
        raw.lines().next().unwrap_or("")
    );

    // The daemon survived the oversized claim — a normal request still works.
    let (status, _) = http_request(&d.addr, "GET", "/health", "");
    assert!(status.starts_with("HTTP/1.1 200"), "status: {status}");
}
