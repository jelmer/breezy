use bazaar::RevisionId;
use chrono::{DateTime, NaiveDateTime, Utc};
use pyo3::class::basic::CompareOp;
use pyo3::exceptions::{PyNotImplementedError, PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict, PyList};
use std::collections::HashMap;

/// Create a new file id suffix that is reasonably unique.
///
/// On the first call we combine the current time with 64 bits of randomness to
/// give a highly probably globally unique number. Then each call in the same
/// process adds 1 to a serial number we append to that unique value.
#[pyfunction]
fn _next_id_suffix(py: Python, suffix: Option<&str>) -> PyObject {
    PyBytes::new(py, &bazaar::gen_ids::next_id_suffix(suffix)).into_py(py)
}

/// Return new file id for the basename 'name'.
///
/// The uniqueness is supplied from _next_id_suffix.
#[pyfunction]
fn gen_file_id(py: Python, name: &str) -> PyObject {
    PyBytes::new(py, &bazaar::gen_ids::gen_file_id(name)).into_py(py)
}

/// Return a new tree-root file id.
#[pyfunction]
fn gen_root_id(py: Python) -> PyObject {
    PyBytes::new(py, &bazaar::gen_ids::gen_root_id()).into_py(py)
}

/// Return new revision-id.
///
/// Args:
///   username: The username of the committer, in the format returned by
///      config.username().  This is typically a real name, followed by an
///      email address. If found, we will use just the email address portion.
///      Otherwise we flatten the real name, and use that.
/// Returns: A new revision id.
#[pyfunction]
fn gen_revision_id(py: Python, username: &str, timestamp: Option<PyObject>) -> PyResult<PyObject> {
    let timestamp = match timestamp {
        Some(timestamp) => {
            if let Ok(timestamp) = timestamp.extract::<f64>(py) {
                Some(timestamp as u64)
            } else if let Ok(timestamp) = timestamp.extract::<u64>(py) {
                Some(timestamp)
            } else {
                return Err(PyTypeError::new_err(
                    "timestamp must be a float or an int".to_string(),
                ));
            }
        }
        None => None,
    };
    Ok(PyBytes::new(py, &bazaar::gen_ids::gen_revision_id(username, timestamp)).into_py(py))
}

#[pyfunction]
fn normalize_pattern(pattern: &str) -> String {
    bazaar::globbing::normalize_pattern(pattern)
}

#[pyclass]
struct Replacer {
    replacer: bazaar::globbing::Replacer,
}

#[pymethods]
impl Replacer {
    #[new]
    fn new(source: Option<&Self>) -> Self {
        Self {
            replacer: bazaar::globbing::Replacer::new(source.map(|p| &p.replacer)),
        }
    }

    /// Add a pattern and replacement.
    ///
    /// The pattern must not contain capturing groups.
    /// The replacement might be either a string template in which \& will be
    /// replaced with the match, or a function that will get the matching text
    /// as argument. It does not get match object, because capturing is
    /// forbidden anyway.
    fn add(&mut self, py: Python, pattern: &str, func: PyObject) -> PyResult<()> {
        if let Ok(func) = func.extract::<String>(py) {
            self.replacer
                .add(pattern, bazaar::globbing::Replacement::String(func));
            Ok(())
        } else {
            let callable = Box::new(move |t: String| -> String {
                Python::with_gil(|py| match func.call1(py, (t,)) {
                    Ok(result) => result.extract::<String>(py).unwrap(),
                    Err(e) => {
                        e.restore(py);
                        String::new()
                    }
                })
            });
            self.replacer
                .add(pattern, bazaar::globbing::Replacement::Closure(callable));
            Ok(())
        }
    }

    /// Add all patterns from another replacer.
    ///
    /// All patterns and replacements from replacer are appended to the ones
    /// already defined.
    fn add_replacer(&mut self, replacer: &Self) {
        self.replacer.add_replacer(&replacer.replacer)
    }

    fn __call__(&mut self, py: Python, text: &str) -> PyResult<String> {
        let ret = self
            .replacer
            .replace(text)
            .map_err(|e| PyValueError::new_err(e.to_string()))?;
        if PyErr::occurred(py) {
            Err(PyErr::fetch(py))
        } else {
            Ok(ret)
        }
    }
}

#[pyclass(subclass)]
struct Revision(bazaar::revision::Revision);

/// Single revision on a branch.
///
/// Revisions may know their revision_hash, but only once they've been
/// written out.  This is not stored because you cannot write the hash
/// into the file it describes.
///
/// Attributes:
///   parent_ids: List of parent revision_ids
///
///   properties:
///     Dictionary of revision properties.  These are attached to the
///     revision as extra metadata.  The name must be a single
///     word; the value can be an arbitrary string.
#[pymethods]
impl Revision {
    #[new]
    fn new(
        py: Python,
        revision_id: &PyBytes,
        parent_ids: Vec<&PyBytes>,
        committer: Option<String>,
        message: String,
        properties: Option<HashMap<String, String>>,
        inventory_sha1: Option<Vec<u8>>,
        timestamp: f64,
        timezone: Option<i32>,
    ) -> PyResult<Self> {
        let properties = properties.unwrap_or(HashMap::new());
        if !bazaar::revision::validate_properties(&properties) {
            return Err(PyValueError::new_err(
                "properties must be a dictionary of strings",
            ));
        }
        Ok(Self(bazaar::revision::Revision {
            revision_id: bazaar::RevisionId::from(revision_id.as_bytes().to_vec()),
            parent_ids: parent_ids
                .iter()
                .map(|id| bazaar::RevisionId::from(id.as_bytes().to_vec()))
                .collect(),
            committer,
            message,
            properties,
            inventory_sha1,
            timestamp,
            timezone,
        }))
    }

    fn __richcmp__(&self, other: &Self, op: CompareOp) -> PyResult<bool> {
        match op {
            CompareOp::Eq => Ok(self.0 == other.0),
            CompareOp::Ne => Ok(self.0 != other.0),
            _ => Err(PyNotImplementedError::new_err(
                "only == and != are supported",
            )),
        }
    }

    fn __repr__(self_: PyRef<Self>) -> String {
        format!("<Revision id {:?}>", self_.0.revision_id)
    }

    #[getter]
    fn revision_id(&self, py: Python) -> PyObject {
        PyBytes::new(py, self.0.revision_id.bytes()).into_py(py)
    }

    #[getter]
    fn parent_ids(&self, py: Python) -> PyObject {
        PyList::new(
            py,
            self.0
                .parent_ids
                .iter()
                .map(|id| PyBytes::new(py, id.bytes())),
        )
        .into_py(py)
    }

    #[getter]
    fn committer(&self) -> Option<String> {
        self.0.committer.clone()
    }

    #[getter]
    fn message(&self) -> String {
        self.0.message.clone()
    }

    #[getter]
    fn properties(&self) -> HashMap<String, String> {
        self.0.properties.clone()
    }

    #[getter]
    fn get_inventory_sha1(&self, py: Python) -> PyObject {
        if let Some(sha1) = &self.0.inventory_sha1 {
            PyBytes::new(py, sha1).into_py(py)
        } else {
            py.None()
        }
    }

    #[setter]
    fn set_inventory_sha1(&mut self, py: Python, value: PyObject) -> PyResult<()> {
        if let Ok(value) = value.extract::<&PyBytes>(py) {
            self.0.inventory_sha1 = Some(value.as_bytes().to_vec());
            Ok(())
        } else if value.is_none(py) {
            self.0.inventory_sha1 = None;
            Ok(())
        } else {
            Err(PyTypeError::new_err("expected bytes or None"))
        }
    }

    #[getter]
    fn timestamp(&self) -> f64 {
        self.0.timestamp
    }

    #[getter]
    fn timezone(&self) -> Option<i32> {
        self.0.timezone
    }

    fn datetime(&self) -> PyResult<NaiveDateTime> {
        Ok(self.0.datetime())
    }

    fn check_properties(&self) -> PyResult<()> {
        if self.0.check_properties() {
            Ok(())
        } else {
            Err(PyValueError::new_err("invalid properties"))
        }
    }

    fn get_summary(&self) -> String {
        self.0.get_summary()
    }

    fn get_apparent_authors(&self) -> Vec<String> {
        self.0.get_apparent_authors()
    }

    fn bug_urls(&self) -> Vec<String> {
        self.0.bug_urls()
    }
}

#[pymodule]
fn _bzr_rs(py: Python, m: &PyModule) -> PyResult<()> {
    m.add_wrapped(wrap_pyfunction!(_next_id_suffix))?;
    m.add_wrapped(wrap_pyfunction!(gen_file_id))?;
    m.add_wrapped(wrap_pyfunction!(gen_root_id))?;
    m.add_wrapped(wrap_pyfunction!(gen_revision_id))?;
    let m_globbing = PyModule::new(py, "globbing")?;
    m_globbing.add_wrapped(wrap_pyfunction!(normalize_pattern))?;
    m_globbing.add_class::<Replacer>()?;
    m.add_submodule(m_globbing)?;
    m.add_class::<Revision>()?;
    Ok(())
}
