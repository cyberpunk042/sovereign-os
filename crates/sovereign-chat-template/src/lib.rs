//! `sovereign-chat-template` — format messages the way each model expects.
//!
//! A chat model is trained on a specific prompt format, and using the wrong one
//! quietly wrecks quality: an instruction-tuned model that expects ChatML's
//! `<|im_start|>` turn markers will not behave if you feed it Llama-2's
//! `[INST] … [/INST]`. Hugging Face calls turning a list of role-tagged messages
//! into that exact string `apply_chat_template`; this crate is that step for the
//! formats that matter.
//!
//! [`ChatFormat`] selects the dialect:
//! - **ChatML** — `<|im_start|>role\ncontent<|im_end|>` per turn (OpenAI / Qwen
//!   / many open models).
//! - **Llama2** — `<s>[INST] <<SYS>>system<</SYS>> user [/INST] assistant </s>`.
//! - **Alpaca** — `### Instruction:` / `### Response:` blocks.
//! - **Custom** — your own per-role prefix/suffix [`RoleTemplate`]s.
//!
//! [`render`] takes the messages and a format and produces the prompt; with
//! `add_generation_prompt` it appends the opener that cues the model to start its
//! assistant turn (e.g. ChatML's trailing `<|im_start|>assistant\n`). A single
//! leading system message is handled per-format; multiple are concatenated.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version of the chat-template surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A message role.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Role {
    /// System / instruction role.
    System,
    /// End-user role.
    User,
    /// Model / assistant role.
    Assistant,
}

/// One chat message.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Message {
    /// The speaker.
    pub role: Role,
    /// The content.
    pub content: String,
}

impl Message {
    /// Build a message.
    pub fn new(role: Role, content: impl Into<String>) -> Self {
        Self {
            role,
            content: content.into(),
        }
    }
    /// A system message.
    pub fn system(c: impl Into<String>) -> Self {
        Self::new(Role::System, c)
    }
    /// A user message.
    pub fn user(c: impl Into<String>) -> Self {
        Self::new(Role::User, c)
    }
    /// An assistant message.
    pub fn assistant(c: impl Into<String>) -> Self {
        Self::new(Role::Assistant, c)
    }
}

/// Per-role prefix/suffix wrapping for a [`ChatFormat::Custom`] template.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct RoleTemplate {
    /// Text emitted before a system message.
    pub system: (String, String),
    /// Text emitted before/after a user message.
    pub user: (String, String),
    /// Text emitted before/after an assistant message.
    pub assistant: (String, String),
    /// The opener appended to cue the assistant's turn (generation prompt).
    pub generation_prompt: String,
}

/// A chat prompt format.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum ChatFormat {
    /// ChatML (`<|im_start|>` / `<|im_end|>`).
    ChatML,
    /// Llama-2 (`[INST]` / `<<SYS>>`).
    Llama2,
    /// Alpaca (`### Instruction:` / `### Response:`).
    Alpaca,
    /// A custom per-role template.
    Custom(RoleTemplate),
}

/// Render `messages` into a prompt string for `format`. If `add_generation_prompt`
/// is set, append the assistant-turn opener so the model continues from there.
pub fn render(messages: &[Message], format: &ChatFormat, add_generation_prompt: bool) -> String {
    match format {
        ChatFormat::ChatML => render_chatml(messages, add_generation_prompt),
        ChatFormat::Llama2 => render_llama2(messages, add_generation_prompt),
        ChatFormat::Alpaca => render_alpaca(messages, add_generation_prompt),
        ChatFormat::Custom(t) => render_custom(messages, t, add_generation_prompt),
    }
}

fn render_chatml(messages: &[Message], add_gen: bool) -> String {
    let mut out = String::new();
    for m in messages {
        let role = match m.role {
            Role::System => "system",
            Role::User => "user",
            Role::Assistant => "assistant",
        };
        out.push_str("<|im_start|>");
        out.push_str(role);
        out.push('\n');
        out.push_str(&m.content);
        out.push_str("<|im_end|>\n");
    }
    if add_gen {
        out.push_str("<|im_start|>assistant\n");
    }
    out
}

fn render_llama2(messages: &[Message], add_gen: bool) -> String {
    // Group into [system?] then alternating user/assistant turns.
    let system: Option<&str> = messages
        .iter()
        .find(|m| m.role == Role::System)
        .map(|m| m.content.as_str());
    let mut out = String::new();
    let mut first_user = true;
    for m in messages {
        match m.role {
            Role::System => {} // folded into the first user turn below
            Role::User => {
                out.push_str("<s>[INST] ");
                if first_user {
                    if let Some(sys) = system {
                        out.push_str("<<SYS>>\n");
                        out.push_str(sys);
                        out.push_str("\n<</SYS>>\n\n");
                    }
                    first_user = false;
                }
                out.push_str(&m.content);
                out.push_str(" [/INST]");
            }
            Role::Assistant => {
                out.push(' ');
                out.push_str(&m.content);
                out.push_str(" </s>");
            }
        }
    }
    if add_gen {
        out.push(' ');
    }
    out
}

fn render_alpaca(messages: &[Message], add_gen: bool) -> String {
    let mut out = String::new();
    if let Some(sys) = messages.iter().find(|m| m.role == Role::System) {
        out.push_str(&sys.content);
        out.push_str("\n\n");
    }
    for m in messages {
        match m.role {
            Role::System => {}
            Role::User => {
                out.push_str("### Instruction:\n");
                out.push_str(&m.content);
                out.push_str("\n\n");
            }
            Role::Assistant => {
                out.push_str("### Response:\n");
                out.push_str(&m.content);
                out.push_str("\n\n");
            }
        }
    }
    if add_gen {
        out.push_str("### Response:\n");
    }
    out
}

fn render_custom(messages: &[Message], t: &RoleTemplate, add_gen: bool) -> String {
    let mut out = String::new();
    for m in messages {
        let (pre, suf) = match m.role {
            Role::System => &t.system,
            Role::User => &t.user,
            Role::Assistant => &t.assistant,
        };
        out.push_str(pre);
        out.push_str(&m.content);
        out.push_str(suf);
    }
    if add_gen {
        out.push_str(&t.generation_prompt);
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn convo() -> Vec<Message> {
        vec![
            Message::system("You are helpful."),
            Message::user("Hi"),
            Message::assistant("Hello!"),
            Message::user("Bye"),
        ]
    }

    #[test]
    fn chatml_format() {
        let s = render(&convo(), &ChatFormat::ChatML, true);
        assert!(s.contains("<|im_start|>system\nYou are helpful.<|im_end|>\n"));
        assert!(s.contains("<|im_start|>user\nHi<|im_end|>\n"));
        assert!(s.contains("<|im_start|>assistant\nHello!<|im_end|>\n"));
        // generation prompt at the end
        assert!(s.ends_with("<|im_start|>assistant\n"));
    }

    #[test]
    fn chatml_without_generation_prompt() {
        let s = render(&convo(), &ChatFormat::ChatML, false);
        assert!(!s.ends_with("<|im_start|>assistant\n"));
        assert!(s.ends_with("<|im_end|>\n"));
    }

    #[test]
    fn llama2_folds_system_into_first_instruction() {
        let s = render(&convo(), &ChatFormat::Llama2, false);
        assert!(s.contains("[INST] <<SYS>>\nYou are helpful.\n<</SYS>>\n\nHi [/INST]"));
        assert!(s.contains("Hello! </s>"));
        // the SYS block appears only once (first turn)
        assert_eq!(s.matches("<<SYS>>").count(), 1);
        assert!(s.contains("<s>[INST] Bye [/INST]"));
    }

    #[test]
    fn alpaca_instruction_response_blocks() {
        let s = render(&convo(), &ChatFormat::Alpaca, true);
        assert!(s.starts_with("You are helpful.\n\n"));
        assert!(s.contains("### Instruction:\nHi\n\n"));
        assert!(s.contains("### Response:\nHello!\n\n"));
        assert!(s.ends_with("### Response:\n"));
    }

    #[test]
    fn custom_template() {
        let t = RoleTemplate {
            system: ("<sys>".into(), "</sys>".into()),
            user: ("<u>".into(), "</u>".into()),
            assistant: ("<a>".into(), "</a>".into()),
            generation_prompt: "<a>".into(),
        };
        let msgs = vec![Message::user("hi"), Message::assistant("yo")];
        let s = render(&msgs, &ChatFormat::Custom(t), true);
        assert_eq!(s, "<u>hi</u><a>yo</a><a>");
    }

    #[test]
    fn no_system_message() {
        let msgs = vec![Message::user("just this")];
        let chatml = render(&msgs, &ChatFormat::ChatML, true);
        assert!(!chatml.contains("system"));
        let llama = render(&msgs, &ChatFormat::Llama2, false);
        assert!(!llama.contains("<<SYS>>"));
        assert!(llama.contains("<s>[INST] just this [/INST]"));
    }

    #[test]
    fn empty_messages() {
        assert_eq!(render(&[], &ChatFormat::ChatML, false), "");
        assert_eq!(
            render(&[], &ChatFormat::ChatML, true),
            "<|im_start|>assistant\n"
        );
    }

    #[test]
    fn serde_round_trip() {
        let fmt = ChatFormat::Custom(RoleTemplate {
            system: ("a".into(), "b".into()),
            user: ("c".into(), "d".into()),
            assistant: ("e".into(), "f".into()),
            generation_prompt: "g".into(),
        });
        let j = serde_json::to_string(&fmt).unwrap();
        let back: ChatFormat = serde_json::from_str(&j).unwrap();
        assert_eq!(fmt, back);
        let m = Message::user("x");
        let jm = serde_json::to_string(&m).unwrap();
        assert_eq!(serde_json::from_str::<Message>(&jm).unwrap(), m);
    }
}
