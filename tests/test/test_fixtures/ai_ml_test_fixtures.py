"""
Test fixtures for AI/ML integration testing.

This module provides specialized fixtures for testing AI/ML integration features,
including mocks for common ML frameworks, dataset handling, and distributed training.
"""

import json
import os
import pickle
import tempfile
import time
import uuid
from unittest.mock import MagicMock, patch

import numpy as np

# Create path if it doesn't exist
os.makedirs(os.path.dirname(os.path.abspath(__file__)), exist_ok=True)


class MockMLModel:
    """Base class for mock ML models across frameworks."""
    
    def __init__(self, name="mock_model", model_type="classification", framework="base"):
        """Initialize a mock ML model.
        
        Args:
            name: Model name
            model_type: Type of model (classification, regression, etc.)
            framework: ML framework (sklearn, pytorch, tensorflow, etc.)
        """
        self.name = name
        self.model_type = model_type
        self.framework = framework
        self.params = {
            "hidden_size": 128,
            "learning_rate": 0.01,
            "optimizer": "adam"
        }
        self.state = {
            "epoch": 0,
            "trained": False,
            "accuracy": 0.0
        }
    
    def train(self, epochs=10, learning_rate=None):
        """Simulate model training."""
        if learning_rate:
            self.params["learning_rate"] = learning_rate
        
        # Simulate training progress
        for i in range(epochs):
            self.state["epoch"] += 1
            # Simulate accuracy improvement with diminishing returns
            improvement = 0.1 * (1.0 - self.state["accuracy"]) * (1.0 - i / epochs)
            self.state["accuracy"] += improvement
        
        self.state["trained"] = True
        return self.state["accuracy"]
    
    def predict(self, data):
        """Simulate prediction."""
        if not self.state["trained"]:
            raise ValueError("Model not trained")
        
        # Generate random predictions based on data and accuracy
        if isinstance(data, list):
            n_samples = len(data)
        elif hasattr(data, "shape"):
            n_samples = data.shape[0]
        else:
            n_samples = 1
            
        # Create random predictions, more accurate if model is better trained
        if self.model_type == "classification":
            return np.random.randint(0, 2, size=n_samples)
        else:
            base = np.random.normal(0, 1, size=n_samples)
            # Add signal based on accuracy
            signal = np.random.normal(0, 1 - self.state["accuracy"], size=n_samples)
            return base + signal
    
    def save(self, path):
        """Save model to disk."""
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump({
                "name": self.name,
                "model_type": self.model_type,
                "framework": self.framework,
                "params": self.params,
                "state": self.state
            }, f)
        return path
    
    @classmethod
    def load(cls, path):
        """Load model from disk."""
        with open(path, "rb") as f:
            data = pickle.load(f)
        
        model = cls(
            name=data["name"],
            model_type=data["model_type"],
            framework=data["framework"]
        )
        model.params = data["params"]
        model.state = data["state"]
        return model
    
    def get_embedding(self, text):
        """Generate a mock embedding for text input."""
        # Create a deterministic but unique embedding based on input
        import hashlib
        # Get hash of input
        hash_obj = hashlib.md5(str(text).encode())
        hash_bytes = hash_obj.digest()
        
        # Convert to a vector of 64 dimensions
        embedding = []
        for i in range(64):
            # Use bytes from hash to seed the embedding values
            val = float(hash_bytes[i % 16]) / 255.0
            embedding.append(val)
            
        return np.array(embedding)


class MockSklearnModel(MockMLModel):
    """Mock for scikit-learn models."""
    
    def __init__(self, name="sklearn_model", model_type="classification"):
        """Initialize a mock scikit-learn model."""
        super().__init__(name, model_type, framework="sklearn")
        
        # Add sklearn-specific attributes
        self.feature_importances_ = np.random.rand(10)
        self.classes_ = np.array([0, 1])
        
    def fit(self, X, y):
        """Sklearn-style fit method."""
        # Extract epochs from data size
        epochs = min(10, len(X) // 10 + 1)
        self.train(epochs=epochs)
        return self
    
    def predict(self, X):
        """Sklearn-style predict method."""
        return super().predict(X)
    
    def predict_proba(self, X):
        """Sklearn-style predict_proba method."""
        if not self.state["trained"]:
            raise ValueError("Model not trained")
            
        if isinstance(X, list):
            n_samples = len(X)
        elif hasattr(X, "shape"):
            n_samples = X.shape[0]
        else:
            n_samples = 1
            
        # Generate probabilities biased by accuracy
        probs = np.random.rand(n_samples, 2)
        probs = probs / probs.sum(axis=1, keepdims=True)  # Normalize to sum to 1
        
        # Make more confident with higher accuracy
        confidence = 0.5 + 0.5 * self.state["accuracy"]
        probs = (probs - 0.5) * confidence * 2 + 0.5
        probs = probs / probs.sum(axis=1, keepdims=True)  # Renormalize
        
        return probs
    
    def score(self, X, y):
        """Sklearn-style score method."""
        return float(self.state["accuracy"])


class MockPyTorchModel(MockMLModel):
    """Mock for PyTorch models."""
    
    def __init__(self, name="pytorch_model", model_type="classification"):
        """Initialize a mock PyTorch model."""
        super().__init__(name, model_type, framework="pytorch")
        
        # Add PyTorch-specific attributes and methods
        self.training = True
        self._modules = {}
        self._parameters = {}
    
    def __call__(self, x):
        """Forward pass for PyTorch model."""
        if self.model_type == "classification":
            batch_size = x.shape[0] if hasattr(x, "shape") else 1
            return MagicMock(shape=(batch_size, 2))
        else:
            batch_size = x.shape[0] if hasattr(x, "shape") else 1
            return MagicMock(shape=(batch_size, 1))
    
    def forward(self, x):
        """PyTorch forward method."""
        return self.__call__(x)
    
    def train(self, mode=True):
        """PyTorch-style train mode setter."""
        self.training = mode
        return self
    
    def eval(self):
        """PyTorch-style eval mode setter."""
        self.training = False
        return self
    
    def to(self, device):
        """PyTorch-style device movement."""
        return self
    
    def parameters(self):
        """PyTorch-style parameters iterator."""
        return MagicMock()
    
    def state_dict(self):
        """PyTorch-style state dict."""
        return {
            "name": self.name,
            "model_type": self.model_type,
            "params": self.params,
            "state": self.state,
            "weights": {
                "layer1.weight": np.random.rand(64, 128),
                "layer1.bias": np.random.rand(128),
                "layer2.weight": np.random.rand(128, 64),
                "layer2.bias": np.random.rand(64)
            }
        }
    
    def load_state_dict(self, state_dict):
        """PyTorch-style state dict loading."""
        self.name = state_dict.get("name", self.name)
        self.model_type = state_dict.get("model_type", self.model_type)
        if "params" in state_dict:
            self.params = state_dict["params"]
        if "state" in state_dict:
            self.state = state_dict["state"]
        return self


class MockTensorflowModel(MockMLModel):
    """Mock for TensorFlow models."""
    
    def __init__(self, name="tensorflow_model", model_type="classification"):
        """Initialize a mock TensorFlow model."""
        super().__init__(name, model_type, framework="tensorflow")
        
        # Add TensorFlow-specific attributes
        self.trainable_weights = [MagicMock() for _ in range(4)]
        self.non_trainable_weights = [MagicMock() for _ in range(2)]
        self.trainable = True
    
    def __call__(self, x):
        """Call method for TensorFlow model."""
        return self.predict(x)
    
    def fit(self, x, y, epochs=10, batch_size=32, verbose=0, callbacks=None):
        """TensorFlow-style fit method."""
        self.train(epochs=epochs)
        
        # Create a history object
        history = MagicMock()
        history.history = {
            "loss": [1.0 - (i / epochs) * self.state["accuracy"] for i in range(epochs)],
            "accuracy": [self.state["accuracy"] * i / epochs for i in range(epochs)]
        }
        
        return history
    
    def predict(self, x, batch_size=None):
        """TensorFlow-style predict method."""
        return super().predict(x)
    
    def save(self, path, save_format=None):
        """TensorFlow-style save method."""
        os.makedirs(path, exist_ok=True)
        
        # Save model.json
        with open(os.path.join(path, "model.json"), "w") as f:
            json.dump({
                "name": self.name,
                "model_type": self.model_type,
                "framework": self.framework,
                "keras_version": "2.8.0",
                "backend": "tensorflow"
            }, f)
            
        # Save weights.h5 (mock)
        with open(os.path.join(path, "weights.h5"), "wb") as f:
            pickle.dump({
                "params": self.params,
                "state": self.state
            }, f)
            
        return path
    
    @classmethod
    def load_model(cls, path):
        """TensorFlow-style load_model method."""
        # Load model.json
        with open(os.path.join(path, "model.json"), "r") as f:
            model_data = json.load(f)
            
        # Create model
        model = cls(
            name=model_data["name"],
            model_type=model_data["model_type"]
        )
        
        # Load weights.h5
        with open(os.path.join(path, "weights.h5"), "rb") as f:
            weights_data = pickle.load(f)
            model.params = weights_data["params"]
            model.state = weights_data["state"]
            
        return model
    
    def to_json(self):
        """TensorFlow-style to_json method."""
        return json.dumps({
            "name": self.name,
            "model_type": self.model_type,
            "framework": self.framework,
            "keras_version": "2.8.0",
            "backend": "tensorflow",
            "config": {
                "layers": [
                    {"name": "input", "class_name": "InputLayer", "config": {"shape": [None, 10]}},
                    {"name": "dense1", "class_name": "Dense", "config": {"units": 128}},
                    {"name": "dense2", "class_name": "Dense", "config": {"units": 64}},
                    {"name": "output", "class_name": "Dense", "config": {"units": 2}}
                ]
            }
        })
    
    def get_config(self):
        """TensorFlow-style get_config method."""
        return {
            "name": self.name,
            "layers": [
                {"name": "input", "class_name": "InputLayer", "config": {"shape": [None, 10]}},
                {"name": "dense1", "class_name": "Dense", "config": {"units": 128}},
                {"name": "dense2", "class_name": "Dense", "config": {"units": 64}},
                {"name": "output", "class_name": "Dense", "config": {"units": 2}}
            ]
        }


class MockDataset:
    """Mock dataset for AI/ML testing."""
    
    def __init__(self, name="mock_dataset", size=1000, n_features=10, n_classes=2, 
                format_type="tabular", embedded=False):
        """Initialize a mock dataset.
        
        Args:
            name: Dataset name
            size: Number of samples
            n_features: Number of features per sample
            n_classes: Number of classes for classification
            format_type: Dataset type (tabular, text, image, audio, etc.)
            embedded: Whether the dataset has pre-computed embeddings
        """
        self.name = name
        self.size = size
        self.n_features = n_features
        self.n_classes = n_classes
        self.format_type = format_type
        self.embedded = embedded
        self.metadata = {
            "name": name,
            "size": size,
            "n_features": n_features,
            "n_classes": n_classes,
            "format_type": format_type,
            "embedded": embedded,
            "created_at": time.time()
        }
        self.samples = self._generate_samples()
    
    def _generate_samples(self):
        """Generate mock samples."""
        samples = []
        
        for i in range(self.size):
            if self.format_type == "tabular":
                # Generate tabular data
                features = np.random.rand(self.n_features).tolist()
                label = np.random.randint(0, self.n_classes)
                
                sample = {
                    "id": f"sample-{i}",
                    "features": features,
                    "label": label
                }
                
                if self.embedded:
                    sample["embedding"] = np.random.rand(64).tolist()
                    
            elif self.format_type == "text":
                # Generate text data
                text = f"This is sample {i} of the {self.name} dataset."
                label = np.random.randint(0, self.n_classes)
                
                sample = {
                    "id": f"sample-{i}",
                    "text": text,
                    "label": label
                }
                
                if self.embedded:
                    sample["embedding"] = np.random.rand(64).tolist()
                    
            elif self.format_type == "image":
                # Generate image data (paths)
                sample = {
                    "id": f"sample-{i}",
                    "image_path": f"/images/{i:05d}.jpg",
                    "label": np.random.randint(0, self.n_classes)
                }
                
                if self.embedded:
                    sample["embedding"] = np.random.rand(64).tolist()
                    
            else:
                # Generic sample
                sample = {
                    "id": f"sample-{i}",
                    "data": np.random.rand(self.n_features).tolist(),
                    "label": np.random.randint(0, self.n_classes)
                }
                
                if self.embedded:
                    sample["embedding"] = np.random.rand(64).tolist()
            
            samples.append(sample)
            
        return samples
    
    def save(self, path):
        """Save dataset to disk."""
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        
        # Save metadata
        with open(os.path.join(path, "metadata.json"), "w") as f:
            json.dump(self.metadata, f)
            
        # Save samples
        with open(os.path.join(path, "samples.json"), "w") as f:
            json.dump(self.samples, f)
            
        return path
    
    @classmethod
    def load(cls, path):
        """Load dataset from disk."""
        # Load metadata
        with open(os.path.join(path, "metadata.json"), "r") as f:
            metadata = json.load(f)
            
        # Create dataset instance
        dataset = cls(
            name=metadata["name"],
            size=metadata["size"],
            n_features=metadata["n_features"],
            n_classes=metadata["n_classes"],
            format_type=metadata["format_type"],
            embedded=metadata["embedded"]
        )
        
        # Load samples
        with open(os.path.join(path, "samples.json"), "r") as f:
            dataset.samples = json.load(f)
            
        return dataset
    
    def __len__(self):
        """Get number of samples."""
        return len(self.samples)
    
    def __getitem__(self, idx):
        """Get a sample by index."""
        return self.samples[idx]
    
    def get_batch(self, indices):
        """Get a batch of samples by indices."""
        return [self.samples[i] for i in indices]
    
    def to_cid_dataset(self):
        """Convert to a CID-based dataset for IPFS storage."""
        # Create a representation that uses CIDs for sample references
        cid_dataset = {
            "metadata": self.metadata,
            "samples": [f"sample-cid-{uuid.uuid4()}" for _ in range(len(self.samples))]
        }
        
        # Create a mapping from CIDs to samples
        sample_map = {
            cid_dataset["samples"][i]: self.samples[i]
            for i in range(len(self.samples))
        }
        
        return cid_dataset, sample_map


class MockIPFSClient:
    """Mock IPFS client for AI/ML testing."""
    
    def __init__(self):
        """Initialize a mock IPFS client."""
        self.content_store = {}
        self.json_store = {}
        self.dir_store = {}
        self.pin_set = set()
    
    def add(self, content):
        """Add content to IPFS."""
        import hashlib
        
        # Generate a CID based on content
        cid = "Qm" + hashlib.sha256(content if isinstance(content, bytes) else str(content).encode()).hexdigest()[:44]
        
        # Store the content
        self.content_store[cid] = content
        
        return {
            "success": True,
            "Hash": cid,
            "Size": len(content) if isinstance(content, bytes) else len(str(content))
        }
    
    def cat(self, cid):
        """Get content by CID."""
        if cid in self.content_store:
            return {
                "success": True,
                "content": self.content_store[cid]
            }
        else:
            return {
                "success": False,
                "error": f"Content not found: {cid}"
            }
    
    def add_json(self, obj):
        """Add JSON object to IPFS."""
        # Convert to JSON string
        json_str = json.dumps(obj)
        
        # Add to IPFS
        result = self.add(json_str)
        
        # Store in JSON store for easy access
        cid = result["Hash"]
        self.json_store[cid] = obj
        
        return {
            "success": True,
            "Hash": cid,
            "Size": result["Size"]
        }
    
    def get_json(self, cid):
        """Get JSON object by CID."""
        if cid in self.json_store:
            return {
                "success": True,
                "content": self.json_store[cid]
            }
        else:
            # Try to get from content store and parse
            result = self.cat(cid)
            if result["success"]:
                try:
                    obj = json.loads(result["content"])
                    self.json_store[cid] = obj
                    return {
                        "success": True,
                        "content": obj
                    }
                except (json.JSONDecodeError, TypeError):
                    return {
                        "success": False,
                        "error": f"Not a JSON object: {cid}"
                    }
            else:
                return result
    
    def dag_put(self, obj):
        """Add a DAG object to IPFS."""
        # DAG objects are similar to JSON for our mock
        result = self.add_json(obj)
        return result["Hash"]
    
    def dag_get(self, cid):
        """Get a DAG object from IPFS."""
        # For mock purposes, we'll treat it same as get_json
        result = self.get_json(cid)
        if result["success"]:
            return result["content"]
        else:
            raise ValueError(result["error"])
    
    def ipfs_add_path(self, path):
        """Add a directory to IPFS."""
        import hashlib
        
        # Generate a CID for the directory
        dir_cid = "Qm" + hashlib.sha256(path.encode()).hexdigest()[:44]
        
        # Store the directory path
        self.dir_store[dir_cid] = path
        
        return {
            "success": True,
            "Hash": dir_cid,
            "is_directory": True,
            "files": {path: dir_cid}
        }
    
    # For backward compatibility
    add_directory = ipfs_add_path
    add_path = ipfs_add_path
    
    def get(self, cid, dest=None):
        """Get content by CID and save to destination."""
        if dest is None:
            dest = tempfile.mkdtemp()
            
        if cid in self.dir_store:
            # It's a directory
            return {
                "success": True,
                "path": dest,
                "files": [self.dir_store[cid]]
            }
        elif cid in self.content_store:
            # It's a file
            os.makedirs(dest, exist_ok=True)
            with open(os.path.join(dest, cid), "wb") as f:
                content = self.content_store[cid]
                if isinstance(content, str):
                    content = content.encode()
                f.write(content)
            return {
                "success": True,
                "path": os.path.join(dest, cid)
            }
        else:
            return {
                "success": False,
                "error": f"Content not found: {cid}"
            }
    
    def pin_add(self, cid):
        """Pin content by CID."""
        if cid in self.content_store or cid in self.dir_store:
            self.pin_set.add(cid)
            return {
                "success": True,
                "pins": [cid]
            }
        else:
            return {
                "success": False,
                "error": f"Content not found: {cid}"
            }
    
    def pin_rm(self, cid):
        """Unpin content by CID."""
        if cid in self.pin_set:
            self.pin_set.remove(cid)
            return {
                "success": True,
                "pins": [cid]
            }
        else:
            return {
                "success": False,
                "error": f"Content not pinned: {cid}"
            }
    
    def pin_ls(self, cid=None):
        """List pinned content."""
        if cid:
            return {
                "success": True,
                "pins": [cid] if cid in self.pin_set else []
            }
        else:
            return {
                "success": True,
                "pins": list(self.pin_set)
            }


class MockModelRegistry:
    """Mock model registry for AI/ML testing."""
    
    def __init__(self, ipfs_client=None):
        """Initialize a mock model registry."""
        self.ipfs = ipfs_client or MockIPFSClient()
        self.registry = {
            "models": {},
            "version": "1.0.0",
            "updated_at": time.time()
        }
    
    def add_model(self, model, model_name, version="1.0.0", framework=None, metadata=None):
        """Add a model to the registry."""
        if metadata is None:
            metadata = {}
            
        # Determine framework if not specified
        if framework is None:
            framework = model.framework if hasattr(model, "framework") else "unknown"
            
        # Create a temporary directory for model
        temp_dir = tempfile.mkdtemp()
        model_dir = os.path.join(temp_dir, f"{model_name}-{version}")
        os.makedirs(model_dir, exist_ok=True)
        
        # Save model to directory
        if hasattr(model, "save"):
            model_path = model.save(os.path.join(model_dir, "model"))
        else:
            # Generic save for unknown model types
            model_path = os.path.join(model_dir, "model.pkl")
            with open(model_path, "wb") as f:
                pickle.dump(model, f)
                
        # Save metadata
        metadata_path = os.path.join(model_dir, "metadata.json")
        with open(metadata_path, "w") as f:
            full_metadata = {
                "name": model_name,
                "version": version,
                "framework": framework,
                "created_at": time.time()
            }
            full_metadata.update(metadata)
            json.dump(full_metadata, f)
            
        # Add to IPFS
        result = self.ipfs.ipfs_add_path(model_dir)
        model_cid = result["Hash"]
        
        # Add to registry
        if model_name not in self.registry["models"]:
            self.registry["models"][model_name] = {}
        
        self.registry["models"][model_name][version] = {
            "cid": model_cid,
            "framework": framework,
            "added_at": time.time(),
            "metadata": metadata
        }
        
        # Update registry timestamp
        self.registry["updated_at"] = time.time()
        
        # Pin the model
        self.ipfs.pin_add(model_cid)
        
        return {
            "success": True,
            "model_name": model_name,
            "version": version,
            "cid": model_cid,
            "framework": framework
        }
    
    def get_model(self, model_name, version=None):
        """Get a model from the registry."""
        if model_name not in self.registry["models"]:
            return {
                "success": False,
                "error": f"Model not found: {model_name}"
            }
            
        # Get latest version if not specified
        if version is None:
            versions = list(self.registry["models"][model_name].keys())
            if not versions:
                return {
                    "success": False,
                    "error": f"No versions found for model: {model_name}"
                }
            version = max(versions)
            
        if version not in self.registry["models"][model_name]:
            return {
                "success": False,
                "error": f"Version not found: {version} for model: {model_name}"
            }
            
        # Get model CID
        model_cid = self.registry["models"][model_name][version]["cid"]
        
        # Get model from IPFS
        temp_dir = tempfile.mkdtemp()
        result = self.ipfs.get(model_cid, temp_dir)
        
        if not result["success"]:
            return {
                "success": False,
                "error": f"Failed to get model from IPFS: {result['error']}"
            }
            
        # Get model directory
        model_dir = os.path.join(temp_dir, model_cid)
        
        # Load metadata
        metadata_path = os.path.join(model_dir, "metadata.json")
        with open(metadata_path, "r") as f:
            metadata = json.load(f)
            
        # Load model based on framework
        framework = metadata["framework"]
        if framework == "sklearn":
            model_path = os.path.join(model_dir, "model")
            model = MockSklearnModel.load(model_path)
        elif framework == "pytorch":
            model_path = os.path.join(model_dir, "model")
            model = MockPyTorchModel.load(model_path)
        elif framework == "tensorflow":
            model_path = os.path.join(model_dir, "model")
            model = MockTensorflowModel.load_model(model_path)
        else:
            # Generic load for unknown frameworks
            model_path = os.path.join(model_dir, "model.pkl")
            with open(model_path, "rb") as f:
                model = pickle.load(f)
                
        return {
            "success": True,
            "model": model,
            "metadata": metadata
        }
    
    def list_models(self):
        """List all models in the registry."""
        model_list = {}
        
        for model_name, versions in self.registry["models"].items():
            model_list[model_name] = list(versions.keys())
            
        return {
            "success": True,
            "count": len(model_list),
            "models": model_list
        }
    
    def get_model_info(self, model_name, version=None):
        """Get information about a model."""
        if model_name not in self.registry["models"]:
            return {
                "success": False,
                "error": f"Model not found: {model_name}"
            }
            
        # Get latest version if not specified
        if version is None:
            versions = list(self.registry["models"][model_name].keys())
            if not versions:
                return {
                    "success": False,
                    "error": f"No versions found for model: {model_name}"
                }
            version = max(versions)
            
        if version not in self.registry["models"][model_name]:
            return {
                "success": False,
                "error": f"Version not found: {version} for model: {model_name}"
            }
            
        # Get model info
        model_info = self.registry["models"][model_name][version]
        
        return {
            "success": True,
            "model_name": model_name,
            "version": version,
            "info": model_info
        }


class MockDatasetManager:
    """Mock dataset manager for AI/ML testing."""
    
    def __init__(self, ipfs_client=None):
        """Initialize a mock dataset manager."""
        self.ipfs = ipfs_client or MockIPFSClient()
        self.registry = {
            "datasets": {},
            "version": "1.0.0",
            "updated_at": time.time()
        }
    
    def add_dataset(self, dataset, dataset_name=None, version="1.0.0", format=None, metadata=None):
        """Add a dataset to the registry."""
        if isinstance(dataset, str):
            # It's a path to a dataset
            dataset_path = dataset
        elif hasattr(dataset, "save"):
            # It's a MockDataset instance
            dataset_name = dataset_name or dataset.name
            format = format or dataset.format_type
            
            # Save to temporary directory
            temp_dir = tempfile.mkdtemp()
            dataset_path = os.path.join(temp_dir, f"{dataset_name}-{version}")
            dataset.save(dataset_path)
        else:
            # Unknown dataset type
            return {
                "success": False,
                "error": "Unsupported dataset type"
            }
            
        if metadata is None:
            metadata = {}
            
        # Add to IPFS
        result = self.ipfs.ipfs_add_path(dataset_path)
        dataset_cid = result["Hash"]
        
        # Add to registry
        if dataset_name not in self.registry["datasets"]:
            self.registry["datasets"][dataset_name] = {}
        
        self.registry["datasets"][dataset_name][version] = {
            "cid": dataset_cid,
            "format": format,
            "added_at": time.time(),
            "metadata": metadata
        }
        
        # Update registry timestamp
        self.registry["updated_at"] = time.time()
        
        # Pin the dataset
        self.ipfs.pin_add(dataset_cid)
        
        return {
            "success": True,
            "dataset_name": dataset_name,
            "version": version,
            "cid": dataset_cid,
            "format": format
        }
    
    def get_dataset(self, dataset_name, version=None):
        """Get a dataset from the registry."""
        if dataset_name not in self.registry["datasets"]:
            return {
                "success": False,
                "error": f"Dataset not found: {dataset_name}"
            }
            
        # Get latest version if not specified
        if version is None:
            versions = list(self.registry["datasets"][dataset_name].keys())
            if not versions:
                return {
                    "success": False,
                    "error": f"No versions found for dataset: {dataset_name}"
                }
            version = max(versions)
            
        if version not in self.registry["datasets"][dataset_name]:
            return {
                "success": False,
                "error": f"Version not found: {version} for dataset: {dataset_name}"
            }
            
        # Get dataset CID
        dataset_cid = self.registry["datasets"][dataset_name][version]["cid"]
        
        # Get dataset from IPFS
        temp_dir = tempfile.mkdtemp()
        result = self.ipfs.get(dataset_cid, temp_dir)
        
        if not result["success"]:
            return {
                "success": False,
                "error": f"Failed to get dataset from IPFS: {result['error']}"
            }
            
        # Get dataset directory
        dataset_dir = os.path.join(temp_dir, dataset_cid)
        
        # Load dataset
        dataset = MockDataset.load(dataset_dir)
        
        return {
            "success": True,
            "dataset": dataset,
            "dataset_cid": dataset_cid
        }


class ModelScenario:
    """Factory for creating model test scenarios."""
    
    @staticmethod
    def create_classification_model(framework="sklearn"):
        """Create a classification model test fixture."""
        if framework == "sklearn":
            return MockSklearnModel(name="test_classifier", model_type="classification")
        elif framework == "pytorch":
            return MockPyTorchModel(name="test_classifier", model_type="classification")
        elif framework == "tensorflow":
            return MockTensorflowModel(name="test_classifier", model_type="classification")
        else:
            raise ValueError(f"Unsupported framework: {framework}")
    
    @staticmethod
    def create_regression_model(framework="sklearn"):
        """Create a regression model test fixture."""
        if framework == "sklearn":
            return MockSklearnModel(name="test_regressor", model_type="regression")
        elif framework == "pytorch":
            return MockPyTorchModel(name="test_regressor", model_type="regression")
        elif framework == "tensorflow":
            return MockTensorflowModel(name="test_regressor", model_type="regression")
        else:
            raise ValueError(f"Unsupported framework: {framework}")
    
    @staticmethod
    def create_embedding_model(framework="pytorch"):
        """Create an embedding model test fixture."""
        if framework == "sklearn":
            raise ValueError("Sklearn doesn't support embedding models")
        elif framework == "pytorch":
            model = MockPyTorchModel(name="test_embedder", model_type="embedding")
            # Add embedding method
            model.get_embedding = lambda text: np.random.rand(64)
            return model
        elif framework == "tensorflow":
            model = MockTensorflowModel(name="test_embedder", model_type="embedding")
            # Add embedding method
            model.get_embedding = lambda text: np.random.rand(64)
            return model
        else:
            raise ValueError(f"Unsupported framework: {framework}")
    
    @staticmethod
    def create_trained_model(framework="sklearn", epochs=10):
        """Create a pre-trained model test fixture."""
        model = ModelScenario.create_classification_model(framework)
        model.train(epochs=epochs)
        return model


class DatasetScenario:
    """Factory for creating dataset test scenarios."""
    
    @staticmethod
    def create_tabular_dataset(size=1000, n_features=10, n_classes=2):
        """Create a tabular dataset test fixture."""
        return MockDataset(
            name="test_tabular",
            size=size,
            n_features=n_features,
            n_classes=n_classes,
            format_type="tabular"
        )
    
    @staticmethod
    def create_text_dataset(size=100):
        """Create a text dataset test fixture."""
        return MockDataset(
            name="test_text",
            size=size,
            format_type="text"
        )
    
    @staticmethod
    def create_image_dataset(size=50, embedded=True):
        """Create an image dataset test fixture."""
        return MockDataset(
            name="test_images",
            size=size,
            format_type="image",
            embedded=embedded
        )
    
    @staticmethod
    def create_embedded_dataset(size=500, embedding_dim=64):
        """Create a dataset with pre-computed embeddings."""
        dataset = MockDataset(
            name="test_embedded",
            size=size,
            n_features=10,
            format_type="tabular",
            embedded=True
        )
        
        # Set embedding size manually
        for sample in dataset.samples:
            sample["embedding"] = np.random.rand(embedding_dim).tolist()
            
        return dataset


# Example usage:
if __name__ == "__main__":
    # Create a mock IPFS client
    ipfs = MockIPFSClient()
    
    # Create a model registry
    registry = MockModelRegistry(ipfs)
    
    # Create a test model
    model = ModelScenario.create_trained_model(framework="sklearn", epochs=10)
    
    # Add model to registry
    result = registry.add_model(
        model=model,
        model_name="test_model",
        version="1.0.0",
        metadata={"description": "Test model for unit tests"}
    )
    
    print(f"Model added to registry: {result['model_name']} v{result['version']} with CID {result['cid']}")
    
    # List models in registry
    models = registry.list_models()
    print(f"Models in registry: {models['count']}")
    
    # Get model from registry
    result = registry.get_model("test_model")
    retrieved_model = result["model"]
    
    print(f"Retrieved model accuracy: {retrieved_model.state['accuracy']:.4f}")
    
    # Test prediction
    x = np.random.rand(5, 10)
    predictions = retrieved_model.predict(x)
    print(f"Predictions: {predictions}")