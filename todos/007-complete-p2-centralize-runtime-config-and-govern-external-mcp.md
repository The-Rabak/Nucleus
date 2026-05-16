---
status: complete
priority: p2
issue_id: "007"
tags: [code-review, config, constitution, security, quality]
dependencies: []
---

# Centralize runtime config and govern external MCP

## Problem Statement

Runtime config loading is scattered and external MCP integration governance is not explicitly captured.

## Findings

- `src/nucleus/adapters/mcp/server.py:93-105` parses env locally.
- Constitution review flagged central config rule drift (`docs/constitution.md` configurability principle).
- `.github/copilot-mcp-config.json` external `context7` endpoint lacks explicit approval evidence in slice artifacts.

## Proposed Solutions

### Option 1: Typed global config module + explicit external integration policy
**Approach:** Centralize env parsing/validation and require allowlisted external MCP entries with approval metadata.
**Pros:** Strong consistency and governance.
**Cons:** Moderate refactor across adapter startup.
**Effort:** Medium
**Risk:** Low

---

### Option 2: Keep current config flow, add strict lint/check policy
**Approach:** Maintain current code with policy tests that forbid new scattered parsing and enforce approval docs.
**Pros:** Lower immediate code churn.
**Cons:** Existing drift remains.
**Effort:** Small
**Risk:** Medium

## Recommended Action

Implement Option 1 with minimal surface-area changes: add one typed runtime config loader used by app startup, pass resolved config into adapters via `create_app`, and add explicit external MCP allowlist + approval artifact checks for `context7`.

## Technical Details

**Affected files:**
- `src/nucleus/adapters/mcp/server.py`
- `src/nucleus/infra/app_factory.py`
- `.github/copilot-mcp-config.json`

## Resources

- `docs/constitution.md`
- `slice1-constitution-review`
- `slice1-security-review`

## Acceptance Criteria

- [x] Config is loaded through one typed central module.
- [x] Adapters receive config via injection, not ad hoc env reads.
- [x] External MCP registrations require explicit allowlist + approval artifact.

## Work Log

### 2026-05-14 - Review finding created

**By:** Copilot CLI

**Actions:**
- Combined config and governance findings into one P2 remediation track.

**Learnings:**
- Config centralization and integration governance are tightly coupled in harness reliability.

### 2026-05-15 - Runtime config centralization + external MCP governance implemented

**By:** Copilot CLI

**Actions:**
- Added `src/nucleus/infra/runtime_config.py` with typed `RuntimeConfig` and centralized env/env-file loading.
- Updated `src/nucleus/infra/app_factory.py` to consume injected `RuntimeConfig` and stop direct env reads in adapter wiring.
- Updated `src/nucleus/adapters/mcp/server.py` to initialize app using centralized runtime config loader.
- Added explicit external MCP allowlist + approval artifact metadata in `.github/copilot-mcp-config.json`.
- Added `docs/contracts/external-mcp-approvals.md` as the approval artifact and wired test assertions in `tests/e2e/test_copilot_cli_parity.py`.
- Added `tests/unit/test_runtime_config.py` covering env-file-backed config loading and config injection behavior.
- Ran targeted tests for unit + e2e coverage of this change set.

**Learnings:**
- Centralizing runtime config in infra keeps adapter startup parity without changing use-case behavior.
- External MCP governance is easiest to enforce by asserting config metadata and artifact existence in e2e tests.

## Notes

- WHY classification: 🔧 QUALITY IMPROVEMENT
