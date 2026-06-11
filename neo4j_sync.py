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
            self.driver = None

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

        # Build per-note summary strings
        explanations: dict[str, list[str]] = {}
        for c in concepts:
            note = c.get("source_note")
            if note:
                explanations.setdefault(note, []).append(
                    f"{c.get('concept_name')}: {c.get('explanation')}"
                )
        note_summaries = {k: "; ".join(v) for k, v in explanations.items()}

        valid_files = set(files.keys())
        nodes_data = [
            {"name": name, "summary": note_summaries.get(name, "")}
            for name in valid_files
        ]

        # Group links by sanitized relationship type up front (Python-side, zero Cypher overhead)
        links_by_type: dict[str, list[dict]] = {}
        for lnk in links:
            src, dst = lnk.get("from_note"), lnk.get("to_note")
            if src not in valid_files or dst not in valid_files:
                continue
            rel = str(lnk.get("relationship", "LINKS_TO")).upper().replace(" ", "_").replace("-", "_") or "LINKS_TO"
            links_by_type.setdefault(rel, []).append({"from": src, "to": dst})

        try:
            with self.driver.session() as session:
                # ----------------------------------------------------------------
                # 1. Clear existing graph
                # ----------------------------------------------------------------
                session.run("MATCH (n:Note) DETACH DELETE n")

                # ----------------------------------------------------------------
                # 2. Bulk-upsert nodes in a single UNWIND statement
                # ----------------------------------------------------------------
                if nodes_data:
                    session.run(
                        """
                        UNWIND $nodes AS n
                        MERGE (note:Note {name: n.name})
                        SET note.summary = n.summary
                        """,
                        nodes=nodes_data,
                    )
                    logger.info("Upserted %s Note nodes.", len(nodes_data))

                # ----------------------------------------------------------------
                # 3. Bulk-upsert relationships per type
                #    Each type requires its own Cypher statement (dynamic rel types),
                #    but within a type we still do a single UNWIND batch.
                # ----------------------------------------------------------------
                total_links = 0
                for rel_type, type_links in links_by_type.items():
                    session.run(
                        f"""
                        UNWIND $links AS l
                        MATCH (from:Note {{name: l.from}})
                        MATCH (to:Note   {{name: l.to}})
                        MERGE (from)-[:{rel_type}]->(to)
                        """,
                        links=type_links,
                    )
                    total_links += len(type_links)

            logger.info(
                "Successfully synced %s notes and %s links to Neo4j.",
                len(nodes_data), total_links
            )
            return True

        except Exception as e:
            logger.error("Error writing to Neo4j: %s", e)
            return False
        finally:
            self.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    Neo4jSync().sync()
