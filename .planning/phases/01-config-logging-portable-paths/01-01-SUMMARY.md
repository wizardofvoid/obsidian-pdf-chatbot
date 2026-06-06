---
phase: 01-config-logging-portable-paths
plan: 01
subsystem: config
tags: [logging, config, environment-variables, paths]

requires: []
provides:
  - "config.init() function — explicit I/O initialization, safe import"
  - "OBSIDIAN_LINKER_PATH env var with sensible fallback"
  - "logger-based diagnostics in linker_trigger.py and main.py"
  - "Zero print() calls in linker_trigger.py and main.py"
affects:
  - "01-02-PLAN.md — Print→Logger Migration: Core Modules"
  - "01-03-PLAN.md — Print→Logger Migration: Remaining Modules"

tech-stack:
  added: []
  patterns:
    - "Explicit init() pattern for config modules with I/O side effects"
    - "Env var overrides with Path-based fallbacks for portable paths"
    - "Module-level logger pattern (logging.getLogger(__name__))"

key-files:
  created: []
  modified:
    - config.py
    - linker_trigger.py
    - main.py

key-decisions:
  - "config.init() consolidates all I/O side effects (mkdir, .env copy) — import is side-effect-free"
  - "OBSIDIAN_LINKER_PATH env var defaults to sibling obsidian-linker/main.py with Path-typed return"
  - "print() replaced with logger.debug() for TTS diagnostics (debug-level, not info)"
  - "%s format strings used instead of f-strings in logger calls (lazy evaluation)"

patterns-established:
  - "Config module follows init()-after-import pattern: define constants first, call init() explicitly"
  - "Logger calls strip bracket-prefix tags (e.g., [CONFIG], [TTS DEBUG]) — %(name)s provides module identity"
  - "Path constants use env var overrides with Path() wrapping and str()-based fallbacks"

requirements-completed: [BUGFIX-03, BUGFIX-04, DX-01, DX-02]

duration: ~5min
completed: 2026-06-06
---

# Phase 01 Plan 01: Config Foundation — Config init(), OBSIDIAN_LINKER_PATH, Print→Logger Migration

**config.init() eliminates import-time side effects, OBSIDIAN_LINKER_PATH replaces hardcoded Windows path, and print()→logger() migrations in linker_trigger.py and main.py enable filterable, timestamped diagnostics**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-06-06
- **Completed:** 2026-06-06
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

1. **Config init() pattern established** — `config.py` now has an explicit `init()` function that handles `.env` copying, inputPDF/ and output/ directory creation. Importing `config` is completely side-effect-free.
2. **Portable OBSIDIAN_LINKER_PATH** — Added `OBSIDIAN_LINKER_PATH` env var (default: `BASE_DIR.parent / "obsidian-linker" / "main.py"`). `linker_trigger.py` uses it instead of a hardcoded Windows absolute path.
3. **print()→logger() migration** — All 10 `print()` calls in `linker_trigger.py` and all 6 `print()` calls in `main.py` replaced with `logger.info/error/debug()`. Prefix tags like `[TTS DEBUG]` and `[Linker Trigger Error]` stripped — `%(name)s` in the format provides module identity.
4. **main.py startup wired** — `config.init()` called as the first statement in `main()`, ensuring required directories exist before any Streamlet initialization.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create config.init() — consolidate I/O side effects** - `c23681b` (refactor)
2. **Task 2: Add OBSIDIAN_LINKER_PATH to config.py + fix linker_trigger.py** - `d5fe9c1` (feat)
3. **Task 3: Wire config.init() into main.py + replace print→logger** - `77afcb7` (feat)

## Files Modified

- `config.py` (57 lines) — Added `init()` function, `OBSIDIAN_LINKER_PATH` constant; removed module-level `.mkdir()` and `.env` copy (moved into `init()`)
- `linker_trigger.py` (79 lines) — Added `import logging`, `logger = logging.getLogger(__name__)`, imports `OBSIDIAN_LINKER_PATH` from config; replaced hardcoded path with `OBSIDIAN_LINKER_PATH`; replaced `os.path.exists()` with `Path.exists()`; replaced all 10 `print()` calls with `logger.info()/error()`
- `main.py` (402 lines) — Added `import logging`, `import config`, `logger = logging.getLogger(__name__)`, `config.init()` call in `main()`; replaced all 6 TTS `print()` calls with `logger.debug()/error()`

## Verification Results

| # | Check | Result |
|---|-------|--------|
| 1 | `python -c "import config"` — completes silently | ✅ PASS |
| 2 | `OBSIDIAN_LINKER_PATH` shows expected default path | ✅ PASS |
| 3 | `from linker_trigger import trigger_obsidian_linker` | ✅ PASS |
| 4 | Zero `print()` in `linker_trigger.py` (AST) | ✅ PASS |
| 5 | Zero `print()` in `main.py` (AST) | ✅ PASS |
| 6 | `config.py` syntax valid (AST) | ✅ PASS |
| 7 | `linker_trigger.py` syntax valid (AST) | ✅ PASS |
| 8 | `main.py` syntax valid (AST) | ✅ PASS |
| 9 | AST print() check on `main.py` — zero remaining | ✅ PASS |

## Decisions Made

- **config.init() pattern** — All I/O side effects moved to an explicit `init()` function rather than using a lazy-init or property-based approach. This is simpler, more explicit, and aligns with the existing pattern of calling `main()` at entry points.
- **logger.debug() for TTS diagnostics** — TTS is a detail-level operation. Using `logger.debug()` (not `info()`) ensures normal operation is not noisy while still available when debug logging is enabled.
- **%s format strings** — Used instead of f-strings in logger calls to leverage lazy evaluation (formatting only happens when the log level is enabled).

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

- **main.py encoding issue** — The file contains non-UTF-8 bytes (0x8f, likely from SVG data URIs in avatar strings) causing `UnicodeDecodeError` with Python's default `cp1252` codec on Windows. Verification commands updated to use `encoding='utf-8'` explicitly. This is a pre-existing issue in the file, not introduced by this plan's changes.

## Requirements Completed

- **BUGFIX-03** — Replace hardcoded `c:\Users\saraf\...\obsidian-linker\main.py` with `OBSIDIAN_LINKER_PATH` env var
- **BUGFIX-04** — Move config.py I/O side effects (directory creation, .env copy) into explicit `init()` function
- **DX-01** — Replace all `print()` calls with `logger` calls in `linker_trigger.py` and `main.py`
- **DX-02** — Add `OBSIDIAN_LINKER_PATH` env var with sensible default fallback

## Next Phase Readiness

- Phase 01-02 (Print→Logger Migration: Core Modules) can proceed — the logging infrastructure (`logging.basicConfig` in config.py, module-level `logger = logging.getLogger(__name__)` pattern) is now established.
- Phase 01-03 (Print→Logger Migration: Remaining Modules) follows the same pattern already proven in linker_trigger.py and main.py.

## Self-Check: PASSED

All 3 files exist. All 3 commits verified.

---

*Phase: 01-config-logging-portable-paths*
*Plan: 01*
*Completed: 2026-06-06*
