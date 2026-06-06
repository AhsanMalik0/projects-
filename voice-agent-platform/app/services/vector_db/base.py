from abc import ABC, abstractmethod
from typing import Any


class VectorDBProvider(ABC):
    @abstractmethod
    async def upsert(self, namespace: str, records: list[dict[str, Any]]) -> None:
        """Upsert vector records into the given namespace."""

    @abstractmethod
    async def query(
        self,
        namespace: str,
        vector: list[float],
        top_k: int = 5,
        include_metadata: bool = True,
    ) -> dict[str, Any]:
        """Query vectors by similarity."""

    @abstractmethod
    async def delete(self, namespace: str, ids: list[str]) -> None:
        """Delete vectors by ID."""
