"""Database access for the POD graph query.

The UI calls `fetch_graph()` and expects a `Graph` back. Right now it returns
sample data; swap the body for the real query and nothing else has to change.
"""

from __future__ import annotations

from app.core.graph import Edge, Graph, Vertex, sample_graph


def fetch_graph() -> Graph:
    """Return the POD graph.

    TODO: replace with the real query, e.g.

        with get_connection() as conn:
            v_rows = conn.execute(VERTEX_SQL).fetchall()
            e_rows = conn.execute(EDGE_SQL).fetchall()
        return rows_to_graph(v_rows, e_rows)
    """
    return sample_graph()


def rows_to_graph(
    vertex_rows: list[tuple],
    edge_rows: list[tuple],
    directed: bool = True,
) -> Graph:
    """Map query results onto the Graph model.

    Expected shapes:
        vertex_rows: (id, label) or (id, label, group)
        edge_rows:   (source, target) or (source, target, weight)
    """
    vertices = [
        Vertex(
            id=str(row[0]),
            label=str(row[1]) if len(row) > 1 and row[1] is not None else None,
            group=str(row[2]) if len(row) > 2 and row[2] is not None else None,
        )
        for row in vertex_rows
    ]
    edges = [
        Edge(
            source=str(row[0]),
            target=str(row[1]),
            weight=float(row[2]) if len(row) > 2 and row[2] is not None else 1.0,
        )
        for row in edge_rows
    ]
    return Graph(vertices=vertices, edges=edges, directed=directed)
