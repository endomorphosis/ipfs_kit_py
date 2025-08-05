from .config import get_config
from .enhanced_daemon_manager import EnhancedDaemonManager

class HealthManager:
    def check_health(self, backend=None):
        health = {}
        # Check daemon status
        daemon_manager = EnhancedDaemonManager()
        daemon_status = daemon_manager.check_daemon_status()
        health['daemon'] = 'Running' if daemon_status.get('running') else 'Stopped'

        # Check backend status
        config = get_config()
        backends = config.get('backends', {})
        for name, backend_config in backends.items():
            if backend and name != backend:
                continue
            # This is a placeholder for actually checking the backend health
            health[name] = 'Healthy'

        return health