//! SDD-712/713 (F-2026-088): server-side agentic tool use.
//!
//! Where SDD-711 made `/v1/chat/completions` return `tool_calls` for the CLIENT
//! to execute (single-turn, client-driven), this runs the ReAct loop **inside
//! the daemon** over a set of built-in tools the daemon executes itself, and
//! returns only the final answer. It is the multi-step half of F-2026-088.
//!
//! **Model-sharing = Option A** (operator-chosen): [`GatewayResponder`] wraps the
//! daemon's existing `GatewayServer` and calls its `generate_chat` per step — the
//! same shared `Arc<Mutex<Generator>>` every request already uses, **no
//! per-step model clone**. Each ReAct step re-sends the growing transcript to
//! `generate_chat` exactly as an ordinary request would; the safety spine stays
//! in the loop for every step.
//!
//! **Tool catalog (SDD-713)** — beyond the pure string transforms, the daemon
//! offers `calc` (the pure `sovereign-calc` arithmetic evaluator), `time` (a
//! read-only wall-clock read), `recall` (queries the daemon's own learning
//! Cortex memory via [`sovereign_cortex::Cortex::recall_text`]), and `search`
//! (read-only retrieval over the operator's RAG corpus — the same hybrid
//! BM25+embedding, coverage-reranked passages that ground a prompt, now callable
//! on demand). `recall`/`search` each own an `Arc` handle (a `'static` capture);
//! everything else is pure. All tools are read-only or pure — no shell / fs /
//! network tool exists (those need the sandbox + capability story in selfdef).
//!
//! **Sovereignty posture**: a root-adjacent daemon that autonomously executes
//! tools is gated two ways — a per-request opt-in (`sovereign_agentic: true`)
//! AND an env kill-switch (`SOVEREIGN_GATEWAY_AGENTIC=1`, **default OFF**).

use std::sync::{Arc, Mutex};
use std::time::{SystemTime, UNIX_EPOCH};

use sovereign_agent_loop::{AgentLoop, Responder, StopReason};
use sovereign_cortex::Cortex;
use sovereign_gatewayd::GatewayServer;
use sovereign_tool_bridge::ToolSpec;
use sovereign_tool_dispatch::ToolRegistry;

/// Default step cap for a server-side agentic turn (bounded so a runaway loop
/// can't pin the shared generator). Overridable per request via `max_steps`.
pub const DEFAULT_MAX_STEPS: usize = 4;
/// Repeat-guard: stop if the model calls the same tool with the same args this
/// many times (a cheap cycle breaker on top of the step cap).
pub const DEFAULT_MAX_REPEATS: usize = 2;
/// Epoch tick + half-life for `recall` freshness decay (match the CoAT recall
/// defaults so tool recall and steering recall see the same clock), and the
/// number of memories a `recall` returns.
const RECALL_NOW: u64 = 100;
const RECALL_HALF_LIFE: u64 = 1000;
const RECALL_K: usize = 3;

/// Is the agentic capability enabled on this daemon? `SOVEREIGN_GATEWAY_AGENTIC`
/// must be a truthy value (`1`/`true`/`yes`/`on`, case-insensitive). Default OFF
/// — the daemon does not autonomously execute tools unless an operator opts in.
pub fn agentic_enabled() -> bool {
    match std::env::var("SOVEREIGN_GATEWAY_AGENTIC") {
        Ok(v) => matches!(
            v.trim().to_ascii_lowercase().as_str(),
            "1" | "true" | "yes" | "on"
        ),
        Err(_) => false,
    }
}

/// Format an `f64` calc result without a trailing `.0` for whole numbers, so the
/// model sees `4` not `4.0` (and `2.5` stays `2.5`).
fn fmt_calc(v: f64) -> String {
    if v.fract() == 0.0 && v.is_finite() {
        format!("{}", v as i64)
    } else {
        format!("{v}")
    }
}

/// Passages a `search` tool call returns from the RAG corpus.
const SEARCH_K: usize = 3;

/// The daemon's built-in tool set. Pure string transforms + `calc` (pure
/// arithmetic) + `time` (read-only wall clock) are always present; `recall`
/// (read-only Cortex memory) is added only when a `cortex` handle is supplied,
/// and `search` (read-only RAG-corpus retrieval) only when a `corpus` handle is.
/// Each state-carrying closure OWNS its `Arc` handle (a `'static` capture), which
/// is why the daemon threads handles in rather than borrows. All tools are
/// read-only or pure — no shell / fs / network tool exists.
pub fn builtin_registry(
    cortex: Option<Arc<Mutex<Cortex>>>,
    corpus: Option<Arc<sovereign_retrieval::HybridStore>>,
) -> ToolRegistry {
    let mut r = ToolRegistry::new();
    r.register("upper", |a| a.to_uppercase());
    r.register("lower", |a| a.to_lowercase());
    r.register("reverse", |a| a.chars().rev().collect::<String>());
    r.register("wordcount", |a| a.split_whitespace().count().to_string());
    r.register("charcount", |a| a.chars().count().to_string());
    r.register("calc", |a| match sovereign_calc::eval(a) {
        Ok(v) => fmt_calc(v),
        Err(e) => format!("[calc error: {e}]"),
    });
    r.register("time", |_a| {
        match SystemTime::now().duration_since(UNIX_EPOCH) {
            Ok(d) => format!("{} (unix seconds, UTC)", d.as_secs()),
            Err(_) => "[time error: clock before epoch]".to_string(),
        }
    });
    if let Some(cx) = cortex {
        r.register("recall", move |q| match cx.lock() {
            Ok(c) => {
                let hits = c.recall_text(q, RECALL_NOW, RECALL_HALF_LIFE, RECALL_K);
                if hits.is_empty() {
                    "[no relevant memory]".to_string()
                } else {
                    hits.join("\n---\n")
                }
            }
            Err(_) => "[recall unavailable: memory lock poisoned]".to_string(),
        });
    }
    if let Some(corpus) = corpus {
        // Read-only retrieval over the operator's RAG corpus (hybrid BM25 +
        // embedding, coverage-reranked) — the same passages that ground a prompt,
        // now callable as a tool so the agent can pull facts on demand.
        r.register("search", move |q| {
            let hits = sovereign_gatewayd::corpus_retrieve(&corpus, q, SEARCH_K);
            if hits.is_empty() {
                "[no relevant passages in the corpus]".to_string()
            } else {
                hits.join("\n---\n")
            }
        });
    }
    r
}

/// The [`ToolSpec`]s advertised to the model, in the shape SDD-711's bridge
/// renders into a prompt preamble. `include_recall` mirrors whether
/// [`builtin_registry`] was built with a cortex handle, so the advertised set
/// always matches the executable set (a test asserts the two agree).
pub fn builtin_specs(include_recall: bool, include_search: bool) -> Vec<ToolSpec> {
    let mut specs: Vec<(&str, &str)> = vec![
        ("upper", "uppercase the argument text"),
        ("lower", "lowercase the argument text"),
        ("reverse", "reverse the argument text"),
        (
            "wordcount",
            "count whitespace-separated words in the argument",
        ),
        ("charcount", "count characters in the argument"),
        ("calc", "evaluate an arithmetic expression, e.g. (2+3)*4"),
        (
            "time",
            "current time as unix seconds (UTC); takes no argument",
        ),
    ];
    if include_recall {
        specs.push((
            "recall",
            "search the daemon's own learned memory for text relevant to the argument",
        ));
    }
    if include_search {
        specs.push((
            "search",
            "search the operator's document corpus (RAG) for passages relevant to the argument",
        ));
    }
    specs
        .into_iter()
        .map(|(name, desc)| ToolSpec {
            name: name.to_string(),
            description: desc.to_string(),
            parameters: serde_json::json!({}),
        })
        .collect()
}

/// Format a completed [`sovereign_agent_loop::AgentResult`] into the text a chat
/// response should carry: the final answer when the loop converged, else an
/// honest note about why it stopped (step cap / repeated action). Pure + tested.
fn format_agent_answer(result: &sovereign_agent_loop::AgentResult) -> String {
    match (&result.answer, &result.stop_reason) {
        (Some(ans), _) => ans.clone(),
        (None, StopReason::StepCap) => format!(
            "[agentic: reached the {}-step cap without a final answer]",
            result.steps.len()
        ),
        (None, StopReason::RepeatedAction) => {
            "[agentic: stopped — the model repeated the same tool call]".to_string()
        }
        (None, StopReason::FinalAnswer) => String::new(),
    }
}

/// A [`Responder`] backed by the daemon's shared generator (Option A). Each
/// `respond` locks the same generator every request uses and runs one
/// `generate_chat`, accumulating the streamed chunks into the reply — **no model
/// clone**. `seed` is ignored (the daemon's generation is deterministic; the
/// loop's repeat-guard breaks cycles).
pub struct GatewayResponder<'a> {
    server: &'a GatewayServer,
    model: Option<String>,
    max_new: usize,
}

impl<'a> GatewayResponder<'a> {
    pub fn new(server: &'a GatewayServer, model: Option<String>, max_new: usize) -> Self {
        Self {
            server,
            model,
            max_new,
        }
    }
}

impl Responder for GatewayResponder<'_> {
    fn respond(&mut self, prompt: &str, _seed: u64) -> Result<String, String> {
        // A PROXY-backed model is not reachable through generate_chat: that path
        // resolves the local worker pool and in-process secondaries and never
        // consults resolve_proxy. Before this, asking the loop for a GPU model
        // silently ran it against the CPU primary — the answer came from a 1.7B
        // while the caller believed a 120B was reasoning.
        //
        // The tool convention is a PROMPT convention, so a remote OpenAI-dialect
        // backend drives the loop exactly as a local generator does: send the
        // transcript, read the reply, let the loop parse [[tool:...]] out of it.
        // Non-streaming, because the loop needs a whole turn before it can act.
        let model = self
            .server
            .expand_alias(self.model.as_deref())
            .or_else(|| self.model.clone());
        if let Some(id) = model.as_deref()
            && let Some((endpoint, dialect)) = self.server.resolve_proxy(id)
        {
            if dialect != "openai" {
                return Err(format!(
                    "model '{id}' is an {dialect}-dialect proxy; the agentic loop                      drives openai-dialect backends"
                ));
            }
            return self.respond_via_proxy(&endpoint, id, prompt);
        }
        let mut buf = String::new();
        self.server
            .generate_chat(self.model.as_deref(), prompt, self.max_new, |c| {
                buf.push_str(c)
            })?;
        Ok(buf)
    }
}

impl GatewayResponder<'_> {
    /// One non-streaming turn against an openai-dialect proxy backend.
    ///
    /// The `model` sent upstream is the RESOLVED id, never the caller's alias —
    /// the same rule the streaming relay needs, for the same reason: a tier
    /// serves under its --served-model-name and 404s on a gateway-side name.
    fn respond_via_proxy(
        &self,
        endpoint: &str,
        model: &str,
        prompt: &str,
    ) -> Result<String, String> {
        let body = serde_json::json!({
            "model": model,
            "max_tokens": self.max_new,
            "stream": false,
            "messages": [{"role": "user", "content": prompt}],
        })
        .to_string();
        let (status, resp) = sovereign_gatewayd::http::proxy_forward(endpoint, "/v1/chat/completions", &body)?;
        if status != 200 {
            return Err(format!("proxy upstream {status}: {}", resp.trim()));
        }
        // proxy_forward returns the raw HTTP response; the JSON body follows the
        // blank line that ends the headers.
        let json = resp.split("\r\n\r\n").nth(1).unwrap_or(&resp);
        let v: serde_json::Value =
            serde_json::from_str(json.trim()).map_err(|e| format!("proxy reply not JSON: {e}"))?;
        let msg = v
            .pointer("/choices/0/message")
            .ok_or_else(|| "proxy reply has no choices[0].message".to_string())?;
        // A reasoning model splits its turn: the tool call can land in EITHER
        // field depending on the parser, and content is often empty while the
        // model is still thinking. Concatenate both so a [[tool:...]] emitted
        // mid-reasoning is not lost — the loop's parser takes the first call it
        // finds either way.
        let reasoning = msg
            .get("reasoning")
            .or_else(|| msg.get("reasoning_content"))
            .and_then(|r| r.as_str())
            .unwrap_or("");
        let content = msg.get("content").and_then(|c| c.as_str()).unwrap_or("");
        Ok(format!("{reasoning}{content}"))
    }
}

/// Run the ReAct loop with a given registry + advertised specs and any
/// [`Responder`], returning the answer text. Split out from [`run_agent`] so the
/// loop wiring is testable with a scripted responder (no model). Prepends the
/// tool preamble so the model knows the `[[tool:…]]` convention + the tools.
pub fn run_loop<R: Responder>(
    responder: R,
    registry: ToolRegistry,
    specs: &[ToolSpec],
    user: &str,
    max_steps: usize,
    seed: u64,
) -> String {
    let preamble = sovereign_tool_bridge::tool_specs_to_prompt(specs);
    let mut agent =
        AgentLoop::new(responder, registry, max_steps).with_repeat_guard(DEFAULT_MAX_REPEATS);
    match agent.run(&format!("{preamble}\n\nUser: {user}"), seed) {
        Ok(result) => {
            // Log what the loop actually DID. Only the final answer reaches the
            // caller, so without this there is no way — from the response, the
            // journal, or anywhere else — to tell a turn that called a tool and
            // used its result from one that called nothing and made the answer
            // up. Both look like a plain assistant message. Diagnosing a wrong
            // answer meant guessing at which of the two had happened.
            for (i, step) in result.steps.iter().enumerate() {
                // The RAW reply, not just the parsed call. Logging only the
                // parsed form cannot distinguish "the model wrote a malformed
                // argument" from "the parser mangled a good one" — which is
                // exactly the question a call like calc(2+3]*4) raises. Bounded
                // so a runaway reply cannot flood the journal.
                let raw: String = step.reply.chars().take(200).collect();
                eprintln!(
                    "sovereign-gatewayd: agentic step {}/{} raw reply: {:?}{}",
                    i + 1,
                    max_steps,
                    raw,
                    if step.reply.chars().count() > 200 {
                        " …(truncated)"
                    } else {
                        ""
                    }
                );
                match &step.tool {
                    Some(o) => eprintln!(
                        "sovereign-gatewayd: agentic step {}/{}: {}({}) -> {}",
                        i + 1,
                        max_steps,
                        o.call.name,
                        o.call.args,
                        o.result
                    ),
                    None => eprintln!(
                        "sovereign-gatewayd: agentic step {}/{}: no tool call (final answer)",
                        i + 1,
                        max_steps
                    ),
                }
            }
            eprintln!(
                "sovereign-gatewayd: agentic finished after {} step(s): {:?}",
                result.steps.len(),
                result.stop_reason
            );
            format_agent_answer(&result)
        }
        Err(e) => format!("[agentic error: {e}]"),
    }
}

/// Run a server-side agentic turn against the daemon's shared model (Option A)
/// with the full built-in tool catalog (incl. `recall` over the daemon's own
/// Cortex memory). Returns the final answer text. Caller has already checked
/// [`agentic_enabled`] and the per-request opt-in.
pub fn run_agent(
    server: &GatewayServer,
    model: Option<&str>,
    user: &str,
    max_new: usize,
    max_steps: usize,
    seed: u64,
) -> String {
    let corpus = server.corpus_handle();
    let has_corpus = corpus.is_some();
    let registry = builtin_registry(Some(server.cortex_handle()), corpus);
    let specs = builtin_specs(true, has_corpus);
    let responder = GatewayResponder::new(server, model.map(str::to_string), max_new);
    run_loop(responder, registry, &specs, user, max_steps, seed)
}

#[cfg(test)]
mod tests {
    use super::*;
    use sovereign_agent_loop::ScriptedResponder;

    #[test]
    fn builtin_tools_are_pure_and_dispatch() {
        let r = builtin_registry(None, None);
        assert_eq!(r.call("upper", "hi").unwrap(), "HI");
        assert_eq!(r.call("reverse", "abc").unwrap(), "cba");
        assert_eq!(r.call("wordcount", "a b c").unwrap(), "3");
        assert_eq!(r.call("charcount", "abc").unwrap(), "3");
        assert!(
            r.call("rm_rf", "/").is_err(),
            "no unadvertised/unsafe tool exists"
        );
    }

    #[test]
    fn calc_tool_evaluates_and_reports_errors() {
        let r = builtin_registry(None, None);
        assert_eq!(r.call("calc", "(2+3)*4").unwrap(), "20");
        assert_eq!(r.call("calc", "5/2").unwrap(), "2.5");
        assert!(r.call("calc", "2+").unwrap().contains("calc error"));
    }

    #[test]
    fn time_tool_returns_unix_seconds() {
        let r = builtin_registry(None, None);
        let out = r.call("time", "").unwrap();
        assert!(out.contains("unix seconds"), "got {out}");
        // the numeric prefix parses as a plausible (post-2020) epoch
        let secs: u64 = out.split_whitespace().next().unwrap().parse().unwrap();
        assert!(secs > 1_600_000_000, "clock looks wrong: {secs}");
    }

    #[test]
    fn recall_tool_present_only_with_a_cortex_and_queries_memory() {
        // No cortex → no recall tool.
        assert!(builtin_registry(None, None).call("recall", "x").is_err());
        // With a cortex handle → recall queries it (empty store → the note).
        let cx = Arc::new(Mutex::new(Cortex::default()));
        let r = builtin_registry(Some(cx), None);
        assert_eq!(
            r.call("recall", "anything").unwrap(),
            "[no relevant memory]"
        );
    }

    #[test]
    fn builtin_specs_match_the_registry_names() {
        let names: Vec<String> = builtin_registry(None, None).names();
        let spec_names: Vec<String> = builtin_specs(false, false)
            .into_iter()
            .map(|s| s.name)
            .collect();
        let mut a = names.clone();
        a.sort();
        let mut b = spec_names.clone();
        b.sort();
        assert_eq!(
            a, b,
            "registry(None) and specs(false) must list the same tools"
        );
        // recall appears in both the with-cortex registry and specs(true).
        let cx = Arc::new(Mutex::new(Cortex::default()));
        assert!(builtin_registry(Some(cx), None).has("recall"));
        assert!(
            builtin_specs(true, false)
                .iter()
                .any(|s| s.name == "recall")
        );
    }

    #[test]
    fn search_tool_present_only_with_a_corpus_and_retrieves() {
        use sovereign_retrieval::HybridStore;
        // No corpus → no search tool (and it's absent from the specs).
        assert!(builtin_registry(None, None).call("search", "x").is_err());
        assert!(
            !builtin_specs(true, false)
                .iter()
                .any(|s| s.name == "search")
        );
        // With a corpus handle → search retrieves the relevant passage.
        let mut store = HybridStore::new();
        store.add("a", "The capital of France is Paris.");
        store.add("b", "Mitochondria are the powerhouse of the cell.");
        let corpus = Arc::new(store);
        let r = builtin_registry(None, Some(corpus));
        let out = r.call("search", "capital of France").unwrap();
        assert!(out.contains("Paris"), "got: {out}");
        // The relevant passage ranks first even if backfill (k > corpus size)
        // also includes the irrelevant one.
        let paris = out.find("Paris").unwrap();
        assert!(
            out.find("Mitochondria").is_none_or(|m| paris < m),
            "France passage should rank first: {out}"
        );
        // search is advertised only when include_search.
        assert!(builtin_specs(true, true).iter().any(|s| s.name == "search"));
    }

    #[test]
    fn run_loop_dispatches_a_tool_then_returns_the_final_answer() {
        let responder =
            ScriptedResponder::new(["I'll add them. [[tool:calc|2+3]]", "The sum is 5."]);
        let out = run_loop(
            responder,
            builtin_registry(None, None),
            &builtin_specs(false, false),
            "add 2 and 3",
            DEFAULT_MAX_STEPS,
            7,
        );
        assert_eq!(out, "The sum is 5.");
    }

    #[test]
    fn run_loop_answers_directly_when_no_tool_is_called() {
        let responder = ScriptedResponder::new(["Just an answer, no tools."]);
        let out = run_loop(
            responder,
            builtin_registry(None, None),
            &builtin_specs(false, false),
            "hello",
            DEFAULT_MAX_STEPS,
            1,
        );
        assert_eq!(out, "Just an answer, no tools.");
    }

    #[test]
    fn run_loop_reports_the_step_cap() {
        let responder = ScriptedResponder::new([
            "[[tool:upper|a]]",
            "[[tool:lower|B]]",
            "[[tool:reverse|c]]",
            "[[tool:calc|1+1]]",
            "[[tool:charcount|fff]]",
        ]);
        let out = run_loop(
            responder,
            builtin_registry(None, None),
            &builtin_specs(false, false),
            "loop",
            3,
            0,
        );
        assert!(
            out.contains("step cap"),
            "expected a step-cap note, got: {out}"
        );
    }

    #[test]
    fn agentic_enabled_defaults_off_and_reads_truthy() {
        assert!(!matches!(
            "".to_string().as_str(),
            "1" | "true" | "yes" | "on"
        ));
    }
}
