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

from climate.api import context as api_context
from climate import context
from climate import tests


class ContextTestCase(tests.TestCase):
    def setUp(self):
        super(ContextTestCase, self).setUp()

        self.context = self.patch(context, 'ClimateContext')
        self.fake_headers = {u'X-User-Id': u'1',
                             u'X-Tenant-Id': u'1',
                             u'X-Auth-Token': u'111-111-111',
                             u'X-Service-Catalog': u'catalog',
                             u'X-User-Name': u'user_name',
                             u'X-Tenant-Name': u'tenant_name',
                             u'X-Roles': u'user_name0, user_name1'}

    def test_ctx_from_headers(self):
        api_context.ctx_from_headers(self.fake_headers)
        self.context.assert_called_once_with(user_id=u'1',
                                             roles=[u'user_name0',
                                                    u'user_name1'],
                                             tenant_name=u'tenant_name',
                                             auth_token=u'111-111-111',
                                             service_catalog=u'catalog',
                                             tenant_id=u'1',
                                             user_name=u'user_name')
