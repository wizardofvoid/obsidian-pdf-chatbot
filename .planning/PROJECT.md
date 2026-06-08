# Obsidian & PDF Study Brain — Overhaul

**What this is:** A local RAG (Retrieval-Augmented Generation) application with a Streamlit UI that queries PDF textbooks and Obsidian markdown notes using FAISS vector search and LLM (Groq + Gemini).

**Core value:** Seamlessly blend knowledge from Obsidian vault and uploaded PDFs to provide contextual, cited answers about study materials — all running locally.

## Requirements

### Validated (existing)
- PDF text extraction with PyMuPDF + Gemini OCR
- FAISS vector store for similarity search
- LangChain-based RAG pipeline with Groq LLM
- Obsidian vault sync via external obsidian-linker tool
- GraphRAG for note-level retrieval
- Streamlit chat UI with glassmorphic theme
- Voice input (mic-recorder) + TTS (edge-tts)
- Session management with conversation history
- Streaming responses from LLM
- "Compile & Save to Obsidian" feature

### Active (overhaul requirements)
- REFACTOR-01: Extract shared retrieval logic from ask()/ask_stream() into a private _retrieve_context() method
- REFACTOR-02: Split RAGAgent monolith into focused modules (retriever, conversation, sync, note_service)
- PERFORM-01: Implement parallel embedding (remove fixed 0.15s sleep, use backoff on actual rate limits)
- PERFORM-02: Add conversation windowing (keep last N messages, summarize after N turns)
- BUGFIX-01: Fix CSS selector for user chat bubbles (replace :contains() with data-testid selector)
- BUGFIX-02: Fix empty transcript guard in voice mode (early return before toast)
- BUGFIX-03: Parameterize hardcoded obsidian-linker path via env var
- BUGFIX-04: Move config side effects into explicit init() function
- DX-01: Replace all print() with logger calls throughout all modules
- DX-02: Add portable env var config for all hardcoded paths
- TEST-01: Add pytest with unit tests for RAGAgent.ask() (mocked LLM)
- TEST-02: Add tests for extract_text PDF extraction + OCR
- TEST-03: Add tests for text_chunker embedding pipeline
- TEST-04: Add tests for graph_rag note selection (mocked LLM)
- TEST-05: Add integration tests for full RAG pipeline
- ADR-01: Adopt Pydantic models for FAISS docstore access (replace _dict private attr access)
- ADR-02: Adopt Pydantic models for linker_cache.json validation

### Out of Scope
- Security hardening (FAISS deserialization, XSS, API key masking) — deferred
- Multi-user support — single-user desktop app
- Remote/server deployment — local-only
- Alternative vector databases (Chroma, Pinecone) — keep FAISS
- CI/CD pipeline — no cloud deployment target

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Keep existing tech stack | No need to change working stack (Streamlit + LangChain + FAISS + Groq) | — Pending |
| Security deferred | User explicitly opted out of security work for this pass | — Pending |
| Standard granularity | 5-8 balanced phases for the overhaul | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

---

*Last updated: 2026-06-06 after initialization*
