import os
import logging
import threading
from pathlib import Path
from typing import List, Dict, Any
from neo4j import GraphDatabase
from config import OBSIDIAN_VAULT_DIR

logger = logging.getLogger(__name__)


class Neo4jGraphRAG:
    """
    Agentic Graph Retrieval system that uses Pinecone to find entry nodes
    and Neo4j to traverse relationships and pull context.

    Optimizations vs original:
    - Pinecone vectorstore is created once and cached (_vectorstore), not rebuilt on every query.
    - Neo4j driver is kept alive for the object lifetime; connection checked lazily.
    - A threading.Lock guards the one-time vectorstore initialization to be safe under Streamlit's
      multi-thread execution model.
    """

    def __init__(self):
        self.vault_dir = Path(OBSIDIAN_VAULT_DIR)
        self.uri = os.getenv("NEO4J_URI")
        self.user = os.getenv("NEO4J_USERNAME")
        self.password = os.getenv("NEO4J_PASSWORD")
        self.driver = None
        self._vectorstore = None
        self._vs_lock = threading.Lock()
        self._connect()

    def _connect(self):
        if self.uri and self.user and self.password:
            try:
                self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
                self.driver.verify_connectivity()
            except Exception as e:
                logger.error("Failed to connect Neo4j in Neo4jGraphRAG: %s", e)
                self.driver = None

    def close(self):
        if self.driver:
            self.driver.close()
            self.driver = None

    def _get_vectorstore(self):
        """
        Returns a cached Pinecone vectorstore, initializing it exactly once.
        Thread-safe via a lock.
        """
        if self._vectorstore is not None:
            return self._vectorstore

        with self._vs_lock:
            # Double-checked locking pattern
            if self._vectorstore is not None:
                return self._vectorstore
            try:
                from langchain_google_genai import GoogleGenerativeAIEmbeddings
                from langchain_pinecone import PineconeVectorStore
                from pinecone import Pinecone as PineconeClient
                from config import EMBEDDING_MODEL, PINECONE_INDEX_NAME, PINECONE_API_KEY

                google_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_API_KEY_1")
                if not google_key or not PINECONE_INDEX_NAME:
                    return None

                embeddings = GoogleGenerativeAIEmbeddings(model=EMBEDDING_MODEL, google_api_key=google_key)
                pc = PineconeClient(api_key=PINECONE_API_KEY)
                # Verify index exists before storing
                pc.Index(PINECONE_INDEX_NAME)

                self._vectorstore = PineconeVectorStore(
                    index_name=PINECONE_INDEX_NAME,
                    embedding=embeddings,
                    namespace="obsidian",
                    pinecone_api_key=PINECONE_API_KEY
                )
                logger.info("Neo4jGraphRAG: Pinecone vectorstore initialized and cached.")
            except Exception as e:
                logger.error("Failed to initialize Obsidian concept Pinecone index: %s", e)
                return None

        return self._vectorstore

    def invalidate_vectorstore(self):
        """Call this after re-indexing the vault to force a fresh vectorstore on next query."""
        with self._vs_lock:
            self._vectorstore = None

    def semantic_graph_search(self, question: str, top_k: int = 2) -> Dict[str, Any]:
        """
        Execute GraphRAG retrieval using cached Pinecone for entry nodes, and Neo4j for neighbor traversal.
        """
        if not self.driver:
            return {
                "context": "Database connection to Neo4j is offline. Please check your .env credentials.",
                "citations": []
            }

        # 1. Cached Pinecone lookup for entry nodes
        vectorstore = self._get_vectorstore()
        entry_nodes = []
        if vectorstore:
            try:
                results_with_scores = vectorstore.similarity_search_with_score(question, k=10)
                seen: set[str] = set()
                for doc, score in results_with_scores:
                    # Keep the correct threshold for Pinecone cosine similarity
                    if score >= 0.70:
                        note = doc.metadata.get("note")
                        if note and note not in seen:
                            seen.add(note)
                            entry_nodes.append(note)
                            if len(entry_nodes) >= top_k:
                                break
            except Exception as e:
                logger.error("Pinecone similarity search failed: %s", e)

        if not entry_nodes:
            return {"context": "No relevant entry nodes found in the knowledge base.", "citations": []}

        logger.info("Pinecone isolated entry nodes: %s", entry_nodes)

        # 2. Neo4j traversal — single session reused across all entry nodes
        primary_contents = []
        citations = []
        neighbor_definitions = []
        seen_neighbors: set[str] = set()

        # Cypher: fetch all neighbors for all entry nodes in ONE query
        NEIGHBOR_LIMIT = 5

        try:
            with self.driver.session() as session:
                # Batch query: fetch neighbors for all entry nodes at once
                batch_query = '''
                UNWIND $note_names AS note_name
                MATCH (n:Note {name: note_name})
                OPTIONAL MATCH (n)-[r_out]->(out:Note)
                OPTIONAL MATCH (in_node:Note)-[r_in]->(n)
                RETURN
                    note_name,
                    collect(DISTINCT {name: out.name, summary: out.summary, dir: "outgoing",  type: type(r_out)}) AS outgoing,
                    collect(DISTINCT {name: in_node.name, summary: in_node.summary, dir: "incoming", type: type(r_in)}) AS incoming
                '''
                results = session.run(batch_query, note_names=entry_nodes)

                for record in results:
                    note_name = record["note_name"]

                    # Read note content from disk
                    file_path = self.vault_dir / note_name
                    if file_path.exists():
                        try:
                            content = file_path.read_text(encoding="utf-8")
                            primary_contents.append(
                                f"--- START NOTE: {note_name} ---\n{content}\n--- END NOTE: {note_name} ---"
                            )
                            citations.append({"source": f"Obsidian: {note_name}", "page": "Entry Node"})
                        except Exception as e:
                            logger.error("Could not read note %s: %s", note_name, e)

                    neighbors = record["outgoing"] + record["incoming"]
                    for nb in neighbors:
                        if not nb.get("name"):
                            continue
                        if nb["name"] in entry_nodes or nb["name"] in seen_neighbors:
                            continue
                        seen_neighbors.add(nb["name"])

                        rel_type = nb.get("type", "LINKS_TO")
                        direction = (
                            f"connects out via {rel_type}" if nb["dir"] == "outgoing"
                            else f"connects in via {rel_type}"
                        )
                        display_name = nb["name"][:-3] if nb["name"].endswith(".md") else nb["name"]
                        summary = nb.get("summary") or "No summary available."

                        neighbor_definitions.append(f"- [[{display_name}]] ({direction}): {summary}")
                        citations.append({
                            "source": f"Obsidian Link: {nb['name']}",
                            "page": f"Neighbor ({rel_type})"
                        })

                        if len(seen_neighbors) >= NEIGHBOR_LIMIT:
                            break

        except Exception as e:
            logger.error("Neo4j batch Cypher query failed: %s", e)

        # 3. Synthesize context
        context_parts = []
        if primary_contents:
            context_parts.append("### Primary Notes from your Personal Vault:")
            context_parts.extend(primary_contents)
        if neighbor_definitions:
            context_parts.append("\n### Related Connected Concepts in your Knowledge Graph:")
            context_parts.append("\n".join(neighbor_definitions))

        return {
            "context": "\n\n".join(context_parts),
            "citations": citations
        }
