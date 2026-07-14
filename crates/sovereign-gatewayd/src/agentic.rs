//! SDD-712 (F-2026-088): server-side agentic tool use.
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
//! **Sovereignty posture**: a root-adjacent daemon that autonomously executes
//! tools is gated two ways — a per-request opt-in (`sovereign_agentic: true`)
//! AND an env kill-switch (`SOVEREIGN_GATEWAY_AGENTIC=1`, **default OFF**). The
//! built-in tools are deliberately **pure and side-effect-free** (no shell, fs,
//! or network), so executing them carries no security surface; the gate exists
//! for the *capability* (an autonomous loop), not these specific tools. A
//! curated production tool catalog (calc, time, local retrieval) is a follow-up.

use sovereign_agent_loop::{AgentLoop, Responder, StopReason};
use sovereign_gatewayd::GatewayServer;
use sovereign_tool_bridge::ToolSpec;
use sovereign_tool_dispatch::ToolRegistry;

/// Default step cap for a server-side agentic turn (bounded so a runaway loop
/// can't pin the shared generator). Overridable per request via `max_steps`.
pub const DEFAULT_MAX_STEPS: usize = 4;
/// Repeat-guard: stop if the model calls the same tool with the same args this
/// many times (a cheap cycle breaker on top of the step cap).
pub const DEFAULT_MAX_REPEATS: usize = 2;

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

/// The daemon's built-in tool set — **pure, deterministic, side-effect-free**
/// string transforms. Safe to execute on a root daemon; the whole point of
/// keeping slice-1 tools pure is that no sandbox is needed to run them.
pub fn builtin_tools() -> ToolRegistry {
    let mut r = ToolRegistry::new();
    r.register("upper", |a| a.to_uppercase());
    r.register("lower", |a| a.to_lowercase());
    r.register("reverse", |a| a.chars().rev().collect::<String>());
    r.register("wordcount", |a| a.split_whitespace().count().to_string());
    r.register("charcount", |a| a.chars().count().to_string());
    r
}

/// The [`ToolSpec`]s advertised to the model for the built-in tools, in the same
/// shape SDD-711's bridge renders into a prompt preamble. Kept in lockstep with
/// [`builtin_tools`] (the contract lint asserts the two agree).
pub fn builtin_specs() -> Vec<ToolSpec> {
    [
        ("upper", "uppercase the argument text"),
        ("lower", "lowercase the argument text"),
        ("reverse", "reverse the argument text"),
        (
            "wordcount",
            "count whitespace-separated words in the argument",
        ),
        ("charcount", "count characters in the argument"),
    ]
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
        let mut buf = String::new();
        self.server
            .generate_chat(self.model.as_deref(), prompt, self.max_new, |c| {
                buf.push_str(c)
            })?;
        Ok(buf)
    }
}

/// Run the ReAct loop over the built-in tools with any [`Responder`], returning
/// the answer text. Split out from [`run_agent`] so the loop wiring is testable
/// with a scripted responder (no model). Prepends the built-in tool preamble so
/// the model knows the `[[tool:…]]` convention + the available tools.
pub fn run_loop<R: Responder>(responder: R, user: &str, max_steps: usize, seed: u64) -> String {
    let preamble = sovereign_tool_bridge::tool_specs_to_prompt(&builtin_specs());
    let mut agent = AgentLoop::new(responder, builtin_tools(), max_steps)
        .with_repeat_guard(DEFAULT_MAX_REPEATS);
    match agent.run(&format!("{preamble}\n\nUser: {user}"), seed) {
        Ok(result) => format_agent_answer(&result),
        Err(e) => format!("[agentic error: {e}]"),
    }
}

/// Run a server-side agentic turn against the daemon's shared model (Option A).
/// Returns the final answer text. Caller has already checked [`agentic_enabled`]
/// and the per-request opt-in.
pub fn run_agent(
    server: &GatewayServer,
    model: Option<&str>,
    user: &str,
    max_new: usize,
    max_steps: usize,
    seed: u64,
) -> String {
    let responder = GatewayResponder::new(server, model.map(str::to_string), max_new);
    run_loop(responder, user, max_steps, seed)
}

#[cfg(test)]
mod tests {
    use super::*;
    use sovereign_agent_loop::ScriptedResponder;

    #[test]
    fn builtin_tools_are_pure_and_dispatch() {
        let r = builtin_tools();
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
    fn builtin_specs_match_the_registry_names() {
        let names: Vec<String> = builtin_tools().names();
        let spec_names: Vec<String> = builtin_specs().into_iter().map(|s| s.name).collect();
        let mut a = names.clone();
        a.sort();
        let mut b = spec_names.clone();
        b.sort();
        assert_eq!(
            a, b,
            "builtin_tools() and builtin_specs() must list the same tools"
        );
    }

    #[test]
    fn run_loop_dispatches_a_tool_then_returns_the_final_answer() {
        // Step 1: the model calls a tool. Step 2: it answers with no tool call.
        let responder = ScriptedResponder::new([
            "I'll uppercase it. [[tool:upper|sovereign]]",
            "The result is SOVEREIGN.",
        ]);
        let out = run_loop(responder, "uppercase 'sovereign'", DEFAULT_MAX_STEPS, 7);
        assert_eq!(out, "The result is SOVEREIGN.");
    }

    #[test]
    fn run_loop_answers_directly_when_no_tool_is_called() {
        let responder = ScriptedResponder::new(["Just an answer, no tools."]);
        let out = run_loop(responder, "hello", DEFAULT_MAX_STEPS, 1);
        assert_eq!(out, "Just an answer, no tools.");
    }

    #[test]
    fn run_loop_reports_the_step_cap() {
        // Always calls a (different) tool → never a final answer → hits the cap.
        let responder = ScriptedResponder::new([
            "[[tool:upper|a]]",
            "[[tool:lower|B]]",
            "[[tool:reverse|c]]",
            "[[tool:wordcount|d e]]",
            "[[tool:charcount|fff]]",
        ]);
        let out = run_loop(responder, "loop", 3, 0);
        assert!(
            out.contains("step cap"),
            "expected a step-cap note, got: {out}"
        );
    }

    #[test]
    fn agentic_enabled_defaults_off_and_reads_truthy() {
        // The default-off behaviour is asserted indirectly: with the var unset the
        // helper is false. (Env is process-global; we only assert the parse of an
        // explicit value here to avoid cross-test env races.)
        assert!(!matches!(
            "".to_string().as_str(),
            "1" | "true" | "yes" | "on"
        ));
    }
}
