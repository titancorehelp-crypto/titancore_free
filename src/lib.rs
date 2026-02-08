use pyo3::prelude::*;
use pyo3::exceptions::{PyRuntimeError, PyPermissionError, PyIOError};
use aes_gcm_siv::{Aes256GcmSiv, Key, Nonce, aead::{Aead, KeyInit}};
use pqcrypto_kyber::kyber1024;
use pqcrypto_dilithium::dilithium5;
use pqcrypto_traits::kem::{PublicKey as KEMPublicKey, Ciphertext as KEMCiphertext, SharedSecret as KEMSharedSecret};
use sha2::Sha256;
use hkdf::Hkdf;
use zeroize::{Zeroize, Zeroizing};
use blake3;
use getrandom;
use parking_lot::Mutex;
use std::collections::VecDeque;
use std::fs::OpenOptions;
use std::io::Write;
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::{Instant, SystemTime, UNIX_EPOCH};
use rand::Rng;

// --- GLOBAL STATE ---
static AUDIT_CHAIN: Mutex<[u8;32]> = Mutex::new([0u8;32]);
static OPERATION_CTR: AtomicU64 = AtomicU64::new(0);
const RATE_LIMIT_WINDOW: u64 = 3;
const MAX_BURST_REQUESTS: usize = 15;

// --- PLACEHOLDER KEYS ---
const KEY_PART_1: &[u8] = &[0xAB]; 
const KEY_PART_2: &[u8] = &[0xCD];
const KEY_PART_3: &[u8] = &[0xEF];

#[pyclass]
pub struct SovereignEngine {
    fingerprint: [u8;32],
    #[pyo3(get)]
    log_path: String,
    #[pyo3(get)]
    is_authorized: bool,
    rate_history: Mutex<VecDeque<Instant>>,
}

#[pymethods]
impl SovereignEngine {
    #[new]
    fn new(hw_info: String, seed: String, _license_sig: String, log_path: String) -> PyResult<Self> {
        // Hardware fingerprint
        let mut hasher = blake3::Hasher::new();
        hasher.update(hw_info.as_bytes());
        hasher.update(seed.as_bytes());
        let fingerprint: [u8;32] = hasher.finalize().into();

        // Dummy license verification
        let is_auth = true;
        if !is_auth {
            return Err(PyPermissionError::new_err("Authentication Failed"));
        }

        Ok(SovereignEngine{
            fingerprint,
            log_path,
            is_authorized: true,
            rate_history: Mutex::new(VecDeque::with_capacity(MAX_BURST_REQUESTS)),
        })
    }

    pub fn vault_execute(&self, data: Vec<u8>, pk_bytes: Vec<u8>) -> PyResult<(Vec<u8>, Vec<u8>, String)> {
        // Rate limit check
        if self.check_rate_limit() {
            return Err(PyRuntimeError::new_err("Rate Limit Exceeded"));
        }

        let current_ctr = OPERATION_CTR.fetch_add(1, Ordering::Relaxed) + 1;

        // PQC Key Encapsulation (Kyber)
        let pk = kyber1024::PublicKey::from_bytes(&pk_bytes)
            .map_err(|_| PyRuntimeError::new_err("Invalid PQC Key"))?;
        let (pqc_ct, shared_secret) = kyber1024::encapsulate(&pk);

        // Derive AES session key using HKDF
        let mut sess_key = [0u8;32];
        {
            let mut ikm = Zeroizing::new(Vec::with_capacity(64));
            ikm.extend_from_slice(shared_secret.as_bytes());
            ikm.extend_from_slice(&self.fingerprint);
            ikm.extend_from_slice(&current_ctr.to_be_bytes());

            let hk = Hkdf::<Sha256>::new(None, &ikm);
            hk.expand(b"TITAN_V18_1_DIAMOND", &mut sess_key)
                .map_err(|_| PyRuntimeError::new_err("KDF failed"))?;
        }

        // AES-256-GCM-SIV encryption
        let mut nonce = [0u8;12];
        nonce[..8].copy_from_slice(&current_ctr.to_be_bytes());
        getrandom::getrandom(&mut nonce[8..]).map_err(|_| PyRuntimeError::new_err("Entropy fail"))?;

        let cipher = Aes256GcmSiv::new(Key::from_slice(&sess_key));
        let ct = cipher.encrypt(Nonce::from_slice(&nonce), data.as_slice())
            .map_err(|_| PyRuntimeError::new_err("Encryption fail"))?;

        // Audit log
        let evidence = self.append_to_audit(current_ctr, &nonce, &ct, pqc_ct.as_bytes())?;

        Ok((ct, pqc_ct.as_bytes().to_vec(), evidence))
    }
}

// --- Internal logic ---
impl SovereignEngine {
    fn check_rate_limit(&self) -> bool {
        let now = Instant::now();
        let mut history = self.rate_history.lock();
        while let Some(&t) = history.front() {
            if now.duration_since(t).as_secs() > RATE_LIMIT_WINDOW { history.pop_front(); }
            else { break; }
        }
        if history.len() >= MAX_BURST_REQUESTS { return true; }
        history.push_back(now);
        false
    }

    fn append_to_audit(&self, ctr: u64, nonce: &[u8], ct: &[u8], pqc_ct: &[u8]) -> PyResult<String> {
        let mut chain_guard = AUDIT_CHAIN.lock();
        let prev_h = *chain_guard;

        let mut hasher = blake3::Hasher::new();
        hasher.update(&prev_h);
        hasher.update(&ctr.to_be_bytes());
        hasher.update(&self.fingerprint);
        hasher.update(pqc_ct);
        hasher.update(nonce);
        hasher.update(ct);
        let curr_h: [u8;32] = hasher.finalize().into();

        let timestamp = SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_secs();
        let entry = format!("{}|{}|{}|{}\n", hex::encode(prev_h), hex::encode(curr_h), ctr, timestamp);

        let mut file = OpenOptions::new().create(true).append(true).open(&self.log_path)
            .map_err(|e| PyIOError::new_err(format!("Storage error: {}", e)))?;
        file.write_all(entry.as_bytes()).map_err(|_| PyIOError::new_err("Write fail"))?;
        file.sync_data().map_err(|_| PyIOError::new_err("Sync fail"))?;

        *chain_guard = curr_h;
        Ok(hex::encode(curr_h))
    }
}
