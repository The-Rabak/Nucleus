from __future__ import annotations

from typing import Literal, TypeAlias, TypedDict

JsonPrimitive: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonPrimitive | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]


class MCPTextContent(TypedDict):
    type: Literal["text"]
    text: str


class MCPToolEnvelope(TypedDict):
    structuredContent: JsonObject
    content: list[MCPTextContent]


class HTTPOperationEnvelope(TypedDict):
    operation: str
    result: JsonObject
    summary: str
