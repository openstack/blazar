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

import flask
from oslo_utils import uuidutils
from testtools import matchers

from oslo_middleware import request_id as id

from blazar.api import context as api_context
from blazar.api.v1 import api_version_request
from blazar.api.v1.leases import service as service_api
from blazar.api.v1.leases import v1_0 as leases_api_v1_0
from blazar.api.v1 import request_id
from blazar.api.v1 import request_log
from blazar import context
from blazar import tests


def make_app():
    """App builder (wsgi).

    Entry point for Blazar REST API server.
    """
    app = flask.Flask('blazar.api')

    app.register_blueprint(leases_api_v1_0.rest, url_prefix='/v1')
    app.wsgi_app = request_id.BlazarReqIdMiddleware(app.wsgi_app)
    app.wsgi_app = request_log.RequestLog(app.wsgi_app)

    return app


def fake_lease(**kw):
    return {
        'id': kw.get('id', '2bb8720a-0873-4d97-babf-0d906851a1eb'),
        'name': kw.get('name', 'lease_test'),
        'start_date': kw.get('start_date', '2014-01-01 01:23'),
        'end_date': kw.get('end_date', '2014-02-01 13:37'),
        'trust_id': kw.get('trust_id',
                           '35b17138b3644e6aa1318f3099c5be68'),
        'user_id': kw.get('user_id', 'efd8780712d24b389c705f5c2ac427ff'),
        'project_id': kw.get('project_id',
                             'bd9431c18d694ad3803a8d4a6b89fd36'),
        'reservations': kw.get('reservations', [
            {
                'resource_id': '1234',
                'resource_type': 'virtual:instance'
            }
        ]),
        'events': kw.get('events', []),
        'status': kw.get('status', 'ACTIVE'),
    }


def fake_lease_request_body(exclude=None, **kw):
    default_exclude = set(['id', 'trust_id', 'user_id', 'project_id',
                           'status'])
    exclude = exclude or set()
    exclude |= default_exclude
    lease_body = fake_lease(**kw)
    return dict((key, lease_body[key])
                for key in lease_body if key not in exclude)


class LeaseAPITestCase(tests.TestCase):
    def setUp(self):
        super(LeaseAPITestCase, self).setUp()
        self.app = make_app()
        self.headers = {'Accept': 'application/json',
                        'OpenStack-API-Version': 'reservation 1.0'}
        self.lease_uuid = str(uuidutils.generate_uuid())
        self.mock_ctx = self.patch(api_context, 'ctx_from_headers')
        self.mock_ctx.return_value = context.BlazarContext(
            user_id='fake', project_id='fake', roles=['member'])
        self.create_lease = self.patch(service_api.API, 'create_lease')
        self.get_leases = self.patch(service_api.API, 'get_leases')
        self.get_lease = self.patch(service_api.API, 'get_lease')
        self.update_lease = self.patch(service_api.API, 'update_lease')
        self.delete_lease = self.patch(service_api.API, 'delete_lease')

    def _assert_response(self, actual_resp, expected_status_code,
                         expected_resp_body, key='lease',
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
            self.get_leases.return_value = []
            res = c.get('/v1/leases', headers=self.headers)
            self._assert_response(res, 200, [], key='leases')

    def test_list_with_non_acceptable_api_version(self):
        headers = {'Accept': 'application/json',
                   'OpenStack-API-Version': 'reservation 1.2'}
        with self.app.test_client() as c:
            res = c.get('/v1/leases', headers=headers)
            self.assertEqual(406, res.status_code)

    def test_create(self):
        with self.app.test_client() as c:
            self.create_lease.return_value = fake_lease(id=self.lease_uuid)
            res = c.post('/v1/leases', json=fake_lease_request_body(
                id=self.lease_uuid), headers=self.headers)
            self._assert_response(res, 201, fake_lease(id=self.lease_uuid))

    def test_create_with_bad_api_version(self):
        headers = {'Accept': 'application/json',
                   'OpenStack-API-Version': 'reservation 1.a'}
        with self.app.test_client() as c:
            res = c.post('/v1/leases', json=fake_lease_request_body(
                id=self.lease_uuid), headers=headers)
            self.assertEqual(400, res.status_code)

    def test_get(self):
        with self.app.test_client() as c:
            self.get_lease.return_value = fake_lease(id=self.lease_uuid)
            res = c.get('/v1/leases/{0}'.format(self.lease_uuid),
                        headers=self.headers)
            self._assert_response(res, 200, fake_lease(id=self.lease_uuid))

    def test_get_with_latest_api_version(self):
        headers = {'Accept': 'application/json',
                   'OpenStack-API-Version': 'reservation latest'}
        with self.app.test_client() as c:
            self.get_lease.return_value = fake_lease(id=self.lease_uuid)
            res = c.get('/v1/leases/{0}'.format(self.lease_uuid),
                        headers=headers)
            self._assert_response(res, 200, fake_lease(id=self.lease_uuid),
                                  expected_api_version='reservation 1.0')

    def test_update(self):
        headers = {'Accept': 'application/json'}
        with self.app.test_client() as c:
            self.fake_lease = fake_lease(id=self.lease_uuid, name='updated')
            self.fake_lease_body = fake_lease_request_body(
                exclude=set(['reservations', 'events']),
                id=self.lease_uuid,
                name='updated'
            )
            self.update_lease.return_value = self.fake_lease

            res = c.put('/v1/leases/{0}'.format(self.lease_uuid),
                        json=self.fake_lease_body, headers=headers)
            self._assert_response(res, 200, self.fake_lease)

    def test_update_with_no_service_type_in_header(self):
        headers = {'Accept': 'application/json',
                   'OpenStack-API-Version': '1.0'}
        with self.app.test_client() as c:
            self.fake_lease = fake_lease(id=self.lease_uuid, name='updated')
            self.fake_lease_body = fake_lease_request_body(
                exclude=set(['reservations', 'events']),
                id=self.lease_uuid,
                name='updated'
            )
            self.update_lease.return_value = self.fake_lease

            res = c.put('/v1/leases/{0}'.format(self.lease_uuid),
                        json=self.fake_lease_body, headers=headers)
            self._assert_response(res, 200, self.fake_lease)

    def test_delete(self):
        with self.app.test_client() as c:
            res = c.delete('/v1/leases/{0}'.format(self.lease_uuid),
                           headers=self.headers)
            res_id = res.headers.get(id.HTTP_RESP_HEADER_REQUEST_ID)
            self.assertEqual(204, res.status_code)
            self.assertIn(id.HTTP_RESP_HEADER_REQUEST_ID, res.headers)
            self.assertThat(res_id, matchers.StartsWith('req-'))
