# Codebase Concerns

**Analysis Date:** 2026-06-06

## Tech Debt

### Duplicated Complex Logic Between `ask()` and `ask_stream()`

**Issue:** The entire retrieval pipeline (meta query detection, checkbox scanning, PDF retrieval, Obsidian retrieval, hybrid context building) is duplicated verbatim between `rag_agent.py:ask()` (lines 255-374) and `rag_agent.py:ask_stream()` (lines 376-514). Changes to one must be manually mirrored to the other.
**Files:** `rag_agent.py` (lines 255-374 vs 376-514)
**Impact:** ~200 lines of near-duplicate code. High maintenance burden — bugs fixed in one method will likely remain in the other.
**Fix approach:** Extract shared retrieval logic into a private method `_retrieve_context(standalone_query, mode, citations=None) -> tuple[str, list]` and call it from both `ask()` and `ask_stream()`.

### Hardcoded Absolute Path to External Project

**Issue:** `linker_trigger.py` references `c:\Users\saraf\Desktop\projects\obsidian-linker\main.py` as a hardcoded absolute Windows path. This is not portable.
**Files:** `linker_trigger.py` (lines 12, 44)
**Impact:** The application will crash on any machine where the obsidian-linker project is not at this exact path.
**Fix approach:** Add `OBSIDIAN_LINKER_PATH` env var in `.env`, with a relative fallback like `../obsidian-linker/main.py`, or make the path discoverable via a project-level config.

### Config Module Side Effects at Import Time

**Issue:** `config.py` performs I/O at import time: `.env` copying from sibling project, directory creation (`INPUT_PDF_DIR`, `OUTPUT_DIR`), and `load_dotenv()`.
**Files:** `config.py` (lines 17-33)
**Impact:** Any module importing from config triggers filesystem side effects. Makes testing difficult (importing for constants creates directories). Circular dependency with `.env` auto-copy could fail silently in CI.
**Fix approach:** Move side effects into an `init()` function called explicitly from `main.py` on startup.

### Print-Based Debugging Everywhere

**Issue:** Heavy use of `print()` instead of `logging` throughout `rag_agent.py`, `text_chunker.py`, `extract_text.py`, `graph_rag.py`, `linker_trigger.py`. Mixed usage within single files (e.g., `rag_agent.py` uses both `logger.info()` and `print()`).
**Files:** `rag_agent.py` (~15+ print calls), `text_chunker.py` (~20+), `extract_text.py` (~10+), `graph_rag.py` (~15+), `linker_trigger.py` (~8+)
**Impact:** `print()` output cannot be filtered by severity, has no timestamps, and clutters stdout. Makes production debugging difficult.
**Fix approach:** Replace every `print()` with the appropriate `logger.log()` call. Add `__name__` logger to each module.

### RAGAgent Has Too Many Responsibilities

**Issue:** `rag_agent.py` at 683 lines is a monolithic class handling: ingestion orchestration, vector retrieval, LLM chain management, streaming, query reformulation, meta-query detection, checkbox scanning, note compilation to Obsidian, audio transcription delegation, TTS, key rotation, index status tracking, session management.
**Files:** `rag_agent.py`
**Impact:** Violates Single Responsibility Principle. Hard to test, modify, or extend without risk of regression.
**Fix approach:** Split into focused modules: `retriever.py` (retrieval + meta queries), `conversation.py` (history + reformulation), `sync_service.py` (index/vault sync), `note_service.py` (Obsidian note compilation).

### `allow_dangerous_deserialization=True` on FAISS Load

**Issue:** Every `FAISS.load_local()` call passes `allow_dangerous_deserialization=True` (3 locations). This allows arbitrary pickle deserialization.
**Files:** `rag_agent.py:88`, `text_chunker.py:216`, `graph_rag.py:72`
**Impact:** If an attacker can write to the `faiss_index/` directory, they can achieve arbitrary code execution on load. Risk is low for local-only use but technically a security concern.
**Fix approach:** Add a config flag with a clear warning. Consider switching to FAISS's JSON-based serialization if available.

## Known Bugs

### CSS Selector for User Chat Bubbles Broken

**Issue:** The CSS selector `:has(div[role="img"]:contains("👤"))` in `assets/style.css:137-139` uses `:contains()` which is not a standard CSS pseudo-class and is not supported by any modern browser. The `:nth-child(odd)` fallback is unreliable because Streamlit may interleave system messages.
**Files:** `assets/style.css` (lines 137-142)
**Symptoms:** User chat messages may not receive the intended background styling (`#27272a`), making them indistinguishable from assistant messages.
**Workaround:** None. Visual distinction between user and assistant messages may be inconsistent.
**Fix approach:** Streamlit renders user messages with `data-testid="chatAvatarIcon-user"`. Use `[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"])` instead.

### Empty Transcript Returns But No Guard in Voice Mode

**Issue:** If `transcribe_audio` returns empty string (API error, silent audio, unsupported format), the code checks `if transcribed_text.strip()` but the fallback only shows a `st.warning`. However, if the user clicks "Stop & Submit" without speaking, the toast "Heard: " with empty text is briefly shown before the warning.
**Files:** `main.py` (lines 322-326)
**Symptoms:** Brief toast showing empty text, then warning. Not a crash but confusing UX.
**Fix approach:** Add early return `if not transcribed_text.strip(): st.warning(...); return` before the toast.

## Security Considerations

### `unsafe_allow_html=True` Throughout Main UI

**Issue:** `main.py` uses `unsafe_allow_html=True` in multiple `st.markdown()` calls for CSS injection and formatted HTML badges (source pills, sidebar headers). While the current code only passes application-controlled strings, future changes that interpolate user content could create XSS vectors.
**Files:** `main.py` (lines 24, 38-61, 88, 108, 117, 205-216)
**Risk:** Cross-site scripting (XSS) if user question or uploaded file names are rendered via `unsafe_allow_html=True`.
**Current mitigation:** Only application-controlled strings are used (CSS, hardcoded HTML templates, file names from upload widget).
**Recommendations:** Never pass user-provided content through `unsafe_allow_html`. For file names, use `st.markdown(f"...{st.text(file_name)}...")` or escape HTML entities.

### API Keys in Environment Variables

**Issue:** Two API keys (Groq, Google) stored in `.env` in plaintext. Keys are printed in debug/log output (noted in `audio_service.py:129` — `logger.info(f"STT Result: ...")` but not the key itself). Groq key is cycled due to rate limits.
**Risk:** Key exposure via log files, stdout capture, or `.env` leakage.
**Current mitigation:** `.env` is in `.gitignore`.
**Recommendations:** Consider using a secrets manager for production, or at minimum add key masking in log output.

### Hardcoded File Path Leaks Developer Info

**Issue:** `linker_trigger.py:12` contains the developer's full username (`saraf`) and directory structure in a hardcoded path.
**Files:** `linker_trigger.py` (lines 12, 44)
**Risk:** Information disclosure if this code is shared.
**Fix approach:** Parameterize the path via env var (same fix as tech debt item above).

## Performance Bottlenecks

### Sequential LLM Calls in Critical Path

**Issue:** The `_get_standalone_question()` method makes an additional Groq API call (to `llama-3.1-8b-instant`) before the main retrieval. This adds 200-500ms latency to every user question that has chat history, even for simple follow-ups.
**Files:** `rag_agent.py` (lines 160-211)
**Improvement path:** Cache the standalone query if the user question is a direct follow-up. Or skip LLM-based reformulation for simple references ("tell me more", "explain further").

### ThreadPoolExecutor Overhead for Small PDFs

**Issue:** `extract_text.py` always uses a `ThreadPoolExecutor(max_workers=4)` even for single-page PDFs. The overhead of thread pool creation (~10-20ms) may exceed parallelization benefit for small documents.
**Files:** `extract_text.py` (lines 81, 110)
**Improvement path:** Add a conditional: `if num_pages <= 2: process sequentially; else: use thread pool`.

### Rate-Limit Throttling on Embeddings

**Issue:** `text_chunker.py:create_vectorstore()` embeds chunks with `time.sleep(0.15)` between each and `max_workers=2` to avoid rate limits. For large PDFs (100+ chunks), this takes 15+ seconds.
**Files:** `text_chunker.py` (lines 143-166)
**Improvement path:** Use exponential backoff only on actual rate-limit errors rather than fixed per-chunk delay. Or batch embeddings if the API supports it.

## Fragile Areas

### `.linker_cache.json` Format Dependency

**Issue:** `graph_rag.py` relies on the exact JSON structure produced by `obsidian-linker/main.py`. If the linker changes its output format (key names, nesting), the graph retrieval silently breaks.
**Files:** `graph_rag.py` (lines 25-48, 169-182, 236-241)
**Why fragile:** Only the `"files"`, `"concepts"`, and `"links"` keys are used. No schema validation on load. The cache file is produced by an external project with no versioning contract.
**Fix approach:** Add Pydantic model for cache validation on load. Add a version key to the cache format.

### `docstore._dict` Private Attribute Access

**Issue:** `rag_agent.py:649` and `text_chunker.py:219` access `vectorstore.docstore._dict` — a private/protected attribute of the FAISS wrapper. This is an internal implementation detail of LangChain's FAISS integration.
**Files:** `rag_agent.py:649`, `text_chunker.py:219`
**Why fragile:** LangChain version bumps may rename or restructure internal attributes without notice.
**Fix approach:** Use the public API (`vectorstore.index_to_docstore_id`, `vectorstore.docstore.search`) instead of accessing `_dict` directly.

### `edge_tts` Async Wrapper

**Issue:** `audio_service.py:67-76` runs an async function synchronously via `asyncio.run()`. If the Streamlit event loop is already running (e.g., in async Streamlit mode), this will raise a `RuntimeError`.
**Files:** `audio_service.py` (lines 67-76)
**Why fragile:** Works in default Streamlit sync mode but will break if Streamlit's `runner.fastReruns` or async execution is enabled.
**Fix approach:** Use `asyncio.run_coroutine_threadsafe()` or check for running event loop.

**Test coverage:** Audio service has no automated tests (only the manual `test_audio.py` roundtrip script).

## Scaling Limits

**Chat History:**
- **Current capacity:** Unlimited (in-memory dict grows unbounded with each session's conversation)
- **Limit:** Memory exhaustion after long sessions with many messages; no truncation or summarization
- **Scaling path:** Add message windowing (keep last N messages) or summarization after N turns

**FAISS Index:**
- **Current capacity:** Single local FAISS index for all PDFs
- **Limit:** FAISS in-memory index size limited by available RAM; `faiss-cpu` uses flat (brute-force) indexing by default
- **Scaling path:** For >10k documents, consider IVF or HNSW index types, or a persistent vector database

**Obsidian Vault:**
- **Current capacity:** Scanned on demand via `_load_cache()`
- **Limit:** No hard limit, but LLM note selection prompt accepts only candidate notes (pre-filtered to ~10-12)
- **Scaling path:** Already well-designed with FAISS pre-filtering before LLM selection

## Dependencies at Risk

**`langchain-community` FAISS:**
- **Risk:** `langchain-community` is a community-maintained package with frequent breaking changes. The FAISS wrapper (`FAISS.load_local`, `FAISS.from_embeddings`, `merge_from`) has changed APIs across versions.
- **Impact:** Version bumps of `langchain-community` or `faiss-cpu` may break saving/loading of indices.
- **Migration plan:** Pin `langchain-community==0.0.10` or migrate to `langchain-huggingface` for vector store.

**`streamlit-mic-recorder`:**
- **Risk:** Third-party Streamlit component by a single maintainer. May not keep pace with Streamlit API changes.
- **Impact:** Voice input feature breaks if component is incompatible with newer Streamlit versions.
- **Migration plan:** Replace with `streamlit-audio-recorder` or native `st.audio_input()` (if/when available).

## Missing Critical Features

**No automated test coverage:**
- **Problem:** Zero unit tests, zero integration tests with assertions. `test_audio.py` is a manual visual-inspection script.
- **Blocks:** Safe refactoring, CI/CD pipeline, regression detection.
- **Fix:** Add `pytest` with `pytest-mock` for unit tests covering `RAGAgent.ask()`, `extract_text.extract_page_hybrid()`, `graph_rag.select_relevant_notes()` (with mocked LLM).

**No graceful API key error handling for GOOGLE_API_KEY:**
- **Problem:** `image_text.py:18` raises `ValueError` with bare `raise` if key is missing — unhandled in `extract_text.py` worker thread, causing the thread to fail silently.
- **Files:** `image_text.py:17-18`, `extract_text.py:76-77`
- **Impact:** OCR silently fails on all images if Google API key is missing or invalid, with only a generic warning.

## Test Coverage Gaps

**Untested area:** All production modules
| What's not tested | Files | Risk | Priority |
|---|---|---|---|
| RAGAgent `ask()` / `ask_stream()` | `rag_agent.py` | Core retrieval/generation logic can break silently | High |
| PDF text extraction + OCR | `extract_text.py`, `image_text.py` | Extraction quality regressions | High |
| Text chunking + embedding | `text_chunker.py` | Index quality, chunk boundary issues | Medium |
| GraphRAG note selection | `graph_rag.py` | LLM prompt changes reduce relevance | Medium |
| Audio TTS + STT | `audio_service.py` | Voice features degrade | Low |
| Subprocess linker trigger | `linker_trigger.py` | Sync failures undetected | Low |

---

*Concerns audit: 2026-06-06*
