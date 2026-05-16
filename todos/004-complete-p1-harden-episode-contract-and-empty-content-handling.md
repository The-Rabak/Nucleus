---
status: complete
priority: p1
issue_id: "004"
tags: [code-review, data-integrity, reliability, protects-user-story]
dependencies: []
---

# Harden episode contract and empty-content handling

## Problem Statement

Episode handling can crash or violate contract requirements when content/frontmatter is empty or malformed.

## Findings

- `retrieve_use_case.py:52` and `bootcard_use_case.py:74` index first line unsafely (`IndexError` risk).
- `episode_store.py` write frontmatter misses required contract fields (`sensitivity`, `extraction_status`) noted by constitution review.
- `episode_store.py:133-147,175-206` parse path can raise on malformed content and fail entire flow.

## Proposed Solutions

### Option 1: Contract-first validator + safe fallback parsing
**Approach:** Validate/write full required frontmatter and gracefully skip malformed records with explicit diagnostics.
**Pros:** Improves integrity and resilience with moderate change.
**Cons:** Requires clear degraded-output behavior decisions.
**Effort:** Medium
**Risk:** Low

---

### Option 2: Strict fail-fast parser with repair tooling
**Approach:** Reject malformed records and require repair path before operations succeed.
**Pros:** Strong consistency guarantees.
**Cons:** Harsh UX; can block retrieval unnecessarily.
**Effort:** Medium
**Risk:** Medium

## Recommended Action

Implemented contract-complete episode frontmatter writes, safe parsing with malformed-record tolerance, and empty-content-safe statement generation.

## Technical Details

**Affected files:**
- `src/nucleus/adapters/filesystem/episode_store.py`
- `src/nucleus/application/retrieve_use_case.py`
- `src/nucleus/application/bootcard_use_case.py`

## Resources

- `docs/contracts/nucleus-stage-1-contract.md`
- `slice1-python-review`
- `slice1-constitution-review`

## Acceptance Criteria

- [x] Empty/whitespace episode content cannot crash retrieve/bootcard.
- [x] Required episode frontmatter fields are persisted per contract.
- [x] Malformed records degrade safely with explicit warnings.
- [x] Tests cover empty content and malformed markdown/frontmatter.

## Work Log

### 2026-05-14 - Review finding created

**By:** Copilot CLI

**Actions:**
- Consolidated crash + contract + parse robustness findings.

**Learnings:**
- Contract compliance and runtime resilience must be fixed together.

### 2026-05-15 - Resolution completed

**By:** Copilot CLI

**Actions:**
- Added `sensitivity` and `extraction_status` frontmatter fields in episode writes.
- Hardened episode loading to skip malformed/contract-incomplete files safely.
- Replaced unsafe first-line indexing with shared safe statement extraction helpers.
- Added coverage in `tests/unit/test_retrieve_guards.py`.

**Learnings:**
- Content-safety and contract-validity checks should be centralized and reused.

## Notes

- WHY classification: 🎯 PROTECTS USER STORY
