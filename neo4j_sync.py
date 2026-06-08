import os
import json
import logging
from pathlib import Path
from dotenv import load_dotenv
from neo4j import GraphDatabase
from config import OBSIDIAN_CACHE_FILE

load_dotenv()
logger = logging.getLogger(__name__)

class Neo4jSync:
    def __init__(self):
        self.uri = os.getenv("NEO4J_URI")
        self.user = os.getenv("NEO4J_USERNAME")
        self.password = os.getenv("NEO4J_PASSWORD")
        self.cache_file = Path(OBSIDIAN_CACHE_FILE)
        self.driver = None

    def connect(self) -> bool:
        if not self.uri or not self.user or not self.password:
            logger.warning("Neo4j credentials missing from .env. Sync aborted.")
            return False
        try:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
            self.driver.verify_connectivity()
            return True
        except Exception as e:
            logger.error("Failed to connect to Neo4j: %s", e)
            return False

    def close(self):
        if self.driver:
            self.driver.close()

    def sync(self) -> bool:
        if not self.connect():
            return False
            
        if not self.cache_file.exists():
            logger.warning("Cache file %s not found. Run Obsidian Linker first.", self.cache_file)
            return False
            
        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.error("Failed to read cache file: %s", e)
            return False

        files = data.get("files", {})
        links = data.get("links", [])
        concepts = data.get("concepts", [])

        # Build concepts map for node summaries
        explanations = {}
        for c in concepts:
            note = c.get("source_note")
            if note:
                if note not in explanations:
                    explanations[note] = []
                explanations[note].append(f"{c.get('concept_name')}: {c.get('explanation')}")
        
        note_summaries = {k: "; ".join(v) for k, v in explanations.items()}

        try:
            with self.driver.session() as session:
                # 1. Clear existing graph to ensure exact parity with current vault state
                # Note: In a massive vault, DETACH DELETE might be slow, but for Obsidian it's fast enough.
                session.run("MATCH (n:Note) DETACH DELETE n")

                # 2. Insert Nodes
                nodes_data = [{"name": name, "summary": note_summaries.get(name, "")} for name in files.keys()]
                if nodes_data:
                    session.run('''
                        UNWIND $nodes AS n
                        MERGE (note:Note {name: n.name})
                        SET note.summary = n.summary
                    ''', nodes=nodes_data)

                # 3. Insert Links dynamically based on relationship type
                valid_files = set(files.keys())
                
                # Group links by relationship type
                links_by_type = {}
                for l in links:
                    if l.get("from_note") in valid_files and l.get("to_note") in valid_files:
                        # Sanitize relationship type (e.g., uses -> USES)
                        rel_type = str(l.get("relationship", "LINKS_TO")).upper().replace(" ", "_").replace("-", "_")
                        # Fallback if empty
                        if not rel_type:
                            rel_type = "LINKS_TO"
                            
                        if rel_type not in links_by_type:
                            links_by_type[rel_type] = []
                            
                        links_by_type[rel_type].append({"from": l["from_note"], "to": l["to_note"]})
                
                total_links_inserted = 0
                for rel_type, type_links in links_by_type.items():
                    query = f'''
                        UNWIND $links AS l
                        MATCH (from:Note {{name: l.from}})
                        MATCH (to:Note {{name: l.to}})
                        MERGE (from)-[:{rel_type}]->(to)
                    '''
                    session.run(query, links=type_links)
                    total_links_inserted += len(type_links)
                
            logger.info("Successfully synced %s notes and %s links to Neo4j.", len(nodes_data), total_links_inserted)
            success = True
        except Exception as e:
            logger.error("Error writing to Neo4j: %s", e)
            success = False
        finally:
            self.close()
            
        return success

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sync = Neo4jSync()
    sync.sync()
