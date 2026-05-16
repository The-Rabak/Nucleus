from __future__ import annotations

from dataclasses import dataclass, field

from nucleus.domain.constants import DEFAULT_SCOPE_MODE, SCOPE_POLICY
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
    effective_scope: str = DEFAULT_SCOPE_MODE
    scope_widened: bool = False
    requested_scope_mode: str = DEFAULT_SCOPE_MODE
    scope_policy: str = SCOPE_POLICY

    def to_dict(self) -> JsonObject:
        return {
            "markdown": self.markdown,
            "context_packet": self.context_packet,
            "readiness": self.readiness,
            "observability": self.observability,
            "effective_scope": self.effective_scope,
            "scope_widened": self.scope_widened,
            "requested_scope_mode": self.requested_scope_mode,
            "scope_policy": self.scope_policy,
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
    requested_scope_mode: str = DEFAULT_SCOPE_MODE
    scope_policy: str = SCOPE_POLICY

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
            "requested_scope_mode": self.requested_scope_mode,
            "scope_policy": self.scope_policy,
        }


@dataclass(slots=True)
class SessionCheckpointResult:
    checkpoint_id: str
    recorded_at: str
    effective_scope: str
    readiness: JsonObject
    trigger: str
    idempotency_key: str
    summary: str
    citations: list[JsonObject]
    preview_tokens: JsonObject = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    observability: JsonObject = field(default_factory=dict)
    idempotent: bool = False

    def to_dict(self) -> JsonObject:
        return {
            "checkpoint_id": self.checkpoint_id,
            "recorded_at": self.recorded_at,
            "effective_scope": self.effective_scope,
            "readiness": self.readiness,
            "trigger": self.trigger,
            "idempotency_key": self.idempotency_key,
            "summary": self.summary,
            "citations": self.citations,
            "preview_tokens": self.preview_tokens,
            "warnings": self.warnings,
            "observability": self.observability,
            "idempotent": self.idempotent,
        }


@dataclass(slots=True)
class InspectStatusResult:
    effective_scope: str
    scope_widened: bool
    readiness: JsonObject
    latest_checkpoint: JsonObject | None
    requested_scope_mode: str = DEFAULT_SCOPE_MODE
    scope_policy: str = SCOPE_POLICY
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> JsonObject:
        return {
            "effective_scope": self.effective_scope,
            "scope_widened": self.scope_widened,
            "readiness": self.readiness,
            "latest_checkpoint": self.latest_checkpoint,
            "requested_scope_mode": self.requested_scope_mode,
            "scope_policy": self.scope_policy,
            "warnings": self.warnings,
        }


@dataclass(slots=True)
class MutationPreviewResult:
    operation: str
    preview_token: str
    token_id: str
    issued_at: str
    expires_at: str
    ttl_seconds: int
    effective_scope: str
    requested_scope_mode: str
    scope_policy: str
    scope: JsonObject
    selection: JsonObject
    candidates: list[JsonObject]
    candidate_integrity: JsonObject
    observability: JsonObject = field(default_factory=dict)

    def to_dict(self) -> JsonObject:
        return {
            "operation": self.operation,
            "preview_token": self.preview_token,
            "token_id": self.token_id,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "ttl_seconds": self.ttl_seconds,
            "effective_scope": self.effective_scope,
            "requested_scope_mode": self.requested_scope_mode,
            "scope_policy": self.scope_policy,
            "scope": self.scope,
            "selection": self.selection,
            "candidates": self.candidates,
            "candidate_integrity": self.candidate_integrity,
            "observability": self.observability,
        }


@dataclass(slots=True)
class UpdateConfirmResult:
    operation: str
    effective_scope: str
    requested_scope_mode: str
    scope_policy: str
    applied_count: int
    superseded_episode_ids: list[str]
    replacement_episode_id: str
    audit: JsonObject

    def to_dict(self) -> JsonObject:
        return {
            "operation": self.operation,
            "effective_scope": self.effective_scope,
            "requested_scope_mode": self.requested_scope_mode,
            "scope_policy": self.scope_policy,
            "applied_count": self.applied_count,
            "superseded_episode_ids": self.superseded_episode_ids,
            "replacement_episode_id": self.replacement_episode_id,
            "audit": self.audit,
        }


@dataclass(slots=True)
class ForgetConfirmResult:
    operation: str
    effective_scope: str
    requested_scope_mode: str
    scope_policy: str
    forgotten_episode_ids: list[str]
    audit: JsonObject

    def to_dict(self) -> JsonObject:
        return {
            "operation": self.operation,
            "effective_scope": self.effective_scope,
            "requested_scope_mode": self.requested_scope_mode,
            "scope_policy": self.scope_policy,
            "forgotten_episode_ids": self.forgotten_episode_ids,
            "audit": self.audit,
        }
