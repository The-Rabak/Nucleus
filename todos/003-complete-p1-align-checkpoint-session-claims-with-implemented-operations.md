---
status: complete
priority: p1
issue_id: "003"
tags: [code-review, parity, constitution, drift-risk]
dependencies: []
---

# Align checkpoint_session claims with implemented operations

## Problem Statement

Instructions claim a manual `checkpoint_session` path, but Slice 1 exposed operations do not implement it, causing behavior/documentation drift.

## Findings

- `.github/copilot-instructions.md:15-16` and `.github/instructions/nucleus-memory.instructions.md:23-24` describe manual `checkpoint_session`.
- `src/nucleus/adapters/mcp/server.py:14` operation list excludes `checkpoint_session`.
- Constitution review classified this as truthfulness/parity violation.

## Proposed Solutions

### Option 1: Implement `checkpoint_session` now on shared use-case path
**Approach:** Add operation to shared adapter and MCP/HTTP parity surfaces.
**Pros:** Restores truthful docs and parity story.
**Cons:** Adds feature work into current slice remediation.
**Effort:** Medium
**Risk:** Medium

---

### Option 2: Mark as not yet available and remove imperative claims
**Approach:** Update instruction files to explicitly state future availability until operation ships.
**Pros:** Fast truthfulness fix.
**Cons:** Leaves capability gap unresolved.
**Effort:** Small
**Risk:** Low

## Recommended Action

Aligned instruction text with the current Slice 1 operation surface and removed success-shaped checkpoint availability claims.

## Technical Details

**Affected files:**
- `.github/copilot-instructions.md`
- `.github/instructions/nucleus-memory.instructions.md`
- `src/nucleus/adapters/mcp/server.py`
- `src/nucleus/adapters/http/api.py`

## Resources

- `docs/contracts/nucleus-stage-1-contract.md`
- `docs/constitution.md`

## Acceptance Criteria

- [x] Docs and runtime operations match exactly for checkpoint behavior.
- [x] If operation is shipped, MCP and HTTP parity tests cover it.
- [x] If not shipped, docs clearly mark it unavailable without success-shaped language.

## Work Log

### 2026-05-14 - Review finding created

**By:** Copilot CLI

**Actions:**
- Merged constitution + agent-native drift findings into one blocking issue.

**Learnings:**
- Prompt-level claims are part of product behavior and must be truthful.

### 2026-05-15 - Resolution completed

**By:** Copilot CLI

**Actions:**
- Updated `.github/copilot-instructions.md` to state `checkpoint_session` is planned and not in Slice 1 operations.
- Updated `.github/instructions/nucleus-memory.instructions.md` with matching non-availability guidance.
- Updated e2e parity assertions to enforce truthful instruction language.

**Learnings:**
- Interface/docs parity must be treated as a contract, not a suggestion.

## Notes

- WHY classification: 🏛️ CONSTITUTION VIOLATION (blocking)
