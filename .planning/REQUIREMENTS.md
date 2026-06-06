# Requirements

## v1 Requirements

### Refactoring
- [ ] **REFACTOR-01**: Extract shared retrieval logic into `_retrieve_context()` method — eliminates ~200 lines of duplication between `ask()` and `ask_stream()`
- [ ] **REFACTOR-02**: Split RAGAgent into `retriever.py`, `conversation.py`, `sync_service.py`, `note_service.py` — each with single responsibility

### Performance
- [ ] **PERFORM-01**: Replace fixed 0.15s sleep in embedding with exponential backoff on actual rate-limit errors
- [ ] **PERFORM-02**: Add conversation windowing — keep last N messages, auto-summarize after N turns

### Bug Fixes
- [ ] **BUGFIX-01**: Fix CSS selector for user chat bubbles — replace `:contains("👤")` with `[data-testid="chatAvatarIcon-user"]`
- [ ] **BUGFIX-02**: Add early return for empty `transcribed_text.strip()` before the toast in voice mode
- [x] **BUGFIX-03**: Replace hardcoded `c:\Users\saraf\...\obsidian-linker\main.py` with `OBSIDIAN_LINKER_PATH` env var
- [x] **BUGFIX-04**: Move config.py I/O side effects (directory creation, .env copy) into explicit `init()` function

### Developer Experience
- [x] **DX-01**: Replace all `print()` calls with `logger.info()/warning()/error()` across all modules
- [x] **DX-02**: Add env var config for all hardcoded paths, with sensible defaults and fallbacks

### Testing
- [ ] **TEST-01**: Unit tests for `RAGAgent.ask()` with mocked LLM chain
- [ ] **TEST-02**: Unit tests for `extract_text.extract_page_hybrid()` with test PDF fixtures
- [ ] **TEST-03**: Unit tests for `text_chunker.create_vectorstore()` and FAISS operations
- [ ] **TEST-04**: Unit tests for `graph_rag.select_relevant_notes()` with mocked LLM
- [ ] **TEST-05**: Integration test for complete RAG pipeline (PDF → chunk → embed → retrieve → answer)

### Architecture & Reliability
- [ ] **ADR-01**: Replace `vectorstore.docstore._dict` private attribute access with public API (`index_to_docstore_id`, `docstore.search`)
- [ ] **ADR-02**: Add Pydantic model for `.linker_cache.json` validation on load

## v2 (Deferred)
- Chat history persistence across sessions
- Multi-file upload batch processing
- Dark/light theme toggle
- PDF annotation export

## Out of Scope
- Security hardening (FAISS dangerous deserialization, XSS mitigation, API key masking)
- Multi-user or server deployment
- Alternative vector databases
- CI/CD pipeline
- UI redesign or theme overhaul

## Traceability

| REQ-ID | Phase | Status |
|--------|-------|--------|
| REFACTOR-01 | | |
| REFACTOR-02 | | |
| PERFORM-01 | | |
| PERFORM-02 | | |
| BUGFIX-01 | | |
| BUGFIX-02 | | |
| BUGFIX-03 | Phase 1 | ✅ Complete |
| BUGFIX-04 | Phase 1 | ✅ Complete |
| DX-01 | Phase 1 | ✅ Complete |
| DX-02 | Phase 1 | ✅ Complete |
| TEST-01 | | |
| TEST-02 | | |
| TEST-03 | | |
| TEST-04 | | |
| TEST-05 | | |
| ADR-01 | | |
| ADR-02 | | |
