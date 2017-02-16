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

from blazar.db import api as db_api
from blazar import tests


class DBApiTestCase(tests.TestCase):
    """Test case for DB API."""

    # TODO(sbauza) : Extend methods to CRUD lease

    def setUp(self):
        super(DBApiTestCase, self).setUp()
        self.db_api = db_api

        self.patch(self.db_api.IMPL, "setup_db").return_value = True
        self.patch(self.db_api.IMPL, "drop_db").return_value = True

    def test_setup_db(self):
        self.assertTrue(self.db_api.setup_db())

    def test_drop_db(self):
        self.assertTrue(self.db_api.drop_db())
