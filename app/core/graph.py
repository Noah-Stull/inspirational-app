"""Bipartite graph model: vertices, edge-nodes, and a layout algorithm.


"""

from __future__ import annotations

import math
import random
from collections.abc import Iterable
from dataclasses import dataclass, field, replace

SIDE_VERTEX = "vertex"
SIDE_EDGE = "edge"


@dataclass(frozen=True)
class Vertex:
    id: str
    label: str | None = None
    group: str | None = None

    @property
    def display(self) -> str:
        return self.label if self.label is not None else self.id


@dataclass(frozen=True)
class EdgeNode:
    """An edge promoted to a node.

    `members` holds the vertex ids this edge connects. Two members is an
    ordinary edge; three or more is a hyperedge. Both are drawn identically —
    as an edge-node with one incidence line per member.
    """

    id: str
    members: frozenset[str] = frozenset()
    label: str | None = None
    weight: float = 1.0

    @property
    def display(self) -> str:
        return self.label if self.label is not None else self.id

    @property
    def arity(self) -> int:
        return len(self.members)


@dataclass
class Graph:
    """Membership runs both ways, so incidences are always undirected."""

    vertices: list[Vertex] = field(default_factory=list)
    edges: list[EdgeNode] = field(default_factory=list)

    def __len__(self) -> int:
        """Total layout participants: both sides of the bipartition."""
        return len(self.vertices) + len(self.edges)

    # --- identity ----------------------------------------------------------

    def vertex_ids(self) -> set[str]:
        return {v.id for v in self.vertices}

    def edge_ids(self) -> set[str]:
        return {e.id for e in self.edges}

    def id_conflicts(self) -> set[str]:
        """Ids claimed by a vertex and an edge-node at once — always a bug.

        Both sides share one coordinate space, so a collision would silently
        merge two nodes into one.
        """
        return self.vertex_ids() & self.edge_ids()

    def side(self, node_id: str) -> str | None:
        if node_id in self.vertex_ids():
            return SIDE_VERTEX
        if node_id in self.edge_ids():
            return SIDE_EDGE
        return None

    # --- structure ---------------------------------------------------------

    def valid_edges(self) -> list[EdgeNode]:
        """Edge-nodes trimmed to members that actually exist.

        Guards against partial queries: an edge referencing a vertex the
        query didn't return keeps its remaining members; one left with no
        members at all is dropped.
        """
        ids = self.vertex_ids()
        kept: list[EdgeNode] = []
        for e in self.edges:
            members = e.members & ids
            if not members:
                continue
            kept.append(e if members == e.members else replace(e, members=members))
        return kept

    def incidences(self) -> list[tuple[str, str, float]]:
        """(edge_id, vertex_id, weight) — one entry per drawn connection."""
        return [
            (e.id, vid, e.weight)
            for e in self.valid_edges()
            for vid in sorted(e.members)
        ]

    def degree(self, vertex_id: str) -> int:
        """How many edge-nodes this vertex participates in."""
        return sum(1 for e in self.valid_edges() if vertex_id in e.members)

    def neighbors(self, vertex_id: str) -> set[str]:
        """Vertices sharing at least one edge-node with this one."""
        out: set[str] = set()
        for e in self.valid_edges():
            if vertex_id in e.members:
                out |= e.members
        return out - {vertex_id}

    @classmethod
    def from_incidence(
        cls,
        vertices: Iterable[str | tuple[str, str]],
        incidences: Iterable[tuple[str, str]],
    ) -> "Graph":
        """Build from plain tuples: vertex ids plus (edge_id, vertex_id) pairs.

        This mirrors a relational junction table, which is the shape a real
        query usually returns.
        """
        vs: list[Vertex] = []
        for v in vertices:
            if isinstance(v, str):
                vs.append(Vertex(id=v))
            else:
                vs.append(Vertex(id=v[0], label=v[1]))

        members: dict[str, set[str]] = {}
        for edge_id, vertex_id in incidences:
            members.setdefault(edge_id, set()).add(vertex_id)

        return cls(
            vertices=vs,
            edges=[
                EdgeNode(id=eid, members=frozenset(m)) for eid, m in members.items()
            ],
        )


def spring_layout(
    graph: Graph,
    iterations: int = 300,
    seed: int | None = 7,
) -> dict[str, tuple[float, float]]:
    """Force-directed (Fruchterman-Reingold) layout over both sides.

    Vertices and edge-nodes share one coordinate space and one repulsion
    field; attraction runs along incidences only. An edge-node with several
    members is pulled by each of them, so it settles near their centroid —
    which is exactly where you want to draw it.

    Returns {node_id: (x, y)} for every vertex *and* edge-node, normalized to
    [0, 1]. Pass seed=None for a different arrangement on every call.
    """
    rnd = random.Random(seed)
    ids = [v.id for v in graph.vertices] + [e.id for e in graph.edges]
    n = len(ids)
    if n == 0:
        return {}
    if n == 1:
        return {ids[0]: (0.5, 0.5)}

    pos = {nid: [rnd.uniform(0.0, 1.0), rnd.uniform(0.0, 1.0)] for nid in ids}
    arity = {e.id: max(e.arity, 1) for e in graph.valid_edges()}
    incidences = graph.incidences()

    k = math.sqrt(1.0 / n)          # ideal edge length
    temp = 0.1                       # max displacement per step

    for _ in range(iterations):
        disp = {nid: [0.0, 0.0] for nid in ids}

        # Repulsion between every pair of nodes, both sides alike.
        for a in range(n):
            for b in range(a + 1, n):
                ia, ib = ids[a], ids[b]
                dx = pos[ia][0] - pos[ib][0]
                dy = pos[ia][1] - pos[ib][1]
                dist = math.hypot(dx, dy)
                if dist < 1e-6:
                    dx, dy = rnd.uniform(-1e-3, 1e-3), rnd.uniform(-1e-3, 1e-3)
                    dist = math.hypot(dx, dy) or 1e-6
                force = (k * k) / dist
                ux, uy = dx / dist, dy / dist
                disp[ia][0] += ux * force
                disp[ia][1] += uy * force
                disp[ib][0] -= ux * force
                disp[ib][1] -= uy * force

        # Attraction along incidences (edge-node <-> member vertex).
        for edge_id, vertex_id, weight in incidences:
            dx = pos[edge_id][0] - pos[vertex_id][0]
            dy = pos[edge_id][1] - pos[vertex_id][1]
            dist = math.hypot(dx, dy) or 1e-6
            # Damp by arity so a wide edge doesn't out-pull a narrow one;
            # sqrt(2/arity) leaves ordinary 2-member edges at full strength.
            damping = math.sqrt(2.0 / arity.get(edge_id, 2))
            force = (dist * dist) / k * max(weight, 0.1) * damping
            ux, uy = dx / dist, dy / dist
            disp[edge_id][0] -= ux * force
            disp[edge_id][1] -= uy * force
            disp[vertex_id][0] += ux * force
            disp[vertex_id][1] += uy * force

        # Apply displacement, capped by the cooling temperature.
        for nid in ids:
            dx, dy = disp[nid]
            dist = math.hypot(dx, dy) or 1e-6
            step = min(dist, temp)
            pos[nid][0] += (dx / dist) * step
            pos[nid][1] += (dy / dist) * step

        temp *= 0.97

    return _normalize(pos)


def _normalize(pos: dict[str, list[float]]) -> dict[str, tuple[float, float]]:
    """Scale coordinates into the unit square, preserving aspect ratio."""
    xs = [p[0] for p in pos.values()]
    ys = [p[1] for p in pos.values()]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span = max(max_x - min_x, max_y - min_y, 1e-6)

    # Center the smaller axis inside the unit square.
    off_x = (span - (max_x - min_x)) / 2.0
    off_y = (span - (max_y - min_y)) / 2.0

    return {
        vid: ((p[0] - min_x + off_x) / span, (p[1] - min_y + off_y) / span)
        for vid, p in pos.items()
    }

# There is deliberately no sample graph here. The dataset lives in
# data/pod_graph.json and is loaded via app.data.pod_schema.graph_from_file.
# A second hardcoded copy would drift and quietly mislead about which data
# is actually on screen.
