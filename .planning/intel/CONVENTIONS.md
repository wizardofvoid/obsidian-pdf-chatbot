# Coding Conventions

**Analysis Date:** 2026-06-06

## Naming Patterns

**Files:**
- `snake_case.py` for all Python modules: `rag_agent.py`, `extract_text.py`, `text_chunker.py`, `image_text.py`, `graph_rag.py`, `audio_service.py`, `linker_trigger.py`
- `UPPERCASE` for the Streamlit config: `.streamlit/config.toml`
- `style.css` for the CSS asset

**Classes:**
- `PascalCase`: `RAGAgent`, `ChatResult`, `VectorlessGraphRAG`, `MatchedNotes`

**Functions:**
- `snake_case` for all functions and methods: `get_agent()`, `format_citation()`, `inject_premium_styles()`, `render_message_with_source()`, `_get_graph_rag()`, `_load_vectorstore()`, `rotate_groq_key()`, `_is_meta_query()`
- Leading underscore for private/internal methods: `_get_graph_rag()`, `_load_vectorstore()`, `_load_chain()`, `_get_session_history()`, `_get_standalone_question()`, `_is_meta_query()`, `_load_cache()`, `_load_faiss_index()`, `_get_client()` (module-level in `image_text.py`)
- `main()` as entry point in every executable module

**Variables:**
- `snake_case` for all local variables and instance attributes: `session_id`, `rag_mode`, `voice_mode`, `audio_bytes`, `context_text`, `chunks`, `citations_container`
- Descriptive names preferred over abbreviations

**Constants:**
- `SCREAMING_SNAKE_CASE` for module-level config constants defined in `config.py`: `INPUT_PDF_DIR`, `OUTPUT_DIR`, `VECTORSTORE_DIR`, `FAISS_INDEX_FILE`, `EMBEDDING_MODEL`, `LLM_MODEL`, `RETRIEVAL_K`, `CHUNK_SIZE`, `CHUNK_OVERLAP`, `MIN_IMAGE_SIZE`, `BASE_DIR`, `ENV_PATH`, `OUTPUT_TEXT`, `OBSIDIAN_VAULT_DIR`, `OBSIDIAN_CACHE_FILE`

**Types:**
- Standard library types with `| None` union syntax (Python 3.10+): `self._vectorstore: FAISS | None = None`
- `list[str]`, `dict[str, Any]`, `Set[str]`
- Pydantic models for structured LLM output: `MatchedNotes(BaseModel)`

## Code Style

**Formatting:**
- No auto-formatter config detected (no `.prettierrc`, no `pyproject.toml` with `[tool.black]`)
- Inconsistent formatting: some files use 4-space indentation (standard), all appear PEP 8 compliant
- Long lines exist (e.g., `main.py:121-130` — long f-strings with HTML)
- No type checker config detected (but `# pyrefly: ignore` comments suggest Pyrefly usage)

**Linting:**
- **Pyrefly** type checker referenced in inline ignores:
  - `# pyrefly: ignore [missing-import]` (in `rag_agent.py:10-23`, `text_chunker.py:6-13`) — silencing import errors for langchain packages
- No ESLint, Flake8, or Ruff config detected

## Import Organization

**Order (observed pattern):**
1. Standard library imports (`os`, `logging`, `re`, `json`, `pathlib`, `typing`, `io`, `asyncio`)
2. Third-party library imports (`streamlit`, `langchain_*`, `pydantic`, `dotenv`, `pymupdf`, `PIL`, `edge_tts`, `requests`)
3. Local module imports (`import extract_text as et`, `from config import ...`)

**Examples from codebase:**
```python
# rag_agent.py — Standard
import os
import logging
from typing import Any
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

# Third-party with type checker ignores
# pyrefly: ignore [missing-import]
from langchain_community.vectorstores import FAISS
# pyrefly: ignore [missing-import]
from langchain_core.chat_history import InMemoryChatMessageHistory
# ...

# Local
import extract_text as et
import text_chunker as tc
from config import EMBEDDING_MODEL, VECTORSTORE_DIR, FAISS_INDEX_FILE, LLM_MODEL, RETRIEVAL_K
```

**Path Aliases:**
- None detected. All imports use relative file paths or direct module references.

## Error Handling

**Patterns:**
- **Return error values instead of raising:** `rag_agent.py` methods return `ChatResult(answer="", error="...")` or `{"success": False, "error": "..."}` dicts
- **Retry with key rotation:** 3 attempts with Groq API key rotation on 429/rate_limit errors
- **Try/except with fallback:** Return empty string, empty list, or `None` on failure
- **Graceful degradation:** `audio_service.text_to_speech()` returns `b""` on failure; `extract_text.py` continues with next page/image on individual failures
- **`Exception` catch-all:** Almost all except clauses catch bare `Exception` — no fine-grained exception handling

Example (preferred pattern from `rag_agent.py`):
```python
try:
    # ... operation
    return {"success": True, ...}
except Exception as e:
    return {"success": False, "error": str(e)}
```

## Logging

**Framework:** `logging` module with `logging.basicConfig` in `config.py`

**Patterns:**
- Mix of two approaches throughout the codebase:
  1. **Proper logging** (`logger.info/warning/error`) — used in `config.py`, `audio_service.py`
  2. **Bare print()** — used heavily in `rag_agent.py`, `text_chunker.py`, `extract_text.py`, `graph_rag.py`, `linker_trigger.py`

**Inconsistent patterns in single file (rag_agent.py):**
```python
# print-based debugging (lines 202, 207, 330, etc.)
print(f"[RAGAgent] Reformulated conversational query: ...")
print(f"[RAGAgent Rate Limit] ...")

# logging-based (line 109)
logger.info(f"[RAGAgent Key Rotation] Rotated key index: ...")
```

**Log prefixes used:**
- `[RAGAgent ...]`, `[ERROR]`, `[WARNING]`, `[INFO]`, `[SUCCESS]`, `[GraphRAG ...]`, `[Linker Trigger ...]`, `[TTS DEBUG]`, `[TTS Error]`

## Comments

**When to Comment:**
- Docstrings on classes (e.g., `RAGAgent` docstring: "RAG pipeline: ingest PDFs, retrieve chunks, answer with history.")
- Docstrings on most public methods (e.g., `rotate_groq_key`, `reload`, `run_ingestion`, `save_concepts_to_obsidian`, `sync_obsidian_vault`, `get_index_status`)
- Section headers within long functions (e.g., `text_chunker.py:18-20` — `# CONFIG`)
- Inline comments explaining "why" not "what" (e.g., `# Space out requests naturally to avoid hitting the burst RPM limit`)

**JSDoc/TSDoc:**
- Not applicable (Python project)

**Docstring Style:**
- Triple-quoted `"""docstring"""` for classes and public methods
- Single-line for simple methods, multi-line for complex ones
- Some docstrings include parameter and return descriptions (e.g., `save_concepts_to_obsidian`)
- Some are minimal/absent (e.g., `_get_session_history`, `_load_chain` have no docstrings)

## Function Design

**Size:**
- Ranges from very small (1-3 lines) to very large (60+ lines)
- Large functions: `ask_stream()` (~137 lines), `ask()` (~120 lines), `main()` in `text_chunker.py` (~129 lines), `main()` in `main.py` (~330 lines)
- Some functions contain significant duplicated logic between `ask()` and `ask_stream()` (meta query handling, context building, retry logic)

**Parameters:**
- Keyword arguments with defaults preferred: `def ask(self, question: str, session_id: str = "default_session", mode: str = "pdf", chat_history: list = None) -> ChatResult`
- 3-5 parameters per function typical; up to 6 in some cases
- Mutable default argument anti-pattern: `citations: list = None` (handled correctly with None check, but `chat_history: list = None` appears)

**Return Values:**
- Public methods return structured types: `ChatResult`, `dict`, `bool`
- Generator methods: `ask_stream()` uses `yield` for streaming
- Error returns: consistent `{"success": bool, "error": str}` dict pattern

## Module Design

**Exports:**
- No `__init__.py` or `__all__` definitions
- Each module exposes its `main()` function and supporting utilities
- Symmetric module structure: each module has `main()` that can run standalone

**Barrel Files:**
- None detected

**Module Independence:**
- `extract_text.py` and `text_chunker.py` have `if __name__ == "__main__": main()` guards for standalone execution
- `linker_trigger.py` has test execution at bottom
- `test_audio.py` is standalone test script (not importable as module)
- `config.py` has side effects at import time (directory creation, env loading, .env copying)

**Config coupling:**
- Most modules directly import constants from `config.py` — tight coupling to global config
- No dependency injection or config objects passed between modules

---

*Convention analysis: 2026-06-06*
