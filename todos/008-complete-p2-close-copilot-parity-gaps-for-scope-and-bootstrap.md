---
status: complete
priority: p2
issue_id: "008"
tags: [code-review, agent-native, parity, drift-risk]
dependencies: ["003"]
---

# Close Copilot parity gaps for scope and bootstrap

## Problem Statement

Copilot flow has parity gaps: scope widening semantics are documented but not executable, and bootstrap is policy-only instead of deterministic wiring.

## Findings

- `.github/instructions/nucleus-memory.instructions.md` describes explicit widening; `retrieve` path hardcodes `workspace_local`.
- Claude has hook bootstrap (`config/claude/hooks/session_start.py`), Copilot relies on instruction compliance only.
- Agent-native review marked these as parity warnings that can block intended outcome under real usage.

## Proposed Solutions

### Option 1: Add explicit scope inputs + deterministic bootstrap helper
**Approach:** Expose scope controls on shared use case/adapters and provide deterministic Copilot bootstrap entrypoint.
**Pros:** Restores action/context parity.
**Cons:** Requires adapter contract updates.
**Effort:** Medium
**Risk:** Medium

---

### Option 2: Constrain docs to current behavior until wiring ships
**Approach:** Remove widening/bootstrap claims from instructions temporarily.
**Pros:** Fast truthfulness patch.
**Cons:** Leaves parity capability incomplete.
**Effort:** Small
**Risk:** Low

## Recommended Action

Implemented Option 1 by wiring explicit `scope_mode` handling through retrieve and adding a deterministic Copilot bootstrap entrypoint (`config/copilot/session_start.py`) parallel to the Claude hook flow.

## Technical Details

**Affected files:**
- `src/nucleus/application/retrieve_use_case.py`
- `src/nucleus/adapters/filesystem/episode_store.py`
- `src/nucleus/adapters/mcp/server.py`
- `.github/copilot-instructions.md`
- `.github/instructions/nucleus-memory.instructions.md`
- `config/copilot/session_start.py`
- `tests/unit/test_retrieve_guards.py`
- `tests/unit/test_scope_guardrails.py`
- `tests/contract/test_mcp_http_parity.py`
- `tests/e2e/test_copilot_cli_parity.py`

## Resources

- `slice1-agent-native-review-1`
- `docs/architecture/2026-04-30-nucleus-stage-1-architecture.md`

## Acceptance Criteria

- [x] Scope widening is explicit, executable, and reflected truthfully in responses.
- [x] Copilot bootstrap has deterministic invocation equivalent to current harness constraints.
- [x] Parity tests validate scope and bootstrap semantics across harnesses.

## Work Log

### 2026-05-14 - Review finding created

**By:** Copilot CLI

**Actions:**
- Converted agent-native parity warnings into one actionable P2 todo.

**Learnings:**
- “Documented parity” is insufficient without executable parity paths.

### 2026-05-15 - Resolution completed

**By:** Copilot CLI

**Actions:**
- Added explicit retrieve `scope_mode` validation and truthful `effective_scope`/`scope_widened` signaling.
- Implemented profile-wide retrieval path in `EpisodeStore` for explicit `profile_global` widening.
- Added deterministic Copilot bootstrap script at `config/copilot/session_start.py`.
- Updated Copilot/memory instructions to document executable scope widening and bootstrap invocation.
- Added unit/contract/e2e tests covering scope widening, bound-scope guardrails, and Copilot bootstrap parity.

**Learnings:**
- Parity claims stay reliable only when instructions map directly to executable entrypoints and adapter-level contracts.

## Notes

- WHY classification: ⚠️ DRIFT RISK
