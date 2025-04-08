from setuptools import setup

# This file is maintained for backwards compatibility
# Most configuration is now in pyproject.toml

setup(
    name='ipfs_kit_py',
    version='0.2.0',
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
    ],
    # All other configurations come from pyproject.toml
)