//! `sovereign-regex-nfa` — a regex engine you can *step*, for constrained decoding.
//!
//! Matching text against a pattern is the obvious use of a regex; the reason this
//! engine exists is the *other* direction. Constrained decoding keeps a model's
//! output on a format — a date, a number, a JSON-ish shape — by only allowing
//! tokens whose characters the pattern can still accept. That needs a regex you
//! can advance one character at a time and ask, at any point, "is this character
//! allowed next?" and "is what we have so far a complete match?". A
//! Thompson-constructed **NFA**, simulated as a *set of live states*, answers both
//! cheaply.
//!
//! Construction follows Thompson: the pattern is parsed (alternation → concat →
//! repetition → atom) and each piece becomes an NFA fragment wired with epsilon
//! transitions; `*`, `+`, `?`, `|`, grouping, `.`, and character classes
//! `[...]`/`[^...]` (with ranges and the `\d \w \s` escapes) are supported.
//! Simulation tracks the epsilon-closure of the reachable states: [`step`]
//! advances every live state by one character, [`can_consume`] reports whether a
//! character keeps at least one state alive, and [`is_accepting`] reports whether
//! any live state is final.
//!
//! [`Regex::is_match`] is the whole-string convenience; [`Regex::start`] /
//! [`Regex::step`] / [`Regex::is_accepting`] are the incremental interface a
//! constrained sampler drives.
//!
//! Matching is over Unicode scalar values (`char`).
//!
//! [`step`]: Regex::step
//! [`can_consume`]: Regex::can_consume
//! [`is_accepting`]: Regex::is_accepting
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;
use thiserror::Error;

/// Schema version of the regex-nfa surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Errors compiling a pattern.
#[derive(Debug, Clone, PartialEq, Eq, Error)]
pub enum RegexError {
    /// The pattern ended unexpectedly (e.g. an open group or class).
    #[error("unexpected end of pattern")]
    UnexpectedEnd,
    /// An unbalanced or unexpected character at a position.
    #[error("unexpected '{ch}' at position {pos}")]
    Unexpected {
        /// The offending character.
        ch: char,
        /// Byte-agnostic character position.
        pos: usize,
    },
    /// A repetition operator had nothing to repeat.
    #[error("nothing to repeat at position {0}")]
    NothingToRepeat(usize),
}

/// What a transition matches.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
enum Matcher {
    /// A specific character.
    Char(char),
    /// Any character (`.`).
    Any,
    /// A character class: ranges plus negation flag.
    Class {
        ranges: Vec<(char, char)>,
        negated: bool,
    },
}

impl Matcher {
    fn matches(&self, c: char) -> bool {
        match self {
            Matcher::Char(x) => *x == c,
            Matcher::Any => true,
            Matcher::Class { ranges, negated } => {
                let inside = ranges.iter().any(|&(lo, hi)| c >= lo && c <= hi);
                inside != *negated
            }
        }
    }
}

/// An NFA state: epsilon targets plus at most a few matched transitions.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
struct State {
    epsilon: Vec<usize>,
    transitions: Vec<(Matcher, usize)>,
    accept: bool,
}

impl State {
    fn new() -> Self {
        Self {
            epsilon: Vec::new(),
            transitions: Vec::new(),
            accept: false,
        }
    }
}

/// A compiled regular expression as a Thompson NFA.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Regex {
    states: Vec<State>,
    start: usize,
}

/// A fragment with a single start and a single (dangling) accept state.
struct Frag {
    start: usize,
    accept: usize,
}

impl Regex {
    /// Compile `pattern`. The whole pattern must match (anchored at both ends) for
    /// [`is_match`](Self::is_match).
    pub fn new(pattern: &str) -> Result<Self, RegexError> {
        let chars: Vec<char> = pattern.chars().collect();
        let mut p = Parser {
            chars,
            pos: 0,
            states: Vec::new(),
        };
        let frag = if p.chars.is_empty() {
            // empty pattern matches the empty string
            let s = p.new_state();
            Frag {
                start: s,
                accept: s,
            }
        } else {
            let f = p.parse_alt()?;
            if p.pos != p.chars.len() {
                return Err(RegexError::Unexpected {
                    ch: p.chars[p.pos],
                    pos: p.pos,
                });
            }
            f
        };
        p.states[frag.accept].accept = true;
        Ok(Self {
            states: p.states,
            start: frag.start,
        })
    }

    /// The epsilon-closure of a set of states.
    fn closure(&self, set: BTreeSet<usize>) -> BTreeSet<usize> {
        let mut stack: Vec<usize> = set.iter().copied().collect();
        let mut out = set;
        while let Some(s) = stack.pop() {
            for &e in &self.states[s].epsilon {
                if out.insert(e) {
                    stack.push(e);
                }
            }
        }
        out
    }

    /// The initial live-state set (epsilon-closure of the start state).
    pub fn start(&self) -> BTreeSet<usize> {
        let mut s = BTreeSet::new();
        s.insert(self.start);
        self.closure(s)
    }

    /// Advance every live state in `set` by `c`. Returns the new live set, which
    /// is empty if `c` cannot be consumed (a dead end).
    pub fn step(&self, set: &BTreeSet<usize>, c: char) -> BTreeSet<usize> {
        let mut next = BTreeSet::new();
        for &s in set {
            for (m, target) in &self.states[s].transitions {
                if m.matches(c) {
                    next.insert(*target);
                }
            }
        }
        self.closure(next)
    }

    /// Whether `c` keeps at least one state alive from `set` — i.e. the pattern
    /// still permits `c` as the next character.
    pub fn can_consume(&self, set: &BTreeSet<usize>, c: char) -> bool {
        set.iter()
            .any(|&s| self.states[s].transitions.iter().any(|(m, _)| m.matches(c)))
    }

    /// Whether any state in `set` is accepting (the input so far is a full match).
    pub fn is_accepting(&self, set: &BTreeSet<usize>) -> bool {
        set.iter().any(|&s| self.states[s].accept)
    }

    /// Whether `text` matches the whole pattern.
    pub fn is_match(&self, text: &str) -> bool {
        let mut set = self.start();
        for c in text.chars() {
            set = self.step(&set, c);
            if set.is_empty() {
                return false;
            }
        }
        self.is_accepting(&set)
    }

    /// Whether `text` is a viable *prefix* of some matching string — every
    /// character was consumable, even if not yet accepting. Useful for validating
    /// a partial generation.
    pub fn is_prefix(&self, text: &str) -> bool {
        let mut set = self.start();
        for c in text.chars() {
            set = self.step(&set, c);
            if set.is_empty() {
                return false;
            }
        }
        true
    }

    // ── Unanchored (substring) search ──────────────────────────────────────
    //
    // [`is_match`] is anchored: the *whole* string must match. Constrained
    // decoding sometimes needs the opposite question — does the pattern match
    // *anywhere* in a stream? — e.g. to FORBID it (a negated-regex denylist). The
    // trick is standard Thompson simulation with the start state always active:
    // re-seed the start closure at every position so a match may begin there, and
    // an accepting live set means a substring match ends at the current position.

    /// The initial live set for an **unanchored** (substring) search. Drive it
    /// with [`step_unanchored`](Self::step_unanchored); an [`is_accepting`] set
    /// means a match ended at the last consumed character.
    pub fn start_unanchored(&self) -> BTreeSet<usize> {
        self.start()
    }

    /// Advance an unanchored search by `c`: step every live state **and** re-seed
    /// the start closure, so a match may begin at this position. Never empties
    /// (the start state is always alive), so the caller checks [`is_accepting`]
    /// to detect a completed substring match rather than emptiness.
    pub fn step_unanchored(&self, set: &BTreeSet<usize>, c: char) -> BTreeSet<usize> {
        let mut next = self.step(set, c);
        // re-inject the start closure — union of two epsilon-closed sets is itself
        // epsilon-closed, so no re-closure is needed.
        next.extend(self.start());
        next
    }

    /// Whether the pattern matches **any substring** of `text` (unanchored). The
    /// negated-search counterpart of [`is_match`].
    pub fn matches_anywhere(&self, text: &str) -> bool {
        let mut set = self.start_unanchored();
        if self.is_accepting(&set) {
            return true; // pattern accepts the empty string → matches everywhere
        }
        for c in text.chars() {
            set = self.step_unanchored(&set, c);
            if self.is_accepting(&set) {
                return true;
            }
        }
        false
    }
}

/// Recursive-descent parser building NFA fragments directly.
struct Parser {
    chars: Vec<char>,
    pos: usize,
    states: Vec<State>,
}

impl Parser {
    fn new_state(&mut self) -> usize {
        let id = self.states.len();
        self.states.push(State::new());
        id
    }

    fn peek(&self) -> Option<char> {
        self.chars.get(self.pos).copied()
    }

    /// alt := concat ('|' concat)*
    fn parse_alt(&mut self) -> Result<Frag, RegexError> {
        let mut left = self.parse_concat()?;
        while self.peek() == Some('|') {
            self.pos += 1;
            let right = self.parse_concat()?;
            let start = self.new_state();
            let accept = self.new_state();
            self.states[start].epsilon.push(left.start);
            self.states[start].epsilon.push(right.start);
            self.states[left.accept].epsilon.push(accept);
            self.states[right.accept].epsilon.push(accept);
            left = Frag { start, accept };
        }
        Ok(left)
    }

    /// concat := repeat*
    fn parse_concat(&mut self) -> Result<Frag, RegexError> {
        // an empty concatenation (e.g. before '|' or ')') matches empty.
        if matches!(self.peek(), None | Some('|') | Some(')')) {
            let s = self.new_state();
            return Ok(Frag {
                start: s,
                accept: s,
            });
        }
        let mut frag = self.parse_repeat()?;
        while !matches!(self.peek(), None | Some('|') | Some(')')) {
            let next = self.parse_repeat()?;
            self.states[frag.accept].epsilon.push(next.start);
            frag = Frag {
                start: frag.start,
                accept: next.accept,
            };
        }
        Ok(frag)
    }

    /// repeat := atom ('*' | '+' | '?')?
    fn parse_repeat(&mut self) -> Result<Frag, RegexError> {
        let atom = self.parse_atom()?;
        match self.peek() {
            Some('*') => {
                self.pos += 1;
                let start = self.new_state();
                let accept = self.new_state();
                self.states[start].epsilon.push(atom.start);
                self.states[start].epsilon.push(accept);
                self.states[atom.accept].epsilon.push(atom.start);
                self.states[atom.accept].epsilon.push(accept);
                Ok(Frag { start, accept })
            }
            Some('+') => {
                self.pos += 1;
                let accept = self.new_state();
                self.states[atom.accept].epsilon.push(atom.start);
                self.states[atom.accept].epsilon.push(accept);
                Ok(Frag {
                    start: atom.start,
                    accept,
                })
            }
            Some('?') => {
                self.pos += 1;
                let start = self.new_state();
                let accept = self.new_state();
                self.states[start].epsilon.push(atom.start);
                self.states[start].epsilon.push(accept);
                self.states[atom.accept].epsilon.push(accept);
                Ok(Frag { start, accept })
            }
            _ => Ok(atom),
        }
    }

    /// atom := '(' alt ')' | '[' class ']' | '.' | escape | literal
    fn parse_atom(&mut self) -> Result<Frag, RegexError> {
        match self.peek() {
            None => Err(RegexError::UnexpectedEnd),
            Some('(') => {
                self.pos += 1;
                let inner = self.parse_alt()?;
                if self.peek() != Some(')') {
                    return Err(RegexError::UnexpectedEnd);
                }
                self.pos += 1;
                Ok(inner)
            }
            Some(')') | Some('|') | Some('*') | Some('+') | Some('?') => {
                Err(RegexError::NothingToRepeat(self.pos))
            }
            Some('[') => {
                self.pos += 1;
                self.parse_class()
            }
            Some('.') => {
                self.pos += 1;
                Ok(self.matcher_frag(Matcher::Any))
            }
            Some('\\') => {
                self.pos += 1;
                let m = self.parse_escape()?;
                Ok(self.matcher_frag(m))
            }
            Some(c) => {
                self.pos += 1;
                Ok(self.matcher_frag(Matcher::Char(c)))
            }
        }
    }

    /// Build a one-transition fragment for `m`.
    fn matcher_frag(&mut self, m: Matcher) -> Frag {
        let start = self.new_state();
        let accept = self.new_state();
        self.states[start].transitions.push((m, accept));
        Frag { start, accept }
    }

    /// Parse an escape sequence after a consumed backslash into a matcher.
    fn parse_escape(&mut self) -> Result<Matcher, RegexError> {
        let c = self.peek().ok_or(RegexError::UnexpectedEnd)?;
        self.pos += 1;
        let m = match c {
            'd' => Matcher::Class {
                ranges: vec![('0', '9')],
                negated: false,
            },
            'w' => Matcher::Class {
                ranges: vec![('a', 'z'), ('A', 'Z'), ('0', '9'), ('_', '_')],
                negated: false,
            },
            's' => Matcher::Class {
                ranges: vec![(' ', ' '), ('\t', '\t'), ('\n', '\n'), ('\r', '\r')],
                negated: false,
            },
            'n' => Matcher::Char('\n'),
            't' => Matcher::Char('\t'),
            'r' => Matcher::Char('\r'),
            other => Matcher::Char(other), // escaped metachar (\., \[, \\ ...)
        };
        Ok(m)
    }

    /// Parse the body of a character class after the consumed '['.
    fn parse_class(&mut self) -> Result<Frag, RegexError> {
        let mut negated = false;
        if self.peek() == Some('^') {
            negated = true;
            self.pos += 1;
        }
        let mut ranges: Vec<(char, char)> = Vec::new();
        loop {
            match self.peek() {
                None => return Err(RegexError::UnexpectedEnd),
                Some(']') => {
                    self.pos += 1;
                    break;
                }
                Some('\\') => {
                    self.pos += 1;
                    // an escape inside a class contributes its matcher's ranges
                    match self.parse_escape()? {
                        Matcher::Char(c) => ranges.push((c, c)),
                        Matcher::Class { ranges: rs, .. } => ranges.extend(rs),
                        Matcher::Any => ranges.push(('\u{0}', char::MAX)),
                    }
                }
                Some(lo) => {
                    self.pos += 1;
                    // range lo-hi?
                    if self.peek() == Some('-') && self.chars.get(self.pos + 1) != Some(&']') {
                        self.pos += 1; // consume '-'
                        let hi = self.peek().ok_or(RegexError::UnexpectedEnd)?;
                        self.pos += 1;
                        ranges.push((lo, hi));
                    } else {
                        ranges.push((lo, lo));
                    }
                }
            }
        }
        Ok(self.matcher_frag(Matcher::Class { ranges, negated }))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn literals_and_concatenation() {
        let re = Regex::new("abc").unwrap();
        assert!(re.is_match("abc"));
        assert!(!re.is_match("ab"));
        assert!(!re.is_match("abcd"));
        assert!(!re.is_match("xbc"));
    }

    #[test]
    fn alternation() {
        let re = Regex::new("cat|dog|bird").unwrap();
        assert!(re.is_match("cat"));
        assert!(re.is_match("dog"));
        assert!(re.is_match("bird"));
        assert!(!re.is_match("fish"));
    }

    #[test]
    fn quantifiers() {
        let star = Regex::new("ab*c").unwrap();
        assert!(star.is_match("ac"));
        assert!(star.is_match("abc"));
        assert!(star.is_match("abbbbc"));
        assert!(!star.is_match("abd"));

        let plus = Regex::new("ab+c").unwrap();
        assert!(!plus.is_match("ac"));
        assert!(plus.is_match("abc"));
        assert!(plus.is_match("abbc"));

        let opt = Regex::new("colou?r").unwrap();
        assert!(opt.is_match("color"));
        assert!(opt.is_match("colour"));
        assert!(!opt.is_match("colouur"));
    }

    #[test]
    fn character_classes() {
        let re = Regex::new("[a-z]+").unwrap();
        assert!(re.is_match("hello"));
        assert!(!re.is_match("Hello"));
        assert!(!re.is_match("hell0"));

        let neg = Regex::new("[^0-9]+").unwrap();
        assert!(neg.is_match("abc"));
        assert!(!neg.is_match("a1c"));
    }

    #[test]
    fn escapes_and_dot() {
        let digits = Regex::new(r"\d+").unwrap();
        assert!(digits.is_match("12345"));
        assert!(!digits.is_match("12a45"));

        let any = Regex::new("a.c").unwrap();
        assert!(any.is_match("abc"));
        assert!(any.is_match("a c"));
        assert!(!any.is_match("ac"));

        let dot = Regex::new(r"a\.c").unwrap(); // literal dot
        assert!(dot.is_match("a.c"));
        assert!(!dot.is_match("abc"));
    }

    #[test]
    fn groups_and_combinations() {
        let re = Regex::new("(ab)+").unwrap();
        assert!(re.is_match("ab"));
        assert!(re.is_match("abab"));
        assert!(!re.is_match("aba"));

        // a simple date-ish pattern
        let date = Regex::new(r"\d\d\d\d-\d\d-\d\d").unwrap();
        assert!(date.is_match("2026-06-09"));
        assert!(!date.is_match("2026/06/09"));
        assert!(!date.is_match("206-06-09"));
    }

    #[test]
    fn empty_pattern_matches_empty() {
        let re = Regex::new("").unwrap();
        assert!(re.is_match(""));
        assert!(!re.is_match("a"));
    }

    #[test]
    fn constrained_decoding_interface() {
        // drive the engine one char at a time, as a constrained sampler would.
        let re = Regex::new(r"[a-z]+@[a-z]+").unwrap(); // toy email-ish
        let mut set = re.start();
        // a valid prefix "ab"
        for c in "ab".chars() {
            assert!(re.can_consume(&set, c));
            set = re.step(&set, c);
        }
        // not yet a full match (no @domain)
        assert!(!re.is_accepting(&set));
        // '@' is allowed, a digit is not
        assert!(re.can_consume(&set, '@'));
        assert!(!re.can_consume(&set, '1'));
        // complete it
        for c in "@x".chars() {
            set = re.step(&set, c);
        }
        assert!(re.is_accepting(&set));
    }

    #[test]
    fn is_prefix_validates_partial_generation() {
        let re = Regex::new("foo[0-9]+").unwrap();
        assert!(re.is_prefix("fo"));
        assert!(re.is_prefix("foo"));
        assert!(re.is_prefix("foo1"));
        assert!(!re.is_prefix("bar"));
        // a viable prefix is not necessarily a full match
        assert!(!re.is_match("foo"));
        assert!(re.is_match("foo1"));
    }

    #[test]
    fn rejects_malformed_patterns() {
        assert!(matches!(Regex::new("(ab"), Err(RegexError::UnexpectedEnd)));
        assert!(matches!(
            Regex::new("*ab"),
            Err(RegexError::NothingToRepeat(_))
        ));
        assert!(matches!(Regex::new("[a-z"), Err(RegexError::UnexpectedEnd)));
    }

    #[test]
    fn matches_anywhere_finds_substrings() {
        // unanchored: the pattern may match any substring, unlike is_match.
        let re = Regex::new(r"\d\d\d").unwrap();
        assert!(re.matches_anywhere("id=427x")); // "427" inside
        assert!(re.matches_anywhere("427"));
        assert!(!re.matches_anywhere("id=42x")); // only two digits in a row
        assert!(!re.matches_anywhere("no digits here"));
        // is_match stays anchored (whole string)
        assert!(!re.is_match("id=427x"));
        assert!(re.is_match("427"));
    }

    #[test]
    fn step_unanchored_detects_a_match_completing_mid_stream() {
        // drive char-by-char; is_accepting flips true exactly when a substring
        // match completes — the basis of a negated-regex denylist plane.
        let re = Regex::new("ab").unwrap();
        let mut set = re.start_unanchored();
        assert!(!re.is_accepting(&set));
        for (c, want) in [('x', false), ('a', false), ('b', true), ('y', false)] {
            set = re.step_unanchored(&set, c);
            assert_eq!(re.is_accepting(&set), want, "after {c:?}");
        }
    }

    #[test]
    fn matches_anywhere_with_alternation_and_classes() {
        let re = Regex::new("cat|dog").unwrap();
        assert!(re.matches_anywhere("the cat sat"));
        assert!(re.matches_anywhere("a dog!"));
        assert!(!re.matches_anywhere("a fish"));
    }

    #[test]
    fn serde_round_trip() {
        let re = Regex::new(r"[a-z]+\d*").unwrap();
        let j = serde_json::to_string(&re).unwrap();
        let back: Regex = serde_json::from_str(&j).unwrap();
        assert_eq!(re, back);
        assert!(back.is_match("abc123"));
        assert!(back.is_match("abc"));
    }
}
