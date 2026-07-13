//! `sovereign-chat` — multi-turn conversation over the LLM runtime.
//!
//! The runtime completes a prompt; a *conversation* is the agentic layer above
//! that. This crate tracks a role-tagged message history, renders it into a
//! single prompt the model continues, generates the assistant's reply, and
//! appends it — turning one-shot completion into stateful dialogue.
//!
//! For *endless* dialogue the history is **bounded**: an optional turn cap
//! keeps the system message plus the most recent turns, dropping the oldest,
//! so the rendered prompt never grows without limit. Generation is the
//! runtime's, so a conversation is reproducible for a given seed.
//!
//! ```text
//!   say(user):  history += User(user)
//!               prompt   = render(history) + "Assistant:"
//!               reply    = llm.complete(prompt)
//!               history += Assistant(reply)
//! ```
//!
//! Composes [`sovereign-llm`].
//!
//! [`sovereign-llm`]: https://github.com/cyberpunk042/sovereign-os/tree/main/crates/sovereign-llm
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use sovereign_llm::{LlmError, SovereignLlm};
use sovereign_stop_sequence::StopSequences;
use thiserror::Error;

/// Schema version of the chat surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Who authored a message.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Role {
    /// The system / instruction message (kept across history trimming).
    System,
    /// A user turn.
    User,
    /// An assistant (model) turn.
    Assistant,
}

impl Role {
    /// The label used when rendering the prompt.
    pub fn label(self) -> &'static str {
        match self {
            Role::System => "System",
            Role::User => "User",
            Role::Assistant => "Assistant",
        }
    }
}

/// One message in a conversation.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Message {
    /// Who wrote it.
    pub role: Role,
    /// The text.
    pub content: String,
}

/// Things that can go wrong in a chat turn.
#[derive(Debug, Error, PartialEq)]
pub enum ChatError {
    /// The underlying runtime failed.
    #[error("llm: {0}")]
    Llm(#[from] LlmError),
}

/// A role-tagged message history.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub struct Conversation {
    /// The messages, oldest first.
    pub messages: Vec<Message>,
}

impl Conversation {
    /// An empty conversation.
    pub fn new() -> Self {
        Self::default()
    }

    /// Start with a system message.
    pub fn with_system(system: impl Into<String>) -> Self {
        Self {
            messages: vec![Message {
                role: Role::System,
                content: system.into(),
            }],
        }
    }

    /// Append a message.
    pub fn push(&mut self, role: Role, content: impl Into<String>) {
        self.messages.push(Message {
            role,
            content: content.into(),
        });
    }

    /// Number of messages.
    pub fn len(&self) -> usize {
        self.messages.len()
    }

    /// Whether there are no messages.
    pub fn is_empty(&self) -> bool {
        self.messages.is_empty()
    }

    /// Render the history into a prompt for the model to continue. Ends with
    /// the bare `Assistant:` cue so generation produces the next reply.
    pub fn render_prompt(&self) -> String {
        let mut s = String::new();
        for m in &self.messages {
            s.push_str(m.role.label());
            s.push_str(": ");
            s.push_str(&m.content);
            s.push('\n');
        }
        s.push_str("Assistant:");
        s
    }

    /// Render the history using a real chat-template dialect (ChatML / Llama-2 /
    /// Alpaca / custom) via [`sovereign-chat-template`](sovereign_chat_template)'s
    /// `apply_chat_template`, appending the assistant generation cue. Use this
    /// when the model was trained on a specific turn format — the plain
    /// [`render_prompt`](Self::render_prompt) labels (`User:`/`Assistant:`) are a
    /// neutral default, but an instruction-tuned model needs its exact dialect.
    pub fn render_prompt_with(&self, format: &sovereign_chat_template::ChatFormat) -> String {
        let msgs: Vec<sovereign_chat_template::Message> = self
            .messages
            .iter()
            .map(|m| {
                let role = match m.role {
                    Role::System => sovereign_chat_template::Role::System,
                    Role::User => sovereign_chat_template::Role::User,
                    Role::Assistant => sovereign_chat_template::Role::Assistant,
                };
                sovereign_chat_template::Message::new(role, m.content.clone())
            })
            .collect();
        sovereign_chat_template::render(&msgs, format, true)
    }

    /// Trim to at most `max_turns` non-system messages, keeping the most recent
    /// (the leading system message, if any, is always retained).
    pub fn trim_to(&mut self, max_turns: usize) {
        let has_system = self
            .messages
            .first()
            .is_some_and(|m| m.role == Role::System);
        let sys_count = usize::from(has_system);
        let body = self.messages.len() - sys_count;
        if body <= max_turns {
            return;
        }
        let drop = body - max_turns;
        // remove `drop` messages right after the system message
        self.messages.drain(sys_count..sys_count + drop);
    }
}

/// A stateful chat session: a runtime + its conversation.
#[derive(Debug)]
pub struct ChatSession {
    llm: SovereignLlm,
    conversation: Conversation,
    max_new: usize,
    max_turns: Option<usize>,
    stops: StopSequences,
    /// When set, render each prompt in this chat-template dialect instead of the
    /// plain `Role:`-labelled default.
    format: Option<sovereign_chat_template::ChatFormat>,
}

impl ChatSession {
    /// Start a session with an optional system message and a per-reply token
    /// budget. By default the reply is cut at `"\nUser:"` (the next-turn cue)
    /// if it appears, so the model can't role-play the user.
    pub fn new(llm: SovereignLlm, system: Option<&str>, max_new: usize) -> Self {
        let conversation = match system {
            Some(s) => Conversation::with_system(s),
            None => Conversation::new(),
        };
        Self {
            llm,
            conversation,
            max_new,
            max_turns: None,
            stops: StopSequences::from(["\nUser:", "\nSystem:"]),
            format: None,
        }
    }

    /// Bound the retained history to `max_turns` non-system messages.
    pub fn with_max_turns(mut self, max_turns: usize) -> Self {
        self.max_turns = Some(max_turns);
        self
    }

    /// Render prompts in a specific chat-template dialect (ChatML / Llama-2 /
    /// Alpaca / custom) via [`Conversation::render_prompt_with`], instead of the
    /// plain `Role:`-labelled default — for a model trained on that exact format.
    pub fn with_format(mut self, format: sovereign_chat_template::ChatFormat) -> Self {
        self.format = Some(format);
        self
    }

    /// Replace the stop sequences that truncate each reply.
    pub fn with_stops(mut self, stops: StopSequences) -> Self {
        self.stops = stops;
        self
    }

    /// Borrow the conversation so far.
    pub fn history(&self) -> &Conversation {
        &self.conversation
    }

    /// Take one turn: record `user`, generate the assistant's reply, record and
    /// return it. Reproducible for a given `seed`.
    pub fn say(&mut self, user: &str, seed: u64) -> Result<String, ChatError> {
        self.conversation.push(Role::User, user);
        if let Some(max) = self.max_turns {
            self.conversation.trim_to(max);
        }
        let prompt = match &self.format {
            Some(fmt) => self.conversation.render_prompt_with(fmt),
            None => self.conversation.render_prompt(),
        };
        let full = self.llm.complete(&prompt, self.max_new, seed)?;
        // cut the reply at the first stop sequence (e.g. the next-turn cue)
        let reply = self.stops.cut(&full).to_string();
        self.conversation.push(Role::Assistant, reply.clone());
        if let Some(max) = self.max_turns {
            self.conversation.trim_to(max);
        }
        Ok(reply)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use sovereign_decoder_stack::StackConfig;
    use sovereign_ffn::SwiGlu;
    use sovereign_llm::SovereignLlm;
    use sovereign_rmsnorm::RmsNorm;
    use sovereign_sampler::{Sampler, SamplerConfig};
    use sovereign_tokenizer::Tokenizer;
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
    fn render_prompt_lists_roles_and_cues_assistant() {
        let mut c = Conversation::with_system("be terse");
        c.push(Role::User, "hi");
        c.push(Role::Assistant, "hello");
        c.push(Role::User, "ok");
        let p = c.render_prompt();
        assert!(p.starts_with("System: be terse\n"));
        assert!(p.contains("User: hi\n"));
        assert!(p.contains("Assistant: hello\n"));
        assert!(p.ends_with("Assistant:"));
    }

    #[test]
    fn render_prompt_with_chatml_uses_turn_markers() {
        use sovereign_chat_template::ChatFormat;
        let mut c = Conversation::with_system("be terse");
        c.push(Role::User, "hi");
        let p = c.render_prompt_with(&ChatFormat::ChatML);
        // ChatML wraps each turn in <|im_start|>role … <|im_end|> and cues the
        // assistant turn at the end (add_generation_prompt).
        assert!(p.contains("<|im_start|>system\nbe terse<|im_end|>"), "{p}");
        assert!(p.contains("<|im_start|>user\nhi<|im_end|>"), "{p}");
        assert!(p.trim_end().ends_with("<|im_start|>assistant"), "{p}");
        // it differs from the plain default render
        assert_ne!(p, c.render_prompt());
    }

    #[test]
    fn session_with_format_uses_the_dialect() {
        use sovereign_chat_template::ChatFormat;
        // A formatted session still records turns correctly (the format only
        // changes how the prompt is rendered to the model).
        let mut s = ChatSession::new(runtime(), Some("sys"), 6).with_format(ChatFormat::ChatML);
        let reply = s.say("hello there", 42).unwrap();
        assert_eq!(s.history().len(), 3);
        assert_eq!(s.history().messages[2].content, reply);
    }

    #[test]
    fn a_turn_records_user_and_assistant() {
        let mut s = ChatSession::new(runtime(), Some("sys"), 6);
        let reply = s.say("hello there", 42).unwrap();
        // system + user + assistant
        assert_eq!(s.history().len(), 3);
        assert_eq!(s.history().messages[1].role, Role::User);
        assert_eq!(s.history().messages[2].role, Role::Assistant);
        assert_eq!(s.history().messages[2].content, reply);
    }

    #[test]
    fn multiple_turns_accumulate() {
        let mut s = ChatSession::new(runtime(), None, 4);
        s.say("one", 1).unwrap();
        s.say("two", 2).unwrap();
        // 2 user + 2 assistant
        assert_eq!(s.history().len(), 4);
    }

    #[test]
    fn replies_are_reproducible_per_seed() {
        let mut a = ChatSession::new(runtime(), Some("sys"), 8);
        let mut b = ChatSession::new(runtime(), Some("sys"), 8);
        assert_eq!(
            a.say("same input", 7).unwrap(),
            b.say("same input", 7).unwrap()
        );
    }

    #[test]
    fn bounded_history_keeps_system_and_recent_turns() {
        let mut s = ChatSession::new(runtime(), Some("sys"), 3).with_max_turns(2);
        for i in 0..5 {
            s.say(&format!("msg {i}"), i as u64).unwrap();
        }
        // system always kept; non-system bounded to 2
        let h = s.history();
        assert_eq!(h.messages[0].role, Role::System);
        let non_system = h.len() - 1;
        assert!(non_system <= 2, "non-system {non_system} should be <= 2");
    }

    #[test]
    fn trim_keeps_most_recent() {
        let mut c = Conversation::with_system("s");
        for i in 0..6 {
            c.push(Role::User, format!("u{i}"));
        }
        c.trim_to(2);
        assert_eq!(c.messages[0].role, Role::System);
        assert_eq!(c.messages.len(), 3); // system + 2
        assert_eq!(c.messages[1].content, "u4");
        assert_eq!(c.messages[2].content, "u5");
    }

    #[test]
    fn replies_are_cut_at_stop_sequences() {
        use sovereign_stop_sequence::StopSequences;
        // Force a stop the reply will contain: with a 1-token reply over the
        // default byte vocab the reply is a single char; instead set a stop of
        // the empty-ish guarantee by using a permissive runtime and a stop on a
        // common char. We assert the recorded reply never contains the stop.
        let mut s =
            ChatSession::new(runtime(), Some("sys"), 12).with_stops(StopSequences::from(["a"]));
        let reply = s.say("hello", 5).unwrap();
        assert!(
            !reply.contains('a'),
            "reply {reply:?} should be cut before any 'a'"
        );
        // and the recorded assistant message equals the cut reply
        assert_eq!(s.history().messages.last().unwrap().content, reply);
    }

    #[test]
    fn conversation_serde_round_trip() {
        let mut c = Conversation::with_system("s");
        c.push(Role::User, "hi");
        c.push(Role::Assistant, "yo");
        let j = serde_json::to_string(&c).unwrap();
        let back: Conversation = serde_json::from_str(&j).unwrap();
        assert_eq!(c, back);
    }
}
