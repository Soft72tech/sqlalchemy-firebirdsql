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
