#!/bin/bash

echo "Creating backup of storage_manager.py..."
cp ipfs_kit_py/mcp/models/storage_manager.py ipfs_kit_py/mcp/models/storage_manager.py.bak

echo "Fixing storage_manager.py..."

# Fix the __init__ method parameters
sed -i 's/    def __init__(/    def __init__(self,/' ipfs_kit_py/mcp/models/storage_manager.py
sed -i 's/        self/        self,/' ipfs_kit_py/mcp/models/storage_manager.py
sed -i 's/ipfs_model = None/ipfs_model = None,/' ipfs_kit_py/mcp/models/storage_manager.py
sed -i 's/cache_manager = None/cache_manager = None,/' ipfs_kit_py/mcp/models/storage_manager.py
sed -i 's/credential_manager = None/credential_manager = None,/' ipfs_kit_py/mcp/models/storage_manager.py
sed -i 's/resources = None/resources = None,/' ipfs_kit_py/mcp/models/storage_manager.py
sed -i 's/metadata = None/metadata = None):/' ipfs_kit_py/mcp/models/storage_manager.py

# Fix logger.info with missing parenthesis
sed -i 's/            f"Storage Manager initialized with backends: {", ".join(self.storage_models.keys())}"/            f"Storage Manager initialized with backends: {", ".join(self.storage_models.keys())}")/' ipfs_kit_py/mcp/models/storage_manager.py

# Fix S3 model initialization
sed -i 's/s3_kit_instance=s3_kit_instance/s3_kit_instance=s3_kit_instance,/' ipfs_kit_py/mcp/models/storage_manager.py
sed -i 's/ipfs_model=self.ipfs_model/ipfs_model=self.ipfs_model,/' ipfs_kit_py/mcp/models/storage_manager.py
sed -i 's/cache_manager=self.cache_manager/cache_manager=self.cache_manager,/' ipfs_kit_py/mcp/models/storage_manager.py
sed -i 's/credential_manager=self.credential_manager/credential_manager=self.credential_manager)/' ipfs_kit_py/mcp/models/storage_manager.py

# Fix Hugging Face model initialization
sed -i 's/huggingface_kit_instance=hf_kit_instance/huggingface_kit_instance=hf_kit_instance,/' ipfs_kit_py/mcp/models/storage_manager.py
sed -i 's/ipfs_model=self.ipfs_model/ipfs_model=self.ipfs_model,/' ipfs_kit_py/mcp/models/storage_manager.py
sed -i 's/cache_manager=self.cache_manager/cache_manager=self.cache_manager,/' ipfs_kit_py/mcp/models/storage_manager.py
sed -i 's/credential_manager=self.credential_manager/credential_manager=self.credential_manager)/' ipfs_kit_py/mcp/models/storage_manager.py

# Fix logger.info with missing parenthesis
sed -i 's/                "Hugging Face Hub not available. Install with: pip install ipfs_kit_py\[huggingface\]"/                "Hugging Face Hub not available. Install with: pip install ipfs_kit_py\[huggingface\]")/' ipfs_kit_py/mcp/models/storage_manager.py

# Fix missing parenthesis in storacha_kit initialization
sed -i 's/                resources=storacha_resources, metadata=storacha_metadata/                resources=storacha_resources, metadata=storacha_metadata)/' ipfs_kit_py/mcp/models/storage_manager.py

# Fix Storacha model initialization
sed -i 's/storacha_kit_instance=storacha_kit_instance/storacha_kit_instance=storacha_kit_instance,/' ipfs_kit_py/mcp/models/storage_manager.py
sed -i 's/ipfs_model=self.ipfs_model/ipfs_model=self.ipfs_model,/' ipfs_kit_py/mcp/models/storage_manager.py
sed -i 's/cache_manager=self.cache_manager/cache_manager=self.cache_manager,/' ipfs_kit_py/mcp/models/storage_manager.py
sed -i 's/credential_manager=self.credential_manager/credential_manager=self.credential_manager)/' ipfs_kit_py/mcp/models/storage_manager.py

# Fix missing parenthesis in lotus_kit initialization
sed -i 's/                    resources=filecoin_resources, metadata=filecoin_metadata/                    resources=filecoin_resources, metadata=filecoin_metadata)/' ipfs_kit_py/mcp/models/storage_manager.py

# Fix Filecoin model initialization
sed -i 's/lotus_kit_instance=lotus_kit_instance/lotus_kit_instance=lotus_kit_instance,/' ipfs_kit_py/mcp/models/storage_manager.py
sed -i 's/ipfs_model=self.ipfs_model/ipfs_model=self.ipfs_model,/' ipfs_kit_py/mcp/models/storage_manager.py
sed -i 's/cache_manager=self.cache_manager/cache_manager=self.cache_manager,/' ipfs_kit_py/mcp/models/storage_manager.py
sed -i 's/credential_manager=self.credential_manager/credential_manager=self.credential_manager)/' ipfs_kit_py/mcp/models/storage_manager.py

# Fix logger.info with missing parenthesis for Lotus kit
sed -i 's/            "Lotus kit not available. Install with: pip install ipfs_kit_py\[filecoin\]"/            "Lotus kit not available. Install with: pip install ipfs_kit_py\[filecoin\]")/' ipfs_kit_py/mcp/models/storage_manager.py

# Fix missing parenthesis in lassie_kit initialization
sed -i 's/                    resources=lassie_resources, metadata=lassie_metadata/                    resources=lassie_resources, metadata=lassie_metadata)/' ipfs_kit_py/mcp/models/storage_manager.py

# Fix Lassie model initialization
sed -i 's/lassie_kit_instance=lassie_kit_instance/lassie_kit_instance=lassie_kit_instance,/' ipfs_kit_py/mcp/models/storage_manager.py
sed -i 's/ipfs_model=self.ipfs_model/ipfs_model=self.ipfs_model,/' ipfs_kit_py/mcp/models/storage_manager.py
sed -i 's/cache_manager=self.cache_manager/cache_manager=self.cache_manager,/' ipfs_kit_py/mcp/models/storage_manager.py
sed -i 's/credential_manager=self.credential_manager/credential_manager=self.credential_manager)/' ipfs_kit_py/mcp/models/storage_manager.py

# Fix logger.info with missing parenthesis for Lassie kit
sed -i 's/            "Lassie kit not available. Install with: pip install ipfs_kit_py\[filecoin\]"/            "Lassie kit not available. Install with: pip install ipfs_kit_py\[filecoin\]")/' ipfs_kit_py/mcp/models/storage_manager.py

# Fix aggregate stats dictionary missing commas
sed -i 's/"total_operations": total_operations/"total_operations": total_operations,/' ipfs_kit_py/mcp/models/storage_manager.py
sed -i 's/"bytes_uploaded": total_uploaded/"bytes_uploaded": total_uploaded,/' ipfs_kit_py/mcp/models/storage_manager.py
sed -i 's/"bytes_downloaded": total_downloaded/"bytes_downloaded": total_downloaded,/' ipfs_kit_py/mcp/models/storage_manager.py

echo "Running Black on the fixed file..."
black ipfs_kit_py/mcp/models/storage_manager.py

echo "Running Ruff on the fixed file..."
ruff check --fix ipfs_kit_py/mcp/models/storage_manager.py

echo "Done with storage_manager.py"