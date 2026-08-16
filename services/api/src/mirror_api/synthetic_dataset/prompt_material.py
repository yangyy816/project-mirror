from __future__ import annotations

from collections.abc import Mapping
from typing import Never, SupportsIndex

MAX_EPHEMERAL_PROMPT_BYTES = 16 * 1024


class EphemeralPrompt:
    """Bounded Prompt material that redacts representation and forbids serialization."""

    __slots__ = ("__value",)

    def __init__(self, value: str) -> None:
        if not isinstance(value, str):
            raise TypeError("prompt material must be text")
        encoded = value.encode("utf-8")
        if not encoded or len(encoded) > MAX_EPHEMERAL_PROMPT_BYTES or "\x00" in value:
            raise ValueError("prompt material is outside the bounded safe shape")
        self.__value = value

    @classmethod
    def from_template_content(cls, content: Mapping[str, object]) -> EphemeralPrompt:
        value = content.get("template")
        if not isinstance(value, str):
            raise ValueError("prompt template content is not materializable")
        return cls(value)

    def reveal_for_provider_adapter(self) -> str:
        """Reveal only at the immediate Provider Adapter call boundary."""
        return self.__value

    def __repr__(self) -> str:
        return "EphemeralPrompt(<redacted>)"

    def __str__(self) -> str:
        return "<redacted>"

    def __reduce_ex__(self, protocol: SupportsIndex) -> Never:
        del protocol
        raise TypeError("ephemeral prompt material cannot be serialized")

    def __getstate__(self) -> Never:
        raise TypeError("ephemeral prompt material cannot be serialized")
