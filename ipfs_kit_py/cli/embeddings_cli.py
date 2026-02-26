#!/usr/bin/env python3
"""
IPFS Kit CLI - Embeddings Router Commands

CLI for generating embeddings across multiple providers.
"""

import sys
import os
import argparse
import json

# Add the ipfs_kit_py directory to the Python path
ipfs_kit_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ipfs_kit_dir not in sys.path:
    sys.path.insert(0, ipfs_kit_dir)

# Also add the root directory
root_dir = os.path.dirname(ipfs_kit_dir)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

try:
    # Try importing as a package first
    try:
        from ipfs_kit_py.embeddings_router import (
            embed_texts,
            embed_text,
            get_embeddings_provider,
            clear_embeddings_router_caches,
        )
        from ipfs_kit_py.router_deps import get_default_router_deps
    except ImportError:
        # Fall back to direct import
        import embeddings_router
        import router_deps
        embed_texts = embeddings_router.embed_texts
        embed_text = embeddings_router.embed_text
        get_embeddings_provider = embeddings_router.get_embeddings_provider
        clear_embeddings_router_caches = embeddings_router.clear_embeddings_router_caches
        get_default_router_deps = router_deps.get_default_router_deps
    
    EMBEDDINGS_ROUTER_AVAILABLE = True
except ImportError as e:
    EMBEDDINGS_ROUTER_AVAILABLE = False
    print(f"Warning: Embeddings router not available - {e}")


def handle_embed(args):
    """Handle embedding generation command."""
    if not EMBEDDINGS_ROUTER_AVAILABLE:
        print("❌ Embeddings router not available")
        return 1
    
    try:
        # Read texts from file or arguments
        if args.input_file:
            with open(args.input_file, 'r') as f:
                texts = [line.strip() for line in f if line.strip()]
        elif args.texts:
            texts = args.texts
        else:
            print("❌ No texts provided. Use --texts or --input-file")
            return 1
        
        print(f"🔢 Generating embeddings for {len(texts)} text(s)...")
        if args.provider:
            print(f"   Provider: {args.provider}")
        if args.model:
            print(f"   Model: {args.model}")
        if args.device:
            print(f"   Device: {args.device}")
        
        # Generate embeddings
        result = embed_texts(
            texts=texts,
            model_name=args.model,
            device=args.device,
            provider=args.provider,
            timeout=args.timeout,
        )
        
        print(f"\n{'=' * 60}")
        print(f"Generated {len(result)} embedding(s)")
        print(f"{'=' * 60}")
        
        if args.verbose:
            for i, (text, embedding) in enumerate(zip(texts, result)):
                print(f"\nText {i+1}: {text[:50]}...")
                print(f"Embedding dimension: {len(embedding)}")
                print(f"First 5 values: {embedding[:5]}")
        else:
            print(f"Embedding dimensions: {len(result[0])} (use --verbose to see details)")
        
        # Save to file if specified
        if args.output:
            output_data = {
                "texts": texts,
                "embeddings": result,
                "provider": args.provider or "auto",
                "model": args.model,
                "device": args.device
            }
            with open(args.output, 'w') as f:
                json.dump(output_data, f, indent=2)
            print(f"\n✅ Embeddings saved to {args.output}")
        
        return 0
    
    except Exception as e:
        print(f"❌ Embedding generation failed: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1


def handle_embed_single(args):
    """Handle single text embedding."""
    if not EMBEDDINGS_ROUTER_AVAILABLE:
        print("❌ Embeddings router not available")
        return 1
    
    try:
        # Read text from file or argument
        if args.input_file:
            with open(args.input_file, 'r') as f:
                text = f.read().strip()
        else:
            text = args.text
        
        if not text:
            print("❌ No text provided. Use --text or --input-file")
            return 1
        
        print(f"🔢 Generating embedding for text: {text[:50]}...")
        
        # Generate embedding
        result = embed_text(
            text=text,
            model_name=args.model,
            device=args.device,
            provider=args.provider,
            timeout=args.timeout,
        )
        
        print(f"\n✅ Embedding generated!")
        print(f"Dimension: {len(result)}")
        
        if args.verbose:
            print(f"\nFirst 10 values: {result[:10]}")
        
        # Save to file if specified
        if args.output:
            output_data = {
                "text": text,
                "embedding": result,
                "provider": args.provider or "auto",
                "model": args.model,
                "device": args.device
            }
            with open(args.output, 'w') as f:
                json.dump(output_data, f, indent=2)
            print(f"✅ Embedding saved to {args.output}")
        
        return 0
    
    except Exception as e:
        print(f"❌ Embedding generation failed: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1


def handle_list_providers(args):
    """Handle list providers command."""
    if not EMBEDDINGS_ROUTER_AVAILABLE:
        print("❌ Embeddings router not available")
        return 1
    
    try:
        print("🔍 Checking available embeddings providers...\n")
        
        deps = get_default_router_deps()
        
        provider_checks = [
            ("openrouter", "OpenRouter API", "OPENROUTER_API_KEY"),
            ("gemini_cli", "Gemini CLI", "gemini command in PATH"),
            ("local_adapter", "HuggingFace Local Adapter", "transformers package"),
            ("ipfs_peer", "IPFS Peer Endpoints", "IPFS backend with peer manager"),
        ]
        
        available = []
        unavailable = []
        
        for provider_name, description, requirement in provider_checks:
            try:
                provider = get_embeddings_provider(provider_name, deps=deps, use_cache=False)
                if provider is not None:
                    available.append((provider_name, description, requirement))
                else:
                    unavailable.append((provider_name, description, requirement))
            except Exception:
                unavailable.append((provider_name, description, requirement))
        
        # Display available providers
        if available:
            print("✅ Available Providers:")
            for name, desc, req in available:
                print(f"   • {name:15} - {desc}")
                if args.verbose:
                    print(f"     Requirement: {req}")
            print()
        else:
            print("⚠️  No providers currently available\n")
        
        # Display unavailable providers
        if unavailable and args.verbose:
            print("❌ Unavailable Providers:")
            for name, desc, req in unavailable:
                print(f"   • {name:15} - {desc}")
                print(f"     Requirement: {req}")
            print()
        
        # Show default provider
        default_provider = os.getenv("IPFS_KIT_EMBEDDINGS_PROVIDER") or os.getenv("IPFS_DATASETS_PY_EMBEDDINGS_PROVIDER")
        if default_provider:
            print(f"🎯 Default Provider: {default_provider}")
        else:
            print("🎯 Default Provider: Auto-select first available")
        
        return 0
    
    except Exception as e:
        print(f"❌ Failed to list providers: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1


def handle_clear_cache(args):
    """Handle clear cache command."""
    if not EMBEDDINGS_ROUTER_AVAILABLE:
        print("❌ Embeddings router not available")
        return 1
    
    try:
        print("🗑️  Clearing embeddings router caches...")
        clear_embeddings_router_caches()
        print("✅ Caches cleared successfully")
        return 0
    
    except Exception as e:
        print(f"❌ Failed to clear caches: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1


def handle_test(args):
    """Handle test command."""
    if not EMBEDDINGS_ROUTER_AVAILABLE:
        print("❌ Embeddings router not available")
        return 1
    
    try:
        test_texts = ["Hello world", "IPFS is a distributed file system"]
        print(f"🧪 Testing embeddings router with {len(test_texts)} sample texts")
        
        result = embed_texts(
            texts=test_texts,
            provider=args.provider,
        )
        
        print(f"\n✅ Test successful!")
        print(f"Generated {len(result)} embeddings")
        print(f"Embedding dimension: {len(result[0])}")
        print(f"First embedding preview: {result[0][:5]}...\n")
        
        return 0
    
    except Exception as e:
        print(f"❌ Test failed: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="IPFS Kit Embeddings Router CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate embeddings for multiple texts
  %(prog)s embed --texts "Hello world" "Another text"
  
  # Generate from file
  %(prog)s embed --input-file texts.txt --output embeddings.json
  
  # Use specific provider
  %(prog)s embed --texts "Sample text" --provider openrouter
  
  # Single text embedding
  %(prog)s embed-single --text "Sample text" --output embedding.json
  
  # List available providers
  %(prog)s providers --verbose
  
  # Test the router
  %(prog)s test
  
  # Clear caches
  %(prog)s clear-cache

Environment Variables:
  IPFS_KIT_EMBEDDINGS_PROVIDER    - Force a specific provider
  IPFS_KIT_EMBEDDINGS_MODEL        - Model name
  IPFS_KIT_EMBEDDINGS_DEVICE       - Device (cpu/cuda)
  IPFS_KIT_OPENROUTER_API_KEY      - OpenRouter API key
  IPFS_KIT_GEMINI_EMBEDDINGS_CMD   - Gemini CLI command
        """
    )
    
    parser.add_argument('--debug', action='store_true', help='Enable debug output')
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Embed command
    embed_parser = subparsers.add_parser('embed', aliases=['emb'], help='Generate embeddings for texts')
    embed_parser.add_argument('--texts', '-t', nargs='+', help='Texts to embed')
    embed_parser.add_argument('--input-file', '-f', help='Read texts from file (one per line)')
    embed_parser.add_argument('--output', '-o', help='Save embeddings to JSON file')
    embed_parser.add_argument('--provider', '-p', help='Embeddings provider to use')
    embed_parser.add_argument('--model', '-m', help='Model name')
    embed_parser.add_argument('--device', '-d', help='Device (cpu/cuda)')
    embed_parser.add_argument('--timeout', type=float, default=120.0, help='Timeout in seconds')
    embed_parser.add_argument('--verbose', '-v', action='store_true', help='Show detailed output')
    
    # Embed single command
    single_parser = subparsers.add_parser('embed-single', aliases=['emb1'], help='Generate embedding for single text')
    single_parser.add_argument('--text', '-t', help='Text to embed')
    single_parser.add_argument('--input-file', '-f', help='Read text from file')
    single_parser.add_argument('--output', '-o', help='Save embedding to JSON file')
    single_parser.add_argument('--provider', '-p', help='Embeddings provider to use')
    single_parser.add_argument('--model', '-m', help='Model name')
    single_parser.add_argument('--device', '-d', help='Device (cpu/cuda)')
    single_parser.add_argument('--timeout', type=float, default=120.0, help='Timeout in seconds')
    single_parser.add_argument('--verbose', '-v', action='store_true', help='Show detailed output')
    
    # Providers command
    prov_parser = subparsers.add_parser('providers', aliases=['prov', 'list'], help='List available providers')
    prov_parser.add_argument('--verbose', '-v', action='store_true', help='Show detailed information')
    
    # Clear cache command
    cache_parser = subparsers.add_parser('clear-cache', aliases=['clear'], help='Clear embeddings router caches')
    
    # Test command
    test_parser = subparsers.add_parser('test', help='Test embeddings router')
    test_parser.add_argument('--provider', '-p', help='Provider to test')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 0
    
    # Route to appropriate handler
    if args.command in ['embed', 'emb']:
        return handle_embed(args)
    elif args.command in ['embed-single', 'emb1']:
        return handle_embed_single(args)
    elif args.command in ['providers', 'prov', 'list']:
        return handle_list_providers(args)
    elif args.command in ['clear-cache', 'clear']:
        return handle_clear_cache(args)
    elif args.command == 'test':
        return handle_test(args)
    else:
        parser.print_help()
        return 0


if __name__ == '__main__':
    sys.exit(main())
