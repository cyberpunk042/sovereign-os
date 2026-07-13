//! `sovereign-agent-runtime` — run the agent loop on the real LLM runtime.
//!
//! [`sovereign-agent-loop`] is generic over a `Responder`; this crate provides
//! the production one. [`LlmResponder`] wraps a [`SovereignLlm`] and implements
//! [`Responder`] by completing the loop's prompt with the runtime, cutting the
//! reply at configured stop sequences so the model can't run past its turn.
//! Because the runtime's completion is **stateless** (it decodes from a fresh
//! model clone each call), one `LlmResponder` can serve every step of the loop
//! without the steps contaminating each other — which is exactly what a
//! multi-step agent needs.
//!
//! This is the wiring that turns the whole stack — quantized inference engine
//! plus the agentic control layer — into one running, tool-using agent.
//!
//! Composes [`sovereign-agent-loop`] and [`sovereign-llm`].
//!
//! [`sovereign-agent-loop`]: https://github.com/cyberpunk042/sovereign-os/tree/main/crates/sovereign-agent-loop
//! [`sovereign-llm`]: https://github.com/cyberpunk042/sovereign-os/tree/main/crates/sovereign-llm
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use sovereign_agent_loop::Responder;
use sovereign_llm::SovereignLlm;
use sovereign_stop_sequence::StopSequences;

/// Schema version of the agent-runtime surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A [`Responder`] backed by the real [`SovereignLlm`] runtime.
#[derive(Debug, Clone)]
pub struct LlmResponder {
    llm: SovereignLlm,
    max_new: usize,
    stops: StopSequences,
}

impl LlmResponder {
    /// Wrap a runtime, generating up to `max_new` tokens per step and cutting
    /// each reply at the loop's structural cues so a turn can't overrun.
    pub fn new(llm: SovereignLlm, max_new: usize) -> Self {
        Self {
            llm,
            max_new,
            // stop before the loop's own markers so a reply is one turn only
            stops: StopSequences::from(["\nUser:", "\nObservation:", "\nAssistant:"]),
        }
    }

    /// Replace the stop sequences that bound each reply.
    pub fn with_stops(mut self, stops: StopSequences) -> Self {
        self.stops = stops;
        self
    }
}

impl Responder for LlmResponder {
    fn respond(&mut self, prompt: &str, seed: u64) -> Result<String, String> {
        let full = self
            .llm
            .complete(prompt, self.max_new, seed)
            .map_err(|e| e.to_string())?;
        Ok(self.stops.cut(&full).to_string())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use sovereign_agent_loop::AgentLoop;
    use sovereign_decoder_stack::StackConfig;
    use sovereign_ffn::SwiGlu;
    use sovereign_rmsnorm::RmsNorm;
    use sovereign_sampler::{Sampler, SamplerConfig};
    use sovereign_tokenizer::Tokenizer;
    use sovereign_tool_dispatch::ToolRegistry;
    use sovereign_transformer_block::BlockWeights;

    const MD: usize = 4;

    fn mat(s: f32, n: usize) -> Vec<f32> {
        (0..n).map(|i| ((i as f32 + s) * 0.017).sin()).collect()
    }

    fn runtime() -> SovereignLlm {
        let tok = Tokenizer::default();
        let vocab = tok.vocab_size();
        let block = BlockWeights {
            model_dim: MD,
            head_dim: MD,
            attn_norm: RmsNorm::new(MD),
            ffn_norm: RmsNorm::new(MD),
            w_q: mat(1.0, MD * MD),
            w_k: mat(2.0, MD * MD),
            w_v: mat(3.0, MD * MD),
            w_o: mat(4.0, MD * MD),
            ffn: SwiGlu::new(
                MD,
                MD,
                mat(5.0, MD * MD),
                mat(6.0, MD * MD),
                mat(7.0, MD * MD),
            )
            .unwrap(),
        };
        let cfg = StackConfig {
            vocab,
            model_dim: MD,
            embedding: mat(0.5, vocab * MD),
            blocks: vec![block],
            final_norm: RmsNorm::new(MD),
            head: mat(0.9, vocab * MD),
            sampler: Sampler::new(SamplerConfig::default()),
            recent_window: 64,
        };
        SovereignLlm::new(tok, cfg).unwrap()
    }

    #[test]
    fn responder_returns_a_bounded_reply() {
        let mut r = LlmResponder::new(runtime(), 8);
        let reply = r.respond("User: hi\nAssistant:", 1).unwrap();
        // a reply is produced and never contains a loop marker (cut by stops)
        assert!(!reply.contains("\nUser:"));
        assert!(!reply.contains("\nObservation:"));
    }

    #[test]
    fn responder_is_reproducible_and_stateless() {
        let mut r = LlmResponder::new(runtime(), 8);
        let a = r.respond("User: hi\nAssistant:", 7).unwrap();
        // an intervening different prompt must not perturb the repeat
        let _ = r.respond("User: something else\nAssistant:", 3).unwrap();
        let b = r.respond("User: hi\nAssistant:", 7).unwrap();
        assert_eq!(a, b);
    }

    #[test]
    fn agent_loop_runs_on_the_real_runtime() {
        // With random weights the model won't emit a tool call, so the loop
        // completes in one step with a (gibberish) final answer — but it proves
        // the real runtime drives the agent-loop control flow end to end.
        let mut tools = ToolRegistry::new();
        tools.register("echo", |a| a.to_string());
        let responder = LlmResponder::new(runtime(), 6);
        let mut agent = AgentLoop::new(responder, tools, 4);
        let res = agent.run("hello", 0).unwrap();
        assert!(res.completed);
        assert!(res.answer.is_some());
        assert_eq!(res.steps.len(), 1);
        assert!(res.steps[0].tool.is_none());
    }

    #[test]
    fn custom_stops_override_defaults() {
        let mut r = LlmResponder::new(runtime(), 12).with_stops(StopSequences::from(["a"]));
        let reply = r.respond("User: hi\nAssistant:", 5).unwrap();
        assert!(!reply.contains('a'));
    }
}
