"""Graph model: vertices, edges, and a layout algorithm.

This module is UI-agnostic on purpose — it knows nothing about Qt, and the
data layer knows nothing about how the graph is drawn.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Vertex:
    id: str
    label: str | None = None
    group: str | None = None

    @property
    def display(self) -> str:
        return self.label if self.label is not None else self.id


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    weight: float = 1.0
    label: str | None = None


@dataclass
class Graph:
    vertices: list[Vertex] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    directed: bool = False

    def __len__(self) -> int:
        return len(self.vertices)

    def vertex_ids(self) -> set[str]:
        return {v.id for v in self.vertices}

    def valid_edges(self) -> list[Edge]:
        """Edges whose endpoints both exist (guards against partial queries)"""
        ids = self.vertex_ids()
        return [e for e in self.edges if e.source in ids and e.target in ids]

    def degree(self, vertex_id: str) -> int:
        return sum(
            1
            for e in self.valid_edges()
            if vertex_id in (e.source, e.target)
        )

    @classmethod
    def from_pairs(
        cls,
        vertices: list[str | tuple[str, str]],
        edges: list[tuple[str, str]],
        directed: bool = False,
    ) -> "Graph":
        """Build a Graph from plain tuples, e.g. rows returned by a query."""
        vs: list[Vertex] = []
        for v in vertices:
            if isinstance(v, str):
                vs.append(Vertex(id=v))
            else:
                vs.append(Vertex(id=v[0], label=v[1]))
        return cls(
            vertices=vs,
            edges=[Edge(source=s, target=t) for s, t in edges],
            directed=directed,
        )


def spring_layout(
    graph: Graph,
    iterations: int = 300,
    seed: int | None = 7,
) -> dict[str, tuple[float, float]]:
    """Force-directed (Fruchterman-Reingold) layout.

    Returns {vertex_id: (x, y)} with coordinates normalized to [0, 1].
    Pass seed=None for a different arrangement on every call.
    """
    rnd = random.Random(seed)
    n = len(graph.vertices)
    if n == 0:
        return {}
    if n == 1:
        return {graph.vertices[0].id: (0.5, 0.5)}

    ids = [v.id for v in graph.vertices]
    pos = {vid: [rnd.uniform(0.0, 1.0), rnd.uniform(0.0, 1.0)] for vid in ids}
    edges = [(e.source, e.target, e.weight) for e in graph.valid_edges()]

    k = math.sqrt(1.0 / n)          # ideal edge length
    temp = 0.1                       # max displacement per step

    for _ in range(iterations):
        disp = {vid: [0.0, 0.0] for vid in ids}

        # Repulsion between every pair of vertices.
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

        # Attraction along edges.
        for src, tgt, weight in edges:
            if src == tgt:
                continue
            dx = pos[src][0] - pos[tgt][0]
            dy = pos[src][1] - pos[tgt][1]
            dist = math.hypot(dx, dy) or 1e-6
            force = (dist * dist) / k * max(weight, 0.1)
            ux, uy = dx / dist, dy / dist
            disp[src][0] -= ux * force
            disp[src][1] -= uy * force
            disp[tgt][0] += ux * force
            disp[tgt][1] += uy * force

        # Apply displacement, capped by the cooling temperature.
        for vid in ids:
            dx, dy = disp[vid]
            dist = math.hypot(dx, dy) or 1e-6
            step = min(dist, temp)
            pos[vid][0] += (dx / dist) * step
            pos[vid][1] += (dy / dist) * step

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


def sample_graph() -> Graph:
    """Placeholder graph used until queryPOD returns real rows."""
    vertices = [
        Vertex("pod-core", "POD Core", group="core"),
        Vertex("ingest", "Ingest", group="service"),
        Vertex("transform", "Transform", group="service"),
        Vertex("warehouse", "Warehouse", group="store"),
        Vertex("api", "API", group="service"),
        Vertex("dashboard", "Dashboard", group="client"),
        Vertex("alerts", "Alerts", group="client"),
        Vertex("archive", "Archive", group="store"),
        Vertex("scheduler", "Scheduler", group="service"),
    ]
    edges = [
        Edge("pod-core", "ingest"),
        Edge("pod-core", "scheduler"),
        Edge("ingest", "transform"),
        Edge("transform", "warehouse"),
        Edge("warehouse", "api"),
        Edge("warehouse", "archive"),
        Edge("api", "dashboard"),
        Edge("api", "alerts"),
        Edge("scheduler", "transform"),
        Edge("scheduler", "alerts"),
        Edge("pod-core", "warehouse", weight=0.5),
    ]
    return Graph(vertices=vertices, edges=edges, directed=True)
