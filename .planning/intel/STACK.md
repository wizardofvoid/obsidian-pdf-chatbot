# Technology Stack

**Analysis Date:** 2026-06-06

## Languages

**Primary:**
- Python 3.9+ — All application code

**Secondary:**
- CSS 3 — Custom premium dark theme (`assets/style.css`, 179 lines)
- SVG — Inline chat avatars with CSS animations (`main.py` lines 265-266)
- Markdown — Obsidian vault notes, README documentation

## Runtime

**Environment:**
- Python 3.9+ (CPython)
- Virtual environment via conda/venv (ambient `python` picked from `sys.executable`)

**Package Manager:**
- `pip` with `requirements.txt`
- Lockfile: Not detected (no `requirements.lock`, `poetry.lock`, or `Pipfile.lock`)

## Frameworks

**Core:**
- **Streamlit** 1.35+ — Frontend UI framework (`main.py`, `.streamlit/config.toml`)
- **LangChain** 0.1+ — RAG pipeline orchestration (`rag_agent.py`, `text_chunker.py`)
  - `langchain-core` — Prompt templates, output parsers, runnables, message history
  - `langchain-community` — FAISS vector store integration
  - `langchain-google-genai` — Google Gemini embeddings
  - `langchain-groq` — Groq LLM chat models
  - `langchain-text-splitters` — Recursive character text splitting
- **FAISS** 1.8+ — Local vector similarity search (`faiss_index/` directory)

**LLM & Embeddings:**
- **Groq** — Primary LLM provider (`llama-3.3-70b-versatile` default, `llama-3.1-8b-instant` for auxiliary tasks)
- **Google Gemini** — Embeddings (`models/gemini-embedding-2`) and image OCR (`gemini-2.5-flash`)

**Audio & Speech:**
- **edge-tts** 7.2+ — Microsoft Edge Neural TTS (read-aloud responses)
- **Groq Whisper API** (`whisper-large-v3`) — Speech-to-text transcription and translation
- **`streamlit-mic-recorder`** 0.1.4+ — Microphone recording widget
- **gTTS** (development/test only in `test_audio.py`) — Google Text-to-Speech test harness

**PDF & Image Processing:**
- **PyMuPDF** (fitz) 1.24+ — PDF page text/table/image extraction (`extract_text.py`)
- **Pillow** 10.0+ — Image opening, resize checks for OCR (`image_text.py`)
- **Google GenAI SDK** (`google-genai`) — Gemini API client for image OCR

**Other:**
- `python-dotenv` 1.0+ — Environment variable loading
- `pydantic` 2.0+ — Structured output schemas (`graph_rag.py`)
- `tiktoken` 0.6+ — Token-aware text splitting (LangChain `from_tiktoken_encoder`)
- `requests` — HTTP client (Groq Whisper API calls in `audio_service.py`)

## Configuration

**Environment:**
- `.env` file in project root (loaded via `python-dotenv` in `config.py`)
- Automatic `.env` copy from sibling `obsidian-linker/` project if absent

**Required env vars:**
| Variable | Purpose |
|----------|---------|
| `GROQ_API_KEY` | Groq LLM + Whisper API key |
| `GOOGLE_API_KEY` | Google Gemini embeddings + image OCR API key |
| `OBSIDIAN_VAULT_DIR` | Path to Obsidian vault (optional, defaults to `./ObsidianVault`) |
| `LLM_MODEL` | Groq model name (optional, defaults to `llama-3.3-70b-versatile`) |

**Key rotation support:** `GROQ_API_KEY_1` through `GROQ_API_KEY_9` as fallback/rotation keys; similarly `GOOGLE_API_KEY_1`.

**Build/Dev:**
- `.streamlit/config.toml` — Streamlit theme overrides (dark theme)
- No TypeScript/Webpack/Babel configs present

## Platform Requirements

**Development:**
- Python 3.9+
- pip with virtual environment
- API keys for Groq and Google Gemini
- Windows (hardcoded path patterns suggest Windows dev machine, but cross-platform compatible)

**Production:**
- Local desktop deployment via `streamlit run main.py`
- Not designed for remote/server deployment (no `secrets.toml`, no nginx config)

---

*Stack analysis: 2026-06-06*
