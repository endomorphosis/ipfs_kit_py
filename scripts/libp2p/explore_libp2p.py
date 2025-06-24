#!/usr/bin/env python3
"""
Explore the libp2p module to understand its API.
"""
import sys
import inspect
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s"
)
logger = logging.getLogger()

def explore_module(module_name):
    """Explore a module's structure and API."""
    try:
        # Import the module
        module = __import__(module_name)

        logger.info(f"Successfully imported {module_name}")
        logger.info(f"Module path: {module.__file__}")

        if hasattr(module, "__version__"):
            logger.info(f"Version: {module.__version__}")
        else:
            logger.info("No version information available")

        # Get all attributes
        logger.info(f"\nAttributes of {module_name}:")
        for name in dir(module):
            if not name.startswith("_"):  # Skip private attrs
                try:
                    attr = getattr(module, name)
                    attr_type = type(attr).__name__
                    logger.info(f"  {name}: {attr_type}")
                except Exception as e:
                    logger.info(f"  {name}: Error accessing - {e}")

        return module
    except ImportError:
        logger.error(f"Could not import {module_name}")
        return None

def explore_class(module, class_name):
    """Explore a specific class in the module."""
    try:
        # Get the class
        cls = getattr(module, class_name)

        logger.info(f"\nExploring class: {cls.__name__}")
        logger.info(f"Module: {cls.__module__}")

        # Get methods
        logger.info("\nMethods:")
        for name, method in inspect.getmembers(cls, inspect.isfunction):
            if not name.startswith("_"):  # Skip private methods
                try:
                    signature = inspect.signature(method)
                    logger.info(f"  {name}{signature}")
                except Exception as e:
                    logger.info(f"  {name}: Error getting signature - {e}")

        # Get class methods and static methods
        logger.info("\nClass/Static Methods:")
        for name, method in inspect.getmembers(cls, lambda x: inspect.ismethod(x) or inspect.ismethoddescriptor(x)):
            if not name.startswith("_"):  # Skip private methods
                try:
                    signature = inspect.signature(method)
                    logger.info(f"  {name}{signature}")
                except Exception as e:
                    logger.info(f"  {name}: Error getting signature - {e}")

        # Get attributes
        logger.info("\nAttributes:")
        for name in dir(cls):
            if not name.startswith("_") and not inspect.ismethod(getattr(cls, name)) and not inspect.isfunction(getattr(cls, name)):
                try:
                    attr = getattr(cls, name)
                    attr_type = type(attr).__name__
                    logger.info(f"  {name}: {attr_type}")
                except Exception as e:
                    logger.info(f"  {name}: Error accessing - {e}")

        return cls
    except AttributeError:
        logger.error(f"Class {class_name} not found in module")
        return None

def main():
    """Main function."""
    # First explore libp2p module
    libp2p = explore_module("libp2p")
    if not libp2p:
        return 1

    # Explore crypto submodule
    crypto = explore_module("libp2p.crypto")
    if not crypto:
        return 1

    # Explore keys submodule
    keys = explore_module("libp2p.crypto.keys")
    if not keys:
        return 1

    # Explore KeyPair class
    if hasattr(keys, "KeyPair"):
        explore_class(keys, "KeyPair")
    else:
        logger.error("KeyPair class not found in libp2p.crypto.keys")
        # List all classes in the module
        logger.info("Available classes in libp2p.crypto.keys:")
        for name, obj in inspect.getmembers(keys, inspect.isclass):
            logger.info(f"  {name}")

    return 0

if __name__ == "__main__":
    sys.exit(main())
