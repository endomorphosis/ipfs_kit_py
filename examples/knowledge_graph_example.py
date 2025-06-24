#!/usr/bin/env python3
"""
Knowledge Graph Example for IPFS Kit

This example demonstrates how to use the IPLD Knowledge Graph functionality
in IPFS Kit to create, query, and leverage a semantic graph of content-addressed
data. It shows how to build a graph representing research papers, concepts, and
their relationships, and then perform various types of queries including path
finding and graph-based retrieval.

The example covers:
1. Setting up the knowledge graph
2. Creating entities and relationships
3. Basic graph queries
4. Path finding
5. Vector search and GraphRAG
6. Importing and exporting subgraphs
7. Integration with other IPFS Kit components

Note: The GraphRAG demonstration requires `sentence-transformers` package.
Install it with `pip install sentence-transformers` if you want to run
the full example.
"""

import os
import json
import time
import uuid
import logging
import argparse
from typing import Dict, List, Optional, Any

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import from ipfs_kit_py
from ipfs_kit_py.ipfs_kit import ipfs_kit
from ipfs_kit_py.ipld_knowledge_graph import IPLDGraphDB, KnowledgeGraphQuery, GraphRAG

# Check if sentence-transformers is available for the GraphRAG demo
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logger.warning("sentence-transformers package not available. GraphRAG demo will be skipped.")
    logger.warning("Install with: pip install sentence-transformers")


def setup_knowledge_graph():
    """Initialize the knowledge graph components."""
    # Initialize IPFS Kit with knowledge graph enabled
    kit = ipfs_kit(metadata={"enable_knowledge_graph": True})

    if not hasattr(kit, "knowledge_graph"):
        logger.error("Knowledge graph not available in IPFS Kit instance")
        return None, None, None

    # Get components
    graph_db = kit.knowledge_graph
    query_interface = kit.graph_query

    # Initialize GraphRAG if sentence-transformers is available
    graph_rag = None
    if SENTENCE_TRANSFORMERS_AVAILABLE and hasattr(kit, "graph_rag"):
        # Load a small, fast model for the example
        logger.info("Loading sentence embedding model...")
        embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        graph_rag = GraphRAG(graph_db, embedding_model)
        logger.info("GraphRAG initialized with embedding model")

    return graph_db, query_interface, graph_rag


def build_research_knowledge_graph(graph_db):
    """Build a knowledge graph representing research papers and concepts."""
    logger.info("Building research knowledge graph...")

    # Add research papers
    paper1 = graph_db.add_entity(
        entity_id="paper1",
        entity_type="research_paper",
        properties={
            "title": "IPFS - Content Addressed, Versioned, P2P File System",
            "authors": ["Juan Benet"],
            "year": 2014,
            "abstract": "IPFS is a peer-to-peer distributed file system that seeks to connect "
                        "all computing devices with the same system of files. In some ways, IPFS is "
                        "similar to the Web, but IPFS could be seen as a single BitTorrent swarm, "
                        "exchanging objects within one Git repository. In other words, IPFS provides "
                        "a high-throughput, content-addressed block storage model, with content-addressed "
                        "hyperlinks. This forms a generalized Merkle directed acyclic graph (DAG).",
            "doi": "10.48550/arXiv.1407.3561",
            "keywords": ["content addressing", "distributed systems", "p2p", "merkle dag"]
        },
        # Simple vector embedding for the demonstration
        vector=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
    )

    paper2 = graph_db.add_entity(
        entity_id="paper2",
        entity_type="research_paper",
        properties={
            "title": "Filecoin: A Decentralized Storage Network",
            "authors": ["Protocol Labs"],
            "year": 2017,
            "abstract": "Filecoin is a distributed electronic currency similar to Bitcoin. Unlike Bitcoin's "
                        "computation-only proof-of-work, Filecoin's proof-of-work function includes a proof "
                        "that miners are storing the data they claim to hold. The Filecoin protocol weaves "
                        "crypto-economic incentives to ensure files are stored reliably over time.",
            "keywords": ["distributed storage", "cryptocurrency", "incentives", "proof of storage"]
        },
        vector=[0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
    )

    paper3 = graph_db.add_entity(
        entity_id="paper3",
        entity_type="research_paper",
        properties={
            "title": "libp2p: Multiprotocol Network Framework for Peer-to-Peer Applications",
            "authors": ["Juan Benet", "David Dias"],
            "year": 2018,
            "abstract": "libp2p is a modular network stack for peer-to-peer applications. It consists of "
                        "a collection of protocols, specifications and libraries that facilitate "
                        "peer-to-peer application development.",
            "keywords": ["p2p", "networking", "distributed systems", "protocol"]
        },
        vector=[0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    )

    # Add concepts
    concept_content_addressing = graph_db.add_entity(
        entity_id="concept_content_addressing",
        entity_type="concept",
        properties={
            "name": "Content Addressing",
            "description": "A technique to store and retrieve data based on its content rather than its location. "
                          "Content is typically hashed using a cryptographic hash function, and the resulting hash "
                          "serves as the content identifier (CID) used for retrieval."
        },
        vector=[0.9, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]
    )

    concept_dht = graph_db.add_entity(
        entity_id="concept_dht",
        entity_type="concept",
        properties={
            "name": "Distributed Hash Table",
            "description": "A distributed system that provides a lookup service similar to a hash table. "
                          "DHTs store key-value pairs and allow any participating node to efficiently retrieve "
                          "the value associated with a given key."
        },
        vector=[0.8, 0.9, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6]
    )

    concept_merkle_dag = graph_db.add_entity(
        entity_id="concept_merkle_dag",
        entity_type="concept",
        properties={
            "name": "Merkle DAG",
            "description": "A Merkle Directed Acyclic Graph is a data structure combining a Merkle tree "
                          "(hash tree) with a directed acyclic graph. It allows for content-addressed storage "
                          "with deduplicated data and secure verification of data integrity."
        },
        vector=[0.7, 0.8, 0.9, 0.1, 0.2, 0.3, 0.4, 0.5]
    )

    # Add authors
    author_benet = graph_db.add_entity(
        entity_id="author_benet",
        entity_type="person",
        properties={
            "name": "Juan Benet",
            "affiliation": "Protocol Labs",
            "role": "Founder and CEO"
        },
        vector=[0.5, 0.6, 0.7, 0.8, 0.9, 0.1, 0.2, 0.3]
    )

    author_dias = graph_db.add_entity(
        entity_id="author_dias",
        entity_type="person",
        properties={
            "name": "David Dias",
            "affiliation": "Protocol Labs",
            "role": "Research Engineer"
        },
        vector=[0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.1, 0.2]
    )

    # Add organizations
    org_protocol_labs = graph_db.add_entity(
        entity_id="org_protocol_labs",
        entity_type="organization",
        properties={
            "name": "Protocol Labs",
            "founded": 2014,
            "website": "https://protocol.ai/",
            "focus_areas": ["distributed systems", "content addressing", "web3"]
        },
        vector=[0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.1]
    )

    # Add relationships - papers to concepts
    graph_db.add_relationship(
        from_entity="paper1",
        to_entity="concept_content_addressing",
        relationship_type="discusses",
        properties={"centrality": "primary"}
    )

    graph_db.add_relationship(
        from_entity="paper1",
        to_entity="concept_dht",
        relationship_type="discusses",
        properties={"centrality": "secondary"}
    )

    graph_db.add_relationship(
        from_entity="paper1",
        to_entity="concept_merkle_dag",
        relationship_type="discusses",
        properties={"centrality": "primary"}
    )

    graph_db.add_relationship(
        from_entity="paper2",
        to_entity="concept_content_addressing",
        relationship_type="discusses",
        properties={"centrality": "secondary"}
    )

    graph_db.add_relationship(
        from_entity="paper3",
        to_entity="concept_dht",
        relationship_type="discusses",
        properties={"centrality": "primary"}
    )

    # Add relationships - papers to authors
    graph_db.add_relationship(
        from_entity="author_benet",
        to_entity="paper1",
        relationship_type="authored",
        properties={"date": "2014-07-14"}
    )

    graph_db.add_relationship(
        from_entity="org_protocol_labs",
        to_entity="paper2",
        relationship_type="published",
        properties={"date": "2017-07-19"}
    )

    graph_db.add_relationship(
        from_entity="author_benet",
        to_entity="paper3",
        relationship_type="authored",
        properties={"date": "2018-05-02"}
    )

    graph_db.add_relationship(
        from_entity="author_dias",
        to_entity="paper3",
        relationship_type="authored",
        properties={"date": "2018-05-02"}
    )

    # Add relationships - papers to papers
    graph_db.add_relationship(
        from_entity="paper2",
        to_entity="paper1",
        relationship_type="cites",
        properties={"section": "Background"}
    )

    graph_db.add_relationship(
        from_entity="paper3",
        to_entity="paper1",
        relationship_type="cites",
        properties={"section": "Introduction"}
    )

    # Add relationships - authors to organizations
    graph_db.add_relationship(
        from_entity="author_benet",
        to_entity="org_protocol_labs",
        relationship_type="founded",
        properties={"date": "2014"}
    )

    graph_db.add_relationship(
        from_entity="author_dias",
        to_entity="org_protocol_labs",
        relationship_type="works_for",
        properties={"start_date": "2016"}
    )

    logger.info("Knowledge graph built successfully with research papers, concepts, authors, and organizations")


def demonstrate_basic_queries(graph_db, query):
    """Demonstrate basic query operations on the knowledge graph."""
    logger.info("\n=== Basic Queries ===")

    # Query entities by type
    research_papers = graph_db.query_entities(entity_type="research_paper")
    logger.info(f"Found {len(research_papers)} research papers")
    for paper in research_papers:
        logger.info(f"  - {paper['properties']['title']} ({paper['properties']['year']})")

    # Find papers discussing content addressing
    papers_discussing_ca = query.find_related(
        entity_id="concept_content_addressing",
        relationship_type="discusses",
        direction="incoming"
    )
    logger.info(f"\nFound {len(papers_discussing_ca)} papers discussing content addressing:")
    for rel in papers_discussing_ca:
        paper = graph_db.get_entity(rel["entity_id"])
        logger.info(f"  - {paper['properties']['title']} (centrality: {rel['properties'].get('centrality', 'unknown')})")

    # Find papers by Juan Benet
    benet_papers = query.find_related(
        entity_id="author_benet",
        relationship_type="authored",
        direction="outgoing"
    )
    logger.info(f"\nPapers authored by Juan Benet: {len(benet_papers)}")
    for rel in benet_papers:
        paper = graph_db.get_entity(rel["entity_id"])
        logger.info(f"  - {paper['properties']['title']} ({paper['properties']['year']})")

    # Find papers that cite the original IPFS paper
    papers_citing_ipfs = query.find_related(
        entity_id="paper1",
        relationship_type="cites",
        direction="incoming"
    )
    logger.info(f"\nPapers citing the IPFS paper: {len(papers_citing_ipfs)}")
    for rel in papers_citing_ipfs:
        paper = graph_db.get_entity(rel["entity_id"])
        logger.info(f"  - {paper['properties']['title']} (section: {rel['properties'].get('section', 'unknown')})")


def demonstrate_path_finding(graph_db):
    """Demonstrate path finding between entities in the knowledge graph."""
    logger.info("\n=== Path Finding ===")

    # Find paths from Juan Benet to Content Addressing concept
    paths = graph_db.path_between(
        source_id="author_benet",
        target_id="concept_content_addressing",
        max_depth=3
    )

    logger.info(f"Found {len(paths)} paths from Juan Benet to Content Addressing concept:")
    for i, path in enumerate(paths):
        logger.info(f"Path {i+1}:")
        for node, rel in path:
            link_text = f" -> {rel}" if rel else ""
            logger.info(f"  {node}{link_text}")

    # Find all paths from Protocol Labs to the DHT concept
    paths = graph_db.path_between(
        source_id="org_protocol_labs",
        target_id="concept_dht",
        max_depth=4
    )

    logger.info(f"\nFound {len(paths)} paths from Protocol Labs to DHT concept:")
    for i, path in enumerate(paths):
        logger.info(f"Path {i+1}:")
        for node, rel in path:
            link_text = f" -> {rel}" if rel else ""
            logger.info(f"  {node}{link_text}")


def demonstrate_vector_search(graph_db, graph_rag):
    """Demonstrate vector search and GraphRAG capabilities."""
    if graph_rag is None:
        logger.warning("Skipping vector search demonstration (GraphRAG not available)")
        return

    logger.info("\n=== Vector Search and GraphRAG ===")

    # Define a query vector (in practice this would come from an embedding model)
    query_vector = [0.9, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]  # Similar to content_addressing

    # Perform vector similarity search
    similar_entities = graph_db.vector_search(query_vector, top_k=3)
    logger.info(f"Vector search results for query:")
    for result in similar_entities:
        entity = graph_db.get_entity(result["entity_id"])
        entity_name = entity["properties"].get("name", entity["properties"].get("title", entity["id"]))
        logger.info(f"  - {entity_name} (Score: {result['score']:.4f})")

    # Perform hybrid graph-vector search (GraphRAG)
    expanded_results = graph_db.graph_vector_search(query_vector, hop_count=1, top_k=5)
    logger.info(f"\nGraphRAG search results (with 1-hop expansion):")
    for result in expanded_results:
        entity = graph_db.get_entity(result["entity_id"])
        entity_name = entity["properties"].get("name", entity["properties"].get("title", entity["id"]))
        logger.info(f"  - {entity_name} (Score: {result['score']:.4f}, Distance: {result.get('distance', 0)})")

    # Demonstrate text query with GraphRAG
    user_query = "How does content addressing work in distributed systems?"
    logger.info(f"\nProcessing GraphRAG query: '{user_query}'")

    # Generate embedding for the query
    query_embedding = graph_rag.generate_embedding(user_query)

    # Retrieve context from knowledge graph
    context = graph_rag.retrieve(
        query_text=user_query,
        entity_types=["research_paper", "concept"],
        top_k=3,
        hop_count=1
    )

    logger.info(f"Retrieved {len(context['entities'])} entities as context")

    # Format context for LLM (for demonstration)
    formatted_context = graph_rag.format_context_for_llm(context, format_type="text")
    logger.info("\nFormatted context for LLM (first 500 chars):")
    logger.info(formatted_context[:500] + "...")

    # Generate LLM prompt
    prompt = graph_rag.generate_llm_prompt(user_query, context)
    logger.info("\nGenerated LLM prompt (first 500 chars):")
    logger.info(prompt[:500] + "...")


def demonstrate_subgraph_export_import(graph_db):
    """Demonstrate exporting and importing subgraphs."""
    logger.info("\n=== Subgraph Export and Import ===")

    # Export a subgraph centered on the IPFS paper
    subgraph = graph_db.export_subgraph(
        entity_ids=["paper1"],
        include_relationships=True,
        max_hops=2
    )

    logger.info(f"Exported subgraph with {len(subgraph['entities'])} entities and {len(subgraph['relationships'])} relationships")

    # Save to file (for demonstration)
    with open("ipfs_paper_subgraph.json", "w") as f:
        json.dump(subgraph, f, indent=2)

    logger.info("Exported subgraph to ipfs_paper_subgraph.json")

    # Create a new graph instance to demonstrate import
    # In a real scenario, this might be on a different machine
    new_graph = IPLDGraphDB(
        ipfs_client=graph_db.ipfs,
        base_path=os.path.join(os.path.dirname(graph_db.base_path), "imported_graph")
    )

    # Import the subgraph
    import_result = new_graph.import_subgraph(subgraph, merge_strategy="update")

    logger.info("\nImported subgraph to new graph instance:")
    logger.info(f"  - Entities added: {import_result['entities_added']}")
    logger.info(f"  - Entities updated: {import_result['entities_updated']}")
    logger.info(f"  - Entities skipped: {import_result['entities_skipped']}")
    logger.info(f"  - Relationships added: {import_result['relationships_added']}")
    logger.info(f"  - Relationships skipped: {import_result['relationships_skipped']}")

    # Verify that we can query the imported graph
    papers = new_graph.query_entities(entity_type="research_paper")
    logger.info(f"\nResearch papers in imported graph: {len(papers)}")
    for paper in papers:
        logger.info(f"  - {paper['properties']['title']}")


def demonstrate_knowledge_cards(query):
    """Demonstrate the knowledge cards functionality."""
    logger.info("\n=== Knowledge Cards ===")

    # Get knowledge cards for a few entities
    cards = query.get_knowledge_cards(
        entity_ids=["paper1", "author_benet", "concept_content_addressing"],
        include_connected=True
    )

    logger.info(f"Generated knowledge cards for {len(cards)} entities")

    # Display a sample card
    if "paper1" in cards:
        paper_card = cards["paper1"]
        logger.info("\nKnowledge Card for IPFS Paper:")
        logger.info(f"  Title: {paper_card['properties']['title']}")
        logger.info(f"  Year: {paper_card['properties']['year']}")
        logger.info(f"  Authors: {paper_card['properties']['authors']}")

        if "outgoing_relationships" in paper_card:
            logger.info("\n  Discusses concepts:")
            for rel_type, targets in paper_card["outgoing_relationships"].items():
                if rel_type == "discusses":
                    for target in targets:
                        logger.info(f"    - {target['properties']['name']} (Centrality: {target.get('properties', {}).get('centrality', 'unknown')})")

        if "incoming_relationships" in paper_card:
            logger.info("\n  Cited by:")
            for rel_type, sources in paper_card["incoming_relationships"].items():
                if rel_type == "cites":
                    for source in sources:
                        logger.info(f"    - {source['properties']['title']} ({source['properties']['year']})")


def main():
    """Main function demonstrating the IPLD Knowledge Graph functionality."""
    parser = argparse.ArgumentParser(description="IPLD Knowledge Graph example")
    parser.add_argument("--skip-build", action="store_true", help="Skip building the example knowledge graph")
    args = parser.parse_args()

    # Set up the knowledge graph
    graph_db, query, graph_rag = setup_knowledge_graph()
    if graph_db is None:
        logger.error("Failed to set up knowledge graph components")
        return

    # Build the research knowledge graph (unless skipped)
    if not args.skip_build:
        build_research_knowledge_graph(graph_db)
    else:
        logger.info("Skipping knowledge graph building (--skip-build specified)")

    # Demonstrate various functionality
    demonstrate_basic_queries(graph_db, query)
    demonstrate_path_finding(graph_db)
    demonstrate_vector_search(graph_db, graph_rag)
    demonstrate_subgraph_export_import(graph_db)
    demonstrate_knowledge_cards(query)

    logger.info("\nKnowledge Graph example completed successfully!")


if __name__ == "__main__":
    main()
