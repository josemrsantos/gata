from abc import ABC, abstractmethod

from agents.types import Community, Headline


class SourceAdapter(ABC):
    @abstractmethod
    def fetch(self, community: Community) -> list[Headline]:
        """Return headlines for the community. Return [] on any failure."""
