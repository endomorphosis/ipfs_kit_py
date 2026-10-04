from ipfs_kit_py import IPFSSimpleAPI
from ipfs_kit_py.transformers_integration import TransformersIntegration

transformers = TransformersIntegration()
print("transformers = ", transformers)

# Initialize the API
api = IPFSSimpleAPI()

# Check if transformers integration is available
if transformers is not None:
    # Load a model from auto-download
    model = transformers.from_auto_download("bge-small-en-v1.5")
    print(f"Loaded model: {model}")

    # Or load directly from IPFS
    # model = transformers.from_ipfs("QmccfbkWLYs9K3yucc6b3eSt8s8fKcyRRt24e3CDaeRhM1")

    # Use the model
    # ... model operations ...
else:
    print("Transformers integration not available. Install with:")
    print("pip install ipfs_kit_py[transformers]")
