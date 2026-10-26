import networkx as nx
from datetime import date
from typing import List
from src.domain.models import TemporalEdge
from src.domain.interfaces import BaseTemporalKnowledgeGraph


class TemporalKnowledgeGraph(BaseTemporalKnowledgeGraph):
    """
    Темпоральная память агента.
    Позволяет делать time-travel запросы по версиям внутренней документации.
    """

    def __init__(self):
        # MultiDiGraph позволяет хранить несколько версий одного правила между двумя узлами
        self.graph = nx.MultiDiGraph()

    def add_rule(self, edge: TemporalEdge) -> None:
        self.graph.add_edge(
            edge.source,
            edge.target,
            relation=edge.relation,
            doc_id=edge.doc_id,
            valid_from=edge.valid_from,
            valid_to=edge.valid_to,
        )

    def retrieve_subgraph(self, entities: List[str], as_of_date: date) -> List[str]:
        """
        Извлекает только те триплеты вокруг ключевых сущностей,
        которые были действительны на дату `as_of_date`.
        """
        active_facts = []
        for entity in entities:
            if entity not in self.graph:
                continue

            # Обходим исходящие и входящие ребра (1-hop neighborhood)
            for u, v, data in self.graph.edges(entity, data=True):
                edge = TemporalEdge(
                    source=u,
                    target=v,
                    relation=data["relation"],
                    doc_id=data["doc_id"],
                    valid_from=data["valid_from"],
                    valid_to=data["valid_to"],
                )
                if edge.is_active_at(as_of_date):
                    valid_str = f"с {edge.valid_from} по {edge.valid_to or 'н.в.'}"
                    fact = (
                        f"[{edge.doc_id} ({valid_str})]: {u} -> {edge.relation} -> {v}"
                    )
                    active_facts.append(fact)

        return active_facts
