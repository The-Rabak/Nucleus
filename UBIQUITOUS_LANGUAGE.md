# Ubiquitous Language

This glossary is the canonical language for Nucleus planning. It exists to prevent PACore-style drift where the same idea was described as WAL, memory item, vector payload, graph node, knowledge page, or route behavior depending on which document was open.

Nucleus terminology should be used in brainstorms, architecture artifacts, contracts, benchmarks, plans, code comments, API schemas, MCP tools, and review findings. If a new term is needed, update this file before using it broadly.

## Product Identity

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Nucleus** | A local-first agent memory core that persists raw source episodes, extracts durable memories with evidence, and retrieves cited evidence for agent harnesses. | PACore v2, memory OS, assistant OS |
| **Memory Core** | Stage 1 product shape focused on `remember -> extract -> retrieve -> cite` quality before broad platform features. | MVP database, vector wrapper, RAG service |
| **Memory Plugin Platform** | Later-stage product shape that adds graph traversal, wiki summaries, decay, richer bootcards, and broader agent workflows after benchmark gates pass. | Assistant OS, all-in-one PA runtime |
| **Benchmark Gate** | Promotion rule requiring evidence-first benchmark quality before enabling Stage 2 platform subsystems by default. | Release gate, quality gate, benchmark score only |
| **Evidence-First Retrieval** | Retrieval quality model where supporting source evidence and citations are evaluated before generated answer accuracy. | RAG score, final answer score, LLM judge score |

## Ownership And Scope

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Profile** | Top-level user-owned memory namespace containing curated files, episodes, extracted memories, indexes, and settings. | tenant, account, user, persona |
| **Workspace** | Optional project or application context inside a profile used to scope memories without creating a separate profile. | project, namespace, tenant |
| **Agent** | Caller identity or harness that uses Nucleus and is recorded as provenance on writes and reads. | tenant, user, profile |
| **Agent Harness** | The external runtime that calls Nucleus through MCP, HTTP, or a library interface and performs reasoning over returned evidence. | client, assistant, agent runtime |
| **Curated File** | Human-maintained profile file that guides behavior or context and cannot be silently overwritten by extraction. | identity memory, system memory, profile row |

## Source Material

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Episode** | One coherent raw source event saved as human-readable Markdown with fixed frontmatter and TTL. | raw memory, chunk, document, turn, WAL row |
| **Episode Body** | Original human-readable Markdown content of an episode. | payload JSON, source blob |
| **Episode Catalog** | Postgres metadata row that indexes a file-backed episode without owning the raw body. | canonical episode row, source table |
| **Source Event** | Real-world input event that becomes an episode, such as a chat turn, tool result, user note, document chunk, or imported record. | source, input, record |
| **Source Reference** | Stable external identifier for where an episode came from, such as chat session ID, turn index, file path, or importer ref. | provenance string, source ID |
| **Raw TTL** | Configurable retention window for raw episode Markdown before cleanup, defaulting to 90 days in Stage 1. | memory expiry, retention, decay |
| **Pinned Episode** | Episode whose raw Markdown file is retained past normal TTL because it is important for audit, debugging, identity, or explicit user choice. | permanent raw memory, exempt file |

## Durable Memory

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Memory** | Agent-facing term for a durable extracted memory returned by APIs and tools. | fact, row, vector point, WAL entry |
| **ExtractedMemory** | Internal precise term for a durable structured memory derived from one or more episodes. | memory item, fact record, vector payload |
| **Statement** | Concise normalized text generated for an extracted memory. | summary, claim only, content |
| **Evidence Span** | Exact quoted text from a source episode that supports an extracted memory. | snippet, context, source text |
| **Evidence Capsule** | Durable proof package stored with an extracted memory so it remains citable after raw episode TTL expires. | citation, provenance, source backup |
| **Attribute** | Flexible normalized property attached to an extracted memory, such as amount, date, location, person, status, object, or polarity. | facet, metadata field, slot |
| **Attribute Registry** | Lightweight registry of canonical attribute names, aliases, types, and normalization hints. | facet schema, metadata dictionary |
| **Type Registry** | Canonical registry of active, proposed, aliased, and promoted memory types available to extraction. | enum list, class registry, memory taxonomy |
| **Proposed Type** | Extractor-suggested type that is stored but not promoted into active future prompts until review or repeated high-confidence use. | unknown type, dynamic type |
| **Canonical Type** | Promoted memory type that future extractions may reuse and prompts may describe. | enum type, approved type |
| **Entity Mention** | Lightweight observed mention of a person, project, place, organization, object, or concept in an episode or memory. | entity, graph node, canonical entity |
| **Relationship Memory** | Extracted memory whose statement describes a relationship between mentions or concepts, without requiring graph traversal. | edge, relation row, graph fact |

## Ingest And Processing

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **IngestEvent** | Internal durable event representing one `remember` operation and its processing lifecycle. | WAL row, write job, memory event |
| **IngestLog** | Narrow WAL-like log that tracks episode persistence, extraction, indexing, readiness, and failures. | broad WAL, replay service, outbox |
| **Remember** | Agent-facing operation that durably records source material as an episode and starts async extraction/indexing. | retain, add memory, write |
| **Extraction** | Process that turns episode content into extracted memories, attributes, evidence spans, and quarantine decisions. | enrichment, parsing, summarization |
| **Deterministic Extractor** | Local non-LLM extraction pass for obvious signals such as dates, numbers, money, speaker metadata, code symbols, and URLs. | heuristic extractor, regex only |
| **Extractor Driver** | Adapter that calls a model runtime such as Ollama or OpenRouter without changing extraction pipeline logic. | LLM client, provider, model wrapper |
| **Extraction Pipeline** | Application service that runs deterministic passes, optional LLM extraction, validation, registry canonicalization, and quarantine. | extractor, orchestrator, worker |
| **Quarantine** | State for extracted memories that are stored for diagnostics/reprocessing but excluded from normal retrieval by default. | rejected, deleted, hidden |
| **Readiness** | Truthful state reporting whether ingest, extraction, and indexing completed enough for reliable retrieval. | health, capability, done |

## Retrieval

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Retrieve** | Agent-facing operation that returns ranked cited memories and a context packet for a query. | search, recall, query |
| **QueryIntent** | Structured analysis of a retrieval query containing optional signals for channels and ranking. | query parse, search params, intent only |
| **Retrieval Channel** | Independent candidate source that can interpret `QueryIntent` and return scored candidates. | backend, searcher, stage |
| **Vector Channel** | Retrieval channel over semantic embeddings stored in the vector index. | dense search, Qdrant search |
| **Exact Channel** | Retrieval channel over normalized memory attributes and identifiers. | facet search, metadata lookup |
| **Lexical Channel** | Retrieval channel over raw words, phrases, and evidence spans, likely Postgres FTS or sparse retrieval after baseline. | BM25, FTS, text search |
| **Fusion** | Combining candidates from multiple retrieval channels into one candidate set. | reranking, scoring, aggregation |
| **FusionRanker** | Deterministic component that fuses channel candidates and applies transparent ranking boosts/penalties. | reranker, scorer |
| **Evidence Status** | Retrieval-level status indicating whether supporting evidence is found, weak, absent, conflicting, or pending. | answer status, confidence only |
| **Context Packet** | Prompt-ready fenced block containing cited evidence snippets, separate from structured retrieval results. | answer context, synthesized answer |
| **Citation** | Machine-readable pointer from a retrieval result to evidence span, episode, source metadata, raw file path or evidence capsule. | provenance, source, reference |

## Phase 2 Scope And Mutation Safety

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Scope Mode (`scope_mode`)** | Explicit request parameter that controls whether a read or mutation preview runs against workspace-only or profile-wide candidates. | scope, widen flag, global toggle |
| **Scope Policy (`scope_policy`)** | Declared enforcement rule for scope handling; Phase 2 uses `per_request_non_sticky` so scope widening applies only to the current request. | scope config, sticky scope, session scope mode |
| **`workspace_local`** | Scope mode value that limits candidates and effects to the active workspace context. | local mode, default scope, project-only (without token) |
| **`profile_global`** | Scope mode value that allows profile-wide candidate selection beyond the active workspace. | global mode, account-wide scope, tenant-global |
| **Preview Token** | Short-lived signed mutation preview credential (`preview_token`) returned by preview operations and required by confirm operations. | draft id, mutation id, one-time code |
| **Preview Token Claims** | Canonical payload fields carried by a preview token (`token_id`, operation, profile/workspace IDs, scope mode, timestamps, candidate integrity). | token metadata, token payload blob |
| **Candidate Integrity** | Deterministic candidate fingerprint map embedded in preview token claims and checked at confirm time to prevent drift between preview and apply. | checksum only, optimistic lock id |

## Derived Artifacts And Future Systems

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Derived Artifact** | Rebuildable output generated from canonical episodes or extracted memories, such as vector indexes, exact indexes, bootcards, summaries, or wiki pages. | canonical memory, source truth |
| **Vector Index** | Rebuildable derived semantic index, with Qdrant as the first Stage 1 adapter. | vector database as source of truth |
| **Exact Index** | Rebuildable derived or queryable index over normalized attributes and identifiers. | benchmark facet table |
| **Bootcard** | Agent startup context assembled from curated files, retrieval protocol, current session context, and a small memory map. | prompt, context dump |
| **Wiki Page** | Stage 2 derived summary artifact synthesized from multiple memories and citations after volume/evidence gates pass. | canonical fact, memory page |
| **Memory Decay** | Stage 2 lifecycle automation that changes relevance or archival state based on age, access, feedback, and confidence. | raw TTL, deletion |
| **Graph Traversal** | Stage 2 retrieval expansion over promoted entities and relationships after relationship extraction proves useful. | relationship memory, entity mentions |
| **Future Capability Backlog** | Non-implementation list of delayed capabilities with value, preserving seam, promotion trigger, and Stage 1 non-goal. | roadmap tasks, nice-to-have list |

## Relationships

- A **Profile** contains zero or more **Workspaces**.
- A **Workspace** contains zero or more **Episodes** and **Memories**.
- An **Agent** writes **Episodes** through **Remember** and receives **Memories** through **Retrieve**.
- An **Episode** is backed by exactly one Markdown file while raw TTL has not expired.
- An **Episode Catalog** row points to exactly one **Episode Body** file path and content hash.
- An **IngestEvent** creates one or more **Episodes** and may produce zero or more **ExtractedMemories**.
- An **ExtractedMemory** must cite at least one **Evidence Span** or be placed in **Quarantine**.
- An **Evidence Capsule** belongs to exactly one **ExtractedMemory** and survives raw episode TTL.
- A **Memory** may have zero or more **Attributes**.
- A **Memory** may mention zero or more **Entity Mentions**.
- A **Relationship Memory** is a **Memory** whose statement and attributes describe a relationship; it is not yet a graph edge in Stage 1.
- A **Retrieval Channel** reads canonical or derived stores and emits candidates; **FusionRanker** combines them.
- A **Context Packet** is derived from retrieval results and does not become canonical memory.
- A **Bootcard** may include **Memories**, but it is a derived artifact, not source truth.
- A **Wiki Page** may summarize **Memories**, but it is Stage 2 and advisory by default.

## Example Dialogue

> **Dev:** "When an agent calls **Remember**, are we storing a **Memory** immediately?"
>
> **Domain expert:** "No. **Remember** creates an **IngestEvent** and persists one or more **Episodes** as Markdown. **Extraction** later creates **ExtractedMemories** with **Evidence Spans**."
>
> **Dev:** "If the raw **Episode** expires after 90 days, can we still cite the **Memory**?"
>
> **Domain expert:** "Yes, if the **ExtractedMemory** has an **Evidence Capsule**. The raw file can disappear; the durable capsule remains citable and indexes can rebuild from Postgres."
>
> **Dev:** "Should a new extractor type like `travel_preference` become part of the prompt forever?"
>
> **Domain expert:** "Not immediately. Store it as a **Proposed Type**, map it through the **Type Registry**, and only promote it to **Canonical Type** after review or repeated high-confidence use."
>
> **Dev:** "When retrieval returns a prompt block, is that trusted instruction context?"
>
> **Domain expert:** "No. The **Context Packet** is untrusted evidence. **RULES.md** is curated and higher authority than retrieved memory snippets."

## Flagged Ambiguities

- **Memory** vs **Episode**: use **Episode** for raw source material and **Memory** for durable extracted knowledge. Do not call raw Markdown files memories in contracts.
- **WAL** vs **IngestEvent**: PACore used WAL heavily; Nucleus should expose **ingest_id** and keep WAL language internal as **IngestLog**.
- **Facet** vs **Attribute**: avoid benchmark-sounding "facets" in product language. Use **Attribute** for flexible normalized properties.
- **Tenant** vs **Profile**: Stage 1 is local profile scoped, not PACore-style SaaS multi-tenant. Use **Profile** unless discussing future hosted isolation.
- **Graph Relationship** vs **Relationship Memory**: Stage 1 extracts relationship memories; Stage 2 may promote them into graph traversal data.
- **Decay** vs **Raw TTL**: raw file TTL deletes source files; decay changes memory relevance/lifecycle later. These are separate.
- **Answer** vs **Evidence**: Nucleus Stage 1 retrieves cited evidence. Agent harnesses or benchmark readers generate answers.
- **Capabilities** vs **Readiness**: avoid synthetic capabilities manifests. Report truthful readiness and configured adapters.
