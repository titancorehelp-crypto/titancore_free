use pyo3::prelude::*;
use pyo3::exceptions::PyRuntimeError;
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::{Instant};
use parking_lot::Mutex;
use std::collections::VecDeque;

// --- GLOBAL STATE ---
static OPERATION_CTR: AtomicU64 = AtomicU64::new(0);
const MAX_BURST_REQUESTS: usize = 15;
const RATE_LIMIT_WINDOW: u64 = 3;

#[pyclass]
pub struct SovereignEngine {
    rate_history: Mutex<VecDeque<Instant>>,
}

#[pymethods]
impl SovereignEngine {
    #[new]
    fn new(_hw_info: String, _seed: String, _license_sig: String, _log_path: String) -> PyResult<Self> {
        Ok(SovereignEngine {
            rate_history: Mutex::new(VecDeque::with_capacity(MAX_BURST_REQUESTS))
        })
    }

    pub fn vault_execute(&self, data: Vec<u8>, _pk_bytes: Vec<u8>) -> PyResult<(Vec<u8>, Vec<u8>, String)> {
        let current_ctr = OPERATION_CTR.fetch_add(1, Ordering::Relaxed) + 1;
        if self.check_rate_limit() {
            return Err(PyRuntimeError::new_err("Rate limit exceeded"));
        }
        let result = data;
        let mock_ct = vec![0u8; 16];
        let audit_ref = format!("FREE-AUDIT-{}", current_ctr);
        Ok((result, mock_ct, audit_ref))
    }
}

impl SovereignEngine {
    fn check_rate_limit(&self) -> bool {
        let now = Instant::now();
        let mut history = self.rate_history.lock();
        while let Some(&t) = history.front() {
            if now.duration_since(t).as_secs() > RATE_LIMIT_WINDOW {
                history.pop_front();
            } else { break; }
        }
        if history.len() >= MAX_BURST_REQUESTS { return true; }
        history.push_back(now);
        false
    }
}
