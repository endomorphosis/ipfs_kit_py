import json
from pathlib import Path
import logging
import time

logger = logging.getLogger(__name__)

IPFS_KIT_PATH = Path.home() / '.ipfs_kit'
SERVICES_PATH = IPFS_KIT_PATH / 'services.json'

class ServiceManager:
    def __init__(self):
        self.services_data = self._load_services()

    def _load_services(self):
        if not SERVICES_PATH.exists():
            return []
        try:
            with open(SERVICES_PATH, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading services data: {e}")
            return []

    def _save_services(self):
        SERVICES_PATH.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(SERVICES_PATH, 'w') as f:
                json.dump(self.services_data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving services data: {e}")

    def list_services(self):
        return {"services": self.services_data, "total": len(self.services_data)}

    def get_service_status(self, service_name):
        for service in self.services_data:
            if service.get("name") == service_name:
                return {"service": service}
        return {"error": "Service not found"}

    def start_service(self, service_name):
        for service in self.services_data:
            if service.get("name") == service_name:
                service["status"] = "running"
                service["last_action"] = time.time()
                self._save_services()
                return {"status": "Service started", "service": service}
        return {"error": "Service not found"}

    def stop_service(self, service_name):
        for service in self.services_data:
            if service.get("name") == service_name:
                service["status"] = "stopped"
                service["last_action"] = time.time()
                self._save_services()
                return {"status": "Service stopped", "service": service}
        return {"error": "Service not found"}
