from setuptools import setup

# This file is maintained for backwards compatibility
# Most configuration is now in pyproject.toml

setup(
    name='ipfs_kit_py',
    version='0.3.0',
    description='Python toolkit for IPFS with high-level API, cluster management, tiered storage, and AI/ML integration',
    author='Benjamin Barber',
    author_email='starworks5@gmail.com',
    url='https://github.com/endomorphosis/ipfs_kit_py/',
    python_requires='>=3.8',
    install_requires=[
        'requests>=2.28.0',
        'psutil>=5.9.0',
        'pyyaml>=6.0',
        'base58>=2.1.1',
        'multiaddr>=0.0.9',  # For libp2p multiaddress support
        'python-magic>=0.4.27',  # For file type detection
        'anyio>=3.7.0',  # For async operations with backend flexibility
        'trio>=0.22.0',  # Optional backend for anyio
        'cryptography>=38.0.0',  # Required for libp2p
    ],
    extras_require={
        'libp2p': [
            'libp2p>=0.1.5',  # Core libp2p functionality
            'multiaddr>=0.0.9',  # For peer addressing
            'multiformats>=0.2.0',  # For content addressing
            'base58>=2.1.1',  # Used by CIDs and peer IDs
            'cryptography>=38.0.0',  # For key generation and encryption
            'google-protobuf>=4.21.0',  # For protocol buffer support
            'eth-hash>=0.3.3',  # Optional for ETH integration
            'eth-keys>=0.4.0',  # Optional for ETH integration
        ],
    },
    # All other configurations come from pyproject.toml
)