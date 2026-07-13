//! `sovereign-agent-loop` — a ReAct-style agent control loop.
//!
//! A language model plus tools becomes an *agent* only with a control loop
//! around them. This is that loop: it asks a [`Responder`] for a response, and
//! if the response contains a `[[tool:NAME|ARGS]]` call it dispatches the call
//! through a [`ToolRegistry`], appends the result as an `Observation`, and asks
//! again — repeating until the model answers without calling a tool (the final
//! answer) or a step cap is hit.
//!
//! The loop is generic over the [`Responder`] so it can be driven by any text
//! generator — a real runtime in production, or a scripted responder in tests
//! — which makes the control flow itself fully testable independent of model
//! quality. Every step is recorded, so the whole trajectory (thoughts, tool
//! calls, observations) is inspectable.
//!
//! Composes [`sovereign-tool-dispatch`].
//!
//! [`sovereign-tool-dispatch`]: https://github.com/cyberpunk042/sovereign-os/tree/main/crates/sovereign-tool-dispatch
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use sovereign_tool_dispatch::{ToolError, ToolOutcome, ToolRegistry};
use std::collections::VecDeque;
use thiserror::Error;

/// Schema version of the agent-loop surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A source of model responses, given the running transcript as a prompt.
pub trait Responder {
    /// Produce a response to `prompt`. `seed` makes a stochastic responder
    /// reproducible; deterministic responders may ignore it.
    fn respond(&mut self, prompt: &str, seed: u64) -> Result<String, String>;
}

/// Things that can go wrong running the loop.
#[derive(Debug, Error, PartialEq)]
pub enum AgentError {
    /// The responder failed.
    #[error("responder: {0}")]
    Responder(String),
    /// A tool dispatch failed (e.g. the model called an unknown tool).
    #[error("tool: {0}")]
    Tool(#[from] ToolError),
}

/// One step of the loop: the model's reply, and the tool it ran (if any).
#[derive(Debug, Clone, PartialEq)]
pub struct AgentStep {
    /// The model's raw reply this step.
    pub reply: String,
    /// The tool call + result, if the reply invoked a tool.
    pub tool: Option<ToolOutcome>,
}

/// Why an agent run ended.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum StopReason {
    /// The model produced a reply with no tool call — the final answer.
    FinalAnswer,
    /// The step cap was reached without a final answer.
    StepCap,
    /// The repeat guard tripped: the same tool call (name + args) was issued
    /// `max_repeats` times, so the loop was broken to avoid spinning.
    RepeatedAction,
}

/// The outcome of a loop run.
#[derive(Debug, Clone, PartialEq)]
pub struct AgentResult {
    /// The final answer (the last reply that did not call a tool), if reached.
    pub answer: Option<String>,
    /// Every step taken, in order.
    pub steps: Vec<AgentStep>,
    /// Whether the loop ended with a final answer (`true`) or hit the step cap.
    pub completed: bool,
    /// Why the run ended.
    pub stop_reason: StopReason,
}

/// A ReAct agent loop over a responder and a tool registry.
pub struct AgentLoop<R: Responder> {
    responder: R,
    tools: ToolRegistry,
    max_steps: usize,
    /// Stop early if the same tool call (name + args) is issued this many times.
    /// `0` disables the guard (default).
    max_repeats: usize,
}

impl<R: Responder> AgentLoop<R> {
    /// Build a loop. `max_steps` caps tool-using iterations.
    pub fn new(responder: R, tools: ToolRegistry, max_steps: usize) -> Self {
        Self {
            responder,
            tools,
            max_steps,
            max_repeats: 0,
        }
    }

    /// Enable the **repeat guard**: if the same tool call (name + args) is
    /// issued `max_repeats` times across the run, stop early with
    /// [`StopReason::RepeatedAction`] instead of spinning until the step cap.
    /// `0` disables it (the default). A real safeguard against models that get
    /// stuck re-issuing an identical action.
    pub fn with_repeat_guard(mut self, max_repeats: usize) -> Self {
        self.max_repeats = max_repeats;
        self
    }

    /// The registered tool names, sorted.
    pub fn tool_names(&self) -> Vec<String> {
        self.tools.names()
    }

    /// Run the loop on `user` input. Each step's `seed` is `seed + step` for
    /// reproducibility.
    pub fn run(&mut self, user: &str, seed: u64) -> Result<AgentResult, AgentError> {
        let mut transcript = format!("User: {user}\n");
        let mut steps = Vec::new();
        let mut action_counts: std::collections::HashMap<(String, String), usize> =
            std::collections::HashMap::new();

        for step in 0..self.max_steps {
            let prompt = format!("{transcript}Assistant:");
            let reply = self
                .responder
                .respond(&prompt, seed + step as u64)
                .map_err(AgentError::Responder)?;

            match self.tools.dispatch(&reply)? {
                Some(outcome) => {
                    // tool used → record, feed the observation back, keep going
                    transcript.push_str(&format!(
                        "Assistant: {reply}\nObservation: {}\n",
                        outcome.result
                    ));
                    let key = (outcome.call.name.clone(), outcome.call.args.clone());
                    steps.push(AgentStep {
                        reply,
                        tool: Some(outcome),
                    });
                    // Repeat guard: stop if this identical action has now been
                    // issued max_repeats times.
                    if self.max_repeats > 0 {
                        let count = action_counts.entry(key).or_insert(0);
                        *count += 1;
                        if *count >= self.max_repeats {
                            return Ok(AgentResult {
                                answer: None,
                                steps,
                                completed: false,
                                stop_reason: StopReason::RepeatedAction,
                            });
                        }
                    }
                }
                None => {
                    // no tool call → this is the final answer
                    steps.push(AgentStep {
                        reply: reply.clone(),
                        tool: None,
                    });
                    return Ok(AgentResult {
                        answer: Some(reply),
                        steps,
                        completed: true,
                        stop_reason: StopReason::FinalAnswer,
                    });
                }
            }
        }

        // step cap reached without a final answer
        Ok(AgentResult {
            answer: None,
            steps,
            completed: false,
            stop_reason: StopReason::StepCap,
        })
    }
}

/// A deterministic responder that replays a fixed script of replies — for
/// tests and demos of the loop independent of any model.
#[derive(Debug, Clone, Default)]
pub struct ScriptedResponder {
    replies: VecDeque<String>,
}

impl ScriptedResponder {
    /// Build from an ordered list of replies.
    pub fn new<I: IntoIterator<Item = S>, S: Into<String>>(replies: I) -> Self {
        Self {
            replies: replies.into_iter().map(Into::into).collect(),
        }
    }
}

impl Responder for ScriptedResponder {
    fn respond(&mut self, _prompt: &str, _seed: u64) -> Result<String, String> {
        self.replies
            .pop_front()
            .ok_or_else(|| "scripted responder exhausted".to_string())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn calc_tools() -> ToolRegistry {
        let mut r = ToolRegistry::new();
        r.register("upper", |a| a.to_uppercase());
        r.register("len", |a| a.chars().count().to_string());
        r
    }

    #[test]
    fn answers_directly_when_no_tool_is_called() {
        let responder = ScriptedResponder::new(["the answer is 42"]);
        let mut agent = AgentLoop::new(responder, calc_tools(), 5);
        let res = agent.run("what is the meaning?", 0).unwrap();
        assert!(res.completed);
        assert_eq!(res.answer.as_deref(), Some("the answer is 42"));
        assert_eq!(res.steps.len(), 1);
        assert!(res.steps[0].tool.is_none());
    }

    #[test]
    fn runs_a_tool_then_answers() {
        // step 1 calls `upper`, step 2 gives the final answer.
        let responder =
            ScriptedResponder::new(["let me shout: [[tool:upper|hello]]", "the result was HELLO"]);
        let mut agent = AgentLoop::new(responder, calc_tools(), 5);
        let res = agent.run("shout hello", 1).unwrap();
        assert!(res.completed);
        assert_eq!(res.steps.len(), 2);
        let tool = res.steps[0].tool.as_ref().unwrap();
        assert_eq!(tool.call.name, "upper");
        assert_eq!(tool.result, "HELLO");
        assert!(res.steps[1].tool.is_none());
        assert_eq!(res.answer.as_deref(), Some("the result was HELLO"));
    }

    #[test]
    fn chains_multiple_tools() {
        let responder = ScriptedResponder::new(["[[tool:upper|abc]]", "[[tool:len|abcd]]", "done"]);
        let mut agent = AgentLoop::new(responder, calc_tools(), 5);
        let res = agent.run("go", 0).unwrap();
        assert_eq!(res.steps.len(), 3);
        assert_eq!(res.steps[0].tool.as_ref().unwrap().result, "ABC");
        assert_eq!(res.steps[1].tool.as_ref().unwrap().result, "4");
        assert_eq!(res.answer.as_deref(), Some("done"));
    }

    #[test]
    fn step_cap_ends_without_answer() {
        // always calls a tool → never a final answer → caps out
        let responder =
            ScriptedResponder::new(["[[tool:upper|a]]", "[[tool:upper|b]]", "[[tool:upper|c]]"]);
        let mut agent = AgentLoop::new(responder, calc_tools(), 2);
        let res = agent.run("loop", 0).unwrap();
        assert!(!res.completed);
        assert_eq!(res.answer, None);
        assert_eq!(res.steps.len(), 2); // capped
        assert_eq!(res.stop_reason, StopReason::StepCap);
    }

    #[test]
    fn repeat_guard_breaks_an_identical_action_loop() {
        // The model keeps issuing the exact same call; the guard stops it on the
        // 2nd identical action instead of running to the (large) step cap.
        let responder = ScriptedResponder::new([
            "[[tool:upper|x]]",
            "[[tool:upper|x]]",
            "[[tool:upper|x]]",
            "[[tool:upper|x]]",
        ]);
        let mut agent = AgentLoop::new(responder, calc_tools(), 50).with_repeat_guard(2);
        let res = agent.run("spin", 0).unwrap();
        assert_eq!(res.stop_reason, StopReason::RepeatedAction);
        assert!(!res.completed);
        assert_eq!(res.steps.len(), 2); // stopped on the 2nd identical call
    }

    #[test]
    fn repeat_guard_allows_distinct_actions() {
        // Different args are not "the same action" → the guard does not trip.
        let responder = ScriptedResponder::new(["[[tool:upper|a]]", "[[tool:upper|b]]", "done"]);
        let mut agent = AgentLoop::new(responder, calc_tools(), 50).with_repeat_guard(2);
        let res = agent.run("vary", 0).unwrap();
        assert_eq!(res.stop_reason, StopReason::FinalAnswer);
        assert_eq!(res.answer.as_deref(), Some("done"));
    }

    #[test]
    fn final_answer_sets_stop_reason() {
        let responder = ScriptedResponder::new(["just an answer"]);
        let mut agent = AgentLoop::new(responder, calc_tools(), 5);
        let res = agent.run("q", 0).unwrap();
        assert_eq!(res.stop_reason, StopReason::FinalAnswer);
    }

    #[test]
    fn unknown_tool_is_an_error() {
        let responder = ScriptedResponder::new(["[[tool:ghost|x]]"]);
        let mut agent = AgentLoop::new(responder, calc_tools(), 3);
        let err = agent.run("call ghost", 0).unwrap_err();
        assert!(matches!(err, AgentError::Tool(ToolError::UnknownTool(_))));
    }

    #[test]
    fn responder_failure_propagates() {
        // exhausted scripted responder → responder error
        let responder = ScriptedResponder::new(Vec::<String>::new());
        let mut agent = AgentLoop::new(responder, calc_tools(), 3);
        assert!(matches!(
            agent.run("hi", 0).unwrap_err(),
            AgentError::Responder(_)
        ));
    }

    #[test]
    fn observation_is_fed_back_into_the_prompt() {
        // a responder that echoes the prompt lets us verify the observation
        // from step 1 appears in step 2's prompt.
        struct PromptCapture {
            seen: std::rc::Rc<std::cell::RefCell<Vec<String>>>,
            scripted: ScriptedResponder,
        }
        impl Responder for PromptCapture {
            fn respond(&mut self, prompt: &str, seed: u64) -> Result<String, String> {
                self.seen.borrow_mut().push(prompt.to_string());
                self.scripted.respond(prompt, seed)
            }
        }
        let seen = std::rc::Rc::new(std::cell::RefCell::new(Vec::new()));
        let responder = PromptCapture {
            seen: seen.clone(),
            scripted: ScriptedResponder::new(["[[tool:upper|hi]]", "final"]),
        };
        let mut agent = AgentLoop::new(responder, calc_tools(), 4);
        agent.run("go", 0).unwrap();
        let prompts = seen.borrow();
        assert_eq!(prompts.len(), 2);
        // step 2's prompt must contain the observation "HI" from step 1
        assert!(prompts[1].contains("Observation: HI"), "{}", prompts[1]);
    }

    #[test]
    fn tool_names_are_exposed() {
        let agent = AgentLoop::new(ScriptedResponder::default(), calc_tools(), 1);
        assert_eq!(agent.tool_names(), vec!["len", "upper"]);
    }
}
