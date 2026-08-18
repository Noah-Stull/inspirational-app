"""event schema for the graph.

One event per entity, plus one index event:

    <graph_id>/index          type pod_graph_index   lists member ids
    <graph_id>/vertex/<id>    type pod_graph_vertex  one vertex
    <graph_id>/edge/<id>      type pod_graph_edge    one edge-node
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import quote

from app.core.graph import EdgeNode, Graph, Vertex

SCHEMA_VERSION = "pod-graph/1"

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_FILE = Path(
    os.environ.get("POD_GRAPH_FILE", REPO_ROOT / "data" / "pod_graph.json")
)

TYPE_INDEX = "pod_graph_index"
TYPE_VERTEX = "pod_graph_vertex"
TYPE_EDGE = "pod_graph_edge"

MIME_JSON = "application/json"

DEFAULT_GRAPH_ID = "world-cities"  # must match graph_id in data/pod_graph.json
DEFAULT_OWNER = "$sys"


class SchemaError(ValueError):
    """Raised when stored or file data doesn't match the expected shape."""


# --- unique_id conventions -------------------------------------------------
# Ids are percent-encoded so a vertex id containing "/" can't forge the path
# of another event - Replacable with another convention if needed


def index_uid(graph_id: str) -> str:
    return f"{graph_id}/index"


def vertex_uid(graph_id: str, vertex_id: str) -> str:
    return f"{graph_id}/vertex/{quote(vertex_id, safe='')}"


def edge_uid(graph_id: str, edge_id: str) -> str:
    return f"{graph_id}/edge/{quote(edge_id, safe='')}"


# --- serialization ---------------------------------------------------------


def vertex_payload(vertex: Vertex) -> str:
    return json.dumps(
        {
            "schema": SCHEMA_VERSION,
            "id": vertex.id,
            "label": vertex.label,
            "group": vertex.group,
        }
    )


def edge_payload(edge: EdgeNode) -> str:
    return json.dumps(
        {
            "schema": SCHEMA_VERSION,
            "id": edge.id,
            "label": edge.label,
            "weight": edge.weight,
            "members": sorted(edge.members),
        }
    )


def index_payload(graph: Graph, graph_id: str, revision: str) -> str:
    return json.dumps(
        {
            "schema": SCHEMA_VERSION,
            "graph_id": graph_id,
            "revision": revision,
            "vertices": [v.id for v in graph.vertices],
            "edges": [e.id for e in graph.valid_edges()],
        }
    )


# --- deserialization--------------------------------------------------------


def _loads(raw: Any, what: str) -> dict:
    if isinstance(raw, (bytes, str)):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SchemaError(f"{what} payload is not valid JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise SchemaError(f"{what} payload is not an object: {type(raw).__name__}")
    version = raw.get("schema")
    if version is not None and version != SCHEMA_VERSION:
        raise SchemaError(
            f"{what} payload has schema {version!r}, expected {SCHEMA_VERSION!r}"
        )
    return raw


def vertex_from_payload(raw: Any) -> Vertex:
    data = _loads(raw, "vertex")
    if not data.get("id"):
        raise SchemaError("vertex payload has no id")
    return Vertex(
        id=str(data["id"]),
        label=data.get("label"),
        group=data.get("group"),
    )


def edge_from_payload(raw: Any) -> EdgeNode:
    data = _loads(raw, "edge")
    if not data.get("id"):
        raise SchemaError("edge payload has no id")
    members = data.get("members") or []
    if not isinstance(members, list):
        raise SchemaError("edge payload 'members' must be a list")
    return EdgeNode(
        id=str(data["id"]),
        members=frozenset(str(m) for m in members),
        label=data.get("label"),
        weight=float(data.get("weight", 1.0)),
    )


def index_from_payload(raw: Any) -> tuple[list[str], list[str]]:
    """Return (vertex_ids, edge_ids) from an index payload."""
    data = _loads(raw, "index")
    vertices = data.get("vertices") or []
    edges = data.get("edges") or []
    if not isinstance(vertices, list) or not isinstance(edges, list):
        raise SchemaError("index payload 'vertices'/'edges' must be lists")
    return [str(v) for v in vertices], [str(e) for e in edges]


# --- source file -----------------------------------------------------------


def graph_from_file(path: str | Path = SOURCE_FILE) -> Graph:
    #Load the on-disk mock dataset.

    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)

    if not isinstance(data, dict):
        raise SchemaError("source file must contain a JSON object")

    graph = Graph(
        vertices=[vertex_from_payload({**v, "schema": SCHEMA_VERSION})
                  for v in data.get("vertices", [])],
        edges=[edge_from_payload({**e, "schema": SCHEMA_VERSION})
               for e in data.get("edges", [])],
    )

    conflicts = graph.id_conflicts()
    if conflicts:
        raise SchemaError(f"ids used by both a vertex and an edge: {sorted(conflicts)}")

    known = graph.vertex_ids()
    for edge in graph.edges:
        missing = edge.members - known
        if missing:
            raise SchemaError(
                f"edge {edge.id!r} references unknown vertices: {sorted(missing)}"
            )
    return graph


def graph_id_from_file(
    path: str | Path = SOURCE_FILE, default: str = DEFAULT_GRAPH_ID
) -> str:
    with open(path, encoding="utf-8") as fh:
        return str(json.load(fh).get("graph_id") or default)
