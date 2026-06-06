import os
import re
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Set
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from config import OBSIDIAN_CACHE_FILE, OBSIDIAN_VAULT_DIR

logger = logging.getLogger(__name__)

class MatchedNotes(BaseModel):
    notes: List[str] = Field(
        description="List of exact note titles from the available options that are relevant to the query."
    )

class VectorlessGraphRAG:
    def __init__(self):
        self.vault_dir = Path(OBSIDIAN_VAULT_DIR)
        self.cache_file = Path(OBSIDIAN_CACHE_FILE)
        self.metadata_cache: Dict[str, Any] = {}
        self.available_notes: List[str] = []
        self.last_cache_mtime = 0.0
        self._load_cache()

    def _load_cache(self) -> None:
        """Load the Obsidian Linker cache file if it has been updated."""
        if not self.cache_file.exists():
            logger.warning("Obsidian linker cache file not found at: %s", self.cache_file)
            return
        
        try:
            mtime = self.cache_file.stat().st_mtime
            if mtime <= self.last_cache_mtime:
                return # Cache is already up to date!
                
            with open(self.cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            self.metadata_cache = data
            self.last_cache_mtime = mtime
            
            # Populate available notes from the cache keys
            if "files" in data:
                self.available_notes = list(data["files"].keys())
                
            logger.info("Loaded cache successfully. Found %s notes in index (mtime: %s).", len(self.available_notes), mtime)
        except Exception as e:
            logger.error("Failed to load Obsidian linker cache: %s", e)

    def _load_faiss_index(self):
        """Lazily load the Obsidian concept FAISS vector index."""
        faiss_path = self.vault_dir / ".linker_faiss_index"
        if not faiss_path.exists():
            logger.warning("Obsidian concept FAISS index not found at: %s", faiss_path)
            return None
        try:
            from langchain_google_genai import GoogleGenerativeAIEmbeddings
            from langchain_community.vectorstores import FAISS
            from config import EMBEDDING_MODEL
            
            google_key = os.getenv("GOOGLE_API_KEY")
            if not google_key:
                google_key = os.getenv("GOOGLE_API_KEY_1")
            if not google_key:
                logger.error("GOOGLE_API_KEY not found in environment.")
                return None
                
            embeddings = GoogleGenerativeAIEmbeddings(model=EMBEDDING_MODEL, google_api_key=google_key)
            vectorstore = FAISS.load_local(
                str(faiss_path),
                embeddings,
                allow_dangerous_deserialization=True
            )
            return vectorstore
        except Exception as e:
            logger.error("Failed to load Obsidian concept FAISS index: %s", e)
            return None

    def select_relevant_notes(self, question: str, limit: int = 3) -> List[str]:
        """Use LLM structured output to select relevant note names matching the query, pre-filtered using FAISS vector search."""
        self._load_cache()
        if not self.available_notes:
            return []

        try:
            # 1. Pre-filter candidate notes using FAISS index similarity search
            vectorstore = self._load_faiss_index()
            candidate_notes = []
            
            if vectorstore:
                logger.info("Running similarity search on Obsidian FAISS index for: '%s'", question)
                # Search for top 12 relevant concepts with scores
                results_with_scores = vectorstore.similarity_search_with_score(question, k=12)
                seen_candidates = set()
                for doc, score in results_with_scores:
                    logger.info("Note concept: %s, Score (L2 Distance): %.4f", doc.metadata.get('note'), score)
                    if score <= 0.85:
                        note = doc.metadata.get("note")
                        if note and note in self.available_notes and note not in seen_candidates:
                            seen_candidates.add(note)
                            candidate_notes.append(note)
                logger.info("Vector pre-filtering found %s candidate notes: %s", len(candidate_notes), candidate_notes)
            
            # 2. Fallback to keyword matching if FAISS is missing/empty, or use a small default subset
            if not candidate_notes:
                keywords = [w.lower() for w in re.findall(r'\w+', question) if len(w) > 3]
                seen_candidates = set()
                for note in sorted(self.available_notes):
                    note_lower = note.lower()
                    if any(kw in note_lower for kw in keywords):
                        seen_candidates.add(note)
                        candidate_notes.append(note)
                
                # If still empty, use top 10 notes as broad fallback
                if not candidate_notes:
                    candidate_notes = sorted(self.available_notes)[:10]
                logger.info("Selected %s fallback candidates: %s", len(candidate_notes), candidate_notes)

            # 3. Call the LLM to verify and select from the small candidate list (O(1) prompt size!)
            api_key = os.getenv("GROQ_API_KEY")
            if not api_key:
                # Support rotation keys
                for key_env in ["GROQ_API_KEY_1", "GROQ_API_KEY_2", "GROQ_API_KEY_3"]:
                    if os.getenv(key_env):
                        api_key = os.getenv(key_env)
                        break
            if not api_key:
                logger.error("GROQ_API_KEY not found in environment.")
                return []

            # We use a fast, cost-effective 8B model for selection
            llm = ChatGroq(groq_api_key=api_key, model="llama-3.1-8b-instant", max_tokens=512)
            structured_llm = llm.with_structured_output(MatchedNotes)
            
            # Format candidate notes along with their concept summaries/explanations
            note_explanations = self.get_note_explanations()
            notes_str = ""
            for note in sorted(candidate_notes):
                summary = note_explanations.get(note, "No concept summary available.")
                notes_str += f"- **{note}** (Summary: {summary})\n"
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", "You are an intelligent knowledge retrieval assistant. Your job is to select the most relevant study notes from a personal knowledge base to answer a user's question. Be extremely strict: do not select any notes unless they are directly relevant."),
                ("user", """User Question: {question}
 
Here is the list of candidate study notes in your knowledge base:
{notes_list}
 
CRITICAL RULES:
- **Strict Relevance Only**: Only select notes that contain actual, concrete factual content directly relevant to answering the user's question.
- **Empty List Fallback**: If NONE of the available notes are directly relevant, or if the question is specifically asking about an uploaded PDF, document, or paper that is not in the list above, you MUST return an empty list: [].
- **No Force-Matching**: Do not select notes just because they share a few broad technical keywords if they do not contain specific information to help answer the user's query.
- Do not invent note names. Select ONLY from the exact list provided above.
- Select at most {limit} notes.
- Return the selection as a structured object containing a 'notes' list.""")
            ])
            
            chain = prompt | structured_llm
            result = chain.invoke({"question": question, "notes_list": notes_str, "limit": limit})
            
            # Ensure we only keep valid notes that actually exist and strictly respect the limit
            matched = [note for note in result.notes if note in candidate_notes][:limit]
            logger.info("Selected relevant notes: %s", matched)
            return matched
        except Exception as e:
            logger.error("Failed to select relevant notes via LLM: %s", e)
            return []

    def get_note_explanations(self) -> Dict[str, str]:
        """Build a mapping of note names to their concept explanations from the cache."""
        explanations = {}
        if "concepts" in self.metadata_cache:
            for concept in self.metadata_cache["concepts"]:
                note_name = concept.get("source_note")
                explanation = concept.get("explanation", "")
                if note_name and explanation:
                    # Collect explanations per note
                    if note_name not in explanations:
                        explanations[note_name] = []
                    explanations[note_name].append(f"{concept.get('concept_name')}: {explanation}")
        
        return {k: "; ".join(v) for k, v in explanations.items()}

    def retrieve_context(self, question: str) -> Dict[str, Any]:
        """
        Execute GraphRAG retrieval:
        1. Select main notes.
        2. Walk graph links (outgoing & incoming) to fetch first-degree neighbors.
        3. Build combined semantic context.
        """
        self._load_cache()
        if not self.available_notes:
            return {"context": "", "citations": []}

        # 1. Select the top-level matching notes
        matched_notes = self.select_relevant_notes(question, limit=2)
        if not matched_notes:
            return {"context": "No relevant personal notes found in your Obsidian Vault.", "citations": []}

        primary_contents = []
        citations = []
        outgoing_links: Set[str] = set()
        incoming_links: Set[str] = set()

        note_explanations = self.get_note_explanations()

        # 2. Process primary notes
        for note_name in matched_notes:
            file_path = self.vault_dir / note_name
            if not file_path.exists():
                continue

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                # Extract outgoing wikilinks e.g., [[Note Name]] or [[Note Name|Label]]
                links = re.findall(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]', content)
                for link in links:
                    # Clean filename e.g. add extension if missing
                    cleaned_link = link.strip()
                    if not cleaned_link.endswith(".md"):
                        cleaned_link += ".md"
                    
                    if cleaned_link in self.available_notes and cleaned_link not in matched_notes:
                        outgoing_links.add(cleaned_link)

                primary_contents.append(f"--- START NOTE: {note_name} ---\n{content}\n--- END NOTE: {note_name} ---")
                citations.append({"source": f"Obsidian: {note_name}", "page": "Note Content"})

            except Exception as e:
                logger.error("Failed to read note %s: %s", note_name, e)

        # 3. Find incoming links (backlinks) from the cache
        # If any note in the vault links to our matched notes, it's an incoming link
        for note_name in matched_notes:
            for link in self.metadata_cache.get("links", []):
                from_note = link.get("from_note")
                to_note = link.get("to_note")
                if to_note == note_name and from_note and from_note not in matched_notes:
                    incoming_links.add(from_note)

        # Gather brief definitions of neighboring connected concepts
        neighbor_definitions = []
        all_neighbors = list(outgoing_links) + list(incoming_links)
        seen_neighbors = set()
        
        # Limit to top 5 unique neighbors to prevent token spam
        for neighbor in all_neighbors:
            if neighbor in seen_neighbors:
                continue
            seen_neighbors.add(neighbor)
            if len(seen_neighbors) > 5:
                break
                
            exp = note_explanations.get(neighbor)
            if exp:
                display_name = neighbor[:-3] if neighbor.lower().endswith(".md") else neighbor
                direction = "links to this" if neighbor in incoming_links else "linked from this"
                neighbor_definitions.append(f"- [[{display_name}]] ({direction}): {exp}")
                citations.append({"source": f"Obsidian Link: {neighbor}", "page": f"Graph Neighbor ({direction})"})

        # 4. Synthesize final prompt context
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
