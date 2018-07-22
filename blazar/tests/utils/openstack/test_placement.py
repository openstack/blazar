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

import json
import mock

from blazar import tests
from blazar.tests import fake_requests
from blazar.utils.openstack import exceptions
from blazar.utils.openstack import placement

from oslo_config import cfg
from oslo_config import fixture as conf_fixture
from oslo_utils import uuidutils

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

    @mock.patch('keystoneauth1.session.Session.request')
    def test_get_resource_provider(self, kss_req):
        rp_name = 'blazar'
        rp_uuid = uuidutils.generate_uuid()
        parent_uuid = uuidutils.generate_uuid()

        mock_json_data = {
            'resource_providers': [
                {
                    'uuid': rp_uuid,
                    'name': rp_name,
                    'generation': 0,
                    'parent_provider_uuid': parent_uuid
                }
            ]
        }

        kss_req.return_value = fake_requests.FakeResponse(
            200, content=json.dumps(mock_json_data))

        result = self.client.get_resource_provider(rp_name)

        expected_url = '/resource_providers?name=blazar'
        kss_req.assert_called_once_with(
            expected_url, 'GET',
            endpoint_filter={'service_type': 'placement',
                             'interface': 'public'},
            headers={'accept': 'application/json'},
            microversion=PLACEMENT_MICROVERSION, raise_exc=False)
        expected = {'uuid': rp_uuid,
                    'name': rp_name,
                    'generation': 0,
                    'parent_provider_uuid': parent_uuid}
        self.assertEqual(expected, result)

    @mock.patch('keystoneauth1.session.Session.request')
    def test_get_resource_provider_fail(self, kss_req):
        rp_name = 'blazar'
        kss_req.return_value = fake_requests.FakeResponse(404)

        self.assertRaises(
            exceptions.ResourceProviderRetrievalFailed,
            self.client.get_resource_provider, rp_name)

    @mock.patch('keystoneauth1.session.Session.request')
    def test_create_resource_provider(self, kss_req):
        rp_name = 'Blazar'
        rp_uuid = uuidutils.generate_uuid()
        parent_uuid = uuidutils.generate_uuid()

        mock_json_data = {'uuid': rp_uuid,
                          'name': rp_name,
                          'generation': 0,
                          'parent_provider_uuid': parent_uuid}

        kss_req.return_value = fake_requests.FakeResponse(
            200, content=json.dumps(mock_json_data))

        result = self.client.create_resource_provider(
            rp_name, rp_uuid=rp_uuid, parent_uuid=parent_uuid)

        expected_url = '/resource_providers'
        kss_req.assert_called_once_with(
            expected_url, 'POST',
            json={'uuid': rp_uuid,
                  'name': rp_name,
                  'parent_provider_uuid': parent_uuid},
            endpoint_filter={'service_type': 'placement',
                             'interface': 'public'},
            headers={'accept': 'application/json'},
            microversion=PLACEMENT_MICROVERSION, raise_exc=False)
        self.assertEqual(mock_json_data, result)

    @mock.patch('keystoneauth1.session.Session.request')
    def test_create_resource_provider_fail(self, kss_req):
        rp_name = 'Blazar'
        kss_req.return_value = fake_requests.FakeResponse(404)

        self.assertRaises(
            exceptions.ResourceProviderCreationFailed,
            self.client.create_resource_provider, rp_name)

    @mock.patch('keystoneauth1.session.Session.request')
    def test_delete_resource_provider(self, kss_req):
        rp_uuid = uuidutils.generate_uuid()
        kss_req.return_value = fake_requests.FakeResponse(200)

        self.client.delete_resource_provider(rp_uuid)

        expected_url = '/resource_providers/' + str(rp_uuid)
        kss_req.assert_called_once_with(
            expected_url, 'DELETE',
            endpoint_filter={'service_type': 'placement',
                             'interface': 'public'},
            headers={'accept': 'application/json'},
            microversion=PLACEMENT_MICROVERSION, raise_exc=False)

    @mock.patch('keystoneauth1.session.Session.request')
    def test_delete_resource_provider_fail(self, kss_req):
        rp_uuid = uuidutils.generate_uuid()
        kss_req.return_value = fake_requests.FakeResponse(404)

        self.assertRaises(
            exceptions.ResourceProviderDeletionFailed,
            self.client.delete_resource_provider, rp_uuid)

    @mock.patch('keystoneauth1.session.Session.request')
    def test_create_reservation_provider(self, kss_req):
        host_uuid = uuidutils.generate_uuid()
        host_name = "compute-1"
        rp_uuid = uuidutils.generate_uuid()
        rp_name = "blazar_compute-1"
        get_json_mock = {
            'resource_providers': [
                {
                    'uuid': host_uuid,
                    'name': host_name,
                    'generation': 0,
                    'parent_provider_uuid': None
                }
            ]
        }
        post_json_mock = {'uuid': rp_uuid,
                          'name': rp_name,
                          'generation': 0,
                          'parent_provider_uuid': host_uuid}
        mock_call1 = fake_requests.FakeResponse(
            200, content=json.dumps(get_json_mock))
        mock_call2 = fake_requests.FakeResponse(
            200, content=json.dumps(post_json_mock))
        kss_req.side_effect = [mock_call1, mock_call2]

        self.client.create_reservation_provider(host_name)

        expected_url_get = "/resource_providers?name=%s" % host_name
        kss_req.assert_any_call(
            expected_url_get, 'GET',
            endpoint_filter={'service_type': 'placement',
                             'interface': 'public'},
            headers={'accept': 'application/json'},
            microversion=PLACEMENT_MICROVERSION, raise_exc=False)

        expected_url_post = "/resource_providers"
        kss_req.assert_any_call(
            expected_url_post, 'POST',
            endpoint_filter={'service_type': 'placement',
                             'interface': 'public'},
            json={'name': 'blazar_compute-1',
                  'parent_provider_uuid': host_uuid},
            headers={'accept': 'application/json'},
            microversion=PLACEMENT_MICROVERSION, raise_exc=False)

    @mock.patch('keystoneauth1.session.Session.request')
    def test_delete_reservation_provider(self, kss_req):
        host_uuid = uuidutils.generate_uuid()
        host_name = "compute-1"
        rp_uuid = uuidutils.generate_uuid()
        rp_name = "blazar_compute-1"
        get_json_mock = {
            'resource_providers': [
                {
                    'uuid': rp_uuid,
                    'name': rp_name,
                    'generation': 0,
                    'parent_provider_uuid': host_uuid
                }
            ]
        }
        mock_call1 = fake_requests.FakeResponse(
            200, content=json.dumps(get_json_mock))
        mock_call2 = fake_requests.FakeResponse(200)
        kss_req.side_effect = [mock_call1, mock_call2]

        self.client.delete_reservation_provider(host_name)

        expected_url_get = "/resource_providers?name=%s" % rp_name
        kss_req.assert_any_call(
            expected_url_get, 'GET',
            endpoint_filter={'service_type': 'placement',
                             'interface': 'public'},
            headers={'accept': 'application/json'},
            microversion=PLACEMENT_MICROVERSION, raise_exc=False)

        expected_url_post = "/resource_providers/%s" % rp_uuid
        kss_req.assert_any_call(
            expected_url_post, 'DELETE',
            endpoint_filter={'service_type': 'placement',
                             'interface': 'public'},
            headers={'accept': 'application/json'},
            microversion=PLACEMENT_MICROVERSION, raise_exc=False)
