from __future__ import annotations

from dataclasses import dataclass

DEFAULT_SCOPE_MODE = "workspace_local"
PROFILE_GLOBAL_SCOPE_MODE = "profile_global"
SCOPE_POLICY = "per_request_non_sticky"
VALID_SCOPE_MODES = {DEFAULT_SCOPE_MODE, PROFILE_GLOBAL_SCOPE_MODE}


@dataclass(frozen=True, slots=True)
class ScopeDecision:
    requested_scope_mode: str
    effective_scope: str
    scope_widened: bool
    scope_policy: str = SCOPE_POLICY

    def to_dict(self) -> dict[str, object]:
        return {
            "requested_scope_mode": self.requested_scope_mode,
            "effective_scope": self.effective_scope,
            "scope_widened": self.scope_widened,
            "scope_policy": self.scope_policy,
        }


def resolve_scope_mode(*, scope_mode: str | None = None) -> ScopeDecision:
    requested_scope_mode = scope_mode or DEFAULT_SCOPE_MODE
    if requested_scope_mode not in VALID_SCOPE_MODES:
        raise ValueError("scope_mode must be one of: workspace_local, profile_global.")
    return ScopeDecision(
        requested_scope_mode=requested_scope_mode,
        effective_scope=requested_scope_mode,
        scope_widened=(requested_scope_mode == PROFILE_GLOBAL_SCOPE_MODE),
    )


def workspace_local_scope() -> ScopeDecision:
    return resolve_scope_mode(scope_mode=DEFAULT_SCOPE_MODE)
