from __future__ import annotations

from datetime import UTC, datetime, timedelta
import heapq
import hashlib
import json
from pathlib import Path
import re
import secrets
from typing import cast
import uuid

from nucleus.application.scope_validation import validate_scope_identifier
from nucleus.domain.constants import (
    DEFAULT_SCOPE_MODE,
    MutationOperation,
    ScopeMode,
    VALID_PREVIEW_OPERATIONS,
    VALID_SCOPE_MODES,
)
from nucleus.domain.models import EpisodeRecord

_MIN_BOOTCARD_SCAN = 96
_MAX_SEARCH_SCAN = 512
_RECENT_INDEX_LIMIT = 4096
_MAX_AUDIT_EVENTS = 200
_REQUIRED_FRONTMATTER_FIELDS = {
    "episode_id",
    "profile_id",
    "workspace_id",
    "source_type",
    "observed_at",
    "ingested_at",
    "ttl_expires_at",
    "content_hash",
    "sensitivity",
    "extraction_status",
}


class EpisodeStore:
    """Filesystem-backed repository for episode persistence and lifecycle state."""

    def __init__(self, *, data_root: Path) -> None:
        self._data_root = data_root
        self._profiles_root = (self._data_root / "profiles").resolve()

    def persist_episode(self, *, profile_id: str, workspace_id: str, source_type: str, content: str, source_ref: str | None, session_id: str | None, turn_index: int | None, speaker: str | None, role: str | None, observed_at: str | None) -> EpisodeRecord:
        """Persists a source event as an episode markdown file."""
        source_fields = self._source_fields(
            source_type=source_type,
            source_ref=source_ref,
            session_id=session_id,
            turn_index=turn_index,
            speaker=speaker,
            role=role,
        )
        safe_profile_id, safe_workspace_id = self._validated_scope_ids(
            profile_id=profile_id,
            workspace_id=workspace_id,
        )
        metadata, episode_path, frontmatter = self._episode_artifacts(
            profile_id=safe_profile_id,
            workspace_id=safe_workspace_id,
            source_fields=source_fields,
            content=content,
            observed_at=observed_at,
        )
        self._atomic_write_markdown(episode_path, self._render_markdown(frontmatter, content))
        self._record_recent_markdown_path(episode_path=episode_path)
        return self._episode_record(
            profile_id=safe_profile_id,
            workspace_id=safe_workspace_id,
            source_fields=source_fields,
            metadata=metadata,
            raw_file_path=episode_path,
            content=content,
        )

    def _episode_artifacts(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        source_fields: dict[str, object],
        content: str,
        observed_at: str | None,
    ) -> tuple[dict[str, str], Path, dict[str, object]]:
        metadata, ingested_at = self._episode_metadata(content=content, observed_at=observed_at)
        episode_path = self._episode_path(
            profile_id=profile_id,
            workspace_id=workspace_id,
            episode_id=metadata["episode_id"],
            ingested_at=ingested_at,
        )
        frontmatter = self._episode_frontmatter(
            profile_id=profile_id,
            workspace_id=workspace_id,
            source_fields=source_fields,
            metadata=metadata,
        )
        return metadata, episode_path, frontmatter

    @staticmethod
    def _source_fields(
        *,
        source_type: str,
        source_ref: str | None,
        session_id: str | None,
        turn_index: int | None,
        speaker: str | None,
        role: str | None,
    ) -> dict[str, object]:
        return {
            "source_type": source_type,
            "source_ref": source_ref,
            "session_id": session_id,
            "turn_index": turn_index,
            "speaker": speaker,
            "role": role,
        }

    @staticmethod
    def _validated_scope_ids(*, profile_id: str, workspace_id: str) -> tuple[str, str]:
        safe_profile_id = validate_scope_identifier(name="profile_id", value=profile_id)
        safe_workspace_id = validate_scope_identifier(name="workspace_id", value=workspace_id)
        return safe_profile_id, safe_workspace_id

    @staticmethod
    def _episode_metadata(
        *,
        content: str,
        observed_at: str | None,
    ) -> tuple[dict[str, str], datetime]:
        ingested_at = datetime.now(UTC)
        metadata = {
            "episode_id": f"ep_{uuid.uuid4().hex[:12]}",
            "observed_at": observed_at or ingested_at.isoformat(),
            "ingested_at": ingested_at.isoformat(),
            "ttl_expires_at": (ingested_at + timedelta(days=90)).isoformat(),
            "content_hash": f"sha256:{hashlib.sha256(content.encode('utf-8')).hexdigest()}",
        }
        return metadata, ingested_at

    def _episode_path(self, *, profile_id: str, workspace_id: str, episode_id: str, ingested_at: datetime) -> Path:
        episode_dir = self._workspace_episodes_root(
            profile_id=profile_id,
            workspace_id=workspace_id,
        ) / ingested_at.strftime("%Y/%m/%d")
        episode_dir.mkdir(parents=True, exist_ok=True)
        episode_path = episode_dir / f"{episode_id}.md"
        self._ensure_within_profiles_root(episode_path)
        return episode_path

    @staticmethod
    def _episode_frontmatter(
        *,
        profile_id: str,
        workspace_id: str,
        source_fields: dict[str, object],
        metadata: dict[str, str],
    ) -> dict[str, object]:
        return {
            "episode_id": metadata["episode_id"],
            "profile_id": profile_id,
            "workspace_id": workspace_id,
            **source_fields,
            "observed_at": metadata["observed_at"],
            "ingested_at": metadata["ingested_at"],
            "ttl_expires_at": metadata["ttl_expires_at"],
            "content_hash": metadata["content_hash"],
            "sensitivity": "internal",
            "extraction_status": "episode_persisted",
            "schema_version": "nucleus.episode.v1",
        }

    @staticmethod
    def _episode_record(
        *,
        profile_id: str,
        workspace_id: str,
        source_fields: dict[str, object],
        metadata: dict[str, str],
        raw_file_path: Path,
        content: str,
    ) -> EpisodeRecord:
        return EpisodeRecord(
            episode_id=metadata["episode_id"],
            profile_id=profile_id,
            workspace_id=workspace_id,
            source_type=str(source_fields["source_type"]),
            source_ref=source_fields["source_ref"] if isinstance(source_fields["source_ref"], str) else None,
            session_id=source_fields["session_id"] if isinstance(source_fields["session_id"], str) else None,
            turn_index=source_fields["turn_index"] if isinstance(source_fields["turn_index"], int) else None,
            speaker=source_fields["speaker"] if isinstance(source_fields["speaker"], str) else None,
            role=source_fields["role"] if isinstance(source_fields["role"], str) else None,
            observed_at=metadata["observed_at"],
            ingested_at=metadata["ingested_at"],
            ttl_expires_at=metadata["ttl_expires_at"],
            content_hash=metadata["content_hash"],
            raw_file_path=str(raw_file_path),
            content=content,
        )

    def list_recent(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        limit: int = 3,
    ) -> tuple[list[EpisodeRecord], dict[str, int]]:
        episodes, scan_counters = self._load_workspace_episodes(
            profile_id=profile_id,
            workspace_id=workspace_id,
            max_files=max(limit * 32, _MIN_BOOTCARD_SCAN),
            include_inactive=False,
        )
        return heapq.nlargest(limit, episodes, key=lambda item: item.observed_at), scan_counters

    def search(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        query: str,
        top_k: int = 5,
        scope_mode: str = DEFAULT_SCOPE_MODE,
    ) -> tuple[list[EpisodeRecord], dict[str, int]]:
        """Searches episodes using token overlap scoring."""
        tokens = self._query_tokens(query)
        episodes, scan_counters = self._episodes_for_scope(
            profile_id=profile_id,
            workspace_id=workspace_id,
            top_k=top_k,
            scope_mode=scope_mode,
        )
        scan_counters["query_token_count"] = len(tokens)
        if not tokens:
            return episodes[:top_k], scan_counters

        scored = self._score_episodes(episodes=episodes, tokens=tokens)
        scan_counters["match_count"] = len(scored)
        top_scored = heapq.nlargest(top_k, scored, key=lambda item: (item[0], item[1].observed_at))
        return [episode for _, episode in top_scored], scan_counters

    @staticmethod
    def _query_tokens(query: str) -> list[str]:
        return [token.lower() for token in re.findall(r"\w+", query)]

    def _episodes_for_scope(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        top_k: int,
        scope_mode: str,
    ) -> tuple[list[EpisodeRecord], dict[str, int]]:
        resolved_scope_mode = self._validated_scope_mode(scope_mode)
        max_files = max(top_k * 64, _MAX_SEARCH_SCAN)
        if resolved_scope_mode == ScopeMode.WORKSPACE_LOCAL.value:
            return self._load_workspace_episodes(
                profile_id=profile_id,
                workspace_id=workspace_id,
                max_files=max_files,
                include_inactive=False,
            )
        if resolved_scope_mode == ScopeMode.PROFILE_GLOBAL.value:
            return self._load_profile_episodes(
                profile_id=profile_id,
                max_files=max_files,
                include_inactive=False,
            )
        raise AssertionError("validated scope_mode must resolve to a known scope.")

    @staticmethod
    def _score_episodes(*, episodes: list[EpisodeRecord], tokens: list[str]) -> list[tuple[int, EpisodeRecord]]:
        scored: list[tuple[int, EpisodeRecord]] = []
        for episode in episodes:
            score = sum(1 for token in tokens if token in episode.content.lower())
            if score:
                scored.append((score, episode))
        return scored

    def candidate_integrity(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        episode_ids: list[str],
        scope_mode: str = DEFAULT_SCOPE_MODE,
    ) -> dict[str, dict[str, str]]:
        """Builds integrity snapshots used to validate preview confirmation."""
        if not episode_ids:
            return {}

        episode_by_id = self._episode_index_for_scope(
            profile_id=profile_id,
            workspace_id=workspace_id,
            scope_mode=scope_mode,
            episode_ids=episode_ids,
        )
        lifecycle_cache: dict[tuple[str, str], dict[str, object]] = {}
        integrity: dict[str, dict[str, str]] = {}
        for episode_id in dict.fromkeys(episode_ids):
            snapshot = self._integrity_snapshot(
                episode_id=episode_id,
                episode_by_id=episode_by_id,
                lifecycle_cache=lifecycle_cache,
            )
            if snapshot is not None:
                integrity[episode_id] = snapshot
        return integrity

    def _episode_index_for_scope(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        scope_mode: str,
        episode_ids: list[str] | None = None,
    ) -> dict[str, EpisodeRecord]:
        resolved_scope_mode = self._validated_scope_mode(scope_mode)
        if episode_ids:
            return self._episode_index_for_selected_ids(
                profile_id=profile_id,
                workspace_id=workspace_id,
                scope_mode=resolved_scope_mode,
                episode_ids=episode_ids,
            )
        if resolved_scope_mode == ScopeMode.WORKSPACE_LOCAL.value:
            episodes, _ = self._load_workspace_episodes(
                profile_id=profile_id,
                workspace_id=workspace_id,
                include_inactive=True,
            )
        else:
            episodes, _ = self._load_profile_episodes(
                profile_id=profile_id,
                include_inactive=True,
            )
        return {episode.episode_id: episode for episode in episodes}

    def _episode_index_for_selected_ids(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        scope_mode: str,
        episode_ids: list[str],
    ) -> dict[str, EpisodeRecord]:
        requested_ids = list(dict.fromkeys(episode_ids))
        if scope_mode == ScopeMode.WORKSPACE_LOCAL.value:
            workspace_root = self._workspace_episodes_root(
                profile_id=profile_id,
                workspace_id=workspace_id,
            )
            return self._episode_index_from_workspace_root(
                workspace_root=workspace_root,
                episode_ids=requested_ids,
            )

        profile_workspaces_root = self._profiles_root / profile_id / "workspaces"
        self._ensure_within_profiles_root(profile_workspaces_root)
        if not profile_workspaces_root.exists():
            return {}
        remaining_ids = set(requested_ids)
        indexed: dict[str, EpisodeRecord] = {}
        for workspace_root in self._workspace_episode_roots(
            profile_workspaces_root=profile_workspaces_root,
        ):
            matched = self._episode_index_from_workspace_root(
                workspace_root=workspace_root,
                episode_ids=list(remaining_ids),
            )
            indexed.update(matched)
            remaining_ids.difference_update(matched.keys())
            if not remaining_ids:
                break
        return indexed

    def _episode_index_from_workspace_root(
        self,
        *,
        workspace_root: Path,
        episode_ids: list[str],
    ) -> dict[str, EpisodeRecord]:
        if not workspace_root.exists() or not episode_ids:
            return {}
        scan_counters = self._default_scan_counters(max_files=len(episode_ids))
        indexed: dict[str, EpisodeRecord] = {}
        for episode_id in episode_ids:
            markdown_file = self._find_episode_markdown_file(
                workspace_root=workspace_root,
                episode_id=episode_id,
            )
            if markdown_file is None:
                continue
            episode = self._load_episode_from_markdown(
                markdown_file=markdown_file,
                scan_counters=scan_counters,
            )
            if episode is not None:
                indexed[episode.episode_id] = episode
        return indexed

    def _find_episode_markdown_file(
        self,
        *,
        workspace_root: Path,
        episode_id: str,
    ) -> Path | None:
        safe_episode_id = validate_scope_identifier(name="episode_id", value=episode_id)
        indexed_candidates = self._workspace_markdown_files_from_index(
            root=workspace_root,
            max_files=_RECENT_INDEX_LIMIT,
        )
        for markdown_file in indexed_candidates:
            if markdown_file.stem == safe_episode_id:
                return markdown_file
        for markdown_file in workspace_root.glob(f"**/{safe_episode_id}.md"):
            return markdown_file
        return None

    def _integrity_snapshot(
        self,
        *,
        episode_id: str,
        episode_by_id: dict[str, EpisodeRecord],
        lifecycle_cache: dict[tuple[str, str], dict[str, object]],
    ) -> dict[str, str] | None:
        episode = episode_by_id.get(episode_id)
        if episode is None:
            return None
        lifecycle_state = self._load_lifecycle_state_cached(
            cache=lifecycle_cache,
            profile_id=episode.profile_id,
            workspace_id=episode.workspace_id,
        )
        episode_state = self._lifecycle_episode_state(
            lifecycle_state=lifecycle_state,
            episode_id=episode_id,
        )
        return {
            "state_hash": self._state_hash(episode=episode, episode_state=episode_state),
            "source_hash": episode.content_hash,
            "workspace_id": episode.workspace_id,
        }

    def register_preview_token(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        operation: str,
        scope_mode: str,
        token_id: str,
        issued_at: str,
        expires_at: str,
        claims_digest: str,
    ) -> None:
        self._validate_preview_operation(operation)
        self._validated_scope_mode(scope_mode)
        lifecycle_state = self._read_lifecycle_state(
            profile_id=profile_id,
            workspace_id=workspace_id,
        )
        preview_tokens = cast(dict[str, object], lifecycle_state["preview_tokens"])
        preview_tokens[self._preview_token_key(operation=operation, scope_mode=scope_mode)] = {
            "token_id": token_id,
            "issued_at": issued_at,
            "expires_at": expires_at,
            "claims_digest": claims_digest,
        }
        self._write_lifecycle_state(
            profile_id=profile_id,
            workspace_id=workspace_id,
            lifecycle_state=lifecycle_state,
        )

    def preview_token_snapshot(
        self,
        *,
        profile_id: str,
        workspace_id: str,
    ) -> dict[str, dict[str, str]]:
        lifecycle_state = self._read_lifecycle_state(
            profile_id=profile_id,
            workspace_id=workspace_id,
        )
        preview_tokens = cast(dict[str, object], lifecycle_state["preview_tokens"])
        snapshot: dict[str, dict[str, str]] = {}
        for token_key, entry in preview_tokens.items():
            if not isinstance(token_key, str) or not isinstance(entry, dict):
                continue
            raw_entry = cast(dict[object, object], entry)
            if not all(isinstance(key, str) and isinstance(value, str) for key, value in raw_entry.items()):
                continue
            snapshot[token_key] = cast(dict[str, str], dict(raw_entry))
        return snapshot

    def preview_token_signing_key(
        self,
        *,
        profile_id: str,
        workspace_id: str,
    ) -> str:
        _ = (profile_id, workspace_id)
        key_path = self._preview_signing_key_path()
        if key_path.exists():
            try:
                payload = json.loads(key_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                payload = {}
            if isinstance(payload, dict):
                existing = payload.get("signing_key")
                if isinstance(existing, str) and existing:
                    return existing
        signing_key = secrets.token_urlsafe(32)
        key_path.parent.mkdir(parents=True, exist_ok=True)
        self._atomic_write_json(key_path, {"signing_key": signing_key})
        return signing_key

    def lifecycle_state_metrics(
        self,
        *,
        profile_id: str,
        workspace_id: str,
    ) -> dict[str, int]:
        state_path = self._lifecycle_state_path(profile_id=profile_id, workspace_id=workspace_id)
        raw_bytes = 0
        if state_path.exists():
            try:
                raw_bytes = len(state_path.read_bytes())
            except OSError:
                raw_bytes = -1
        lifecycle_state = self._read_lifecycle_state(
            profile_id=profile_id,
            workspace_id=workspace_id,
        )
        preview_tokens = cast(dict[str, object], lifecycle_state["preview_tokens"])
        episode_states = cast(dict[str, object], lifecycle_state["episode_states"])
        audit_events = cast(list[object], lifecycle_state["audit_events"])
        return {
            "lifecycle_state_bytes": raw_bytes,
            "preview_token_count": len(preview_tokens),
            "episode_state_count": len(episode_states),
            "audit_event_count": len(audit_events),
            "max_audit_events": _MAX_AUDIT_EVENTS,
        }

    def is_preview_token_active(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        operation: str,
        scope_mode: str,
        token_id: str,
        claims_digest: str,
        now: datetime,
    ) -> bool:
        self._validate_preview_operation(operation)
        self._validated_scope_mode(scope_mode)
        lifecycle_state = self._read_lifecycle_state(
            profile_id=profile_id,
            workspace_id=workspace_id,
        )
        preview_tokens = cast(dict[str, object], lifecycle_state["preview_tokens"])
        entry = preview_tokens.get(self._preview_token_key(operation=operation, scope_mode=scope_mode))
        if not isinstance(entry, dict):
            return False
        if entry.get("token_id") != token_id:
            return False
        if entry.get("claims_digest") != claims_digest:
            return False
        expires_at = self._parse_iso_datetime(str(entry.get("expires_at")))
        if expires_at is None:
            return False
        return now <= expires_at

    def invalidate_preview_token(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        operation: str,
        scope_mode: str,
        token_id: str,
    ) -> None:
        self._validate_preview_operation(operation)
        self._validated_scope_mode(scope_mode)
        lifecycle_state = self._read_lifecycle_state(
            profile_id=profile_id,
            workspace_id=workspace_id,
        )
        preview_tokens = cast(dict[str, object], lifecycle_state["preview_tokens"])
        token_key = self._preview_token_key(operation=operation, scope_mode=scope_mode)
        entry = preview_tokens.get(token_key)
        if isinstance(entry, dict) and entry.get("token_id") == token_id:
            del preview_tokens[token_key]
            self._write_lifecycle_state(
                profile_id=profile_id,
                workspace_id=workspace_id,
                lifecycle_state=lifecycle_state,
            )

    def mark_superseded(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        episode_ids: list[str],
        replacement_episode_id: str,
        token_id: str,
        scope_mode: str,
    ) -> dict[str, object]:
        """Marks selected episodes as superseded by a replacement episode."""
        return self._apply_mutation(
            profile_id=profile_id,
            workspace_id=workspace_id,
            episode_ids=episode_ids,
            operation=MutationOperation.UPDATE_CONFIRM.value,
            token_id=token_id,
            scope_mode=scope_mode,
            replacement_episode_id=replacement_episode_id,
        )

    def mark_forgotten(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        episode_ids: list[str],
        token_id: str,
        scope_mode: str,
    ) -> dict[str, object]:
        """Marks selected episodes as forgotten and records an audit event."""
        return self._apply_mutation(
            profile_id=profile_id,
            workspace_id=workspace_id,
            episode_ids=episode_ids,
            operation=MutationOperation.FORGET_CONFIRM.value,
            token_id=token_id,
            scope_mode=scope_mode,
        )

    def _apply_mutation(self, *, profile_id: str, workspace_id: str, episode_ids: list[str], operation: str, token_id: str, scope_mode: str, replacement_episode_id: str | None = None) -> dict[str, object]:
        lifecycle_state, selected_episode_ids, recorded_at = self._prepare_mutation(
            profile_id=profile_id,
            workspace_id=workspace_id,
            episode_ids=episode_ids,
            scope_mode=scope_mode,
        )
        self._apply_mutation_state(
            lifecycle_state=lifecycle_state,
            selected_episode_ids=selected_episode_ids,
            recorded_at=recorded_at,
            replacement_episode_id=replacement_episode_id,
        )
        audit_event = self._append_audit_event(
            lifecycle_state=lifecycle_state,
            operation=operation,
            token_id=token_id,
            scope_mode=scope_mode,
            selected_episode_ids=selected_episode_ids,
            recorded_at=recorded_at,
            replacement_episode_id=replacement_episode_id,
        )
        return self._finalize_mutation(profile_id=profile_id, workspace_id=workspace_id, lifecycle_state=lifecycle_state, audit_event=audit_event, operation=operation, selected_episode_ids=selected_episode_ids, replacement_episode_id=replacement_episode_id)

    def _finalize_mutation(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        lifecycle_state: dict[str, object],
        audit_event: dict[str, object],
        operation: str,
        selected_episode_ids: list[str],
        replacement_episode_id: str | None,
    ) -> dict[str, object]:
        self._write_lifecycle_state(
            profile_id=profile_id,
            workspace_id=workspace_id,
            lifecycle_state=lifecycle_state,
        )
        return self._mutation_result(
            audit_event=audit_event,
            operation=operation,
            selected_episode_ids=selected_episode_ids,
            replacement_episode_id=replacement_episode_id,
        )

    def _apply_mutation_state(
        self,
        *,
        lifecycle_state: dict[str, object],
        selected_episode_ids: list[str],
        recorded_at: str,
        replacement_episode_id: str | None,
    ) -> None:
        if replacement_episode_id is not None:
            self._apply_superseded_state(
                lifecycle_state=lifecycle_state,
                selected_episode_ids=selected_episode_ids,
                replacement_episode_id=replacement_episode_id,
                recorded_at=recorded_at,
            )
            return
        self._apply_forgotten_state(
            lifecycle_state=lifecycle_state,
            selected_episode_ids=selected_episode_ids,
            recorded_at=recorded_at,
        )

    def _prepare_mutation(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        episode_ids: list[str],
        scope_mode: str,
    ) -> tuple[dict[str, object], list[str], str]:
        integrity = self.candidate_integrity(
            profile_id=profile_id,
            workspace_id=workspace_id,
            episode_ids=episode_ids,
            scope_mode=scope_mode,
        )
        self._assert_mutation_scope(
            integrity=integrity,
            workspace_id=workspace_id,
            expected_episode_ids=episode_ids,
        )
        lifecycle_state = self._read_lifecycle_state(
            profile_id=profile_id,
            workspace_id=workspace_id,
        )
        return lifecycle_state, sorted(set(episode_ids)), datetime.now(UTC).isoformat()

    def _apply_superseded_state(
        self,
        *,
        lifecycle_state: dict[str, object],
        selected_episode_ids: list[str],
        replacement_episode_id: str,
        recorded_at: str,
    ) -> None:
        episode_states = cast(dict[str, object], lifecycle_state["episode_states"])
        for episode_id in selected_episode_ids:
            episode_state = self._mutable_episode_state(episode_states=episode_states, episode_id=episode_id)
            episode_state["superseded_by_episode_id"] = replacement_episode_id
            episode_state["superseded_at"] = recorded_at

    def _apply_forgotten_state(
        self,
        *,
        lifecycle_state: dict[str, object],
        selected_episode_ids: list[str],
        recorded_at: str,
    ) -> None:
        episode_states = cast(dict[str, object], lifecycle_state["episode_states"])
        for episode_id in selected_episode_ids:
            episode_state = self._mutable_episode_state(episode_states=episode_states, episode_id=episode_id)
            episode_state["forgotten_at"] = recorded_at

    def _append_audit_event(
        self,
        *,
        lifecycle_state: dict[str, object],
        operation: str,
        token_id: str,
        scope_mode: str,
        selected_episode_ids: list[str],
        recorded_at: str,
        replacement_episode_id: str | None = None,
    ) -> dict[str, object]:
        audit_event = {
            "event_id": f"evt_{uuid.uuid4().hex[:12]}",
            "operation": operation,
            "recorded_at": recorded_at,
            "token_id": token_id,
            "scope_mode": scope_mode,
            "selected_episode_ids": selected_episode_ids,
        }
        if replacement_episode_id is not None:
            audit_event["replacement_episode_id"] = replacement_episode_id
        audit_events = cast(list[object], lifecycle_state["audit_events"])
        audit_events.append(audit_event)
        if len(audit_events) > _MAX_AUDIT_EVENTS:
            del audit_events[:-_MAX_AUDIT_EVENTS]
        return audit_event

    @staticmethod
    def _mutation_result(
        *,
        audit_event: dict[str, object],
        operation: str,
        selected_episode_ids: list[str],
        replacement_episode_id: str | None = None,
    ) -> dict[str, object]:
        result: dict[str, object] = {
            "event_id": audit_event["event_id"],
            "recorded_at": audit_event["recorded_at"],
            "preserved": True,
            "operation": operation,
            "selected_episode_ids": selected_episode_ids,
        }
        if replacement_episode_id is not None:
            result["replacement_episode_id"] = replacement_episode_id
        return result

    def _load_profile_episodes(
        self,
        *,
        profile_id: str,
        max_files: int | None = None,
        include_inactive: bool = False,
    ) -> tuple[list[EpisodeRecord], dict[str, int]]:
        safe_profile_id = validate_scope_identifier(name="profile_id", value=profile_id)
        profile_workspaces_root = self._profiles_root / safe_profile_id / "workspaces"
        self._ensure_within_profiles_root(profile_workspaces_root)
        if not profile_workspaces_root.exists():
            return [], self._default_scan_counters(max_files=max_files)
        markdown_files = self._profile_markdown_files(
            profile_workspaces_root=profile_workspaces_root,
            max_files=max_files,
        )
        return self._scan_episode_files(
            markdown_files=markdown_files,
            max_files=max_files,
            include_inactive=include_inactive,
            profile_id_filter=safe_profile_id,
        )

    def _load_workspace_episodes(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        max_files: int | None = None,
        include_inactive: bool = False,
    ) -> tuple[list[EpisodeRecord], dict[str, int]]:
        safe_profile_id = validate_scope_identifier(name="profile_id", value=profile_id)
        safe_workspace_id = validate_scope_identifier(name="workspace_id", value=workspace_id)
        workspace_dir = self._workspace_episodes_root(
            profile_id=safe_profile_id,
            workspace_id=safe_workspace_id,
        )
        if not workspace_dir.exists():
            return [], self._default_scan_counters(max_files=max_files)
        markdown_files = self._workspace_markdown_files(root=workspace_dir, max_files=max_files)
        return self._scan_episode_files(
            markdown_files=markdown_files,
            max_files=max_files,
            include_inactive=include_inactive,
        )

    def _profile_markdown_files(
        self,
        *,
        profile_workspaces_root: Path,
        max_files: int | None,
    ) -> list[Path]:
        if max_files is None:
            return sorted(
                profile_workspaces_root.rglob("*.md"),
                key=EpisodeStore._markdown_sort_key,
                reverse=True,
            )
        if max_files < 1:
            return []
        workspace_roots = self._workspace_episode_roots(profile_workspaces_root=profile_workspaces_root)
        candidates: list[tuple[tuple[float, str], Path]] = []
        for workspace_root in workspace_roots:
            for markdown_file in self._workspace_markdown_files(
                root=workspace_root,
                max_files=max_files,
            ):
                entry = (self._markdown_sort_key(markdown_file), markdown_file)
                if len(candidates) < max_files:
                    heapq.heappush(candidates, entry)
                    continue
                heapq.heappushpop(candidates, entry)
        ordered = sorted(candidates, key=lambda item: item[0], reverse=True)
        return [path for _, path in ordered]

    @staticmethod
    def _workspace_episode_roots(*, profile_workspaces_root: Path) -> list[Path]:
        try:
            workspace_roots = [
                workspace_dir / "episodes"
                for workspace_dir in profile_workspaces_root.iterdir()
                if workspace_dir.is_dir() and (workspace_dir / "episodes").is_dir()
            ]
        except OSError:
            return []
        return sorted(workspace_roots, reverse=True)

    @staticmethod
    def _workspace_markdown_files(*, root: Path, max_files: int | None) -> list[Path]:
        if max_files is None:
            return sorted(root.rglob("*.md"), key=EpisodeStore._markdown_sort_key, reverse=True)
        if max_files < 1:
            return []
        indexed_markdown_files = EpisodeStore._workspace_markdown_files_from_index(
            root=root,
            max_files=max_files,
        )
        if len(indexed_markdown_files) >= max_files:
            return indexed_markdown_files
        markdown_files: list[Path] = []
        for day_dir in EpisodeStore._episode_day_dirs_desc(root=root):
            for markdown_file in sorted(
                day_dir.glob("*.md"),
                key=EpisodeStore._markdown_sort_key,
                reverse=True,
            ):
                markdown_files.append(markdown_file)
                if len(markdown_files) >= max_files:
                    break
            if len(markdown_files) >= max_files:
                break
        merged = EpisodeStore._dedupe_markdown_paths(
            indexed_markdown_files + markdown_files,
            max_files=max_files,
        )
        EpisodeStore._write_recent_index_rel_paths(
            root=root,
            rel_paths=[
                EpisodeStore._relative_markdown_path(root=root, markdown_file=path)
                for path in merged[:_RECENT_INDEX_LIMIT]
            ],
        )
        return merged

    @staticmethod
    def _workspace_recent_index_path(*, root: Path) -> Path:
        return root / ".recent-index.json"

    @staticmethod
    def _record_recent_markdown_path(*, episode_path: Path) -> None:
        if len(episode_path.parents) < 4:
            return
        episodes_root = episode_path.parents[3]
        if not episodes_root.is_dir():
            return
        existing_rel_paths = EpisodeStore._load_recent_index_rel_paths(root=episodes_root)
        current_rel_path = EpisodeStore._relative_markdown_path(
            root=episodes_root,
            markdown_file=episode_path,
        )
        updated_rel_paths = [current_rel_path]
        updated_rel_paths.extend(path for path in existing_rel_paths if path != current_rel_path)
        EpisodeStore._write_recent_index_rel_paths(
            root=episodes_root,
            rel_paths=updated_rel_paths[:_RECENT_INDEX_LIMIT],
        )

    @staticmethod
    def _workspace_markdown_files_from_index(*, root: Path, max_files: int) -> list[Path]:
        recent_rel_paths = EpisodeStore._load_recent_index_rel_paths(root=root)
        markdown_files: list[Path] = []
        for rel_path in recent_rel_paths:
            markdown_file = root / rel_path
            if not markdown_file.exists() or not markdown_file.is_file():
                continue
            markdown_files.append(markdown_file)
            if len(markdown_files) >= max_files:
                break
        return markdown_files

    @staticmethod
    def _load_recent_index_rel_paths(*, root: Path) -> list[str]:
        index_path = EpisodeStore._workspace_recent_index_path(root=root)
        if not index_path.exists():
            return []
        try:
            payload = json.loads(index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        if not isinstance(payload, dict):
            return []
        raw_paths = payload.get("recent_markdown_paths")
        if not isinstance(raw_paths, list):
            return []
        return [path for path in raw_paths if isinstance(path, str)]

    @staticmethod
    def _write_recent_index_rel_paths(*, root: Path, rel_paths: list[str]) -> None:
        index_path = EpisodeStore._workspace_recent_index_path(root=root)
        index_path.parent.mkdir(parents=True, exist_ok=True)
        EpisodeStore._atomic_write_json(
            index_path,
            {"recent_markdown_paths": rel_paths[:_RECENT_INDEX_LIMIT]},
        )

    @staticmethod
    def _relative_markdown_path(*, root: Path, markdown_file: Path) -> str:
        return str(markdown_file.resolve().relative_to(root.resolve()))

    @staticmethod
    def _dedupe_markdown_paths(paths: list[Path], *, max_files: int) -> list[Path]:
        deduped: list[Path] = []
        seen: set[Path] = set()
        for path in paths:
            if path in seen:
                continue
            seen.add(path)
            deduped.append(path)
            if len(deduped) >= max_files:
                break
        return deduped

    @staticmethod
    def _episode_day_dirs_desc(*, root: Path) -> list[Path]:
        day_dirs: list[Path] = []
        for year_dir in EpisodeStore._numeric_dirs_desc(root=root, min_value=1, max_value=9999):
            for month_dir in EpisodeStore._numeric_dirs_desc(root=year_dir, min_value=1, max_value=12):
                day_dirs.extend(
                    EpisodeStore._numeric_dirs_desc(
                        root=month_dir,
                        min_value=1,
                        max_value=31,
                    )
                )
        return day_dirs

    @staticmethod
    def _numeric_dirs_desc(
        *,
        root: Path,
        min_value: int,
        max_value: int,
    ) -> list[Path]:
        numbered_dirs: list[tuple[int, Path]] = []
        try:
            children = list(root.iterdir())
        except OSError:
            return []
        for child in children:
            if not child.is_dir():
                continue
            try:
                number = int(child.name)
            except ValueError:
                continue
            if number < min_value or number > max_value:
                continue
            numbered_dirs.append((number, child))
        numbered_dirs.sort(key=lambda item: item[0], reverse=True)
        return [directory for _, directory in numbered_dirs]

    def _scan_episode_files(
        self,
        *,
        markdown_files: list[Path],
        max_files: int | None,
        include_inactive: bool,
        profile_id_filter: str | None = None,
    ) -> tuple[list[EpisodeRecord], dict[str, int]]:
        episodes: list[EpisodeRecord] = []
        scan_counters = self._default_scan_counters(max_files=max_files)
        lifecycle_cache: dict[tuple[str, str], dict[str, object]] = {}
        for markdown_file in markdown_files:
            episode = self._load_episode_from_markdown(markdown_file=markdown_file, scan_counters=scan_counters)
            if episode is None:
                continue
            if profile_id_filter is not None and episode.profile_id != profile_id_filter:
                scan_counters["scope_filtered"] += 1
                continue
            if self._should_filter_lifecycle(episode=episode, include_inactive=include_inactive, lifecycle_cache=lifecycle_cache, scan_counters=scan_counters):
                continue
            episodes.append(episode)
        scan_counters["loaded_records"] = len(episodes)
        return episodes, scan_counters

    def _load_episode_from_markdown(
        self,
        *,
        markdown_file: Path,
        scan_counters: dict[str, int],
    ) -> EpisodeRecord | None:
        scan_counters["scanned_files"] += 1
        try:
            parsed = self._parse_markdown(markdown_file)
        except (OSError, ValueError, json.JSONDecodeError):
            scan_counters["parse_failures"] += 1
            return None
        if parsed is None:
            scan_counters["parse_failures"] += 1
            return None
        frontmatter, content = parsed
        episode = self._episode_from_frontmatter(
            frontmatter=frontmatter,
            content=content,
            raw_file_path=markdown_file,
        )
        if episode is None:
            scan_counters["invalid_records"] += 1
            return None
        if self._is_expired(episode.ttl_expires_at):
            scan_counters["expired_filtered"] += 1
            return None
        return episode

    def _should_filter_lifecycle(
        self,
        *,
        episode: EpisodeRecord,
        include_inactive: bool,
        lifecycle_cache: dict[tuple[str, str], dict[str, object]],
        scan_counters: dict[str, int],
    ) -> bool:
        if include_inactive:
            return False
        if not self._is_lifecycle_hidden(episode=episode, lifecycle_cache=lifecycle_cache):
            return False
        scan_counters["lifecycle_filtered"] += 1
        return True

    @staticmethod
    def _render_markdown(frontmatter: dict[str, object], content: str) -> str:
        lines = ["---"]
        for key, value in frontmatter.items():
            lines.append(f"{key}: {EpisodeStore._scalar_to_yaml(value)}")
        lines.append("---")
        lines.append("")
        lines.append(content)
        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _scalar_to_yaml(value: object) -> str:
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, int):
            return str(value)
        return json.dumps(str(value))

    @staticmethod
    def _parse_markdown(path: Path) -> tuple[dict[str, object], str] | None:
        raw_text = path.read_text(encoding="utf-8")
        if not raw_text.startswith("---\n"):
            return None

        lines = raw_text.splitlines()
        cursor = 1
        frontmatter: dict[str, object] = {}
        while cursor < len(lines):
            line = lines[cursor]
            cursor += 1
            if line == "---":
                break
            if not line or ":" not in line:
                continue
            key, raw_value = line.split(":", 1)
            frontmatter[key.strip()] = EpisodeStore._parse_scalar(raw_value.strip())

        content = "\n".join(lines[cursor:]).strip()
        return frontmatter, content

    @staticmethod
    def _is_expired(ttl_expires_at: str) -> bool:
        try:
            expires_at = datetime.fromisoformat(ttl_expires_at)
        except ValueError:
            return False
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        return expires_at < datetime.now(UTC)

    def _workspace_root(self, *, profile_id: str, workspace_id: str) -> Path:
        safe_profile_id = validate_scope_identifier(name="profile_id", value=profile_id)
        safe_workspace_id = validate_scope_identifier(name="workspace_id", value=workspace_id)
        workspace_root = self._profiles_root / safe_profile_id / "workspaces" / safe_workspace_id
        self._ensure_within_profiles_root(workspace_root)
        return workspace_root

    def _workspace_episodes_root(self, *, profile_id: str, workspace_id: str) -> Path:
        path = self._workspace_root(profile_id=profile_id, workspace_id=workspace_id) / "episodes"
        self._ensure_within_profiles_root(path)
        return path

    def _lifecycle_state_path(self, *, profile_id: str, workspace_id: str) -> Path:
        path = self._workspace_root(profile_id=profile_id, workspace_id=workspace_id) / "lifecycle" / "state.json"
        self._ensure_within_profiles_root(path)
        return path

    def _ensure_within_profiles_root(self, path: Path) -> None:
        resolved = path.resolve()
        try:
            resolved.relative_to(self._profiles_root)
        except ValueError as exc:
            raise ValueError("Resolved path escapes configured profiles root.") from exc

    @staticmethod
    def _atomic_write_markdown(path: Path, content: str) -> None:
        temp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        temp_path.write_text(content, encoding="utf-8")
        temp_path.replace(path)

    @staticmethod
    def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
        temp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        temp_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        temp_path.replace(path)

    @staticmethod
    def _markdown_sort_key(path: Path) -> tuple[float, str]:
        try:
            modified_at = path.stat().st_mtime
        except OSError:
            modified_at = -1.0
        return modified_at, str(path)

    @staticmethod
    def _default_scan_counters(*, max_files: int | None) -> dict[str, int]:
        return {
            "scanned_files": 0,
            "loaded_records": 0,
            "expired_filtered": 0,
            "parse_failures": 0,
            "invalid_records": 0,
            "scope_filtered": 0,
            "lifecycle_filtered": 0,
            "scan_budget": -1 if max_files is None else max_files,
        }

    @staticmethod
    def _episode_from_frontmatter(
        *,
        frontmatter: dict[str, object],
        content: str,
        raw_file_path: Path,
    ) -> EpisodeRecord | None:
        if not _REQUIRED_FRONTMATTER_FIELDS.issubset(frontmatter):
            return None
        observed_at = EpisodeStore._observed_at(frontmatter)
        if observed_at is None:
            return None
        return EpisodeStore._build_episode_record(
            frontmatter=frontmatter,
            content=content,
            raw_file_path=raw_file_path,
            observed_at=observed_at,
        )

    @staticmethod
    def _observed_at(frontmatter: dict[str, object]) -> str | None:
        observed_at = frontmatter.get("observed_at") or frontmatter.get("ingested_at")
        if observed_at is None:
            return None
        return str(observed_at)

    @staticmethod
    def _turn_index(frontmatter: dict[str, object]) -> int | None:
        turn_index_value = frontmatter.get("turn_index")
        if isinstance(turn_index_value, bool):
            return None
        if isinstance(turn_index_value, int):
            return turn_index_value
        return None

    @staticmethod
    def _frontmatter_optional_str(frontmatter: dict[str, object], key: str) -> str | None:
        value = frontmatter.get(key)
        if value is None:
            return None
        return str(value)

    @staticmethod
    def _build_episode_record(
        *,
        frontmatter: dict[str, object],
        content: str,
        raw_file_path: Path,
        observed_at: str,
    ) -> EpisodeRecord:
        return EpisodeRecord(
            episode_id=str(frontmatter["episode_id"]),
            profile_id=str(frontmatter["profile_id"]),
            workspace_id=str(frontmatter["workspace_id"]),
            source_type=str(frontmatter["source_type"]),
            source_ref=EpisodeStore._frontmatter_optional_str(frontmatter, "source_ref"),
            session_id=EpisodeStore._frontmatter_optional_str(frontmatter, "session_id"),
            turn_index=EpisodeStore._turn_index(frontmatter),
            speaker=EpisodeStore._frontmatter_optional_str(frontmatter, "speaker"),
            role=EpisodeStore._frontmatter_optional_str(frontmatter, "role"),
            observed_at=observed_at,
            ingested_at=str(frontmatter["ingested_at"]),
            ttl_expires_at=str(frontmatter["ttl_expires_at"]),
            content_hash=str(frontmatter["content_hash"]),
            raw_file_path=str(raw_file_path),
            content=content,
        )

    @staticmethod
    def _parse_scalar(raw_value: str) -> object:
        if raw_value in {"null", "None"}:
            return None
        if raw_value in {"true", "false"}:
            return raw_value == "true"
        if raw_value.isdigit():
            return int(raw_value)
        if raw_value.startswith('"'):
            return json.loads(raw_value)
        return raw_value

    def _default_lifecycle_state(self) -> dict[str, object]:
        return {
            "preview_tokens": {},
            "episode_states": {},
            "audit_events": [],
        }

    def _read_lifecycle_state(self, *, profile_id: str, workspace_id: str) -> dict[str, object]:
        state_path = self._lifecycle_state_path(profile_id=profile_id, workspace_id=workspace_id)
        if not state_path.exists():
            return self._default_lifecycle_state()
        try:
            raw_payload = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(
                f"Lifecycle state is corrupt at {state_path}."
            ) from exc
        if not isinstance(raw_payload, dict):
            raise ValueError(f"Lifecycle state is corrupt at {state_path}.")
        if "preview_tokens" in raw_payload and not isinstance(raw_payload.get("preview_tokens"), dict):
            raise ValueError(f"Lifecycle state is corrupt at {state_path}.")
        if "episode_states" in raw_payload and not isinstance(raw_payload.get("episode_states"), dict):
            raise ValueError(f"Lifecycle state is corrupt at {state_path}.")
        if "audit_events" in raw_payload and not isinstance(raw_payload.get("audit_events"), list):
            raise ValueError(f"Lifecycle state is corrupt at {state_path}.")

        payload = self._default_lifecycle_state()
        if isinstance(raw_payload.get("preview_tokens"), dict):
            payload["preview_tokens"] = raw_payload["preview_tokens"]
        if isinstance(raw_payload.get("episode_states"), dict):
            payload["episode_states"] = raw_payload["episode_states"]
        if isinstance(raw_payload.get("audit_events"), list):
            payload["audit_events"] = raw_payload["audit_events"]
        return payload

    def _preview_signing_key_path(self) -> Path:
        return (self._data_root / "preview-token-signing-key.json").resolve()

    def _write_lifecycle_state(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        lifecycle_state: dict[str, object],
    ) -> None:
        state_path = self._lifecycle_state_path(profile_id=profile_id, workspace_id=workspace_id)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        self._atomic_write_json(state_path, lifecycle_state)

    def _load_lifecycle_state_cached(
        self,
        *,
        cache: dict[tuple[str, str], dict[str, object]],
        profile_id: str,
        workspace_id: str,
    ) -> dict[str, object]:
        key = (profile_id, workspace_id)
        if key not in cache:
            cache[key] = self._read_lifecycle_state(
                profile_id=profile_id,
                workspace_id=workspace_id,
            )
        return cache[key]

    def _lifecycle_episode_state(
        self,
        *,
        lifecycle_state: dict[str, object],
        episode_id: str,
    ) -> dict[str, object]:
        episode_states = cast(dict[str, object], lifecycle_state["episode_states"])
        episode_state = episode_states.get(episode_id)
        if isinstance(episode_state, dict):
            return episode_state
        return {}

    def _mutable_episode_state(
        self,
        *,
        episode_states: dict[str, object],
        episode_id: str,
    ) -> dict[str, object]:
        episode_state = episode_states.get(episode_id)
        if not isinstance(episode_state, dict):
            episode_state = {}
            episode_states[episode_id] = episode_state
        return episode_state

    def _is_lifecycle_hidden(
        self,
        *,
        episode: EpisodeRecord,
        lifecycle_cache: dict[tuple[str, str], dict[str, object]],
    ) -> bool:
        lifecycle_state = self._load_lifecycle_state_cached(
            cache=lifecycle_cache,
            profile_id=episode.profile_id,
            workspace_id=episode.workspace_id,
        )
        episode_state = self._lifecycle_episode_state(
            lifecycle_state=lifecycle_state,
            episode_id=episode.episode_id,
        )
        return bool(
            episode_state.get("forgotten_at")
            or episode_state.get("superseded_by_episode_id")
        )

    def _state_hash(self, *, episode: EpisodeRecord, episode_state: dict[str, object]) -> str:
        payload = {
            "episode_id": episode.episode_id,
            "workspace_id": episode.workspace_id,
            "content_hash": episode.content_hash,
            "ttl_expires_at": episode.ttl_expires_at,
            "forgotten_at": episode_state.get("forgotten_at"),
            "superseded_by_episode_id": episode_state.get("superseded_by_episode_id"),
            "superseded_at": episode_state.get("superseded_at"),
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return f"sig_{hashlib.sha256(encoded.encode('utf-8')).hexdigest()[:16]}"

    @staticmethod
    def _preview_token_key(*, operation: str, scope_mode: str) -> str:
        return f"{operation}:{scope_mode}"

    @staticmethod
    def _parse_iso_datetime(raw_value: str) -> datetime | None:
        try:
            timestamp = datetime.fromisoformat(raw_value)
        except ValueError:
            return None
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)
        return timestamp

    @staticmethod
    def _validate_preview_operation(operation: str) -> None:
        if operation not in VALID_PREVIEW_OPERATIONS:
            raise ValueError(
                "preview operation must be one of: "
                f"{', '.join(sorted(VALID_PREVIEW_OPERATIONS))}."
            )

    @staticmethod
    def _validated_scope_mode(scope_mode: str) -> str:
        if scope_mode not in VALID_SCOPE_MODES:
            raise ValueError(
                f"scope_mode must be one of: {', '.join(sorted(VALID_SCOPE_MODES))}."
            )
        return scope_mode

    @staticmethod
    def _assert_mutation_scope(
        *,
        integrity: dict[str, dict[str, str]],
        workspace_id: str,
        expected_episode_ids: list[str],
    ) -> None:
        expected = set(expected_episode_ids)
        if expected != set(integrity):
            raise ValueError("selected_episode_ids contain unknown episode IDs.")
        for metadata in integrity.values():
            if metadata.get("workspace_id") != workspace_id:
                raise ValueError("selected_episode_ids scope mismatch.")
