---
status: complete
priority: p2
issue_id: "010"
tags: [code-review, architecture, simplicity, drift-risk]
dependencies: []
---

# Reduce adapter coupling and duplicate packet formatting

## Problem Statement

Use cases depend on concrete adapter types and duplicate packet formatting logic across retrieval/bootcard flows.

## Findings

- `remember/retrieve/bootcard` use cases import `EpisodeStore` directly instead of port interface.
- Context-packet formatting is duplicated in `retrieve_use_case.py` and `bootcard_use_case.py`.
- Simplicity review flagged pass-through parameter creep in remember flow.

## Proposed Solutions

### Option 1: Introduce `EpisodeRepository` port + shared packet builder
**Approach:** Add app-layer interface and extract one packet construction utility used by both paths.
**Pros:** Better architecture fidelity and reduced drift.
**Cons:** Moderate refactor touches.
**Effort:** Medium
**Risk:** Medium

---

### Option 2: Keep structure, add strict parity tests around duplication
**Approach:** Retain current code and protect with stronger tests for output equivalence.
**Pros:** Lower immediate change cost.
**Cons:** Preserves structural debt and churn risk.
**Effort:** Small
**Risk:** Medium

## Recommended Action

Implemented Option 1 with minimal behavior-safe changes:
- add `EpisodeRepository` app-layer port and type use cases against it
- centralize retrieve/bootcard context-packet empty-message wrappers in `context_packet.py`
- introduce `RememberRequest` and route adapter invocation through request object

## Technical Details

**Affected files:**
- `src/nucleus/application/ports.py`
- `src/nucleus/application/context_packet.py`
- `src/nucleus/application/remember_use_case.py`
- `src/nucleus/application/retrieve_use_case.py`
- `src/nucleus/application/bootcard_use_case.py`
- `src/nucleus/adapters/mcp/server.py`

## Resources

- `slice1-python-review`
- `slice1-simplicity-review`
- `slice1-constitution-review`

## Acceptance Criteria

- [x] Application layer depends on ports/interfaces, not concrete filesystem adapter.
- [x] Context packet formatting is implemented once and reused.
- [x] Remember input shape is simplified (request object or equivalent) with no behavior drift.

## Work Log

### 2026-05-14 - Review finding created

**By:** Copilot CLI

**Actions:**
- Unified architecture and simplicity findings into one P2 modernization task.

**Learnings:**
- Structural drift risks parity regressions over time even when tests currently pass.

### 2026-05-15 - Todo resolved

**By:** Copilot CLI

**Actions:**
- Added `EpisodeRepository` protocol and updated `RememberUseCase`, `RetrieveUseCase`, and `BootcardUseCase` to depend on it.
- Consolidated context packet entry points via `build_retrieve_context_packet` and `build_bootcard_context_packet` in `context_packet.py`.
- Added `RememberRequest` and switched operation adapter wiring to request-object execution (with `execute_from_fields` bridge for existing tests/callers).
- Updated related unit/contract tests to use `execute_from_fields` where they call remember directly.
- Verified targeted suite: `pytest tests/unit/test_bootcard_use_case.py tests/unit/test_retrieve_guards.py tests/unit/test_scope_guardrails.py tests/unit/test_readiness_persistence.py tests/contract/test_mcp_http_parity.py`.

**Learnings:**
- Introducing a request object at the adapter boundary reduces pass-through argument creep while preserving current behavior through a narrow compatibility method.

## Notes

- WHY classification: ⚠️ DRIFT RISK
