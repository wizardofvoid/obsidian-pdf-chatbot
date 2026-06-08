---
phase: 02-retrieve-shared
plan: 01
subsystem: rag
tags: [refactoring, retrieval, deduplication, meta-query, pdf-search, graphrag]
requires:
  - phase: 01-config-logging-portable-paths
    provides: clean logging, portable path config, no print() statements
provides:
  - Shared _retrieve_context() method eliminating ~200 lines of duplicated retrieval logic
  - ask() and ask_stream() both delegate to _retrieve_context()
affects: [03-split-monolith]
tech-stack:
  added: []
  patterns:
    - "Delegation pattern: shared _retrieve_context() with citations-guards for streaming differences"
    - "Single-responsibility retrieval method that both invoke and stream flows call"
key-files:
  created: []
  modified:
    - rag_agent.py
key-decisions:
  - "Uses citations is not None guards rather than separate methods for ask vs ask_stream paths"
  - "Chunks list returned for ask(); ignored via _ for ask_stream() which only needs context_text"
requirements-completed: [REFACTOR-01]
duration: 8min
completed: 2026-06-06
---

# Phase 2 Plan 1: Refactor — Shared Retrieval Summary

**Extract ~200 lines of duplicated retrieval logic from ask() and ask_stream() into a shared _retrieve_context() method**

## Performance

- **Duration:** 8 min
- **Started:** 2026-06-06T21:30:00Z
- **Completed:** 2026-06-06T21:38:00Z
- **Tasks:** 3
- **Files modified:** 1

## Accomplishments

- Added `_retrieve_context()` method that handles meta-queries (checkbox scan, PDF listing, Obsidian notes listing), PDF similarity search, and Obsidian GraphRAG retrieval in a single shared code path
- Refactored `ask()` to delegate to `_retrieve_context()` — replaces ~88 lines of inline retrieval with a single call
- Refactored `ask_stream()` to delegate to `_retrieve_context()` with `citations` parameter for inline citation population — replaces ~100 lines
- Difference between ask/ask_stream handled via `citations is not None` guards in the shared method
- File reduced from 683 to 618 lines (65 lines net reduction, ~179 lines of duplication removed)

## Task Commits

| Task | Name | Commit |
|------|------|--------|
| 1-3 | Extract _retrieve_context(), refactor ask() and ask_stream() | `23c69ee` |

**Plan metadata:** (pending)

## Files Created/Modified

- `rag_agent.py` — +114 / -179 lines. New `_retrieve_context()` method, both `ask()` and `ask_stream()` simplified to call it.

## Decisions Made

- **`citations is not None` guards** rather than separate methods: The only behavioral difference between `ask()` and `ask_stream()` is that `ask_stream()` populates a `citations` list inline during retrieval. Using an optional `citations` parameter with `is not None` checks keeps one shared method instead of two variants.
- **`chunks` list still returned for `ask()`**: `ask()` needs the chunks for `ChatResult.context_chunks`. `ask_stream()` ignores the second return value via `_`.
- **Single commit** for all three tasks: Since the method extraction and both callers' refactoring are interdependent (you can't commit the new method without updating the callers), all changes were made and verified together.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

- Verification 5 (import check) failed with `ModuleNotFoundError: No module named 'langchain_community'` — this is a pre-existing environment dependency issue, not a regression from our changes. All structural and syntax checks passed.

## TDD Gate Compliance

N/A — this plan does not use TDD.

## Known Stubs

None found.

## Threat Flags

None found — no new network endpoints, auth paths, file access patterns, or schema changes introduced.

## Next Phase Readiness

- Retrieval logic is now centralized in `_retrieve_context()` — ready for Phase 3 (Split RAGAgent Monolith into `retriever.py`, `conversation.py`, etc.)
- The shared method provides a clean extraction boundary for splitting into a dedicated `retriever.py` module

---
*Phase: 02-retrieve-shared*
*Completed: 2026-06-06*
