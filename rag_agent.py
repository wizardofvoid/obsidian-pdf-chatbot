import os
import logging
from typing import Any
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone as PineconeClient
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.output_parsers import StrOutputParser
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_groq import ChatGroq

import extract_text as et
import text_chunker as tc
from config import EMBEDDING_MODEL, LLM_MODEL, PINECONE_API_KEY, PINECONE_INDEX_NAME

load_dotenv()

@dataclass
class ChatResult:
    answer: str
    context_chunks: list[str] = field(default_factory=list)
    error: str | None = None

class RAGAgent:
    """Agentic RAG pipeline: retrieves from Neo4j Graph and Pinecone PDFs using autonomous tools."""

    def __init__(self):
        self._vectorstore: PineconeVectorStore | None = None
        self._agent_executor = None
        self._session_store: dict[str, InMemoryChatMessageHistory] = {}
        self._graph_rag = None
        self._current_key_idx = 1
        self._current_citations = []

    def _get_graph_rag(self):
        if self._graph_rag is None:
            from graph_rag import Neo4jGraphRAG
            self._graph_rag = Neo4jGraphRAG()
        return self._graph_rag

    @staticmethod
    def env_configured() -> bool:
        groq_ok = bool(os.getenv("GROQ_API_KEY")) or any("GROQ_API_KEY_" in k for k in os.environ)
        google_ok = bool(os.getenv("GOOGLE_API_KEY")) or any("GOOGLE_API_KEY_" in k for k in os.environ)
        neo4j_ok = bool(os.getenv("NEO4J_URI")) and bool(os.getenv("NEO4J_USERNAME"))
        return groq_ok and google_ok and neo4j_ok

    @staticmethod
    def missing_env_vars() -> list[str]:
        missing = []
        if not (bool(os.getenv("GROQ_API_KEY")) or any("GROQ_API_KEY_" in k for k in os.environ)):
            missing.append("GROQ_API_KEY")
        if not (bool(os.getenv("GOOGLE_API_KEY")) or any("GOOGLE_API_KEY_" in k for k in os.environ)):
            missing.append("GOOGLE_API_KEY")
        if not os.getenv("NEO4J_URI"):
            missing.append("NEO4J_URI")
        return missing

    @staticmethod
    def index_ready() -> bool:
        try:
            pc = PineconeClient(api_key=PINECONE_API_KEY)
            index = pc.Index(PINECONE_INDEX_NAME)
            stats = index.describe_index_stats()
            namespaces = stats.get('namespaces', {})
            return 'pdfs' in namespaces and namespaces['pdfs'].vector_count > 0
        except Exception:
            return False

    def _get_session_history(self, session_id: str) -> InMemoryChatMessageHistory:
        if session_id not in self._session_store:
            self._session_store[session_id] = InMemoryChatMessageHistory()
        return self._session_store[session_id]

    def _load_vectorstore(self) -> PineconeVectorStore:
        if self._vectorstore is None:
            google_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_API_KEY_1")
            embeddings = GoogleGenerativeAIEmbeddings(model=EMBEDDING_MODEL, google_api_key=google_key)
            pc = PineconeClient(api_key=PINECONE_API_KEY)
            index = pc.Index(PINECONE_INDEX_NAME)
            self._vectorstore = PineconeVectorStore(
                index_name=PINECONE_INDEX_NAME,
                embedding=embeddings,
                namespace="pdfs",
                pinecone_api_key=PINECONE_API_KEY
            )
        return self._vectorstore

    def _get_groq_key(self) -> str:
        key = os.getenv("GROQ_API_KEY")
        if key: return key
        k = os.getenv(f"GROQ_API_KEY_{self._current_key_idx}")
        if k: return k
        return os.getenv("GROQ_API_KEY_1")

    def rotate_groq_key(self) -> bool:
        old_idx = self._current_key_idx
        for offset in range(1, 10):
            next_idx = ((old_idx + offset - 1) % 9) + 1
            if os.getenv(f"GROQ_API_KEY_{next_idx}"):
                self._current_key_idx = next_idx
                self._agent_executor = None
                logger.info(f"Rotated key index: {old_idx} -> {self._current_key_idx}")
                return True
        return False

    def _load_agent(self) -> Any:
        if self._agent_executor is None:
            groq_key = self._get_groq_key()
            llm = ChatGroq(groq_api_key=groq_key, model=LLM_MODEL, temperature=0.0)
            
            from langchain_core.tools import tool
            
            @tool
            def search_pdf_materials(query: str) -> str:
                """Search uploaded PDF textbooks and study materials for factual knowledge."""
                if not self.index_ready():
                    return "No PDFs indexed."
                try:
                    vectorstore = self._load_vectorstore()
                    docs = vectorstore.similarity_search_with_score(query, k=5)
                    chunks = []
                    for doc, score in docs:
                        if score >= 0.70:
                            chunks.append(doc.page_content)
                            self._current_citations.append({"source": doc.metadata.get("source"), "page": doc.metadata.get("page")})
                    if not chunks:
                        # Fallback for generic/meta queries: fetch page 1 and page 2 of all indexed PDFs as context
                        status = self.get_index_status()
                        indexed_files = status.get("indexed_files", [])
                        if indexed_files:
                            fallback_chunks = []
                            for filename in indexed_files:
                                for page_num in [1, 2]:
                                    try:
                                        res_docs = vectorstore.similarity_search(
                                            query="title overview introduction index",
                                            k=1,
                                            filter={"source": filename, "page": page_num}
                                        )
                                        if res_docs:
                                            fallback_chunks.append(f"--- File: {filename} (Page {page_num}) ---\n{res_docs[0].page_content}")
                                            self._current_citations.append({"source": filename, "page": page_num})
                                    except: pass
                            if fallback_chunks:
                                return "\n\n".join(fallback_chunks)
                        return "No relevant PDF materials found."
                    return "\n\n".join(chunks)
                except Exception as e:
                    return f"Error searching PDFs: {e}"

            @tool
            def search_obsidian_graph(query: str) -> str:
                """Search the personal Obsidian graph database for connected concepts and notes."""
                graph_rag = self._get_graph_rag()
                res = graph_rag.semantic_graph_search(query)
                if res.get("citations"):
                    self._current_citations.extend(res["citations"])
                return res["context"]
                
            @tool
            def scan_obsidian_tasks() -> str:
                """Scan the entire Obsidian vault for pending or completed tasks (checkboxes - [ ] or - [x])."""
                from config import OBSIDIAN_VAULT_DIR
                vault_path = Path(OBSIDIAN_VAULT_DIR)
                checkbox_notes = []
                if vault_path.exists():
                    for note_file in vault_path.glob("*.md"):
                        try:
                            content = note_file.read_text(encoding="utf-8")
                            if "- [ ]" in content or "- [x]" in content:
                                checkbox_notes.append(f"--- {note_file.name} ---\n{content}")
                                self._current_citations.append({"source": f"Obsidian: {note_file.name}", "page": "Task Note"})
                        except: pass
                if checkbox_notes:
                    return "\n".join(checkbox_notes)
                return "No tasks found."
                
            @tool
            def list_obsidian_notes() -> str:
                """List all available markdown notes in the Obsidian vault."""
                from config import OBSIDIAN_VAULT_DIR
                vault_path = Path(OBSIDIAN_VAULT_DIR)
                if not vault_path.exists():
                    return "Vault directory not found."
                notes = [f.name for f in vault_path.glob("*.md")]
                if notes:
                    return "Available notes: \n" + "\n".join(notes)
                return "No notes found in the vault."
                
            @tool
            def read_obsidian_note(note_title: str) -> str:
                """Read the exact, raw markdown content of a specific Obsidian note. Provide the note title (with or without .md)."""
                from config import OBSIDIAN_VAULT_DIR
                vault_path = Path(OBSIDIAN_VAULT_DIR)
                if not note_title.lower().endswith(".md"):
                    note_title += ".md"
                
                note_file = vault_path / note_title
                if not note_file.exists():
                    # Try case-insensitive search
                    for f in vault_path.glob("*.md"):
                        if f.name.lower() == note_title.lower():
                            note_file = f
                            break
                            
                if note_file.exists():
                    try:
                        content = note_file.read_text(encoding="utf-8")
                        self._current_citations.append({"source": f"Obsidian: {note_file.name}", "page": "Raw Note"})
                        return content
                    except Exception as e:
                        return f"Error reading note: {e}"
                return f"Note '{note_title}' not found in the vault."
                
            @tool
            def list_indexed_pdfs() -> str:
                """List the filenames of all PDF files that are currently uploaded and indexed in the system."""
                status = self.get_index_status()
                indexed = status.get("indexed_files", [])
                if not indexed:
                    return "No PDFs are currently indexed."
                return "Indexed PDF Files:\n" + "\n".join(f"- {name}" for name in indexed)
                
            from langgraph.prebuilt import create_react_agent
            system_message = (
                "You are an expert personal study assistant. You have access to tools to search the user's Obsidian notes, PDF materials, and tasks.\n"
                "Use the search tools when you need to retrieve factual information from study materials or notes to answer the user's questions.\n"
                "If the user's query can be answered using general knowledge or does not require searching, respond directly."
            )
            
            self._agent_executor = create_react_agent(llm, tools=[search_pdf_materials, search_obsidian_graph, scan_obsidian_tasks, list_obsidian_notes, read_obsidian_note, list_indexed_pdfs], prompt=system_message)
            
        return self._agent_executor

    def reload(self) -> None:
        self._vectorstore = None
        self._agent_executor = None
        self._graph_rag = None

    def run_ingestion(self, skip_ocr: bool = False) -> bool:
        et.main(skip_ocr=skip_ocr)
        ok = tc.main()
        if ok:
            try:
                self.extract_pdf_knowledge_to_obsidian()
            except Exception as e:
                logger.error(f"Failed in PDF knowledge extraction: {e}")
            self.reload()
        return ok

    def extract_pdf_knowledge_to_obsidian(self) -> None:
        import json
        import re
        from pathlib import Path
        from config import OBSIDIAN_VAULT_DIR, INPUT_PDF_DIR, OUTPUT_DIR
        
        status = self.get_index_status()
        indexed_files = status.get("indexed_files", [])
        if not indexed_files:
            logger.info("No indexed files found. Skipping PDF knowledge extraction.")
            return

        # Load processed list to prevent duplicate LLM calls
        processed_file = Path(INPUT_PDF_DIR) / ".processed_pdfs.json"
        processed = set()
        if processed_file.exists():
            try:
                processed = set(json.loads(processed_file.read_text()))
            except: pass

        new_notes_created = False
        vault_path = Path(OBSIDIAN_VAULT_DIR)
        cache_dir = Path(OUTPUT_DIR) / "cache"

        for pdf_name in indexed_files:
            if pdf_name in processed:
                continue
            
            logger.info(f"Extracting key concepts from {pdf_name} to generate Obsidian notes...")
            # Locate cached text file
            txt_file = cache_dir / f"{pdf_name}_ocr_False.txt"
            if not txt_file.exists():
                txt_file = cache_dir / f"{pdf_name}_ocr_True.txt"
            
            if not txt_file.exists():
                logger.warning(f"No cached text file found for {pdf_name}, skipping concept generation.")
                continue

            try:
                # Read the first 25,000 characters to extract core concepts from intro/syllabus/outcomes
                full_text = txt_file.read_text(encoding="utf-8")
                sample_text = full_text[:25000]

                # Initialize LLM
                api_key = self._get_groq_key()
                llm = ChatGroq(groq_api_key=api_key, model="llama-3.1-8b-instant", temperature=0.0)
                
                # Define system message
                system_msg = (
                    "You are an expert academic curriculum analyzer. Your task is to analyze the introductory text "
                    "and syllabus of a study material PDF, identify the core concepts/topics, and generate structured "
                    "atomic Markdown study notes for each key concept that is not already present.\n\n"
                    "Return the output as a valid JSON object with a key 'notes' containing a list of objects. "
                    "Each object in the 'notes' list MUST have:\n"
                    "1. 'title': A concise 2-4 word concept name (e.g. 'Cloud Service Models').\n"
                    "2. 'tags': A list of tags (e.g. ['#cloud', '#architecture']).\n"
                    "3. 'content': A detailed study note in Markdown format describing this concept. Include YAML frontmatter at the top of the content with title, tags, and summary.\n\n"
                    "Example output format:\n"
                    "{\n"
                    "  \"notes\": [\n"
                    "    {\n"
                    "      \"title\": \"Cloud Service Models\",\n"
                    "      \"tags\": [\"#cloud\", \"#architecture\"],\n"
                    "      \"content\": \"---\\ntitle: Cloud Service Models\\ntags: [#cloud, #architecture]\\nsummary: Explanation of IaaS, PaaS, and SaaS.\\n---\\n\\n# Cloud Service Models...\"\n"
                    "    }\n"
                    "  ]\n"
                    "}"
                )
                
                from langchain_core.messages import SystemMessage, HumanMessage
                messages = [
                    SystemMessage(content=system_msg),
                    HumanMessage(content=f"Here is the introductory text of the study material PDF:\n\n{sample_text}")
                ]
                
                # Request JSON output
                res = llm.invoke(messages)
                content = res.content.strip()
                
                # Clean JSON codeblock wrapper if present
                if content.startswith("```json"):
                    content = content[7:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()
                
                data = json.loads(content)
                notes_list = data.get("notes", [])
                
                for note_data in notes_list:
                    title = note_data.get("title", "").strip()
                    note_content = note_data.get("content", "").strip()
                    if not title or not note_content:
                        continue
                    
                    # Clean title for filename
                    clean_title = re.sub(r'[\\/*?:"<>|]', "", title).strip()
                    if not clean_title:
                        continue
                    
                    note_file = vault_path / f"{clean_title}.md"
                    if not note_file.exists():
                        note_file.write_text(note_content, encoding="utf-8")
                        logger.info(f"Auto-created note: {note_file.name}")
                        new_notes_created = True
                    else:
                        logger.info(f"Note '{clean_title}' already exists. Skipping.")
                
                processed.add(pdf_name)
            except Exception as ex:
                logger.error(f"Failed to generate concepts for {pdf_name}: {ex}")

        # Save processed files
        try:
            processed_file.write_text(json.dumps(list(processed)), encoding="utf-8")
        except: pass

        # If any new notes were written, run Obsidian linker and Neo4j sync to update the graph database
        if new_notes_created:
            logger.info("New notes created. Running Obsidian Linker and Neo4j Graph Database Sync...")
            from linker_trigger import run_obsidian_linker_sync
            import subprocess
            if run_obsidian_linker_sync():
                subprocess.run(["python", "neo4j_sync.py"], check=False)

    def clear_session(self, session_id: str) -> None:
        self._session_store.pop(session_id, None)

    def ask(self, question: str, session_id: str = "default_session", mode: str = "pdf", chat_history: list = None) -> ChatResult:
        self._current_citations = []
        try:
            from langchain_core.messages import HumanMessage, AIMessage
            formatted_messages = []
            if chat_history:
                for msg in chat_history:
                    if msg["role"] == "user":
                        formatted_messages.append(HumanMessage(content=msg["content"]))
                    elif msg["role"] == "assistant":
                        formatted_messages.append(AIMessage(content=msg["content"]))
            formatted_messages.append(HumanMessage(content=question))

            max_retries = 3
            for attempt in range(max_retries):
                try:
                    agent = self._load_agent()
                    res = agent.invoke({"messages": formatted_messages})
                    final_answer = res["messages"][-1].content
                    return ChatResult(answer=final_answer, context_chunks=[])
                except Exception as e:
                    err_str = str(e)
                    if ("429" in err_str or "rate_limit" in err_str.lower()) and attempt < max_retries - 1:
                        if self.rotate_groq_key():
                            continue
                    if ("failed to call" in err_str.lower() or "failed_generation" in err_str.lower()) and attempt < max_retries - 1:
                        logger.warning(f"Groq tool parsing failed on attempt {attempt+1}/{max_retries}: {err_str}. Retrying...")
                        continue
                    raise e
        except Exception as e:
            return ChatResult(answer="", error=str(e))

    def ask_stream(self, question: str, session_id: str = "default_session", citations: list = None, mode: str = "pdf", chat_history: list = None):
        self._current_citations = []
        try:
            from langchain_core.messages import HumanMessage, AIMessage
            formatted_messages = []
            if chat_history:
                for msg in chat_history:
                    if msg["role"] == "user":
                        formatted_messages.append(HumanMessage(content=msg["content"]))
                    elif msg["role"] == "assistant":
                        formatted_messages.append(AIMessage(content=msg["content"]))
            formatted_messages.append(HumanMessage(content=question))

            max_retries = 3
            for attempt in range(max_retries):
                try:
                    agent = self._load_agent()
                    stream = agent.stream({"messages": formatted_messages}, stream_mode="messages")

                    for event in stream:
                        msg, metadata = event
                        if msg.__class__.__name__ == "AIMessageChunk":
                            if msg.content and not getattr(msg, 'tool_calls', None) and not getattr(msg, 'tool_call_chunks', None):
                                yield msg.content

                                
                    if citations is not None and self._current_citations:
                        # De-duplicate citations safely
                        seen = set()
                        for c in self._current_citations:
                            key = f"{c.get('source')}-{c.get('page')}"
                            if key not in seen:
                                seen.add(key)
                                citations.append(c)
                    return
                except Exception as e:
                    err_str = str(e)
                    if ("429" in err_str or "rate_limit" in err_str.lower()) and attempt < max_retries - 1:
                        if self.rotate_groq_key():
                            continue
                    if ("failed to call" in err_str.lower() or "failed_generation" in err_str.lower()) and attempt < max_retries - 1:
                        logger.warning(f"Groq tool parsing failed on attempt {attempt+1}/{max_retries}: {err_str}. Retrying...")
                        continue
                    yield f"[ERROR] {err_str}"
                    return
        except Exception as e:
            yield f"[ERROR] {str(e)}"

    def save_concepts_to_obsidian(self, question: str, answer: str, citations: list) -> dict:
        import re
        from pathlib import Path
        from config import OBSIDIAN_VAULT_DIR
        from linker_trigger import trigger_obsidian_linker
        
        try:
            api_key = self._get_groq_key()
            llm = ChatGroq(groq_api_key=api_key, model="llama-3.1-8b-instant", max_tokens=1500, temperature=0.0)
            from prompts import DISTILL_NOTE_PROMPT
            chain = DISTILL_NOTE_PROMPT | llm | StrOutputParser()
            note_content = chain.invoke({"question": question, "answer": answer, "citations": str(citations)})
            
            title_match = re.search(r'title:\s*["\']?(.*?)["\']?\n', note_content)
            title = title_match.group(1).strip() if title_match else "Takeaway - " + question[:20]
            clean_title = re.sub(r'[\\/*?:"<>|]', "", title).strip() or "Takeaway"
                
            vault_dir = Path(OBSIDIAN_VAULT_DIR)
            file_path = vault_dir / f"{clean_title}.md"
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(note_content)
                
            trigger_success = trigger_obsidian_linker()
            
            return {
                "success": True,
                "note_title": clean_title,
                "file_path": str(file_path),
                "linker_triggered": trigger_success
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def sync_obsidian_vault(self) -> dict:
        from linker_trigger import run_obsidian_linker_sync
        from git_sync import sync_obsidian_repo
        import subprocess
        try:
            success = run_obsidian_linker_sync()
            if success:
                # Pull the updated cache file and notes from GitHub first
                sync_obsidian_repo()
                # Trigger neo4j_sync.py to push the new cache to Neo4j
                subprocess.run(["python", "neo4j_sync.py"], check=False)
                self.reload()
                return {"success": True}
            else:
                return {"success": False, "error": "Re-indexing failed."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def transcribe_audio(self, audio_bytes: bytes, format: str = "webm", translate: bool = False) -> str:
        import audio_service
        api_key = self._get_groq_key()
        return audio_service.transcribe_audio(audio_bytes, api_key, format, translate)

    def get_index_status(self) -> dict:
        from config import INPUT_PDF_DIR
        import json
        pdf_paths = sorted(Path(INPUT_PDF_DIR).glob("*.pdf"))
        active_files = {p.name for p in pdf_paths}
        
        indexed_files = set()
        cache_file = Path(INPUT_PDF_DIR) / ".pinecone_sync_cache.json"
        if cache_file.exists():
            try:
                indexed_files = set(json.loads(cache_file.read_text()).keys())
            except: pass
        
        to_add = list(active_files - indexed_files)
        to_delete = list(indexed_files - active_files)
        needs_sync = bool(to_add or to_delete)
        return {
            "active_files": sorted(list(active_files)),
            "indexed_files": sorted(list(indexed_files)),
            "needs_sync": needs_sync,
            "to_add": sorted(list(set(to_add))),
            "to_delete": sorted(list(set(to_delete)))
        }

    def clean_text_for_tts(self, text: str) -> str:
        import audio_service
        return audio_service.clean_text_for_tts(text)

    def text_to_speech(self, text: str, rate: str = "-10%") -> bytes:
        import audio_service
        return audio_service.text_to_speech(text, rate)
