from sqlalchemy.testing import exclusions
from sqlalchemy.testing.requirements import SuiteRequirements


class Requirements(SuiteRequirements):
    @property
    def drop_table(self):
        return exclusions.open()

    @property
    def autocommit(self):
        return exclusions.open()

    @property
    def check_constraint_reflection(self):
        return exclusions.open()

    @property
    def comment_reflection(self):
        return exclusions.open()

    @property
    def indexes_with_ascdesc(self):
        return exclusions.open()

    @property
    def indexes_with_expressions(self):
        return exclusions.open()

    @property
    def table_ddl_if_exists(self):
        return exclusions.closed()

    @property
    def index_ddl_if_exists(self):
        return exclusions.closed()

    @property
    def foreign_keys(self):
        return exclusions.open()

    @property
    def foreign_keys_reflect_as_index(self):
        return exclusions.open()

    @property
    def array_type(self):
        """Target platform implements a native ARRAY type"""
        return exclusions.open()

    @property
    def json_type(self):
        """target platform implements a native JSON type."""

        return exclusions.open()

