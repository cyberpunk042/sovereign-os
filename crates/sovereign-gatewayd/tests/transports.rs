//! End-to-end transport tests: spin the real `sovereign-gatewayd` binary on an
//! ephemeral port and talk to it over actual sockets. The unit tests cover the
//! pure serving core (`handle_line` / `http::respond`); these lock the socket
//! plumbing in `main.rs` that unit tests can't reach — request framing, the
//! NDJSON line loop, and the hand-rolled HTTP/1.1 parser.

use std::io::{BufRead, BufReader, Read, Write};
use std::net::{TcpListener, TcpStream};
use std::process::{Child, Command};
use std::sync::{Mutex, MutexGuard};
use std::time::{Duration, Instant};

/// Serialize the persistent-daemon tests. On a constrained CI runner, spinning
/// up many daemon processes (each with its own threads + cortex inference) in
/// parallel saturates resources and a connection can reset mid-test. Holding
/// this lock for each daemon's lifetime keeps at most one running at a time
/// within this binary. Poisoning is ignored so a panicking test can't cascade.
fn serial_guard() -> MutexGuard<'static, ()> {
    static SERIAL: Mutex<()> = Mutex::new(());
    SERIAL.lock().unwrap_or_else(|e| e.into_inner())
}

/// A spawned daemon on a free loopback port, killed on drop.
struct Daemon {
    child: Child,
    addr: String,
    /// Held for the daemon's lifetime to serialize daemon-spawning tests.
    _serial: MutexGuard<'static, ()>,
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
fn spawn(mode: &str) -> Daemon {
    spawn_with_env(mode, &[])
}

/// Like [`spawn`] but with extra environment variables (e.g. a low
/// `SOVEREIGN_GATEWAY_MAX_CONN` to exercise the connection cap).
#[allow(clippy::zombie_processes)]
fn spawn_with_env(mode: &str, extra_env: &[(&str, &str)]) -> Daemon {
    // Held across the retries and stored in the returned Daemon, so only one
    // daemon-spawning test runs at a time within this binary.
    let serial = serial_guard();
    for attempt in 0..5 {
        let addr = format!("127.0.0.1:{}", free_port());
        let mut cmd = Command::new(env!("CARGO_BIN_EXE_sovereign-gatewayd"));
        cmd.env("SOVEREIGN_GATEWAY_ADDR", &addr);
        for (k, v) in extra_env {
            cmd.env(k, v);
        }
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
                return Daemon {
                    child,
                    addr,
                    _serial: serial,
                };
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
fn tcp_caps_concurrent_connections() {
    // With the cap at 2, two held-open connections saturate it; the third is
    // accepted then closed immediately (back-pressure), so its read sees EOF.
    let d = spawn_with_env("", &[("SOVEREIGN_GATEWAY_MAX_CONN", "2")]);

    // Hold two connections open (NDJSON handlers block reading a line).
    let _c1 = connect_retry(&d.addr);
    let _c2 = connect_retry(&d.addr);
    // Let the daemon accept + count both before the third arrives.
    std::thread::sleep(Duration::from_millis(300));

    let mut c3 = connect_retry(&d.addr);
    c3.set_read_timeout(Some(Duration::from_secs(2))).unwrap();
    let mut buf = [0u8; 16];
    let n = c3.read(&mut buf).unwrap_or(0);
    assert_eq!(
        n, 0,
        "a connection over the cap should be closed immediately"
    );

    // Once a slot frees, the daemon serves again.
    drop(_c1);
    std::thread::sleep(Duration::from_millis(300));
    assert_eq!(ndjson_infer_kind(&d.addr), "decision");
}

/// Send one infer over NDJSON and return the reply's `kind`.
fn ndjson_infer_kind(addr: &str) -> String {
    let stream = connect_retry(addr);
    let mut reader = BufReader::new(stream.try_clone().unwrap());
    let mut writer = stream;
    let env = format!("{{\"op\":\"infer\",\"request\":{}}}", demo_request_json());
    writeln!(writer, "{env}").unwrap();
    writer.flush().unwrap();
    let mut line = String::new();
    reader.read_line(&mut line).unwrap();
    let v: serde_json::Value = serde_json::from_str(&line).unwrap();
    v["kind"].as_str().unwrap_or("").to_string()
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
// selftest mode
// ---------------------------------------------------------------------------

#[test]
fn selftest_runs_the_demo_session() {
    let out = Command::new(env!("CARGO_BIN_EXE_sovereign-gatewayd"))
        .arg("--selftest")
        .output()
        .expect("run --selftest");
    // Exit 0 only if the never-cloud-spill invariant held through the session.
    assert!(out.status.success(), "exit: {:?}", out.status);
    let s = String::from_utf8_lossy(&out.stdout);
    assert!(s.contains("\"kind\":\"decision\""), "no decisions:\n{s}");
    assert!(s.contains("\"kind\":\"ledger\""), "no ledger:\n{s}");
    assert!(s.contains("\"kind\":\"health\""), "no health:\n{s}");
}

// ---------------------------------------------------------------------------
// stdio transport (MCP / claude-code shape)
// ---------------------------------------------------------------------------

#[test]
fn stdio_transport_handles_ndjson() {
    use std::process::Stdio;

    // --stdio reads NDJSON on stdin and replies on stdout; no socket to poll, so
    // spawn directly with piped stdio rather than via `spawn()`.
    let mut child = Command::new(env!("CARGO_BIN_EXE_sovereign-gatewayd"))
        .arg("--stdio")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .spawn()
        .expect("spawn --stdio");

    let line = format!("{{\"op\":\"infer\",\"request\":{}}}\n", demo_request_json());
    child
        .stdin
        .take()
        .unwrap()
        .write_all(line.as_bytes())
        .unwrap();
    // stdin dropped → EOF → the read loop ends and the process exits.

    let out = child.wait_with_output().expect("wait --stdio");
    assert!(out.status.success());
    let stdout = String::from_utf8_lossy(&out.stdout);
    let reply = stdout.lines().next().expect("a reply line");
    let v: serde_json::Value = serde_json::from_str(reply).unwrap();
    assert_eq!(v["kind"], "decision");
    assert_eq!(v["decision"]["placement"]["spilled_to_cloud"], false);
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
fn http_infer_runs_engine_and_messages_speaks_anthropic() {
    let d = spawn("--http");

    // /v1/infer is the routing DECISION (runs the engine).
    let (status, body) = http_request(&d.addr, "POST", "/v1/infer", &demo_request_json());
    assert!(status.starts_with("HTTP/1.1 200"), "status: {status}");
    let v: serde_json::Value = serde_json::from_str(&body).unwrap();
    assert_eq!(v["kind"], "decision");

    // /v1/messages is the Anthropic Messages API; no model loaded here → an honest
    // Anthropic error envelope (never a fabricated message). Both non-stream…
    let anthropic = serde_json::json!({
        "model": "claude-3-5-sonnet", "max_tokens": 16,
        "messages": [{"role": "user", "content": "hi"}],
    })
    .to_string();
    let (astatus, abody) = http_request(&d.addr, "POST", "/v1/messages", &anthropic);
    assert!(astatus.starts_with("HTTP/1.1 503"), "status: {astatus}");
    assert_eq!(
        serde_json::from_str::<serde_json::Value>(&abody).unwrap()["type"],
        "error"
    );
    // …and the streaming path fail the same way (no model → Anthropic error, not SSE).
    let streamed = serde_json::json!({
        "model": "claude-3-5-sonnet", "max_tokens": 16, "stream": true,
        "messages": [{"role": "user", "content": "hi"}],
    })
    .to_string();
    let (sstatus, sbody) = http_request(&d.addr, "POST", "/v1/messages", &streamed);
    assert!(sstatus.starts_with("HTTP/1.1 503"), "status: {sstatus}");
    assert_eq!(
        serde_json::from_str::<serde_json::Value>(&sbody).unwrap()["type"],
        "error"
    );

    // /metrics reflects the one engine request (/v1/messages didn't touch it).
    let (mstatus, mbody) = http_request(&d.addr, "GET", "/metrics", "");
    assert!(mstatus.starts_with("HTTP/1.1 200"), "status: {mstatus}");
    assert!(
        mbody.contains("sovereign_gateway_requests_total 1"),
        "metrics:\n{mbody}"
    );
    assert!(mbody.contains("sovereign_gateway_never_cloud_spill_holds 1"));
}

/// A mock GPU serve-process speaking OpenAI `/v1/chat/completions` SSE over
/// `Transfer-Encoding: chunked` (as llama-server / vLLM do). Returns its address.
fn spawn_mock_openai_sse_upstream() -> String {
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let addr = listener.local_addr().unwrap().to_string();
    std::thread::spawn(move || {
        // Serve a couple of streamed requests (register probe is non-streaming; the
        // real one streams), so accept in a loop.
        for conn in listener.incoming() {
            let Ok(mut sock) = conn else { break };
            let mut buf = [0u8; 4096];
            let _ = sock.read(&mut buf);
            // one SSE frame per chunk, split mid-stream, then [DONE]
            let frames = [
                r#"data: {"choices":[{"delta":{"content":"Hello"}}]}"#,
                r#"data: {"choices":[{"delta":{"content":" from the GPU"},"finish_reason":"stop"}]}"#,
                "data: [DONE]",
            ];
            let mut body = String::new();
            for f in frames {
                let frame = format!("{f}\n\n");
                body.push_str(&format!("{:x}\r\n{}\r\n", frame.len(), frame));
            }
            body.push_str("0\r\n\r\n"); // terminal chunk
            let resp = format!(
                "HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nTransfer-Encoding: chunked\r\nConnection: close\r\n\r\n{body}"
            );
            let _ = sock.write_all(resp.as_bytes());
        }
    });
    addr
}

#[test]
fn http_streams_a_proxy_backend_as_anthropic_sse() {
    // Increment 2b: a `stream:true` request for a GPU proxy model transcodes the
    // upstream's OpenAI SSE into the Anthropic event sequence, rather than the old
    // honest-error gate. Register a mock OpenAI upstream, then stream through it.
    let up = spawn_mock_openai_sse_upstream();
    let d = spawn("--http");

    let reg = serde_json::json!({
        "id": "gpu-stream", "endpoint": up, "device": "logic",
        "vram_gb": 18.0, "dialect": "openai",
    })
    .to_string();
    let (rstatus, _) = http_request(&d.addr, "POST", "/v1/models/register", &reg);
    assert!(
        rstatus.starts_with("HTTP/1.1 200"),
        "register status: {rstatus}"
    );

    let streamed = serde_json::json!({
        "model": "gpu-stream", "max_tokens": 32, "stream": true,
        "messages": [{"role": "user", "content": "hi"}],
    })
    .to_string();
    let (sstatus, sbody) = http_request(&d.addr, "POST", "/v1/messages", &streamed);
    assert!(
        sstatus.starts_with("HTTP/1.1 200"),
        "stream status: {sstatus}"
    );
    // the Anthropic event envelope, transcoded from the OpenAI chunks
    assert!(sbody.contains("event: message_start"), "sse:\n{sbody}");
    assert!(
        sbody.contains("event: content_block_delta"),
        "sse:\n{sbody}"
    );
    assert!(
        sbody.contains("\"text\":\"Hello\""),
        "first delta transcoded; sse:\n{sbody}"
    );
    assert!(
        sbody.contains("\"text\":\" from the GPU\""),
        "second delta; sse:\n{sbody}"
    );
    assert!(sbody.contains("event: message_stop"), "sse:\n{sbody}");
    // finish_reason:stop → anthropic end_turn
    assert!(
        sbody.contains("\"stop_reason\":\"end_turn\""),
        "sse:\n{sbody}"
    );
}

#[test]
fn http_streams_a_proxy_backend_through_the_openai_shim() {
    // The Code Console chat rides the OpenAI shim (scripts/inference/prompt.py). A
    // proxy model there relays the upstream's OpenAI SSE verbatim (UX loop) — it must
    // reach the GPU backend, not silently fall back to the primary.
    let up = spawn_mock_openai_sse_upstream();
    let d = spawn("--http");

    let reg = serde_json::json!({
        "id": "gpu-oai", "endpoint": up, "device": "logic", "vram_gb": 18.0, "dialect": "openai",
    })
    .to_string();
    let (rstatus, _) = http_request(&d.addr, "POST", "/v1/models/register", &reg);
    assert!(rstatus.starts_with("HTTP/1.1 200"), "register: {rstatus}");

    let streamed = serde_json::json!({
        "model": "gpu-oai", "max_tokens": 32, "stream": true,
        "messages": [{"role": "user", "content": "hi"}],
    })
    .to_string();
    let (sstatus, sbody) = http_request(&d.addr, "POST", "/v1/chat/completions", &streamed);
    assert!(sstatus.starts_with("HTTP/1.1 200"), "stream: {sstatus}");
    // the upstream OpenAI SSE relayed verbatim — bare `data:` chunks, not Anthropic events
    assert!(
        sbody.contains("\"content\":\"Hello\""),
        "relayed openai chunk; sse:\n{sbody}"
    );
    assert!(
        sbody.contains("\"content\":\" from the GPU\""),
        "sse:\n{sbody}"
    );
    assert!(sbody.contains("[DONE]"), "sse:\n{sbody}");
}

#[test]
fn http_survives_a_malicious_upstream_chunk_size() {
    // F1/F6: a bogus giant chunk-size line must NOT abort the daemon on a huge
    // allocation; the stream ends gracefully with an honest `error` event, and the
    // daemon keeps serving.
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let up = listener.local_addr().unwrap().to_string();
    std::thread::spawn(move || {
        if let Ok((mut sock, _)) = listener.accept() {
            let mut buf = [0u8; 2048];
            let _ = sock.read(&mut buf);
            // 200 + chunked, then a 16-hex-digit chunk size (~18 EB) a naive
            // `vec![0u8; n]` would abort on. Then close.
            let _ = sock.write_all(b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nTransfer-Encoding: chunked\r\nConnection: close\r\n\r\nffffffffffffffff\r\n");
        }
    });
    let d = spawn("--http");
    let reg =
        serde_json::json!({ "id": "bad-gpu", "endpoint": up, "dialect": "openai" }).to_string();
    let (rs, _) = http_request(&d.addr, "POST", "/v1/models/register", &reg);
    assert!(rs.starts_with("HTTP/1.1 200"), "register: {rs}");

    let streamed = serde_json::json!({
        "model": "bad-gpu", "max_tokens": 16, "stream": true,
        "messages": [{"role": "user", "content": "hi"}],
    })
    .to_string();
    let (ss, sb) = http_request(&d.addr, "POST", "/v1/messages", &streamed);
    assert!(ss.starts_with("HTTP/1.1 200"), "stream status: {ss}");
    assert!(
        sb.contains("event: error"),
        "a truncated stream must emit an honest error; sse:\n{sb}"
    );
    assert!(sb.contains("event: message_stop"), "sse:\n{sb}");
    // the daemon is still alive (it did not abort) — it serves a subsequent request
    let (hs, _) = http_request(&d.addr, "GET", "/health", "");
    assert!(
        hs.starts_with("HTTP/1.1 200"),
        "daemon must survive the bad upstream: {hs}"
    );
}

#[test]
fn http_rate_limits_generation() {
    // A tiny bucket (capacity 2, no refill) admits 2 generation requests then 429s the
    // 3rd — proving admission control (sovereign-rate-limit) is wired in front of
    // generate. No model is loaded, so an admitted request is a 503; the point is that
    // the 3rd is refused BEFORE any work, and the refusal is tallied on /metrics.
    let d = spawn_with_env(
        "--http",
        &[
            ("SOVEREIGN_GATEWAY_RATE_CAPACITY", "2"),
            ("SOVEREIGN_GATEWAY_RATE_PER_SEC", "0"),
        ],
    );
    let body = serde_json::json!({
        "model": "x", "max_tokens": 4, "messages": [{"role": "user", "content": "hi"}],
    })
    .to_string();
    let (s1, _) = http_request(&d.addr, "POST", "/v1/messages", &body);
    let (s2, _) = http_request(&d.addr, "POST", "/v1/messages", &body);
    let (s3, b3) = http_request(&d.addr, "POST", "/v1/messages", &body);
    assert!(
        s1.starts_with("HTTP/1.1 503"),
        "1st admitted (503 no model): {s1}"
    );
    assert!(s2.starts_with("HTTP/1.1 503"), "2nd admitted: {s2}");
    assert!(
        s3.starts_with("HTTP/1.1 429"),
        "3rd must be rate-limited: {s3}"
    );
    assert_eq!(
        serde_json::from_str::<serde_json::Value>(&b3).unwrap()["error"]["type"],
        "rate_limit_error"
    );
    let (_, m) = http_request(&d.addr, "GET", "/metrics", "");
    assert!(
        m.contains("sovereign_gateway_rate_limited_total 1"),
        "metrics:\n{m}"
    );
}

#[test]
fn http_simple_runs_engine_from_minimal_input_over_socket() {
    let d = spawn("--http");
    let reqs = sovereign_cortex::demo_requests();
    let req = &reqs[0];
    // The client sends only the task axes + a quality dial.
    let body = serde_json::json!({ "axes": req.axes, "expected_quality": 0.9 }).to_string();
    let (status, rbody) = http_request(&d.addr, "POST", "/v1/simple", &body);
    assert!(status.starts_with("HTTP/1.1 200"), "status: {status}");
    let v: serde_json::Value = serde_json::from_str(&rbody).unwrap();
    assert_eq!(v["kind"], "decision");
    assert_eq!(v["decision"]["placement"]["spilled_to_cloud"], false);
}

#[test]
fn http_explain_returns_rationale_over_socket() {
    let d = spawn("--http");
    let (status, body) = http_request(&d.addr, "POST", "/v1/explain", &demo_request_json());
    assert!(status.starts_with("HTTP/1.1 200"), "status: {status}");
    let v: serde_json::Value = serde_json::from_str(&body).unwrap();
    assert_eq!(v["kind"], "explanation");
    assert!(v["explanation"].as_str().unwrap().contains("Routed to"));
}

#[test]
fn http_deliberate_returns_best_of_n_over_socket() {
    let d = spawn("--http");
    let reqs = sovereign_cortex::demo_requests();
    let req = &reqs[0];
    let body = serde_json::json!({
        "request": req,
        "candidates": [req.reward.clone(), req.reward.clone()],
        "tier": "normal",
    })
    .to_string();
    let (status, rbody) = http_request(&d.addr, "POST", "/v1/deliberate", &body);
    assert!(status.starts_with("HTTP/1.1 200"), "status: {status}");
    let v: serde_json::Value = serde_json::from_str(&rbody).unwrap();
    assert_eq!(v["kind"], "deliberation");
    assert_eq!(v["deliberation"]["candidates_considered"], 2);
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
fn http_oversized_header_line_is_431() {
    // A header line over the 8 KiB cap with no newline must be refused with 431,
    // not buffered, and the daemon must stay responsive. The daemon refuses
    // before draining the input, so closing with unread bytes can surface as a
    // reset — read defensively (the 431 line still arrives first).
    let d = spawn("--http");
    let mut stream = connect_retry(&d.addr);
    let mut req = b"GET /health HTTP/1.1\r\nX-Big: ".to_vec();
    req.extend(std::iter::repeat_n(b'a', 9_000));
    stream.write_all(&req).unwrap();
    stream.shutdown(std::net::Shutdown::Write).unwrap();

    let mut raw = Vec::new();
    let mut buf = [0u8; 1024];
    loop {
        match stream.read(&mut buf) {
            Ok(0) => break,
            Ok(n) => raw.extend_from_slice(&buf[..n]),
            Err(_) => break, // a trailing reset after the response is fine
        }
    }
    let raw = String::from_utf8_lossy(&raw);
    assert!(
        raw.starts_with("HTTP/1.1 431"),
        "expected 431, got: {:?}",
        raw.lines().next()
    );

    let (status, _) = http_request(&d.addr, "GET", "/health", "");
    assert!(status.starts_with("HTTP/1.1 200"), "status: {status}");
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
