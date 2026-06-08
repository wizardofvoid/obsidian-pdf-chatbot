import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Set
from neo4j import GraphDatabase
from config import OBSIDIAN_VAULT_DIR

logger = logging.getLogger(__name__)

class Neo4jGraphRAG:
    """
    Agentic Graph Retrieval system that uses Pinecone to find entry nodes
    and Neo4j to traverse relationships and pull context.
    """
    def __init__(self):
        self.vault_dir = Path(OBSIDIAN_VAULT_DIR)
        self.uri = os.getenv("NEO4J_URI")
        self.user = os.getenv("NEO4J_USERNAME")
        self.password = os.getenv("NEO4J_PASSWORD")
        self.driver = None
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

    def _load_pinecone_index(self):
        """Lazily load the Obsidian concept Pinecone vector index."""
        try:
            from langchain_google_genai import GoogleGenerativeAIEmbeddings
            from langchain_community.vectorstores import Pinecone
            from pinecone import Pinecone as PineconeClient
            from config import EMBEDDING_MODEL, PINECONE_INDEX_NAME
            
            google_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_API_KEY_1")
            if not google_key or not PINECONE_INDEX_NAME:
                return None
            
            from config import PINECONE_API_KEY
            
            embeddings = GoogleGenerativeAIEmbeddings(model=EMBEDDING_MODEL, google_api_key=google_key)
            pc = PineconeClient(api_key=PINECONE_API_KEY)
            index = pc.Index(PINECONE_INDEX_NAME)
            
            vectorstore = Pinecone(
                index=index,
                embedding=embeddings,
                namespace="obsidian",
                text_key="text"
            )
            return vectorstore
        except Exception as e:
            logger.error("Failed to load Obsidian concept Pinecone index: %s", e)
            return None

    def semantic_graph_search(self, question: str, top_k: int = 2) -> Dict[str, Any]:
        """
        Execute GraphRAG retrieval using Pinecone for entry nodes, and Neo4j for neighbor traversal.
        """
        if not self.driver:
            return {"context": "Database connection to Neo4j is offline. Please check your .env credentials.", "citations": []}

        # 1. Pinecone Pre-filtering to find Entry Nodes
        vectorstore = self._load_pinecone_index()
        entry_nodes = []
        if vectorstore:
            results_with_scores = vectorstore.similarity_search_with_score(question, k=10)
            seen = set()
            for doc, score in results_with_scores:
                if score <= 0.85:
                    note = doc.metadata.get("note")
                    if note and note not in seen:
                        seen.add(note)
                        entry_nodes.append(note)
                        if len(entry_nodes) >= top_k:
                            break
        
        if not entry_nodes:
            return {"context": "No relevant entry nodes found in the knowledge base.", "citations": []}

        logger.info("Pinecone isolated entry nodes: %s", entry_nodes)

        # 2. Neo4j Traversal for 1st-degree neighbors
        primary_contents = []
        citations = []
        neighbor_definitions = []
        seen_neighbors = set()

        try:
            with self.driver.session() as session:
                for note_name in entry_nodes:
                    # Read the primary note content from disk
                    file_path = self.vault_dir / note_name
                    if file_path.exists():
                        try:
                            with open(file_path, "r", encoding="utf-8") as f:
                                content = f.read()
                            primary_contents.append(f"--- START NOTE: {note_name} ---\n{content}\n--- END NOTE: {note_name} ---")
                            citations.append({"source": f"Obsidian: {note_name}", "page": "Entry Node"})
                        except Exception as e:
                            logger.error("Could not read note %s: %s", note_name, e)

                    # Query Neo4j for outgoing and incoming links
                    query = '''
                    MATCH (n:Note {name: $note_name})
                    OPTIONAL MATCH (n)-[r_out]->(out:Note)
                    OPTIONAL MATCH (in:Note)-[r_in]->(n)
                    RETURN 
                        collect(DISTINCT {name: out.name, summary: out.summary, dir: "outgoing", type: type(r_out)}) AS outgoing,
                        collect(DISTINCT {name: in.name, summary: in.summary, dir: "incoming", type: type(r_in)}) AS incoming
                    '''
                    result = session.run(query, note_name=note_name)
                    record = result.single()
                    
                    if record:
                        neighbors = record["outgoing"] + record["incoming"]
                        for nb in neighbors:
                            if not nb.get("name") or nb["name"] in entry_nodes or nb["name"] in seen_neighbors:
                                continue
                            seen_neighbors.add(nb["name"])
                            
                            rel_type = nb.get("type", "LINKS_TO")
                            if nb["dir"] == "outgoing":
                                direction = f"connects out to this via {rel_type}"
                            else:
                                direction = f"is connected in from this via {rel_type}"
                                
                            display_name = nb["name"][:-3] if nb["name"].endswith(".md") else nb["name"]
                            summary = nb.get("summary") or "No summary available."
                            
                            neighbor_definitions.append(f"- [[{display_name}]] ({direction}): {summary}")
                            citations.append({"source": f"Obsidian Link: {nb['name']}", "page": f"Neighbor ({rel_type})"})
                            
                            if len(seen_neighbors) >= 5: # Limit neighbor bloat
                                break
        except Exception as e:
            logger.error("Neo4j Cypher query failed: %s", e)

        # 3. Synthesize final prompt context
        context_parts = []
        if primary_contents:
            context_parts.append("### Primary Notes from your Personal Vault:")
            context_parts.extend(primary_contents)

        if neighbor_definitions:
            context_parts.append("\n### Related Connected Concepts in your Knowledge Graph:")
            context_parts.append("\n".join(neighbor_definitions))

        full_context = "\n\n".join(context_parts)
        return {
            "context": full_context,
            "citations": citations
        }
