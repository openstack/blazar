# Copyright (c) 2019 NTT.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import mock

from blazar.db import api as db_api
from blazar.manager import exceptions as mgr_exceptions
from blazar.plugins.floatingips import floatingip_plugin
from blazar import tests
from blazar.utils.openstack import exceptions as opst_exceptions
from blazar.utils.openstack import neutron


class FloatingIpPluginTest(tests.TestCase):

    def setUp(self):
        super(FloatingIpPluginTest, self).setUp()
        self.fip_pool = self.patch(neutron, 'FloatingIPPool')

    def test_create_floatingip(self):
        m = mock.MagicMock()
        m.fetch_subnet.return_value = {'id': 'subnet-id'}
        self.fip_pool.return_value = m
        fip_row = {
            'id': 'fip-id',
            'network_id': 'net-id',
            'subnet_id': 'subnet-id',
            'floating_ip_address': '172.24.4.100',
            'reservable': True
        }
        patch_fip_create = self.patch(db_api, 'floatingip_create')
        patch_fip_create.return_value = fip_row

        data = {
            'floating_ip_address': '172.24.4.100',
            'floating_network_id': 'net-id'
        }
        expected = fip_row

        fip_plugin = floatingip_plugin.FloatingIpPlugin()
        ret = fip_plugin.create_floatingip(data)

        self.assertDictEqual(expected, ret)
        m.fetch_subnet.assert_called_once_with('172.24.4.100')
        patch_fip_create.assert_called_once_with({
            'floating_network_id': 'net-id',
            'subnet_id': 'subnet-id',
            'floating_ip_address': '172.24.4.100'})

    def test_create_floatingip_with_invalid_ip(self):
        m = mock.MagicMock()
        m.fetch_subnet.side_effect = opst_exceptions.NeutronUsesFloatingIP()
        self.fip_pool.return_value = m

        fip_plugin = floatingip_plugin.FloatingIpPlugin()
        self.assertRaises(opst_exceptions.NeutronUsesFloatingIP,
                          fip_plugin.create_floatingip,
                          {'floating_ip_address': 'invalid-ip',
                           'floating_network_id': 'id'})

    def test_get_floatingip(self):
        fip_row = {
            'id': 'fip-id',
            'network_id': 'net-id',
            'subnet_id': 'subnet-id',
            'floating_ip_address': '172.24.4.100',
            'reservable': True
        }
        patch_fip_get = self.patch(db_api, 'floatingip_get')
        patch_fip_get.return_value = fip_row

        expected = fip_row

        fip_plugin = floatingip_plugin.FloatingIpPlugin()
        ret = fip_plugin.get_floatingip('fip-id')

        self.assertDictEqual(expected, ret)
        patch_fip_get.assert_called_once_with('fip-id')

    def test_get_floatingip_with_no_exist(self):
        patch_fip_get = self.patch(db_api, 'floatingip_get')
        patch_fip_get.return_value = None

        fip_plugin = floatingip_plugin.FloatingIpPlugin()
        self.assertRaises(mgr_exceptions.FloatingIPNotFound,
                          fip_plugin.get_floatingip, 'fip-id')

        patch_fip_get.assert_called_once_with('fip-id')

    def test_get_list_floatingips(self):
        fip_rows = [{
            'id': 'fip-id',
            'network_id': 'net-id',
            'subnet_id': 'subnet-id',
            'floating_ip_address': '172.24.4.100',
            'reservable': True
        }]
        patch_fip_list = self.patch(db_api, 'floatingip_list')
        patch_fip_list.return_value = fip_rows

        expected = fip_rows

        fip_plugin = floatingip_plugin.FloatingIpPlugin()
        ret = fip_plugin.list_floatingip()

        self.assertListEqual(expected, ret)
        patch_fip_list.assert_called_once_with()

    def test_delete_floatingip(self):
        fip_row = {
            'id': 'fip-id',
            'network_id': 'net-id',
            'subnet_id': 'subnet-id',
            'floating_ip_address': '172.24.4.100',
            'reservable': True
        }
        patch_fip_get = self.patch(db_api, 'floatingip_get')
        patch_fip_get.return_value = fip_row
        patch_fip_destroy = self.patch(db_api, 'floatingip_destroy')

        fip_plugin = floatingip_plugin.FloatingIpPlugin()
        fip_plugin.delete_floatingip('fip-id')

        patch_fip_get.assert_called_once_with('fip-id')
        patch_fip_destroy.assert_called_once_with('fip-id')

    def test_delete_floatingip_with_no_exist(self):
        patch_fip_get = self.patch(db_api, 'floatingip_get')
        patch_fip_get.return_value = None

        fip_plugin = floatingip_plugin.FloatingIpPlugin()
        self.assertRaises(mgr_exceptions.FloatingIPNotFound,
                          fip_plugin.delete_floatingip,
                          'non-exists-id')
