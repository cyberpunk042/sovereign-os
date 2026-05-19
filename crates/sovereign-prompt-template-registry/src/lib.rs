//! `sovereign-prompt-template-registry` — operator-curated prompt templates.
//!
//! Each `PromptTemplate` declares:
//! - `name` (unique within registry)
//! - `body` (text with `{{var}}` slots)
//! - `variables` (declared variable names; render fails if any slot is
//!    missing from the substitution map or any declared variable isn't
//!    used)
//! - `allowed_modes`, `allowed_bundles` — context gates
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use sovereign_execution_mode_registry::ExecutionMode;
use sovereign_profile_bundles::BundleName;
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One template.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct PromptTemplate {
    /// Unique name.
    pub name: String,
    /// Body with `{{var}}` slots.
    pub body: String,
    /// Declared variables (must match the slots used in body).
    pub variables: Vec<String>,
    /// Modes in which this template is offered.
    pub allowed_modes: Vec<ExecutionMode>,
    /// Bundles in which this template is offered.
    pub allowed_bundles: Vec<BundleName>,
}

/// Registry envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct TemplateRegistry {
    /// Schema version.
    pub schema_version: String,
    /// Templates (order = display order).
    pub templates: Vec<PromptTemplate>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum TemplateError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Template name empty.
    #[error("template name empty")]
    EmptyName,
    /// Duplicate name.
    #[error("duplicate template name: {0}")]
    DuplicateName(String),
    /// allowed_modes empty.
    #[error("template {0} has no allowed_modes")]
    NoModes(String),
    /// allowed_bundles empty.
    #[error("template {0} has no allowed_bundles")]
    NoBundles(String),
    /// Declared variable not referenced in body.
    #[error("template {0} declares unused variable {1}")]
    UnusedVariable(String, String),
    /// Body slot references undeclared variable.
    #[error("template {0} body references undeclared variable {1}")]
    UndeclaredVariable(String, String),
    /// Render missing a value.
    #[error("render: missing variable {0}")]
    RenderMissing(String),
    /// Unknown template.
    #[error("unknown template: {0}")]
    Unknown(String),
}

fn body_slots(body: &str) -> Vec<String> {
    let mut out = Vec::new();
    let bytes = body.as_bytes();
    let mut i = 0;
    while i + 3 < bytes.len() {
        if bytes[i] == b'{' && bytes[i + 1] == b'{' {
            let mut j = i + 2;
            while j + 1 < bytes.len() && !(bytes[j] == b'}' && bytes[j + 1] == b'}') {
                j += 1;
            }
            if j + 1 < bytes.len() && bytes[j] == b'}' && bytes[j + 1] == b'}' {
                let name = body[i + 2..j].trim();
                if !name.is_empty() {
                    out.push(name.to_string());
                }
                i = j + 2;
                continue;
            }
        }
        i += 1;
    }
    out
}

impl PromptTemplate {
    /// Validate this template in isolation (slot vs declared-vars + non-empty fields).
    pub fn validate(&self) -> Result<(), TemplateError> {
        if self.name.is_empty() { return Err(TemplateError::EmptyName); }
        if self.allowed_modes.is_empty() { return Err(TemplateError::NoModes(self.name.clone())); }
        if self.allowed_bundles.is_empty() { return Err(TemplateError::NoBundles(self.name.clone())); }
        let slots = body_slots(&self.body);
        for s in &slots {
            if !self.variables.iter().any(|v| v == s) {
                return Err(TemplateError::UndeclaredVariable(self.name.clone(), s.clone()));
            }
        }
        for v in &self.variables {
            if !slots.iter().any(|s| s == v) {
                return Err(TemplateError::UnusedVariable(self.name.clone(), v.clone()));
            }
        }
        Ok(())
    }

    /// Render the template by substituting variables.
    pub fn render(&self, vars: &BTreeMap<String, String>) -> Result<String, TemplateError> {
        self.validate()?;
        for v in &self.variables {
            if !vars.contains_key(v) {
                return Err(TemplateError::RenderMissing(v.clone()));
            }
        }
        let mut out = String::with_capacity(self.body.len());
        let bytes = self.body.as_bytes();
        let mut i = 0;
        while i < bytes.len() {
            if i + 3 < bytes.len() && bytes[i] == b'{' && bytes[i + 1] == b'{' {
                let mut j = i + 2;
                while j + 1 < bytes.len() && !(bytes[j] == b'}' && bytes[j + 1] == b'}') {
                    j += 1;
                }
                if j + 1 < bytes.len() && bytes[j] == b'}' && bytes[j + 1] == b'}' {
                    let name = self.body[i + 2..j].trim();
                    if let Some(val) = vars.get(name) {
                        out.push_str(val);
                    }
                    i = j + 2;
                    continue;
                }
            }
            out.push(bytes[i] as char);
            i += 1;
        }
        Ok(out)
    }

    /// True if available in (mode, bundle) context.
    pub fn is_available(&self, mode: ExecutionMode, bundle: BundleName) -> bool {
        self.allowed_modes.contains(&mode) && self.allowed_bundles.contains(&bundle)
    }
}

impl TemplateRegistry {
    /// New empty registry.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            templates: Vec::new(),
        }
    }

    /// Add a template; rejects duplicate names.
    pub fn add(&mut self, t: PromptTemplate) -> Result<(), TemplateError> {
        t.validate()?;
        if self.templates.iter().any(|x| x.name == t.name) {
            return Err(TemplateError::DuplicateName(t.name));
        }
        self.templates.push(t);
        Ok(())
    }

    /// Lookup by name.
    pub fn get(&self, name: &str) -> Result<&PromptTemplate, TemplateError> {
        self.templates.iter().find(|t| t.name == name)
            .ok_or_else(|| TemplateError::Unknown(name.into()))
    }

    /// Render a named template.
    pub fn render(&self, name: &str, vars: &BTreeMap<String, String>) -> Result<String, TemplateError> {
        self.get(name)?.render(vars)
    }

    /// Available templates in the given context.
    pub fn available_in(&self, mode: ExecutionMode, bundle: BundleName) -> Vec<&PromptTemplate> {
        self.templates.iter().filter(|t| t.is_available(mode, bundle)).collect()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), TemplateError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(TemplateError::SchemaMismatch);
        }
        use std::collections::HashSet;
        let mut seen: HashSet<&str> = HashSet::new();
        for t in &self.templates {
            t.validate()?;
            if !seen.insert(t.name.as_str()) {
                return Err(TemplateError::DuplicateName(t.name.clone()));
            }
        }
        Ok(())
    }
}

impl Default for TemplateRegistry {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn tpl(name: &str, body: &str, vars: &[&str]) -> PromptTemplate {
        PromptTemplate {
            name: name.into(),
            body: body.into(),
            variables: vars.iter().map(|s| s.to_string()).collect(),
            allowed_modes: vec![ExecutionMode::Plan, ExecutionMode::Execute],
            allowed_bundles: vec![BundleName::Careful, BundleName::Sovereign],
        }
    }

    #[test]
    fn empty_registry_validates() {
        TemplateRegistry::new().validate().unwrap();
    }

    #[test]
    fn add_and_render() {
        let mut r = TemplateRegistry::new();
        r.add(tpl("greet", "hello {{name}}", &["name"])).unwrap();
        let mut vars = BTreeMap::new();
        vars.insert("name".into(), "world".into());
        assert_eq!(r.render("greet", &vars).unwrap(), "hello world");
    }

    #[test]
    fn render_missing_var_caught() {
        let r = TemplateRegistry::new();
        let mut r = r;
        r.add(tpl("greet", "hello {{name}}", &["name"])).unwrap();
        let vars = BTreeMap::new();
        assert!(matches!(r.render("greet", &vars).unwrap_err(), TemplateError::RenderMissing(ref v) if v == "name"));
    }

    #[test]
    fn undeclared_variable_in_body_caught() {
        let t = tpl("x", "{{undeclared}}", &[]);
        assert!(matches!(t.validate().unwrap_err(), TemplateError::UndeclaredVariable(_, ref v) if v == "undeclared"));
    }

    #[test]
    fn unused_declared_variable_caught() {
        let t = tpl("x", "plain text", &["unused"]);
        assert!(matches!(t.validate().unwrap_err(), TemplateError::UnusedVariable(_, ref v) if v == "unused"));
    }

    #[test]
    fn duplicate_name_rejected() {
        let mut r = TemplateRegistry::new();
        r.add(tpl("a", "x {{v}}", &["v"])).unwrap();
        assert!(matches!(r.add(tpl("a", "y {{v}}", &["v"])).unwrap_err(), TemplateError::DuplicateName(ref n) if n == "a"));
    }

    #[test]
    fn empty_name_rejected() {
        let t = tpl("", "x {{v}}", &["v"]);
        assert!(matches!(t.validate().unwrap_err(), TemplateError::EmptyName));
    }

    #[test]
    fn no_modes_rejected() {
        let mut t = tpl("x", "y {{v}}", &["v"]);
        t.allowed_modes.clear();
        assert!(matches!(t.validate().unwrap_err(), TemplateError::NoModes(_)));
    }

    #[test]
    fn no_bundles_rejected() {
        let mut t = tpl("x", "y {{v}}", &["v"]);
        t.allowed_bundles.clear();
        assert!(matches!(t.validate().unwrap_err(), TemplateError::NoBundles(_)));
    }

    #[test]
    fn available_in_filters_by_mode_and_bundle() {
        let mut r = TemplateRegistry::new();
        let mut t1 = tpl("a", "x {{v}}", &["v"]);
        t1.allowed_modes = vec![ExecutionMode::Plan];
        t1.allowed_bundles = vec![BundleName::Careful];
        let mut t2 = tpl("b", "y {{v}}", &["v"]);
        t2.allowed_modes = vec![ExecutionMode::Execute];
        t2.allowed_bundles = vec![BundleName::Sovereign];
        r.add(t1).unwrap();
        r.add(t2).unwrap();
        let v = r.available_in(ExecutionMode::Plan, BundleName::Careful);
        assert_eq!(v.len(), 1);
        assert_eq!(v[0].name, "a");
    }

    #[test]
    fn unknown_template_caught() {
        let r = TemplateRegistry::new();
        let vars = BTreeMap::new();
        assert!(matches!(r.render("none", &vars).unwrap_err(), TemplateError::Unknown(ref n) if n == "none"));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut r = TemplateRegistry::new();
        r.schema_version = "9.9.9".into();
        assert!(matches!(r.validate().unwrap_err(), TemplateError::SchemaMismatch));
    }

    #[test]
    fn multi_var_render_all_substituted() {
        let mut r = TemplateRegistry::new();
        r.add(tpl("note", "User {{user}} performed {{action}} at {{time}}", &["user", "action", "time"])).unwrap();
        let mut vars = BTreeMap::new();
        vars.insert("user".into(), "alice".into());
        vars.insert("action".into(), "commit".into());
        vars.insert("time".into(), "03:00".into());
        assert_eq!(r.render("note", &vars).unwrap(), "User alice performed commit at 03:00");
    }

    #[test]
    fn registry_serde_roundtrip() {
        let mut r = TemplateRegistry::new();
        r.add(tpl("a", "x {{v}}", &["v"])).unwrap();
        let j = serde_json::to_string(&r).unwrap();
        let back: TemplateRegistry = serde_json::from_str(&j).unwrap();
        assert_eq!(r, back);
    }
}
