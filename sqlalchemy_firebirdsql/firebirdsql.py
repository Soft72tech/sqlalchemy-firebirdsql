import importlib
from collections import deque
from typing import Type, cast

from sqlalchemy import util
from sqlalchemy.connectors.asyncio import (
    AsyncAdapt_dbapi_connection,
    AsyncAdapt_dbapi_cursor,
    AsyncAdapt_dbapi_ss_cursor,
)
from sqlalchemy.engine import URL, Dialect
from sqlalchemy.engine.interfaces import DBAPIConnection, IsolationLevel
from sqlalchemy.util.concurrency import await_only

from sqlalchemy_firebirdsql.base import FirebirdDialect, FirebirdExecutionContext


class FirebirdDialect_firebirdsql(FirebirdDialect):
    driver: str = "firebirdsql"
    supports_statement_cache: bool = True

    default_isolation_level: IsolationLevel | None = "READ COMMITTED"

    @classmethod
    def import_dbapi(cls):
        return importlib.import_module("firebirdsql")

    @classmethod
    def get_async_dialect_cls(cls, url: URL) -> Type[Dialect]:
        return FirebirdDialectAsync_firebirdsql

    @util.memoized_property
    def _isolation_lookup(self):
        return {
            "READ COMMITTED LEGACY": 0,
            "READ COMMITTED": 1,
            "REPEATABLE READ": 2,
            "SNAPSHOT": 2,
            "SERIALIZABLE": 3,
        }

    def get_isolation_level_values(self, dbapi_conn: DBAPIConnection) -> list[IsolationLevel]:
        return cast(list[IsolationLevel], list(self._isolation_lookup) + ["AUTOCOMMIT"])

    def get_isolation_level(self, dbapi_connection: DBAPIConnection) -> IsolationLevel:
        return cast(
            IsolationLevel,
            list(self._isolation_lookup.keys())[
                list(self._isolation_lookup.values()).index(dbapi_connection.isolation_level)
            ],
        )

    def detect_autocommit_setting(self, dbapi_connection: DBAPIConnection) -> bool:
        # Pool proxies and async adapters expose the raw driver connection.
        # Read its local flag only: rollback suppression must not do wire I/O.
        raw = getattr(dbapi_connection, "driver_connection", dbapi_connection)
        if isinstance(raw, AsyncAdapt_dbapi_connection):
            raw = raw._connection
        return bool(raw._autocommit)

    def set_isolation_level(self, dbapi_connection: DBAPIConnection, level: IsolationLevel):
        if level == "AUTOCOMMIT":
            dbapi_connection.set_autocommit(True)
            dbapi_connection.set_isolation_level(self._isolation_lookup["READ COMMITTED"])

        else:
            dbapi_connection.set_autocommit(False)
            dbapi_connection.set_isolation_level(self._isolation_lookup[level])

    def connect(self, *args, **kwargs):
        connection = super().connect(*args, **kwargs)
        connection.set_autocommit(False)
        return connection

    # def do_commit(self, dbapi_connection: DBAPIConnection):
    #     if dbapi_connection.is_active():
    #         dbapi_connection.commit()

    #     return super().do_commit(dbapi_connection)


class AsyncAdapt_firebirdsql_ss_cursor(AsyncAdapt_dbapi_ss_cursor):
    __slots__ = ()


class AsyncAdapt_firebirdsql_cursor(AsyncAdapt_dbapi_cursor):
    __slots__ = ('_rowcount',)

    def __init__(self, adapt_connection):
        super().__init__(adapt_connection)
        self._rowcount = -1

    @property
    def rowcount(self):
        # SQLAlchemy can read this outside the async/greenlet context and
        # after soft close. Never perform wire I/O from this property.
        return self._rowcount

    async def _execute_async(self, operation, parameters):
        self._rowcount = -1
        async with self._adapt_connection._execute_mutex:
            if parameters is None:
                result = await self._cursor.execute(operation)
            else:
                result = await self._cursor.execute(operation, parameters)
            if self._cursor.description and not self.server_side:
                self._rows = deque(await self._cursor.fetchall())
            self._rowcount = await self._cursor.get_rowcount()
            return result

    async def _executemany_async(self, operation, seq_of_parameters):
        self._rowcount = -1
        async with self._adapt_connection._execute_mutex:
            # The driver exposes only the final statement's count, not the
            # batch total. Report unknown rather than a misleading partial sum.
            return await self._cursor.executemany(operation, seq_of_parameters)


class AsyncAdapt_firebirdsql_connection(AsyncAdapt_dbapi_connection):
    __slots__ = ()

    _cursor_cls = AsyncAdapt_firebirdsql_cursor
    _ss_cursor_cls = AsyncAdapt_firebirdsql_ss_cursor

    def close(self):
        # pyfirebirdsql closes its transport synchronously, unlike its cursors.
        self._connection.close()

    def ping(self):
        # Pool reconnection belongs to SQLAlchemy, not the raw driver.
        return await_only(self._connection.ping(reconnect=False))

    def set_autocommit(self, value):
        await_only(self._connection.set_autocommit(value))

    def set_isolation_level(self, value):
        self._connection.isolation_level = int(value)

    @property
    def isolation_level(self):
        return self._connection.isolation_level

    @isolation_level.setter
    def isolation_level(self, value):
        self.set_isolation_level(value)


class AsyncAdapt_firebirdsql_dbapi:
    def __init__(self, firebirdsql):
        self.firebirdsql = firebirdsql
        self._init_dbapi_attributes()

    def _init_dbapi_attributes(self):
        for error in (
            "Error",
            "InterfaceError",
            "DatabaseError",
            "DataError",
            "OperationalError",
            "IntegrityError",
            "InternalError",
            "ProgrammingError",
            "NotSupportedError",
        ):
            firebird_sync = importlib.import_module("firebirdsql")
            setattr(self, error, getattr(firebird_sync, error))

        self.firebirdsql_version = getattr(firebird_sync, "__version__")
        self.paramstyle = "qmark"
        self.Binary = firebird_sync.Binary

    def connect(self, *args, **kwargs):
        creator_fn = kwargs.pop("async_creator_fn", self.firebirdsql.connect)

        return AsyncAdapt_firebirdsql_connection(self, await_only(creator_fn(*args, **kwargs)))


class FirebirdExecutionContextAsync(FirebirdExecutionContext): ...


class FirebirdDialectAsync_firebirdsql(FirebirdDialect_firebirdsql):
    is_async = True

    supports_statement_cache = True
    supports_server_side_cursors = False

    execution_ctx_cls = FirebirdExecutionContextAsync

    def get_driver_connection(self, connection):
        return connection._connection

    @classmethod
    def import_dbapi(cls):
        return AsyncAdapt_firebirdsql_dbapi(importlib.import_module("firebirdsql.aio"))


dialect = FirebirdDialect_firebirdsql
dialect_async = FirebirdDialectAsync_firebirdsql
