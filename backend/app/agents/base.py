from abc import ABC, abstractmethod
from typing import Any
from app.utils.logging import get_logger


class BaseAgent(ABC):
    """Base class for all LangGraph agents in the pipeline."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.logger = get_logger(f"agents.{name}")

    @abstractmethod
    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """Execute the agent's logic and return state updates."""
        ...

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}({self.name})>"
