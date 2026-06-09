//! `sovereign-cfg-grammar` — constrain generation to a context-free grammar.
//!
//! Guided decoding keeps a model on the rails of a format: only emit characters
//! that could still lead to a valid output. A regular expression handles flat
//! patterns, but real formats nest — balanced brackets, JSON, arithmetic
//! expressions — and nesting to arbitrary depth is beyond any regular language.
//! That needs a **context-free grammar** and a parser that can answer, at every
//! step, *which terminals are allowed to come next.*
//!
//! This crate is an **Earley recognizer** (Earley, 1970). It parses left to right
//! building a chart of dotted rules — each item says "we are partway through this
//! production, having started at position `j`". Three operations grow the chart:
//! *predict* opens every rule that could begin here, *scan* advances items whose
//! next symbol matches the input character, and *complete* advances the items that
//! were waiting on a non-terminal once it finishes. Nullable (empty-deriving) rules
//! are handled with the standard predict-time completion fix, so empty productions
//! work correctly.
//!
//! Earley parses *any* context-free grammar — ambiguous, left- or right-recursive
//! — in cubic time, and far faster on the near-linear grammars formats use. The
//! payoff for constrained decoding is [`Grammar::allowed_next`]: feed it the text
//! generated so far and it returns the [`Terminal`]s that keep a valid parse alive,
//! plus whether the prefix is already a complete sentence. [`Grammar::accepts`]
//! checks a full string; [`Grammar::is_live_prefix`] asks whether any continuation
//! exists at all (a dead end means the generator painted itself into a corner).
//!
//! Terminals are single characters, character ranges, or explicit sets, so a
//! grammar can express digits, letters, or any byte class without an alternation
//! blow-up. Build grammars with [`GrammarBuilder`].
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::HashSet;

/// Schema version of the grammar surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A terminal symbol: a matcher over a single character.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum Terminal {
    /// Exactly this character.
    Char(char),
    /// Any character in the inclusive range `lo..=hi`.
    Range(char, char),
    /// Any one of the listed characters.
    Set(Vec<char>),
}

impl Terminal {
    /// Whether this terminal matches `c`.
    pub fn matches(&self, c: char) -> bool {
        match self {
            Terminal::Char(t) => *t == c,
            Terminal::Range(lo, hi) => *lo <= c && c <= *hi,
            Terminal::Set(s) => s.contains(&c),
        }
    }
}

/// A grammar symbol: a terminal or a reference to a non-terminal by id.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum Symbol {
    /// A terminal matcher.
    Term(Terminal),
    /// A non-terminal, identified by its index in the grammar.
    NonTerm(usize),
}

impl Symbol {
    /// Convenience: a single-character terminal.
    pub fn ch(c: char) -> Symbol {
        Symbol::Term(Terminal::Char(c))
    }
    /// Convenience: an inclusive character-range terminal.
    pub fn range(lo: char, hi: char) -> Symbol {
        Symbol::Term(Terminal::Range(lo, hi))
    }
    /// Convenience: a reference to non-terminal `id`.
    pub fn nt(id: usize) -> Symbol {
        Symbol::NonTerm(id)
    }
}

/// A production `lhs -> rhs` (an empty `rhs` is an epsilon rule).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
struct Rule {
    lhs: usize,
    rhs: Vec<Symbol>,
}

/// A context-free grammar with a designated start non-terminal.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Grammar {
    rules: Vec<Rule>,
    /// rules grouped by left-hand non-terminal (`by_lhs[nt]` = rule indices).
    by_lhs: Vec<Vec<usize>>,
    start: usize,
    num_nonterminals: usize,
    /// Precomputed: which non-terminals can derive the empty string.
    nullable: Vec<bool>,
}

/// Builds a [`Grammar`]. Reserve non-terminal ids with [`GrammarBuilder::nonterminal`],
/// add productions with [`GrammarBuilder::rule`], then [`GrammarBuilder::build`].
#[derive(Debug, Default, Clone)]
pub struct GrammarBuilder {
    rules: Vec<Rule>,
    num_nonterminals: usize,
}

impl GrammarBuilder {
    /// A fresh builder.
    pub fn new() -> Self {
        Self::default()
    }

    /// Reserve and return a new non-terminal id.
    pub fn nonterminal(&mut self) -> usize {
        let id = self.num_nonterminals;
        self.num_nonterminals += 1;
        id
    }

    /// Add a production `lhs -> rhs`. An empty `rhs` is an epsilon rule.
    pub fn rule(&mut self, lhs: usize, rhs: Vec<Symbol>) -> &mut Self {
        self.rules.push(Rule { lhs, rhs });
        self
    }

    /// Finalize the grammar with `start` as the start non-terminal.
    ///
    /// # Panics
    /// Panics if `start`, or any symbol, references a non-terminal id that was
    /// never reserved with [`GrammarBuilder::nonterminal`].
    pub fn build(self, start: usize) -> Grammar {
        let n = self.num_nonterminals;
        assert!(start < n, "start non-terminal {start} out of range");
        for r in &self.rules {
            assert!(r.lhs < n, "rule lhs {} out of range", r.lhs);
            for s in &r.rhs {
                if let Symbol::NonTerm(id) = s {
                    assert!(*id < n, "rule references non-terminal {id} out of range");
                }
            }
        }
        let mut by_lhs = vec![Vec::new(); n];
        for (i, r) in self.rules.iter().enumerate() {
            by_lhs[r.lhs].push(i);
        }
        let nullable = compute_nullable(&self.rules, n);
        Grammar {
            rules: self.rules,
            by_lhs,
            start,
            num_nonterminals: n,
            nullable,
        }
    }
}

/// Fixpoint computation of the nullable (empty-deriving) non-terminals.
fn compute_nullable(rules: &[Rule], n: usize) -> Vec<bool> {
    let mut nullable = vec![false; n];
    let mut changed = true;
    while changed {
        changed = false;
        for r in rules {
            if nullable[r.lhs] {
                continue;
            }
            // a rule makes its lhs nullable if every rhs symbol is nullable.
            let all_null = r.rhs.iter().all(|s| match s {
                Symbol::Term(_) => false,
                Symbol::NonTerm(id) => nullable[*id],
            });
            if all_null {
                nullable[r.lhs] = true;
                changed = true;
            }
        }
    }
    nullable
}

/// An Earley item: dotted rule `rule[dot]` with the dot at `dot`, begun at input
/// position `origin`.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
struct Item {
    rule: usize,
    dot: usize,
    origin: usize,
}

/// The result of asking what may come after a prefix.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct NextSet {
    /// Terminals that could legally be scanned next.
    pub terminals: Vec<Terminal>,
    /// Whether the prefix is itself a complete sentence of the grammar.
    pub complete: bool,
}

impl NextSet {
    /// Whether `c` is an allowed next character.
    pub fn allows(&self, c: char) -> bool {
        self.terminals.iter().any(|t| t.matches(c))
    }
    /// Whether the prefix is a dead end: nothing may follow and it is not complete.
    pub fn is_dead(&self) -> bool {
        self.terminals.is_empty() && !self.complete
    }
}

impl Grammar {
    /// Number of non-terminals.
    pub fn num_nonterminals(&self) -> usize {
        self.num_nonterminals
    }

    /// Whether non-terminal `id` can derive the empty string.
    pub fn is_nullable(&self, id: usize) -> bool {
        self.nullable.get(id).copied().unwrap_or(false)
    }

    /// Run predict + complete to a fixpoint on state `s`, given the chart so far.
    /// Items are processed in order; newly added ones are reprocessed because the
    /// list grows while we iterate.
    fn close_state(&self, chart: &mut [Vec<Item>], seen: &mut [HashSet<Item>], s: usize) {
        let mut i = 0;
        while i < chart[s].len() {
            let item = chart[s][i];
            let rule = &self.rules[item.rule];
            if item.dot < rule.rhs.len() {
                if let Symbol::NonTerm(nt) = rule.rhs[item.dot] {
                    // PREDICT: open every rule for `nt` starting here.
                    for &ri in &self.by_lhs[nt] {
                        push_item(
                            chart,
                            seen,
                            s,
                            Item {
                                rule: ri,
                                dot: 0,
                                origin: s,
                            },
                        );
                    }
                    // nullable fix: if `nt` can vanish, advance past it now.
                    if self.nullable[nt] {
                        push_item(
                            chart,
                            seen,
                            s,
                            Item {
                                rule: item.rule,
                                dot: item.dot + 1,
                                origin: item.origin,
                            },
                        );
                    }
                }
                // terminals are handled by scan (between states), not here.
            } else {
                // COMPLETE: `rule.lhs` finished; advance items that awaited it.
                let lhs = rule.lhs;
                let origin = item.origin;
                // collect first to avoid borrowing chart mutably while reading.
                let advanced: Vec<Item> = chart[origin]
                    .iter()
                    .filter(|w| {
                        let wr = &self.rules[w.rule];
                        w.dot < wr.rhs.len() && wr.rhs[w.dot] == Symbol::NonTerm(lhs)
                    })
                    .map(|w| Item {
                        rule: w.rule,
                        dot: w.dot + 1,
                        origin: w.origin,
                    })
                    .collect();
                for a in advanced {
                    push_item(chart, seen, s, a);
                }
            }
            i += 1;
        }
    }

    /// Build the Earley chart for `input`, returning one state set per position
    /// `0..=input.len()`. Stops early (returns a short chart) if a state becomes
    /// empty, meaning the prefix is unparseable.
    fn parse_chart(&self, input: &[char]) -> Vec<Vec<Item>> {
        let n = input.len();
        let mut chart: Vec<Vec<Item>> = vec![Vec::new(); n + 1];
        let mut seen: Vec<HashSet<Item>> = vec![HashSet::new(); n + 1];

        // seed S[0] with the start rules.
        for &ri in &self.by_lhs[self.start] {
            let it = Item {
                rule: ri,
                dot: 0,
                origin: 0,
            };
            if seen[0].insert(it) {
                chart[0].push(it);
            }
        }

        for pos in 0..=n {
            self.close_state(&mut chart, &mut seen, pos);
            if pos < n {
                // SCAN: advance items whose next symbol matches input[pos].
                let c = input[pos];
                let mut scanned = Vec::new();
                for item in &chart[pos] {
                    let rule = &self.rules[item.rule];
                    if item.dot < rule.rhs.len() {
                        if let Symbol::Term(t) = &rule.rhs[item.dot] {
                            if t.matches(c) {
                                scanned.push(Item {
                                    rule: item.rule,
                                    dot: item.dot + 1,
                                    origin: item.origin,
                                });
                            }
                        }
                    }
                }
                for it in scanned {
                    if seen[pos + 1].insert(it) {
                        chart[pos + 1].push(it);
                    }
                }
                if chart[pos + 1].is_empty() {
                    // unparseable prefix: truncate and stop.
                    chart.truncate(pos + 2);
                    return chart;
                }
            }
        }
        chart
    }

    /// Whether the final state contains a completed start rule spanning the whole
    /// input (origin 0, dot at end).
    fn state_accepts(&self, state: &[Item]) -> bool {
        state.iter().any(|it| {
            let rule = &self.rules[it.rule];
            rule.lhs == self.start && it.origin == 0 && it.dot == rule.rhs.len()
        })
    }

    /// Whether `input` is a complete sentence of the grammar.
    pub fn accepts(&self, input: &str) -> bool {
        let chars: Vec<char> = input.chars().collect();
        let chart = self.parse_chart(&chars);
        // a truncated chart (dead prefix) cannot accept the full string.
        if chart.len() != chars.len() + 1 {
            return false;
        }
        self.state_accepts(&chart[chars.len()])
    }

    /// The terminals that may legally follow `prefix`, and whether `prefix` is
    /// already complete. An unparseable prefix yields an empty, non-complete set.
    pub fn allowed_next(&self, prefix: &str) -> NextSet {
        let chars: Vec<char> = prefix.chars().collect();
        let chart = self.parse_chart(&chars);
        if chart.len() != chars.len() + 1 {
            return NextSet {
                terminals: Vec::new(),
                complete: false,
            };
        }
        let last = &chart[chars.len()];
        let mut terminals: Vec<Terminal> = Vec::new();
        for item in last {
            let rule = &self.rules[item.rule];
            if item.dot < rule.rhs.len() {
                if let Symbol::Term(t) = &rule.rhs[item.dot] {
                    if !terminals.contains(t) {
                        terminals.push(t.clone());
                    }
                }
            }
        }
        NextSet {
            terminals,
            complete: self.state_accepts(last),
        }
    }

    /// Whether any continuation of `prefix` is accepted — i.e. the prefix is not a
    /// dead end. A complete prefix is also live.
    pub fn is_live_prefix(&self, prefix: &str) -> bool {
        let ns = self.allowed_next(prefix);
        !ns.is_dead()
    }
}

/// Append `item` to state `s` if not already present.
fn push_item(chart: &mut [Vec<Item>], seen: &mut [HashSet<Item>], s: usize, item: Item) {
    if seen[s].insert(item) {
        chart[s].push(item);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// S -> '(' S ')' S | ε  (balanced parentheses, the classic non-regular language)
    fn balanced() -> Grammar {
        let mut b = GrammarBuilder::new();
        let s = b.nonterminal();
        b.rule(
            s,
            vec![
                Symbol::ch('('),
                Symbol::nt(s),
                Symbol::ch(')'),
                Symbol::nt(s),
            ],
        );
        b.rule(s, vec![]); // epsilon
        b.build(s)
    }

    #[test]
    fn balanced_accepts_valid() {
        let g = balanced();
        for ok in ["", "()", "()()", "(())", "(()())", "((()))()"] {
            assert!(g.accepts(ok), "should accept {ok:?}");
        }
    }

    #[test]
    fn balanced_rejects_invalid() {
        let g = balanced();
        for bad in ["(", ")", ")(", "(()", "())", "(()))"] {
            assert!(!g.accepts(bad), "should reject {bad:?}");
        }
    }

    #[test]
    fn balanced_allowed_next_guides_decoding() {
        let g = balanced();
        // empty: may open a paren, and empty is itself complete.
        let n0 = g.allowed_next("");
        assert!(n0.allows('('));
        assert!(!n0.allows(')'));
        assert!(n0.complete);
        // after "(": may open another or close this one; not complete.
        let n1 = g.allowed_next("(");
        assert!(n1.allows('('));
        assert!(n1.allows(')'));
        assert!(!n1.complete);
        // after "()": balanced again — complete, may open more.
        let n2 = g.allowed_next("()");
        assert!(n2.complete);
        assert!(n2.allows('('));
    }

    #[test]
    fn balanced_dead_end_detected() {
        let g = balanced();
        // a closing paren with nothing open is a dead prefix.
        let ns = g.allowed_next(")");
        assert!(ns.is_dead());
        assert!(!g.is_live_prefix(")"));
        // a live, incomplete prefix:
        assert!(g.is_live_prefix("(()"));
    }

    /// Number -> Digit Rest ; Rest -> Digit Rest | ε ; Digit -> [0-9]
    fn number() -> Grammar {
        let mut b = GrammarBuilder::new();
        let num = b.nonterminal();
        let rest = b.nonterminal();
        let digit = b.nonterminal();
        b.rule(num, vec![Symbol::nt(digit), Symbol::nt(rest)]);
        b.rule(rest, vec![Symbol::nt(digit), Symbol::nt(rest)]);
        b.rule(rest, vec![]);
        b.rule(digit, vec![Symbol::range('0', '9')]);
        b.build(num)
    }

    #[test]
    fn number_with_ranges() {
        let g = number();
        assert!(g.accepts("0"));
        assert!(g.accepts("12345"));
        assert!(!g.accepts(""));
        assert!(!g.accepts("12a"));
        // allowed next after some digits: any digit, and it's complete.
        let ns = g.allowed_next("12");
        assert!(ns.allows('7'));
        assert!(!ns.allows('x'));
        assert!(ns.complete);
        // at the very start, a digit is required and empty is not complete.
        let start = g.allowed_next("");
        assert!(start.allows('0'));
        assert!(!start.complete);
    }

    /// Right-recursive, ambiguous-ish expression grammar:
    /// E -> E '+' E | '(' E ')' | D ; D -> [0-9]
    fn expr() -> Grammar {
        let mut b = GrammarBuilder::new();
        let e = b.nonterminal();
        let d = b.nonterminal();
        b.rule(e, vec![Symbol::nt(e), Symbol::ch('+'), Symbol::nt(e)]);
        b.rule(e, vec![Symbol::ch('('), Symbol::nt(e), Symbol::ch(')')]);
        b.rule(e, vec![Symbol::nt(d)]);
        b.rule(d, vec![Symbol::range('0', '9')]);
        b.build(e)
    }

    #[test]
    fn ambiguous_left_recursive_expression() {
        let g = expr();
        assert!(g.accepts("1"));
        assert!(g.accepts("1+2"));
        assert!(g.accepts("1+2+3"));
        assert!(g.accepts("(1+2)+3"));
        assert!(g.accepts("((1))"));
        assert!(!g.accepts("1+"));
        assert!(!g.accepts("+1"));
        assert!(!g.accepts("(1+2"));
    }

    #[test]
    fn nullable_chain() {
        // A -> B ; B -> C ; C -> ε  — everything derives empty.
        let mut b = GrammarBuilder::new();
        let a = b.nonterminal();
        let bb = b.nonterminal();
        let c = b.nonterminal();
        b.rule(a, vec![Symbol::nt(bb)]);
        b.rule(bb, vec![Symbol::nt(c)]);
        b.rule(c, vec![]);
        let g = b.build(a);
        assert!(g.is_nullable(a));
        assert!(g.is_nullable(bb));
        assert!(g.is_nullable(c));
        assert!(g.accepts(""));
        assert!(!g.accepts("x"));
    }

    #[test]
    fn set_terminal() {
        // Greeting -> ('h'|'H') 'i'
        let mut b = GrammarBuilder::new();
        let g = b.nonterminal();
        b.rule(
            g,
            vec![Symbol::Term(Terminal::Set(vec!['h', 'H'])), Symbol::ch('i')],
        );
        let gram = b.build(g);
        assert!(gram.accepts("hi"));
        assert!(gram.accepts("Hi"));
        assert!(!gram.accepts("hello"));
        let ns = gram.allowed_next("");
        assert!(ns.allows('h') && ns.allows('H') && !ns.allows('i'));
    }

    #[test]
    fn deep_nesting_does_not_blow_up() {
        let g = balanced();
        let deep: String = "(".repeat(200);
        let closed: String = format!("{deep}{}", ")".repeat(200));
        assert!(g.is_live_prefix(&deep));
        assert!(g.accepts(&closed));
    }

    #[test]
    fn serde_round_trip() {
        let g = balanced();
        let j = serde_json::to_string(&g).unwrap();
        let back: Grammar = serde_json::from_str(&j).unwrap();
        assert_eq!(g, back);
        assert!(back.accepts("(())"));
    }

    #[test]
    fn schema_version_is_set() {
        assert_eq!(SCHEMA_VERSION, "1.0.0");
    }
}
