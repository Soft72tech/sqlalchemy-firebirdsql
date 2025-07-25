from sqlalchemy.testing import exclusions
from sqlalchemy.testing.requirements import SuiteRequirements


class Requirements(SuiteRequirements):
    @property
    def autocommit(self):
        return exclusions.open()
