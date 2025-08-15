from ipfs_kit_py import s3_kit


class test_s3_kit:
    def __init__(self, resources, metadata):
        self.metadata = metadata
        self.resources = resources
        self.s3_kit = s3_kit(resources, metadata)
        return None

    def test(self):
        results = {}
        try:
            s3_kit = self.s3_kit.test()
            results["s3_kit"] = s3_kit
        except Exception as e:
            results["s3_kit"] = e
        return results
