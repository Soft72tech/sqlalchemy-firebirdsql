from sqlalchemy.dialects import registry
import pytest

registry.register("firebird.firebirdsql", "sqlalchemy_firebird.firebirdsql", "AccessDialect_firebirdsql")

pytest.register_assert_rewrite("sqlalchemy_firebird.testing.assertions")

from sqlalchemy.testing.plugin.pytestplugin import *