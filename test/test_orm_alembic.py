import asyncio
import os
from uuid import uuid4

import pytest
from sqlalchemy import Column, Identity, Integer, String, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


@pytest.mark.skipif(not os.environ.get('FIREBIRD_TEST_URL'), reason='isolated DB required')
def test_async_orm_crud_savepoint_and_rollback():
    class Base(DeclarativeBase):
        pass

    class Item(Base):
        __tablename__ = 'orm_' + uuid4().hex[:12]
        id: Mapped[int] = mapped_column(Identity(), primary_key=True)
        name: Mapped[str] = mapped_column(String(40))

    async def run():
        engine = create_async_engine(make_url(os.environ['FIREBIRD_TEST_URL']).set(drivername='firebird+firebirdsql_async'))
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            try:
                sessions = async_sessionmaker(engine, expire_on_commit=False)
                async with sessions.begin() as session:
                    item = Item(name='first')
                    session.add(item)
                    await session.flush()
                    key = item.id
                    assert isinstance(key, int)
                    nested = await session.begin_nested()
                    item.name = 'discard'
                    await session.flush()
                    await nested.rollback()
                    await session.refresh(item)
                    assert item.name == 'first'
                    item.name = 'second'
                async with sessions() as session:
                    item = await session.get(Item, key)
                    assert item.name == 'second'
                    item.name = 'rollback'
                    await session.flush()
                    await session.rollback()
                async with sessions.begin() as session:
                    item = (await session.scalars(select(Item))).one()
                    assert item.name == 'second'
                    await session.delete(item)
                async with sessions() as session:
                    assert (await session.scalars(select(Item))).all() == []
            finally:
                async with engine.begin() as conn:
                    await conn.run_sync(Base.metadata.drop_all)
        finally:
            await engine.dispose()
    asyncio.run(run())


@pytest.mark.skipif(not os.environ.get('FIREBIRD_TEST_URL'), reason='isolated DB required')
def test_alembic_upgrade_downgrade_over_async_connection():
    pytest.importorskip('alembic')
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    import sqlalchemy_firebirdsql.alembic  # noqa: F401

    name = 'mig_' + uuid4().hex[:12]

    def upgrade(conn):
        operations = Operations(MigrationContext.configure(conn))
        operations.create_table(name, Column('id', Integer, primary_key=True))

    def change(conn):
        operations = Operations(MigrationContext.configure(conn))
        operations.add_column(name, Column('label', String(40)))

    def rename(conn):
        operations = Operations(MigrationContext.configure(conn))
        operations.alter_column(name, 'label', new_column_name='title')

    def check(conn):
        assert [c['name'] for c in inspect(conn).get_columns(name)] == ['id', 'title']

    def downgrade(conn):
        operations = Operations(MigrationContext.configure(conn))
        operations.drop_column(name, 'title')

    async def run():
        engine = create_async_engine(make_url(os.environ['FIREBIRD_TEST_URL']).set(drivername='firebird+firebirdsql_async'))
        try:
            async with engine.begin() as conn:
                await conn.run_sync(upgrade)
            try:
                for action in (change, rename, check, downgrade):
                    async with engine.begin() as conn:
                        await conn.run_sync(action)
                async with engine.connect() as conn:
                    await conn.execute(text(f'INSERT INTO {name} (id) VALUES (1)'))
                    await conn.commit()
            finally:
                async with engine.begin() as conn:
                    await conn.execute(text(f'DROP TABLE {name}'))
        finally:
            await engine.dispose()
    asyncio.run(run())
