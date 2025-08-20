import pytest
from sqlalchemy.dialects import registry
from sqlalchemy.testing.plugin.pytestplugin import *  # noqa: E402, F403

import firebirdsql.utils


registry.register("firebird.firebirdsql", "sqlalchemy_firebirdsql.firebirdsql", "FirebirdDialect_firebirdsql")

pytest.register_assert_rewrite("sqlalchemy_firebirdsql.testing.assertions")

firebirdsql.utils.enable_debug_print(verbose=True)
