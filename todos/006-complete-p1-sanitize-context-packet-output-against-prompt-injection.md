---
status: complete
priority: p1
issue_id: "006"
tags: [code-review, security, prompt-injection, protects-user-story]
dependencies: ["004"]
---

# Sanitize context packet output against prompt injection

## Problem Statement

Retrieved episode content is injected into markdown/fenced output without hardening, enabling prompt-structure breakouts.

## Findings

- `retrieve_use_case.py:83-95` and `bootcard_use_case.py:48-60,73-76` interpolate untrusted text directly into fenced output.
- Security review classified this as P1 due instruction-injection escalation risk.

## Proposed Solutions

### Option 1: Escape control tokens and separate data fields
**Approach:** Escape fence/control tokens and keep raw text in structured fields; render safe human text separately.
**Pros:** Strong mitigation with moderate effort.
**Cons:** Requires schema and rendering updates.
**Effort:** Medium
**Risk:** Low

---

### Option 2: Structured-only machine output for retrieved evidence
**Approach:** Remove markdown-composed packet from machine path and use strict JSON schema.
**Pros:** Minimizes injection surface.
**Cons:** UX change for human-readable traces.
**Effort:** Medium
**Risk:** Medium

## Recommended Action

Implemented shared context-packet rendering with explicit escaping of fence breakouts and sanitized inline evidence text.

## Technical Details

**Affected files:**
- `src/nucleus/application/retrieve_use_case.py`
- `src/nucleus/application/bootcard_use_case.py`
- `src/nucleus/adapters/mcp/server.py`

## Resources

- `slice1-security-review`
- MCP tool output guidance in architecture artifact

## Acceptance Criteria

- [x] Episode text cannot break packet structure or inject control instructions.
- [x] Structured retrieval fields remain stable and quoted safely.
- [x] Security test covers malicious content with fence/control payloads.

## Work Log

### 2026-05-14 - Review finding created

**By:** Copilot CLI

**Actions:**
- Extracted dedicated P1 todo for prompt injection risk.

**Learnings:**
- Evidence packaging is part of the threat model, not only retrieval quality.

### 2026-05-15 - Resolution completed

**By:** Copilot CLI

**Actions:**
- Added `src/nucleus/application/context_packet.py` with shared escaping/sanitization helpers.
- Migrated retrieve/bootcard context packet construction to the shared safe builder.
- Added injection-focused guard test in `tests/unit/test_retrieve_guards.py`.

**Learnings:**
- Treating rendered context as hostile-input output is required to preserve prompt integrity.

## Notes

- WHY classification: 🎯 PROTECTS USER STORY
