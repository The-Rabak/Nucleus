from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import json
from pathlib import Path
import re
import uuid

from nucleus.application.scope_validation import validate_scope_identifier
from nucleus.domain.models import EpisodeRecord

_MIN_BOOTCARD_SCAN = 96
_MAX_SEARCH_SCAN = 512
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
    def __init__(self, *, data_root: Path) -> None:
        self._data_root = data_root
        self._profiles_root = (self._data_root / "profiles").resolve()

    def persist_episode(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        source_type: str,
        content: str,
        source_ref: str | None,
        session_id: str | None,
        turn_index: int | None,
        speaker: str | None,
        role: str | None,
        observed_at: str | None,
    ) -> EpisodeRecord:
        safe_profile_id = validate_scope_identifier(name="profile_id", value=profile_id)
        safe_workspace_id = validate_scope_identifier(name="workspace_id", value=workspace_id)
        ingested_at = datetime.now(UTC)
        observed_timestamp = observed_at or ingested_at.isoformat()
        ttl_expires_at = ingested_at + timedelta(days=90)
        episode_id = f"ep_{uuid.uuid4().hex[:12]}"
        content_hash = f"sha256:{hashlib.sha256(content.encode('utf-8')).hexdigest()}"

        episode_dir = self._workspace_episodes_root(
            profile_id=safe_profile_id,
            workspace_id=safe_workspace_id,
        ) / ingested_at.strftime("%Y/%m/%d")
        episode_dir.mkdir(parents=True, exist_ok=True)
        episode_path = episode_dir / f"{episode_id}.md"
        self._ensure_within_profiles_root(episode_path)

        frontmatter = {
            "episode_id": episode_id,
            "profile_id": safe_profile_id,
            "workspace_id": safe_workspace_id,
            "source_type": source_type,
            "source_ref": source_ref,
            "session_id": session_id,
            "turn_index": turn_index,
            "speaker": speaker,
            "role": role,
            "observed_at": observed_timestamp,
            "ingested_at": ingested_at.isoformat(),
            "ttl_expires_at": ttl_expires_at.isoformat(),
            "content_hash": content_hash,
            "sensitivity": "internal",
            "extraction_status": "episode_persisted",
            "schema_version": "nucleus.episode.v1",
        }
        self._atomic_write_markdown(
            episode_path,
            self._render_markdown(frontmatter, content),
        )

        return EpisodeRecord(
            episode_id=episode_id,
            profile_id=safe_profile_id,
            workspace_id=safe_workspace_id,
            source_type=source_type,
            source_ref=source_ref,
            session_id=session_id,
            turn_index=turn_index,
            speaker=speaker,
            role=role,
            observed_at=observed_timestamp,
            ingested_at=ingested_at.isoformat(),
            ttl_expires_at=ttl_expires_at.isoformat(),
            content_hash=content_hash,
            raw_file_path=str(episode_path),
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
        )
        episodes.sort(key=lambda item: item.observed_at, reverse=True)
        return episodes[:limit], scan_counters

    def search(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        query: str,
        top_k: int = 5,
        scope_mode: str = "workspace_local",
    ) -> tuple[list[EpisodeRecord], dict[str, int]]:
        tokens = [token.lower() for token in re.findall(r"\w+", query)]
        if scope_mode == "workspace_local":
            episodes, scan_counters = self._load_workspace_episodes(
                profile_id=profile_id,
                workspace_id=workspace_id,
                max_files=max(top_k * 64, _MAX_SEARCH_SCAN),
            )
        else:
            episodes, scan_counters = self._load_profile_episodes(
                profile_id=profile_id,
                max_files=max(top_k * 64, _MAX_SEARCH_SCAN),
            )
        scan_counters["query_token_count"] = len(tokens)
        if not tokens:
            return episodes[:top_k], scan_counters

        scored: list[tuple[int, EpisodeRecord]] = []
        for episode in episodes:
            content_lower = episode.content.lower()
            score = sum(1 for token in tokens if token in content_lower)
            if score:
                scored.append((score, episode))

        scored.sort(key=lambda item: (item[0], item[1].observed_at), reverse=True)
        scan_counters["match_count"] = len(scored)
        return [episode for _, episode in scored[:top_k]], scan_counters

    def _load_profile_episodes(
        self,
        *,
        profile_id: str,
        max_files: int | None = None,
    ) -> tuple[list[EpisodeRecord], dict[str, int]]:
        safe_profile_id = validate_scope_identifier(name="profile_id", value=profile_id)
        profile_workspaces_root = self._profiles_root / safe_profile_id / "workspaces"
        self._ensure_within_profiles_root(profile_workspaces_root)
        if not profile_workspaces_root.exists():
            return [], self._default_scan_counters(max_files=max_files)

        episodes: list[EpisodeRecord] = []
        scan_counters = self._default_scan_counters(max_files=max_files)
        markdown_files = sorted(profile_workspaces_root.rglob("*.md"), reverse=True)
        if max_files is not None:
            markdown_files = markdown_files[:max_files]

        for markdown_file in markdown_files:
            scan_counters["scanned_files"] += 1
            try:
                parsed = self._parse_markdown(markdown_file)
            except (OSError, ValueError, json.JSONDecodeError):
                scan_counters["parse_failures"] += 1
                continue
            if parsed is None:
                scan_counters["parse_failures"] += 1
                continue
            frontmatter, content = parsed
            episode = self._episode_from_frontmatter(
                frontmatter=frontmatter,
                content=content,
                raw_file_path=markdown_file,
            )
            if episode is None:
                scan_counters["invalid_records"] += 1
                continue
            if self._is_expired(episode.ttl_expires_at):
                scan_counters["expired_filtered"] += 1
                continue
            if episode.profile_id != safe_profile_id:
                scan_counters["scope_filtered"] += 1
                continue
            episodes.append(episode)
        scan_counters["loaded_records"] = len(episodes)
        return episodes, scan_counters

    def _load_workspace_episodes(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        max_files: int | None = None,
    ) -> tuple[list[EpisodeRecord], dict[str, int]]:
        workspace_dir = self._workspace_episodes_root(
            profile_id=profile_id,
            workspace_id=workspace_id,
        )
        if not workspace_dir.exists():
            return [], self._default_scan_counters(max_files=max_files)

        episodes: list[EpisodeRecord] = []
        scan_counters = self._default_scan_counters(max_files=max_files)
        markdown_files = sorted(workspace_dir.rglob("*.md"), reverse=True)
        if max_files is not None:
            markdown_files = markdown_files[:max_files]

        for markdown_file in markdown_files:
            scan_counters["scanned_files"] += 1
            try:
                parsed = self._parse_markdown(markdown_file)
            except (OSError, ValueError, json.JSONDecodeError):
                scan_counters["parse_failures"] += 1
                continue
            if parsed is None:
                scan_counters["parse_failures"] += 1
                continue
            frontmatter, content = parsed
            episode = self._episode_from_frontmatter(
                frontmatter=frontmatter,
                content=content,
                raw_file_path=markdown_file,
            )
            if episode is None:
                scan_counters["invalid_records"] += 1
                continue
            if self._is_expired(episode.ttl_expires_at):
                scan_counters["expired_filtered"] += 1
                continue
            episodes.append(episode)
        scan_counters["loaded_records"] = len(episodes)
        return episodes, scan_counters

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

    def _workspace_episodes_root(self, *, profile_id: str, workspace_id: str) -> Path:
        safe_profile_id = validate_scope_identifier(name="profile_id", value=profile_id)
        safe_workspace_id = validate_scope_identifier(name="workspace_id", value=workspace_id)
        path = (
            self._profiles_root
            / safe_profile_id
            / "workspaces"
            / safe_workspace_id
            / "episodes"
        )
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
    def _default_scan_counters(*, max_files: int | None) -> dict[str, int]:
        return {
            "scanned_files": 0,
            "loaded_records": 0,
            "expired_filtered": 0,
            "parse_failures": 0,
            "invalid_records": 0,
            "scope_filtered": 0,
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

        turn_index_value = frontmatter.get("turn_index")
        if isinstance(turn_index_value, bool):
            turn_index: int | None = None
        elif isinstance(turn_index_value, int):
            turn_index = turn_index_value
        else:
            turn_index = None

        observed_at = frontmatter.get("observed_at") or frontmatter.get("ingested_at")
        if observed_at is None:
            return None

        return EpisodeRecord(
            episode_id=str(frontmatter["episode_id"]),
            profile_id=str(frontmatter["profile_id"]),
            workspace_id=str(frontmatter["workspace_id"]),
            source_type=str(frontmatter["source_type"]),
            source_ref=(
                str(frontmatter["source_ref"]) if frontmatter.get("source_ref") is not None else None
            ),
            session_id=(
                str(frontmatter["session_id"]) if frontmatter.get("session_id") is not None else None
            ),
            turn_index=turn_index,
            speaker=str(frontmatter["speaker"]) if frontmatter.get("speaker") is not None else None,
            role=str(frontmatter["role"]) if frontmatter.get("role") is not None else None,
            observed_at=str(observed_at),
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
