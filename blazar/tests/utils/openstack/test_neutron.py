# Copyright (c) 2019 NTT.
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

from unittest import mock

import neutronclient
from neutronclient.common import exceptions as neutron_exceptions
from oslo_config import cfg
from oslo_config import fixture

from blazar import context
from blazar import tests
from blazar.utils.openstack import exceptions
from blazar.utils.openstack import neutron

CONF = cfg.CONF


class TestBlazarNeutronClient(tests.TestCase):
    def setUp(self):
        super(TestBlazarNeutronClient, self).setUp()
        self.cfg = self.useFixture(fixture.Config(CONF))
        self.context = context
        self.ctx = self.patch(self.context, 'current')

    def test_client_from_kwargs(self):
        kwargs = {
            'auth_url': 'http://foo:8080/identity/v3',
            'region_name': 'RegionTwo',
            'global_request_id': 'req-e19f8f4f-40e7-441e-b776-7b43ed15c7dd'
        }
        client = neutron.BlazarNeutronClient(**kwargs)
        self.assertEqual("http://foo:8080/identity/v3",
                         client.neutron.httpclient.session.auth.auth_url)
        self.assertEqual("RegionTwo", client.neutron.httpclient.region_name)
        self.assertEqual("req-e19f8f4f-40e7-441e-b776-7b43ed15c7dd",
                         client.neutron.httpclient.global_request_id)


class TestFloatingIPPool(tests.TestCase):
    def setUp(self):
        super(TestFloatingIPPool, self).setUp()
        self.mock_net = self.patch(neutronclient.v2_0.client.Client,
                                   'show_network')
        self.mock_net.return_value = {'network': {'id': 'net-id'}}

    def test_init_floatingippool(self):
        client = neutron.FloatingIPPool('net-id')
        self.assertEqual('net-id', client.network_id)
        self.mock_net.assert_called_once_with('net-id')

    def test_init_with_invalid_network_id(self):
        self.mock_net.side_effect = neutron_exceptions.NotFound()

        self.assertRaises(exceptions.FloatingIPNetworkNotFound,
                          neutron.FloatingIPPool, 'invalid-net-id')

    @mock.patch.object(neutronclient.v2_0.client.Client, 'create_floatingip')
    @mock.patch.object(neutronclient.v2_0.client.Client, 'replace_tag')
    def test_create_reserved_floatingip(self, mock_tag, mock_fip):
        mock_fip.return_value = {'floatingip': {'id': 'fip-id'}}

        client = neutron.FloatingIPPool('net-id')
        client.create_reserved_floatingip('subnet-id', '172.24.4.200',
                                          'project-id', 'reservation-id')
        expected_body = {
            'floatingip': {
                'floating_network_id': 'net-id',
                'subnet_id': 'subnet-id',
                'floating_ip_address': '172.24.4.200',
                'project_id': 'project-id'
            }
        }
        mock_fip.assert_called_once_with(expected_body)
        mock_tag.assert_called_once_with(
            'floatingips',
            'fip-id',
            {'tags': ['blazar', 'reservation:reservation-id']}
        )

    @mock.patch.object(neutronclient.v2_0.client.Client, 'list_floatingips')
    @mock.patch.object(neutronclient.v2_0.client.Client, 'update_floatingip')
    @mock.patch.object(neutronclient.v2_0.client.Client, 'delete_floatingip')
    def test_delete_floatingip_with_deleted(self, mock_delete,
                                            mock_update, mock_list):
        mock_list.return_value = {'floatingips': []}

        client = neutron.FloatingIPPool('net-id')
        client.delete_reserved_floatingip('172.24.4.200')

        query = {
            'floating_ip_address': '172.24.4.200',
            'floating_network_id': 'net-id'
        }
        mock_list.assert_called_once_with(**query)
        mock_update.assert_not_called()
        mock_delete.assert_not_called()

    @mock.patch.object(neutronclient.v2_0.client.Client, 'list_floatingips')
    @mock.patch.object(neutronclient.v2_0.client.Client, 'update_floatingip')
    @mock.patch.object(neutronclient.v2_0.client.Client, 'delete_floatingip')
    def test_delete_floatingip_with_associated(self, mock_delete,
                                               mock_update, mock_list):
        mock_list.return_value = {
            'floatingips': [
                {'port_id': 'port-id', 'id': 'fip-id'}
            ]}

        client = neutron.FloatingIPPool('net-id')
        client.delete_reserved_floatingip('172.24.4.200')

        query = {
            'floating_ip_address': '172.24.4.200',
            'floating_network_id': 'net-id'
        }
        mock_list.assert_called_once_with(**query)

        mock_update.assert_called_once_with('fip-id',
                                            {'floatingip': {'port_id': None}})
        mock_delete.assert_called_once_with('fip-id')

    @mock.patch.object(neutronclient.v2_0.client.Client, 'list_floatingips')
    @mock.patch.object(neutronclient.v2_0.client.Client, 'update_floatingip')
    @mock.patch.object(neutronclient.v2_0.client.Client, 'delete_floatingip')
    def test_delete_floatingip_with_deassociated(self, mock_delete,
                                                 mock_update, mock_list):
        mock_list.return_value = {
            'floatingips': [
                {'port_id': None, 'id': 'fip-id'}
            ]}

        client = neutron.FloatingIPPool('net-id')
        client.delete_reserved_floatingip('172.24.4.200')

        query = {
            'floating_ip_address': '172.24.4.200',
            'floating_network_id': 'net-id'
        }
        mock_list.assert_called_once_with(**query)
        mock_update.assert_not_called()
        mock_delete.assert_called_once_with('fip-id')
