from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy_firebirdsql.firebirdsql import (
    AsyncAdapt_firebirdsql_connection, FirebirdDialect_firebirdsql,
    FirebirdDialectAsync_firebirdsql,
)


@pytest.mark.parametrize('dialect_cls', [FirebirdDialect_firebirdsql, FirebirdDialectAsync_firebirdsql])
@pytest.mark.parametrize('enabled', [False, True])
@pytest.mark.parametrize('kind', ['raw', 'proxy', 'adapter', 'proxied_adapter'])
def test_detection_reads_raw_local_state(dialect_cls, enabled, kind):
    raw = SimpleNamespace(_autocommit=enabled)
    connection = raw
    if 'adapter' in kind:
        connection = object.__new__(AsyncAdapt_firebirdsql_connection)
        connection._connection = raw
    if kind in ('proxy', 'proxied_adapter'):
        connection = SimpleNamespace(driver_connection=connection)
    assert dialect_cls().detect_autocommit_setting(connection) is enabled
    raw._autocommit = not enabled
    assert dialect_cls().detect_autocommit_setting(connection) is not enabled


@pytest.mark.parametrize('dialect_cls', [FirebirdDialect_firebirdsql, FirebirdDialectAsync_firebirdsql])
@pytest.mark.parametrize('enabled', [False, True])
@pytest.mark.parametrize('skip', [False, True])
def test_rollback_suppression_is_opt_in_and_autocommit_only(dialect_cls, enabled, skip):
    connection = SimpleNamespace(driver_connection=SimpleNamespace(_autocommit=enabled), rollback=Mock())
    dialect_cls(skip_autocommit_rollback=skip).do_rollback(connection)
    assert connection.rollback.call_count == (0 if enabled and skip else 1)
