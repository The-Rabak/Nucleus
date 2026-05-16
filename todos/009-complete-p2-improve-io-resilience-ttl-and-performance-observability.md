---
status: complete
priority: p2
issue_id: "009"
tags: [code-review, performance, reliability, quality]
dependencies: ["005"]
---

# Improve I/O resilience, TTL behavior, and performance observability

## Problem Statement

File writes are not atomic, TTL is not enforced on read path, and performance observability is insufficient to detect regressions early.

## Findings

- `episode_store.py` writes directly to final path; concurrent reads can observe partial data.
- `ttl_expires_at` is written but not used for filtering/pruning.
- Limited budget/metric instrumentation for bootcard/retrieve hot paths.

## Proposed Solutions

### Option 1: Atomic writes + TTL filtering + lightweight operation metrics
**Approach:** Temp-file rename writes, skip/prune expired records, emit per-op scan/latency counters.
**Pros:** Good reliability/perf signal with moderate complexity.
**Cons:** Adds background maintenance concerns.
**Effort:** Medium
**Risk:** Low

---

### Option 2: Keep current flow and rely on benchmark-only monitoring
**Approach:** Defer runtime hardening and catch regressions via periodic test runs.
**Pros:** Minimal immediate code changes.
**Cons:** Late detection and production-facing fragility.
**Effort:** Small
**Risk:** High

## Recommended Action

Implement Option 1 with minimal surface-area changes:
- keep filesystem persistence atomic (`*.tmp` + `replace`) on episode writes;
- enforce TTL filtering in workspace/profile read paths so expired episodes are skipped for both retrieve and bootcard candidate sets;
- expose operation-level observability payloads with timing plus scan counters on retrieve/bootcard responses.

## Technical Details

**Affected files:**
- `src/nucleus/adapters/filesystem/episode_store.py`
- `src/nucleus/application/retrieve_use_case.py`
- `src/nucleus/application/bootcard_use_case.py`
- adapter response telemetry surfaces

## Resources

- `slice1-performance-review-1`

## Acceptance Criteria

- [x] Writes are atomic and readers never parse partial files.
- [x] Expired records are excluded from retrieval and bootcard candidate sets.
- [x] Operation-level timing/scan counters are available for regression tracking.

## Work Log

### 2026-05-14 - Review finding created

**By:** Copilot CLI

**Actions:**
- Grouped related P2 reliability/perf findings into one execution unit.

**Learnings:**
- Hot-path scaling and data lifecycle controls should be addressed together.

### 2026-05-15 - Implemented IO resilience, TTL filtering, and observability

**By:** Copilot CLI

**Actions:**
- Extended `EpisodeStore` read-path methods to return scan counters (`scanned_files`, `loaded_records`, `expired_filtered`, parse/invalid/scope counters) alongside records.
- Kept atomic episode persistence through temp-file replace and added a unit test to verify no temporary residue remains.
- Added TTL-focused test coverage proving expired records are excluded from retrieve and bootcard outputs.
- Added operation observability on `RetrieveResult` and `Bootcard` payloads (`operation`, `duration_ms`, `scan_counters`).
- Updated bootcard/retrieve tests to assert observability signals are present and populated.

**Learnings:**
- Adding counters at the storage boundary yields reliable regression signals while preserving existing operation semantics.

## Notes

- WHY classification: 🔧 QUALITY IMPROVEMENT
