from abc import ABC, abstractmethod
from datetime import date
from typing import List
from src.domain.models import TemporalEdge


class BaseTemporalKnowledgeGraph(ABC):
    """Абстрактный интерфейс темпорального хранилища правил (Dependency Inversion)."""

    @abstractmethod
    def add_rule(self, edge: TemporalEdge) -> None:
        pass

    @abstractmethod
    def retrieve_subgraph(self, entities: List[str], as_of_date: date) -> List[str]:
        pass
