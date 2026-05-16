---
artifact: project-constitution
status: active
version: 1.0.0
ratified: 2026-05-14
last_amended: 2026-05-14
owners:
  - maintainers
review_cycle: quarterly
applies_to:
  - ideate
  - brainstorm
  - plan
  - work
  - review
handoff:
  purpose: true
  principles: true
  phase_guardrails: true
  agent_rules: true
  amendment_process: true
---

# Project Constitution

## Purpose

Nucleus exists to deliver a Stage-1 local-first agent memory foundation that preserves evidence-grounded recall and exposes parity behavior through thin protocol adapters.

## Scope Boundaries

- **In scope:** Stage-1 memory foundation capabilities, including canonical memory/evidence modeling, retrieval quality, and parity delivery through shared application use-cases.
- **Out of scope:** Graph memory, wiki generation, decay/reminders, webhooks, and other future capability backlog items unless formally ratified as amendments.

## Core Principles

### 1. Evidence-First Truthfulness

- The system and all workflow outputs **MUST** prioritize evidence-grounded claims over fluent but unsupported summaries.
- Retrieval-facing work **MUST** preserve explicit citation traceability.
- Work **MUST NOT** represent assumptions as facts.
- **Rationale:** Nucleus is a memory system; trust depends on verifiable evidence.

### 2. Thin Adapter Parity

- MCP and HTTP surfaces **MUST** be thin adapters over shared application use-cases.
- Transport adapters **MUST NOT** own business logic.
- Public interfaces **MUST** preserve parity semantics across supported transports.
- **Rationale:** Parity prevents drift and keeps behavior portable across agent harnesses.

### 3. Canonical Language and Clear Contracts

- Repo planning and public interface terms **MUST** align with `UBIQUITOUS_LANGUAGE.md`.
- New or changed domain terms **MUST** be ratified in `UBIQUITOUS_LANGUAGE.md` before becoming canonical.
- Module interfaces **MUST** remain explicit and intention-revealing.
- **Rationale:** Shared language reduces ambiguity and protects contract integrity.

### 4. Configurability and Harness Ergonomics

- Runtime configuration **MUST** be environment-driven and centrally consumable.
- Defaults **SHOULD** minimize friction for consumer agent harnesses and local operators.
- Changes **MUST NOT** introduce hidden hard-coded environment assumptions.
- **Rationale:** Low-friction operation and portability are core product constraints.

### 5. Clean Design and Deep Modules

- Implementations **MUST** favor clean-code paradigms aligned with Uncle Bob style discipline: clear names, focused units, and high signal-to-noise structure.
- Modules **SHOULD** be deep: concentrated internal power behind simple, clear interfaces.
- Interfaces **MUST** stay smaller and clearer than the complexity they encapsulate.
- **Rationale:** Deep, clean modules reduce long-term complexity and improve maintainability.

## Agent Execution Rules

- Agents **MUST** ask blocking clarification questions when scope, behavior, or approvals are ambiguous.
- Agents **MUST** provide explicit blocked-state reporting when constitution gates prevent execution.
- Agent execution prompts **MUST** include relevant constitution guardrails for the current phase.
- Agent workflows **MUST** preserve user/agent portability expectations and parity constraints.
- Agents **MUST NOT** silently bypass approval gates or constitution waivers.

## Phase Guardrails

### Ideation Guardrails

- Ideation **MUST** score proposals for constitution fit.
- Ideas conflicting with this constitution **MUST** be framed as explicit amendment candidates.

### Brainstorm Guardrails

- Brainstorms **MUST** read and reference this constitution before exploring approaches.
- Brainstorms **MUST NOT** silently normalize scope drift.

### Planning Guardrails

- Plans **MUST** record `constitution_version`.
- Plans **MUST** record any `constitution_waivers` with rationale, approver, and expiry/exit criteria.
- Plans **MUST** translate applicable constitution rules into acceptance criteria and approval checkpoints.

### Execution Guardrails

- Execution **MUST** honor Ralph-driven red-green-refactor discipline with explicit evidence.
- Work completion **MUST** include relevant tests, lint/build checks where applicable, and required docs updates for behavior changes.
- Execution **MUST** stop for explicit human approval when the constitution requires it.

### Review Guardrails

- Review **MUST** treat unwaived constitution violations as blocking.
- Review **MUST** verify waiver validity (scope, approver, and expiry).
- Repeated waiver patterns **SHOULD** trigger constitution amendment consideration.

## Allowed Exceptions

- Exceptions are permitted only through explicit waivers recorded in plan artifacts.
- A waiver record **MUST** include: rule waived, why waiver is necessary, approver, scope, and expiry or removal condition.
- The following **MUST** receive explicit human approval before execution or merge:
  - production or external writes
  - schema or data migrations
  - authentication or access-control changes
  - new external integrations
  - constitution waivers and scope expansions

## Amendment Process

- Any maintainer **MAY** propose a constitution amendment via pull request.
- Ratification **MUST** include maintainer review and explicit approval in the PR.
- Amendment versioning policy:
  - **MAJOR:** a principle is removed or redefined
  - **MINOR:** a new principle or section is added
  - **PATCH:** clarification without behavioral change
- Constitution review cadence is quarterly and additionally triggered when the same waiver or review finding recurs more than once.

## Amendment Log

- v1.0.0 - Initial ratification.
