//! `sovereign-balanced-constrain` — keep generated brackets balanced, live.
//!
//! Constraining a model to a *regular* pattern (a regex) cannot enforce balanced
//! nesting: "every `{` is eventually closed by a matching `}`" is not a regular
//! property, it is **context-free** — the Dyck language. Enforcing it needs a
//! pushdown automaton: a stack of the delimiters opened so far. This crate is that
//! stack, driven one character at a time so a constrained sampler can ask, before
//! emitting a token, "would this character keep things balanced?".
//!
//! A [`BalanceConstraint`] knows the delimiter pairs (`()`, `[]`, `{}` by default)
//! and the quote characters that open string literals (`"` by default). A
//! [`BalanceState`] holds the open-delimiter stack and whether we are inside a
//! string (where brackets are literal text, not structure). [`step`] advances the
//! state by a character or rejects it; [`can_emit`] is the non-mutating check a
//! sampler uses to mask tokens; [`is_balanced`] reports when the output is a
//! complete, closeable structure (stack empty, not mid-string).
//!
//! Pair it with a regex or grammar for the token-level shape and this for the
//! nesting, and a model's structured output stays well-formed by construction.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Schema version of the balanced-constrain surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A balanced-delimiter constraint.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct BalanceConstraint {
    /// open delimiter → its required closer.
    pairs: HashMap<char, char>,
    /// closer → its opener (derived).
    closers: HashMap<char, char>,
    /// characters that open/close a string literal (brackets inside are literal).
    quotes: Vec<char>,
    /// the escape character inside strings.
    escape: char,
}

impl Default for BalanceConstraint {
    fn default() -> Self {
        Self::new(&[('(', ')'), ('[', ']'), ('{', '}')], &['"'], '\\')
    }
}

impl BalanceConstraint {
    /// A constraint with the given delimiter `pairs`, string `quotes`, and string
    /// `escape` character.
    pub fn new(pairs: &[(char, char)], quotes: &[char], escape: char) -> Self {
        let mut p = HashMap::new();
        let mut c = HashMap::new();
        for &(open, close) in pairs {
            p.insert(open, close);
            c.insert(close, open);
        }
        Self {
            pairs: p,
            closers: c,
            quotes: quotes.to_vec(),
            escape,
        }
    }

    /// A fresh starting state.
    pub fn start(&self) -> BalanceState {
        BalanceState::default()
    }

    /// Advance `state` by character `c`. Returns the new state if `c` is allowed
    /// (keeps the structure valid), or `None` if it would be illegal (a closer
    /// that doesn't match the top of the stack).
    pub fn step(&self, state: &BalanceState, c: char) -> Option<BalanceState> {
        let mut s = state.clone();
        if let Some(active) = s.string_delim {
            // inside a string: only an unescaped matching quote closes it.
            if s.escaped {
                s.escaped = false;
            } else if c == self.escape {
                s.escaped = true;
            } else if c == active {
                s.string_delim = None;
            }
            // any other char is literal text inside the string.
            return Some(s);
        }
        // not in a string.
        if self.quotes.contains(&c) {
            s.string_delim = Some(c);
            return Some(s);
        }
        if self.pairs.contains_key(&c) {
            s.stack.push(c);
            return Some(s);
        }
        if let Some(&opener) = self.closers.get(&c) {
            // a closer is legal only if it matches the top of the stack.
            match s.stack.last() {
                Some(&top) if top == opener => {
                    s.stack.pop();
                    Some(s)
                }
                _ => None, // unbalanced or wrong closer
            }
        } else {
            // an ordinary character is always allowed.
            Some(s)
        }
    }

    /// Whether emitting `c` from `state` is legal (non-mutating check for masking).
    pub fn can_emit(&self, state: &BalanceState, c: char) -> bool {
        self.step(state, c).is_some()
    }

    /// Run a whole string through, returning the final state, or `None` at the
    /// first illegal character.
    pub fn run(&self, text: &str) -> Option<BalanceState> {
        let mut s = self.start();
        for c in text.chars() {
            s = self.step(&s, c)?;
        }
        Some(s)
    }

    /// Whether `text` is balanced (and string-closed) end to end.
    pub fn is_balanced(&self, text: &str) -> bool {
        self.run(text).map(|s| s.is_complete()).unwrap_or(false)
    }
}

/// The live state of the pushdown automaton.
#[derive(Debug, Clone, PartialEq, Eq, Default, Serialize, Deserialize)]
pub struct BalanceState {
    /// Stack of currently-open delimiter characters.
    stack: Vec<char>,
    /// The quote char of the string currently open, if any.
    string_delim: Option<char>,
    /// Whether the next character inside a string is escaped.
    escaped: bool,
}

impl BalanceState {
    /// The current nesting depth (number of unclosed delimiters).
    pub fn depth(&self) -> usize {
        self.stack.len()
    }

    /// Whether we are currently inside a string literal.
    pub fn in_string(&self) -> bool {
        self.string_delim.is_some()
    }

    /// Whether the structure is complete: nothing open and not inside a string.
    pub fn is_complete(&self) -> bool {
        self.stack.is_empty() && self.string_delim.is_none()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn balanced_strings_pass() {
        let c = BalanceConstraint::default();
        assert!(c.is_balanced("{}"));
        assert!(c.is_balanced("[1, 2, {\"a\": [3]}]"));
        assert!(c.is_balanced("()"));
        assert!(c.is_balanced("plain text no brackets"));
    }

    #[test]
    fn unbalanced_strings_fail() {
        let c = BalanceConstraint::default();
        assert!(!c.is_balanced("{")); // unclosed
        assert!(!c.is_balanced("}")); // closer with empty stack
        assert!(!c.is_balanced("[}")); // mismatched
        assert!(!c.is_balanced("([)]")); // crossed nesting
    }

    #[test]
    fn brackets_inside_strings_are_literal() {
        let c = BalanceConstraint::default();
        // the "}" inside the string must not close the object
        assert!(c.is_balanced("{\"k\": \"a } b ] c )\"}"));
        // an unclosed string is not complete
        assert!(!c.is_balanced("{\"unterminated"));
    }

    #[test]
    fn escaped_quote_does_not_close_string() {
        let c = BalanceConstraint::default();
        assert!(c.is_balanced("\"she said \\\"hi\\\"\""));
        // the escaped quote keeps the string open until the real closer
        let st = c.run("\"a\\\"b").unwrap();
        assert!(st.in_string());
    }

    #[test]
    fn incremental_can_emit() {
        let c = BalanceConstraint::default();
        let s = c.start();
        // at the start, '{' and 'a' are fine; '}' is not (nothing to close)
        assert!(c.can_emit(&s, '{'));
        assert!(c.can_emit(&s, 'a'));
        assert!(!c.can_emit(&s, '}'));
        // after '{', '}' becomes legal
        let s = c.step(&s, '{').unwrap();
        assert!(c.can_emit(&s, '}'));
        assert!(!c.can_emit(&s, ']')); // wrong closer
        assert_eq!(s.depth(), 1);
    }

    #[test]
    fn depth_and_completion_tracking() {
        let c = BalanceConstraint::default();
        let mut s = c.start();
        for ch in "{[".chars() {
            s = c.step(&s, ch).unwrap();
        }
        assert_eq!(s.depth(), 2);
        assert!(!s.is_complete());
        for ch in "]}".chars() {
            s = c.step(&s, ch).unwrap();
        }
        assert!(s.is_complete());
    }

    #[test]
    fn custom_delimiters() {
        // a constraint over angle brackets and single quotes
        let c = BalanceConstraint::new(&[('<', '>')], &['\''], '\\');
        assert!(c.is_balanced("<a<b>c>"));
        assert!(!c.is_balanced("<a"));
        assert!(c.is_balanced("'<not a tag>'")); // brackets literal in string
    }

    #[test]
    fn illegal_step_returns_none() {
        let c = BalanceConstraint::default();
        let s = c.start();
        assert!(c.step(&s, ')').is_none()); // closer on empty stack
    }

    #[test]
    fn serde_round_trip() {
        let c = BalanceConstraint::default();
        let j = serde_json::to_string(&c).unwrap();
        let back: BalanceConstraint = serde_json::from_str(&j).unwrap();
        assert_eq!(c, back);
        let s = c.run("{[").unwrap();
        let js = serde_json::to_string(&s).unwrap();
        let backs: BalanceState = serde_json::from_str(&js).unwrap();
        assert_eq!(s, backs);
    }
}
