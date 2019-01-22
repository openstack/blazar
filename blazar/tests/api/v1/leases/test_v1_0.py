# Copyright (c) 2013 Mirantis Inc.
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

from blazar.api.v1.leases import service as service_api
from blazar.api.v1.leases import v1_0 as api
from blazar.api.v1 import utils as utils_api
from blazar import tests


class RESTApiTestCase(tests.TestCase):
    def setUp(self):
        super(RESTApiTestCase, self).setUp()
        self.api = api
        self.u_api = utils_api
        self.s_api = service_api

        self.render = self.patch(self.u_api, "render")
        self.get_leases = self.patch(self.s_api.API, 'get_leases')
        self.create_lease = self.patch(self.s_api.API, 'create_lease')
        self.get_lease = self.patch(self.s_api.API, 'get_lease')
        self.update_lease = self.patch(self.s_api.API, 'update_lease')
        self.delete_lease = self.patch(self.s_api.API, 'delete_lease')

        self.fake_id = '1'

    def test_lease_list(self):
        self.api.leases_list(query={})
        self.render.assert_called_once_with(leases=self.get_leases(query={}))

    def test_leases_create(self):
        self.api.leases_create(data=None)
        self.render.assert_called_once_with(lease=self.create_lease())

    def test_leases_get(self):
        self.api.leases_get(lease_id=self.fake_id)
        self.render.assert_called_once_with(lease=self.get_lease())

    def test_leases_update(self):
        self.api.leases_update(lease_id=self.fake_id, data=self.fake_id)
        self.render.assert_called_once_with(lease=self.update_lease())

    def test_leases_delete(self):
        self.api.leases_delete(lease_id=self.fake_id)
        self.render.assert_called_once_with()
