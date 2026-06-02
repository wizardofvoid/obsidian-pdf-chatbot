import os
from typing import Any
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

# pyrefly: ignore [missing-import]
from langchain_community.vectorstores import FAISS
# pyrefly: ignore [missing-import]
from langchain_core.chat_history import InMemoryChatMessageHistory
# pyrefly: ignore [missing-import]
from langchain_core.output_parsers import StrOutputParser
# pyrefly: ignore [missing-import]
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
# pyrefly: ignore [missing-import]
from langchain_core.runnables.history import RunnableWithMessageHistory
# pyrefly: ignore [missing-import]
from langchain_google_genai import GoogleGenerativeAIEmbeddings
# pyrefly: ignore [missing-import]
from langchain_groq import ChatGroq

import extract_text as et
import text_chunker as tc
from config import EMBEDDING_MODEL, VECTORSTORE_DIR, FAISS_INDEX_FILE, LLM_MODEL, RETRIEVAL_K

load_dotenv()

@dataclass
class ChatResult:
    answer: str
    context_chunks: list[str] = field(default_factory=list)
    error: str | None = None

class RAGAgent:
    """RAG pipeline: ingest PDFs, retrieve chunks, answer with history."""

    def __init__(self):
        self._vectorstore: FAISS | None = None
        self._chain: RunnableWithMessageHistory | None = None
        self._session_store: dict[str, InMemoryChatMessageHistory] = {}
        self._graph_rag = None

    def _get_graph_rag(self):
        if self._graph_rag is None:
            from graph_rag import VectorlessGraphRAG
            self._graph_rag = VectorlessGraphRAG()
        return self._graph_rag

    @staticmethod
    def env_configured() -> bool:
        groq_ok = bool(os.getenv("GROQ_API_KEY")) or any("GROQ_API_KEY_" in k for k in os.environ)
        google_ok = bool(os.getenv("GOOGLE_API_KEY")) or any("GOOGLE_API_KEY_" in k for k in os.environ)
        return groq_ok and google_ok

    @staticmethod
    def missing_env_vars() -> list[str]:
        missing = []
        groq_ok = bool(os.getenv("GROQ_API_KEY")) or any("GROQ_API_KEY_" in k for k in os.environ)
        google_ok = bool(os.getenv("GOOGLE_API_KEY")) or any("GOOGLE_API_KEY_" in k for k in os.environ)
        if not groq_ok:
            missing.append("GROQ_API_KEY")
        if not google_ok:
            missing.append("GOOGLE_API_KEY")
        return missing

    @staticmethod
    def index_ready() -> bool:
        return FAISS_INDEX_FILE.exists()

    def _get_session_history(self, session_id: str) -> InMemoryChatMessageHistory:
        if session_id not in self._session_store:
            self._session_store[session_id] = InMemoryChatMessageHistory()
        return self._session_store[session_id]

    def _load_vectorstore(self) -> FAISS:
        if self._vectorstore is None:
            google_key = os.getenv("GOOGLE_API_KEY")
            if not google_key:
                google_key = os.getenv("GOOGLE_API_KEY_1")
            embeddings = GoogleGenerativeAIEmbeddings(model=EMBEDDING_MODEL, google_api_key=google_key)
            self._vectorstore = FAISS.load_local(
                folder_path=str(VECTORSTORE_DIR),
                embeddings=embeddings,
                allow_dangerous_deserialization=True,
            )
        return self._vectorstore

    def _get_groq_key(self) -> str:
        key = os.getenv("GROQ_API_KEY")
        if not key:
            for i in range(1, 10):
                k = os.getenv(f"GROQ_API_KEY_{i}")
                if k:
                    return k
        return key

    def _load_chain(self) -> Any:
        if self._chain is None:
            groq_key = self._get_groq_key()
            llm = ChatGroq(groq_api_key=groq_key, model=LLM_MODEL)
            prompt = ChatPromptTemplate.from_messages(
                [
                    (
                        "system",
                        "You are an expert personal study assistant. Answer the user's questions naturally and conversationally using the provided Context.\n\n"
                        "CRITICAL SOURCE PRIORITIZATION RULES:\n"
                        "1. **Study Materials Override**: Always prioritize the facts, definitions, formulas, and content provided in the 'Context' section below. If there is a conflict between the Context and your general knowledge, the Context MUST win. Treat the Context as absolute truth.\n"
                        "2. **General Knowledge Fallback**: If the provided Context is empty, irrelevant, or does not contain enough information to answer the question, you MUST answer the question using your general pre-trained knowledge to the best of your ability. Do not say 'I don't know' if it can be explained using general knowledge.\n"
                        "3. **Speak naturally**: DO NOT use robotic introductory prefaces like 'According to your notes', 'Based on the provided materials', 'As in the notes', 'According to the context', or 'In your notes'. Avoid meta-commentary about the source materials or notes entirely. Simply answer the question directly as if you already know the facts.\n"
                        "4. **Obsidian Task Checkbox Syntax**:\n"
                        "   - In Obsidian Markdown notes, `- [ ]` represents an **unchecked / incomplete task or checkbox**.\n"
                        "   - `- [x]` represents a **checked / completed task or checkbox**.\n"
                        "   - If asked about tasks, todo items, incomplete/complete checklists, or checkboxes, parse this syntax from the Context and present them clearly.\n"
                        "5. **Transparency Source Indicator**: You must explicitly append one of the following exact tokens to the VERY END of your response on a new line (do not embed it in normal sentences):\n"
                        "   - `[SOURCE: MATERIALS]` if the answer is derived strictly or mostly from the provided Context.\n"
                        "   - `[SOURCE: GENERAL]` if the Context was empty/irrelevant and you answered using general knowledge.\n"
                        "   - `[SOURCE: HYBRID]` if you successfully blended facts from the Context with general knowledge explanations.\n\n"
                        "Context:\n{context}",
                    ),
                    MessagesPlaceholder("history"),
                    ("human", "{input}"),
                ]
            )
            self._chain = prompt | llm | StrOutputParser()
        return self._chain

    def reload(self) -> None:
        """Drop cached vectorstore and chain (call after rebuilding the index)."""
        self._vectorstore = None
        self._chain = None
        self._graph_rag = None

    def run_ingestion(self, skip_ocr: bool = False) -> bool:
        et.main(skip_ocr=skip_ocr)
        # Always run text chunker indexing when explicitly triggered by the user
        ok = tc.main()
        if ok:
            self.reload()
        return ok

    def clear_session(self, session_id: str) -> None:
        self._session_store.pop(session_id, None)

    def _get_standalone_question(self, question: str, chat_history: list = None) -> str:
        """
        Formulate a standalone search query from the raw user question and chat history
        using a fast LLM, ensuring conversational follow-up questions retrieve correct data.
        """
        if not chat_history:
            return question

        from langchain_core.messages import HumanMessage, AIMessage
        
        # Convert streamlit session history to LangChain messages
        formatted_messages = []
        for msg in chat_history:
            if msg["role"] == "user":
                formatted_messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                formatted_messages.append(AIMessage(content=msg["content"]))

        try:
            api_key = self._get_groq_key()
            if not api_key:
                return question

            llm = ChatGroq(groq_api_key=api_key, model="llama-3.1-8b-instant", max_tokens=256)
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", "Given a chat history and the latest user question which might reference context in the chat history, formulate a standalone question which can be understood without the chat history. Do NOT answer the question, just reformulate it if needed and otherwise return it as is. Respond with ONLY the reformulated question text."),
                MessagesPlaceholder("history"),
                ("human", "{input}")
            ])
            
            chain = prompt | llm | StrOutputParser()
            standalone = chain.invoke({"history": formatted_messages, "input": question})
            print(f"[RAGAgent] Reformulated conversational query: '{question}' -> '{standalone.strip()}'")
            return standalone.strip()
        except Exception as e:
            print(f"[RAGAgent Error] Failed to reformulate conversational query: {e}")
            return question

    def _is_meta_query(self, question: str) -> bool:
        q = question.lower()
        # Intent words: list, show, tell, what, which, print, display, name, find, access, active
        # Object words: file, note, document, pdf, vault, book, textbook, paper, material, graph, knowledge
        has_intent = any(k in q for k in ["list", "show", "tell", "what", "which", "print", "display", "name", "access to", "do you have", "have access", "status of", "get my"])
        has_object = any(o in q for o in ["file", "note", "document", "pdf", "vault", "book", "textbook", "paper", "material", "graph", "knowledge"])
        
        # Checkbox queries are also meta-queries that scan vault structure
        is_checkbox_query = any(k in q for k in ["checkbox", "task", "todo", "to-do", "check list", "checklist", "incomplete", "completed", "checked", "unchecked"])
        return (has_intent and has_object) or is_checkbox_query

    def ask(self, question: str, session_id: str = "default_session", mode: str = "pdf", chat_history: list = None) -> ChatResult:
        if mode == "pdf" and not self.index_ready():
            return ChatResult(
                answer="",
                error="No search index found. Run extraction and index build first.",
            )

        try:
            chain = self._load_chain()
            context_text = ""
            chunks = []
            
            # Reformulate conversational follow-ups into standalone search queries
            standalone_query = self._get_standalone_question(question, chat_history)
            
            # Check if this is a meta query asking to list available files/notes
            if self._is_meta_query(standalone_query):
                meta_context = []
                
                # Check for checkbox task query scan first
                if any(k in standalone_query.lower() for k in ["checkbox", "task", "todo", "to-do", "checklist", "incomplete", "completed", "checked", "unchecked"]):
                    from config import OBSIDIAN_VAULT_DIR
                    vault_path = Path(OBSIDIAN_VAULT_DIR)
                    if vault_path.exists():
                        checkbox_notes = []
                        for note_file in vault_path.glob("*.md"):
                            try:
                                note_content = note_file.read_text(encoding="utf-8")
                                if "- [ ]" in note_content or "- [x]" in note_content:
                                    checkbox_notes.append(f"--- START NOTE: {note_file.name} ---\n{note_content}\n--- END NOTE: {note_file.name} ---")
                            except Exception as e:
                                print(f"[Error reading note {note_file.name} for checkboxes]: {e}")
                        if checkbox_notes:
                            meta_context.append("### Obsidian Notes containing Checkboxes / Tasks:")
                            meta_context.extend(checkbox_notes)
                        else:
                            meta_context.append("No notes with checkboxes or tasks were found in your Obsidian Vault.")
                    else:
                        meta_context.append("Obsidian vault directory not found or configured.")
                else:
                    # Regular meta query (list all available notes/PDFs)
                    if mode in ("pdf", "hybrid"):
                        from config import INPUT_PDF_DIR
                        pdf_path = Path(INPUT_PDF_DIR)
                        if pdf_path.exists():
                            pdfs = sorted([f.name for f in pdf_path.glob("*.pdf")])
                            if pdfs:
                                meta_context.append("### Available PDF Documents in Knowledge Base:")
                                for p in pdfs:
                                    meta_context.append(f"- {p}")
                            else:
                                meta_context.append("No PDF documents have been uploaded yet.")
                        else:
                            meta_context.append("No PDF documents have been uploaded yet.")
                    
                    if mode in ("obsidian", "hybrid"):
                        graph_rag = self._get_graph_rag()
                        notes = sorted(graph_rag.available_notes)
                        if notes:
                            meta_context.append("### Available Obsidian Study Notes in Knowledge Base:")
                            for n in notes:
                                meta_context.append(f"- {n}")
                        else:
                            meta_context.append("No Obsidian study notes found in the knowledge graph cache.")
                
                context_text = "\n\n".join(meta_context)
                chunks = [context_text]
            else:
                # 1. Retrieve PDF context if mode is pdf or hybrid
                if mode in ("pdf", "hybrid") and self.index_ready():
                    vectorstore = self._load_vectorstore()
                    # Perform search with scores (L2 distance: lower is closer)
                    docs_and_scores = vectorstore.similarity_search_with_score(standalone_query, k=RETRIEVAL_K)
                    filtered_docs = []
                    for doc, score in docs_and_scores:
                        print(f"[RAGAgent PDF Search] Chunk source: {doc.metadata.get('source')} pg {doc.metadata.get('page')}, Score (L2 Distance): {score:.4f}")
                        if score <= 0.85:
                            filtered_docs.append(doc)
                    chunks = [doc.page_content for doc in filtered_docs]
                    pdf_context = "\n\n".join(chunks)
                    context_text = pdf_context
                    
                # 2. Retrieve Obsidian GraphRAG context if mode is obsidian or hybrid
                if mode in ("obsidian", "hybrid"):
                    graph_rag = self._get_graph_rag()
                    obs_res = graph_rag.retrieve_context(standalone_query)
                    obs_context = obs_res["context"]
                    
                    if mode == "hybrid":
                        context_text = f"--- PDF STUDY MATERIAL CHUNKS ---\n{context_text}\n\n--- PERSONAL KNOWLEDGE GRAPH NOTES ---\n{obs_context}"
                    else:
                        context_text = obs_context
                        chunks = [obs_context]
                    
            from langchain_core.messages import HumanMessage, AIMessage
            formatted_messages = []
            if chat_history:
                for msg in chat_history:
                    if msg["role"] == "user":
                        formatted_messages.append(HumanMessage(content=msg["content"]))
                    elif msg["role"] == "assistant":
                        formatted_messages.append(AIMessage(content=msg["content"]))
                        
            answer = chain.invoke(
                {"input": question, "context": context_text, "history": formatted_messages}
            )
            return ChatResult(answer=answer, context_chunks=chunks)
        except Exception as e:
            return ChatResult(answer="", error=str(e))

    def ask_stream(self, question: str, session_id: str = "default_session", citations: list = None, mode: str = "pdf", chat_history: list = None):
        if mode == "pdf" and not self.index_ready():
            yield "[ERROR] No search index found. Run extraction and index build first."
            return

        try:
            chain = self._load_chain()
            context_text = ""
            
            # Reformulate conversational follow-ups into standalone search queries
            standalone_query = self._get_standalone_question(question, chat_history)
            
            # Check if this is a meta query asking to list available files/notes
            if self._is_meta_query(standalone_query):
                meta_context = []
                
                # Check for checkbox task query scan first
                if any(k in standalone_query.lower() for k in ["checkbox", "task", "todo", "to-do", "checklist", "incomplete", "completed", "checked", "unchecked"]):
                    from config import OBSIDIAN_VAULT_DIR
                    vault_path = Path(OBSIDIAN_VAULT_DIR)
                    if vault_path.exists():
                        checkbox_notes = []
                        for note_file in vault_path.glob("*.md"):
                            try:
                                note_content = note_file.read_text(encoding="utf-8")
                                if "- [ ]" in note_content or "- [x]" in note_content:
                                    checkbox_notes.append(f"--- START NOTE: {note_file.name} ---\n{note_content}\n--- END NOTE: {note_file.name} ---")
                                    if citations is not None:
                                        citations.append({"source": f"Obsidian: {note_file.name}", "page": "Task Note"})
                            except Exception as e:
                                print(f"[Error reading note {note_file.name} for checkboxes]: {e}")
                        if checkbox_notes:
                            meta_context.append("### Obsidian Notes containing Checkboxes / Tasks:")
                            meta_context.extend(checkbox_notes)
                        else:
                            meta_context.append("No notes with checkboxes or tasks were found in your Obsidian Vault.")
                    else:
                        meta_context.append("Obsidian vault directory not found or configured.")
                else:
                    if mode in ("pdf", "hybrid"):
                        from config import INPUT_PDF_DIR
                        pdf_path = Path(INPUT_PDF_DIR)
                        if pdf_path.exists():
                            pdfs = sorted([f.name for f in pdf_path.glob("*.pdf")])
                            if pdfs:
                                meta_context.append("### Available PDF Documents in Knowledge Base:")
                                for p in pdfs:
                                    meta_context.append(f"- {p}")
                                if citations is not None:
                                    for p in pdfs:
                                        citations.append({"source": p, "page": "Document List"})
                            else:
                                meta_context.append("No PDF documents have been uploaded yet.")
                        else:
                            meta_context.append("No PDF documents have been uploaded yet.")
                    
                    if mode in ("obsidian", "hybrid"):
                        graph_rag = self._get_graph_rag()
                        notes = sorted(graph_rag.available_notes)
                        if notes:
                            meta_context.append("### Available Obsidian Study Notes in Knowledge Base:")
                            for n in notes:
                                meta_context.append(f"- {n}")
                            if citations is not None:
                                for n in notes:
                                    citations.append({"source": f"Obsidian: {n}", "page": "Note List"})
                        else:
                            meta_context.append("No Obsidian study notes found in the knowledge graph cache.")
                
                context_text = "\n\n".join(meta_context)
            else:
                # 1. Retrieve PDF context if mode is pdf or hybrid
                if mode in ("pdf", "hybrid") and self.index_ready():
                    vectorstore = self._load_vectorstore()
                    docs_and_scores = vectorstore.similarity_search_with_score(standalone_query, k=RETRIEVAL_K)
                    filtered_docs = []
                    for doc, score in docs_and_scores:
                        print(f"[RAGAgent PDF Search Stream] Chunk source: {doc.metadata.get('source')} pg {doc.metadata.get('page')}, Score (L2 Distance): {score:.4f}")
                        if score <= 0.85:
                            filtered_docs.append(doc)
                            if citations is not None:
                                citations.append({
                                    "source": doc.metadata.get("source"),
                                    "page": doc.metadata.get("page")
                                })
                    context_text = "\n\n".join([doc.page_content for doc in filtered_docs])
                    
                # 2. Retrieve Obsidian GraphRAG context if mode is obsidian or hybrid
                if mode in ("obsidian", "hybrid"):
                    graph_rag = self._get_graph_rag()
                    obs_res = graph_rag.retrieve_context(standalone_query)
                    obs_context = obs_res["context"]
                    
                    if citations is not None:
                        citations.extend(obs_res["citations"])
                        
                    if mode == "hybrid":
                        context_text = f"--- PDF STUDY MATERIAL CHUNKS ---\n{context_text}\n\n--- PERSONAL KNOWLEDGE GRAPH NOTES ---\n{obs_context}"
                    else:
                        context_text = obs_context
                        
            from langchain_core.messages import HumanMessage, AIMessage
            formatted_messages = []
            if chat_history:
                for msg in chat_history:
                    if msg["role"] == "user":
                        formatted_messages.append(HumanMessage(content=msg["content"]))
                    elif msg["role"] == "assistant":
                        formatted_messages.append(AIMessage(content=msg["content"]))
                        
            for chunk in chain.stream(
                {"input": question, "context": context_text, "history": formatted_messages}
            ):
                yield chunk
        except Exception as e:
            yield f"[ERROR] {str(e)}"

    def save_concepts_to_obsidian(self, question: str, answer: str, citations: list) -> dict:
        """
        Distills a Q&A exchange into an atomic study note, saves it as markdown
        in the Obsidian Vault, and triggers the background linker to update the graph.
        """
        import re
        from pathlib import Path
        from config import OBSIDIAN_VAULT_DIR
        from linker_trigger import trigger_obsidian_linker
        
        try:
            api_key = self._get_groq_key()
            if not api_key:
                return {"success": False, "error": "GROQ_API_KEY not found in environment."}

            llm = ChatGroq(groq_api_key=api_key, model="llama-3.1-8b-instant", max_tokens=1500)
            
            prompt_distill = ChatPromptTemplate.from_messages([
                ("system", "You are an expert study note compiler. Your job is to distill a Q&A exchange about study materials into a beautifully structured, highly readable, atomic Obsidian study note. Focus strictly on clarity and concise markdown formatting."),
                ("user", """User Question: {question}
Chatbot Answer: {answer}
Citations: {citations}
 
YOUR TASK:
Compile this exchange into a single atomic study note in Markdown format.
 
Required Structure:
1. YAML Frontmatter: Enclosed in '---' containing:
   - title: A concise, clear 3-5 word note title (without special characters or file extensions).
   - tags: A list of 2-4 study category tags (prefixed with '#', e.g., '#dsa', '#algorithms').
   - summary: A brief 1-2 sentence high-level summary of the concepts.
2. Note Body: Clean Markdown with headers, bullet points, explanations, formulas, or code blocks.
3. Citations / Sources: A dedicated section at the bottom citing the source materials used (e.g. 'Source: Book.pdf, page 45').
 
CRITICAL RULES:
- **Active Wikilinking**: If the 'Citations' list contains any cited Obsidian notes (e.g., 'Obsidian: Search in 2D matrix.md'), you MUST include active Obsidian wiki-links pointing to them (e.g., `[[Search in 2D matrix]]` - do not include the `.md` extension in the link) inside the body or the sources section of the new note! This is highly critical to connect your new note directly to its parent sources.
- **Output Only Note**: Your entire output must start with the YAML '---' and contain ONLY the compiled markdown note. Do not include any chat preface, conversational preamble, or markdown wrapper code blocks. Make the title extremely concise as it will be used as the filename.""")
            ])
            
            chain = prompt_distill | llm | StrOutputParser()
            note_content = chain.invoke({
                "question": question,
                "answer": answer,
                "citations": str(citations)
            })
            
            # Extract title from the YAML frontmatter
            title_match = re.search(r'title:\s*["\']?(.*?)["\']?\n', note_content)
            if title_match:
                title = title_match.group(1).strip()
            else:
                # Fallback title from the question
                title = "Study Takeaway - " + question[:25]
                
            # Clean title for a valid Windows/Mac filename
            clean_title = re.sub(r'[\\/*?:"<>|]', "", title).strip()
            if not clean_title:
                clean_title = "Study_Note_Takeaway"
                
            vault_dir = Path(OBSIDIAN_VAULT_DIR)
            if not vault_dir.exists():
                return {"success": False, "error": f"Obsidian vault directory not found: {OBSIDIAN_VAULT_DIR}"}
                
            file_path = vault_dir / f"{clean_title}.md"
            
            # Write note to Obsidian vault
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(note_content)
                
            print(f"[RAGAgent] Successfully wrote new note: {file_path}")
            
            # Trigger background graph re-linking
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
        """
        Triggers a synchronous scan and re-indexing of the Obsidian vault.
        Reloads the internal GraphRAG cache upon success.
        """
        from linker_trigger import run_obsidian_linker_sync
        try:
            success = run_obsidian_linker_sync()
            if success:
                # Reload our internal GraphRAG to read the newly updated .linker_cache.json
                self.reload()
                return {"success": True}
            else:
                return {"success": False, "error": "Re-indexing process failed. Check terminal logs."}
        except Exception as e:
            return {"success": False, "error": str(e)}
