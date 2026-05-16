---
date: 2026-04-30
topic: nucleus-future-capability-backlog
status: complete
stage: 2-plus
source_brainstorm: docs/brainstorms/2026-04-30-nucleus-clean-room-rebuild-brainstorm.md
architecture_ref: docs/architecture/2026-04-30-nucleus-stage-1-architecture.md
---

# Nucleus Future Capability Backlog

## Purpose

This backlog preserves the full Nucleus vision without letting future features pollute Stage 1. It exists because the user explicitly wants Nucleus to become a one-stop agent memory plugin with graph traversal, wiki extraction, memory decay, richer bootcards, and other advanced capabilities. Stage 1 delays these systems, but the architecture must remember them and preserve the right seams.

Each future capability has:

- value
- Stage 1 seam that preserves the option
- promotion trigger
- Stage 1 non-goal
- PACore reference where relevant
- risk if built too early

No item in this backlog is an implementation task. An item becomes plannable only after its promotion trigger is met and the architecture/contract artifacts are updated.

## Promotion Rule

No future capability becomes default until:

- Stage 1 dev benchmark passes.
- LoCoMo/LongMemEval smoke shows evidence-quality improvement over PACore baseline.
- The capability has a concrete user story tied to a failure or volume pain.
- A deletion test proves the capability is needed now.
- The relevant Stage 1 seam has enough data to support it.

## Capability 1: Graph Traversal

### Value

Graph traversal can answer relationship-expansion questions such as:

- `What is Sarah connected to?`
- `What tools does Project Atlas depend on?`
- `How are these people/projects related?`
- `Find related memories through two-hop relationships.`

PACore had graph tables, entity services, relation services, and CTE traversal, but benchmark evidence did not show graph retrieval as a decisive core path. Nucleus should preserve graph potential through relationship memories and entity mentions, then add graph traversal only when relationship retrieval needs exceed simple attribute/semantic retrieval.

### Stage 1 Seam

- Relationship memories.
- Entity mentions.
- Attributes for source/target/type/evidence.
- Memory IDs and evidence capsules as source provenance.

### Promotion Trigger

- Dev or official benchmark cases fail because correct evidence requires traversing multiple relationships, and direct semantic/exact retrieval cannot retrieve enough related context.
- Real profile has enough relationship memories to justify traversal, e.g. >1,000 relationship memories or repeated agent queries asking for connected context.
- Relationship extraction quality has golden-fixture proof.

### Stage 1 Non-Goal

- No graph traversal API.
- No canonical global entity resolver.
- No recursive CTE ranking.
- No graph-derived bootcard map.

### PACore References

- `/home/rabak/projects/PACore/src/pacore/graph/cte_traversal.py`
- `/home/rabak/projects/PACore/src/pacore/services/graph_ingestion_service.py`
- `/home/rabak/projects/PACore/docs/contracts/v1_6_graph_stage_contract_v1.md`
- `/home/rabak/projects/PACore/src/pacore/retrieval/stages/graph_stage_adapter.py`

### Risk If Built Too Early

- Repeats PACore pseudo-graph: tables and traversal exist, but retrieval quality does not improve.
- Forces premature entity canonicalization.
- Adds hard-to-debug query expansion before basic evidence retrieval stabilizes.

## Capability 2: Wiki Pages And Summaries

### Value

Wiki pages can compact many raw memories into durable, source-linked summaries. They help when raw retrieval returns too many episodes or when an agent needs a topic-level overview.

PACore wiki-lite was one of its best architectural ideas, but adding summary infrastructure before retrieval/extraction quality is strong risks summarizing noisy or missing memories.

### Stage 1 Seam

- Extracted memories with evidence capsules.
- Type/attribute registries.
- Retrieval traces showing repeated topic clusters.
- Bootcard section reserved for future memory map/wiki summaries.

### Promotion Trigger

- >1,000 durable memories in a profile or workspace.
- Retrieval traces show repeated broad-topic queries where top-k evidence is individually correct but too fragmented.
- Dev benchmark introduces summary-needed questions that fail because evidence volume is too high, not because extraction/indexing is weak.
- Evidence citation and source-linking are already reliable.

### Stage 1 Non-Goal

- No wiki page generation.
- No summary synthesis worker.
- No topic pages in bootcard.
- No admin wiki trigger.

### PACore References

- `/home/rabak/projects/PACore/src/pacore/wiki_lite/`
- `/home/rabak/projects/PACore/docs/contracts/v1_8_wiki_lite_contract_v1.md`
- `/home/rabak/projects/PACore/docs/execution-sessions/work-2026-04-17-032149/STATE.md`
- `/home/rabak/projects/PACore/src/pacore/workers/wiki_lite_worker.py`

### Risk If Built Too Early

- Summaries conceal extraction/retrieval failures.
- LLM-generated pages become perceived canonical truth.
- Adds cost and worker complexity before core evidence quality is stable.

## Capability 3: Memory Decay And Revalidation

### Value

Memory decay can reduce stale results, flag old memories for review, and prioritize frequently useful knowledge. Revalidation can refresh uncertain or old extracted memories.

### Stage 1 Seam

- Retrieval feedback signals (`retrieved`, `used`, `dismissed`, `wrong`, `updated`).
- Observed/event timestamps.
- Memory status and confidence.
- Evidence capsules.

### Promotion Trigger

- Retrieval quality degrades from stale memories outranking current memories.
- Profile age or memory volume makes stale context common.
- Feedback data exists for enough retrievals to tune decay.
- Supersession/update handling works reliably.

### Stage 1 Non-Goal

- No autonomous archival.
- No decay worker.
- No revalidation queue.
- No review-needed inbox.

### PACore References

- `/home/rabak/projects/PACore/src/pacore/workers/decay_worker.py`
- `/home/rabak/projects/PACore/src/pacore/services/lifecycle_signal_service.py`
- `/home/rabak/projects/PACore/src/pacore/api/routes/memory_feedback.py`
- `/home/rabak/projects/PACore/docs/execution-sessions/work-2026-04-25-000937/task-15-c3-3-decay-revalidation.md`

### Risk If Built Too Early

- Incorrect decay can hide valid memories.
- Review queues create product burden without enough signal.
- Adds lifecycle complexity before retrieval ranking is explainable.

## Capability 4: Full Contradiction Inbox

### Value

Contradiction handling can surface conflicting facts and let agents/users resolve them. This is a potential differentiator.

Stage 1 only needs lightweight conflict metadata for obvious value/status/preference conflicts and update/supersession. A full inbox should wait.

### Stage 1 Seam

- Simple conflict candidates on extracted memories.
- Supersession/update metadata.
- Evidence capsules for both sides of conflict.

### Promotion Trigger

- Repeated conflicts appear in retrieval traces.
- Users/agents need explicit resolution workflow.
- Lightweight conflict metadata proves useful in dev/local use.

### Stage 1 Non-Goal

- No contradiction inbox API.
- No confirm/dismiss workflow.
- No broad contradiction detection over arbitrary semantic claims.

### PACore References

- `/home/rabak/projects/PACore/src/pacore/api/routes/contradiction_surfacing.py`
- `/home/rabak/projects/PACore/src/pacore/services/contradiction_service.py`
- `/home/rabak/projects/PACore/docs/assessments/2026-04-13-v1-6b-gap-analysis.md`

### Risk If Built Too Early

- Noisy contradiction flags reduce trust.
- Requires robust entity/attribute matching not yet proven.
- Adds workflow surface before agents trust retrieve/update basics.

## Capability 5: Reminders, Daily Briefing, And Suggestions

### Value

These features make Nucleus feel like a memory assistant rather than a memory core. They help agents act on remembered context proactively.

PACore added these surfaces late and broadly. Nucleus should only add them once core evidence retrieval and bootcard are stable.

### Stage 1 Seam

- Minimal bootcard.
- Memory types can include tasks/rules/preferences if extracted.
- Feedback/access signals.
- Agent provenance.

### Promotion Trigger

- Users rely on Nucleus daily and need follow-up/context continuity.
- Task/reminder memories are already extracted reliably.
- Bootcard consumers need more proactive sections.

### Stage 1 Non-Goal

- No reminders API.
- No daily briefing.
- No proactive suggestions.
- No suggestion suppression records.

### PACore References

- `/home/rabak/projects/PACore/docs/contracts/v1_13_assistant_continuity_contract_v1.md`
- `/home/rabak/projects/PACore/src/pacore/api/routes/reminders.py`
- `/home/rabak/projects/PACore/src/pacore/api/routes/daily_briefing.py`
- `/home/rabak/projects/PACore/src/pacore/services/proactive_context_service.py`

### Risk If Built Too Early

- Turns Nucleus into assistant OS before memory core is excellent.
- Adds many workflows and tables.
- Distracts from extraction/retrieval quality.

## Capability 6: Webhooks And SSE Lifecycle Events

### Value

Push events can notify agents when indexing completes, memory changes, or suggestions are available.

Stage 1 uses polling because it is simpler and sufficient for local-first workflows.

### Stage 1 Seam

- IngestLog state transitions.
- ReadinessStore.
- Local retrieval/ingest traces.

### Promotion Trigger

- Agents need high-volume read-after-write coordination.
- Polling becomes noisy in real harness use.
- Multi-agent workflows require eventing.

### Stage 1 Non-Goal

- No webhooks.
- No SSE.
- No delivery records.

### PACore References

- `/home/rabak/projects/PACore/src/pacore/services/webhook_delivery_service.py`
- `/home/rabak/projects/PACore/src/pacore/api/routes/webhooks.py`
- `/home/rabak/projects/PACore/docs/execution-sessions/work-2026-04-25-000937/task-09-c2-2-lifecycle-webhooks.md`

### Risk If Built Too Early

- Requires security and retry semantics.
- Adds ops surface for local-first tool.
- Can mask simpler readiness polling needs.

## Capability 7: Hosted/Multi-Tenant SaaS Isolation

### Value

Nucleus may eventually support multiple users/tenants or hosted deployment.

Stage 1 is local profile scoped. It keeps profile/workspace/agent language to avoid painting itself into a corner.

### Stage 1 Seam

- `profile_id` and `workspace_id` on canonical data.
- Agent provenance.
- Adapter boundaries around auth/config.

### Promotion Trigger

- Actual second independent user/tenant requirement.
- Hosted deployment plan.
- Threat model changes beyond local machine.

### Stage 1 Non-Goal

- No PACore-style API key multi-tenancy.
- No full RLS architecture required by default.
- No distributed rate limiting.

### PACore References

- `/home/rabak/projects/PACore/src/pacore/api/middleware/authentication.py`
- `/home/rabak/projects/PACore/src/pacore/db/session/__init__.py`
- `/home/rabak/projects/PACore/docs/runbooks/v1-1-auth-and-tenant-isolation.md`

### Risk If Built Too Early

- Security architecture dominates product shape.
- Local deployment becomes too complex.
- Repeats PACore overbuilding for one-user PA use case.

## Capability 8: PACore Migration / Importer

### Value

Migration can preserve old PACore memories and benchmark artifacts.

User chose no migration in Stage 1. Nucleus can start clean. Importer may be built later as an explicit workflow that converts PACore rows/files into Nucleus episodes, not table-to-table copying.

### Stage 1 Seam

- `source_type=import`.
- `source_ref` external refs.
- Episode importer concept can exist in docs but not implementation.

### Promotion Trigger

- Nucleus dev benchmark beats PACore baseline.
- User wants to import selected PACore data.
- Import mapping from PACore WAL/Markdown/Qdrant payloads into Nucleus episodes is designed.

### Stage 1 Non-Goal

- No PACore migration code.
- No table compatibility.
- No automatic import.

### PACore References

- `/home/rabak/projects/PACore/src/pacore/db/models/`
- `/home/rabak/projects/PACore/src/pacore/db/repositories/wal_repository.py`
- `/home/rabak/projects/PACore/src/pacore/stores/qdrant_store.py`

### Risk If Built Too Early

- Nucleus schema bends around PACore artifacts.
- Legacy data quality hides Stage 1 design issues.
- Clean-room effort becomes refactor-by-import.

## Capability 9: Learned Reranker Or LLM Reranker

### Value

Learned ranking or model-based reranking can improve retrieval once enough labels and traces exist.

Stage 1 uses deterministic explainable fusion/ranking.

### Stage 1 Seam

- Retrieval traces.
- Score breakdowns.
- Benchmark labels.
- Feedback signals.

### Promotion Trigger

- Deterministic ranker plateaus.
- Enough labeled retrieval cases exist.
- Learned/LLM reranker improves evidence-first metrics without losing explainability.

### Stage 1 Non-Goal

- No learned ranker.
- No LLM rerank in hot path.

### Risk If Built Too Early

- Obscures why retrieval succeeds/fails.
- Adds latency and model dependency.
- Can overfit benchmarks.

## Capability 10: Autonomous Curated File Mutation

### Value

Agents could maintain `PROFILE.md`, `PREFERENCES.md`, and `RULES.md` over time.

Stage 1 allows suggestions only. Human or explicit profile owner confirmation applies changes.

### Stage 1 Seam

- Profile suggestion memories or patch suggestions.
- Curated file read path.
- Bootcard section separation.

### Promotion Trigger

- User explicitly wants agent-managed profile files.
- Patch suggestion workflow proves safe.
- Conflict and approval model designed.

### Stage 1 Non-Goal

- No automatic writes to curated files.

### Risk If Built Too Early

- Retrieved memory or prompt injection could alter agent rules.
- User trust decreases if profile mutates silently.

## Capability 11: Postgres FTS / Lexical Channel

### Value

Lexical retrieval can catch rare terms, exact phrases, and raw evidence spans better than embeddings.

User is partial toward Postgres FTS but willing to wait. Stage 1 keeps RetrievalChannel seam and ships vector/exact first.

### Stage 1 Seam

- RetrievalChannel interface.
- Episode catalog and extracted memory text.
- Evidence spans.

### Promotion Trigger

- Dev benchmark or local traces show semantic + exact misses raw phrase queries.
- Evidence spans need efficient word/phrase search.

### Stage 1 Non-Goal

- No FTS channel in first vertical slice.

### PACore References

- `/home/rabak/projects/PACore/src/pacore/retrieval/lexical_search.py`
- `/home/rabak/projects/PACore/src/pacore/db/models/memory_search_index.py`
- `/home/rabak/projects/PACore/docs/runbooks/v1-15-hybrid-retrieval-ops.md`

### Risk If Built Too Early

- Recreates PACore V15 tandem complexity before vector/exact baseline is proven.

## Capability 12: Rich Unified Search

### Value

Unified search could search memories, wiki pages, curated files, raw episodes, graph nodes, and future artifacts.

Stage 1 retrieve is memory evidence only. Unified search belongs later once multiple surfaces exist.

### Stage 1 Seam

- AgentInterfaceAdapter.
- RetrievalChannel architecture.
- Derived artifact contracts.

### Promotion Trigger

- Wiki/graph/curated search surfaces exist and agents need one search operation.

### Stage 1 Non-Goal

- No unified search endpoint.

### PACore References

- `/home/rabak/projects/PACore/src/pacore/api/routes/unified_search.py`
- `/home/rabak/projects/PACore/docs/execution-sessions/work-2026-04-27-phase6/STATE.md`

### Risk If Built Too Early

- Searches non-existent Stage 2 surfaces.
- Encourages separate source-specific logic in tools.

## Review Rule For Backlog Promotion

Before promoting any backlog item, answer:

- Which Stage 1 benchmark or real-use trace proves the need?
- Which existing seam supports this without breaking Stage 1 contracts?
- What deletion test says this cannot remain delayed?
- What is the smallest implementation slice?
- How will evidence/citations remain intact?
- How will MCP/HTTP parity be maintained?
- Which Stage 1 non-goal is being amended?

If these cannot be answered, the item remains backlog.
