"""Regression for the official suite's Firebird-only DDL transaction hook."""
import asyncio
import uuid

import pytest
from sqlalchemy import Column, Integer, MetaData, Table, create_engine, select
from sqlalchemy.ext.asyncio import create_async_engine

# Explicit opt-in: ordinary application imports must not install this hook.
import sqlalchemy_firebirdsql.provision  # noqa: F401


URL = "firebird+{}://SYSDBA:root@127.0.0.1:13050//var/lib/firebird/data/phase1.fdb"


def exercise(connection):
    metadata = MetaData()
    table = Table("ddl_" + uuid.uuid4().hex[:12], metadata, Column("id", Integer))
    transaction = connection.begin()
    try:
        table.create(connection)
        assert transaction.is_active
        connection.execute(table.insert().values(id=1))
        assert connection.scalar(select(table.c.id)) == 1
        transaction.rollback()
        # Test DDL is committed, but subsequent DML still rolls back normally.
        assert connection.execute(select(table.c.id)).all() == []
    finally:
        connection.rollback()
        table.drop(connection, checkfirst=True)
        connection.commit()


@pytest.mark.parametrize("driver", ["firebirdsql", "firebirdsql_async"])
def test_suite_ddl_transaction(driver):
    if driver == "firebirdsql":
        engine = create_engine(URL.format(driver))
        try:
            with engine.connect() as connection:
                exercise(connection)
        finally:
            engine.dispose()
    else:
        async def run():
            engine = create_async_engine(URL.format(driver))
            try:
                async with engine.connect() as connection:
                    await connection.run_sync(exercise)
            finally:
                await engine.dispose()
        asyncio.run(run())
