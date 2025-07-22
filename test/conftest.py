from sqlalchemy.dialects import registry
import pytest

registry.register("firebird.firebirdsql", "sqlalchemy_firebirdsql.firebirdsql", "FirebirdDialect_firebirdsql")

pytest.register_assert_rewrite("sqlalchemy_firebirdsql.testing.assertions")

from sqlalchemy.testing.plugin.pytestplugin import *
