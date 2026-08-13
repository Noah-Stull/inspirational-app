"""Database access for the POD graph query.

The UI calls `fetch_graph()` and expects a `Graph` back. Right now it returns
sample data; swap the body for the real query and nothing else has to change.
"""

from __future__ import annotations

from app.core.graph import EdgeNode, Graph, Vertex, sample_graph


def fetch_graph() -> Graph:
    """Return the POD graph.

    TODO: replace with the real query, e.g.

        with get_connection() as conn:
            v_rows = conn.execute(VERTEX_SQL).fetchall()
            e_rows = conn.execute(EDGE_SQL).fetchall()
            i_rows = conn.execute(INCIDENCE_SQL).fetchall()
        return rows_to_graph(v_rows, i_rows, e_rows)
    """
    return sample_graph()


def rows_to_graph(
    vertex_rows: list[tuple],
    incidence_rows: list[tuple],
    edge_rows: list[tuple] | None = None,
) -> Graph:
    """Map query results onto the bipartite model.

    Expected shapes:
        vertex_rows:    (id, label) or (id, label, group)
        incidence_rows: (edge_id, vertex_id) — the junction table
        edge_rows:      (id, label) or (id, label, weight) — optional metadata

    Edge-nodes are built from `incidence_rows`, so an edge with three members
    is simply an edge_id appearing on three rows. `edge_rows` only decorates
    them; an edge listed there with no incidences is skipped.
    """
    vertices = [
        Vertex(
            id=str(row[0]),
            label=str(row[1]) if len(row) > 1 and row[1] is not None else None,
            group=str(row[2]) if len(row) > 2 and row[2] is not None else None,
        )
        for row in vertex_rows
    ]

    members: dict[str, set[str]] = {}
    for row in incidence_rows:
        members.setdefault(str(row[0]), set()).add(str(row[1]))

    meta: dict[str, tuple[str | None, float]] = {}
    for row in edge_rows or []:
        label = str(row[1]) if len(row) > 1 and row[1] is not None else None
        weight = float(row[2]) if len(row) > 2 and row[2] is not None else 1.0
        meta[str(row[0])] = (label, weight)

    edges = []
    for edge_id, member_ids in members.items():
        label, weight = meta.get(edge_id, (None, 1.0))
        edges.append(
            EdgeNode(
                id=edge_id,
                members=frozenset(member_ids),
                label=label,
                weight=weight,
            )
        )

    return Graph(vertices=vertices, edges=edges)
