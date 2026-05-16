from __future__ import annotations

from nucleus.domain.envelopes import MCPToolEnvelope


def assert_mcp_tool_envelope(payload: MCPToolEnvelope) -> None:
    assert "structuredContent" in payload
    assert "content" in payload
    assert payload["content"]
    assert payload["content"][0]["type"] == "text"
    assert isinstance(payload["content"][0]["text"], str)
