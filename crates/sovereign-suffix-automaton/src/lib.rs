//! `sovereign-suffix-automaton` — the whole substring structure of a string, in linear space.
//!
//! A suffix automaton is the smallest deterministic finite automaton that accepts
//! exactly the substrings of a string. Despite there being `O(n²)` distinct
//! substrings, the automaton has only `O(n)` states and edges and is built **online
//! in linear time** — append one character and a constant-amortized amount of work
//! keeps it minimal. That compactness makes it a workhorse for string indexing.
//!
//! From it, three questions become cheap. **Is this a substring?** Walk the pattern
//! through the transitions in `O(pattern)` ([`contains`](SuffixAutomaton::contains)).
//! **How many distinct substrings does the text have?** Sum `len(v) − len(link(v))`
//! over the states — each state represents a contiguous band of substring lengths —
//! in `O(n)` ([`distinct_substrings`](SuffixAutomaton::distinct_substrings)).
//! **What is the longest substring shared with another string?** Stream that string
//! through the automaton, following suffix links on a miss to back off the match
//! length, and track the best ([`longest_common_substring`](SuffixAutomaton::longest_common_substring)).
//!
//! The construction is the classic Blumer/Crochemore online algorithm: each new
//! character extends the automaton, occasionally **cloning** a state to keep the
//! suffix-link tree correct. [`SuffixAutomaton::build`] builds from a string and
//! [`SuffixAutomaton::extend`] appends a character incrementally.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

/// Schema version of the suffix-automaton surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One automaton state.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
struct State {
    /// Length of the longest substring ending in this state.
    len: usize,
    /// Suffix link (the initial state's link is itself, marked by `usize::MAX`).
    link: usize,
    /// Outgoing transitions by character.
    next: BTreeMap<char, usize>,
}

/// The minimal automaton of all substrings of a string.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SuffixAutomaton {
    states: Vec<State>,
    /// The state representing the whole string built so far.
    last: usize,
    /// Number of characters appended.
    length: usize,
}

const NIL: usize = usize::MAX;

impl Default for SuffixAutomaton {
    fn default() -> Self {
        Self::new()
    }
}

impl SuffixAutomaton {
    /// An empty automaton (accepts only the empty substring).
    pub fn new() -> Self {
        let initial = State {
            len: 0,
            link: NIL,
            next: BTreeMap::new(),
        };
        Self {
            states: vec![initial],
            last: 0,
            length: 0,
        }
    }

    /// Build an automaton for `text`.
    pub fn build(text: &str) -> Self {
        let mut sa = Self::new();
        for c in text.chars() {
            sa.extend(c);
        }
        sa
    }

    /// Number of states.
    pub fn num_states(&self) -> usize {
        self.states.len()
    }
    /// Number of characters in the indexed text.
    pub fn text_len(&self) -> usize {
        self.length
    }

    /// Append one character, keeping the automaton minimal.
    pub fn extend(&mut self, c: char) {
        self.length += 1;
        let cur = self.states.len();
        self.states.push(State {
            len: self.states[self.last].len + 1,
            link: NIL,
            next: BTreeMap::new(),
        });

        let mut p = self.last;
        // add the transition on `c` along the suffix-link chain until one exists.
        while p != NIL && !self.states[p].next.contains_key(&c) {
            self.states[p].next.insert(c, cur);
            p = self.states[p].link;
        }

        if p == NIL {
            self.states[cur].link = 0;
        } else {
            let q = self.states[p].next[&c];
            if self.states[p].len + 1 == self.states[q].len {
                self.states[cur].link = q;
            } else {
                // split q into a clone with the shorter length.
                let clone = self.states.len();
                self.states.push(State {
                    len: self.states[p].len + 1,
                    link: self.states[q].link,
                    next: self.states[q].next.clone(),
                });
                while p != NIL && self.states[p].next.get(&c) == Some(&q) {
                    self.states[p].next.insert(c, clone);
                    p = self.states[p].link;
                }
                self.states[q].link = clone;
                self.states[cur].link = clone;
            }
        }
        self.last = cur;
    }

    /// Whether `pattern` is a substring of the indexed text.
    pub fn contains(&self, pattern: &str) -> bool {
        let mut v = 0usize;
        for c in pattern.chars() {
            match self.states[v].next.get(&c) {
                Some(&t) => v = t,
                None => return false,
            }
        }
        true
    }

    /// The number of distinct non-empty substrings of the indexed text.
    pub fn distinct_substrings(&self) -> u64 {
        let mut total = 0u64;
        for (i, s) in self.states.iter().enumerate() {
            if i == 0 {
                continue;
            }
            let link_len = if s.link == NIL {
                0
            } else {
                self.states[s.link].len
            };
            total += (s.len - link_len) as u64;
        }
        total
    }

    /// The longest substring that appears in both the indexed text and `other`.
    pub fn longest_common_substring(&self, other: &str) -> String {
        let chars: Vec<char> = other.chars().collect();
        let mut v = 0usize;
        let mut l = 0usize;
        let mut best = 0usize;
        let mut best_end = 0usize; // exclusive end index in `chars`
        for (i, &c) in chars.iter().enumerate() {
            if let Some(&t) = self.states[v].next.get(&c) {
                v = t;
                l += 1;
            } else {
                // back off along suffix links until a transition exists or we hit
                // the initial state.
                while v != 0 && !self.states[v].next.contains_key(&c) {
                    v = self.states[v].link;
                    l = self.states[v].len;
                }
                if let Some(&t) = self.states[v].next.get(&c) {
                    v = t;
                    l += 1;
                } else {
                    l = 0;
                }
            }
            if l > best {
                best = l;
                best_end = i + 1;
            }
        }
        chars[best_end - best..best_end].iter().collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashSet;

    /// Brute-force set of all non-empty substrings.
    fn all_substrings(s: &str) -> HashSet<String> {
        let chars: Vec<char> = s.chars().collect();
        let mut set = HashSet::new();
        for i in 0..chars.len() {
            for j in i + 1..=chars.len() {
                set.insert(chars[i..j].iter().collect::<String>());
            }
        }
        set
    }

    fn brute_lcs(a: &str, b: &str) -> usize {
        let av: Vec<char> = a.chars().collect();
        let bv: Vec<char> = b.chars().collect();
        let mut best = 0;
        for i in 0..av.len() {
            for j in i + 1..=av.len() {
                let sub = &av[i..j];
                // does `sub` appear in b?
                if bv.windows(sub.len()).any(|w| w == sub) {
                    best = best.max(sub.len());
                }
            }
        }
        best
    }

    #[test]
    fn contains_substrings() {
        let sa = SuffixAutomaton::build("abcbc");
        for ok in ["a", "abc", "bcbc", "cbc", "abcbc", ""] {
            assert!(sa.contains(ok), "should contain {ok:?}");
        }
        for bad in ["x", "abd", "cba", "abcbcc"] {
            assert!(!sa.contains(bad), "should not contain {bad:?}");
        }
    }

    #[test]
    fn distinct_substring_count_matches_brute() {
        for s in [
            "",
            "a",
            "aa",
            "abc",
            "abab",
            "banana",
            "mississippi",
            "aaaa",
        ] {
            let sa = SuffixAutomaton::build(s);
            assert_eq!(
                sa.distinct_substrings() as usize,
                all_substrings(s).len(),
                "string {s:?}"
            );
        }
    }

    #[test]
    fn longest_common_substring_examples() {
        let sa = SuffixAutomaton::build("abcde");
        assert_eq!(sa.longest_common_substring("xxcdezz"), "cde");
        let sa2 = SuffixAutomaton::build("abab");
        let lcs = sa2.longest_common_substring("baba");
        assert_eq!(lcs.len(), 3); // "aba" or "bab"
        assert!(sa2.contains(&lcs));
    }

    #[test]
    fn lcs_length_matches_brute() {
        let pairs = [
            ("abcde", "cdefg"),
            ("banana", "ananas"),
            ("mississippi", "missouri"),
            ("abcabcabc", "xyzabcxyz"),
            ("hello", "world"),
        ];
        for (a, b) in pairs {
            let sa = SuffixAutomaton::build(a);
            let lcs = sa.longest_common_substring(b);
            assert_eq!(lcs.len(), brute_lcs(a, b), "pair {a:?},{b:?} got {lcs:?}");
        }
    }

    #[test]
    fn no_common_substring() {
        let sa = SuffixAutomaton::build("aaaa");
        assert_eq!(sa.longest_common_substring("bbbb"), "");
    }

    #[test]
    fn empty_and_single() {
        let e = SuffixAutomaton::build("");
        assert_eq!(e.distinct_substrings(), 0);
        assert!(e.contains(""));
        assert!(!e.contains("a"));
        let s = SuffixAutomaton::build("z");
        assert_eq!(s.distinct_substrings(), 1);
        assert!(s.contains("z"));
    }

    #[test]
    fn state_count_is_linear() {
        // a suffix automaton has at most 2n-1 states for n >= 2.
        let s = "abcdefghijklmnop";
        let sa = SuffixAutomaton::build(s);
        assert!(sa.num_states() < 2 * s.chars().count());
        assert_eq!(sa.text_len(), 16);
    }

    #[test]
    fn incremental_extend_matches_build() {
        let mut sa = SuffixAutomaton::new();
        for c in "abracadabra".chars() {
            sa.extend(c);
        }
        let built = SuffixAutomaton::build("abracadabra");
        assert_eq!(sa.distinct_substrings(), built.distinct_substrings());
        assert!(sa.contains("cadabra"));
    }

    #[test]
    fn unicode_text() {
        let sa = SuffixAutomaton::build("café déjà");
        assert!(sa.contains("é dé"));
        assert!(!sa.contains("zz"));
    }

    #[test]
    fn serde_round_trip() {
        let sa = SuffixAutomaton::build("mississippi");
        let j = serde_json::to_string(&sa).unwrap();
        let back: SuffixAutomaton = serde_json::from_str(&j).unwrap();
        assert_eq!(sa, back);
        assert_eq!(sa.distinct_substrings(), back.distinct_substrings());
    }

    #[test]
    fn schema_version_is_set() {
        assert_eq!(SCHEMA_VERSION, "1.0.0");
    }
}
