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

from blazar.api.v1.oshosts import service as service_api
from blazar.api.v1.oshosts import v1_0 as api
from blazar.api.v1 import utils as utils_api
from blazar import tests


class RESTApiTestCase(tests.TestCase):
    def setUp(self):
        super(RESTApiTestCase, self).setUp()
        self.api = api
        self.u_api = utils_api
        self.s_api = service_api

        self.render = self.patch(self.u_api, "render")
        self.get_computehosts = self.patch(self.s_api.API,
                                           'get_computehosts')
        self.create_computehost = self.patch(self.s_api.API,
                                             'create_computehost')
        self.get_computehost = self.patch(self.s_api.API, 'get_computehost')
        self.update_computehost = self.patch(self.s_api.API,
                                             'update_computehost')
        self.delete_computehost = self.patch(self.s_api.API,
                                             'delete_computehost')
        self.list_allocations = self.patch(self.s_api.API, 'list_allocations')
        self.get_allocations = self.patch(self.s_api.API, 'get_allocations')
        self.fake_id = '1'

    def test_computehost_list(self):
        self.api.computehosts_list(query={})
        self.render.assert_called_once_with(
            hosts=self.get_computehosts(query={}))

    def test_computehosts_create(self):
        self.api.computehosts_create(data=None)
        self.render.assert_called_once_with(host=self.create_computehost())

    def test_computehosts_get(self):
        self.api.computehosts_get(host_id=self.fake_id)
        self.render.assert_called_once_with(host=self.get_computehost())

    def test_computehosts_update(self):
        self.api.computehosts_update(host_id=self.fake_id, data=self.fake_id)
        self.render.assert_called_once_with(host=self.update_computehost())

    def test_computehosts_delete(self):
        self.api.computehosts_delete(host_id=self.fake_id)
        self.render.assert_called_once_with()

    def test_allocation_list(self):
        self.api.allocations_list(query={})
        self.render.assert_called_once_with(
            allocations=self.list_allocations())

    def test_allocation_get(self):
        self.api.allocations_get(host_id=self.fake_id, query={})
        self.render.assert_called_once_with(allocation=self.get_allocations())
