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
from blazar.api.v1 import utils as api_utils
from blazar.api.v1 import validation as validation_api
from blazar import exceptions
from blazar import tests


class ValidationTestCase(tests.TestCase):
    def setUp(self):
        super(ValidationTestCase, self).setUp()

        self.s_api = service_api
        self.u_api = api_utils
        self.v_api = validation_api
        self.exc = exceptions

        self.patch(self.u_api, 'render')
        self.not_found = self.patch(self.u_api, 'not_found')

        self.fake_id = 1

    def test_check_true(self):
        fake_get = self.patch(self.s_api.API, 'get_lease').return_value = True

        @self.v_api.check_exists(fake_get, self.fake_id)
        def trap(fake_id):
            self.u_api.render(lease_id=self.fake_id)
            fake_get.assert_called_once_with()

    def test_check_false(self):
        fake_get = self.patch(
            self.s_api.API, 'get_lease').side_effect = self.exc.NotFound()

        @self.v_api.check_exists(fake_get, self.fake_id)
        def trap(fake_id):
            self.u_api.render(lease_id=self.fake_id)
            self.not_found.assert_called_once_with()
