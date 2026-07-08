//! `sovereign-sentence-split` — break text into sentences, not at every dot.
//!
//! Sentence-level pipelines — semantic chunking, summarization, per-sentence
//! embedding — need text cut into sentences first. The hard part is that a period
//! is not always a sentence end: it also marks abbreviations (`Mr.`, `e.g.`),
//! decimals (`3.14`), and ellipses (`...`). Splitting naively on `.!?` shreds
//! those. This crate is a rule-based segmenter that treats a `.!?` as a boundary
//! only when the context says it really ends a sentence.
//!
//! The rules: a terminator ends a sentence when it is followed by whitespace and
//! then something that looks like a new sentence (an uppercase letter, a digit, a
//! quote, or end of text), *unless* the token just before the period is a known
//! abbreviation, the period sits inside a number (digit on both sides), or it is
//! part of a run of dots (ellipsis), in which case the run is kept with the
//! current sentence. Trailing whitespace is trimmed and empty sentences dropped.
//!
//! [`split`] returns the sentences; [`split_with_offsets`] also returns each
//! sentence's byte span in the original text for downstream alignment.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

/// Schema version of the sentence-split surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Common abbreviations whose trailing period does not end a sentence
/// (compared case-insensitively against the word preceding the period).
pub const ABBREVIATIONS: &[&str] = &[
    "mr", "mrs", "ms", "dr", "prof", "sr", "jr", "st", "vs", "etc", "e.g", "i.e", "eg", "ie",
    "fig", "no", "vol", "pp", "al", "inc", "ltd", "co", "corp", "dept", "est", "min", "max",
    "approx", "appt", "apt", "ave", "blvd", "rd", "u.s", "u.k", "ph.d", "a.m", "p.m",
];

/// Split `text` into trimmed, non-empty sentences.
pub fn split(text: &str) -> Vec<String> {
    split_with_offsets(text)
        .into_iter()
        .map(|(s, _, _)| s)
        .collect()
}

/// Split `text` into `(sentence, start_byte, end_byte)` triples; the span refers
/// to the original (untrimmed) text region the sentence came from.
pub fn split_with_offsets(text: &str) -> Vec<(String, usize, usize)> {
    let chars: Vec<(usize, char)> = text.char_indices().collect();
    let n = chars.len();
    let mut out = Vec::new();
    let mut seg_start = 0usize; // index into `chars`
    let mut i = 0usize;

    while i < n {
        let c = chars[i].1;
        if c == '.' || c == '!' || c == '?' {
            // consume a run of terminators (handles "?!" and "...").
            let mut j = i;
            while j + 1 < n && matches!(chars[j + 1].1, '.' | '!' | '?') {
                j += 1;
            }
            let run_is_ellipsis = j > i && chars[i].1 == '.'; // 2+ dots
            let is_boundary = !run_is_ellipsis
                && self_is_terminal(&chars, i, j, seg_start)
                && followed_by_new_sentence(&chars, j);

            if is_boundary {
                let start_byte = chars[seg_start].0;
                let end_byte = byte_after(&chars, j, text.len());
                push_segment(text, start_byte, end_byte, &mut out);
                // skip the whitespace after the terminator to the next start
                let mut k = j + 1;
                while k < n && chars[k].1.is_whitespace() {
                    k += 1;
                }
                seg_start = k;
                i = k;
                continue;
            } else {
                i = j + 1;
                continue;
            }
        }
        i += 1;
    }
    // trailing segment
    if seg_start < n {
        let start_byte = chars[seg_start].0;
        push_segment(text, start_byte, text.len(), &mut out);
    }
    out
}

/// The byte offset just past character index `j` (or `text_len` if `j` is last).
fn byte_after(chars: &[(usize, char)], j: usize, text_len: usize) -> usize {
    if j + 1 < chars.len() {
        chars[j + 1].0
    } else {
        text_len
    }
}

/// Whether the terminator run is a true sentence-terminator and not an
/// abbreviation period or an in-number decimal.
fn self_is_terminal(chars: &[(usize, char)], i: usize, j: usize, seg_start: usize) -> bool {
    // only single '.' can be an abbreviation/decimal; '!'/'?' always terminal.
    if chars[i].1 != '.' || j != i {
        return true;
    }
    // decimal: digit immediately before and after the dot.
    let before = if i > 0 { Some(chars[i - 1].1) } else { None };
    let after = if i + 1 < chars.len() {
        Some(chars[i + 1].1)
    } else {
        None
    };
    if matches!(before, Some(b) if b.is_ascii_digit())
        && matches!(after, Some(a) if a.is_ascii_digit())
    {
        return false;
    }
    // abbreviation: the alphabetic word ending at i-1 (allowing internal dots
    // like "e.g") is in the list.
    if i > 0 {
        let word = preceding_word(chars, i, seg_start).to_lowercase();
        if !word.is_empty() && ABBREVIATIONS.contains(&word.as_str()) {
            return false;
        }
    }
    true
}

/// The token (letters and internal dots) immediately preceding character `i`.
fn preceding_word(chars: &[(usize, char)], i: usize, seg_start: usize) -> String {
    let mut start = i;
    while start > seg_start {
        let c = chars[start - 1].1;
        if c.is_alphabetic() || c == '.' {
            start -= 1;
        } else {
            break;
        }
    }
    // strip a trailing dot fragment so "e.g" matches (chars[start..i] excludes i)
    chars[start..i].iter().map(|&(_, c)| c).collect()
}

/// Whether what follows the terminator run looks like the start of a new
/// sentence: end of text, or whitespace then an uppercase/digit/quote.
fn followed_by_new_sentence(chars: &[(usize, char)], j: usize) -> bool {
    let n = chars.len();
    if j + 1 >= n {
        return true; // terminator at end of text
    }
    if !chars[j + 1].1.is_whitespace() {
        // e.g. "3.5x" or "word.word" — not a sentence break (unless number case
        // already handled); require whitespace after a terminator.
        return false;
    }
    let mut k = j + 1;
    while k < n && chars[k].1.is_whitespace() {
        k += 1;
    }
    if k >= n {
        return true; // only trailing whitespace
    }
    let c = chars[k].1;
    c.is_uppercase() || c.is_ascii_digit() || c == '"' || c == '\'' || c == '“' || c == '('
}

fn push_segment(text: &str, start: usize, end: usize, out: &mut Vec<(String, usize, usize)>) {
    let raw = &text[start..end];
    let trimmed = raw.trim();
    if !trimmed.is_empty() {
        out.push((trimmed.to_string(), start, end));
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn basic_sentences() {
        let t = "Hello world. How are you? I am fine!";
        assert_eq!(split(t), vec!["Hello world.", "How are you?", "I am fine!"]);
    }

    #[test]
    fn abbreviations_do_not_split() {
        // "Dr." and "Mr." are abbreviations and must not break the sentence; the
        // real boundary is the non-abbreviation period after "early".
        let t = "Dr. Smith met Mr. Jones early. They talked for hours.";
        let s = split(t);
        assert_eq!(s.len(), 2, "got {s:?}");
        assert!(s[0].contains("Dr. Smith"));
        assert!(s[0].contains("Mr. Jones"));
        assert_eq!(s[1], "They talked for hours.");
    }

    #[test]
    fn abbreviation_before_capital_stays_joined() {
        // documented conservative behavior: a known abbreviation suppresses the
        // break even when followed by a capitalized word.
        let t = "We met at 5 p.m. Then we left.";
        let s = split(t);
        assert_eq!(
            s.len(),
            1,
            "abbreviation should keep it one sentence: {s:?}"
        );
    }

    #[test]
    fn decimals_do_not_split() {
        let t = "The value is 3.14 and the ratio 2.5 holds. Done.";
        let s = split(t);
        assert_eq!(s.len(), 2, "got {s:?}");
        assert!(s[0].contains("3.14"));
        assert!(s[0].contains("2.5"));
    }

    #[test]
    fn ellipsis_kept_together() {
        let t = "Well... I suppose so. Maybe.";
        let s = split(t);
        // the ellipsis stays in the first sentence
        assert!(s[0].contains("Well..."), "got {s:?}");
        assert_eq!(s.len(), 2);
    }

    #[test]
    fn question_and_exclaim_runs() {
        let t = "Really?! That is wild. Yes.";
        let s = split(t);
        assert_eq!(s.len(), 3, "got {s:?}");
        assert_eq!(s[0], "Really?!");
    }

    #[test]
    fn no_split_without_following_capital() {
        // lowercase after the dot+space → not treated as a new sentence
        let t = "version 1.2.3 of the tool";
        let s = split(t);
        assert_eq!(s.len(), 1, "got {s:?}");
    }

    #[test]
    fn digit_start_new_sentence() {
        let t = "We waited. 2024 was a strange year.";
        let s = split(t);
        assert_eq!(s.len(), 2, "got {s:?}");
    }

    #[test]
    fn offsets_point_into_original() {
        let t = "One. Two.";
        let spans = split_with_offsets(t);
        assert_eq!(spans.len(), 2);
        // first span trims to "One." within [0, 4)
        assert_eq!(&t[spans[0].1..spans[0].2].trim(), &"One.");
        assert_eq!(spans[1].0, "Two.");
    }

    #[test]
    fn no_terminator_is_one_sentence() {
        assert_eq!(
            split("just a fragment with no end"),
            vec!["just a fragment with no end"]
        );
        assert!(split("   ").is_empty());
        assert!(split("").is_empty());
    }

    #[test]
    fn multibyte_text() {
        let t = "C'est fini. Très bien!";
        let s = split(t);
        assert_eq!(s.len(), 2, "got {s:?}");
        assert!(s[1].contains("Très bien!"));
    }
}
