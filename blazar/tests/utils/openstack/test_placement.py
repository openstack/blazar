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

import mock

from blazar import tests
from blazar.tests import fake_requests
from blazar.utils.openstack import placement

from oslo_config import cfg
from oslo_config import fixture as conf_fixture

CONF = cfg.CONF
PLACEMENT_MICROVERSION = 1.29


class TestPlacementClient(tests.TestCase):
    def setUp(self):
        super(TestPlacementClient, self).setUp()
        self.cfg = self.useFixture(conf_fixture.Config(CONF))
        self.cfg.config(os_auth_host='foofoo')
        self.cfg.config(os_auth_port='8080')
        self.cfg.config(os_auth_prefix='identity')
        self.cfg.config(os_auth_version='v3')
        self.client = placement.BlazarPlacementClient()

    def test_client_auth_url(self):
        self.assertEqual("http://foofoo:8080/identity/v3",
                         self.client._client.session.auth.auth_url)

    @mock.patch('keystoneauth1.session.Session.request')
    def test_get(self, kss_req):
        kss_req.return_value = fake_requests.FakeResponse(200)
        url = '/resource_providers'
        resp = self.client.get(url)
        self.assertEqual(200, resp.status_code)
        kss_req.assert_called_once_with(
            url, 'GET',
            endpoint_filter={'service_type': 'placement',
                             'interface': 'public'},
            headers={'accept': 'application/json'},
            microversion=PLACEMENT_MICROVERSION, raise_exc=False)

    @mock.patch('keystoneauth1.session.Session.request')
    def test_post(self, kss_req):
        kss_req.return_value = fake_requests.FakeResponse(200)
        url = '/resource_providers'
        data = {'name': 'unicorn'}
        resp = self.client.post(url, data)
        self.assertEqual(200, resp.status_code)
        kss_req.assert_called_once_with(
            url, 'POST', json=data,
            endpoint_filter={'service_type': 'placement',
                             'interface': 'public'},
            headers={'accept': 'application/json'},
            microversion=PLACEMENT_MICROVERSION, raise_exc=False)

    @mock.patch('keystoneauth1.session.Session.request')
    def test_put(self, kss_req):
        kss_req.return_value = fake_requests.FakeResponse(200)
        url = '/resource_providers'
        data = {'name': 'unicorn'}
        resp = self.client.put(url, data)
        self.assertEqual(200, resp.status_code)
        kss_req.assert_called_once_with(
            url, 'PUT', json=data,
            endpoint_filter={'service_type': 'placement',
                             'interface': 'public'},
            headers={'accept': 'application/json'},
            microversion=PLACEMENT_MICROVERSION, raise_exc=False)

    @mock.patch('keystoneauth1.session.Session.request')
    def test_delete(self, kss_req):
        kss_req.return_value = fake_requests.FakeResponse(200)
        url = '/resource_providers'
        resp = self.client.delete(url)
        self.assertEqual(200, resp.status_code)
        kss_req.assert_called_once_with(
            url, 'DELETE',
            endpoint_filter={'service_type': 'placement',
                             'interface': 'public'},
            headers={'accept': 'application/json'},
            microversion=PLACEMENT_MICROVERSION, raise_exc=False)
