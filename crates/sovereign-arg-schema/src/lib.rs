//! `sovereign-arg-schema` — typed validation for tool-call arguments.
//!
//! `sovereign-json-extract` pulls a JSON object out of a model's reply, but a
//! tool needs to know that object actually has the fields it requires, with
//! the right types, before it runs. This crate is that check: declare a
//! [`Schema`] — which fields are required, which are optional, and each one's
//! JSON [`FieldType`] — and validate a [`serde_json::Value`] against it. It
//! collects **every** violation (missing required field, wrong type) rather
//! than failing on the first, so a runtime can report all the problems at once
//! or ask the model to fix them.
//!
//! Extra fields the schema doesn't mention are ignored (lenient), which keeps
//! it robust to chatty models that add commentary keys.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use serde_json::Value;
use thiserror::Error;

/// Schema version of the arg-schema surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// The JSON type expected for a field.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum FieldType {
    /// A JSON string.
    String,
    /// A JSON number (integer or float).
    Number,
    /// A JSON boolean.
    Bool,
    /// A JSON array.
    Array,
    /// A JSON object.
    Object,
}

impl FieldType {
    /// Whether `value` is of this type.
    pub fn matches(&self, value: &Value) -> bool {
        match self {
            FieldType::String => value.is_string(),
            FieldType::Number => value.is_number(),
            FieldType::Bool => value.is_boolean(),
            FieldType::Array => value.is_array(),
            FieldType::Object => value.is_object(),
        }
    }

    /// A human label for error messages.
    pub fn label(&self) -> &'static str {
        match self {
            FieldType::String => "string",
            FieldType::Number => "number",
            FieldType::Bool => "bool",
            FieldType::Array => "array",
            FieldType::Object => "object",
        }
    }
}

/// One declared field.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Field {
    /// Field name (object key).
    pub name: String,
    /// Expected type.
    pub ty: FieldType,
    /// Whether the field must be present.
    pub required: bool,
}

/// A single validation violation.
#[derive(Debug, Clone, PartialEq, Eq, Error)]
pub enum SchemaError {
    /// The top-level value was not a JSON object.
    #[error("expected a JSON object")]
    NotAnObject,
    /// A required field was absent.
    #[error("missing required field '{0}'")]
    Missing(String),
    /// A present field had the wrong type.
    #[error("field '{name}' should be {expected}, got {got}")]
    WrongType {
        /// Field name.
        name: String,
        /// Expected type label.
        expected: &'static str,
        /// Observed type label.
        got: &'static str,
    },
}

/// A tool-argument schema.
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct Schema {
    fields: Vec<Field>,
}

impl Schema {
    /// An empty schema (accepts any object).
    pub fn new() -> Self {
        Self::default()
    }

    /// Declare a required field.
    pub fn require(mut self, name: impl Into<String>, ty: FieldType) -> Self {
        self.fields.push(Field {
            name: name.into(),
            ty,
            required: true,
        });
        self
    }

    /// Declare an optional field (validated only if present).
    pub fn optional(mut self, name: impl Into<String>, ty: FieldType) -> Self {
        self.fields.push(Field {
            name: name.into(),
            ty,
            required: false,
        });
        self
    }

    /// The declared fields.
    pub fn fields(&self) -> &[Field] {
        &self.fields
    }

    /// Validate `value`, collecting all violations. `Ok(())` if it conforms.
    pub fn validate(&self, value: &Value) -> Result<(), Vec<SchemaError>> {
        let Some(obj) = value.as_object() else {
            return Err(vec![SchemaError::NotAnObject]);
        };
        let mut errors = Vec::new();
        for f in &self.fields {
            match obj.get(&f.name) {
                None => {
                    if f.required {
                        errors.push(SchemaError::Missing(f.name.clone()));
                    }
                }
                Some(v) => {
                    if !f.ty.matches(v) {
                        errors.push(SchemaError::WrongType {
                            name: f.name.clone(),
                            expected: f.ty.label(),
                            got: json_type_label(v),
                        });
                    }
                }
            }
        }
        if errors.is_empty() {
            Ok(())
        } else {
            Err(errors)
        }
    }

    /// Whether `value` conforms (convenience over [`validate`](Self::validate)).
    pub fn is_valid(&self, value: &Value) -> bool {
        self.validate(value).is_ok()
    }
}

/// A human label for a JSON value's type.
fn json_type_label(v: &Value) -> &'static str {
    match v {
        Value::Null => "null",
        Value::Bool(_) => "bool",
        Value::Number(_) => "number",
        Value::String(_) => "string",
        Value::Array(_) => "array",
        Value::Object(_) => "object",
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn schema() -> Schema {
        Schema::new()
            .require("city", FieldType::String)
            .require("days", FieldType::Number)
            .optional("metric", FieldType::Bool)
    }

    #[test]
    fn valid_object_passes() {
        let s = schema();
        assert!(s.is_valid(&json!({"city":"Paris","days":3})));
        assert!(s.is_valid(&json!({"city":"Paris","days":3,"metric":true})));
        // extra fields are ignored
        assert!(s.is_valid(&json!({"city":"Paris","days":3,"note":"hi"})));
    }

    #[test]
    fn missing_required_field_is_caught() {
        let s = schema();
        let errs = s.validate(&json!({"city":"Paris"})).unwrap_err();
        assert!(errs.contains(&SchemaError::Missing("days".to_string())));
    }

    #[test]
    fn wrong_type_is_caught() {
        let s = schema();
        let errs = s
            .validate(&json!({"city":"Paris","days":"three"}))
            .unwrap_err();
        assert!(errs.iter().any(|e| matches!(
            e,
            SchemaError::WrongType { name, expected: "number", got: "string" } if name == "days"
        )));
    }

    #[test]
    fn optional_field_wrong_type_is_caught_but_absence_is_ok() {
        let s = schema();
        // absent optional → fine
        assert!(s.is_valid(&json!({"city":"X","days":1})));
        // present optional, wrong type → error
        let errs = s
            .validate(&json!({"city":"X","days":1,"metric":"yes"}))
            .unwrap_err();
        assert!(errs.iter().any(|e| matches!(
            e,
            SchemaError::WrongType { name, .. } if name == "metric"
        )));
    }

    #[test]
    fn collects_all_violations() {
        let s = schema();
        // missing days AND wrong-type city
        let errs = s.validate(&json!({"city":123})).unwrap_err();
        assert_eq!(errs.len(), 2);
    }

    #[test]
    fn non_object_is_rejected() {
        let s = schema();
        assert_eq!(
            s.validate(&json!([1, 2, 3])).unwrap_err(),
            vec![SchemaError::NotAnObject]
        );
    }

    #[test]
    fn empty_schema_accepts_any_object() {
        assert!(Schema::new().is_valid(&json!({"anything":1})));
        assert!(Schema::new().is_valid(&json!({})));
    }

    #[test]
    fn field_type_matching() {
        assert!(FieldType::Array.matches(&json!([1])));
        assert!(FieldType::Object.matches(&json!({"a":1})));
        assert!(FieldType::Number.matches(&json!(1.5)));
        assert!(!FieldType::Number.matches(&json!("1.5")));
    }

    #[test]
    fn serde_round_trip() {
        let s = schema();
        let j = serde_json::to_string(&s).unwrap();
        let back: Schema = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
