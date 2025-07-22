import pytest
from sqlalchemy.dialects import registry


registry.register("firebird.firebirdsql", "sqlalchemy_firebirdsql.firebirdsql", "FirebirdDialect_firebirdsql")

pytest.register_assert_rewrite("sqlalchemy_firebirdsql.testing.assertions")

from sqlalchemy.testing.plugin.pytestplugin import *  # noqa: E402, F403
