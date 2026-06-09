//! `sovereign-markdown-strip` — Markdown → plain prose for ingestion.
//!
//! Documents arrive as Markdown, but a chunker, retriever, or embedder wants
//! the *prose*, not the syntax: `# Heading`, `**bold**`, `[text](url)`, and
//! ` ```code``` ` fences are noise that dilutes term matches and wastes the
//! context window. This crate removes that markup while preserving the readable
//! content:
//!
//! * headers (`#`…`######`), list bullets (`-`/`*`/`+`/`1.`), and blockquotes
//!   (`>`) lose their leading marker;
//! * `**bold**`, `*italic*`, `__x__`, and `` `code` `` lose their emphasis
//!   markers — but an underscore *inside* a word (`foo_bar`) is kept, so code
//!   identifiers survive;
//! * `[text](url)` and `![alt](url)` collapse to `text` / `alt`;
//! * code-fence lines (` ``` `) are dropped, but the code between them is kept.
//!
//! It is deterministic and dependency-free.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

/// Schema version of the markdown-strip surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Strip Markdown formatting from `md`, returning plain prose.
pub fn strip(md: &str) -> String {
    let mut out_lines: Vec<String> = Vec::new();
    let mut in_fence = false;

    for line in md.lines() {
        let trimmed = line.trim_start();
        if trimmed.starts_with("```") || trimmed.starts_with("~~~") {
            in_fence = !in_fence;
            continue; // drop the fence marker line
        }
        if in_fence {
            out_lines.push(line.to_string()); // keep code verbatim
            continue;
        }
        out_lines.push(strip_line(trimmed));
    }

    out_lines.join("\n")
}

/// Strip leading block markers and inline markup from a single (already
/// left-trimmed) line.
fn strip_line(line: &str) -> String {
    let line = strip_leading_markers(line);
    strip_inline(line)
}

/// Remove a leading header (`#`+), blockquote (`>`), or list marker.
fn strip_leading_markers(line: &str) -> &str {
    // header: 1–6 '#' then a space
    let hashes = line.chars().take_while(|&c| c == '#').count();
    if (1..=6).contains(&hashes) && line[hashes..].starts_with(' ') {
        return line[hashes + 1..].trim_start();
    }
    // blockquote
    if let Some(rest) = line.strip_prefix("> ").or_else(|| line.strip_prefix(">")) {
        return rest.trim_start();
    }
    // unordered list
    for m in ["- ", "* ", "+ "] {
        if let Some(rest) = line.strip_prefix(m) {
            return rest.trim_start();
        }
    }
    // ordered list: digits then ". "
    let digits = line.chars().take_while(|c| c.is_ascii_digit()).count();
    if digits > 0 && line[digits..].starts_with(". ") {
        return line[digits + 2..].trim_start();
    }
    line
}

/// Remove links/images and emphasis/code markers within a line.
fn strip_inline(line: &str) -> String {
    let no_links = strip_links(line);
    let no_bold = no_links
        .replace("**", "")
        .replace("__", "")
        .replace('`', "");
    let no_star = strip_emphasis(&no_bold, '*');
    strip_emphasis(&no_star, '_')
}

/// Collapse `[text](url)` → `text` and `![alt](url)` → `alt`.
fn strip_links(s: &str) -> String {
    let chars: Vec<char> = s.chars().collect();
    let mut out = String::new();
    let mut i = 0;
    while i < chars.len() {
        // drop a '!' that introduces an image link
        if chars[i] == '!' && chars.get(i + 1) == Some(&'[') {
            i += 1;
            continue;
        }
        if chars[i] == '[' {
            if let Some((text, next)) = parse_link(&chars, i) {
                out.push_str(&text);
                i = next;
                continue;
            }
        }
        out.push(chars[i]);
        i += 1;
    }
    out
}

/// Try to parse `[text](url)` starting at `open` (the `[`). Returns the inner
/// text and the index just past the closing `)`.
fn parse_link(chars: &[char], open: usize) -> Option<(String, usize)> {
    let close = (open + 1..chars.len()).find(|&j| chars[j] == ']')?;
    if chars.get(close + 1) != Some(&'(') {
        return None;
    }
    let paren_close = (close + 2..chars.len()).find(|&j| chars[j] == ')')?;
    let text: String = chars[open + 1..close].iter().collect();
    Some((text, paren_close + 1))
}

/// Drop emphasis markers `m` (`*` or `_`), but keep one that is *inside a word*
/// (alphanumeric on both sides), so identifiers like `foo_bar` survive.
fn strip_emphasis(s: &str, m: char) -> String {
    let chars: Vec<char> = s.chars().collect();
    let mut out = String::new();
    for (i, &c) in chars.iter().enumerate() {
        if c == m {
            let prev_alnum = i > 0 && chars[i - 1].is_alphanumeric();
            let next_alnum = chars.get(i + 1).is_some_and(|n| n.is_alphanumeric());
            if prev_alnum && next_alnum {
                out.push(c); // in-word → keep
            }
            // otherwise it's an emphasis marker → drop
        } else {
            out.push(c);
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn strips_headers() {
        assert_eq!(strip("# Title"), "Title");
        assert_eq!(strip("### Subsection"), "Subsection");
        // 7 hashes is not a header
        assert_eq!(strip("####### nope"), "####### nope");
    }

    #[test]
    fn strips_list_markers() {
        assert_eq!(strip("- item one"), "item one");
        assert_eq!(strip("* item two"), "item two");
        assert_eq!(strip("+ item three"), "item three");
        assert_eq!(strip("1. step one"), "step one");
        assert_eq!(strip("42. step forty-two"), "step forty-two");
    }

    #[test]
    fn strips_blockquote() {
        assert_eq!(strip("> a quote"), "a quote");
        assert_eq!(strip(">no space"), "no space");
    }

    #[test]
    fn strips_emphasis_and_inline_code() {
        assert_eq!(
            strip("**bold** and *italic* and `code`"),
            "bold and italic and code"
        );
        assert_eq!(strip("__also bold__"), "also bold");
    }

    #[test]
    fn keeps_in_word_underscores() {
        // identifiers must survive
        assert_eq!(
            strip("call foo_bar and baz_qux"),
            "call foo_bar and baz_qux"
        );
    }

    #[test]
    fn unwraps_links_and_images() {
        assert_eq!(strip("see [the docs](http://x) here"), "see the docs here");
        assert_eq!(strip("![a cat](cat.png)"), "a cat");
        // malformed link left alone
        assert_eq!(strip("[not a link"), "[not a link");
    }

    #[test]
    fn code_fence_lines_dropped_content_kept() {
        let md = "before\n```rust\nlet x = 1;\n```\nafter";
        assert_eq!(strip(md), "before\nlet x = 1;\nafter");
    }

    #[test]
    fn fenced_content_is_not_inline_stripped() {
        // inside a fence, '*' and '#' are code, not markup
        let md = "```\na * b # c\n```";
        assert_eq!(strip(md), "a * b # c");
    }

    #[test]
    fn combined_document() {
        let md = "# Heading\n\nSome **bold** text with a [link](url).\n- bullet\n";
        let out = strip(md);
        assert!(out.contains("Heading"));
        assert!(out.contains("Some bold text with a link."));
        assert!(out.contains("bullet"));
        assert!(!out.contains('#') && !out.contains("**") && !out.contains("](url)"));
    }
}
