"""Connection settings and client factory for Pod-OS.

Credentials come from the environment:

    POD_OS_HOST POD_OS_PORT POD_OS_CLIENT_NAME POD_OS_USER POD_OS_PASSCODE

`POD_AVAILABLE` lets callers degrade gracefully when the client library
isn't installed, so the GUI still runs against sample data.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

try:  # the client library is internal; the app must survive its absence
    from pod_os_client import Client, Config

    POD_AVAILABLE = True
except ImportError:  # pragma: no cover - depends on the environment
    Client = Config = None  # type: ignore[assignment,misc]
    POD_AVAILABLE = False

MEMORY_ACTOR = "mem@gateway"

HOST = os.environ.get("POD_OS_HOST", "localhost")
PORT = int(os.environ.get("POD_OS_PORT", "62312"))
CLIENT_NAME = os.environ.get("POD_OS_CLIENT_NAME", "inspirational_app")
USER_NAME = os.environ.get("POD_OS_USER", "")
PASSCODE = os.environ.get("POD_OS_PASSCODE", "")


def gateway_address() -> str:
    """The `from_` value every message this app sends carries."""
    return f"{CLIENT_NAME}@gateway"


def make_config() -> "Config":
    if not POD_AVAILABLE:
        raise RuntimeError("pod_os_client is not installed")
    return Config(
        host=HOST,
        port=PORT,
        client_name=CLIENT_NAME,
        passcode=PASSCODE,
        user_name=USER_NAME,
        enable_concurrent_mode=True,
    )


@asynccontextmanager
async def connect() -> AsyncIterator["Client"]:
    """Open a client for the duration of the block."""
    async with Client(make_config()) as client:
        yield client
