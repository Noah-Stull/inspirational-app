"""Read the POD graph, from Pod-OS when it's reachable and the file when not.

`fetch_graph()` is the only thing the UI calls. It tries three sources in
order and reports which one it used, so the window never shows data whose
origin is a mystery:

    1. Pod-OS   — GetEvent the index, then the entities it names
    2. the file — data/pod_graph.json, the same dataset buildData loads
    3. empty    — logged as an error rather than silently drawing nothing

Set POD_GRAPH_SOURCE=file to skip Pod-OS entirely.
"""

from __future__ import annotations

import asyncio
import logging
import os
from uuid import uuid4

from app.core.graph import EdgeNode, Graph, Vertex
from app.data import pod_schema as schema
from app.data.pod_client import (
    MEMORY_ACTOR,
    POD_AVAILABLE,
    connect,
    gateway_address,
)

log = logging.getLogger(__name__)

# IntentType.GetEvent.name — resolved lazily so this module imports without
# the client library present.
GET_EVENT_INTENT = "GetEvent"

FORCE_FILE = os.environ.get("POD_GRAPH_SOURCE", "").lower() == "file"


class FetchError(RuntimeError):
    """A GetEvent came back empty or malformed."""


def get_message(unique_id: str, event_type: str, from_addr: str):
    """Build one GetEvent message."""
    from pod_os_client.message.types import EventFields, Message

    return Message(
        to=MEMORY_ACTOR,
        from_=from_addr,
        intent=GET_EVENT_INTENT,
        message_id=str(uuid4()),
        event=EventFields(
            unique_id=unique_id,
            type=event_type,
            owner=schema.DEFAULT_OWNER,
        ),
    )


async def _get_payload(client, unique_id: str, event_type: str, from_addr: str):
    response = await client.send_message(get_message(unique_id, event_type, from_addr))
    payload = response.payload_data()
    if payload is None:
        raise FetchError(f"no payload for {unique_id}")
    return payload


async def load_graph(
    client,
    graph_id: str = schema.DEFAULT_GRAPH_ID,
    from_addr: str | None = None,
) -> Graph:
    """Rebuild the graph stored under `graph_id`.

    Entities that fail to load are logged and skipped rather than sinking the
    whole read — `Graph.valid_edges()` trims any edge left pointing at a
    vertex that didn't arrive.
    """
    from_addr = from_addr or gateway_address()

    vertex_ids, edge_ids = schema.index_from_payload(
        await _get_payload(client, schema.index_uid(graph_id), schema.TYPE_INDEX, from_addr)
    )

    wanted = [
        (schema.vertex_uid(graph_id, vid), schema.TYPE_VERTEX) for vid in vertex_ids
    ] + [
        (schema.edge_uid(graph_id, eid), schema.TYPE_EDGE) for eid in edge_ids
    ]

    payloads = await asyncio.gather(
        *(_get_payload(client, uid, etype, from_addr) for uid, etype in wanted),
        return_exceptions=True,
    )

    vertices: list[Vertex] = []
    edges: list[EdgeNode] = []
    for (unique_id, event_type), payload in zip(wanted, payloads):
        if isinstance(payload, BaseException):
            log.warning("skipping %s: %s", unique_id, payload)
            continue
        try:
            if event_type == schema.TYPE_VERTEX:
                vertices.append(schema.vertex_from_payload(payload))
            else:
                edges.append(schema.edge_from_payload(payload))
        except schema.SchemaError as exc:
            log.warning("skipping %s: %s", unique_id, exc)

    graph = Graph(vertices=vertices, edges=edges)
    conflicts = graph.id_conflicts()
    if conflicts:
        log.warning("ids claimed by both sides, rendering will merge them: %s", conflicts)
    return graph


async def fetch_graph_async(graph_id: str = schema.DEFAULT_GRAPH_ID) -> Graph:
    async with connect() as client:
        return await load_graph(client, graph_id)


def fetch_graph(graph_id: str = schema.DEFAULT_GRAPH_ID) -> tuple[Graph, str]:
    """Synchronous entry point for the Qt layer.

    Returns (graph, source) where source is a short human-readable label the
    window puts on screen.

    NOTE: this blocks the event loop for the duration of the read, which is
    fine for a graph this size. If the query grows, move the call onto a
    QThread and hand the result back with a signal rather than widening this
    function.
    """
    if FORCE_FILE:
        log.info("POD_GRAPH_SOURCE=file — skipping Pod-OS")
    elif not POD_AVAILABLE:
        log.info("pod_os_client is not installed — falling back to the file")
    else:
        try:
            graph = asyncio.run(fetch_graph_async(graph_id))
            log.info("loaded %d nodes from Pod-OS", len(graph))
            return graph, f"Pod-OS · {graph_id}"
        except Exception as exc:  # noqa: BLE001 - never take the window down
            log.warning("Pod-OS read failed (%s) — falling back to the file", exc)

    return graph_from_file()


def graph_from_file() -> tuple[Graph, str]:
    """Load the dataset file, or an empty graph if it can't be read."""
    path = schema.SOURCE_FILE
    try:
        graph = schema.graph_from_file(path)
        log.info("loaded %d nodes from %s", len(graph), path)
        return graph, f"file · {path.name}"
    except (OSError, ValueError) as exc:
        log.error("could not read %s (%s) — nothing to draw", path, exc)
        return Graph(), "no source available"
