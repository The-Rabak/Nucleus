---
status: complete
priority: p3
issue_id: "011"
tags: [code-review, typing, quality, maintainability]
dependencies: ["010"]
---

# Tighten envelope types and test duplication

## Problem Statement

Adapter envelopes rely on broad `dict[str, Any]` contracts and duplicate assertion helpers in tests, increasing silent drift risk.

## Findings

- `src/nucleus/adapters/mcp/server.py`, `src/nucleus/adapters/http/api.py`, and domain models use flexible `Any`-heavy payloads.
- E2E tests duplicate MCP envelope assertion patterns across Claude/Copilot parity suites.
- Reviewers classified this as non-blocking quality improvement.

## Proposed Solutions

### Option 1: Introduce TypedDict/dataclass schemas + shared test helper
**Approach:** Define typed envelope contracts and centralize assertion helper in shared test utility.
**Pros:** Better type-check signal and contract consistency.
**Cons:** Requires broad but mechanical updates.
**Effort:** Medium
**Risk:** Low

---

### Option 2: Keep dynamic payloads and add documentation-only contract notes
**Approach:** Document shape expectations without hard typing.
**Pros:** Lowest implementation cost.
**Cons:** Drift still likely and harder to catch early.
**Effort:** Small
**Risk:** Medium

## Recommended Action

Implement Option 1 with minimal behavior-preserving edits:
- Add explicit TypedDict/type aliases for MCP/HTTP envelopes and JSON payload objects.
- Update adapter/domain signatures to use typed envelope contracts rather than `Any` maps.
- Consolidate duplicated E2E MCP envelope assertions into one shared helper and reuse it in both parity suites.
- Verify via parity-focused tests.

## Technical Details

**Affected files:**
- `src/nucleus/adapters/mcp/server.py`
- `src/nucleus/adapters/http/api.py`
- `src/nucleus/domain/models.py`
- `src/nucleus/domain/envelopes.py`
- `src/nucleus/testing/envelope_assertions.py`
- `tests/e2e/test_claude_tracer_bullet.py`
- `tests/e2e/test_copilot_cli_parity.py`

## Resources

- `slice1-python-review`
- `slice1-simplicity-review`

## Acceptance Criteria

- [x] Envelope/request/response shapes are typed explicitly.
- [x] Shared assertion helper is reused in both parity-related E2E tests.
- [x] Type checks/tests guard against schema drift.

## Work Log

### 2026-05-14 - Review finding created

**By:** Copilot CLI

**Actions:**
- Captured residual non-blocking quality findings as a single P3 todo.

**Learnings:**
- Contract typing is a long-term drift-prevention lever, not immediate blocker.

### 2026-05-15 - Implemented typed envelopes + shared E2E assertions

**By:** Copilot CLI

**Actions:**
- Added `src/nucleus/domain/envelopes.py` with `JsonObject`/`JsonValue` aliases and TypedDict envelopes for MCP + HTTP payloads.
- Updated `src/nucleus/adapters/mcp/server.py`, `src/nucleus/adapters/http/api.py`, and `src/nucleus/domain/models.py` to use explicit envelope/payload typing while preserving response shapes.
- Added shared helper `src/nucleus/testing/envelope_assertions.py` and replaced duplicated local `_assert_mcp_tool_envelope` helpers in:
  - `tests/e2e/test_claude_tracer_bullet.py`
  - `tests/e2e/test_copilot_cli_parity.py`
- Ran: `pytest tests/e2e/test_claude_tracer_bullet.py tests/e2e/test_copilot_cli_parity.py tests/contract/test_mcp_http_parity.py` (all passed).

**Learnings:**
- Centralizing envelope assertions in `nucleus.testing` avoids test import-path fragility while keeping parity checks identical.

## Notes

- WHY classification: 🔧 QUALITY IMPROVEMENT
