#!/usr/bin/env python3
"""
Advanced Filecoin Mock API Server

This script provides a mock implementation of the advanced Filecoin features
mentioned in the MCP roadmap, including:
1. Network Analytics & Metrics
2. Intelligent Miner Selection & Management
3. Enhanced Storage Operations
4. Content Health & Reliability
5. Blockchain Integration

It runs as a standalone FastAPI server that can be used for testing and
development without requiring actual Filecoin network access.
"""

import os
import sys
import time
import json
import uuid
import random
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import uvicorn
from fastapi import FastAPI, HTTPException, Query, Body, Path
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("filecoin-mock")

# Initialize FastAPI app
app = FastAPI(
    title="Advanced Filecoin Mock API",
    description="Mock API for testing advanced Filecoin features in MCP",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for mock data
storage = {
    "deals": {},
    "miners": {},
    "network_stats": {},
    "content": {},
    "chain": {},
    "transactions": [],
    "health_metrics": {},
}

# Sample miner data
SAMPLE_MINERS = [
    {"id": "t01000", "region": "North America", "reputation": 4.8, "success_rate": 0.99, "ask_price": "50000000000", "available_space": 1024000000000},
    {"id": "t01001", "region": "Europe", "reputation": 4.5, "success_rate": 0.97, "ask_price": "45000000000", "available_space": 2048000000000},
    {"id": "t01002", "region": "Asia", "reputation": 4.2, "success_rate": 0.95, "ask_price": "40000000000", "available_space": 3072000000000},
    {"id": "t01003", "region": "South America", "reputation": 4.0, "success_rate": 0.92, "ask_price": "35000000000", "available_space": 4096000000000},
    {"id": "t01004", "region": "Oceania", "reputation": 3.8, "success_rate": 0.90, "ask_price": "30000000000", "available_space": 5120000000000},
]

# Initialize mock data
def initialize_mock_data():
    """Initialize mock data for the server."""
    # Initialize miners
    for miner in SAMPLE_MINERS:
        storage["miners"][miner["id"]] = miner

    # Initialize network stats
    storage["network_stats"] = {
        "last_updated": time.time(),
        "chain_height": 1000000,
        "network_storage_capacity": 10000000000000,
        "active_miners": len(SAMPLE_MINERS),
        "average_price": "40000000000",
        "avg_block_time": 30,
        "current_base_fee": "100000000",
        "total_committed_storage": 5000000000000,
        "total_deals": 0,
        "gas_trends": [
            {"timestamp": time.time() - 86400, "base_fee": "90000000"},
            {"timestamp": time.time() - 43200, "base_fee": "95000000"},
            {"timestamp": time.time(), "base_fee": "100000000"}
        ]
    }

    # Initialize chain data
    storage["chain"] = {
        "blocks": [generate_mock_block(i) for i in range(10)],
        "height": 1000000,
        "last_finalized": 999990,
    }

    logger.info("Initialized mock data")


# Data Models
class DealRequest(BaseModel):
    """Model for a deal request."""
    cid: str
    miner_id: Optional[str] = None
    duration: int = 518400
    replication: int = 1
    max_price: Optional[str] = None
    verified: bool = False


class MetadataUpdate(BaseModel):
    """Model for metadata updates."""
    metadata: Dict[str, Any]


# Helper functions
def generate_mock_cid() -> str:
    """Generate a mock CID."""
    return f"bafy{uuid.uuid4().hex[:44]}"


def generate_mock_deal(cid: str, miner_id: str, size: int = 1024*1024):
    """Generate mock deal data."""
    deal_id = str(uuid.uuid4())
    now = time.time()
    start_date = now + random.randint(600, 3600)  # Start in 10-60 minutes

    # Calculate price based on size and duration
    price_per_gib_per_epoch = int(storage["miners"][miner_id]["ask_price"])
    gib = size / (1024 * 1024 * 1024)
    duration = 518400  # 180 days in epochs
    price = int(price_per_gib_per_epoch * gib * duration)

    deal = {
        "deal_id": deal_id,
        "cid": cid,
        "miner": miner_id,
        "client": "t3abc123def456",
        "size": size,
        "price": str(price),
        "duration": duration,
        "start_time": start_date,
        "end_time": start_date + (duration * 30),  # Roughly 30 seconds per epoch
        "created_at": now,
        "updated_at": now,
        "verified": False,
        "state": "proposed",
        "sector": None,
        "health": 100,
        "history": [
            {"time": now, "state": "proposed", "message": "Deal proposed"},
        ],
    }

    return deal_id, deal


def generate_mock_block(height: int):
    """Generate a mock blockchain block."""
    return {
        "height": 1000000 - height,
        "cid": generate_mock_cid(),
        "timestamp": time.time() - (height * 30),
        "parent_cid": generate_mock_cid() if height > 0 else None,
        "miner": random.choice(list(storage["miners"].keys())),
        "messages": random.randint(10, 100),
        "reward": str(10000000000 + random.randint(0, 1000000000)),
    }


def select_miners(replication: int, max_price: Optional[str] = None, region: Optional[str] = None):
    """Select appropriate miners based on criteria."""
    candidates = list(storage["miners"].values())

    # Filter by price if specified
    if max_price:
        max_price_int = int(max_price)
        candidates = [m for m in candidates if int(m["ask_price"]) <= max_price_int]

    # Filter by region if specified
    if region:
        candidates = [m for m in candidates if m["region"] == region]

    # Sort by reputation (higher is better)
    candidates.sort(key=lambda m: m["reputation"], reverse=True)

    # Take the top N (replication count)
    selected = candidates[:min(replication, len(candidates))]

    return [m["id"] for m in selected]


def update_deal_state(deal_id: str, new_state: str, message: str = ""):
    """Update a deal's state and add to history."""
    if deal_id not in storage["deals"]:
        return False

    now = time.time()
    deal = storage["deals"][deal_id]
    old_state = deal["state"]
    deal["state"] = new_state
    deal["updated_at"] = now

    # Add to history
    history_entry = {
        "time": now,
        "state": new_state,
        "message": message or f"State changed from {old_state} to {new_state}",
    }
    deal["history"].append(history_entry)

    # Update specific fields based on state
    if new_state == "active":
        deal["sector"] = f"s-t01-{random.randint(1000, 9999)}"

    # Update health metrics
    if new_state == "active" or new_state == "sealed":
        storage["health_metrics"][deal_id] = {
            "last_checked": now,
            "health": 100,
            "message": "Deal is healthy",
            "checks": [
                {"time": now, "result": "success", "message": "Initial health check passed"}
            ]
        }

    return True


# Set up background tasks to update mock data
async def background_task():
    """Background task to update mock data periodically."""
    while True:
        try:
            # Update network stats
            storage["network_stats"]["last_updated"] = time.time()
            storage["network_stats"]["chain_height"] += random.randint(5, 20)

            # Update deal states
            for deal_id, deal in list(storage["deals"].items()):
                # Advance deal states based on time
                now = time.time()

                if deal["state"] == "proposed" and now - deal["created_at"] > 600:
                    # After 10 minutes, move to published
                    update_deal_state(deal_id, "published", "Deal published on-chain")

                elif deal["state"] == "published" and now - deal["updated_at"] > 900:
                    # After 15 minutes, move to active
                    update_deal_state(deal_id, "active", "Deal activated by storage provider")

                elif deal["state"] == "active" and now - deal["updated_at"] > 1800:
                    # After 30 minutes, move to sealed
                    update_deal_state(deal_id, "sealed", "Deal has been sealed")

                # Update health metrics
                if deal["state"] in ["active", "sealed"]:
                    if deal_id in storage["health_metrics"]:
                        health = storage["health_metrics"][deal_id]
                        if now - health["last_checked"] > 1800:  # 30 minutes
                            health["last_checked"] = now
                            health_score = random.randint(90, 100)
                            health["health"] = health_score
                            health["message"] = "Regular health check"
                            health["checks"].append({
                                "time": now,
                                "result": "success",
                                "message": f"Health check passed with score {health_score}"
                            })

            # Add a new block every ~30 seconds
            if random.random() < 0.1:  # Only add block ~10% of the time to simulate 30s block time
                new_block = generate_mock_block(0)
                new_block["height"] = storage["chain"]["height"] + 1
                storage["chain"]["height"] = new_block["height"]
                storage["chain"]["blocks"].insert(0, new_block)
                # Keep only the last 10 blocks
                storage["chain"]["blocks"] = storage["chain"]["blocks"][:10]

            # Sleep for 5 seconds before next update
            await anyio.sleep(5)

        except Exception as e:
            logger.error(f"Error in background task: {e}")
            await anyio.sleep(5)


# API Routes - Network Analytics & Metrics
@app.get("/api/v0/filecoin/advanced/network/stats")
async def get_network_stats():
    """Get current Filecoin network statistics."""
    return {
        "success": True,
        "stats": storage["network_stats"],
        "timestamp": time.time()
    }


@app.get("/api/v0/filecoin/advanced/network/gas")
async def get_gas_prices(days: int = Query(7, description="Number of days of gas price history")):
    """Get gas price trends for the Filecoin network."""
    now = time.time()
    trends = []

    # Generate data points every 6 hours
    for i in range(days * 4):
        timestamp = now - (i * 6 * 3600)
        base_fee = str(int(10000000 + 1000000 * (10 + random.randint(-5, 5))))
        trends.append({
            "timestamp": timestamp,
            "base_fee": base_fee,
            "date": datetime.fromtimestamp(timestamp).isoformat()
        })

    return {
        "success": True,
        "current_base_fee": storage["network_stats"]["current_base_fee"],
        "trends": sorted(trends, key=lambda x: x["timestamp"]),
        "period_days": days
    }


@app.get("/api/v0/filecoin/advanced/network/storage")
async def get_storage_stats():
    """Get storage capacity and utilization statistics."""
    # Generate price trends
    price_history = []
    now = time.time()

    for i in range(30):
        timestamp = now - (i * 24 * 3600)
        avg_price = str(int(40000000000 + 5000000000 * (10 + random.randint(-5, 5))))
        price_history.append({
            "timestamp": timestamp,
            "average_price": avg_price,
            "date": datetime.fromtimestamp(timestamp).isoformat()
        })

    return {
        "success": True,
        "total_capacity": storage["network_stats"]["network_storage_capacity"],
        "committed_storage": storage["network_stats"]["total_committed_storage"],
        "utilization_percentage": round(storage["network_stats"]["total_committed_storage"] / storage["network_stats"]["network_storage_capacity"] * 100, 2),
        "price_trends": sorted(price_history, key=lambda x: x["timestamp"]),
        "regional_stats": {
            "North America": {"capacity": 3000000000000, "price": "50000000000"},
            "Europe": {"capacity": 2500000000000, "price": "45000000000"},
            "Asia": {"capacity": 2000000000000, "price": "40000000000"},
            "South America": {"capacity": 1500000000000, "price": "35000000000"},
            "Oceania": {"capacity": 1000000000000, "price": "30000000000"},
        }
    }


# API Routes - Miner Selection & Management
@app.get("/api/v0/filecoin/advanced/miners")
async def list_miners(
    region: Optional[str] = Query(None, description="Filter by region"),
    min_reputation: Optional[float] = Query(None, description="Minimum reputation score"),
    max_price: Optional[str] = Query(None, description="Maximum price (attoFIL)"),
    available_space: Optional[int] = Query(None, description="Minimum available space (bytes)"),
    limit: int = Query(100, description="Maximum number of miners to return")
):
    """List and filter storage miners."""
    miners = list(storage["miners"].values())

    # Apply filters
    if region:
        miners = [m for m in miners if m["region"] == region]

    if min_reputation:
        miners = [m for m in miners if m["reputation"] >= min_reputation]

    if max_price:
        max_price_int = int(max_price)
        miners = [m for m in miners if int(m["ask_price"]) <= max_price_int]

    if available_space:
        miners = [m for m in miners if m["available_space"] >= available_space]

    # Sort by reputation
    miners.sort(key=lambda m: m["reputation"], reverse=True)

    # Apply limit
    miners = miners[:limit]

    return {
        "success": True,
        "miners": miners,
        "count": len(miners),
        "total_miners": len(storage["miners"])
    }


@app.get("/api/v0/filecoin/advanced/miners/{miner_id}")
async def get_miner_info(miner_id: str = Path(..., description="Miner ID")):
    """Get detailed information about a specific miner."""
    if miner_id not in storage["miners"]:
        raise HTTPException(status_code=404, detail=f"Miner {miner_id} not found")

    miner = storage["miners"][miner_id].copy()

    # Add additional detailed information
    miner["deal_success_count"] = random.randint(100, 1000)
    miner["deal_failure_count"] = int(miner["deal_success_count"] * (1 - miner["success_rate"]))
    miner["online_percentage"] = round(random.uniform(95, 99.9), 2)
    miner["time_to_seal"] = random.randint(1, 24)  # hours
    miner["regions_served"] = [miner["region"]]

    # Add historical performance data
    now = time.time()
    performance_history = []
    for i in range(30):
        timestamp = now - (i * 24 * 3600)
        performance_history.append({
            "timestamp": timestamp,
            "date": datetime.fromtimestamp(timestamp).isoformat(),
            "success_rate": round(miner["success_rate"] + random.uniform(-0.05, 0.05), 2),
            "online_percentage": round(miner["online_percentage"] + random.uniform(-2, 2), 2),
            "time_to_seal": miner["time_to_seal"] + random.randint(-1, 1)
        })

    miner["performance_history"] = sorted(performance_history, key=lambda x: x["timestamp"])

    return {
        "success": True,
        "miner": miner
    }


@app.post("/api/v0/filecoin/advanced/miners/recommend")
async def recommend_miners(
    size: int = Query(..., description="File size in bytes"),
    replication: int = Query(1, description="Number of replicas desired"),
    max_price: Optional[str] = Query(None, description="Maximum price per GiB per epoch"),
    duration: int = Query(518400, description="Deal duration in epochs"),
    region: Optional[str] = Query(None, description="Preferred region"),
    verified: bool = Query(False, description="Whether to use verified datacap")
):
    """Recommend miners based on file requirements."""
    # Get candidate miners based on criteria
    miners = list(storage["miners"].values())

    # Filter by price if specified
    if max_price:
        max_price_int = int(max_price)
        miners = [m for m in miners if int(m["ask_price"]) <= max_price_int]

    # Filter by region if specified
    if region:
        preferred_miners = [m for m in miners if m["region"] == region]
        if preferred_miners:
            miners = preferred_miners

    # Filter by available space
    miners = [m for m in miners if m["available_space"] >= size]

    # Sort by combination of criteria (price, reputation, success_rate)
    def score_miner(m):
        price_score = 1.0 - (float(m["ask_price"]) / 50000000000)  # Lower price is better
        return (price_score * 0.4) + (m["reputation"] / 5.0 * 0.3) + (m["success_rate"] * 0.3)

    miners.sort(key=score_miner, reverse=True)

    # Calculate costs
    gib = size / (1024 * 1024 * 1024)
    if gib < 0.001:
        gib = 0.001  # Minimum 1 MiB

    recommended = miners[:min(replication, len(miners))]

    # Calculate storage costs
    costs = []
    for m in recommended:
        price_per_gib_per_epoch = int(m["ask_price"])
        total_cost = price_per_gib_per_epoch * gib * duration

        # Apply discount for verified deals
        if verified:
            total_cost *= 0.7  # 30% discount for verified deals

        costs.append({
            "miner_id": m["id"],
            "price_per_gib_per_epoch": price_per_gib_per_epoch,
            "total_cost": str(int(total_cost)),
            "total_cost_fil": str(int(total_cost) / 1e18),  # Convert attoFIL to FIL
            "duration_days": round(duration * 30 / 86400),  # Convert epochs to days
        })

    return {
        "success": True,
        "recommended_miners": [m["id"] for m in recommended],
        "file_size_bytes": size,
        "file_size_gib": gib,
        "replication": min(replication, len(recommended)),
        "costs": costs,
        "total_cost": str(sum(int(c["total_cost"]) for c in costs)),
        "total_cost_fil": str(sum(int(c["total_cost"]) for c in costs) / 1e18),
    }


# API Routes - Enhanced Storage Operations
@app.post("/api/v0/filecoin/advanced/storage/deal")
async def make_deal(deal_request: DealRequest):
    """Create a storage deal with enhanced options."""
    cid = deal_request.cid

    # Generate a new CID if not provided
    if not cid or cid == "auto":
        cid = generate_mock_cid()

    # Select miners if not specified
    miners = []
    if deal_request.miner_id:
        if deal_request.miner_id in storage["miners"]:
            miners = [deal_request.miner_id]
        else:
            raise HTTPException(status_code=404, detail=f"Miner {deal_request.miner_id} not found")
    else:
        miners = select_miners(
            deal_request.replication,
            deal_request.max_price
        )

    if not miners:
        raise HTTPException(status_code=400, detail="No suitable miners found")

    # Create deals
    deals = []
    size = random.randint(1024**2, 100*(1024**2))  # Random size between 1MB and 100MB

    for miner_id in miners:
        deal_id, deal = generate_mock_deal(cid, miner_id, size)
        deal["verified"] = deal_request.verified
        deal["duration"] = deal_request.duration

        # Store the deal
        storage["deals"][deal_id] = deal
        deals.append(deal)

    # Store content reference
    storage["content"][cid] = {
        "size": size,
        "deals": [d["deal_id"] for d in deals],
        "created_at": time.time(),
        "replication": len(deals),
    }

    # Update network stats
    storage["network_stats"]["total_deals"] += len(deals)

    return {
        "success": True,
        "cid": cid,
        "deals": deals,
        "deal_count": len(deals),
        "timestamp": time.time(),
    }


@app.get("/api/v0/filecoin/advanced/storage/deal/{deal_id}")
async def get_deal_info(deal_id: str = Path(..., description="Deal ID")):
    """Get information about a specific deal."""
    if deal_id not in storage["deals"]:
        raise HTTPException(status_code=404, detail=f"Deal {deal_id} not found")

    return {
        "success": True,
        "deal": storage["deals"][deal_id]
    }


@app.get("/api/v0/filecoin/advanced/storage/cid/{cid}")
async def get_cid_info(cid: str = Path(..., description="Content ID")):
    """Get information about all deals for a CID."""
    if cid not in storage["content"]:
        raise HTTPException(status_code=404, detail=f"Content {cid} not found")

    content = storage["content"][cid]
    deals = [storage["deals"][deal_id] for deal_id in content["deals"] if deal_id in storage["deals"]]

    return {
        "success": True,
        "cid": cid,
        "size": content["size"],
        "deals": deals,
        "deal_count": len(deals),
        "created_at": content["created_at"],
        "replication": content["replication"],
    }


# API Routes - Content Health & Reliability
@app.get("/api/v0/filecoin/advanced/health/deal/{deal_id}")
async def get_deal_health(deal_id: str = Path(..., description="Deal ID")):
    """Get health metrics for a specific deal."""
    if deal_id not in storage["deals"]:
        raise HTTPException(status_code=404, detail=f"Deal {deal_id} not found")

    deal = storage["deals"][deal_id]

    # Generate health metrics if not already present
    if deal_id not in storage["health_metrics"]:
        now = time.time()
        health_score = random.randint(90, 100)
        storage["health_metrics"][deal_id] = {
            "last_checked": now,
            "health": health_score,
            "message": "Initial health check",
            "checks": [
                {"time": now, "result": "success", "message": f"Initial health check: {health_score}"}
            ]
        }

    return {
        "success": True,
        "deal_id": deal_id,
        "cid": deal["cid"],
        "health": storage["health_metrics"][deal_id],
        "state": deal["state"],
        "history": deal["history"],
    }


@app.get("/api/v0/filecoin/advanced/health/cid/{cid}")
async def get_cid_health(cid: str = Path(..., description="Content ID")):
    """Get health metrics for all deals of a CID."""
    if cid not in storage["content"]:
        raise HTTPException(status_code=404, detail=f"Content {cid} not found")

    content = storage["content"][cid]
    deal_healths = []

    for deal_id in content["deals"]:
        if deal_id in storage["deals"]:
            deal = storage["deals"][deal_id]

            # Generate health metrics if not already present
            if deal_id not in storage["health_metrics"]:
                now = time.time()
                health_score = random.randint(90, 100)
                storage["health_metrics"][deal_id] = {
                    "last_checked": now,
                    "health": health_score,
                    "message": "Initial health check",
                    "checks": [
                        {"time": now, "result": "success", "message": f"Initial health check: {health_score}"}
                    ]
                }

            deal_healths.append({
                "deal_id": deal_id,
                "miner": deal["miner"],
                "state": deal["state"],
                "health": storage["health_metrics"][deal_id]["health"],
                "last_checked": storage["health_metrics"][deal_id]["last_checked"],
            })

    # Calculate overall health
    overall_health = 100
    if deal_healths:
        overall_health = sum(d["health"] for d in deal_healths) / len(deal_healths)

    # Determine if repairs are needed
    needs_repair = overall_health < 90
    repair_recommendations = []

    if needs_repair:
        # Find unhealthy deals
        unhealthy_deals = [d for d in deal_healths if d["health"] < 90]
        for deal in unhealthy_deals:
            repair_recommendations.append({
                "deal_id": deal["deal_id"],
                "health": deal["health"],
                "action": "replicate",
                "reason": f"Deal health below threshold: {deal['health']}",
            })

    return {
        "success": True,
        "cid": cid,
        "overall_health": overall_health,
        "deal_count": len(deal_healths),
        "healthy_deals": len([d for d in deal_healths if d["health"] >= 90]),
        "unhealthy_deals": len([d for d in deal_healths if d["health"] < 90]),
        "deals": deal_healths,
        "needs_repair": needs_repair,
        "repair_recommendations": repair_recommendations,
    }


@app.post("/api/v0/filecoin/advanced/health/repair")
async def repair_content(
    cid: str = Query(..., description="Content ID to repair"),
    strategy: str = Query("replicate", description="Repair strategy: replicate, recover, migrate")
):
    """Initiate repair operations for content."""
    if cid not in storage["content"]:
        raise HTTPException(status_code=404, detail=f"Content {cid} not found")

    content = storage["content"][cid]

    # Find unhealthy deals
    unhealthy_deals = []
    for deal_id in content["deals"]:
        if deal_id in storage["deals"] and deal_id in storage["health_metrics"]:
            if storage["health_metrics"][deal_id]["health"] < 90:
                unhealthy_deals.append(deal_id)

    # Process repairs based on strategy
    repair_results = []

    if strategy == "replicate":
        # Create new deals for the same CID
        size = content["size"]
        needed_replicas = min(content["replication"] - len(content["deals"]) + len(unhealthy_deals), 3)

        if needed_replicas > 0:
            # Select new miners different from current ones
            current_miners = [storage["deals"][deal_id]["miner"] for deal_id in content["deals"] if deal_id in storage["deals"]]
            candidates = [m for m in storage["miners"].keys() if m not in current_miners]

            if candidates:
                new_miners = random.sample(candidates, min(needed_replicas, len(candidates)))

                for miner_id in new_miners:
                    deal_id, deal = generate_mock_deal(cid, miner_id, size)

                    # Store the deal
                    storage["deals"][deal_id] = deal
                    content["deals"].append(deal_id)

                    repair_results.append({
                        "action": "replicate",
                        "deal_id": deal_id,
                        "miner": miner_id,
                        "status": "created",
                    })

    elif strategy == "recover":
        # Simulate data recovery process
        for deal_id in unhealthy_deals:
            # Update health metrics
            now = time.time()
            health = storage["health_metrics"][deal_id]
            health["last_checked"] = now
            health["health"] = 95  # Improved health
            health["message"] = "Repaired via data recovery"
            health["checks"].append({
                "time": now,
                "result": "success",
                "message": "Content repaired via data recovery"
            })

            repair_results.append({
                "action": "recover",
                "deal_id": deal_id,
                "status": "repaired",
                "new_health": 95,
            })

    elif strategy == "migrate":
        # Migrate to new miners
        size = content["size"]

        # Select new miners different from unhealthy ones
        unhealthy_miners = [storage["deals"][deal_id]["miner"] for deal_id in unhealthy_deals if deal_id in storage["deals"]]
        candidates = [m for m in storage["miners"].keys() if m not in unhealthy_miners]

        if candidates:
            for deal_id in unhealthy_deals:
                if deal_id in storage["deals"]:
                    # Select a new miner
                    new_miner = random.choice(candidates)

                    # Create new deal
                    new_deal_id, new_deal = generate_mock_deal(cid, new_miner, size)

                    # Store the deal
                    storage["deals"][new_deal_id] = new_deal
                    content["deals"].append(new_deal_id)

                    # Mark old deal for cancellation
                    old_deal = storage["deals"][deal_id]
                    old_deal["state"] = "terminating"
                    old_deal["history"].append({
                        "time": time.time(),
                        "state": "terminating",
                        "message": "Deal terminating due to migration",
                    })

                    repair_results.append({
                        "action": "migrate",
                        "old_deal_id": deal_id,
                        "new_deal_id": new_deal_id,
                        "old_miner": old_deal["miner"],
                        "new_miner": new_miner,
                        "status": "migrated",
                    })

    # Update network stats
    storage["network_stats"]["total_deals"] += len(repair_results)

    return {
        "success": True,
        "cid": cid,
        "strategy": strategy,
        "unhealthy_deals": len(unhealthy_deals),
        "repair_actions": len(repair_results),
        "results": repair_results,
    }


# API Routes - Blockchain Integration
@app.get("/api/v0/filecoin/advanced/blockchain/status")
async def get_blockchain_status():
    """Get current blockchain status."""
    return {
        "success": True,
        "chain_height": storage["chain"]["height"],
        "last_finalized": storage["chain"]["last_finalized"],
        "avg_block_time": storage["network_stats"]["avg_block_time"],
        "current_base_fee": storage["network_stats"]["current_base_fee"],
        "latest_blocks": storage["chain"]["blocks"][:5],
    }


@app.get("/api/v0/filecoin/advanced/blockchain/blocks")
async def get_blockchain_blocks(
    start: int = Query(None, description="Starting block height"),
    end: int = Query(None, description="Ending block height"),
    limit: int = Query(10, description="Maximum number of blocks to return")
):
    """Get blockchain blocks."""
    blocks = storage["chain"]["blocks"]

    if start:
        blocks = [b for b in blocks if b["height"] >= start]

    if end:
        blocks = [b for b in blocks if b["height"] <= end]

    # Sort by height descending
    blocks.sort(key=lambda b: b["height"], reverse=True)

    # Apply limit
    blocks = blocks[:limit]

    return {
        "success": True,
        "blocks": blocks,
        "count": len(blocks),
        "chain_height": storage["chain"]["height"],
    }


@app.get("/api/v0/filecoin/advanced/blockchain/deals")
async def get_blockchain_deals(
    miner: Optional[str] = Query(None, description="Filter by miner"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(100, description="Maximum number of deals to return")
):
    """Get on-chain deal information."""
    deals = list(storage["deals"].values())

    # Apply filters
    if miner:
        deals = [d for d in deals if d["miner"] == miner]

    if status:
        deals = [d for d in deals if d["state"] == status]

    # Sort by start time
    deals.sort(key=lambda d: d["start_time"], reverse=True)

    # Apply limit
    deals = deals[:limit]

    return {
        "success": True,
        "deals": deals,
        "count": len(deals),
        "total_deals": len(storage["deals"]),
        "filters_applied": {
            "miner": miner,
            "status": status,
        },
    }


@app.get("/api/v0/filecoin/advanced/blockchain/transaction/{tx_id}")
async def get_transaction_status(tx_id: str = Path(..., description="Transaction ID")):
    """Get transaction status from the blockchain."""
    # Generate a mock transaction
    tx = {
        "id": tx_id,
        "block_height": storage["chain"]["height"] - random.randint(0, 10),
        "block_cid": generate_mock_cid(),
        "timestamp": time.time() - random.randint(0, 3600),
        "from": f"t3{uuid.uuid4().hex[:15]}",
        "to": f"t3{uuid.uuid4().hex[:15]}",
        "value": str(random.randint(1000000000, 10000000000000)),
        "gas_fee": str(random.randint(1000000, 100000000)),
        "method": "PublishStorageDeal",
        "status": random.choice(["success", "success", "success", "pending", "failed"]),
        "confirmations": random.randint(1, 10),
    }

    return {
        "success": True,
        "transaction": tx
    }


# Initialize AnyIO for background tasks
import anyio
from fastapi import BackgroundTasks

@app.on_event("startup")
async def startup_event():
    """Initialize data and start background tasks on startup."""
    initialize_mock_data()
    anyio.lowlevel.spawn_system_task(background_task)


# Main entry point
if __name__ == "__main__":
    # Run the FastAPI server
    uvicorn.run("advanced_filecoin_mock:app", host="0.0.0.0", port=8175, reload=True)
