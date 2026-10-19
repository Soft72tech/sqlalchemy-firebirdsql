import pytest
from sqlalchemy.dialects import registry
from sqlalchemy.testing.plugin.pytestplugin import *  # noqa: E402, F403

registry.register("firebird", "sqlalchemy_firebirdsql.firebirdsql", "FirebirdDialect_firebirdsql")
registry.register("firebird.firebirdsql", "sqlalchemy_firebirdsql.firebirdsql", "FirebirdDialect_firebirdsql")

registry.register("firebird.firebirdsql_async", "sqlalchemy_firebirdsql.firebirdsql", "FirebirdDialectAsync_firebirdsql")

pytest.register_assert_rewrite("sqlalchemy_firebirdsql.testing.assertions")
