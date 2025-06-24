from ipfs_kit_py import storacha_kit
from ipfs_kit_py import s3_kit

class s3_to_storacha:
    def __init__(self, resources, metadata):
        self.metadata = metadata
        self.resources = resources
        self.storacha_kit = storacha_kit(resources, metadata)
        self.s3_kit = s3_kit(resources, metadata)
        return None
