"""Lightweight MCP HTTP server for integration tests."""

from __future__ import annotations

import argparse
import time
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class InMemoryClusterState:
    def __init__(self, node_id: str, role: str) -> None:
        self.node_id = node_id
        self.role = role
        self.peers: Dict[str, Dict[str, Any]] = {}
        self.leader: Dict[str, Any] | None = {"id": node_id, "role": role}
        self.replication_tasks: List[Dict[str, Any]] = []
        self.index_data: Dict[str, Dict[str, Any]] = {"embeddings": {}}

    def health_payload(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "timestamp": time.time(),
            "node_info": {"id": self.node_id, "role": self.role},
            "cluster_info": {
                "peer_count": len(self.peers),
                "leader": self.leader,
            },
            "services": {
                "replication_manager": {"status": "running"},
                "indexing_service": {"status": "running"},
            },
        }


def create_app(state: InMemoryClusterState) -> FastAPI:
    app = FastAPI(title="MCP Test Server")

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:  # noqa: ANN001
        return JSONResponse(status_code=400, content={"success": False, "message": f"validation error: {exc}"})

    @app.get("/health")
    async def health() -> Dict[str, Any]:
        return state.health_payload()

    @app.get("/cluster/status")
    async def cluster_status() -> Dict[str, Any]:
        return state.health_payload()

    @app.get("/cluster/peers")
    async def get_peers() -> Dict[str, Any]:
        return {"peers": list(state.peers.values())}

    @app.post("/cluster/peers")
    async def add_peer(payload: Dict[str, Any]) -> Dict[str, Any]:
        required = {"id", "role", "address", "port"}
        if not required.issubset(payload):
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "validation error: missing fields"},
            )
        peer_id = payload["id"]
        state.peers[peer_id] = payload
        return {"success": True, "peer_id": peer_id}

    @app.delete("/cluster/peers/{peer_id}")
    async def remove_peer(peer_id: str) -> Dict[str, Any]:
        state.peers.pop(peer_id, None)
        return {"success": True, "peer_id": peer_id}

    @app.post("/cluster/election/trigger")
    async def trigger_election() -> Dict[str, Any]:
        state.leader = {"id": state.node_id, "role": state.role}
        return {"leader": state.leader, "election_time": time.time()}

    @app.get("/cluster/leader")
    async def get_leader() -> Dict[str, Any]:
        return {"leader": state.leader}

    @app.post("/cluster/heartbeat")
    async def heartbeat(_: Dict[str, Any]) -> Dict[str, Any]:
        return {"success": True}

    @app.post("/replication/replicate")
    async def replicate(payload: Dict[str, Any]) -> Dict[str, Any]:
        cid = payload.get("cid")
        target_peers = payload.get("target_peers")
        if not cid or not target_peers:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "missing cid or target_peers"},
            )
        task = {"cid": cid, "targets": target_peers, "status": "queued"}
        state.replication_tasks.append(task)
        return {"success": True, "cid": cid}

    @app.get("/replication/status")
    async def replication_status() -> Dict[str, Any]:
        total = len(state.replication_tasks)
        completed = len([t for t in state.replication_tasks if t.get("status") == "completed"])
        failed = len([t for t in state.replication_tasks if t.get("status") == "failed"])
        return {"total_tasks": total, "completed_tasks": completed, "failed_tasks": failed}

    @app.post("/indexing/data")
    async def add_index_data(payload: Dict[str, Any]) -> Dict[str, Any]:
        index_type = payload.get("index_type")
        key = payload.get("key")
        data = payload.get("data")
        if index_type != "embeddings" or not key or data is None:
            return JSONResponse(status_code=400, content={"success": False, "message": "validation error"})
        state.index_data.setdefault(index_type, {})[key] = data
        return {"success": True, "key": key}

    @app.get("/indexing/data/{index_type}/{key}")
    async def get_index_data(index_type: str, key: str) -> Dict[str, Any]:
        data = state.index_data.get(index_type, {}).get(key)
        if data is None:
            raise HTTPException(status_code=404, detail={"success": False, "message": "not found"})
        return {"success": True, "key": key, "data": data}

    @app.get("/indexing/data/{index_type}")
    async def get_all_index_data(index_type: str) -> Dict[str, Any]:
        data = state.index_data.get(index_type, {})
        return {"success": True, "total_entries": len(data), "data": data}

    @app.delete("/indexing/data/{index_type}/{key}")
    async def remove_index_data(index_type: str, key: str) -> Dict[str, Any]:
        state.index_data.get(index_type, {}).pop(key, None)
        return {"success": True, "key": key}

    @app.post("/indexing/search/{index_type}")
    async def search_index(index_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if index_type != "embeddings":
            return JSONResponse(status_code=400, content={"success": False, "message": "validation error"})
        top_k = int(payload.get("top_k", 5))
        entries = list(state.index_data.get(index_type, {}).items())
        results = [
            {"key": key, "score": 1.0, "data": data} for key, data in entries[:top_k]
        ]
        return {"success": True, "results": results}

    @app.get("/indexing/stats")
    async def index_stats() -> Dict[str, Any]:
        indexes = {name: len(data) for name, data in state.index_data.items()}
        return {
            "node_role": state.role,
            "total_indexes": len(indexes),
            "indexes": indexes,
        }

    return app


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--node-id", default="test-node")
    parser.add_argument("--role", default="master")
    parser.add_argument("--port", type=int, default=19998)
    args = parser.parse_args()

    state = InMemoryClusterState(node_id=args.node_id, role=args.role)
    app = create_app(state)

    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
