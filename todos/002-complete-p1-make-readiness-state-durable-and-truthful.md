---
status: complete
priority: p1
issue_id: "002"
tags: [code-review, readiness, constitution, parity, protects-user-story]
dependencies: []
---

# Make readiness state durable and truthful

## Problem Statement

Readiness is process-local and can reset to misleading defaults after restart, violating truthful readiness expectations.

## Findings

- `src/nucleus/application/readiness_store.py:24-44` stores readiness only in memory.
- `src/nucleus/infra/app_factory.py:28` wires fresh in-memory state per process.
- Agent-native and Python reviewers confirmed restart can report `ready` despite pending work.

## Proposed Solutions

### Option 1: Persist readiness snapshots in durable local store
**Approach:** Save readiness keyed by `(profile_id, workspace_id)` in filesystem or DB-backed adapter.
**Pros:** Preserves truth across process boundaries.
**Cons:** Requires migration of current store API.
**Effort:** Medium
**Risk:** Low

---

### Option 2: Derive readiness from durable ingest/index state
**Approach:** Compute readiness dynamically from canonical persisted signals.
**Pros:** Single source of truth.
**Cons:** Broader refactor and potential latency impact.
**Effort:** Large
**Risk:** Medium

## Recommended Action

Implemented persisted readiness snapshots under workspace state so readiness survives process restarts and remains truthful.

## Technical Details

**Affected files:**
- `src/nucleus/application/readiness_store.py`
- `src/nucleus/application/remember_use_case.py`
- `src/nucleus/application/bootcard_use_case.py`
- `src/nucleus/infra/app_factory.py`

## Resources

- `docs/constitution.md` (Evidence-First Truthfulness)
- `docs/architecture/2026-04-30-nucleus-stage-1-architecture.md`

## Acceptance Criteria

- [x] Readiness state survives process restart.
- [x] Bootcard/retrieve report effective readiness truthfully after restart.
- [x] Regression tests cover pending→restart→readiness behavior.
- [x] No synthetic ready state is emitted when durability/indexing is incomplete.

## Work Log

### 2026-05-14 - Review finding created

**By:** Copilot CLI

**Actions:**
- Consolidated overlapping findings from python/constitution/agent-native reviewers.

**Learnings:**
- Truthful readiness is a merge-blocking requirement for Stage 1 trust.

### 2026-05-15 - Resolution completed

**By:** Copilot CLI

**Actions:**
- Refactored `ReadinessStore` to persist snapshots in `readiness.json` per profile/workspace.
- Added degraded fallback for unreadable persisted readiness state.
- Updated app wiring and added restart persistence test in `tests/unit/test_readiness_persistence.py`.

**Learnings:**
- Truthful readiness requires durable state, not process-local caches.

## Notes

- WHY classification: 🏛️ CONSTITUTION VIOLATION (blocking)
