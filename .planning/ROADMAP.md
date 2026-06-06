# Roadmap

**Project:** Obsidian & PDF Study Brain
**Initiative:** Full Overhaul (Refactor, Test, Fix, Polish)
**Phases:** 7

---

### Phase 1: Config, Logging & Portable Paths
**Goal:** Eliminate config side effects, migrate print()→logger, and parameterize hardcoded paths so the codebase is portable and debuggable.
**Requirements:** DX-01, DX-02, BUGFIX-03, BUGFIX-04
**Plans:** 3 plans (Wave 1)
**Success Criteria:**
1. `config.py` has an explicit `init()` function; import-time side effects are removed
2. Every `print()` in the codebase is replaced with the appropriate `logger` call
3. `OBSIDIAN_LINKER_PATH` is configurable via env var with sensible fallback
4. Application starts and runs correctly with the changes

Plans:
- [x] 01-01-PLAN.md — Config Foundation: init(), OBSIDIAN_LINKER_PATH, linker_trigger fix+logging, main.py startup+logging
- [ ] 01-02-PLAN.md — Print→Logger Migration: Core Modules (rag_agent, extract_text)
- [ ] 01-03-PLAN.md — Print→Logger Migration: Remaining Modules (text_chunker, graph_rag)

### Phase 2: Refactor RAGAgent — Shared Retrieval
**Goal:** Eliminate the ~200 lines of duplicated retrieval logic between `ask()` and `ask_stream()` by extracting a shared `_retrieve_context()` method.
**Requirements:** REFACTOR-01
**Success Criteria:**
1. `_retrieve_context()` method exists and handles all retrieval modes (PDF, Obsidian, Hybrid)
2. Both `ask()` and `ask_stream()` call `_retrieve_context()` instead of duplicating logic
3. All existing chat functionality works identically (no regression)
4. Acceptance criteria: both streaming and non-streaming answers produce same context

### Phase 3: Refactor RAGAgent — Split Monolith
**Goal:** Split the 683-line RAGAgent into focused modules with single responsibilities.
**Requirements:** REFACTOR-02
**Success Criteria:**
1. `retriever.py` handles all retrieval logic (vector search, meta queries, multi-mode routing)
2. `conversation.py` handles chat history, query reformulation, session management
3. `sync_service.py` handles index management, vault sync, ingestion orchestration
4. `note_service.py` handles Obsidian note compilation and saving
5. `RAGAgent` in `rag_agent.py` imports and delegates to these modules
6. All existing functionality works identically

### Phase 4: Bug Fixes
**Goal:** Fix identified bugs across UI, voice mode, and fragile internals.
**Requirements:** BUGFIX-01, BUGFIX-02, ADR-01, ADR-02
**Success Criteria:**
1. User chat bubbles render with correct background color on all browsers
2. Empty voice transcripts show warning without "Heard: " toast
3. `docstore._dict` private attribute access replaced with public FAISS API
4. `.linker_cache.json` validated with Pydantic model on load

### Phase 5: Performance Optimization
**Goal:** Improve embedding throughput and bound memory growth from unbounded conversation history.
**Requirements:** PERFORM-01, PERFORM-02
**Success Criteria:**
1. Embedding no longer uses fixed per-chunk sleep; uses exponential backoff only on actual rate-limit errors
2. Conversation history windowed to last N messages with auto-summarization
3. Indexing large PDFs is measurably faster (no fixed delay between chunks)

### Phase 6: Test Suite — Unit Tests
**Goal:** Establish test coverage for core logic with mocked external services.
**Requirements:** TEST-01, TEST-02, TEST-03, TEST-04
**Success Criteria:**
1. `pytest` configured with `pytest-mock` and test fixtures
2. Tests for `RAGAgent.ask()` with mocked LLM chain covering success, error, and edge cases
3. Tests for `extract_text.extract_page_hybrid()` with test PDF fixtures
4. Tests for `text_chunker.create_vectorstore()` with mocked embeddings
5. Tests for `graph_rag.select_relevant_notes()` with mocked LLM
6. All tests pass

### Phase 7: Integration Tests & Final Polish
**Goal:** End-to-end integration tests and a comprehensive quality pass.
**Requirements:** TEST-05
**Success Criteria:**
1. Integration test covers complete pipeline: PDF → chunk → embed → retrieve → answer
2. All 7 phases reviewed for completeness and consistency
3. Test suite runs cleanly (`pytest` exits 0)

---

## Milestone View

| Phase | Name | Req Count | Plans | Status |
|-------|------|-----------|-------|--------|
| 1 | Config, Logging & Portable Paths | 4 | 3 | Planned |
| 2 | Refactor — Shared Retrieval | 1 | — | Pending |
| 3 | Refactor — Split Monolith | 1 | — | Pending |
| 4 | Bug Fixes | 4 | — | Pending |
| 5 | Performance Optimization | 2 | — | Pending |
| 6 | Test Suite — Unit Tests | 4 | — | Pending |
| 7 | Integration Tests & Polish | 1 | — | Pending |

**17 requirements** | **7 phases** | All v1 requirements mapped ✓
