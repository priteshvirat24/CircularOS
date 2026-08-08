"""Deterministic compliance-graph reachability for blast-radius verdicts."""

from __future__ import annotations

import enum
from collections import deque
from dataclasses import dataclass

from packages.policy_engine.changes import MaterialityLevel


class OrgNodeKind(enum.StrEnum):
    CHANGE = "change"
    OBLIGATION = "obligation"
    CONTROL = "control"
    PROCESS = "process"
    EVIDENCE = "evidence"
    CALENDAR = "calendar"


@dataclass(frozen=True)
class OrgNode:
    node_id: str
    kind: OrgNodeKind
    label: str


@dataclass(frozen=True)
class OrgGraph:
    nodes: tuple[OrgNode, ...]
    edges: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class ImpactChange:
    obligation_id: str
    severity: MaterialityLevel
    change_id: str | None = None


@dataclass(frozen=True)
class ImpactSet:
    controls: tuple[str, ...]
    processes: tuple[str, ...]
    evidence_requirements: tuple[str, ...]
    calendar_events: tuple[str, ...]
    severity: MaterialityLevel
    named_paths: tuple[str, ...]
    explanation: str


def resolve_blast_radius(change: ImpactChange, org_graph: OrgGraph) -> ImpactSet:
    """Walk all directed links from the changed obligation using cycle-safe BFS."""
    nodes = {node.node_id: node for node in org_graph.nodes}
    root = nodes.get(change.obligation_id)
    if root is None or root.kind not in {OrgNodeKind.CHANGE, OrgNodeKind.OBLIGATION}:
        return ImpactSet(
            (),
            (),
            (),
            (),
            change.severity,
            (),
            f"impact root {change.obligation_id} has no node of kind change or obligation in the organization graph",
        )

    adjacency: dict[str, list[str]] = {}
    for source, target in org_graph.edges:
        if source in nodes and target in nodes:
            adjacency.setdefault(source, []).append(target)
    for targets in adjacency.values():
        targets.sort()

    queue: deque[tuple[str, tuple[str, ...]]] = deque([(root.node_id, (root.node_id,))])
    visited = {root.node_id}
    paths: dict[str, tuple[str, ...]] = {}
    while queue:
        current, path = queue.popleft()
        for target in adjacency.get(current, []):
            if target in visited:
                continue
            visited.add(target)
            target_path = (*path, target)
            paths[target] = target_path
            queue.append((target, target_path))

    def ids(kind: OrgNodeKind) -> tuple[str, ...]:
        return tuple(sorted(node_id for node_id in paths if nodes[node_id].kind is kind))

    named_paths = tuple(
        " -> ".join(f"{nodes[node_id].kind.value} {nodes[node_id].label}" for node_id in path)
        for _, path in sorted(paths.items())
    )
    longest = max(named_paths, key=lambda value: (value.count(" -> "), value), default="")
    explanation = (
        f"reachable impact inherits {change.severity.value} severity; path: {longest}"
        if longest
        else f"obligation {root.label} has no reachable operational nodes"
    )
    return ImpactSet(
        ids(OrgNodeKind.CONTROL),
        ids(OrgNodeKind.PROCESS),
        ids(OrgNodeKind.EVIDENCE),
        ids(OrgNodeKind.CALENDAR),
        change.severity,
        named_paths,
        explanation,
    )
