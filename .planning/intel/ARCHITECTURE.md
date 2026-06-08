<!-- refreshed: 2026-06-06 -->
# Architecture

**Analysis Date:** 2026-06-06

## System Overview

```text
┌─────────────────────────────────────────────────────────────────┐
│                    PRESENTATION LAYER                            │
│           `main.py` (Streamlit UI, 397 lines)                    │
│  ┌───────────────┐  ┌─────────────────┐  ┌──────────────────┐  │
│  │ Chat Interface│  │ Sidebar Controls│  │ Voice Recorder   │  │
│  │ (messages,    │  │ (mode selector, │  │ (mic_recorder)   │  │
│  │  streaming)   │  │  uploads, sync) │  │                  │  │
│  └───────┬───────┘  └────────┬────────┘  └────────┬─────────┘  │
│          │                  │                     │            │
└──────────┼──────────────────┼─────────────────────┼────────────┘
           │                  │                     │
           ▼                  ▼                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                    APPLICATION LOGIC LAYER                        │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  RAGAgent (`rag_agent.py`, 683 lines)                        │ │
│  │  Central orchestrator: ingestion, retrieval, generation      │ │
│  │  + session management + audio transcription + sync           │ │
│  └──────┬─────────────┬──────────────┬─────────────┬───────────┘ │
│         │             │              │             │             │
│         ▼             ▼              ▼             ▼             │
│  ┌──────────┐ ┌────────────┐ ┌──────────┐ ┌──────────────┐     │
│  │extract   │ │text_chunker│ │graph_rag │ │audio_service │     │
│  │_text.py  │ │.py         │ │.py       │ │.py           │     │
│  │PDF→text  │ │text→chunks │ │Obsidian  │ │TTS+STT       │     │
│  │+ OCR     │ │→FAISS      │ │GraphRAG  │ │              │     │
│  └────┬─────┘ └─────┬──────┘ └────┬─────┘ └──────────────┘     │
│       │             │             │                             │
│       ▼             ▼             ▼                             │
│  ┌──────────┐ ┌────────────┐ ┌──────────────┐                  │
│  │image_text│ │FAISS vector│ │Obsidian      │                  │
│  │.py       │ │store       │ │.linker_cache │                  │
│  │GeminiOCR │ │(local dir) │ │.json + FAISS │                  │
│  └──────────┘ └────────────┘ └──────────────┘                  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  linker_trigger.py — Subprocess bridge to obsidian-linker │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| `main.py` | Streamlit UI, event loop, sidebar, chat rendering | `main.py` |
| `config.py` | Path setup, env loading, constants | `config.py` |
| `RAGAgent` | Central orchestrator: ingest, retrieve, generate, sync | `rag_agent.py` |
| `extract_text` | PDF → text extraction + table + OCR | `extract_text.py` |
| `image_text` | Gemini-based image OCR | `image_text.py` |
| `text_chunker` | Text splitting, embedding, FAISS index management | `text_chunker.py` |
| `graph_rag` | Obsidian vault GraphRAG: note selection, graph walking | `graph_rag.py` |
| `audio_service` | TTS (edge-tts) + STT (Groq Whisper) | `audio_service.py` |
| `linker_trigger` | Subprocess bridge to obsidian-linker project | `linker_trigger.py` |
| `assets/style.css` | Custom dark glassmorphic theme | `assets/style.css` |

## Pattern Overview

**Overall:** RAG pipeline (Retrieval-Augmented Generation) with a Streamlit chat frontend, FAISS vector store, and GraphRAG knowledge graph augmentation.

**Key Characteristics:**
- **Streamlit singleton pattern** — `@st.cache_resource` on `get_agent()` for a single RAGAgent instance
- **Modular flat structure** — Top-level `.py` modules, no sub-packages
- **Imperative/script style** — Functions over classes (except `RAGAgent` and `VectorlessGraphRAG`)
- **Concurrent extraction** — `ThreadPoolExecutor` for parallel PDF page processing and OCR
- **State via Streamlit session_state** — Chat messages, UI state persisted in `st.session_state`
- **Manual dependency injection** — Modules import `config.py` constants directly; no IoC

## Layers

**Presentation Layer:**
- Purpose: Streamlit frontend, user interaction, chat rendering
- Location: `main.py`
- Contains: UI layout, event handlers, CSS injection, avatar rendering, audio playback
- Depends on: `rag_agent.RAGAgent`, `config.py` (indirectly via agent)
- Used by: User (via browser)

**Application Logic Layer:**
- Purpose: Retrieval, generation, ingestion orchestration
- Location: `rag_agent.py`
- Contains: RAGAgent class, prompt templates, retrieval logic, key rotation, session history
- Depends on: `extract_text`, `text_chunker`, `graph_rag`, `audio_service`, `linker_trigger`, `config`
- Used by: `main.py`

**Infrastructure Layer:**
- Purpose: PDF extraction, text chunking, vector storage, graph retrieval, audio processing
- Location: `extract_text.py`, `image_text.py`, `text_chunker.py`, `graph_rag.py`, `audio_service.py`, `linker_trigger.py`
- Contains: File I/O, API calls, subprocess management, FAISS operations
- Depends on: `config.py`, external APIs (Groq, Google Gemini, Microsoft Edge TTS)
- Used by: `rag_agent.py`

## Data Flow

### Primary Request Path (User Ask → Answer)

1. **User input** — Chat input or voice recording (`main.py:305-329`)
2. **Query reformulation** — `_get_standalone_question()` rewrites with history context using fast LLM (`rag_agent.py:160-211`)
3. **Meta query detection** — `_is_meta_query()` checks if asking about available files/checkboxes (`rag_agent.py:213-253`)
4. **Vector retrieval** (if content query):
   - **PDF mode:** FAISS `similarity_search_with_score()` → filter by L2 distance ≤ 0.85 (`rag_agent.py:325-335`)
   - **Obsidian mode:** `graph_rag.retrieve_context()` → LLM note selection → graph walk (`rag_agent.py:338-347`)
   - **Hybrid mode:** Both, concatenated with separators (`rag_agent.py:343-346`)
5. **Prompt construction** — System prompt + context + history + user question (`rag_agent.py:118-139`)
6. **LLM generation** — `chain.stream()` for streaming output (`rag_agent.py:489-503`)
7. **UI rendering** — Streamed output + source pill + citations + optional TTS (`main.py:339-394`)

### PDF Ingestion Flow

1. **Upload** — User uploads PDFs via sidebar file uploader (`main.py:134-136`)
2. **Save to disk** — Bytes written to `inputPDF/` directory (`main.py:155-160`)
3. **Extract text** — `extract_text.main()` → PyMuPDF page-by-page extraction with table support and optional Gemini OCR on images (`extract_text.py:131-193`)
4. **Cache** — Per-PDF text cached in `output/cache/{name}_ocr_{bool}.txt` with mtime checking (`extract_text.py:152-170`)
5. **Chunk & embed** — `text_chunker.main()` → RecursiveCharacterTextSplitter → `GoogleGenerativeAIEmbeddings` → FAISS index (`text_chunker.py:186-315`)
6. **Incremental update** — Compares active PDFs vs indexed; only processes new/modified/deleted files (`text_chunker.py:229-251`)

### Obsidian Sync Flow

1. **Trigger** — User clicks "Sync Obsidian Brain" in sidebar (`main.py:107-114`)
2. **Subprocess** — `run_obsidian_linker_sync()` → launches `obsidian-linker/main.py` with vault path as `--dir` argument (`linker_trigger.py:38-70`)
3. **Cache update** — Linker writes `.linker_cache.json` and `.linker_faiss_index/` into vault directory
4. **GraphRAG reload** — `VectorlessGraphRAG._load_cache()` reads updated cache (`graph_rag.py:25-48`)

### Compile & Save to Obsidian Flow

1. **Trigger** — User clicks "Compile & Save to Obsidian" below assistant response (`main.py:287-298`)
2. **Distillation** — LLM distills Q&A into structured markdown note with YAML frontmatter (`rag_agent.py:521-571`)
3. **File write** — Note saved as `.md` file in Obsidian vault directory (`rag_agent.py:590-594`)
4. **Background linking** — `trigger_obsidian_linker()` launches async subprocess to update graph (`rag_agent.py:599`)

**State Management:**
- Chat history: `st.session_state["messages"]` (list of dicts) + `InMemoryChatMessageHistory` per session
- Agent state: `RAGAgent` instance cached via `@st.cache_resource`
- Vector store: Persisted to disk (`faiss_index/`), loaded lazily
- PDF text cache: Filesystem (`output/cache/`)
- Obsidian graph cache: `.linker_cache.json` (read-only, written by obsidian-linker)

## Key Abstractions

**RAGAgent:**
- Purpose: Central orchestrator wrapping all RAG capabilities
- Location: `rag_agent.py` (class `RAGAgent`)
- Pattern: Singleton (via `@st.cache_resource`), stateful (vectorstore, chain, session store held as instance attrs)
- Methods: `ask_stream`, `ask`, `run_ingestion`, `sync_obsidian_vault`, `save_concepts_to_obsidian`, `transcribe_audio`, `text_to_speech`, `get_index_status`, `reload`

**VectorlessGraphRAG:**
- Purpose: Retrieval from Obsidian vault without a separate vector index for full notes (uses LLM for note selection after FAISS concept pre-filter)
- Location: `graph_rag.py` (class `VectorlessGraphRAG`)
- Pattern: Lazy cache loading, stateless-ish (reloads from cache file)
- Method: `retrieve_context(question)` → walks graph links for context synthesis

**ChatResult:**
- Purpose: Dataclass wrapping answer text, context chunks, and error
- Location: `rag_agent.py:31-35`
- Pattern: Simple data transfer object

**MatchedNotes:**
- Purpose: Pydantic model for structured LLM output (note selection)
- Location: `graph_rag.py:11-14`
- Pattern: LangChain structured output binding

## Entry Points

**Primary:**
- Location: `main.py`
- Command: `streamlit run main.py`
- Responsibilities: Bootstrap Streamlit app, render UI, manage event loop

**Ingestion (standalone):**
- Location: `extract_text.py` and `text_chunker.py`
- Pattern: `if __name__ == "__main__": main()`

**Linker Trigger (standalone/test):**
- Location: `linker_trigger.py`
- Pattern: `if __name__ == "__main__":` test execution

**Audio Test:**
- Location: `test_audio.py`
- Purpose: Standalone TTS→STT roundtrip test for Indian languages

## Architectural Constraints

- **Threading:** `ThreadPoolExecutor(max_workers=4)` for PDF page extraction + OCR; `ThreadPoolExecutor(max_workers=2)` for embedding generation (rate-limit throttled). LLM/Groq calls are synchronous (blocking). TTS uses `asyncio.run()` internally.
- **Global state:** Module-level `_client` singleton in `image_text.py:8-20` (Gemini client, lazily initialized). In-memory session store in `RAGAgent._session_store` dict.
- **Circular imports:** None detected. `rag_agent.py` imports `config`, `extract_text`, `text_chunker`; `graph_rag.py` imports `config`; `linker_trigger.py` imports `config`. All one-directional.
- **Session scoping:** `st.session_state` scoped per browser tab (Streamlit default). `RAGAgent._session_store` scoped per `session_id` string (user-provided via sidebar input).
- **No async concurrency for I/O-bound LLM calls:** Groq API calls are synchronous (`chain.invoke`, `chain.stream`). Rate limiting handled by retry + key rotation, not concurrency limits.

## Anti-Patterns

### Print-based Debugging

**What happens:** Extensive use of `print()` for debug/status logging throughout all modules, alongside proper `logging` module.
**Why it's wrong:** `print()` bypasses logging levels, cannot be filtered, goes to stdout without timestamps or module context.
**Do this instead:** Replace all `print()` with `logger.info()`, `logger.warning()`, `logger.error()` as appropriate. See `audio_service.py:78` for the correct pattern.

### Hardcoded Absolute Path

**What happens:** `linker_trigger.py:12` and `linker_trigger.py:44` use `r"c:\Users\saraf\Desktop\projects\obsidian-linker\main.py"` — a hardcoded absolute Windows path to an external project.
**Why it's wrong:** Not portable across machines or OS. Will break for any developer who clones to a different directory.
**Do this instead:** Make the path configurable via env var (e.g., `OBSIDIAN_LINKER_PATH`) or discover it relative to project root.

### allow_dangerous_deserialization=True

**What happens:** Every `FAISS.load_local()` call passes `allow_dangerous_deserialization=True` (`rag_agent.py:88`, `text_chunker.py:216`, `graph_rag.py:72`).
**Why it's wrong:** Loading pickle-based FAISS indices from untrusted sources is a vector for arbitrary code execution.
**Do this instead:** The index is local and user-controlled, so the risk is low. Document the rationale and keep `allow_dangerous_deserialization` behind a config flag or at minimum add a warning log.

### Massive Single-File Orchestrator

**What happens:** `rag_agent.py` at 683 lines handles ingestion orchestration, retrieval, streaming, question reformulation, meta queries, note saving, audio transcription, TTS, key rotation, and index status — too many responsibilities.
**Why it's wrong:** Violates Single Responsibility Principle; hard to test, maintain, or extend.
**Do this instead:** Split into `retriever.py` (retrieval logic), `conversation.py` (chat history + query reformulation), `sync_service.py` (index management + vault sync), `note_service.py` (Obsidian note compilation).

### Inline CSS with unsafe_allow_html

**What happens:** `main.py` uses `st.markdown(css, unsafe_allow_html=True)` to load external CSS, plus inline HTML `<style>` overrides and inline `<div>` tags throughout.
**Why it's wrong:** `unsafe_allow_html=True` is a cross-site scripting (XSS) risk if any user content is interpolated. Also makes the Python file harder to maintain.
**Do this instead:** For the external CSS (already done in `assets/style.css`), keep using that pattern. Replace inline HTML formatting with Streamlit native components where possible.

## Error Handling

**Strategy:** Defensive with fallback values. Most operations wrap in try/except and return partial/default results.

**Patterns:**
- **LLM calls:** Retry loop (3 attempts) with Groq key rotation on 429/rate_limit errors (`rag_agent.py:358-372`, `487-512`, `527-571`)
- **Agent methods:** Return `ChatResult` with `error` field or dict with `success`/`error` keys rather than raising exceptions
- **Streaming errors:** Yield `[ERROR] ...` string tokens to the UI stream (`rag_agent.py:511`)
- **File ops:** try/except with print/log on failure, continue processing remaining items
- **Missing env vars:** Checked upfront in `main.py:81-85`, `st.stop()` if missing

## Cross-Cutting Concerns

**Logging:**
- `config.py`: `logging.basicConfig(level=INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')`
- Mix of `logging.getLogger(__name__)` and bare `print()` calls
- `audio_service.py` uses `logger` consistently; other modules mix both

**Validation:**
- **User input:** Streamlit handles UI-level validation (file type, required fields)
- **Model input:** LangChain prompt templates handle variable injection
- **Minimal runtime validation:** No Pydantic models for API requests/responses except `MatchedNotes` in `graph_rag.py`

**Authentication:**
- API keys validated at startup (`missing_env_vars()`)
- No user-facing authentication

---

*Architecture analysis: 2026-06-06*
