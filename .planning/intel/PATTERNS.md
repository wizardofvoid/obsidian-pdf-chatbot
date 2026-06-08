# Codebase Patterns

**Analysis Date:** 2026-06-06

## Module Structure Pattern

Every functional module follows a consistent structure:
```
module.py
├── imports (standard → third-party → local)
├── module-level constants/loggers
├── helper functions (private with `_` prefix)
├── main() → bool
└── if __name__ == "__main__": main()
```

**Examples:**
- `extract_text.py` — `extract_page_hybrid()` → `extract_page_worker()` → `extract_pdf()` → `main()`
- `text_chunker.py` — `chunk_all_text_files()` → `create_vectorstore()` → `main()`
- `linker_trigger.py` — `trigger_obsidian_linker()` → `run_obsidian_linker_sync()` → `if __name__ ...`

**Pattern rule:** Each module has a `main() -> bool` entry point that can run standalone.

## Singleton Agent Pattern

```python
# main.py:5-7
@st.cache_resource
def get_agent() -> RAGAgent:
    return RAGAgent()
```
- `RAGAgent` is instantiated once via Streamlit's `@st.cache_resource`
- Cache is cleared explicitly: `st.cache_resource.clear()` when index changes
- Self-healing: cache validated on each render by checking attribute existence (`main.py:72-77`)

## Retry with Key Rotation Pattern

Used for all Groq API calls. Consistent across 3 locations:

```python
# rag_agent.py:358-372
max_retries = 3
for attempt in range(max_retries):
    try:
        answer = chain.invoke(...)
        return ChatResult(answer=answer, ...)
    except Exception as e:
        err_str = str(e)
        if ("429" in err_str or "rate_limit" in err_str.lower()) and attempt < max_retries - 1:
            if self.rotate_groq_key():
                continue
        raise e
```
- Up to 3 retry attempts
- On 429/rate_limit: rotate to next `GROQ_API_KEY_N` (1-9)
- Non-rate-limit errors: re-raise immediately
- Used in: `ask()`, `ask_stream()`, `save_concepts_to_obsidian()`, `_get_standalone_question()`

## Dict-Based Return Pattern for Operations

Consistent return type for operations that may fail:

```python
# Success
{"success": True, "note_title": clean_title, "file_path": str(file_path), "linker_triggered": trigger_success}

# Failure
{"success": False, "error": "Obsidian vault directory not found: ..."}
```

Used in:
- `RAGAgent.save_concepts_to_obsidian()` — `rag_agent.py:516-609`
- `RAGAgent.sync_obsidian_vault()` — `rag_agent.py:611-626`

## Dataclass Return Pattern for Retrieval

```python
# rag_agent.py:31-35
@dataclass
class ChatResult:
    answer: str
    context_chunks: list[str] = field(default_factory=list)
    error: str | None = None
```
- Used by `RAGAgent.ask()` for structured return
- Error encoded as field rather than exception
- Caller checks `result.error` for failure

## Streaming Generator Pattern

```python
# rag_agent.py:376-514
def ask_stream(self, ...):
    # ... setup ...
    try:
        # ... retrieval ...
        for attempt in range(max_retries):
            try:
                stream = chain.stream({...})
                iterator = iter(stream)
                first_chunk = next(iterator)
                yield first_chunk
                for chunk in iterator:
                    yield chunk
                return
            except Exception as e:
                # retry logic
                yield f"[ERROR] {err_str}"
                return
    except Exception as e:
        yield f"[ERROR] {str(e)}"
```
- Generator uses `yield` for streaming tokens
- Pre-fetches first chunk to catch connection errors early (`iterator = iter(stream); first_chunk = next(iterator)`)
- Error tokens yielded as `[ERROR] ...` strings
- Early return on StopIteration for empty streams

## File Cache Invalidation (mtime-based)

PDF text extraction uses modification-time comparison:

```python
# extract_text.py:155-169
is_cache_valid = cache_file.exists() and cache_file.stat().st_mtime >= pdf_path.stat().st_mtime
if is_cache_valid:
    pdf_text = cache_file.read_text(encoding="utf-8")
else:
    pdf_text = extract_pdf(pdf_path, skip_ocr=skip_ocr)
    cache_file.write_text(pdf_text, encoding="utf-8")
```

Also used in `text_chunker.py:229-237` for incremental index updates — compares PDF mtime vs FAISS index mtime.

## FAISS Incremental Update Pattern

```python
# text_chunker.py:186-315
def main() -> bool:
    # 1. Load existing FAISS index
    # 2. Determine active PDFs on disk
    # 3. Compare: compute sources_to_delete and sources_to_index
    # 4. Delete removed/modified chunks from existing index
    # 5. Embed new/modified documents → temp FAISS index
    # 6. Merge: vectorstore.merge_from(temp_vectorstore)
    # 7. Save: vectorstore.save_local(str(VECTORSTORE_DIR))
```
- Only processes delta (new, modified, deleted PDFs)
- Avoids full rebuild on every change
- Uses `FAISS.merge_from()` for incremental addition

## GraphRAG Two-Stage Retrieval Pattern

```python
# graph_rag.py:79-167
def select_relevant_notes(self, question: str, limit: int = 3) -> List[str]:
    # Stage 1: FAISS vector pre-filter (fast, cheap)
    candidate_notes = similarity_search_with_score(question, k=12)
    # Filter by L2 distance <= 0.85
    
    # Stage 2: LLM structured selection (precise)
    llm.with_structured_output(MatchedNotes).invoke({candidate_notes, question})
```

**Graph walk for context:**
```python
# graph_rag.py:184-277
def retrieve_context(self, question: str) -> Dict[str, Any]:
    # 1. Select top-2 matching notes
    # 2. Extract outgoing wikilinks from note content ([[Note Name]])
    # 3. Find incoming links from cache metadata
    # 4. Walk up to 5 unique neighbors
    # 5. Build context: primary notes + neighbor concept summaries
```

## Google API Key Fallback Chain Pattern

```python
# Consistently used in 4 locations:
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    api_key = os.getenv("GOOGLE_API_KEY_1")
```
Used in: `rag_agent.py:81-83`, `text_chunker.py:128-130`, `graph_rag.py:61-63`

## Groq API Key Rotation Pattern

```python
# rag_agent.py:92-111
@staticmethod
def rotate_groq_key(self) -> bool:
    old_idx = self._current_key_idx
    for offset in range(1, 10):
        next_idx = ((old_idx + offset - 1) % 9) + 1
        if os.getenv(f"GROQ_API_KEY_{next_idx}"):
            self._current_key_idx = next_idx
            self._chain = None  # Force chain reload with new key
            return True
    return False
```
- Cycles through keys 1-9
- Forces chain reload on rotation
- Used as rate-limit mitigation strategy

## Lazy Initialization Pattern

```python
# rag_agent.py:47-51
def _get_graph_rag(self):
    if self._graph_rag is None:
        from graph_rag import VectorlessGraphRAG
        self._graph_rag = VectorlessGraphRAG()
    return self._graph_rag
```

Also used for:
- `RAGAgent._load_vectorstore()` — `rag_agent.py:79-90`
- `RAGAgent._load_chain()` — `rag_agent.py:113-141`
- `image_text._get_client()` — `image_text.py:10-20` (module-level singleton)

## Observable Naming Conventions

| Category | Convention | Example |
|----------|-----------|---------|
| Module files | `snake_case.py` | `rag_agent.py`, `text_chunker.py` |
| Classes | `PascalCase` | `RAGAgent`, `VectorlessGraphRAG` |
| Public methods | `snake_case` | `run_ingestion()`, `save_concepts_to_obsidian()` |
| Private methods | `_prefix` | `_load_vectorstore()`, `_is_meta_query()` |
| Constants | `SCREAMING_SNAKE` | `EMBEDDING_MODEL`, `RETRIEVAL_K` |
| Entry point | `main()` | `def main() -> bool:` |
| Config values | `UPPERCASE` in `config.py` | `INPUT_PDF_DIR`, `LLM_MODEL` |

## Python Version Features Used

- **3.9+**: `list[str]`, `dict[str, Any]`, `tuple[int, str]` (type hint generics)
- **3.10+**: `str \| None` union syntax, `match` statement (only `re.search` used in `main.py:30`)
- **3.11+**: `StrEnum` not used; `ExceptionGroup` not used
- **`pathlib`** everywhere — `Path()` for all filesystem operations (no `os.path` except in `linker_trigger.py`)

## Streamlit Patterns

**Session state initialization:**
```python
if "prev_uploaded_files" not in st.session_state:
    st.session_state["prev_uploaded_files"] = []
```

**Cache invalidation trigger:**
```python
st.cache_resource.clear()  # Force RAGAgent reload
st.rerun()                 # Re-render with new state
```

**CSS injection:**
```python
with open(style_path, "r", encoding="utf-8") as f:
    css = f.read()
st.markdown(f"<style>\n{css}\n</style>", unsafe_allow_html=True)
```

**Avatar rendering with SVG:**
```python
assistant_avatar = "data:image/svg+xml;utf8,<svg ...>"
with st.chat_message("assistant", avatar=assistant_avatar):
    ...
```

**Streamed output with placeholder:**
```python
message_placeholder = st.empty()
with message_placeholder.container():
    answer = st.write_stream(agent.ask_stream(...))
message_placeholder.empty()
with message_placeholder.container():
    render_message_with_source(answer)
```

## Docker/Deployment Patterns

- None detected. Local-only desktop app via `streamlit run`.
- No Dockerfile, no docker-compose, no deployment scripts.

---

*Pattern analysis: 2026-06-06*
