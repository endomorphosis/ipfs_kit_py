#!/usr/bin/env python3
"""
IPFS Kit CLI - LLM Router Commands

CLI for interacting with the LLM router for text generation across multiple providers.
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
        from ipfs_kit_py.llm_router import (
            generate_text,
            get_llm_provider,
            clear_llm_router_caches,
        )
        from ipfs_kit_py.router_deps import get_default_router_deps
    except ImportError:
        # Fall back to direct import
        import llm_router
        import router_deps
        generate_text = llm_router.generate_text
        get_llm_provider = llm_router.get_llm_provider
        clear_llm_router_caches = llm_router.clear_llm_router_caches
        get_default_router_deps = router_deps.get_default_router_deps
    
    LLM_ROUTER_AVAILABLE = True
except ImportError as e:
    LLM_ROUTER_AVAILABLE = False
    print(f"Warning: LLM router not available - {e}")


def handle_generate(args):
    """Handle text generation command."""
    if not LLM_ROUTER_AVAILABLE:
        print("❌ LLM router not available")
        return 1
    
    try:
        # Read prompt from file if specified
        if args.prompt_file:
            with open(args.prompt_file, 'r') as f:
                prompt = f.read()
        else:
            prompt = args.prompt
        
        if not prompt:
            print("❌ No prompt provided. Use --prompt or --prompt-file")
            return 1
        
        print(f"🤖 Generating text with {args.provider or 'auto'} provider...")
        if args.model:
            print(f"   Model: {args.model}")
        
        # Generate text
        result = generate_text(
            prompt=prompt,
            model_name=args.model,
            provider=args.provider,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
            timeout=args.timeout,
        )
        
        print(f"\n{'=' * 60}")
        print("Generated Text:")
        print(f"{'=' * 60}")
        print(result)
        print(f"{'=' * 60}\n")
        
        # Save to file if specified
        if args.output:
            with open(args.output, 'w') as f:
                f.write(result)
            print(f"✅ Output saved to {args.output}")
        
        return 0
    
    except Exception as e:
        print(f"❌ Text generation failed: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1


def handle_list_providers(args):
    """Handle list providers command."""
    if not LLM_ROUTER_AVAILABLE:
        print("❌ LLM router not available")
        return 1
    
    try:
        print("🔍 Checking available LLM providers...\n")
        
        deps = get_default_router_deps()
        
        provider_checks = [
            ("openrouter", "OpenRouter API", "OPENROUTER_API_KEY or IPFS_KIT_OPENROUTER_API_KEY"),
            ("codex_cli", "OpenAI Codex CLI", "codex command in PATH"),
            ("copilot_cli", "GitHub Copilot CLI", "npx @github/copilot or IPFS_KIT_COPILOT_CLI_CMD"),
            ("copilot_sdk", "GitHub Copilot SDK", "copilot Python package"),
            ("gemini_cli", "Google Gemini CLI", "npx @google/gemini-cli or IPFS_KIT_GEMINI_CLI_CMD"),
            ("gemini_py", "Gemini Python Wrapper", "ipfs_kit_py.utils.gemini_cli"),
            ("claude_code", "Claude Code CLI", "claude command or IPFS_KIT_CLAUDE_CODE_CLI_CMD"),
            ("claude_py", "Claude Python Wrapper", "ipfs_kit_py.utils.claude_cli"),
            ("local_hf", "HuggingFace Transformers", "transformers package"),
            ("ipfs_peer", "IPFS Peer Endpoints", "IPFS backend with peer manager"),
        ]
        
        available = []
        unavailable = []
        
        for provider_name, description, requirement in provider_checks:
            try:
                provider = get_llm_provider(provider_name, deps=deps, use_cache=False)
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
        default_provider = os.getenv("IPFS_KIT_LLM_PROVIDER") or os.getenv("IPFS_DATASETS_PY_LLM_PROVIDER")
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
    if not LLM_ROUTER_AVAILABLE:
        print("❌ LLM router not available")
        return 1
    
    try:
        print("🗑️  Clearing LLM router caches...")
        clear_llm_router_caches()
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
    if not LLM_ROUTER_AVAILABLE:
        print("❌ LLM router not available")
        return 1
    
    try:
        test_prompt = "What is the capital of France?"
        print(f"🧪 Testing LLM router with prompt: '{test_prompt}'")
        
        result = generate_text(
            prompt=test_prompt,
            provider=args.provider,
            max_tokens=50,
            temperature=0.7,
        )
        
        print(f"\n✅ Test successful!")
        print(f"Response: {result}\n")
        
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
        description="IPFS Kit LLM Router CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate text with auto provider selection
  %(prog)s generate --prompt "Write a haiku about IPFS"
  
  # Use a specific provider
  %(prog)s generate --prompt "Explain distributed systems" --provider openrouter
  
  # Generate from file and save output
  %(prog)s generate --prompt-file input.txt --output result.txt
  
  # List available providers
  %(prog)s providers --verbose
  
  # Test the LLM router
  %(prog)s test
  
  # Clear caches
  %(prog)s clear-cache

Environment Variables:
  IPFS_KIT_LLM_PROVIDER        - Force a specific provider
  IPFS_KIT_LLM_MODEL            - Default model name
  IPFS_KIT_OPENROUTER_API_KEY   - OpenRouter API key
  IPFS_KIT_COPILOT_CLI_CMD      - GitHub Copilot CLI command
  IPFS_KIT_GEMINI_CLI_CMD       - Gemini CLI command
  IPFS_KIT_CLAUDE_CODE_CLI_CMD  - Claude CLI command
        """
    )
    
    parser.add_argument('--debug', action='store_true', help='Enable debug output')
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Generate command
    gen_parser = subparsers.add_parser('generate', aliases=['gen', 'g'], help='Generate text')
    gen_parser.add_argument('--prompt', '-p', help='Input prompt')
    gen_parser.add_argument('--prompt-file', '-f', help='Read prompt from file')
    gen_parser.add_argument('--output', '-o', help='Save output to file')
    gen_parser.add_argument('--provider', help='LLM provider to use')
    gen_parser.add_argument('--model', '-m', help='Model name')
    gen_parser.add_argument('--max-tokens', type=int, default=256, help='Max tokens (default: 256)')
    gen_parser.add_argument('--temperature', '-t', type=float, default=0.7, help='Temperature (default: 0.7)')
    gen_parser.add_argument('--timeout', type=float, default=120.0, help='Timeout in seconds (default: 120)')
    
    # Providers command
    prov_parser = subparsers.add_parser('providers', aliases=['prov', 'list'], help='List available providers')
    prov_parser.add_argument('--verbose', '-v', action='store_true', help='Show detailed information')
    
    # Clear cache command
    cache_parser = subparsers.add_parser('clear-cache', aliases=['clear'], help='Clear LLM router caches')
    
    # Test command
    test_parser = subparsers.add_parser('test', help='Test LLM router')
    test_parser.add_argument('--provider', help='Provider to test')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 0
    
    # Route to appropriate handler
    if args.command in ['generate', 'gen', 'g']:
        return handle_generate(args)
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
