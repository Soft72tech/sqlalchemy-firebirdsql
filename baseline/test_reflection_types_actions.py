"""Reflection regressions using only the isolated baseline database."""
import asyncio
import uuid

import pytest
from sqlalchemy import create_engine, inspect, types
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.dialects import registry

registry.register("firebird.firebirdsql_async", "sqlalchemy_firebirdsql.firebirdsql", "FirebirdDialectAsync_firebirdsql")

URL = "firebird+{}://SYSDBA:root@127.0.0.1:13050//var/lib/firebird/data/phase1.fdb"


def exercise(conn):
    parent = "refp_" + uuid.uuid4().hex[:10]
    child = "refc_" + uuid.uuid4().hex[:10]
    conn.exec_driver_sql(f"CREATE TABLE {parent} (id INTEGER PRIMARY KEY)")
    conn.commit()
    try:
        columns = ["s SMALLINT", "i INTEGER", "b BIGINT", "wide INT128"]
        expected = {}
        for prefix, ddl, cls in (("n", "NUMERIC", types.NUMERIC), ("d", "DECIMAL", types.DECIMAL)):
            for precision in (4, 9, 18, 38):
                name = f"{prefix}{precision}"
                columns.append(f"{name} {ddl}({precision}, 2)")
                expected[name] = (cls, precision, 2)
        for name, action in (("default_fk", ""), ("noaction_fk", "ON DELETE NO ACTION ON UPDATE NO ACTION"), ("cascade_fk", "ON DELETE CASCADE ON UPDATE SET NULL")):
            columns.append(f"{name} INTEGER REFERENCES {parent}(id) {action}")
        conn.exec_driver_sql(f"CREATE TABLE {child} ({', '.join(columns)})")
        conn.commit()
        try:
            reflected = {c["name"]: c["type"] for c in inspect(conn).get_columns(child)}
            for name, (cls, precision, scale) in expected.items():
                typ = reflected[name]
                assert isinstance(typ, cls), (name, typ)
                assert (typ.precision, typ.scale) == (precision, scale)
            for name in ("s", "i", "b", "wide"):
                assert isinstance(reflected[name], types.Integer)
                assert not isinstance(reflected[name], types.Numeric)
            fks = {fk["constrained_columns"][0]: fk["options"] for fk in inspect(conn).get_foreign_keys(child)}
            for name in ("default_fk", "noaction_fk"):
                assert fks[name] == {}
            assert fks["cascade_fk"] == {"ondelete": "CASCADE", "onupdate": "SET NULL"}
        finally:
            conn.rollback()
            conn.exec_driver_sql(f"DROP TABLE {child}")
            conn.commit()
    finally:
        conn.rollback()
        conn.exec_driver_sql(f"DROP TABLE {parent}")
        conn.commit()


@pytest.mark.parametrize("driver", ["firebirdsql", "firebirdsql_async"])
def test_reflection_types_and_actions(driver):
    if driver == "firebirdsql":
        engine = create_engine(URL.format(driver))
        try:
            with engine.connect() as conn:
                exercise(conn)
        finally:
            engine.dispose()
    else:
        async def run():
            engine = create_async_engine(URL.format(driver))
            try:
                async with engine.connect() as conn:
                    await conn.run_sync(exercise)
            finally:
                await engine.dispose()
        asyncio.run(run())
