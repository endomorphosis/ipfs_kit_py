from pathlib import Path

IPFS_KIT_PATH = Path.home() / '.ipfs_kit'

class ResourceManager:
    def get_resources(self):
        total_size = sum(f.stat().st_size for f in IPFS_KIT_PATH.glob('**/*') if f.is_file())
        return {'total_storage_used': total_size}