//! `sovereign-answer-extract` — pull the final answer out of reasoning.
//!
//! When a model reasons step by step it ends with the actual answer buried in
//! prose — `... so the answer is 42.` A runtime (and especially
//! self-consistency voting) needs just that answer, normalized, so equivalent
//! conclusions group together. This crate extracts it.
//!
//! [`extract_answer`] honors explicit markers — `Final answer:`, `the answer
//! is`, `Answer:` — taking what follows the last such marker, and falls back to
//! the last non-empty line when there is none. [`extract_number`] pulls the
//! last numeric value, the right move for arithmetic and counting tasks. Both
//! are deterministic and dependency-free.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

/// Schema version of the answer-extract surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Markers that introduce a final answer, most specific first.
const MARKERS: &[&str] = &["final answer:", "the answer is", "answer:", "answer is"];

/// Extract the final answer from `text`.
///
/// Prefers the text following the last occurrence of an answer marker (trimmed,
/// up to the end of that line / sentence); otherwise returns the last non-empty
/// line. Returns an empty string only for empty/whitespace input.
pub fn extract_answer(text: &str) -> String {
    let lower = text.to_lowercase();
    for marker in MARKERS {
        if let Some(pos) = lower.rfind(marker) {
            let after = &text[pos + marker.len()..];
            let answer = first_segment(after);
            if !answer.is_empty() {
                return answer;
            }
        }
    }
    // fallback: last non-empty line
    text.lines()
        .rev()
        .map(str::trim)
        .find(|l| !l.is_empty())
        .unwrap_or("")
        .to_string()
}

/// The first non-empty trimmed segment of `s`, stopping at a line break or a
/// sentence-ending period+space.
fn first_segment(s: &str) -> String {
    let trimmed = s.trim_start();
    let end = trimmed.find(['\n', '\r']).unwrap_or(trimmed.len());
    let line = &trimmed[..end];
    // drop a single trailing period if the whole thing ends like a sentence
    line.trim().trim_end_matches('.').trim().to_string()
}

/// Extract the last numeric value in `text` (integers or decimals, optional
/// leading sign), if any. Useful for arithmetic / counting answers.
pub fn extract_number(text: &str) -> Option<f64> {
    let chars: Vec<char> = text.chars().collect();
    let mut last: Option<f64> = None;
    let mut i = 0;
    while i < chars.len() {
        let c = chars[i];
        let is_num_start = c.is_ascii_digit()
            || (c == '-'
                && i + 1 < chars.len()
                && (chars[i + 1].is_ascii_digit() || chars[i + 1] == '.'))
            || (c == '.' && i + 1 < chars.len() && chars[i + 1].is_ascii_digit());
        if is_num_start {
            let start = i;
            if chars[i] == '-' {
                i += 1;
            }
            let mut seen_dot = false;
            while i < chars.len() && (chars[i].is_ascii_digit() || (chars[i] == '.' && !seen_dot)) {
                if chars[i] == '.' {
                    seen_dot = true;
                }
                i += 1;
            }
            let s: String = chars[start..i].iter().collect();
            if let Ok(n) = s.trim_end_matches('.').parse::<f64>() {
                last = Some(n);
            }
        } else {
            i += 1;
        }
    }
    last
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn extracts_after_answer_marker() {
        assert_eq!(extract_answer("Let me think... Answer: 42"), "42");
        assert_eq!(extract_answer("reasoning. The answer is Paris."), "Paris");
        assert_eq!(extract_answer("blah\nFinal answer: yes\n"), "yes");
    }

    #[test]
    fn prefers_the_last_marker_occurrence() {
        let text = "Answer: draft\nmore thought\nAnswer: final";
        assert_eq!(extract_answer(text), "final");
    }

    #[test]
    fn most_specific_marker_wins() {
        // both "answer:" and "final answer:" present → take final answer
        let text = "Answer: tentative ... Final answer: 7";
        assert_eq!(extract_answer(text), "7");
    }

    #[test]
    fn falls_back_to_last_line() {
        let text = "first line\nsecond line\nthe conclusion";
        assert_eq!(extract_answer(text), "the conclusion");
    }

    #[test]
    fn trailing_period_is_dropped() {
        // the marker takes the rest of the line; a single trailing period goes
        assert_eq!(
            extract_answer("So the answer is yes according to me."),
            "yes according to me"
        );
        assert_eq!(extract_answer("answer: done."), "done");
    }

    #[test]
    fn empty_input_is_empty() {
        assert_eq!(extract_answer(""), "");
        assert_eq!(extract_answer("   \n  "), "");
    }

    #[test]
    fn extracts_last_number() {
        assert_eq!(extract_number("first 1 then 2 then 3"), Some(3.0));
        assert_eq!(extract_number("x = 3.5"), Some(3.5));
        assert_eq!(extract_number("the total is -7"), Some(-7.0));
        assert_eq!(extract_number("value .5 here"), Some(0.5));
    }

    #[test]
    fn no_number_returns_none() {
        assert_eq!(extract_number("no digits here"), None);
        assert_eq!(extract_number(""), None);
    }

    #[test]
    fn number_inside_a_reasoned_answer() {
        let text = "Adding 2 and 2 gives us a result. The answer is 4.";
        assert_eq!(extract_answer(text), "4");
        assert_eq!(extract_number(text), Some(4.0));
    }
}
