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
//! POST /v1/messages    -> {"kind":"decision", …}   Anthropic-path bind (surface 1)
//! POST /v1/infer       -> {"kind":"decision", …}   raw engine alias
//! POST /mcp            -> {"kind":"decision", …}   MCP-bridge bind (surface 3)
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

use crate::{GatewayRequest, GatewayResponse, GatewayServer};
use sovereign_cortex::CortexRequest;

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
        405 => "Method Not Allowed",
        422 => "Unprocessable Entity",
        _ => "Internal Server Error",
    }
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

        ("POST", "/v1/messages") | ("POST", "/v1/infer") | ("POST", "/mcp") => {
            match serde_json::from_str::<CortexRequest>(body) {
                Ok(request) => {
                    let resp = server.handle(GatewayRequest::Infer {
                        request: Box::new(request),
                    });
                    // An engine refusal is a request-level problem (422); a
                    // genuine decision is 200.
                    let status = match resp {
                        GatewayResponse::Error { .. } => 422,
                        _ => 200,
                    };
                    render(status, &resp)
                }
                Err(e) => err(400, format!("invalid request body: {e}")),
            }
        }

        // A known resource with the wrong verb is 405; anything else is 404.
        (_, "/health") | (_, "/manifest") | (_, "/admin/ledger") | (_, "/metrics") => {
            err(405, format!("method {method} not allowed on {route}"))
        }
        (_, "/v1/messages") | (_, "/v1/infer") | (_, "/mcp") => {
            err(405, format!("method {method} not allowed on {route}"))
        }
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
fn err(status: u16, message: String) -> HttpReply {
    render(status, &GatewayResponse::Error { message })
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
    fn post_messages_runs_the_engine() {
        let s = srv();
        let body = serde_json::to_string(&demo_requests()[0]).unwrap();
        let r = respond(&s, "POST", "/v1/messages", &body);
        assert_eq!(r.status, 200);
        let v = body_of(&r);
        assert_eq!(v["kind"], "decision");
        assert!(v["decision"]["route"]["role"].is_string());
        // The engine actually ran: the ledger advanced + nothing spilled.
        let led = body_of(&respond(&s, "GET", "/admin/ledger", ""));
        assert_eq!(led["ledger"]["total_requests"], 1);
        assert_eq!(led["ledger"]["cloud_spills"], 0);
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
        let r = respond(&srv(), "POST", "/v1/messages", "{not json");
        assert_eq!(r.status, 400);
        assert_eq!(body_of(&r)["kind"], "error");
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
    fn metrics_is_prometheus_text_and_reflects_the_engine() {
        let s = srv();
        let body = serde_json::to_string(&demo_requests()[0]).unwrap();
        let _ = respond(&s, "POST", "/v1/messages", &body); // one committed decision

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
        for code in [200, 400, 404, 405, 422] {
            assert_ne!(reason(code), "Internal Server Error");
        }
    }
}
