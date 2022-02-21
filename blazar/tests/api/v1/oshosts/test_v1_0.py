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

import ddt
import flask
from oslo_utils import uuidutils
from testtools import matchers

from oslo_middleware import request_id as id

from blazar.api import context as api_context
from blazar.api.v1 import api_version_request
from blazar.api.v1.oshosts import service as service_api
from blazar.api.v1.oshosts import v1_0 as hosts_api_v1_0
from blazar.api.v1 import request_id
from blazar.api.v1 import request_log
from blazar import context
from blazar import tests


def make_app():
    """App builder (wsgi).

    Entry point for Blazar REST API server.
    """
    app = flask.Flask('blazar.api')

    app.register_blueprint(hosts_api_v1_0.rest, url_prefix='/v1')
    app.wsgi_app = request_id.BlazarReqIdMiddleware(app.wsgi_app)
    app.wsgi_app = request_log.RequestLog(app.wsgi_app)

    return app


def fake_computehost(**kw):
    return {
        'id': kw.get('id', '1'),
        'hypervisor_hostname': kw.get('hypervisor_hostname', 'host01'),
        'hypervisor_type': kw.get('hypervisor_type', 'QEMU'),
        'vcpus': kw.get('vcpus', 1),
        'hypervisor_version': kw.get('hypervisor_version', 1000000),
        'trust_id': kw.get('trust_id',
                           '35b17138-b364-4e6a-a131-8f3099c5be68'),
        'memory_mb': kw.get('memory_mb', 8192),
        'local_gb': kw.get('local_gb', 50),
        'cpu_info': kw.get('cpu_info',
                           "{\"vendor\": \"Intel\", \"model\": \"qemu32\", "
                           "\"arch\": \"x86_64\", \"features\": [],"
                           " \"topology\": {\"cores\": 1}}",
                           ),
        'extra_capas': kw.get('extra_capas',
                              {'vgpus': 2, 'fruits': 'bananas'})
    }


def fake_computehost_request_body(include=None, **kw):
    computehost_body = fake_computehost(**kw)
    computehost_body['name'] = kw.get('name',
                                      computehost_body['hypervisor_hostname'])
    default_include = set(['name', 'extra_capas'])
    include = include or set()
    include |= default_include
    return dict((key, computehost_body[key])
                for key in computehost_body if key in include)


@ddt.ddt
class OsHostAPITestCase(tests.TestCase):

    def setUp(self):
        super(OsHostAPITestCase, self).setUp()
        self.app = make_app()
        self.headers = {'Accept': 'application/json',
                        'OpenStack-API-Version': 'reservation 1.0'}
        self.host_id = str('1')
        self.mock_ctx = self.patch(api_context, 'ctx_from_headers')
        self.mock_ctx.return_value = context.BlazarContext(
            user_id='fake', project_id='fake', roles=['member'])
        self.get_computehosts = self.patch(service_api.API,
                                           'get_computehosts')
        self.create_computehost = self.patch(service_api.API,
                                             'create_computehost')
        self.get_computehost = self.patch(service_api.API, 'get_computehost')
        self.update_computehost = self.patch(service_api.API,
                                             'update_computehost')
        self.delete_computehost = self.patch(service_api.API,
                                             'delete_computehost')
        self.list_allocations = self.patch(service_api.API,
                                           'list_allocations')
        self.get_allocations = self.patch(service_api.API, 'get_allocations')
        self.list_resource_properties = self.patch(service_api.API,
                                                   'list_resource_properties')
        self.update_resource_property = self.patch(service_api.API,
                                                   'update_resource_property')

    def _assert_response(self, actual_resp, expected_status_code,
                         expected_resp_body, key='host',
                         expected_api_version='reservation 1.0'):
        res_id = actual_resp.headers.get(id.HTTP_RESP_HEADER_REQUEST_ID)
        api_version = actual_resp.headers.get(
            api_version_request.API_VERSION_REQUEST_HEADER)
        self.assertIn(id.HTTP_RESP_HEADER_REQUEST_ID,
                      actual_resp.headers)
        self.assertIn(api_version_request.API_VERSION_REQUEST_HEADER,
                      actual_resp.headers)
        self.assertIn(api_version_request.VARY_HEADER, actual_resp.headers)
        self.assertThat(res_id, matchers.StartsWith('req-'))
        self.assertEqual(expected_status_code, actual_resp.status_code)
        self.assertEqual(expected_resp_body, actual_resp.get_json()[key])
        self.assertEqual(expected_api_version, api_version)
        self.assertEqual('OpenStack-API-Version', actual_resp.headers.get(
            api_version_request.VARY_HEADER))

    def test_list(self):
        with self.app.test_client() as c:
            self.get_computehosts.return_value = []
            res = c.get('/v1', headers=self.headers)
            self._assert_response(res, 200, [], key='hosts')

    def test_list_with_non_acceptable_version(self):
        headers = {'Accept': 'application/json',
                   'OpenStack-API-Version': 'reservation 1.2'}
        with self.app.test_client() as c:
            res = c.get('/v1', headers=headers)
            self.assertEqual(406, res.status_code)

    def test_create(self):
        with self.app.test_client() as c:
            self.create_computehost.return_value = fake_computehost(
                id=self.host_id)
            res = c.post('/v1', json=fake_computehost_request_body(
                id=self.host_id), headers=self.headers)
            self._assert_response(res, 201, fake_computehost(
                id=self.host_id))

    def test_create_with_bad_api_version(self):
        headers = {'Accept': 'application/json',
                   'OpenStack-API-Version': 'reservation 1.a'}
        with self.app.test_client() as c:
            res = c.post('/v1', json=fake_computehost_request_body(
                id=self.host_id), headers=headers)
            self.assertEqual(400, res.status_code)

    def test_get(self):
        with self.app.test_client() as c:
            self.get_computehost.return_value = fake_computehost(
                id=self.host_id)
            res = c.get('/v1/{0}'.format(self.host_id), headers=self.headers)
            self._assert_response(res, 200, fake_computehost(id=self.host_id))

    def test_get_with_latest_api_version(self):
        headers = {'Accept': 'application/json',
                   'OpenStack-API-Version': 'reservation latest'}
        with self.app.test_client() as c:
            self.get_computehost.return_value = fake_computehost(
                id=self.host_id)
            res = c.get('/v1/{0}'.format(self.host_id), headers=headers)
            self._assert_response(res, 200, fake_computehost(id=self.host_id),
                                  expected_api_version='reservation 1.0')

    def test_update(self):
        headers = {'Accept': 'application/json'}
        with self.app.test_client() as c:
            self.fake_computehost = fake_computehost(id=self.host_id,
                                                     name='updated')
            self.fake_computehost_body = fake_computehost_request_body(
                id=self.host_id,
                name='updated'
            )
            self.update_computehost.return_value = self.fake_computehost

            res = c.put('/v1/{0}'.format(self.host_id),
                        json=self.fake_computehost_body, headers=headers)
            self._assert_response(res, 200, self.fake_computehost, 'host')

    def test_update_with_no_service_type_in_header(self):
        headers = {'Accept': 'application/json',
                   'OpenStack-API-Version': '1.0'}
        with self.app.test_client() as c:
            self.fake_computehost = fake_computehost(id=self.host_id,
                                                     name='updated')
            self.fake_computehost_body = fake_computehost_request_body(
                id=self.host_id,
                name='updated'
            )
            self.update_computehost.return_value = self.fake_computehost

            res = c.put('/v1/{0}'.format(self.host_id),
                        json=self.fake_computehost_body, headers=headers)
            self._assert_response(res, 200, self.fake_computehost, 'host')

    def test_delete(self):
        with self.app.test_client() as c:
            self.get_computehosts.return_value = fake_computehost(
                id=self.host_id)

            res = c.delete('/v1/{0}'.format(self.host_id),
                           headers=self.headers)
            res_id = res.headers.get(id.HTTP_RESP_HEADER_REQUEST_ID)
            self.assertEqual(204, res.status_code)
            self.assertIn(id.HTTP_RESP_HEADER_REQUEST_ID, res.headers)
            self.assertThat(res_id, matchers.StartsWith('req-'))

    def test_allocation_list(self):
        with self.app.test_client() as c:
            self.list_allocations.return_value = []
            res = c.get('/v1/allocations', headers=self.headers)
            self._assert_response(res, 200, [], key='allocations')

    def test_allocation_get(self):
        with self.app.test_client() as c:
            self.get_allocations.return_value = {}
            res = c.get('/v1/{0}/allocation'.format(self.host_id),
                        headers=self.headers)
            self._assert_response(res, 200, {}, key='allocation')

    @ddt.data({'lease_id': str(uuidutils.generate_uuid()),
               'reservation_id': str(uuidutils.generate_uuid())})
    def test_allocation_list_with_query_params(self, query_params):
        with self.app.test_client() as c:
            res = c.get('/v1/allocations?{0}'.format(query_params),
                        headers=self.headers)
            self._assert_response(res, 200, {}, key='allocations')

    @ddt.data({'lease_id': str(uuidutils.generate_uuid()),
               'reservation_id': str(uuidutils.generate_uuid())})
    def test_allocation_get_with_query_params(self, query_params):
        with self.app.test_client() as c:
            res = c.get('/v1/{0}/allocation?{1}'.format(
                self.host_id, query_params), headers=self.headers)
            self._assert_response(res, 200, {}, key='allocation')

    def test_resource_properties_list(self):
        with self.app.test_client() as c:
            self.list_resource_properties.return_value = []
            res = c.get('/v1/properties', headers=self.headers)
            self._assert_response(res, 200, [], key='resource_properties')

    def test_resource_property_update(self):
        resource_property = 'fake_property'
        resource_property_body = {'private': True}

        with self.app.test_client() as c:

            res = c.patch('/v1/properties/{0}'.format(resource_property),
                          json=resource_property_body,
                          headers=self.headers)
            self._assert_response(res, 200, {}, 'resource_property')
