"""Load the POD graph from a JSON file into Pod-OS storage.

    python -m app.data.buildData --file data/pod_graph.json

Writes one event per vertex and one per edge-node, then the index event
last: a reader that finds the index is guaranteed the entities it names are
already stored  
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from pod_os_client.message.intents import IntentType
from pod_os_client.message.types import EventFields, Message, PayloadFields

from app.core.graph import Graph
from app.data import pod_schema as schema
from app.data.pod_client import MEMORY_ACTOR, connect, gateway_address

DEFAULT_FILE = schema.SOURCE_FILE


class StoreError(RuntimeError):
    """A StoreEvent came back with a non-success status."""


def store_message(
    unique_id: str,
    event_type: str,
    payload: str,
    owner: str,
    from_addr: str,
) -> Message:
    """Build one StoreEvent message."""
    return Message(
        to=MEMORY_ACTOR,
        from_=from_addr,
        intent=IntentType.StoreEvent.name,
        message_id=str(uuid4()),
        event=EventFields(unique_id=unique_id, type=event_type, owner=owner),
        payload=PayloadFields(data=payload, mime_type=schema.MIME_JSON),
    )


def _check(response, unique_id: str) -> None:
    """Reject a store that didn't succeed.

    TODO: further develop once the ProcessingStatus enum is known
    """
    status = response.processing_status()
    text = str(getattr(status, "name", status)).lower()
    if any(bad in text for bad in ("error", "fail", "reject", "denied")):
        raise StoreError(f"storing {unique_id} returned {status!r}")


async def store_graph(
    client,
    graph: Graph,
    graph_id: str = schema.DEFAULT_GRAPH_ID,
    owner: str = schema.DEFAULT_OWNER,
    from_addr: str | None = None,
) -> list[str]:
    #Write `graph` to Pod-OS. Returns the unique_ids written, index last.
    from_addr = from_addr or gateway_address()
    edges = graph.valid_edges()

    entities = [
        (schema.vertex_uid(graph_id, v.id), schema.TYPE_VERTEX, schema.vertex_payload(v))
        for v in graph.vertices
    ] + [
        (schema.edge_uid(graph_id, e.id), schema.TYPE_EDGE, schema.edge_payload(e))
        for e in edges
    ]

    async def put(unique_id: str, event_type: str, payload: str) -> str:
        message = store_message(unique_id, event_type, payload, owner, from_addr)
        _check(await client.send_message(message), unique_id)
        return unique_id

    written = list(await asyncio.gather(*(put(*item) for item in entities)))

    # Index last — it is what makes the new graph visible to readers.
    revision = datetime.now(timezone.utc).isoformat()
    written.append(
        await put(
            schema.index_uid(graph_id),
            schema.TYPE_INDEX,
            schema.index_payload(graph, graph_id, revision),
        )
    )
    return written


async def main() -> None:
    parser = argparse.ArgumentParser(description="Load a graph JSON file into Pod-OS.")
    parser.add_argument("--file", default=DEFAULT_FILE, help="source JSON file")
    parser.add_argument("--graph-id", default=None, help="override the graph id")
    parser.add_argument("--owner", default=schema.DEFAULT_OWNER)
    args = parser.parse_args()

    graph = schema.graph_from_file(args.file)
    graph_id = args.graph_id or schema.graph_id_from_file(args.file)
    print(
        f"Loaded {len(graph.vertices)} vertices, {len(graph.valid_edges())} edge-nodes "
        f"({len(graph.incidences())} incidences) from {args.file}"
    )

    async with connect() as client:
        written = await store_graph(client, graph, graph_id, args.owner)

    print(f"Stored {len(written)} events under graph id {graph_id!r}")
    print(f"Index: {written[-1]}")


if __name__ == "__main__":
    asyncio.run(main())
