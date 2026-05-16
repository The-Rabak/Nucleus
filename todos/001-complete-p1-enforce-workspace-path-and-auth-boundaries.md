---
status: complete
priority: p1
issue_id: "001"
tags: [code-review, security, scope-boundary, slice-1, protects-user-story]
dependencies: []
---

# Enforce workspace path and auth boundaries

## Problem Statement

`profile_id` and `workspace_id` are trusted too early in filesystem and adapter paths, enabling path traversal and tenant spoofing risks.

## Findings

- `src/nucleus/adapters/filesystem/episode_store.py:37-47,119-127` builds paths from caller-controlled IDs.
- `src/nucleus/adapters/mcp/server.py:32-66` and `src/nucleus/adapters/http/api.py:17-23` accept scope IDs without server-side identity binding.
- Security review classified this as P1 (access control + traversal).

## Proposed Solutions

### Option 1: Strict identifier validation + resolved-path guard
**Approach:** Allow only safe ID pattern, reject separators/`..`, and verify resolved path remains under expected root.
**Pros:** Fast, local, low disruption.
**Cons:** Still assumes trusted caller identity unless authz is added.
**Effort:** Medium
**Risk:** Low

---

### Option 2: Add identity-bound scope resolution
**Approach:** Derive effective profile/workspace from authenticated principal and block caller-overridden cross-tenant IDs.
**Pros:** Correct long-term security model.
**Cons:** Larger slice impact and auth plumbing.
**Effort:** Large
**Risk:** Medium

## Recommended Action

Implemented strict scope identifier validation, profiles-root path containment checks, and server-side profile/workspace scope binding via `NUCLEUS_PROFILE_ID`/`NUCLEUS_WORKSPACE_ID`.

## Technical Details

**Affected files:**
- `src/nucleus/adapters/filesystem/episode_store.py`
- `src/nucleus/adapters/mcp/server.py`
- `src/nucleus/adapters/http/api.py`

## Resources

- `docs/constitution.md`
- `docs/contracts/nucleus-stage-1-contract.md`
- Review evidence: `slice1-security-review`

## Acceptance Criteria

- [x] Invalid IDs (`..`, separators, traversal payloads) are rejected.
- [x] Resolved file paths are guaranteed inside the workspace root.
- [x] Cross-tenant/scope spoofing attempts are blocked by server-side checks.
- [x] Security tests cover traversal and tenant-boundary abuse cases.

## Work Log

### 2026-05-14 - Review finding created

**By:** Copilot CLI

**Actions:**
- Consolidated P1 security findings from security reviewer.
- Mapped hotspots in filesystem and adapter scope handling.

**Learnings:**
- Scope integrity is a user-story-critical boundary, not just hardening.

### 2026-05-15 - Resolution completed

**By:** Copilot CLI

**Actions:**
- Added shared identifier validator in `src/nucleus/application/scope_validation.py`.
- Enforced guarded path resolution in `src/nucleus/adapters/filesystem/episode_store.py`.
- Added adapter-level bound scope checks in `src/nucleus/adapters/mcp/server.py` and wiring in `src/nucleus/infra/app_factory.py`.
- Added security tests in `tests/unit/test_scope_guardrails.py`.

**Learnings:**
- Path and scope checks need to exist both at persistence boundaries and operation-entry boundaries.

## Notes

- WHY classification: 🎯 PROTECTS USER STORY
