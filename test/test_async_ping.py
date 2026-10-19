import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.util.concurrency import greenlet_spawn

from sqlalchemy_firebirdsql.firebirdsql import AsyncAdapt_firebirdsql_connection


@pytest.mark.parametrize("result", [True, False])
def test_ping_awaits_driver_without_reconnect(result):
    raw = SimpleNamespace(ping=AsyncMock(return_value=result))
    adapter = object.__new__(AsyncAdapt_firebirdsql_connection)
    adapter._connection = raw
    assert asyncio.run(greenlet_spawn(adapter.ping)) is result
    raw.ping.assert_awaited_once_with(reconnect=False)


def test_ping_propagates_driver_errors():
    raw = SimpleNamespace(ping=AsyncMock(side_effect=RuntimeError("offline")))
    adapter = object.__new__(AsyncAdapt_firebirdsql_connection)
    adapter._connection = raw
    with pytest.raises(RuntimeError, match="offline"):
        asyncio.run(greenlet_spawn(adapter.ping))
