from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types import LoopOutput, TokenUsage


class LLMProvider(ABC):
    @property
    @abstractmethod
    def model_id(self) -> str: ...

    @property
    @abstractmethod
    def timeout(self) -> float | None: ...

    @abstractmethod
    def generate(
        self,
        system_prompt: str,
        messages: list[dict],
        max_tokens: int = 2048,
    ) -> tuple[str, TokenUsage]: ...


class ConversationProtocol(ABC):
    @abstractmethod
    def run(self, initial_input: str) -> LoopOutput: ...
