#!/usr/bin/env python3
"""
AnyIO Event Loop Issue Demo and Fix Demonstration.

This script demonstrates the event loop issue in async functions
and how our AnyIOEventLoopHandler fix resolves it, working with
multiple async backends.
"""

import anyio
import time
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Check for AnyIO dependency
try:
    import anyio
    import sniffio
    HAS_ANYIO = True
except ImportError:
    logger.error("AnyIO and sniffio packages are required. Install with: pip install anyio sniffio")
    HAS_ANYIO = False

# Import our AnyIOEventLoopHandler if AnyIO is available
if HAS_ANYIO:
    from fixes.webrtc_anyio_fix import AnyIOEventLoopHandler

# Sample coroutine that might be called by WebRTC methods
async def sample_coroutine(seconds=1):
    """A sample coroutine that sleeps for a given time."""
    logger.info(f"Starting coroutine, will sleep for {seconds} second(s)")
    await anyio.sleep(seconds)
    logger.info("Coroutine completed!")
    return {"success": True, "slept_for": seconds}

# === PROBLEMATIC IMPLEMENTATION ===

def problematic_method():
    """
    This method demonstrates the problematic approach.

    It attempts to handle a running event loop by creating a new one,
    which doesn't work in FastAPI context.
    """
    logger.info("Running problematic method...")
    start_time = time.time()

    try:
        # Get or create event loop (problematic pattern)
        try:
            loop = anyio.get_event_loop()
            if loop.is_running():
                # Create a new event loop for this operation
                logger.info("Loop is running, creating a new one (THIS WILL FAIL IN FASTAPI)")
                new_loop = anyio.new_event_loop()
                anyio.set_event_loop(new_loop)
                loop = new_loop
        except RuntimeError:
            # No event loop in this thread
            logger.info("No event loop in this thread, creating one")
            loop = anyio.new_event_loop()
            anyio.set_event_loop(loop)

        # Run the coroutine using run_until_complete
        logger.info("Running coroutine with run_until_complete")
        result = loop.run_until_complete(sample_coroutine())

        logger.info(f"Method completed successfully: {result}")
        return result

    except Exception as e:
        logger.error(f"Error in problematic method: {e}")
        return {"success": False, "error": str(e)}
    finally:
        logger.info(f"Method took {time.time() - start_time:.2f} seconds")

# === FIXED IMPLEMENTATION WITH ANYIO ===

def anyio_fixed_method():
    """
    This method demonstrates the fixed approach using AnyIOEventLoopHandler.

    It safely handles running event loops by using AnyIO, which works across
    different async backends (asyncio, trio, etc.) and detects if we're
    already in an async context.
    """
    if not HAS_ANYIO:
        return {"success": False, "error": "AnyIO not installed"}

    logger.info("Running AnyIO fixed method...")
    start_time = time.time()

    try:
        # Create a fallback result for when we can't wait for the coroutine
        fallback_result = {
            "success": True,
            "simulated": True,
            "note": "Operation scheduled in background due to running in async context"
        }

        # Use our utility method to run the coroutine safely with AnyIO
        logger.info("Using AnyIOEventLoopHandler to run coroutine safely")
        result = AnyIOEventLoopHandler.run_coroutine(
            sample_coroutine(),
            fallback_result=fallback_result
        )

        logger.info(f"Method completed successfully: {result}")
        return result

    except Exception as e:
        logger.error(f"Error in AnyIO fixed method: {e}")
        return {"success": False, "error": str(e)}
    finally:
        logger.info(f"Method took {time.time() - start_time:.2f} seconds")

# === FASTAPI SIMULATION ===

async def simulate_fastapi_endpoint_calls():
    """Simulate FastAPI endpoint calls in an already running event loop."""
    logger.info("\n=== SIMULATING FASTAPI ENVIRONMENT ===")
    logger.info(f"Current async library: {sniffio.current_async_library() if HAS_ANYIO else 'unknown'}")

    # First, try the problematic method
    logger.info("\n--- Testing problematic method in FastAPI context ---")
    try:
        problematic_method()
        logger.info("Problematic method did not raise an exception (unexpected)")
    except Exception as e:
        logger.error(f"Problematic method raised an exception (expected): {e}")

    # Now, try the AnyIO fixed method
    if HAS_ANYIO:
        logger.info("\n--- Testing AnyIO fixed method in FastAPI context ---")
        try:
            result = anyio_fixed_method()
            logger.info(f"AnyIO fixed method returned: {result}")
            # If we got a simulated result, the coroutine was scheduled in the background
            if result.get("simulated", False):
                logger.info("The coroutine was scheduled in the background, still running...")
        except Exception as e:
            logger.error(f"AnyIO fixed method raised an exception (unexpected): {e}")

    return

# === TRIO BACKEND DEMONSTRATION ===

async def simulate_trio_backend():
    """Demonstrate operation with the Trio backend."""
    if not HAS_ANYIO:
        return

    logger.info("\n=== SIMULATING TRIO BACKEND ===")
    logger.info(f"Current async library: {sniffio.current_async_library()}")

    # Try the AnyIO fixed method with Trio backend
    logger.info("\n--- Testing AnyIO fixed method with Trio backend ---")
    try:
        result = anyio_fixed_method()
        logger.info(f"AnyIO fixed method returned: {result}")
        # If we got a simulated result, the coroutine was scheduled in the background
        if result.get("simulated", False):
            logger.info("The coroutine was scheduled in the background, still running...")
    except Exception as e:
        logger.error(f"AnyIO fixed method raised an exception (unexpected): {e}")

    return

async def run_demo_anyio():
    """Run the complete demonstration with AnyIO."""
    logger.info("=== ANYIO EVENT LOOP ISSUE DEMO ===\n")

    # First, test without a running event loop
    logger.info("Testing in a context WITHOUT a running event loop:")

    logger.info("\n--- Running problematic method ---")
    problematic_method()

    if HAS_ANYIO:
        logger.info("\n--- Running AnyIO fixed method ---")
        anyio_fixed_method()

        # Now, simulate FastAPI where the event loop is running
        await simulate_fastapi_endpoint_calls()

        # Wait to ensure any background tasks complete
        logger.info("\nWaiting for background tasks to complete...")
        await anyio.sleep(2)

    logger.info("\n=== DEMO COMPLETE ===")

# === MULTI-BACKEND DEMO ===

def run_multi_backend_demo():
    """Run the demo with multiple AnyIO backends."""
    if not HAS_ANYIO:
        logger.error("AnyIO not installed, cannot run multi-backend demo")
        return

    # Run with asyncio backend
    logger.info("\n=== RUNNING WITH ASYNCIO BACKEND ===")
    anyio.run(run_demo_anyio, backend="asyncio")

    # Run with trio backend if available
    try:
        import trio
        logger.info("\n=== RUNNING WITH TRIO BACKEND ===")
        anyio.run(simulate_trio_backend, backend="trio")
    except ImportError:
        logger.warning("\nTrio not installed, skipping Trio backend demo")
        logger.info("To run with Trio backend, install with: pip install trio")

if __name__ == "__main__":
    if not HAS_ANYIO:
        logger.error("AnyIO and sniffio packages are required. Install with: pip install anyio sniffio")
        sys.exit(1)

    run_multi_backend_demo()
