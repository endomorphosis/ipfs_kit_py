import os
from pathlib import Path

IPFS_KIT_PATH = Path.home() / '.ipfs_kit'
LOGS_PATH = IPFS_KIT_PATH / 'logs'

class LogManager:
    def __init__(self):
        LOGS_PATH.mkdir(exist_ok=True)

    def get_logs(self, component=None):
        logs = []
        for log_file in os.listdir(LOGS_PATH):
            if component and component not in log_file:
                continue
            with open(LOGS_PATH / log_file, 'r') as f:
                logs.extend(f.readlines())
        return logs