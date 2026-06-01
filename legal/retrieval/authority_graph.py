from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AuthorityEdge:
    source_id: str
    target_source_id: str
    relation: str = "cites"
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "target_source_id": self.target_source_id,
            "relation": self.relation,
            "metadata": self.metadata or {},
        }


class AuthorityGraph:
    def __init__(self) -> None:
        self.edges: dict[str, list[AuthorityEdge]] = {}
        self.reverse_edges: dict[str, list[AuthorityEdge]] = {}

    def add_authority_relation(
        self,
        source_id: str,
        cited_source: str,
        *,
        relation: str = "cites",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        edge = AuthorityEdge(
            source_id=source_id,
            target_source_id=cited_source,
            relation=relation,
            metadata=metadata,
        )
        self.edges.setdefault(source_id, []).append(edge)
        self.reverse_edges.setdefault(cited_source, []).append(edge)

    def add_case_interprets_statute(self, case_source_id: str, statute_source_id: str) -> None:
        self.add_authority_relation(case_source_id, statute_source_id, relation="interprets")

    def add_case_applies_rule(self, case_source_id: str, rule_source_id: str) -> None:
        self.add_authority_relation(case_source_id, rule_source_id, relation="applies_rule")

    def add_form_depends_on_authority(self, form_source_id: str, authority_source_id: str) -> None:
        self.add_authority_relation(form_source_id, authority_source_id, relation="depends_on")

    def related_authorities(self, source_id: str) -> list[str]:
        return [edge.target_source_id for edge in self.edges.get(source_id, [])]

    def outgoing(self, source_id: str, *, relation: str | None = None) -> list[AuthorityEdge]:
        edges = self.edges.get(source_id, [])
        if relation is None:
            return list(edges)
        return [edge for edge in edges if edge.relation == relation]

    def incoming(self, source_id: str, *, relation: str | None = None) -> list[AuthorityEdge]:
        edges = self.reverse_edges.get(source_id, [])
        if relation is None:
            return list(edges)
        return [edge for edge in edges if edge.relation == relation]

    def to_adjacency(self) -> dict[str, list[dict[str, Any]]]:
        return {source_id: [edge.to_dict() for edge in edges] for source_id, edges in self.edges.items()}
