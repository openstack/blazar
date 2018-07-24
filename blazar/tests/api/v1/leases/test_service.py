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
from blazar import tests


class RPCApiTestCase(tests.TestCase):
    def setUp(self):
        super(RPCApiTestCase, self).setUp()
        self.s_api = service_api

        self.fake_list = []
        self.fake_lease = {}

        self.patch(self.s_api.API, "get_leases").return_value = self.fake_list
        self.patch(self.s_api.API, "create_lease").return_value = True
        self.patch(self.s_api.API, "get_lease").return_value = self.fake_lease
        self.patch(self.s_api.API, "update_lease").return_value = True
        self.patch(self.s_api.API, "delete_lease").return_value = True
        self.patch(self.s_api.API, "get_plugins").return_value(self.fake_lease)

    def test_get_lease(self):
        pass

    def test_create_lease(self):
        pass

    def test_update_lease(self):
        pass

    def test_delete_lease(self):
        pass

    def get_plugins(self):
        pass
