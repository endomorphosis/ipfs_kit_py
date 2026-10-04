"""Profile F Event DAG retention store for ``ipfs_kit_py``.

This is a dependency-free port of the established ``ipfs_datasets_py`` MCP++
epoch-compaction design. Recent events are kept in memory, old epochs are
archived atomically, and each archive has a Merkle certificate. The default
certificate is a hash commitment, not a zero-knowledge proof.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


PROFILE_CAPABILITY = "mcp++/event-dag"
PROFILE_NAME = "Profile F: Event DAG Provenance, Archival, and Compaction"


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _leaf(cid: str) -> str:
    return hashlib.sha256(cid.encode("utf-8")).hexdigest()


def _pair(left: str, right: str) -> str:
    return hashlib.sha256((left + right).encode("utf-8")).hexdigest()


def build_merkle_tree(cids: List[str]) -> tuple[str, List[List[str]]]:
    if not cids:
        return hashlib.sha256(b"empty").hexdigest(), [[]]
    current = [_leaf(cid) for cid in cids]
    layers = [current[:]]
    while len(current) > 1:
        current = [_pair(current[index], current[index + 1] if index + 1 < len(current) else current[index])
                   for index in range(0, len(current), 2)]
        layers.append(current[:])
    return current[0], layers


def merkle_proof(cid: str, cids: List[str], layers: List[List[str]]) -> List[Dict[str, str]]:
    try:
        index = cids.index(cid)
    except ValueError:
        return []
    result: List[Dict[str, str]] = []
    for layer in layers[:-1]:
        if index % 2:
            result.append({"side": "left", "hash": layer[index - 1]})
        else:
            sibling = index + 1 if index + 1 < len(layer) else index
            result.append({"side": "right", "hash": layer[sibling]})
        index //= 2
    return result


def verify_merkle_proof(cid: str, proof: List[Dict[str, str]], root: str) -> bool:
    current = _leaf(cid)
    for step in proof:
        current = _pair(step["hash"], current) if step.get("side") == "left" else _pair(current, step["hash"])
    return current == root


def _profile_f_zk_certificate(event_cids: List[str]) -> Optional[Dict[str, Any]]:
    """Use the canonical datasets provider when a real verifier is provisioned."""
    mode = os.environ.get("MCPPP_PROFILE_F_ZK", "0").strip().lower()
    if mode not in {"1", "true", "yes", "required"}:
        return None
    try:
        from ipfs_datasets_py.mcp_server.event_dag_zkp import availability, prove_event_dag_compaction
        if not availability().get("available"):
            raise RuntimeError("Profile F Groth16 provider is unavailable")
        return prove_event_dag_compaction(event_cids)
    except Exception as error:
        if mode == "required":
            raise RuntimeError("Profile F ZK proof is required but unavailable") from error
        return None


@dataclass(frozen=True)
class ArchiveBoundary:
    event_cid: str
    archive_cid: str
    certificate_cid: str


class EventDAGStore:
    """Persistent hot/cold Event DAG with bounded provenance traversal."""

    def __init__(self, storage_dir: Optional[str] = None, hot_event_max: Optional[int] = None, epoch_size: Optional[int] = None) -> None:
        root = storage_dir or os.environ.get(
            "MCPPLUSPLUS_EVENT_DAG_DIR",
            os.path.expanduser("~/.cache/ipfs_kit_py/mcppp_event_dag"),
        )
        self.root = Path(root)
        self.archive_dir = self.root / "archives"
        self.state_path = self.root / "state.json"
        self.root.mkdir(parents=True, exist_ok=True)
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        self.hot_event_max = int(hot_event_max or os.environ.get("MCPPP_HOT_TIER_MAX", "2000"))
        self.epoch_size = int(epoch_size or os.environ.get("MCPPP_EPOCH_SIZE", "1000"))
        self._state = self._load()

    def _load(self) -> Dict[str, Any]:
        try:
            state = json.loads(self.state_path.read_text(encoding="utf-8"))
            if state.get("version") == 1:
                return state
        except (OSError, ValueError, AttributeError):
            pass
        return {"version": 1, "hot_events": {}, "archives": {}, "certificates": {}, "event_index": {}}

    def _save(self) -> None:
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self._state, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        temporary.replace(self.state_path)

    def profile_metadata(self) -> Dict[str, Any]:
        return {
            "capability": PROFILE_CAPABILITY,
            "profile_name": PROFILE_NAME,
            "retention": {"hot_event_max": self.hot_event_max, "epoch_size": self.epoch_size},
            "certificate_policy": {
                "default_proof_system": "hash-commitment-v1",
                "zero_knowledge": False,
                "note": "Hash commitments prove archive integrity and are not zero-knowledge proofs.",
            },
        }

    def append(self, event: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(event, dict):
            raise ValueError("Event DAG append requires an event object")
        event_cid = str(event.get("event_cid") or _digest(event))
        if event_cid in self._state["hot_events"]:
            return {"event_cid": event_cid, "status": "already_hot", "profile": self.profile_metadata()}
        if event_cid in self._state["event_index"]:
            return {"event_cid": event_cid, "status": "already_archived", "profile": self.profile_metadata()}
        node = dict(event)
        node["event_cid"] = event_cid
        node["parents"] = [str(parent) for parent in node.get("parents", []) if parent]
        node.setdefault("timestamp", "")
        node.setdefault("event_type", "execution")
        self._state["hot_events"][event_cid] = node
        self._save()
        compaction = None
        if len(self._state["hot_events"]) > self.hot_event_max:
            compaction = self.compact(max_events=self.epoch_size, retain_recent=max(0, self.hot_event_max - self.epoch_size))
        return {"event_cid": event_cid, "status": "recorded", "compaction": compaction, "profile": self.profile_metadata()}

    def frontier(self) -> Dict[str, Any]:
        events = list(self._state["hot_events"].values())
        parents = {parent for event in events for parent in event.get("parents", [])}
        frontier = [event["event_cid"] for event in events if event["event_cid"] not in parents]
        if not frontier and self._state["certificates"]:
            newest = max(self._state["certificates"].values(), key=lambda cert: cert["epoch_id"])
            frontier = newest.get("frontier_cids", [])
        return {"frontier": frontier, "profile": self.profile_metadata()}

    def history(self, limit: int = 50) -> Dict[str, Any]:
        events = sorted(self._state["hot_events"].values(), key=lambda event: str(event.get("timestamp", "")), reverse=True)
        return {
            "events": events[:max(1, int(limit))],
            "count": len(events),
            "archived_count": len(self._state["event_index"]),
            "profile": self.profile_metadata(),
        }

    def provenance(self, event_cid: str, limit: int = 100) -> Dict[str, Any]:
        queue, seen, chain, boundaries = [event_cid], set(), [], []
        while queue and len(chain) < max(1, int(limit)):
            current = queue.pop(0)
            if current in seen:
                continue
            seen.add(current)
            event = self._state["hot_events"].get(current)
            if event:
                chain.append(event)
                queue.extend(event.get("parents", []))
            elif current in self._state["event_index"]:
                index = self._state["event_index"][current]
                boundaries.append(ArchiveBoundary(current, index["archive_cid"], index["certificate_cid"]).__dict__)
        return {"chain": chain, "archive_boundaries": boundaries, "truncated": bool(queue), "profile": self.profile_metadata()}

    def compact(self, max_events: Optional[int] = None, retain_recent: int = 0) -> Dict[str, Any]:
        entries = sorted(self._state["hot_events"].items(), key=lambda row: str(row[1].get("timestamp", "")))
        eligible_count = max(0, len(entries) - max(0, int(retain_recent)))
        selected = entries[:min(max(1, int(max_events or self.epoch_size)), eligible_count)]
        if not selected:
            return {"compacted": False, "reason": "no_eligible_hot_events", "profile": self.profile_metadata()}
        cids = [cid for cid, _ in selected]
        cid_set = set(cids)
        events = [event for _, event in selected]
        merkle_root, layers = build_merkle_tree(cids)
        all_events = list(self._state["hot_events"].values())
        roots = [event["event_cid"] for event in events if not any(parent in cid_set for parent in event.get("parents", []))]
        frontier = [event["event_cid"] for event in events if not any(
            candidate["event_cid"] in cid_set and event["event_cid"] in candidate.get("parents", []) for candidate in all_events
        )]
        epoch_id = len(self._state["certificates"])
        archive = {"schema": "mcp++/event-dag-archive@1", "epoch_id": epoch_id, "event_cids": cids, "events": events, "merkle_root": merkle_root, "merkle_layers": layers}
        archive_cid = _digest(archive)
        zk_certificate = _profile_f_zk_certificate(cids)
        certificate_basis = {
            "schema": "mcp++/event-dag-compaction-certificate@1",
            "profile": PROFILE_CAPABILITY,
            "profile_name": PROFILE_NAME,
            "archive_cid": archive_cid,
            "merkle_root": merkle_root,
            "epoch_id": epoch_id,
            "event_count": len(cids),
            "root_cids": roots,
            "frontier_cids": frontier,
            "proof_system": (zk_certificate or {}).get("proof_system", "hash-commitment-v1"),
            "zero_knowledge": bool((zk_certificate or {}).get("zero_knowledge", False)),
        }
        if zk_certificate:
            certificate_basis.update({
                "zk_merkle_root": zk_certificate["zk_merkle_root"],
                "verification_key_cid": zk_certificate["verification_key_cid"],
                "verification_key_sha256": zk_certificate["verification_key_sha256"],
                "circuit_version": zk_certificate["circuit_version"],
                "ruleset_id": zk_certificate["ruleset_id"],
                "proof_commitment": _digest(zk_certificate["proof"]),
            })
        certificate_cid = _digest(certificate_basis)
        certificate = {
            **certificate_basis,
            "certificate_cid": certificate_cid,
            "proof": zk_certificate["proof"] if zk_certificate else _digest(certificate_basis),
        }
        archive_path = self.archive_dir / f"{archive_cid}.json"
        temporary = archive_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(archive, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        temporary.replace(archive_path)
        self._state["archives"][archive_cid] = {"archive_cid": archive_cid, "certificate_cid": certificate_cid, **{key: certificate[key] for key in ("epoch_id", "merkle_root", "event_count", "root_cids", "frontier_cids")}}
        self._state["certificates"][certificate_cid] = certificate
        for cid in cids:
            self._state["hot_events"].pop(cid, None)
            self._state["event_index"][cid] = {"archive_cid": archive_cid, "certificate_cid": certificate_cid}
        self._save()
        return {"compacted": True, "archive_cid": archive_cid, "certificate": certificate, "compacted_cids": cids, "profile": self.profile_metadata()}

    def archives(self) -> Dict[str, Any]:
        return {"archives": list(self._state["archives"].values()), "profile": self.profile_metadata()}

    def certificate(self, certificate_cid: str) -> Optional[Dict[str, Any]]:
        certificate = self._state["certificates"].get(certificate_cid)
        return {"certificate": certificate, "profile": self.profile_metadata()} if certificate else None

    def verify(self, certificate_cid: str) -> Dict[str, Any]:
        certificate = self._state["certificates"].get(certificate_cid)
        if not certificate:
            return {"valid": False, "reason": "certificate_not_found", "profile": self.profile_metadata()}
        try:
            archive = json.loads((self.archive_dir / f"{certificate['archive_cid']}.json").read_text(encoding="utf-8"))
            root, _ = build_merkle_tree(archive["event_cids"])
            basis_keys = ("schema", "profile", "profile_name", "archive_cid", "merkle_root", "epoch_id", "event_count", "root_cids", "frontier_cids", "proof_system", "zero_knowledge")
            basis = {key: certificate[key] for key in basis_keys}
            if certificate.get("zero_knowledge"):
                zk_keys = ("zk_merkle_root", "verification_key_cid", "verification_key_sha256", "circuit_version", "ruleset_id", "proof_commitment")
                basis.update({key: certificate[key] for key in zk_keys})
                from ipfs_datasets_py.mcp_server.event_dag_zkp import verify_event_dag_compaction
                zk_result = verify_event_dag_compaction({key: certificate[key] for key in (*zk_keys[:-1], "proof_system", "zero_knowledge", "event_count", "proof")}, archive["event_cids"])
                proof_valid = bool(zk_result.get("valid")) and certificate["proof_commitment"] == _digest(certificate["proof"])
            else:
                proof_valid = certificate["proof"] == _digest(basis)
            valid = root == certificate["merkle_root"] and len(archive["event_cids"]) == certificate["event_count"] and proof_valid
            return {"valid": valid, "certificate": certificate, "proof_system": certificate["proof_system"], "zero_knowledge": certificate["zero_knowledge"], "profile": self.profile_metadata()}
        except (OSError, ValueError, KeyError):
            return {"valid": False, "reason": "archive_unavailable", "profile": self.profile_metadata()}

    def inclusion(self, event_cid: str) -> Optional[Dict[str, Any]]:
        index = self._state["event_index"].get(event_cid)
        if not index:
            return None
        try:
            archive = json.loads((self.archive_dir / f"{index['archive_cid']}.json").read_text(encoding="utf-8"))
            certificate = self._state["certificates"][index["certificate_cid"]]
            return {"event_cid": event_cid, "archive_cid": index["archive_cid"], "certificate_cid": index["certificate_cid"], "merkle_root": certificate["merkle_root"], "proof": merkle_proof(event_cid, archive["event_cids"], archive["merkle_layers"]), "profile": self.profile_metadata()}
        except (OSError, ValueError, KeyError):
            return None


__all__ = ["PROFILE_CAPABILITY", "PROFILE_NAME", "EventDAGStore", "build_merkle_tree", "merkle_proof", "verify_merkle_proof"]
