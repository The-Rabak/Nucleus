from __future__ import annotations

from dataclasses import dataclass, field

from nucleus.domain.envelopes import JsonObject


@dataclass(slots=True)
class EpisodeRecord:
    episode_id: str
    profile_id: str
    workspace_id: str
    source_type: str
    source_ref: str | None
    session_id: str | None
    turn_index: int | None
    speaker: str | None
    role: str | None
    observed_at: str
    ingested_at: str
    ttl_expires_at: str
    content_hash: str
    raw_file_path: str
    content: str


@dataclass(slots=True)
class Bootcard:
    markdown: str
    context_packet: str
    readiness: JsonObject
    observability: JsonObject = field(default_factory=dict)

    def to_dict(self) -> JsonObject:
        return {
            "markdown": self.markdown,
            "context_packet": self.context_packet,
            "readiness": self.readiness,
            "observability": self.observability,
        }


@dataclass(slots=True)
class RememberResult:
    ingest_id: str
    episode_ids: list[str]
    index_status: str
    readiness_hint: str
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> JsonObject:
        return {
            "ingest_id": self.ingest_id,
            "episode_ids": self.episode_ids,
            "index_status": self.index_status,
            "readiness_hint": self.readiness_hint,
            "warnings": self.warnings,
        }


@dataclass(slots=True)
class RetrieveResult:
    retrieval_id: str
    evidence_status: str
    effective_scope: str
    scope_widened: bool
    results: list[JsonObject]
    context_packet: str
    readiness: JsonObject
    observability: JsonObject = field(default_factory=dict)

    def to_dict(self) -> JsonObject:
        return {
            "retrieval_id": self.retrieval_id,
            "evidence_status": self.evidence_status,
            "effective_scope": self.effective_scope,
            "scope_widened": self.scope_widened,
            "results": self.results,
            "context_packet": self.context_packet,
            "readiness": self.readiness,
            "observability": self.observability,
        }
