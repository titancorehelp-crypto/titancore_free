import json
import logging
import time
from typing import Optional, Dict, Any
import titancore_free as core

class NebulaConfig:
    VERSION = "FREE-1.0"
    LOG_FORMAT = "%(asctime)s | %(levelname)s | [%(node_id)s] | %(message)s"
    HEARTBEAT_INTERVAL = 10
    REQUIRED_KEYS = ["node_id", "hw_id"]
    DEFAULTS = {
        "audit_log": "free_audit.log",
    }

def setup_logger(node_id: str):
    logging.basicConfig(level=logging.INFO,
                        format=NebulaConfig.LOG_FORMAT,
                        handlers=[logging.StreamHandler()])
    return logging.LoggerAdapter(logging.getLogger("NebulaFree"), {"node_id": node_id})

class NebulaPrime:
    def __init__(self, config_path: str):
        raw_config = self._load_json(config_path)
        self.config = {**NebulaConfig.DEFAULTS, **raw_config}
        self._validate_config()
        self.logger = setup_logger(self.config["node_id"])
        self.is_active = False
        self.engine = self._init_sovereign_core()
        self.is_active = True
        self.logger.info(f"🚀 Nebula Free Node Online | Version {NebulaConfig.VERSION}")

    def _load_json(self, path: str) -> Dict[str, Any]:
        with open(path, 'r') as f:
            return json.load(f)

    def _validate_config(self):
        missing = [k for k in NebulaConfig.REQUIRED_KEYS if k not in self.config]
        if missing:
            raise ValueError(f"Missing keys: {missing}")

    def _init_sovereign_core(self):
        return core.SovereignEngine(
            hw_info=self.config['hw_id'],
            seed="FREE-SEED",
            license_sig="",
            log_path=self.config['audit_log']
        )

    def execute_vault(self, data: bytes, pk: bytes) -> Optional[Dict[str, Any]]:
        if not self.is_active: return None
        res = self.engine.vault_execute(data, pk)
        return {"status": "SUCCESS", "payload": res[0], "audit_ref": res[2]}

    def run_forever(self):
        self.logger.info("Entering continuous loop...")
        try:
            while self.is_active:
                self.logger.info("HEARTBEAT")
                time.sleep(NebulaConfig.HEARTBEAT_INTERVAL)
        except KeyboardInterrupt:
            self.is_active = False
            self.logger.info("Shutdown signal received.")
