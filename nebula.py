import os
import logging
import json
import time
import gc
from datetime import datetime
from typing import Optional, Dict, Any

# Import Rust SovereignEngine (PyO3 compiled)
import titancore_free as core

# -------------------------------
# Logging Setup
# -------------------------------
def setup_logger(node_id: str) -> logging.LoggerAdapter:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | [%(node_id)s] | %(message)s",
        handlers=[logging.FileHandler("nebula_system.log"), logging.StreamHandler()]
    )
    return logging.LoggerAdapter(logging.getLogger("NebulaPrime"), {"node_id": node_id})

# -------------------------------
# Config Defaults
# -------------------------------
class NebulaConfig:
    VERSION = "15.3.0-FREE"
    HEARTBEAT_INTERVAL = 30
    MAX_ANOMALY_SCORE = 5
    REQUIRED_KEYS = ["node_id", "hw_id"]
    DEFAULTS = {
        "audit_log": "nebula_audit.log",
        "heartbeat_url": "https://api.nebula-hq.com/v1/heartbeat",
    }

# -------------------------------
# NebulaPrime Node
# -------------------------------
class NebulaPrime:
    def __init__(self, config_path: str):
        raw_config = self._load_json(config_path)
        self.config = {**NebulaConfig.DEFAULTS, **raw_config}
        self._validate_config()

        self.logger = setup_logger(self.config["node_id"])
        self.is_active: bool = False
        self.anomaly_count: int = 0

        # Init Rust core
        self.engine = self._init_sovereign_core()
        self.is_active = True
        self.logger.info(f"NebulaFree Node Online. Version: {NebulaConfig.VERSION}")

    def _load_json(self, path: str) -> Dict[str, Any]:
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"FATAL: Config load failed: {e}")
            exit(1)

    def _validate_config(self) -> None:
        missing = [k for k in NebulaConfig.REQUIRED_KEYS if k not in self.config]
        if missing:
            print(f"FATAL: Missing mandatory config keys: {missing}")
            exit(1)

    def _init_sovereign_core(self) -> core.SovereignEngine:
        license_key = os.getenv("TITAN_LICENSE_KEY", "FREE_LICENSE")
        root_seed = os.getenv("TITAN_ROOT_SEED", "FREE_SEED")

        return core.SovereignEngine(
            hw_info=self.config['hw_id'],
            seed=root_seed,
            license_sig=license_key,
            log_path=self.config['audit_log']
        )

    def execute_vault(self, data: bytes, pk: bytes) -> Optional[Dict[str, Any]]:
        if not self.is_active: return None
        try:
            ct, pqc_ct, ref = self.engine.vault_execute(data, pk)
            self.logger.info(f"Vault Success | Ref: {ref[:12]}")
            return {"status": "SUCCESS", "payload": ct, "audit_ref": ref}
        except Exception as e:
            self.anomaly_count += 1
            self.logger.warning(f"Anomaly {self.anomaly_count}/{NebulaConfig.MAX_ANOMALY_SCORE}: {e}")
            if self.anomaly_count >= NebulaConfig.MAX_ANOMALY_SCORE:
                self._kill_switch()
            return None

    def emit_heartbeat(self) -> bool:
        payload = {
            "node": self.config["node_id"],
            "status": "ACTIVE" if self.is_active else "COMPROMISED",
            "anomalies": self.anomaly_count,
            "ts": datetime.now().isoformat()
        }
        self.logger.info(f"HEARTBEAT -> Sending telemetry to {self.config['heartbeat_url']}")
        return True

    def _kill_switch(self):
        self.logger.critical("EMERGENCY: Max anomalies reached. Shutting down.")
        self.is_active = False
        if hasattr(self, 'engine'): del self.engine
        self.config.clear()
        gc.collect()
        exit("NODE_LOCKED")

    def run_forever(self):
        self.logger.info("Entering continuous operational mode...")
        try:
            while self.is_active:
                self.emit_heartbeat()
                time.sleep(NebulaConfig.HEARTBEAT_INTERVAL)
        except KeyboardInterrupt:
            self.logger.info("System shutdown signal received.")
            self.is_active = False

# -------------------------------
# Quick Launch (Free Node)
# -------------------------------
if __name__ == "__main__":
    os.environ["TITAN_LICENSE_KEY"] = "FREE_LICENSE"
    os.environ["TITAN_ROOT_SEED"] = "FREE_SEED"

    cfg = {"node_id": "FREE-01", "hw_id": "FREE-HW-001"}
    with open("free_node.json", "w") as f: json.dump(cfg, f)

    nebula = NebulaPrime("free_node.json")
    nebula.run_forever()
