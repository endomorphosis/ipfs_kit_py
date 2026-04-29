#!/usr/bin/env python3
"""
Example: LLM Router with IPFS Endpoint Multiplexing

This example demonstrates how to use the LLM router with IPFS Kit's
endpoint multiplexing to route LLM requests across peer endpoints.
"""

import sys
import os

# Add ipfs_kit_py to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ipfs_kit_py.llm_router import generate_text, get_llm_provider, register_llm_provider
from ipfs_kit_py.router_deps import RouterDeps


def example_basic_usage():
    """Basic text generation with auto provider selection."""
    print("=" * 60)
    print("Example 1: Basic Text Generation")
    print("=" * 60)
    
    prompt = "Write a one-sentence description of IPFS"
    
    print(f"Prompt: {prompt}\n")
    
    try:
        # Simple generation with auto provider selection
        text = generate_text(prompt, max_tokens=100)
        print(f"Generated: {text}\n")
    except Exception as e:
        print(f"Error: {e}\n")


def example_custom_provider():
    """Example with a custom provider."""
    print("=" * 60)
    print("Example 2: Custom Provider")
    print("=" * 60)
    
    class SimpleProvider:
        """A simple mock provider for demonstration."""
        
        def generate(self, prompt: str, **kwargs):
            return f"[Mock] Response to: {prompt[:50]}..."
    
    # Register the custom provider
    register_llm_provider("simple", lambda: SimpleProvider())
    
    prompt = "What is distributed computing?"
    
    print(f"Prompt: {prompt}\n")
    
    try:
        text = generate_text(prompt, provider="simple")
        print(f"Generated: {text}\n")
    except Exception as e:
        print(f"Error: {e}\n")


def example_with_deps():
    """Example with shared dependencies."""
    print("=" * 60)
    print("Example 3: Using Router Dependencies")
    print("=" * 60)
    
    # Create shared dependencies
    deps = RouterDeps()
    
    prompts = [
        "List three benefits of decentralization",
        "What is content addressing?",
        "Explain peer-to-peer networks"
    ]
    
    print("Generating responses with shared dependencies...\n")
    
    for i, prompt in enumerate(prompts, 1):
        try:
            print(f"{i}. Prompt: {prompt}")
            text = generate_text(
                prompt,
                deps=deps,
                max_tokens=50
            )
            print(f"   Response: {text[:100]}...\n")
        except Exception as e:
            print(f"   Error: {e}\n")


def example_ipfs_peer_multiplexing():
    """Example with IPFS peer endpoint multiplexing."""
    print("=" * 60)
    print("Example 4: IPFS Peer Endpoint Multiplexing")
    print("=" * 60)
    
    # Create deps with mock IPFS backend
    class MockIPFSBackend:
        """Mock IPFS backend for demonstration."""
        
        class MockPeerManager:
            def route_llm_request(self, prompt, model=None, **kwargs):
                return {
                    "text": f"[Peer Response] {prompt[:50]}...",
                    "peer_id": "QmExamplePeerID",
                    "model": model or "default"
                }
        
        def __init__(self):
            self.peer_manager = self.MockPeerManager()
    
    deps = RouterDeps()
    deps.ipfs_backend = MockIPFSBackend()
    
    prompt = "Generate a summary of distributed systems"
    
    print(f"Prompt: {prompt}\n")
    print("Routing through IPFS peer endpoints...\n")
    
    try:
        text = generate_text(
            prompt,
            provider="ipfs_peer",  # Use peer routing
            deps=deps
        )
        print(f"Generated: {text}\n")
    except Exception as e:
        print(f"Error: {e}\n")


def example_provider_fallback():
    """Example showing provider fallback behavior."""
    print("=" * 60)
    print("Example 5: Provider Fallback")
    print("=" * 60)
    
    # Register a failing provider
    class FailingProvider:
        def generate(self, prompt: str, **kwargs):
            raise RuntimeError("Provider unavailable")
    
    register_llm_provider("failing", lambda: FailingProvider())
    
    # Also register a working fallback
    class WorkingProvider:
        def generate(self, prompt: str, **kwargs):
            return f"[Fallback] {prompt[:50]}..."
    
    register_llm_provider("working", lambda: WorkingProvider())
    
    prompt = "Test fallback behavior"
    
    print(f"Prompt: {prompt}\n")
    print("Trying failing provider, will fall back...\n")
    
    try:
        # Try with auto provider (will use fallback)
        text = generate_text(prompt)
        print(f"Generated: {text}\n")
    except Exception as e:
        print(f"Error: {e}\n")


def main():
    """Run all examples."""
    print("\n")
    print("=" * 60)
    print("LLM Router Examples")
    print("=" * 60)
    print()
    
    examples = [
        example_basic_usage,
        example_custom_provider,
        example_with_deps,
        example_ipfs_peer_multiplexing,
        example_provider_fallback,
    ]
    
    for example in examples:
        try:
            example()
        except Exception as e:
            print(f"Example failed: {e}")
            import traceback
            traceback.print_exc()
        
        print()
    
    print("=" * 60)
    print("Examples Complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
