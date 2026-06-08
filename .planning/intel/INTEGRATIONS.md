# External Integrations

**Analysis Date:** 2026-06-06

## APIs & External Services

**LLM (Groq):**
- **Groq Cloud** — Primary LLM inference provider
  - SDK/Client: `langchain-groq` (`ChatGroq`)
  - Endpoint: `https://api.groq.com/openai/v1/chat/completions` (via LangChain)
  - Models: `llama-3.3-70b-versatile` (main), `llama-3.1-8b-instant` (standalone query reformulation, note distillation, GraphRAG note selection)
  - Auth: `GROQ_API_KEY` env var (with rotation support via `GROQ_API_KEY_1` through `_9`)
  - Usage: Main answer generation, conversational query rewriting, note compilation to Obsidian, GraphRAG relevance selection

**Speech-to-Text (Groq Whisper):**
- **Groq Whisper API** — Audio transcription and translation
  - SDK/Client: Raw `requests` HTTP (`audio_service.py` `transcribe_audio`)
  - Endpoint: `https://api.groq.com/openai/v1/audio/transcriptions` or `.../translations`
  - Model: `whisper-large-v3`
  - Auth: Same `GROQ_API_KEY` env var
  - Usage: Voice input transcription (supports Indian languages)

**Embeddings (Google Gemini):**
- **Google Gemini Embeddings API** — Text embedding generation
  - SDK/Client: `langchain-google-genai` (`GoogleGenerativeAIEmbeddings`)
  - Model: `models/gemini-embedding-2`
  - Auth: `GOOGLE_API_KEY` env var (with rotation support via `GOOGLE_API_KEY_1`)
  - Usage: Generating embeddings for PDF text chunks, Obsidian concept notes

**Image OCR (Google Gemini):**
- **Google Gemini Flash API** — Image text extraction
  - SDK/Client: `google-genai` (`genai.Client()`)
  - Model: `gemini-2.5-flash`
  - Auth: Same `GOOGLE_API_KEY` env var
  - Usage: OCR on embedded images in PDFs during text extraction

**Text-to-Speech (Microsoft Edge):**
- **Microsoft Edge Neural TTS** — Read-aloud response synthesis
  - SDK/Client: `edge-tts` (asyncio-based)
  - Voice: `en-IN-NeerjaNeural` (default), with Indian language auto-detection (Hindi, Gujarati, Tamil, Telugu, Bengali, Kannada, Malayalam, Punjabi)
  - Auth: None (free, uses Edge API)
  - Usage: Synthesizing assistant responses as spoken audio

## External Project Dependencies

**Obsidian Linker:**
- Location: `c:\Users\saraf\Desktop\projects\obsidian-linker\main.py` (hardcoded absolute path)
- Integration: Subprocess launch (`subprocess.Popen` async / `subprocess.run` sync)
  - `linker_trigger.trigger_obsidian_linker()` — Background async launch
  - `linker_trigger.run_obsidian_linker_sync()` — Blocking sync run
- Data exchange via filesystem:
  - Output: `.linker_cache.json` in the vault directory (read by `graph_rag.py`)
  - Output: `.linker_faiss_index/` in the vault directory (FAISS vector store of concepts, read by `graph_rag.py`)
- Purpose: Extracts concepts, generates embeddings, builds wikilink graph for Obsidian notes

## Data Storage

**Vector Storage:**
- **FAISS (local)** — Vector index for PDF chunks
  - Location: `faiss_index/` in project root
  - Files: `index.faiss`, `index.pkl` (serialized FAISS index)
  - Loaded with `allow_dangerous_deserialization=True` (`rag_agent.py:88`, `text_chunker.py:216`, `graph_rag.py:72`)
  - Not version-controlled (in `.gitignore`)

**File Storage:**
- **PDF uploads:** `inputPDF/` directory
- **Extracted text cache:** `output/cache/` — per-PDF, per-OCR-mode text files
- **Combined output:** `output/output.txt`
- All local filesystem only; no cloud storage integration

**Caching:**
- `st.cache_resource` for RAGAgent singleton (Streamlit)
- Filesystem-based cache for extracted PDF text (mtime-based invalidation)
- `langchain_core.chat_history.InMemoryChatMessageHistory` for session history (in-memory only, lost on restart)

## Authentication & Identity

**Auth Provider:**
- **Custom (API Key based):** No user authentication
- API keys read from `.env` file
- No OAuth, no JWT, no user identity management

## Monitoring & Observability

**Error Tracking:**
- None (no Sentry/DataDog/etc.)
- Logging to stdout/stderr via `print()` and `logging` module

**Logs:**
- `logging.basicConfig` set in `config.py` (INFO level, `%(asctime)s - %(name)s - %(levelname)s - %(message)s`)
- Heavy use of `print()` for debug/status output throughout all modules
- No structured logging, no log aggregation
- Console-only output (no log files)

## CI/CD & Deployment

**Hosting:**
- Local desktop only (`streamlit run main.py`)
- No production hosting configuration

**CI Pipeline:**
- None detected

## Environment Configuration

**Required env vars:**
- `GROQ_API_KEY` (or `GROQ_API_KEY_1` through `_9`)
- `GOOGLE_API_KEY` (or `GOOGLE_API_KEY_1`)

**Optional env vars:**
- `OBSIDIAN_VAULT_DIR` — defaults to `./ObsidianVault`
- `LLM_MODEL` — defaults to `llama-3.3-70b-versatile`

**Secrets location:**
- `.env` file in project root (in `.gitignore`)
- Auto-copied from `../obsidian-linker/.env` at module import time in `config.py`

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- None

---

*Integration audit: 2026-06-06*
