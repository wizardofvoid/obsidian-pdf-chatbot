# Testing Patterns

**Analysis Date:** 2026-06-06

## Test Framework

**Runner:**
- None detected (no `pytest`, `unittest`, or other test runner configuration)
- No `pytest.ini`, `pyproject.toml` test config, `tox.ini`, or `setup.cfg` with test settings

**Assertion Library:**
- None detected (no test files found beyond `test_audio.py`)

**Run Commands:**
- No test commands detected. Application launched via `streamlit run main.py` only.
- No CI pipeline to run tests.

## Test File Organization

**Location:**
- No dedicated test directory (`tests/` or `test/`) exists.
- A single ad-hoc test script: `test_audio.py` at project root (co-located, not in a test directory).

**Naming:**
- `test_*.py` pattern used for the one existing test file.

**Structure:**
```
project-root/
  test_audio.py          # Standalone integration test script
```

## Test Structure

**`test_audio.py` is a standalone integration test script, not a structured test suite:**
- No test classes
- No test functions (no `def test_*`)
- Executed via `if __name__ == "__main__": main()` pattern
- Uses `print()` for results display, no assertions (visual inspection only)

**Pattern (from `test_audio.py`):**
```python
def main():
    test_cases = [
        {"language": "Gujarati", "lang_code": "gu", "text": "નમસ્તે..."},
        {"language": "Hindi", "lang_code": "hi", "text": "नमस्ते..."},
        # ...
    ]
    
    for case in test_cases:
        # Step 1: Text-To-Speech (Generate Audio)
        tts = gTTS(text=text, lang=code)
        tts.save(str(audio_file))
        
        # Step 2: STT Transcription
        transcription = transcribe_audio_groq(audio_bytes, format="mp3", translate=False)
        print(f"[{lang}] Result: '{transcription}'")
        
        # Step 3: STT Translation
        translation = transcribe_audio_groq(audio_bytes, format="mp3", translate=True)
        print(f"[{lang}] Result: '{translation}'")
```

## Mocking

**Framework:**
- None used.

**Patterns:**
- No mocking patterns exist in the codebase.
- All API calls are real (no test doubles for Groq, Google Gemini, or Edge TTS).

## Fixtures and Factories

**Test Data:**
- Inline test data in `test_audio.py`: hardcoded Indian language text strings.
- No fixture files, factory functions, or test data generators.

**Location:**
- `test_audio.py` uses a temporary `temp_test_audio/` directory created at runtime and cleaned up.

## Coverage

**Requirements:**
- No coverage requirements. No `.coveragerc` or `--cov` configuration.

**View Coverage:**
- No coverage tooling available.

## Test Types

**Unit Tests:**
- None. No individual module/function unit tests exist.

**Integration Tests:**
- **`test_audio.py`** — End-to-end TTS→STT roundtrip test for Indian languages (Gujarati, Hindi, Tamil, Telugu, Bengali).
  - Generates audio via gTTS → sends to Groq Whisper → verifies by printing results.
  - No automated pass/fail assertions (human visual inspection).

**E2E Tests:**
- None. Streamlit app requires manual testing through browser UI.

## Common Patterns

**No test patterns exist.** The codebase has no established testing conventions.

**Key testing gaps:**
| Area | Missing | Risk |
|------|---------|------|
| RAGAgent | No unit tests | Changes to retrieval logic may break silently |
| PDF extraction | No tests for page parsing, OCR | Regressions in text quality undetected |
| GraphRAG | No tests for note selection, graph walking | LLM prompt changes may reduce relevance |
| Text chunker | No tests for split quality | Chunk boundaries affect retrieval quality |
| Audio service | No automated assertions | Transcription quality changes undetected |
| Linker trigger | No tests for subprocess management | Path/exe issues only caught at runtime |

---

*Testing analysis: 2026-06-06*
