# Obsidian & PDF Study Brain — Overhaul & Cloud Migration

**What this is:** An agentic RAG (Retrieval-Augmented Generation) application with a Streamlit UI that queries PDF textbooks and Obsidian markdown notes using Pinecone vector search, Neo4j Graph traversal, and LLM orchestration (Groq + Gemini).

**Core value:** Seamlessly blend knowledge from Obsidian vault and uploaded PDFs to provide contextual, cited answers about study materials — now fully untethered from local disk and ready for cloud deployment.

## Requirements

### Validated & Completed (Overhaul & Cloud Phase)
- **Vector Store Migration**: Replaced local FAISS with **Pinecone** for cloud-based vector similarity search across both PDF materials and Obsidian notes.
- **Graph Store Migration**: Integrated **Neo4j** to persist the Obsidian concept graph natively in the cloud instead of relying on a local JSON cache.
- **Cloud Deployment Integration**: Added `git_sync.py` to automatically clone/pull the Obsidian Vault from a private GitHub repository on Streamlit Community Cloud startup.
- **Voice Assistant**: Implemented voice input (mic-recorder) with transcription/translation and Text-To-Speech (edge-tts).
- **LangChain/LangGraph Agent**: Upgraded the RAG pipeline to an agentic architecture (`create_react_agent`) using Groq `llama-3.3-70b-versatile`.
- **Dynamic Graph Queries**: GraphRAG successfully extracts dynamic relationships from Neo4j edges and passes them as explicit LLM context.
- **Obsidian Sync**: "Compile & Save to Obsidian" functionality is fully integrated and successfully triggers background linker processing.

### Active (Pending Optimizations)
- PERFORM-01: Implement conversation windowing (keep last N messages, summarize after N turns).
- TEST-01: Add pytest integration for the newly migrated Pinecone & Neo4j components.
- ADR-01: Adopt Pydantic models for stricter Neo4j and Pinecone data access validation.

### Out of Scope
- Security hardening (XSS, complex multi-tenant API key isolation) — deferred.
- Multi-user support — single-user application.
- Alternative vector databases — Pinecone is now the established standard for this project.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Migrate to Pinecone & Neo4j | Required for cloud deployment (Streamlit Cloud resets local disk state) | **Completed** |
| Obsidian Git Sync | Streamlit Cloud cannot access the local file system. A private GitHub repo ensures the agent has access to raw markdown. | **Completed** |
| Relax Tool Calling constraints | Groq's API was throwing `Failed to call a function` errors due to zero-argument tools and strict system messages. | **Completed** |

## Evolution

This document evolves at phase transitions and milestone boundaries.

---

*Last updated: 2026-06-08 after Cloud Architecture Migration*
