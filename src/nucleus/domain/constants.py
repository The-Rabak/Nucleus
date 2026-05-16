from __future__ import annotations

from enum import StrEnum


class ScopeMode(StrEnum):
    WORKSPACE_LOCAL = "workspace_local"
    PROFILE_GLOBAL = "profile_global"


class ScopePolicy(StrEnum):
    PER_REQUEST_NON_STICKY = "per_request_non_sticky"


class PreviewOperation(StrEnum):
    UPDATE = "update"
    FORGET = "forget"


class MutationOperation(StrEnum):
    UPDATE_PREVIEW = "update_preview"
    UPDATE_CONFIRM = "update_confirm"
    FORGET_PREVIEW = "forget_preview"
    FORGET_CONFIRM = "forget_confirm"


class Stage1Operation(StrEnum):
    REMEMBER = "remember"
    RETRIEVE = "retrieve"
    UPDATE_PREVIEW = "update_preview"
    UPDATE_CONFIRM = "update_confirm"
    FORGET_PREVIEW = "forget_preview"
    FORGET_CONFIRM = "forget_confirm"
    CHECKPOINT_SESSION = "checkpoint_session"
    INSPECT_STATUS = "inspect_status"
    BOOTCARD = "bootcard"


class CheckpointTrigger(StrEnum):
    PRE_COMPACT = "pre_compact"
    STOP = "stop"
    MANUAL = "manual"


DEFAULT_SCOPE_MODE = ScopeMode.WORKSPACE_LOCAL.value
SCOPE_POLICY = ScopePolicy.PER_REQUEST_NON_STICKY.value
VALID_SCOPE_MODES = frozenset(mode.value for mode in ScopeMode)
VALID_PREVIEW_OPERATIONS = frozenset(operation.value for operation in PreviewOperation)
VALID_CHECKPOINT_TRIGGERS = frozenset(trigger.value for trigger in CheckpointTrigger)
STAGE1_OPERATION_NAMES = tuple(operation.value for operation in Stage1Operation)
