from ipfs_kit_py import install_ipfs


class test_install_ipfs_kit:
    def __init__(self, resources, metadata):
        self.metadata = metadata
        self.resources = resources
        self.install_ipfs = install_ipfs(resources, metadata)
        return None

    def test(self):
        results = {}
        try:
            install_ipfs = self.install_ipfs.test()
            results["install_ipfs"] = install_ipfs
        except Exception as e:
            results["install_ipfs"] = e
        return results
