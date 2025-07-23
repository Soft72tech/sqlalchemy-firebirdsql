import importlib
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
    driver = "firebirdsql"
    supports_statement_cache = True

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
            "READ COMMITED": 1,
            "REPEATABLE READ": 2,
            "SNAPSHOT": 2,
            "SERIALIZABLE": 3,
            "AUTOCOMMIT": 4,
        }

    def get_isolation_level_values(self, dbapi_conn: DBAPIConnection) -> list[IsolationLevel]:
        return cast(list[IsolationLevel], list(self._isolation_lookup))

    def get_isolation_level(self, dbapi_connection: DBAPIConnection) -> IsolationLevel:
        return cast(
            IsolationLevel,
            list(self._isolation_lookup.keys())[
                list(self._isolation_lookup.values()).index(dbapi_connection.isolation_level)
            ],
        )

    def set_isolation_level(self, dbapi_connection: DBAPIConnection, level: IsolationLevel):
        if level == "AUTOCOMMIT":
            dbapi_connection.set_autocommit(True)
            dbapi_connection.set_isolation_level(self._isolation_lookup["READ COMMITED"])

        else:
            dbapi_connection.set_isolation_level(self._isolation_lookup[level])


class AsyncAdapt_firebirdsql_ss_cursor(AsyncAdapt_dbapi_ss_cursor):
    __slots__ = ()


class AsyncAdapt_firebirdsql_cursor(AsyncAdapt_dbapi_cursor):
    __slots__ = ()


class AsyncAdapt_firebirdsql_connection(AsyncAdapt_dbapi_connection):
    __slots__ = ()

    _cursor_cls = AsyncAdapt_firebirdsql_cursor
    _ss_cursor_cls = AsyncAdapt_firebirdsql_ss_cursor

    # TODO: isolation level


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
            setattr(self, error, getattr(self.firebirdsql, error))

        self.firebirdsql_version = getattr(self.firebirdsql, "__version__")
        self.paramstyle = "qmark"

    def connect(self, *args, **kwargs):
        creator_fn = kwargs.pop("async_creator_fn", self.firebirdsql.aio.connect)

        return AsyncAdapt_firebirdsql_connection(self, await_only(creator_fn(*args, **kwargs)))


class FirebirdExecutionContextAsync(FirebirdExecutionContext): ...


class FirebirdDialectAsync_firebirdsql(FirebirdDialect_firebirdsql):
    is_async = True

    supports_statement_cache = True
    supports_server_side_cursors = False

    execution_ctx_cls = FirebirdExecutionContextAsync

    @classmethod
    def import_dbapi(cls):
        return AsyncAdapt_firebirdsql_dbapi(importlib.import_module("firebirdsql.aio"))


dialect = FirebirdDialect_firebirdsql
dialect_async = FirebirdDialectAsync_firebirdsql
