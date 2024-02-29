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

import fixtures
import tempfile
import testscenarios

from oslo_log import log as logging
from oslotest import base

from blazar import config as cfg
from blazar import context
from blazar.db.sqlalchemy import api as db_api
from blazar.db.sqlalchemy import facade_wrapper

cfg.CONF.set_override('use_stderr', False)

logging.setup(cfg.CONF, 'blazar')
_DB_CACHE = None


class Database(fixtures.Fixture):

    def setUp(self):
        super(Database, self).setUp()

        fd = tempfile.NamedTemporaryFile(delete=False)
        self.db_path = fd.name
        database_connection = 'sqlite:///' + self.db_path
        cfg.CONF.set_override('connection', str(database_connection),
                              group='database')
        facade_wrapper._clear_engine()

        db_api.setup_db()
        self.addCleanup(db_api.drop_db)


class TestCase(testscenarios.WithScenarios, base.BaseTestCase):
    """Test case base class for all unit tests.

    Due to the slowness of DB access, this class is not supporting DB tests.
    If needed, please herit from DBTestCase instead.
    """

    def setUp(self):
        """Run before each test method to initialize test environment."""
        super(TestCase, self).setUp()
        self.context_mock = None
        cfg.CONF(args=[], project='blazar')

    def patch(self, obj, attr):
        """Returns a Mocked object on the patched attribute."""
        mockfixture = self.useFixture(fixtures.MockPatchObject(obj, attr))
        return mockfixture.mock

    def set_context(self, ctx):
        if self.context_mock is None:
            self.context_mock = self.patch(context.BlazarContext, 'current')
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


class FakeServiceCatalog(object):
    def __init__(self, catalog):
        self._catalog = catalog

    def normalize_catalog(self):
        return self._catalog
