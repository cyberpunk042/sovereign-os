//! `sovereign-calc` — a safe arithmetic evaluator.
//!
//! Language models are unreliable at arithmetic, so an agent should *call a
//! calculator*. This is that calculator: a dependency-free recursive-descent
//! evaluator for `+`, `-`, `*`, `/`, parentheses, unary minus, and decimal
//! numbers, with correct operator precedence and associativity. It never
//! executes code or touches the system — it only parses and computes — so it is
//! safe to expose as a tool handler that takes the model's expression string
//! and returns a number.
//!
//! Grammar (precedence low → high):
//! ```text
//!   expr   := term  (('+' | '-') term)*
//!   term   := factor (('*' | '/') factor)*
//!   factor := '-' factor | '(' expr ')' | number
//! ```
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use thiserror::Error;

/// Schema version of the calculator surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Why evaluation failed.
#[derive(Debug, Clone, PartialEq, Error)]
pub enum CalcError {
    /// An unexpected character in the input.
    #[error("unexpected character '{ch}' at position {pos}")]
    UnexpectedChar {
        /// The offending character.
        ch: char,
        /// Byte position.
        pos: usize,
    },
    /// The expression ended while a value was expected.
    #[error("unexpected end of expression")]
    UnexpectedEnd,
    /// Trailing input after a complete expression.
    #[error("trailing input at position {pos}")]
    TrailingInput {
        /// Byte position of the leftover token.
        pos: usize,
    },
    /// A `(` was never closed.
    #[error("unbalanced parenthesis")]
    UnbalancedParen,
    /// Division by zero.
    #[error("division by zero")]
    DivByZero,
    /// The input was empty.
    #[error("empty expression")]
    Empty,
}

#[derive(Debug, Clone, Copy, PartialEq)]
enum Tok {
    Num(f64),
    Plus,
    Minus,
    Star,
    Slash,
    LParen,
    RParen,
}

fn lex(input: &str) -> Result<Vec<(Tok, usize)>, CalcError> {
    let mut toks = Vec::new();
    let chars: Vec<char> = input.chars().collect();
    let mut i = 0;
    while i < chars.len() {
        let c = chars[i];
        match c {
            c if c.is_whitespace() => i += 1,
            '+' => {
                toks.push((Tok::Plus, i));
                i += 1;
            }
            '-' => {
                toks.push((Tok::Minus, i));
                i += 1;
            }
            '*' => {
                toks.push((Tok::Star, i));
                i += 1;
            }
            '/' => {
                toks.push((Tok::Slash, i));
                i += 1;
            }
            '(' => {
                toks.push((Tok::LParen, i));
                i += 1;
            }
            ')' => {
                toks.push((Tok::RParen, i));
                i += 1;
            }
            c if c.is_ascii_digit() || c == '.' => {
                let start = i;
                while i < chars.len() && (chars[i].is_ascii_digit() || chars[i] == '.') {
                    i += 1;
                }
                let s: String = chars[start..i].iter().collect();
                let n: f64 = s
                    .parse()
                    .map_err(|_| CalcError::UnexpectedChar { ch: c, pos: start })?;
                toks.push((Tok::Num(n), start));
            }
            _ => return Err(CalcError::UnexpectedChar { ch: c, pos: i }),
        }
    }
    Ok(toks)
}

struct Parser {
    toks: Vec<(Tok, usize)>,
    pos: usize,
}

impl Parser {
    fn peek(&self) -> Option<Tok> {
        self.toks.get(self.pos).map(|(t, _)| *t)
    }

    fn next(&mut self) -> Option<(Tok, usize)> {
        let t = self.toks.get(self.pos).copied();
        if t.is_some() {
            self.pos += 1;
        }
        t
    }

    fn expr(&mut self) -> Result<f64, CalcError> {
        let mut v = self.term()?;
        while let Some(op) = self.peek() {
            match op {
                Tok::Plus => {
                    self.pos += 1;
                    v += self.term()?;
                }
                Tok::Minus => {
                    self.pos += 1;
                    v -= self.term()?;
                }
                _ => break,
            }
        }
        Ok(v)
    }

    fn term(&mut self) -> Result<f64, CalcError> {
        let mut v = self.factor()?;
        while let Some(op) = self.peek() {
            match op {
                Tok::Star => {
                    self.pos += 1;
                    v *= self.factor()?;
                }
                Tok::Slash => {
                    self.pos += 1;
                    let d = self.factor()?;
                    if d == 0.0 {
                        return Err(CalcError::DivByZero);
                    }
                    v /= d;
                }
                _ => break,
            }
        }
        Ok(v)
    }

    fn factor(&mut self) -> Result<f64, CalcError> {
        match self.next() {
            Some((Tok::Minus, _)) => Ok(-self.factor()?),
            Some((Tok::Num(n), _)) => Ok(n),
            Some((Tok::LParen, _)) => {
                let v = self.expr()?;
                match self.next() {
                    Some((Tok::RParen, _)) => Ok(v),
                    _ => Err(CalcError::UnbalancedParen),
                }
            }
            Some((_, pos)) => Err(CalcError::UnexpectedChar { ch: '?', pos }),
            None => Err(CalcError::UnexpectedEnd),
        }
    }
}

/// Evaluate an arithmetic expression.
pub fn eval(input: &str) -> Result<f64, CalcError> {
    let toks = lex(input)?;
    if toks.is_empty() {
        return Err(CalcError::Empty);
    }
    let mut p = Parser { toks, pos: 0 };
    let v = p.expr()?;
    if p.pos != p.toks.len() {
        return Err(CalcError::TrailingInput {
            pos: p.toks[p.pos].1,
        });
    }
    Ok(v)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn approx(a: f64, b: f64) -> bool {
        (a - b).abs() < 1e-9
    }

    #[test]
    fn basic_arithmetic() {
        assert!(approx(eval("1 + 2").unwrap(), 3.0));
        assert!(approx(eval("10 - 4").unwrap(), 6.0));
        assert!(approx(eval("3 * 4").unwrap(), 12.0));
        assert!(approx(eval("20 / 5").unwrap(), 4.0));
    }

    #[test]
    fn precedence_is_respected() {
        assert!(approx(eval("2 + 3 * 4").unwrap(), 14.0));
        assert!(approx(eval("2 * 3 + 4").unwrap(), 10.0));
        assert!(approx(eval("10 - 2 * 3").unwrap(), 4.0));
    }

    #[test]
    fn parentheses_override_precedence() {
        assert!(approx(eval("(2 + 3) * 4").unwrap(), 20.0));
        assert!(approx(eval("2 * (3 + 4)").unwrap(), 14.0));
        assert!(approx(eval("((1 + 2) * (3 + 4))").unwrap(), 21.0));
    }

    #[test]
    fn unary_minus() {
        assert!(approx(eval("-5").unwrap(), -5.0));
        assert!(approx(eval("3 + -2").unwrap(), 1.0));
        assert!(approx(eval("-(2 + 3)").unwrap(), -5.0));
        assert!(approx(eval("--4").unwrap(), 4.0));
    }

    #[test]
    fn decimals() {
        assert!(approx(eval("1.5 + 2.25").unwrap(), 3.75));
        assert!(approx(eval("0.1 * 10").unwrap(), 1.0));
    }

    #[test]
    fn left_associative_subtraction_and_division() {
        assert!(approx(eval("10 - 3 - 2").unwrap(), 5.0)); // (10-3)-2
        assert!(approx(eval("100 / 5 / 2").unwrap(), 10.0)); // (100/5)/2
    }

    #[test]
    fn division_by_zero_errors() {
        assert_eq!(eval("1 / 0").unwrap_err(), CalcError::DivByZero);
        assert_eq!(eval("5 / (3 - 3)").unwrap_err(), CalcError::DivByZero);
    }

    #[test]
    fn empty_and_malformed_error() {
        assert_eq!(eval("").unwrap_err(), CalcError::Empty);
        assert_eq!(eval("   ").unwrap_err(), CalcError::Empty);
        assert!(matches!(eval("1 +"), Err(CalcError::UnexpectedEnd)));
        assert!(matches!(eval("(1 + 2"), Err(CalcError::UnbalancedParen)));
        assert!(matches!(eval("1 2"), Err(CalcError::TrailingInput { .. })));
        assert!(matches!(
            eval("1 + a"),
            Err(CalcError::UnexpectedChar { .. })
        ));
    }

    #[test]
    fn nested_and_complex() {
        assert!(approx(eval("2 * (3 + 4 * (5 - 1)) / 2").unwrap(), 19.0));
        assert!(approx(eval("-(-(-3))").unwrap(), -3.0));
    }
}
