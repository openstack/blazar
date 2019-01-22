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


from blazar.manager.leases import rpcapi
from blazar import tests


class RPCAPITestCase(tests.TestCase):
    def setUp(self):
        super(RPCAPITestCase, self).setUp()

        self.manager = rpcapi.ManagerRPCAPI()

        self.call = self.patch(self.manager, "call")
        self.cast = self.patch(self.manager, "cast")

        self.fake_id = 1
        self.fake_values = {}

    def test_get_lease(self):
        self.manager.get_lease(self.fake_id)
        self.call.assert_called_once_with('get_lease', lease_id=1)

    def test_list_leases(self):
        self.manager.list_leases('fake')
        self.call.assert_called_once_with('list_leases', project_id='fake',
                                          query=None)

    def test_create_lease(self):
        self.manager.create_lease(self.fake_values)
        self.call.assert_called_once_with('create_lease', lease_values={})

    def test_update_lease(self):
        self.manager.update_lease(self.fake_id,
                                  self.fake_values)
        self.call.assert_called_once_with('update_lease',
                                          lease_id=1,
                                          values={})

    def test_delete_lease(self):
        self.manager.delete_lease(self.fake_id)
        self.call.assert_called_once_with('delete_lease', lease_id=1)
