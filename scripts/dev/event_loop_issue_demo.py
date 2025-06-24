#!/usr/bin/env python3
"""
WebRTC Event Loop Issue Demo and Fix Demonstration.

This script demonstrates the event loop issue in async functions
and how our AsyncEventLoopHandler fix resolves it.
"""

import anyio
import time
import logging
from contextlib import asynccontextmanager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import our AsyncEventLoopHandler
from fixes.webrtc_event_loop_fix import AsyncEventLoopHandler

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

# === FIXED IMPLEMENTATION ===

def fixed_method():
    """
    This method demonstrates the fixed approach using AsyncEventLoopHandler.

    It safely handles running event loops by scheduling a background task
    instead of creating a new loop.
    """
    logger.info("Running fixed method...")
    start_time = time.time()

    try:
        # Create a fallback result for when we can't wait for the coroutine
        fallback_result = {
            "success": True,
            "simulated": True,
            "note": "Operation scheduled in background due to running event loop"
        }

        # Use our utility method to run the coroutine safely
        logger.info("Using AsyncEventLoopHandler to run coroutine safely")
        result = AsyncEventLoopHandler.run_coroutine(
            sample_coroutine(),
            fallback_result=fallback_result
        )

        logger.info(f"Method completed successfully: {result}")
        return result

    except Exception as e:
        logger.error(f"Error in fixed method: {e}")
        return {"success": False, "error": str(e)}
    finally:
        logger.info(f"Method took {time.time() - start_time:.2f} seconds")

# === FASTAPI SIMULATION ===

@asynccontextmanager
async def lifespan(app):
    """Simulate FastAPI lifespan context."""
    # Set up stuff
    yield
    # Clean up stuff
    await anyio.sleep(1.5)  # Wait for background tasks to complete

async def simulate_fastapi_endpoint_calls():
    """Simulate FastAPI endpoint calls in an already running event loop."""
    logger.info("\n=== SIMULATING FASTAPI ENVIRONMENT ===")
    logger.info("FastAPI uses a running event loop for handling requests")

    # First, try the problematic method
    logger.info("\n--- Testing problematic method in FastAPI context ---")
    try:
        problematic_method()
        logger.info("Problematic method did not raise an exception (unexpected)")
    except Exception as e:
        logger.error(f"Problematic method raised an exception (expected): {e}")

    # Now, try the fixed method
    logger.info("\n--- Testing fixed method in FastAPI context ---")
    try:
        result = fixed_method()
        logger.info(f"Fixed method returned: {result}")
        # If we got a simulated result, the coroutine was scheduled in the background
        if result.get("simulated", False):
            logger.info("The coroutine was scheduled in the background, still running...")
    except Exception as e:
        logger.error(f"Fixed method raised an exception (unexpected): {e}")

    return

async def run_demo():
    """Run the complete demonstration."""
    logger.info("=== EVENT LOOP ISSUE DEMO ===\n")

    # First, test without a running event loop
    logger.info("Testing in a context WITHOUT a running event loop:")

    logger.info("\n--- Running problematic method ---")
    problematic_method()

    logger.info("\n--- Running fixed method ---")
    fixed_method()

    # Now, simulate FastAPI where the event loop is running
    app = "FastAPISimulation"
    async with lifespan(app):
        await simulate_fastapi_endpoint_calls()

    # Wait to ensure any background tasks complete
    logger.info("\nWaiting for background tasks to complete...")
    await anyio.sleep(2)

    logger.info("\n=== DEMO COMPLETE ===")

if __name__ == "__main__":
    anyio.run(run_demo())
