import os
from pathlib import Path

IPFS_KIT_PATH = Path.home() / '.ipfs_kit'
BUCKETS_PATH = IPFS_KIT_PATH / 'buckets'

class BucketManager:
    def __init__(self):
        BUCKETS_PATH.mkdir(exist_ok=True)

    def list_buckets(self):
        buckets = []
        for bucket_name in os.listdir(BUCKETS_PATH):
            bucket_path = BUCKETS_PATH / bucket_name
            if bucket_path.is_dir():
                size = sum(f.stat().st_size for f in bucket_path.glob('**/*') if f.is_file())
                files = len(list(bucket_path.glob('**/*')))
                buckets.append({"name": bucket_name, "size": size, "files": files})
        return buckets

    def create_bucket(self, name, **kwargs):
        (BUCKETS_PATH / name).mkdir(exist_ok=True)
        return {"status": "Bucket created"}

    def remove_bucket(self, name):
        (BUCKETS_PATH / name).rmdir()
        return {"status": "Bucket removed"}

    def upload_file(self, bucket_name, file_name, file_content):
        (BUCKETS_PATH / bucket_name / file_name).write_bytes(file_content)
        return {"status": "File uploaded"}

    def list_files(self, bucket_name):
        files = []
        bucket_path = BUCKETS_PATH / bucket_name
        if bucket_path.is_dir():
            for file_path in bucket_path.iterdir():
                if file_path.is_file():
                    files.append({"name": file_path.name, "size": file_path.stat().st_size})
        return files