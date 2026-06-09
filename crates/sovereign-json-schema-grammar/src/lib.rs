//! `sovereign-json-schema-grammar` — turn a JSON Schema into a decoding grammar.
//!
//! The cleanest way to force a model to emit valid structured output — a function
//! call, a typed record — is to *constrain decoding to a grammar* that only
//! accepts conforming text. This crate is the bridge from a schema to that
//! grammar: it compiles a JSON-Schema subset into a [`sovereign_cfg_grammar::Grammar`],
//! which the Earley engine then uses to report, at every step, exactly which
//! characters keep the JSON valid.
//!
//! The supported [`Schema`] covers the shapes that matter for tool-calling and
//! typed extraction:
//!
//! - **objects** with a fixed, ordered set of required properties (and no extras),
//!   the standard constrained-decoding choice — the key order is pinned so the
//!   structure is fully determined;
//! - **arrays** of a single item schema, any length;
//! - **strings** (printable, unescaped) and **string enums** (a closed set of
//!   literal alternatives);
//! - **integers** and **numbers** (optional sign, optional fractional part);
//! - **booleans** and **null**.
//!
//! Insignificant whitespace is permitted between tokens, so both `{"a":1}` and
//! `{ "a": 1 }` parse. [`compile`] returns the grammar; pair it with the cfg-grammar
//! API — [`Grammar::accepts`] to validate a finished value and
//! [`Grammar::allowed_next`] to drive a token-by-token mask. The `Grammar`,
//! `NextSet`, and `Terminal` types are re-exported for convenience.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use sovereign_cfg_grammar::{GrammarBuilder, Symbol, Terminal};

pub use sovereign_cfg_grammar::{Grammar, NextSet};

/// Schema version of the json-schema-grammar surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A JSON-Schema subset describing the JSON values a generator may produce.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum Schema {
    /// `true` or `false`.
    Boolean,
    /// The literal `null`.
    Null,
    /// An integer: optional `-` then one or more digits.
    Integer,
    /// A number: optional `-`, digits, optional `.` and fractional digits.
    Number,
    /// Any JSON string of printable, unescaped characters.
    StringType,
    /// A string whose value is one of a closed set of literals.
    Enum(Vec<String>),
    /// An object with these properties, all required, in this exact key order,
    /// and no additional properties.
    Object(Vec<(String, Schema)>),
    /// An array of zero or more items, each conforming to the inner schema.
    Array(Box<Schema>),
}

impl Schema {
    /// Convenience constructor for an object from `(key, schema)` pairs.
    pub fn object<I>(props: I) -> Schema
    where
        I: IntoIterator<Item = (String, Schema)>,
    {
        Schema::Object(props.into_iter().collect())
    }
    /// Convenience constructor for an array of `item`.
    pub fn array(item: Schema) -> Schema {
        Schema::Array(Box::new(item))
    }
}

/// Builds the grammar, allocating non-terminals and caching shared primitives so
/// the produced grammar stays small.
struct Compiler {
    b: GrammarBuilder,
    ws: Option<usize>,
    digits: Option<usize>,
    integer: Option<usize>,
    number: Option<usize>,
    string: Option<usize>,
    boolean: Option<usize>,
    null: Option<usize>,
}

/// The character classes inside a JSON string: printable ASCII minus `"` and `\`.
const STRING_CHAR_RANGES: &[(char, char)] = &[
    ('\u{20}', '\u{21}'), // space, '!'
    ('\u{23}', '\u{5B}'), // '#'..'['  (skips '"')
    ('\u{5D}', '\u{7E}'), // ']'..'~'  (skips '\')
];

impl Compiler {
    fn new() -> Self {
        Self {
            b: GrammarBuilder::new(),
            ws: None,
            digits: None,
            integer: None,
            number: None,
            string: None,
            boolean: None,
            null: None,
        }
    }

    /// Symbols spelling a literal string as a sequence of char terminals.
    fn literal(s: &str) -> Vec<Symbol> {
        s.chars().map(Symbol::ch).collect()
    }

    /// Symbols for a quoted JSON string literal: `"` value `"`.
    fn quoted(s: &str) -> Vec<Symbol> {
        let mut v = vec![Symbol::ch('"')];
        v.extend(s.chars().map(Symbol::ch));
        v.push(Symbol::ch('"'));
        v
    }

    /// `WS -> ' ' WS | tab | newline | cr | ε` (zero or more whitespace chars).
    fn ws(&mut self) -> usize {
        if let Some(id) = self.ws {
            return id;
        }
        let ws = self.b.nonterminal();
        let space = Symbol::Term(Terminal::Set(vec![' ', '\t', '\n', '\r']));
        self.b.rule(ws, vec![space, Symbol::nt(ws)]);
        self.b.rule(ws, vec![]);
        self.ws = Some(ws);
        ws
    }

    /// `DIGITS -> [0-9] DIGITS | [0-9]` (one or more digits).
    fn digits(&mut self) -> usize {
        if let Some(id) = self.digits {
            return id;
        }
        let d = self.b.nonterminal();
        self.b.rule(d, vec![Symbol::range('0', '9'), Symbol::nt(d)]);
        self.b.rule(d, vec![Symbol::range('0', '9')]);
        self.digits = Some(d);
        d
    }

    /// `INT -> '-'? DIGITS`.
    fn integer(&mut self) -> usize {
        if let Some(id) = self.integer {
            return id;
        }
        let digits = self.digits();
        let int = self.b.nonterminal();
        self.b.rule(int, vec![Symbol::ch('-'), Symbol::nt(digits)]);
        self.b.rule(int, vec![Symbol::nt(digits)]);
        self.integer = Some(int);
        int
    }

    /// `NUM -> '-'? DIGITS FRAC` ; `FRAC -> '.' DIGITS | ε`.
    fn number(&mut self) -> usize {
        if let Some(id) = self.number {
            return id;
        }
        let digits = self.digits();
        let frac = self.b.nonterminal();
        self.b.rule(frac, vec![Symbol::ch('.'), Symbol::nt(digits)]);
        self.b.rule(frac, vec![]);
        let num = self.b.nonterminal();
        self.b.rule(
            num,
            vec![Symbol::ch('-'), Symbol::nt(digits), Symbol::nt(frac)],
        );
        self.b.rule(num, vec![Symbol::nt(digits), Symbol::nt(frac)]);
        self.number = Some(num);
        num
    }

    /// `STR -> '"' CHARS '"'` ; `CHARS -> CH CHARS | ε` ; `CH -> <printable>`.
    fn string(&mut self) -> usize {
        if let Some(id) = self.string {
            return id;
        }
        let ch = self.b.nonterminal();
        for &(lo, hi) in STRING_CHAR_RANGES {
            self.b.rule(ch, vec![Symbol::range(lo, hi)]);
        }
        let chars = self.b.nonterminal();
        self.b.rule(chars, vec![Symbol::nt(ch), Symbol::nt(chars)]);
        self.b.rule(chars, vec![]);
        let s = self.b.nonterminal();
        self.b
            .rule(s, vec![Symbol::ch('"'), Symbol::nt(chars), Symbol::ch('"')]);
        self.string = Some(s);
        s
    }

    /// `BOOL -> "true" | "false"`.
    fn boolean(&mut self) -> usize {
        if let Some(id) = self.boolean {
            return id;
        }
        let b = self.b.nonterminal();
        self.b.rule(b, Self::literal("true"));
        self.b.rule(b, Self::literal("false"));
        self.boolean = Some(b);
        b
    }

    /// `NULL -> "null"`.
    fn null(&mut self) -> usize {
        if let Some(id) = self.null {
            return id;
        }
        let n = self.b.nonterminal();
        self.b.rule(n, Self::literal("null"));
        self.null = Some(n);
        n
    }

    /// Compile `schema` into a non-terminal that derives exactly its JSON values.
    fn compile(&mut self, schema: &Schema) -> usize {
        match schema {
            Schema::Boolean => self.boolean(),
            Schema::Null => self.null(),
            Schema::Integer => self.integer(),
            Schema::Number => self.number(),
            Schema::StringType => self.string(),
            Schema::Enum(values) => {
                let e = self.b.nonterminal();
                for v in values {
                    self.b.rule(e, Self::quoted(v));
                }
                // an empty enum derives nothing (no rule) — an unsatisfiable schema.
                e
            }
            Schema::Array(item) => {
                let item_nt = self.compile(item);
                let ws = self.ws();
                // ELEMS -> item | item WS ',' WS ELEMS
                let elems = self.b.nonterminal();
                self.b.rule(elems, vec![Symbol::nt(item_nt)]);
                self.b.rule(
                    elems,
                    vec![
                        Symbol::nt(item_nt),
                        Symbol::nt(ws),
                        Symbol::ch(','),
                        Symbol::nt(ws),
                        Symbol::nt(elems),
                    ],
                );
                // ARR -> '[' WS ']' | '[' WS ELEMS WS ']'
                let arr = self.b.nonterminal();
                self.b
                    .rule(arr, vec![Symbol::ch('['), Symbol::nt(ws), Symbol::ch(']')]);
                self.b.rule(
                    arr,
                    vec![
                        Symbol::ch('['),
                        Symbol::nt(ws),
                        Symbol::nt(elems),
                        Symbol::nt(ws),
                        Symbol::ch(']'),
                    ],
                );
                arr
            }
            Schema::Object(props) => {
                let ws = self.ws();
                // compile each property's value schema first.
                let prop_nts: Vec<(String, usize)> = props
                    .iter()
                    .map(|(k, s)| (k.clone(), self.compile(s)))
                    .collect();
                let obj = self.b.nonterminal();
                if prop_nts.is_empty() {
                    self.b
                        .rule(obj, vec![Symbol::ch('{'), Symbol::nt(ws), Symbol::ch('}')]);
                    return obj;
                }
                // single production with fixed, ordered keys:
                // '{' WS "k0" WS ':' WS v0  ( WS ',' WS "ki" WS ':' WS vi )*  WS '}'
                let mut rhs: Vec<Symbol> = vec![Symbol::ch('{'), Symbol::nt(ws)];
                for (i, (key, vnt)) in prop_nts.iter().enumerate() {
                    if i > 0 {
                        rhs.push(Symbol::nt(ws));
                        rhs.push(Symbol::ch(','));
                        rhs.push(Symbol::nt(ws));
                    }
                    rhs.extend(Self::quoted(key));
                    rhs.push(Symbol::nt(ws));
                    rhs.push(Symbol::ch(':'));
                    rhs.push(Symbol::nt(ws));
                    rhs.push(Symbol::nt(*vnt));
                }
                rhs.push(Symbol::nt(ws));
                rhs.push(Symbol::ch('}'));
                self.b.rule(obj, rhs);
                obj
            }
        }
    }

    /// Finish: `DOC -> WS value WS`, allowing surrounding whitespace.
    fn finish(mut self, root: usize) -> Grammar {
        let ws = self.ws();
        let doc = self.b.nonterminal();
        self.b
            .rule(doc, vec![Symbol::nt(ws), Symbol::nt(root), Symbol::nt(ws)]);
        self.b.build(doc)
    }
}

/// Compile a [`Schema`] into a grammar that accepts exactly the conforming JSON
/// values (with optional insignificant whitespace between tokens).
pub fn compile(schema: &Schema) -> Grammar {
    let mut c = Compiler::new();
    let root = c.compile(schema);
    c.finish(root)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn integer_schema() {
        let g = compile(&Schema::Integer);
        for ok in ["0", "42", "-7", "1000"] {
            assert!(g.accepts(ok), "accept {ok}");
        }
        for bad in ["", "4.5", "abc", "--1", "1a", "+3"] {
            assert!(!g.accepts(bad), "reject {bad}");
        }
    }

    #[test]
    fn number_schema() {
        let g = compile(&Schema::Number);
        for ok in ["3.14", "-0.5", "10", "-42", "0.0"] {
            assert!(g.accepts(ok), "accept {ok}");
        }
        for bad in ["3.", ".5", "1.2.3", "abc"] {
            assert!(!g.accepts(bad), "reject {bad}");
        }
    }

    #[test]
    fn boolean_and_null() {
        let gb = compile(&Schema::Boolean);
        assert!(gb.accepts("true") && gb.accepts("false"));
        assert!(!gb.accepts("True") && !gb.accepts("yes"));
        let gn = compile(&Schema::Null);
        assert!(gn.accepts("null"));
        assert!(!gn.accepts("nil") && !gn.accepts("none"));
    }

    #[test]
    fn string_schema() {
        let g = compile(&Schema::StringType);
        assert!(g.accepts("\"hello world\""));
        assert!(g.accepts("\"\"")); // empty string
        assert!(!g.accepts("hello")); // unquoted
        assert!(!g.accepts("\"abc")); // unterminated
    }

    #[test]
    fn enum_schema() {
        let g = compile(&Schema::Enum(vec![
            "red".into(),
            "green".into(),
            "blue".into(),
        ]));
        assert!(g.accepts("\"red\""));
        assert!(g.accepts("\"green\""));
        assert!(!g.accepts("\"yellow\""));
        assert!(!g.accepts("red")); // must be quoted
    }

    #[test]
    fn object_schema_fixed_keys() {
        let schema = Schema::object([
            ("name".to_string(), Schema::StringType),
            ("age".to_string(), Schema::Integer),
        ]);
        let g = compile(&schema);
        assert!(g.accepts(r#"{"name":"alice","age":30}"#));
        assert!(g.accepts(r#"{ "name": "bob", "age": -5 }"#)); // whitespace ok
        // wrong key order is rejected (keys are pinned).
        assert!(!g.accepts(r#"{"age":30,"name":"alice"}"#));
        // missing a required key is rejected.
        assert!(!g.accepts(r#"{"name":"alice"}"#));
        // extra key is rejected.
        assert!(!g.accepts(r#"{"name":"a","age":1,"x":2}"#));
    }

    #[test]
    fn empty_object() {
        let g = compile(&Schema::object(Vec::<(String, Schema)>::new()));
        assert!(g.accepts("{}"));
        assert!(g.accepts("{ }"));
        assert!(!g.accepts(r#"{"a":1}"#));
    }

    #[test]
    fn array_schema() {
        let g = compile(&Schema::array(Schema::Integer));
        assert!(g.accepts("[]"));
        assert!(g.accepts("[1]"));
        assert!(g.accepts("[1, 2, 3]"));
        assert!(g.accepts("[1,2,3]"));
        assert!(!g.accepts("[1,]")); // trailing comma
        assert!(!g.accepts("[1 2]")); // missing comma
    }

    #[test]
    fn nested_object_array() {
        let schema = Schema::object([
            ("id".to_string(), Schema::Integer),
            ("tags".to_string(), Schema::array(Schema::StringType)),
            (
                "meta".to_string(),
                Schema::object([("ok".to_string(), Schema::Boolean)]),
            ),
        ]);
        let g = compile(&schema);
        assert!(g.accepts(r#"{"id":1,"tags":["a","b"],"meta":{"ok":true}}"#));
        assert!(g.accepts(r#"{"id":1,"tags":[],"meta":{"ok":false}}"#));
        assert!(!g.accepts(r#"{"id":1,"tags":[1],"meta":{"ok":true}}"#)); // tag not a string
    }

    #[test]
    fn allowed_next_guides_object_start() {
        let schema = Schema::object([("a".to_string(), Schema::Integer)]);
        let g = compile(&schema);
        // at the start, only '{' (or whitespace) is valid.
        let n0 = g.allowed_next("");
        assert!(n0.allows('{'));
        assert!(n0.allows(' '));
        assert!(!n0.allows('['));
        // after '{' optional ws then the key's opening quote.
        let n1 = g.allowed_next("{");
        assert!(n1.allows('"'));
        assert!(!n1.allows('}')); // a required key must follow
        // partway into a value: a digit is expected.
        let n2 = g.allowed_next(r#"{"a":"#);
        assert!(n2.allows('5'));
        assert!(n2.allows('-'));
        assert!(!n2.allows('"'));
    }

    #[test]
    fn dead_end_on_invalid_prefix() {
        let g = compile(&Schema::Integer);
        // a letter can never extend an integer document.
        assert!(!g.is_live_prefix("4a"));
        assert!(g.is_live_prefix("4")); // complete and live
        assert!(g.allowed_next("4").complete);
    }

    #[test]
    fn schema_serde_round_trip() {
        let schema = Schema::object([
            ("x".to_string(), Schema::Number),
            (
                "y".to_string(),
                Schema::Enum(vec!["on".into(), "off".into()]),
            ),
        ]);
        let j = serde_json::to_string(&schema).unwrap();
        let back: Schema = serde_json::from_str(&j).unwrap();
        assert_eq!(schema, back);
        // grammar from the round-tripped schema still works.
        let g = compile(&back);
        assert!(g.accepts(r#"{"x":1.5,"y":"on"}"#));
    }

    #[test]
    fn schema_version_is_set() {
        assert_eq!(SCHEMA_VERSION, "1.0.0");
    }
}
