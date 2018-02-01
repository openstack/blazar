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

from oslo_serialization import jsonutils

from blazar.api import context as api_context
from blazar import context
from blazar import exceptions
from blazar import tests


class ContextTestCase(tests.TestCase):
    def setUp(self):
        super(ContextTestCase, self).setUp()

        self.fake_headers = {u'X-User-Id': u'1',
                             u'X-Project-Id': u'1',
                             u'X-Auth-Token': u'111-111-111',
                             u'X-User-Name': u'user_name',
                             u'X-Project-Name': u'project_name',
                             u'X-Roles': u'user_name0, user_name1'}

    def test_ctx_from_headers(self):
        self.context = self.patch(context, 'BlazarContext')
        catalog = jsonutils.dump_as_bytes({'nova': 'catalog'})
        self.fake_headers[u'X-Service-Catalog'] = catalog
        api_context.ctx_from_headers(self.fake_headers)
        self.context.assert_called_once_with(user_id=u'1',
                                             roles=[u'user_name0',
                                                    u'user_name1'],
                                             project_name=u'project_name',
                                             auth_token=u'111-111-111',
                                             service_catalog={
                                                 u'nova': u'catalog'},
                                             project_id=u'1',
                                             user_name=u'user_name')

    def test_ctx_from_headers_no_catalog(self):
        self.assertRaises(
            exceptions.ServiceCatalogNotFound,
            api_context.ctx_from_headers,
            self.fake_headers)

    def test_ctx_from_headers_wrong_format(self):
        catalog = ['etc']
        self.fake_headers[u'X-Service-Catalog'] = catalog
        self.assertRaises(
            exceptions.WrongFormat,
            api_context.ctx_from_headers,
            self.fake_headers)
