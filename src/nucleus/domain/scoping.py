from __future__ import annotations

from dataclasses import dataclass

from nucleus.domain.constants import (
    DEFAULT_SCOPE_MODE,
    SCOPE_POLICY,
    ScopeMode,
    VALID_SCOPE_MODES,
)


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
        raise ValueError(
            f"scope_mode must be one of: {', '.join(sorted(VALID_SCOPE_MODES))}."
        )
    return ScopeDecision(
        requested_scope_mode=requested_scope_mode,
        effective_scope=requested_scope_mode,
        scope_widened=(requested_scope_mode == ScopeMode.PROFILE_GLOBAL.value),
    )


def workspace_local_scope() -> ScopeDecision:
    return resolve_scope_mode(scope_mode=DEFAULT_SCOPE_MODE)
