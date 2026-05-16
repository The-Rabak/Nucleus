---
date: 2026-04-30
topic: nucleus-stage-1-architecture
status: complete
source_brainstorm: docs/brainstorms/2026-04-30-nucleus-clean-room-rebuild-brainstorm.md
contract_ref: docs/contracts/nucleus-stage-1-contract.md
benchmark_ref: docs/benchmarks/nucleus-dev-slice.md
future_backlog_ref: docs/architecture/2026-04-30-nucleus-future-capability-backlog.md
governing_language: UBIQUITOUS_LANGUAGE.md
architecture_style: ports-and-adapters
stage: 1
---

# Nucleus Stage 1 Architecture

## Purpose

This architecture artifact is the baseline for every future Nucleus plan. It turns the clean-room rebuild brainstorm into concrete structural guidance without becoming an implementation plan. It defines the deep modules, deletion-test boundaries, ports, seams, adapters, data ownership model, and wiring contracts needed to build Stage 1 without repeating PACore's architecture-first but retrieval-second failure mode.

Nucleus Stage 1 has one core promise: a local agent can remember source material, Nucleus can extract durable memories with evidence, and later retrieval can return cited evidence reliably. Every architecture choice in this document must serve that promise or preserve a future option without pulling it into Stage 1.

## Problem Framing And Constraints

### Problem

PACore proved that strong infrastructure is not enough. It had a durable write path, Postgres RLS, Qdrant, filesystem identity files, graph tables, wiki-lite, MCP, runbooks, and benchmark scripts. Yet benchmark runs showed retrieval failures on exact values, temporal questions, speaker-specific questions, preferences, multi-session context, and knowledge updates. The architecture had too many surfaces and too many partially competing paths; core memory quality lagged behind control-plane ambition.

Nucleus must rebuild the architecture around the evidence loop first:

```text
source episode -> extraction -> durable memory -> indexes -> cited retrieval
```

### Constraints

- Greenfield repo at `/home/rabak/projects/Nucleus`.
- Python 3.12+ is the preferred implementation language.
- Stage 1 is local-first and CPU-tolerant.
- Postgres and Qdrant are acceptable local services.
- Raw source episodes are human-readable Markdown files with 90-day TTL.
- Extracted memories and evidence capsules are canonical Postgres data.
- Qdrant is a rebuildable vector index behind `VectorIndex`.
- MCP and HTTP are adapters over the same application services.
- Stage 1 must not implement graph traversal, wiki pages, decay automation, reminders, suggestions, webhooks/SSE, hosted SaaS auth, full contradiction inbox, PACore migration, learned reranking, or autonomous curated-file mutation.

### Non-Negotiable Lessons From PACore

- Component existence is not enough; every user-facing flow needs verified wiring arrows.
- A retrieval path used by REST must be the same retrieval path used by MCP and semantic workflows.
- Extraction quality must be tested independently before retrieval scores are trusted.
- Benchmarks need retrieved evidence artifacts, not just final answer scores.
- Docs must describe shipped behavior or explicitly mark future behavior as non-goal.

PACore references:

- Wiring gap: `/home/rabak/projects/PACore/docs/solutions/integration-issues/wiring-gap-component-creation-without-pipeline-integration.md`
- Data-flow map: `/home/rabak/projects/PACore/docs/architecture/data-flow-and-wiring-map.md`
- V15 assessment: `/home/rabak/projects/PACore/docs/benchmarks/v15-assessment.md`
- PACore retrieval code: `/home/rabak/projects/PACore/src/pacore/retrieval/retrieval_pipeline.py`
- PACore MCP drift example: `/home/rabak/projects/PACore/src/pacore/mcp/tools.py`

## Architectural North Star

Nucleus uses a ports-and-adapters architecture with deep modules. Deep modules hide implementation detail behind small, behavior-rich interfaces. Ports are test surfaces, not abstractions for their own sake. Adapters translate external systems into domain-safe behavior.

The system should feel simple from outside:

```text
remember(source)
retrieve(query)
update_preview(query)
update_confirm(selection)
forget_preview(query)
forget_confirm(selection)
inspect_status(id/profile)
checkpoint_session(session/profile/workspace)
bootcard(profile/workspace)
```

Inside, the system remains modular enough to swap extractor drivers, vector indexes, retrieval channels, and interface adapters.

## Capability Map And Parity

### Stage 1 Agent Capabilities

| Capability | Agent Path | Human Path | Notes |
| --- | --- | --- | --- |
| Record source material | `remember` MCP/HTTP | write/import source via API or CLI | Creates episode and ingest event. |
| Retrieve memory evidence | `retrieve` MCP/HTTP | API/CLI query | Returns structured results and context packet. |
| Inspect ingest/index state | `inspect_status` MCP/HTTP | CLI/API diagnostics | Must be truthful, not synthetic. |
| Preview update | `update_preview` MCP/HTTP | API/CLI preview | No mutation. |
| Confirm update | `update_confirm` MCP/HTTP | API/CLI confirm | Requires selected IDs. |
| Preview forget | `forget_preview` MCP/HTTP | API/CLI preview | No mutation. |
| Confirm forget | `forget_confirm` MCP/HTTP | API/CLI confirm | Requires selected IDs. |
| Read startup context | `bootcard` MCP/HTTP | read generated bootcard | Minimal Stage 1 context. |
| Persist session continuity | `checkpoint_session` MCP/HTTP/hook trigger | CLI/API/manual checkpoint | Same semantics for Claude and Copilot durability paths. |
| Review raw source | citation file path while TTL active | filesystem | Raw episodes are transparent Markdown. |
| Review quarantined output | diagnostics | diagnostics | Not in normal retrieval. |

### Parity Gaps To Track

- Future human UI is not Stage 1, but all operations are accessible through API/CLI/MCP.
- Profile file patch suggestions are allowed, but applying patches is not automatic.
- Full graph/wiki/decay workflows are deliberately absent but preserved via backlog and seams.

## System Context

```text
Agent Harness / CLI / HTTP Client
        |
        v
Interface Adapters (MCP, HTTP, Claude hooks, Copilot bootstrap/instruction adapters)
        |
        v
Application Use Cases
        |
        +--> EpisodeStore port -> Filesystem adapter
        +--> IngestLog port -> Postgres adapter
        +--> ExtractionPipeline port -> deterministic + driver adapters
        +--> MemoryRepository port -> Postgres adapter
        +--> TypeRegistry port -> Postgres adapter
        +--> VectorIndex port -> Qdrant adapter
        +--> RetrievalChannel ports -> vector/exact adapters
        +--> FusionRanker port -> deterministic ranker
        +--> ReadinessStore port -> Postgres/local trace adapter
```

## Harness Lifecycle And Scope Model

- **Claude Code** uses `SessionStart` for minimal bootstrap, `PreCompact` and `Stop` for real durability triggers, and `SessionEnd` for cleanup only.
- **GitHub Copilot/Copilot CLI** uses repo-local instruction templates plus MCP registration for discovery and uses the same shared use cases; when no stable hook surface exists, it falls back to an explicit `checkpoint_session` operation with identical semantics.
- **Scope contract:** `workspace-local` is the default retrieval boundary inside a profile. Profile-global widening is explicit, non-sticky, and echoed in outputs as `effective_scope`.
- **Adapter rule:** hooks, instruction files, and transport adapters may inject context or trigger shared use cases, but they must not own separate memory semantics.

## Data Ownership Model

### Source Of Truth Matrix

| Data | Canonical Owner | Derived From | Rebuildable? | Notes |
| --- | --- | --- | --- | --- |
| Raw episode body | Markdown file | Source event | No after TTL | Human-readable source. |
| Episode metadata | Postgres episode catalog | Markdown frontmatter + ingest | Yes from files while present | Catalog, not source body owner. |
| Ingest state | Postgres ingest log | Remember operation | No | Narrow WAL. |
| Extracted memories | Postgres | Episodes + extraction | Re-extract only while raw exists | Canonical durable memory. |
| Evidence capsules | Postgres | Evidence spans + metadata | No | Required after raw TTL. |
| Type registry | Postgres | Human/system promotion | No | Governs extraction prompts. |
| Attribute registry | Postgres or static seed + Postgres proposals | Extraction/runtime | Yes from registry migrations + proposals | Light governance. |
| Vector index | Qdrant | Extracted memories/evidence | Yes | Derived. |
| Exact index | Postgres query/index or derived table | Attributes | Yes | Generic attributes, not benchmark facets. |
| Retrieval traces | Postgres/local trace store | Retrieval calls | Optional bounded retention | Diagnostics only. |
| Bootcard | Generated Markdown/cache | Profile files + memories | Yes | Derived. |
| Wiki pages | Stage 2 derived artifact | Memories/evidence | Yes | Not Stage 1. |
| Graph traversal data | Stage 2 derived/promoted data | Relationship memories/entity mentions | Yes/partial | Not Stage 1. |

### Episode File Contract

Raw episode files live under:

```text
profiles/{profile_id}/episodes/YYYY/MM/DD/{episode_id}.md
```

The body is readable Markdown. Frontmatter is fixed. Episode files are not arbitrary JSON dumps.

Required frontmatter:

```yaml
episode_id: "ep_..."
profile_id: "profile_..."
workspace_id: "workspace_..."
source_type: "chat_turn|tool_result|user_note|document_chunk|import"
source_ref: "external stable ref"
session_id: "optional session id"
turn_index: 12
speaker: "Rabak"
role: "user|assistant|system|tool|unknown"
observed_at: "2026-04-30T12:34:56Z"
ingested_at: "2026-04-30T12:35:01Z"
ttl_expires_at: "2026-07-29T12:35:01Z"
content_hash: "sha256:..."
sensitivity: "none|possible_secret|secret|personal|unknown"
extraction_status: "pending|running|completed|failed|quarantined"
schema_version: "nucleus.episode.v1"
```

Deletion test outcome: keep raw files as canonical source because they are human-inspectable and align with agent-native file interfaces. Do not store full raw body canonically in Postgres in Stage 1.

## Module Architecture

### `domain/`

Owns terms and pure models. It must not import adapters or infrastructure.

Examples:

- `ProfileId`, `WorkspaceId`, `AgentId`
- `Episode`, `EpisodeMetadata`
- `IngestEvent`, `IngestStatus`
- `ExtractedMemory`, `EvidenceCapsule`, `Attribute`
- `MemoryType`, `TypeRegistryEntry`
- `QueryIntent`, `RetrievalCandidate`, `RetrievalResult`
- `EvidenceStatus`, `Citation`, `ContextPacket`

Deletion test: keep because domain language is the shared contract. Avoid anemic duplication of DB models; domain types should represent behavior and invariants.

### `application/`

Owns use cases and orchestrates ports. It should contain the only workflow logic used by HTTP/MCP.

Use cases:

- `RememberUseCase`
- `RetrieveUseCase`
- `UpdatePreviewUseCase`
- `UpdateConfirmUseCase`
- `ForgetPreviewUseCase`
- `ForgetConfirmUseCase`
- `InspectStatusUseCase`
- `SessionCheckpointUseCase`
- `BootcardUseCase`
- `ExtractionWorkerUseCase` or background service
- `IndexingWorkerUseCase` if separated

Deletion test: keep because it prevents MCP/HTTP drift. Avoid duplicated workflows in adapters.

### `ports/`

Defines interfaces as test surfaces.

Ports are listed below. Every method must have a Stage 1 use case. No graph/wiki/decay/reminder methods are allowed in Stage 1 ports.

### `adapters/`

External detail lives here.

Adapters:

- filesystem episode store
- Postgres ingest log
- Postgres memory repository
- Postgres registries
- Qdrant vector index
- Ollama extractor driver
- OpenRouter extractor driver
- local deterministic extractor
- MCP tools
- FastAPI routes
- config/env loaders
- benchmark dataset loaders

### `infra/`

Composition root and operational wiring.

Rules:

- No PACore-style god `main.py`.
- Use application factory and service container/composition functions.
- Startup wires ports to adapters explicitly.
- Runtime settings come through one global config module loaded from environment, so adapters receive typed config rather than reading environment variables ad hoc.
- Background workers are owned and cancellable.
- Readiness is registered as a service, not inferred from global variables.

## Ports As Test Surfaces

The user requested all ports upfront. The deletion-test rule applies: every coded port needs a Stage 1 use case and test surface.

### `EpisodeStore`

Purpose: write/read/prune file-backed episodes.

Interface as test surface:

- Given episode metadata/body, writes atomic Markdown with correct frontmatter.
- Returns path/hash/mtime for citation and catalog.
- Reads body only if file exists and hash matches.
- Prunes expired unpinned episodes without deleting evidence capsules.

Primary adapter: local filesystem.

Deletion test: keep because raw Markdown is canonical and all ingest depends on it.

### `IngestLog`

Purpose: narrow WAL for remember/extraction/indexing lifecycle.

Interface as test surface:

- Creates ingest event after episode write.
- Transitions states only along valid path.
- Exposes status by `ingest_id`.
- Claims pending extraction/index work with concurrency-safe semantics.

Primary adapter: Postgres.

Deletion test: keep because async ingest needs durable state and readiness.

### `ExtractorDriver`

Purpose: call model runtime for structured extraction without contaminating extraction logic.

Interface as test surface:

- Accepts bounded prompt/context and returns structured raw JSON.
- Reports model, provider, latency, token estimates when available.
- Fails with typed errors.

Adapters: Ollama, OpenRouter.

Deletion test: keep because provider flexibility is explicit requirement.

### `DeterministicExtractor`

Purpose: extract obvious signals without LLM.

Interface as test surface:

- Extracts dates, money, numbers, URLs, code symbols, source metadata, role/speaker signals.
- Emits attributes and evidence spans.
- Never hallucinates beyond source text.

Adapter/module: local implementation, likely concrete but still treated as a port if multiple strategies are planned.

Deletion test: keep because PACore failed exact-value extraction.

### `ExtractionPipeline`

Purpose: combine deterministic passes, optional model output, validation, registry canonicalization, quarantine, and memory persistence output.

Interface as test surface:

- Given an episode, produces canonical extracted memories or quarantine records.
- Requires evidence spans for canonical memories.
- Preserves proposed types/attributes.
- Does not write indexes directly.

Deletion test: keep because extraction is core product behavior and must be tested separately.

### `MemoryRepository`

Purpose: canonical Postgres storage for extracted memories and evidence capsules.

Interface as test surface:

- Stores extracted memory with statement, type, attributes, evidence, source links.
- Retrieves by memory IDs and preview selections.
- Supports soft forget/update/supersession metadata.
- Provides data to rebuild indexes.

Deletion test: keep because Postgres extracted memory is source of truth.

### `TypeRegistry`

Purpose: govern dynamic memory types.

Interface as test surface:

- Resolves proposed type to active canonical type or marks proposal.
- Provides active type prompt context.
- Records usage counts and promotion status.

Deletion test: keep because flexible types without governance will drift.

### `AttributeRegistry`

Purpose: govern common attribute names/types and normalization hints.

Interface as test surface:

- Resolves proposed attribute names.
- Provides normalization hints to deterministic/model extraction.
- Allows proposed attributes without blocking storage.

Deletion test: keep, but light. Do not over-model all attributes.

### `VectorIndex`

Purpose: derived semantic retrieval index.

Interface as test surface:

- Upserts memory/evidence embeddings with profile/workspace scope.
- Searches by query vector with filters.
- Deletes or marks forgotten memories.
- Rebuilds from repository export.

Adapter: Qdrant first.

Deletion test: keep because semantic retrieval is Stage 1 mandatory; adapter hides Qdrant.

### `RetrievalChannel`

Purpose: pluggable candidate source for retrieval.

Interface as test surface:

- Accepts QueryIntent and returns candidates with scores, source, evidence, channel diagnostics.
- Can fail/degrade independently.

Stage 1 channels:

- vector channel
- exact attribute channel

Future channel:

- lexical/FTS (kept Stage 1-ready behind the same seam and promoted only if benchmark evidence requires a rescue path)
- graph traversal
- wiki summary

Deletion test: keep because user explicitly wants pluggable retrieval channels.

### `FusionRanker`

Purpose: combine channel candidates into explainable ranked results.

Interface as test surface:

- Uses deterministic fusion/reranking.
- Defaults to deterministic RRF-style fusion with explicit tie-break and score-breakdown rules.
- Emits score breakdown and evidence status.
- Does not call LLM in Stage 1.

Deletion test: keep because multi-channel retrieval must remain explainable and benchmark-auditable.

### `ReadinessStore`

Purpose: truthful ingest/extraction/index readiness and local traces.

Interface as test surface:

- Reports ingest status by ID.
- Reports profile indexing readiness.
- Stores latest successful checkpoint metadata and recovery-visible durability state.
- Stores bounded retrieval traces.

Deletion test: keep because async remember requires truthful readiness.

### `AgentInterfaceAdapter`

Purpose: HTTP/MCP/CLI adapters over identical application use cases.

Interface as test surface:

- Exposes same capabilities and result semantics through each interface.
- Does not contain business workflow logic.

Deletion test: keep as conceptual seam; concrete adapters can be implemented sequentially.

## Seams And Adapters

### Model Runtime Seam

Seam: `ExtractorDriver` and embedding driver config.

Adapters: Ollama, OpenRouter.

Contract: runtime swap changes model behavior but not extraction envelope or storage schema.

Failure behavior: extraction can degrade to deterministic-only; retrieval still works over existing memories.

### Vector Backend Seam

Seam: `VectorIndex`.

Adapter: Qdrant.

Contract: all vector data is rebuildable from Postgres canonical memories and evidence capsules.

External reference: Qdrant supports hybrid/multi-stage query patterns and RRF, but Nucleus should not expose Qdrant concepts directly in domain language. https://qdrant.tech/documentation/search/hybrid-queries/

### Retrieval Channel Seam

Seam: `RetrievalChannel`.

Adapters: vector channel, exact channel, future FTS/graph/wiki channels.

Contract: channels receive QueryIntent and return candidates with diagnostics; they do not directly format final responses.

### Interface Surface Seam

Seam: application use cases.

Adapters: HTTP, MCP, Claude hook adapter, Copilot bootstrap/instruction adapter.

Contract: MCP tools and HTTP routes are parity adapters over the same application use cases. Hook and instruction adapters may trigger the same use cases but must not implement separate business logic. MCP can provide `structuredContent`, text fallback, and resource/resource-link references for inspectable artifacts such as bootcards or raw episodes. https://modelcontextprotocol.io/docs/concepts/tools

### File Source Seam

Seam: `EpisodeStore`.

Adapter: filesystem.

Contract: raw Markdown files remain inspectable; Postgres catalog points to file path/hash.

Agent-native file reference: files are transparent, inspectable, portable, and effective for agent workflows.

### Future Capability Seams

- Graph traversal uses relationship memories and entity mentions.
- Wiki pages use extracted memories/evidence capsules.
- Decay uses lifecycle signals and retrieval feedback.
- Reminders/suggestions use memory operations and bootcard context.
- Hosted/multi-tenant mode uses profile/workspace scoping as seed.

No future seam should add implementation methods to Stage 1 ports unless Stage 1 needs them.

## Deepening Candidates

These areas need deeper treatment before implementation planning.

### Candidate 1: Extraction Envelope And Registry Governance

Needs precise schema for extracted memory, evidence capsule, attributes, type registry, attribute registry, quarantine reasons, and promotion workflow.

Risk: too loose recreates retrieval weakness; too strict recreates enum rigidity.

Deepen with examples from dev benchmark fixtures.

### Candidate 2: Retrieval Channel Contract And Fusion Diagnostics

Needs exact candidate schema, score normalization rules, evidence status definitions, fusion algorithm, and trace output.

Risk: channel abstraction can become too generic to test or too specific to vector/exact only.

Deepen with query examples: exact amount, date, speaker, preference, update, abstention.

### Candidate 3: Episode File And Catalog Integrity

Needs atomic write protocol, hash verification, path safety, TTL pruning, pinned raw behavior, frontmatter schema, and catalog sync rules.

Risk: file/DB drift can undermine evidence trust.

Deepen with failure cases: missing file, hash mismatch, expired file, user edit.

### Candidate 4: Readiness And Local Trace Semantics

Needs statuses, state transitions, trace retention, error categories, and agent-facing status response.

Risk: PACore-like synthetic capability surfaces can mislead agents.

Deepen by defining exact truth states.

### Candidate 5: MCP/HTTP Parity Adapter Contract

Needs tool names, schemas, structured outputs, error behavior, and parity tests.

Risk: PACore drift between REST and MCP repeats.

Deepen by mapping every public operation to one application use case.

### Candidate 6: Benchmark Dev Slice

Needs fixed cases, expected evidence, extraction expectations, retrieval thresholds, and anti-gaming policy.

Risk: benchmark gate becomes score theater instead of capability proof.

Deepen with artifact in `docs/benchmarks/nucleus-dev-slice.md`.

## Deletion Test Outcomes

### Keep In Stage 1

- Episode Markdown files with frontmatter.
- Postgres episode catalog.
- Narrow IngestLog.
- Deterministic extractor.
- ExtractorDriver seam for Ollama/OpenRouter.
- Strict extraction envelope.
- Type registry and light attribute registry.
- Postgres canonical extracted memories and evidence capsules.
- Qdrant vector adapter behind VectorIndex.
- RetrievalChannel seam.
- Vector and exact retrieval channels.
- Deterministic FusionRanker.
- Structured retrieve result plus context packet.
- Preview-confirm update/forget.
- Minimal bootcard.
- Local traces and readiness.

### Delay But Preserve Seam

- Postgres FTS channel: preserve RetrievalChannel seam.
- Graph traversal: preserve relationship memories and entity mentions.
- Wiki summaries: preserve evidence capsules and source-linked memories.
- Memory decay: preserve lifecycle signals and feedback.
- Reminders/suggestions: preserve agent-facing memory operations and bootcard seam.
- Webhooks/SSE: preserve readiness/status events internally but no external push.
- Hosted auth/RLS: preserve profile/workspace scoping.
- PACore migration: preserve import source_type and external refs, but no migration work.
- Learned reranker: preserve retrieval traces and benchmark labels.

### Delete From Stage 1

- Broad admin endpoints.
- Full contradiction inbox.
- Daily briefing and proactive suggestions.
- Wiki-lite worker.
- Graph CTE traversal and graph browse endpoints.
- Multi-tenant SaaS API key system.
- Direct Qdrant payload as public memory shape.
- Public WAL IDs.
- Separate MCP implementation of retrieval logic.
- Benchmark-specific runtime branches.

## Design-It-Twice Decisions

### Decision A: Raw Episode Canonicality

Option 1: raw episode body canonical in Markdown file, Postgres catalog only.

- Pros: human-readable, agent-native, transparent, portable, natural TTL.
- Cons: file/DB drift risk, slower full-text search unless indexed.

Option 2: raw episode body canonical in Postgres, Markdown export derived.

- Pros: transactional with extracted memories, easier querying, fewer file drift cases.
- Cons: loses file-as-source principle, less transparent, more PACore-like DB centrality.

Decision: Option 1. Mitigation: content hash, catalog sync checks, readiness diagnostics, and evidence capsules.

### Decision B: Dynamic Memory Types

Option 1: fixed enum of memory types.

- Pros: predictable ranking and schema.
- Cons: underfits real memory; user explicitly rejects fixed type count.

Option 2: fully open string types.

- Pros: flexible.
- Cons: taxonomy drift and prompt bloat.

Option 3: dynamic proposed types with registry promotion.

- Pros: flexible and governed.
- Cons: needs registry workflow.

Decision: Option 3.

### Decision C: Exact Retrieval Modeling

Option 1: benchmark-specific value facet table.

- Pros: exact fact retrieval improves quickly.
- Cons: smells like benchmark gaming and rigid architecture.

Option 2: no structured values, text/vector only.

- Pros: pure and simple.
- Cons: repeats PACore failures on exact values.

Option 3: generic attributes attached to memories, indexed by exact channel.

- Pros: general, flexible, strong retrieval, not benchmark-specific.
- Cons: requires attribute registry and generic indexing design.

Decision: Option 3.

### Decision D: Query Understanding

Option 1: deterministic parser only.

- Pros: fast, local, predictable.
- Cons: limited nuance.

Option 2: LLM query parser by default.

- Pros: flexible.
- Cons: local LLM performance concerns and fragility.

Option 3: deterministic QueryIntent plus optional gated LLM enrichment.

- Pros: robust baseline plus opt-in enrichment.
- Cons: more contract complexity.

Decision: Option 3.

### Decision E: Interface Architecture

Option 1: define ports only as needed after code emerges.

- Pros: minimal upfront work.
- Cons: risks adapter drift and unclear tests.

Option 2: define all ports upfront with broad future methods.

- Pros: strong architecture vision.
- Cons: PACore-style overengineering.

Option 3: define all Stage 1 ports upfront, but every coded method must pass deletion test.

- Pros: shared architecture without speculative surface.
- Cons: requires discipline during planning/review.

Decision: Option 3.

## Wiring Map

### Remember Path

```text
Agent/MCP/HTTP
  -> RememberUseCase
  -> validate profile/workspace/source metadata
  -> sensitivity scan
  -> EpisodeStore.write_markdown
  -> EpisodeCatalog.record
  -> IngestLog.create(status=episode_persisted, extraction=pending, indexing=pending)
  -> return ingest_id, episode_id, index_status=pending
```

Required proof: E2E writes file, catalog row, ingest event, returns IDs, no extraction needed for durability.

### Extraction Path

```text
ExtractionWorker
  -> IngestLog.claim_pending_extraction
  -> EpisodeStore.read_body
  -> DeterministicExtractor.extract
  -> TypeRegistry.active_prompt_context
  -> AttributeRegistry.normalization_hints
  -> ExtractorDriver.extract optional
  -> ExtractionPipeline.validate_strict_envelope
  -> TypeRegistry.resolve proposed/canonical
  -> MemoryRepository.store canonical memories + evidence capsules
  -> MemoryRepository.store quarantine records
  -> IngestLog.mark_extraction_completed_or_failed
```

Required proof: golden fixture creates expected memory/evidence/attributes and no hallucinated memory.

### Indexing Path

```text
IndexingWorker or post-extraction step
  -> MemoryRepository.load_indexable_memories
  -> EmbeddingDriver.embed statement+evidence
  -> VectorIndex.upsert
  -> ExactIndex/AttributeIndex upsert or ensure queryable
  -> ReadinessStore.mark_indexed
```

Required proof: vector index and exact retrieval can be rebuilt from Postgres after raw file deletion.

### Retrieve Path

```text
Agent/MCP/HTTP
  -> RetrieveUseCase
  -> QueryIntentAnalyzer.analyze deterministic + optional gated LLM
  -> RetrievalChannel.vector.search and RetrievalChannel.exact.search run concurrently with per-channel deadlines
  -> lexical/FTS rescue path only if enabled by evidence-driven hardening
  -> FusionRanker.fuse_and_rank using deterministic RRF-style rules
  -> MemoryRepository.batch_hydrate citations/evidence
  -> ContextPacketBuilder.fence evidence
  -> RetrievalTraceStore.record
  -> return structured results + context_packet + diagnostics
```

Required proof: one semantic query and one exact query return same cited memory with evidence span.

### Update Path

```text
Agent/MCP/HTTP
  -> UpdatePreviewUseCase(query)
  -> RetrieveUseCase with update intent
  -> return candidate memories + citations + preview_token
  -> UpdateConfirmUseCase(preview_token, selected_memory_ids, replacement source)
  -> RememberUseCase creates new episode/ingest event
  -> MemoryRepository links supersession/update relation after extraction
```

Required proof: no mutation occurs during preview; confirm requires selected IDs.

### Forget Path

```text
Agent/MCP/HTTP
  -> ForgetPreviewUseCase(query)
  -> RetrieveUseCase with forget intent
  -> return candidates + citations + preview_token
  -> ForgetConfirmUseCase(preview_token, selected_memory_ids)
  -> MemoryRepository marks memories forgotten
  -> VectorIndex delete/mark derived points
  -> ReadinessStore record mutation
```

Required proof: forgotten memory does not appear in normal retrieval; diagnostics can show state.

### Bootcard Path

```text
Agent/MCP/HTTP
  -> BootcardUseCase(profile, workspace)
  -> read curated PROFILE/PREFERENCES/RULES
  -> load latest successful checkpoint summary stub if present
  -> retrieve small memory map only when readiness is truthful enough to do so
  -> include retrieval protocol and strict context hierarchy
  -> return bootcard Markdown + section metadata
```

Required proof: bootcard generated without wiki/graph/decay dependencies.

### Checkpoint Path

```text
Claude hook / Copilot command / MCP / HTTP
  -> SessionCheckpointUseCase(profile, workspace, session, trigger)
  -> collect bounded session summary, selected citations, preview-token state, effective_scope, readiness snapshot
  -> ReadinessStore.record_checkpoint(idempotency_key, trigger, checkpoint_sequence)
  -> return checkpoint_id, recorded_at, effective_scope, readiness
```

Required proof: `PreCompact` and `Stop` persist once with replay-safe semantics, and the same checkpoint state can be created through an explicit Copilot/manual path.

## Contracts To Freeze Before Implementation

- Episode frontmatter contract.
- ExtractedMemory envelope contract.
- Attribute contract.
- EvidenceCapsule contract.
- TypeRegistry entry contract.
- QueryIntent contract.
- RetrievalChannel candidate contract.
- RetrievalResponse and ContextPacket contract.
- SessionCheckpoint contract.
- IngestStatus and Readiness contract.
- MCP tool output schema contract.
- Benchmark artifact contract.

These are documented in `docs/contracts/nucleus-stage-1-contract.md`.

## Local Deployment Architecture

Stage 1 deployment:

```text
docker compose
  postgres
  qdrant
  nucleus-api-mcp
external optional
  ollama
  openrouter api
```

Configuration rule:

- A single operator-managed `.env` file is the local configuration source of truth.
- Docker Compose reads that `.env` directly for port mappings, host bindings, volumes, and optional service toggles.
- The application consumes the same values through one global config module in `infra/` so service URLs, credentials, filesystem roots, and runtime feature flags stay aligned with Compose.
- Default ports are convenience defaults only; Postgres, Qdrant, Ollama, and Nucleus endpoints must be remappable without editing Compose YAML or application source.

Commands to design later:

```text
nucleus init
nucleus up
nucleus status
nucleus benchmark dev-slice
```

No Kubernetes, hosted assumptions, multi-replica workers, or distributed rate limiting in Stage 1.
No scattered per-adapter environment parsing; local deployment ergonomics depend on one coherent config surface.

## Testing Architecture

Testing follows agent-native and evidence-first principles.

### Test Categories

- Port contract tests for each port.
- Golden extraction fixture tests.
- Vertical E2E tests per path.
- Dev benchmark slice tests.
- MCP/HTTP parity tests.
- Harness lifecycle parity tests for Claude hook triggers and Copilot/manual checkpoint fallback.
- Rebuild tests from Postgres canonical data.
- Context packet fencing tests.

### Minimum Vertical E2E

```text
remember("I spent $800 on a designer handbag in Miami.")
wait until ready
retrieve("How much did I spend on the handbag?")
assert evidence_status=found
assert result cites exact evidence span
assert context packet includes fenced snippet
```

This is not benchmark gaming; it is a general exact-attribute/evidence/citation capability test.

## Anti-Gaming Architecture Rules

- No dataset-specific runtime branches.
- No benchmark ID checks.
- No gold-answer access in runtime.
- No benchmark-specific extraction types.
- Every improvement must map to general concepts: evidence, attributes, temporal grounding, speaker/session provenance, dynamic type registry, citations, abstention evidence status.
- Benchmark artifacts must include retrieved evidence and not only scores.

## Risks And Mitigations

| Risk | Cause | Mitigation |
| --- | --- | --- |
| Type drift | Dynamic extractor types | Type registry, active/pending states, prompt pruning. |
| Attribute sprawl | Flexible attributes | Light registry, canonical aliases, generic indexing. |
| File/DB drift | Raw files plus Postgres catalog | Hash checks, path safety, readiness diagnostics. |
| Retrieval channel complexity | Pluggable channels too early | Only vector/exact concrete channels Stage 1. |
| LLM performance | Local LLM query/extraction slow | Deterministic baseline, gated optional LLM enrichment. |
| PACore surface creep | Future platform ambition | Future backlog with triggers, Stage 1 non-goals. |
| MCP/HTTP drift | Separate implementations | Application service as only workflow owner. |
| Benchmark gaming | Overfitting to LoCoMo/LongMemEval | General capability rules and evidence artifacts. |
| Quarantine invisibility | Low-confidence memories hidden | Diagnostics and promotion workflow. |
| Raw TTL data loss | Raw files deleted | Evidence capsules and rebuild-from-Postgres contract. |
| Local config fragility | Hard-coded ports, duplicated env parsing, machine-specific defaults | One `.env` source of truth for Compose plus a global typed config module for the app. |

## Downstream Guidance

### For `/deepen-plan`

Deepen only these Stage 1 architecture candidates before implementation:

- extraction envelope and registry governance
- retrieval channel/fusion contracts
- episode file/catalog integrity
- readiness/local traces
- MCP/HTTP parity schemas
- dev benchmark fixture definitions

Do not deepen graph/wiki/decay/reminder implementation; record them in future backlog only.

### For Implementation Planning

Architecture is the invariant artifact, not the rollout order. Execution sequencing now lives in:

`docs/plans/2026-05-13-feat-nucleus-stage-1-harness-memory-foundation-plan.md`

Implementation planning should preserve these priorities while following the plan's slice order:

1. freeze glossary/contract/scope/lifecycle semantics
2. keep one shared application-service layer
3. prove harness tracer bullets before widening quality gates
4. keep benchmark hardening subordinate to evidence needs, not adapter enthusiasm

### For Review

Every PR or phase must answer:

- What user-facing path is now more complete?
- Which wiring arrow was proven?
- Which port contract is exercised?
- What evidence artifact proves it?
- Did any Stage 2 capability leak into Stage 1 code?
- Can an agent achieve same outcome through MCP and HTTP?

## Final Architecture Recommendation

Build Nucleus Stage 1 as a local-first, evidence-grade memory core using ports/adapters. Keep raw episodes transparent in Markdown, extracted memories canonical in Postgres, retrieval indexes rebuildable, and agent interfaces thin. Optimize extraction, attributes, citations, retrieval traces, and lifecycle durability before adding graph/wiki/decay/proactive features. Make future expansion possible through seams, not early implementation.

Current execution authority:

```text
docs/plans/2026-05-13-feat-nucleus-stage-1-harness-memory-foundation-plan.md
```
