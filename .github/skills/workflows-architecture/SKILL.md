---
name: workflows-architecture
description: Produce a dedicated architecture improvement artifact between planning and deepening, using deletion tests, interfaces, seams, and adapters as the shared contract
---

## Arguments
[path to plan file]

# Create an architecture improvement artifact

This phase sits **after** `/workflows-plan` and **before** `/deepen-plan`.

Its job is to turn the plan's architectural context into a **consumable artifact** that downstream phases can read instead of relying on hidden oral tradition. The output is not commentary. It is a concrete architecture improvement document that names the deepening candidates, deletion-test results, interfaces, seams, adapters, and contracts that should guide deeper execution hardening.

**Process knowledge:** Load the `agent-native-architecture` skill for design heuristics around deletion tests, interface-as-test-surface thinking, seams, adapters, and contracts.

## Plan File

<plan_path> #$ARGUMENTS </plan_path>

**If the plan path above is empty:**
1. Check for recent plans: `ls -t docs/plans/*-plan*.md 2>/dev/null | head -5`
2. Ask the user: "Which plan should I improve architecturally? Please provide the path (for example `docs/plans/2026-01-15-feat-my-feature-plan.md`)."

Do not proceed until you have a valid plan file path.

## Required inputs

The architecture phase requires these inputs from the plan or linked artifacts:

- **Problem Narrative** -- why this work exists
- **User Story** -- who needs what outcome
- **Success Criteria** -- what must be true for the work to be done
- **Architectural Context** -- where the change lives and what it touches
- **Implementation phases/tasks** -- the proposed execution shape
- **`brainstorm_ref` / constitution alignment / waivers / source docs** -- when present

If any required WHY or WHERE inputs are missing, stop and tell the user exactly what is missing. Do not invent architectural context.

## Required reference contract

Before drafting the artifact, load `architecture-improvement-prompt.md` from `commands/workflows/references/` (or the generated platform-local equivalent).

Follow this protocol:
1. Use the platform's file-search tool against the local `references/` directory bundled with this skill to look for `architecture-improvement-prompt.md`.
2. Use the file-read tool to load the full template.
3. Before continuing, quote the first non-empty line of the loaded template and record which file you used.
4. If you cannot load and quote the template, stop and report the missing template instead of improvising.

Use that template as the **mandatory artifact contract**.

## Workflow

### 1. Read the plan and linked context

Read the plan file and extract:
- Problem Narrative
- User Story
- Success Criteria
- Architectural Context
- Key Decisions / Approaches Considered (when present)
- Task list and dependencies
- `brainstorm_ref`, `constitution_version`, `constitution_waivers`, `source_docs`, and any existing `architecture_ref`

If `brainstorm_ref` exists, read it for stakeholder impact, resolved questions, and architectural context that should not be lost.

If an existing `architecture_ref` already exists, read it first and decide whether to update it in place or replace it with a newer artifact. Do not create duplicate artifacts without explaining why.

### 2. Run the architecture improvement pass

Use the reference contract to produce explicit architectural guidance:

1. **Name the deepening candidates** -- which parts of the plan need deeper architectural treatment before execution hardening.
2. **Run the deletion test** -- what can be removed, avoided, or kept concrete before adding a new interface, seam, or adapter.
3. **Define interfaces as test surfaces** -- what behavior downstream tests and callers should rely on.
4. **Map seams, adapters, and contracts** -- where the system should flex, what translates external concerns, and what promises must stay stable.
5. **Use design-it-twice only where leverage is high** -- compare at least two structural options for risky boundaries, not for every detail.
6. **Translate findings into downstream guidance** -- what `/deepen-plan`, `/workflows-work`, and `/workflows-review` should preserve or verify.

If you cannot explain a proposed abstraction in terms of deletion test, interface, seam, or adapter, it is not ready to include.

### 3. Write the artifact

Write the architecture artifact to:

```text
docs/architecture/YYYY-MM-DD-<topic>-architecture.md
```

Ensure `docs/architecture/` exists before writing.

After writing the artifact:
1. Add or update `architecture_ref: <artifact path>` in the plan frontmatter when possible.
2. If frontmatter cannot be safely updated, add a clearly labeled `## Related Artifacts` section to the plan with the artifact path.
3. Do not silently move the artifact elsewhere.

## Required outputs

A complete run must leave behind all of the following:

- **Architecture artifact** in `docs/architecture/`
- **Explicit artifact path** recorded back into the plan via `architecture_ref` or `## Related Artifacts`
- **Deepening candidates** the next phase can act on
- **Deletion-test decisions** that justify which abstractions stay or go
- **Interface / seam / adapter / contract guidance** stated in plain language
- **Clear next step**: run `/deepen-plan` with the updated plan

## Handoff

When complete, summarize:

```text
Architecture improvement complete!

Plan: <plan_path>
Artifact: docs/architecture/YYYY-MM-DD-<topic>-architecture.md

Key deepening candidates:
- <candidate 1>
- <candidate 2>

Deletion test:
- Keep: <what stays concrete>
- Add later only if needed: <what failed the deletion test>

Next: Run `/deepen-plan <plan_path>` so execution hardening uses this architecture artifact.
```

NEVER CODE! This phase produces architecture guidance and artifact contracts, not implementation changes.
