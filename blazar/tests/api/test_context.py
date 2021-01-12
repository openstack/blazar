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
from oslo_utils.fixture import uuidsentinel
import webob
from werkzeug import wrappers

from blazar.api import context as api_context
from blazar import context
from blazar import exceptions
from blazar import tests


class ContextTestCase(tests.TestCase):

    def setUp(self):
        super(ContextTestCase, self).setUp()

        self.fake_headers = {'X-User-Id': uuidsentinel.user_id,
                             'X-Project-Id': uuidsentinel.project_id,
                             'X-Auth-Token': '111-111-111',
                             'X-User-Name': 'user_name',
                             'X-Project-Name': 'project_name',
                             'X-Roles': 'user_name0, user_name1'}
        self.context = self.patch(context, 'BlazarContext')
        self.catalog = jsonutils.dump_as_bytes({'nova': 'catalog'})

    def test_ctx_from_headers_no_catalog(self):
        self.assertRaises(
            exceptions.ServiceCatalogNotFound,
            api_context.ctx_from_headers,
            self.fake_headers)

    def test_ctx_from_headers_wrong_format(self):
        catalog = ['etc']
        self.fake_headers['X-Service-Catalog'] = catalog
        self.assertRaises(
            exceptions.WrongFormat,
            api_context.ctx_from_headers,
            self.fake_headers)


class ContextTestCaseV1(ContextTestCase):

    def test_ctx_from_headers(self):
        self.fake_headers['X-Service-Catalog'] = self.catalog
        environ_base = {
            'openstack.request_id': 'req-' + uuidsentinel.reqid,
            'openstack.global_request_id': 'req-' + uuidsentinel.globalreqid}
        req = wrappers.Request.from_values(
            '/v1/leases',
            headers=self.fake_headers,
            environ_base=environ_base)
        api_context.ctx_from_headers(req.headers)

        self.context.assert_called_once_with(
            user_id=uuidsentinel.user_id,
            roles=['user_name0',
                   'user_name1'],
            project_name='project_name',
            auth_token='111-111-111',
            service_catalog={'nova': 'catalog'},
            project_id=uuidsentinel.project_id,
            user_name='user_name',
            request_id='req-' + uuidsentinel.reqid,
            global_request_id='req-' + uuidsentinel.globalreqid)


class ContextTestCaseV2(ContextTestCase):

    def test_ctx_from_headers(self):
        self.fake_headers['X-Service-Catalog'] = self.catalog
        req = webob.Request.blank('/v2/leases')
        req.headers = self.fake_headers
        api_context.ctx_from_headers(req.headers)

        self.context.assert_called_once_with(
            user_id=uuidsentinel.user_id,
            roles=['user_name0',
                   'user_name1'],
            project_name='project_name',
            auth_token='111-111-111',
            service_catalog={'nova': 'catalog'},
            project_id=uuidsentinel.project_id,
            user_name='user_name')
