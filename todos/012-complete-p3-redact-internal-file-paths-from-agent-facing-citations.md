---
status: complete
priority: p3
issue_id: "012"
tags: [code-review, security, privacy, quality]
dependencies: []
---

# Redact internal file paths from agent-facing citations

## Problem Statement

Citation/context payloads expose `raw_file_path`, leaking internal host path structure unnecessarily.

## Findings

- Security review flagged information disclosure risk in retrieval/bootcard response composition.
- Path leakage is low severity but avoidable and useful to attackers during chained exploitation.

## Proposed Solutions

### Option 1: Return opaque/relative references only
**Approach:** Replace absolute paths with stable opaque IDs or sanitized relative references.
**Pros:** Removes host path disclosure without major UX loss.
**Cons:** Requires resolver path for deep diagnostics.
**Effort:** Small
**Risk:** Low

---

### Option 2: Keep paths but gate behind debug-only mode
**Approach:** Hide raw paths by default and expose only when explicit debug flag is enabled.
**Pros:** Preserves diagnostics for local debugging.
**Cons:** Adds mode complexity.
**Effort:** Small
**Risk:** Medium

## Recommended Action

Implement Option 1 with minimal surface-area change: redact `raw_file_path` values in all
agent-facing citation outputs to a stable workspace-relative form rooted at `profiles/`,
while keeping `episode_id` and `source_hash` unchanged for traceability.

## Technical Details

**Affected files:**
- `src/nucleus/application/retrieve_use_case.py`
- `src/nucleus/application/context_packet.py`

## Resources

- `slice1-security-review`

## Acceptance Criteria

- [x] Agent-facing payloads no longer expose absolute host file paths by default.
- [x] Citation references remain usable for evidence traceability.

## Work Log

### 2026-05-15 - Implement citation path redaction

**By:** Copilot CLI

**Actions:**
- Added `redact_raw_file_path()` in `src/nucleus/application/context_packet.py` to convert
  absolute host paths into stable `profiles/...` relative citation references.
- Updated retrieval citation payloads in `src/nucleus/application/retrieve_use_case.py` to emit
  redacted `raw_file_path` values by default.
- Updated context packet citation lines to emit the same redacted `raw_file_path` format.
- Expanded tests in:
  - `tests/e2e/test_claude_tracer_bullet.py`
  - `tests/contract/test_mcp_http_parity.py`
  to assert citation paths are non-absolute while remaining present and traceable.
- Ran targeted tests for e2e and MCP/HTTP parity retrieval behavior.

**Learnings:**
- Redacting to a deterministic `profiles/...` reference preserves operator traceability without
  exposing host filesystem layout details in agent-facing responses.

### 2026-05-14 - Review finding created

**By:** Copilot CLI

**Actions:**
- Promoted residual P3 disclosure finding into dedicated todo.

**Learnings:**
- Even low-severity metadata leakage should be tracked for defense-in-depth.

## Notes

- WHY classification: 🔧 QUALITY IMPROVEMENT
