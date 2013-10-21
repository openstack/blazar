# Copyright (c) 2013 Bull.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import tempfile

import fixtures
from oslo.config import cfg

from climate import context
from climate.db.sqlalchemy import api as db_api
from climate.openstack.common.db.sqlalchemy import session as db_session
from climate.openstack.common.fixture import config
from climate.openstack.common.fixture import mockpatch
from climate.openstack.common import log as logging
from climate.openstack.common import test


CONF = cfg.CONF
CONF.set_override('use_stderr', False)


logging.setup('climate')
_DB_CACHE = None


class Database(fixtures.Fixture):

    def setUp(self):
        super(Database, self).setUp()

        fd = tempfile.NamedTemporaryFile(delete=False)
        self.db_path = fd.name
        database_connection = 'sqlite:///' + self.db_path
        cfg.CONF.set_override('connection', str(database_connection),
                              group='database')
        db_session.cleanup()
        self.engine = db_session.get_engine()

        db_api.setup_db()
        self.addCleanup(db_api.drop_db)


class TestCase(test.BaseTestCase):
    """Test case base class for all unit tests.

    Due to the slowness of DB access, this class is not supporting DB tests.
    If needed, please herit from DBTestCase instead.
    """

    def setUp(self):
        """Run before each test method to initialize test environment."""
        super(TestCase, self).setUp()
        self.useFixture(config.Config())
        cfg.CONF([], project='climate')
        self.context_mock = None

    def patch(self, obj, attr):
        """Returns a Mocked object on the patched attribute."""
        mockfixture = self.useFixture(mockpatch.PatchObject(obj, attr))
        return mockfixture.mock

    def set_context(self, ctx):
        if self.context_mock is None:
            self.context_mock = self.patch(context.Context, 'current')
        self.context_mock.return_value = ctx


class DBTestCase(TestCase):
    """Test case base class for all database unit tests.

    `DBTestCase` differs from TestCase in that DB access is supported.
    Only tests needing DB support should herit from this class.
    """

    def setUp(self):
        super(DBTestCase, self).setUp()
        global _DB_CACHE
        if not _DB_CACHE:
            _DB_CACHE = Database()

        self.useFixture(_DB_CACHE)
