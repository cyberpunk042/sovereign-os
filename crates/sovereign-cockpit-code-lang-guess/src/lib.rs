//! `sovereign-cockpit-code-lang-guess` — guess code language.
//!
//! Tries (in order):
//!   1. Filename extension (rs/py/ts/js/rb/go/c/cpp/h/sh/json/yaml/toml/md).
//!   2. Shebang (`#!/usr/bin/env python` → Python).
//!   3. Returns `Language::Unknown`.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Language.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Language {
    /// Rust.
    Rust,
    /// Python.
    Python,
    /// TypeScript.
    TypeScript,
    /// JavaScript.
    JavaScript,
    /// Ruby.
    Ruby,
    /// Go.
    Go,
    /// C.
    C,
    /// C++.
    Cpp,
    /// Header.
    Header,
    /// Shell.
    Shell,
    /// JSON.
    Json,
    /// YAML.
    Yaml,
    /// TOML.
    Toml,
    /// Markdown.
    Markdown,
    /// Unknown.
    Unknown,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct CodeLangGuess {
    /// Schema version.
    pub schema_version: String,
}

/// Errors.
#[derive(Debug, Error)]
pub enum GuessError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
}

impl CodeLangGuess {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
        }
    }

    /// Guess.
    pub fn guess(&self, filename: &str, first_line: &str) -> Language {
        // 1) extension.
        if let Some(ext) = filename.rsplit('.').next() {
            let l = ext.to_lowercase();
            let by_ext = match l.as_str() {
                "rs" => Some(Language::Rust),
                "py" => Some(Language::Python),
                "ts" => Some(Language::TypeScript),
                "js" => Some(Language::JavaScript),
                "rb" => Some(Language::Ruby),
                "go" => Some(Language::Go),
                "c" => Some(Language::C),
                "cpp" | "cc" | "cxx" => Some(Language::Cpp),
                "h" | "hpp" => Some(Language::Header),
                "sh" | "bash" | "zsh" => Some(Language::Shell),
                "json" => Some(Language::Json),
                "yaml" | "yml" => Some(Language::Yaml),
                "toml" => Some(Language::Toml),
                "md" | "markdown" => Some(Language::Markdown),
                _ => None,
            };
            if let Some(l) = by_ext {
                return l;
            }
        }
        // 2) shebang.
        if first_line.starts_with("#!") {
            let lower = first_line.to_lowercase();
            if lower.contains("python") {
                return Language::Python;
            }
            if lower.contains("ruby") {
                return Language::Ruby;
            }
            if lower.contains("node") {
                return Language::JavaScript;
            }
            if lower.contains("bash") || lower.contains("/sh") || lower.contains("zsh") {
                return Language::Shell;
            }
        }
        Language::Unknown
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), GuessError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(GuessError::SchemaMismatch);
        }
        Ok(())
    }
}

impl Default for CodeLangGuess {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rust_by_ext() {
        let g = CodeLangGuess::new();
        assert_eq!(g.guess("lib.rs", ""), Language::Rust);
    }

    #[test]
    fn python_by_ext() {
        let g = CodeLangGuess::new();
        assert_eq!(g.guess("script.py", ""), Language::Python);
    }

    #[test]
    fn cpp_variants() {
        let g = CodeLangGuess::new();
        assert_eq!(g.guess("a.cpp", ""), Language::Cpp);
        assert_eq!(g.guess("a.cc", ""), Language::Cpp);
        assert_eq!(g.guess("a.cxx", ""), Language::Cpp);
    }

    #[test]
    fn shebang_python() {
        let g = CodeLangGuess::new();
        assert_eq!(g.guess("noext", "#!/usr/bin/env python3"), Language::Python);
    }

    #[test]
    fn shebang_shell() {
        let g = CodeLangGuess::new();
        assert_eq!(g.guess("run", "#!/bin/bash"), Language::Shell);
        assert_eq!(g.guess("run2", "#!/bin/sh"), Language::Shell);
    }

    #[test]
    fn unknown() {
        let g = CodeLangGuess::new();
        assert_eq!(g.guess("data.xyz", ""), Language::Unknown);
    }

    #[test]
    fn ext_beats_shebang() {
        let g = CodeLangGuess::new();
        // .rs file with a python shebang → ext wins.
        assert_eq!(g.guess("file.rs", "#!/usr/bin/env python"), Language::Rust);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut g = CodeLangGuess::new();
        g.schema_version = "9.9.9".into();
        assert!(matches!(
            g.validate().unwrap_err(),
            GuessError::SchemaMismatch
        ));
    }

    #[test]
    fn guess_serde_roundtrip() {
        let g = CodeLangGuess::new();
        let j = serde_json::to_string(&g).unwrap();
        let back: CodeLangGuess = serde_json::from_str(&j).unwrap();
        assert_eq!(g, back);
    }
}
