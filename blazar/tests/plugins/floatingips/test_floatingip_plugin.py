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

import datetime
from unittest import mock

from oslo_config import cfg

from blazar import context
from blazar.db import api as db_api
from blazar.db import utils as db_utils
from blazar.manager import exceptions as mgr_exceptions
from blazar.plugins import floatingips as plugin
from blazar.plugins.floatingips import floatingip_plugin
from blazar import tests
from blazar.utils.openstack import exceptions as opst_exceptions
from blazar.utils.openstack import neutron


CONF = cfg.CONF


class FloatingIpPluginTest(tests.TestCase):

    def setUp(self):
        super(FloatingIpPluginTest, self).setUp()

        self.cfg = cfg

        # Make sure we clean up any override which could impact other tests
        self.addCleanup(self.cfg.CONF.reset)

        self.db_api = db_api
        self.db_utils = db_utils
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
        patch_fip_alloc = self.patch(db_api,
                                     'fip_allocation_get_all_by_values')
        patch_fip_alloc.return_value = []
        patch_fip_destroy = self.patch(db_api, 'floatingip_destroy')

        fip_plugin = floatingip_plugin.FloatingIpPlugin()
        fip_plugin.delete_floatingip('fip-id')

        patch_fip_get.assert_called_once_with('fip-id')
        patch_fip_alloc.assert_called_once_with(floatingip_id='fip-id')
        patch_fip_destroy.assert_called_once_with('fip-id')

    def test_delete_floatingip_with_reservations(self):
        fip_row = {
            'id': 'fip-id',
            'network_id': 'net-id',
            'subnet_id': 'subnet-id',
            'floating_ip_address': '172.24.4.100',
            'reservable': True
        }
        patch_fip_get = self.patch(db_api, 'floatingip_get')
        patch_fip_get.return_value = fip_row
        patch_fip_alloc = self.patch(db_api,
                                     'fip_allocation_get_all_by_values')
        patch_fip_alloc.return_value = [
            {
                'id': 'alloc-id1',
                'floatingip_id': 'fip-id',
                'reservation_id': 'reservations-id1'
            }
        ]
        fip_plugin = floatingip_plugin.FloatingIpPlugin()
        self.assertRaises(mgr_exceptions.CantDeleteFloatingIP,
                          fip_plugin.delete_floatingip,
                          'fip-id1')

    def test_delete_floatingip_with_no_exist(self):
        patch_fip_get = self.patch(db_api, 'floatingip_get')
        patch_fip_get.return_value = None

        fip_plugin = floatingip_plugin.FloatingIpPlugin()
        self.assertRaises(mgr_exceptions.FloatingIPNotFound,
                          fip_plugin.delete_floatingip,
                          'non-exists-id')

    def test_create_reservation_fips_available(self):
        fip_plugin = floatingip_plugin.FloatingIpPlugin()
        values = {
            'lease_id': '018c1b43-e69e-4aef-a543-09681539cf4c',
            'network_id': 'f548089e-fb3e-4013-a043-c5ed809c7a67',
            'start_date': datetime.datetime(2013, 12, 19, 20, 0),
            'end_date': datetime.datetime(2013, 12, 19, 21, 0),
            'resource_type': plugin.RESOURCE_TYPE,
            'amount': 2
        }
        matching_fips = self.patch(fip_plugin, '_matching_fips')
        matching_fips.return_value = ['fip1', 'fip2']
        fip_reservation_create = self.patch(self.db_api,
                                            'fip_reservation_create')
        fip_allocation_create = self.patch(
            self.db_api, 'fip_allocation_create')
        fip_plugin.reserve_resource(
            '441c1476-9f8f-4700-9f30-cd9b6fef3509',
            values)
        fip_values = {
            'reservation_id': '441c1476-9f8f-4700-9f30-cd9b6fef3509',
            'network_id': 'f548089e-fb3e-4013-a043-c5ed809c7a67',
            'amount': 2
        }
        fip_reservation_create.assert_called_once_with(fip_values)
        calls = [
            mock.call(
                {'floatingip_id': 'fip1',
                 'reservation_id': '441c1476-9f8f-4700-9f30-cd9b6fef3509',
                 }),
            mock.call(
                {'floatingip_id': 'fip2',
                 'reservation_id': '441c1476-9f8f-4700-9f30-cd9b6fef3509',
                 }),
        ]
        fip_allocation_create.assert_has_calls(calls)

    def test_create_reservation_fips_with_required(self):
        fip_plugin = floatingip_plugin.FloatingIpPlugin()
        values = {
            'lease_id': '018c1b43-e69e-4aef-a543-09681539cf4c',
            'network_id': 'f548089e-fb3e-4013-a043-c5ed809c7a67',
            'start_date': datetime.datetime(2013, 12, 19, 20, 0),
            'end_date': datetime.datetime(2013, 12, 19, 21, 0),
            'resource_type': plugin.RESOURCE_TYPE,
            'amount': 2,
            'required_floatingips': ['172.24.4.100']
        }
        matching_fips = self.patch(fip_plugin, '_matching_fips')
        matching_fips.return_value = ['fip1', 'fip2']
        fip_reservation_create = self.patch(self.db_api,
                                            'fip_reservation_create')
        fip_reservation_create.return_value = {'id': 'fip_resv_id1'}
        fip_allocation_create = self.patch(
            self.db_api, 'fip_allocation_create')
        required_addr_create = self.patch(self.db_api, 'required_fip_create')
        fip_plugin.reserve_resource(
            '441c1476-9f8f-4700-9f30-cd9b6fef3509',
            values)
        fip_values = {
            'reservation_id': '441c1476-9f8f-4700-9f30-cd9b6fef3509',
            'network_id': 'f548089e-fb3e-4013-a043-c5ed809c7a67',
            'amount': 2
        }
        fip_reservation_create.assert_called_once_with(fip_values)
        required_addr_create.assert_called_once_with(
            {
                'address': '172.24.4.100',
                'floatingip_reservation_id': 'fip_resv_id1'
            })
        calls = [
            mock.call(
                {'floatingip_id': 'fip1',
                 'reservation_id': '441c1476-9f8f-4700-9f30-cd9b6fef3509',
                 }),
            mock.call(
                {'floatingip_id': 'fip2',
                 'reservation_id': '441c1476-9f8f-4700-9f30-cd9b6fef3509',
                 }),
        ]
        fip_allocation_create.assert_has_calls(calls)

    def test_create_reservation_with_missing_param_network(self):
        values = {
            'lease_id': '018c1b43-e69e-4aef-a543-09681539cf4c',
            'amount': 2,
            'start_date': datetime.datetime(2017, 3, 1, 20, 0),
            'end_date': datetime.datetime(2017, 3, 2, 20, 0),
            'resource_type': plugin.RESOURCE_TYPE,
        }
        fip_plugin = floatingip_plugin.FloatingIpPlugin()
        self.assertRaises(
            mgr_exceptions.MissingParameter,
            fip_plugin.reserve_resource,
            '441c1476-9f8f-4700-9f30-cd9b6fef3509',
            values)

    def test_create_reservation_with_invalid_fip(self):
        values = {
            'lease_id': '018c1b43-e69e-4aef-a543-09681539cf4c',
            'network_id': 'a37a14f3-e3eb-4fe2-9e36-082b67f12ea0',
            'amount': 2,
            'required_floatingips': ['aaa.aaa.aaa.aaa'],
            'start_date': datetime.datetime(2017, 3, 1, 20, 0),
            'end_date': datetime.datetime(2017, 3, 2, 20, 0),
            'resource_type': plugin.RESOURCE_TYPE,
        }
        fip_plugin = floatingip_plugin.FloatingIpPlugin()
        self.assertRaises(
            mgr_exceptions.InvalidIPFormat,
            fip_plugin.reserve_resource,
            '441c1476-9f8f-4700-9f30-cd9b6fef3509',
            values)

    def test_create_reservation_required_bigger_than_amount(self):
        values = {
            'lease_id': '018c1b43-e69e-4aef-a543-09681539cf4c',
            'network_id': 'a37a14f3-e3eb-4fe2-9e36-082b67f12ea0',
            'amount': 1,
            'required_floatingips': ['172.24.4.100', '172.24.4.101'],
            'start_date': datetime.datetime(2017, 3, 1, 20, 0),
            'end_date': datetime.datetime(2017, 3, 2, 20, 0),
            'resource_type': plugin.RESOURCE_TYPE,
        }
        fip_plugin = floatingip_plugin.FloatingIpPlugin()
        self.assertRaises(
            mgr_exceptions.TooLongFloatingIPs,
            fip_plugin.reserve_resource,
            '441c1476-9f8f-4700-9f30-cd9b6fef3509',
            values)

    def test_update_pending_reservation_increase_amount_fips_available(self):
        fip_plugin = floatingip_plugin.FloatingIpPlugin()
        values = {
            'start_date': datetime.datetime(2013, 12, 19, 20, 0),
            'end_date': datetime.datetime(2013, 12, 19, 21, 0),
            'resource_type': plugin.RESOURCE_TYPE,
            'amount': 2,
        }
        lease_get = self.patch(self.db_api, 'lease_get')
        lease_get.return_value = {
            'id': '018c1b43-e69e-4aef-a543-09681539cf4c',
            'start_date': datetime.datetime(2013, 12, 19, 20, 0),
            'end_date': datetime.datetime(2013, 12, 19, 21, 0),
        }
        reservation_get = self.patch(self.db_api, 'reservation_get')
        reservation_get.return_value = {
            'id': '441c1476-9f8f-4700-9f30-cd9b6fef3509',
            'lease_id': '018c1b43-e69e-4aef-a543-09681539cf4c',
            'resource_id': 'fip-reservation-id-1',
            'resource_type': 'virtual:floatingip',
            'status': 'pending',
        }
        fip_allocation_get_all_by_values = self.patch(
            self.db_api, 'fip_allocation_get_all_by_values'
        )
        fip_allocation_get_all_by_values.return_value = [{
            'floatingip_id': 'fip1'
        }]
        fip_reservation_get = self.patch(self.db_api, 'fip_reservation_get')
        fip_reservation_get.return_value = {
            'id': 'fip_resv_id1',
            'amount': 1,
            'reservation_id': '441c1476-9f8f-4700-9f30-cd9b6fef3509',
            'network_id': 'f548089e-fb3e-4013-a043-c5ed809c7a67',
            'required_floatingips': [],
        }
        matching_fips = self.patch(fip_plugin, '_matching_fips')
        matching_fips.return_value = ['fip2']
        fip_reservation_update = self.patch(self.db_api,
                                            'fip_reservation_update')
        fip_allocation_create = self.patch(
            self.db_api, 'fip_allocation_create')
        fip_plugin.update_reservation(
            '441c1476-9f8f-4700-9f30-cd9b6fef3509',
            values)
        fip_reservation_update.assert_called_once_with(
            'fip_resv_id1', {'amount': 2})
        calls = [
            mock.call(
                {'floatingip_id': 'fip2',
                 'reservation_id': '441c1476-9f8f-4700-9f30-cd9b6fef3509',
                 })
        ]
        fip_allocation_create.assert_has_calls(calls)

    def test_update_active_reservation_increase_amount_fips_available(self):
        fip_plugin = floatingip_plugin.FloatingIpPlugin()
        values = {
            'start_date': datetime.datetime(2013, 12, 19, 20, 0),
            'end_date': datetime.datetime(2013, 12, 19, 21, 0),
            'resource_type': plugin.RESOURCE_TYPE,
            'amount': 2,
        }
        lease_get = self.patch(self.db_api, 'lease_get')
        lease_get.return_value = {
            'id': '018c1b43-e69e-4aef-a543-09681539cf4c',
            'start_date': datetime.datetime(2013, 12, 19, 20, 0),
            'end_date': datetime.datetime(2013, 12, 19, 21, 0),
        }
        reservation_get = self.patch(self.db_api, 'reservation_get')
        reservation_get.return_value = {
            'id': '441c1476-9f8f-4700-9f30-cd9b6fef3509',
            'lease_id': '018c1b43-e69e-4aef-a543-09681539cf4c',
            'resource_id': 'fip-reservation-id-1',
            'resource_type': 'virtual:floatingip',
            'status': 'active',
        }
        fip_allocation_get_all_by_values = self.patch(
            self.db_api, 'fip_allocation_get_all_by_values'
        )
        fip_allocation_get_all_by_values.return_value = [{
            'floatingip_id': 'fip1'
        }]
        fip_reservation_get = self.patch(self.db_api, 'fip_reservation_get')
        fip_reservation_get.return_value = {
            'id': 'fip_resv_id1',
            'amount': 1,
            'reservation_id': '441c1476-9f8f-4700-9f30-cd9b6fef3509',
            'network_id': 'f548089e-fb3e-4013-a043-c5ed809c7a67',
            'required_floatingips': [],
        }
        matching_fips = self.patch(fip_plugin, '_matching_fips')
        matching_fips.return_value = ['fip2']
        fip_reservation_update = self.patch(self.db_api,
                                            'fip_reservation_update')
        fip_get = self.patch(self.db_api, 'floatingip_get')
        fip_get.return_value = {
            'network_id': 'f548089e-fb3e-4013-a043-c5ed809c7a67',
            'subnet_id': 'subnet-id',
            'floating_ip_address': '172.2.24.100'
        }
        self.set_context(context.BlazarContext(project_id='fake-project-id'))
        m = mock.MagicMock()
        self.fip_pool.return_value = m
        fip_allocation_create = self.patch(
            self.db_api, 'fip_allocation_create')
        fip_allocation_destroy = self.patch(
            self.db_api, 'fip_allocation_destroy')
        fip_plugin.update_reservation(
            '441c1476-9f8f-4700-9f30-cd9b6fef3509',
            values)
        fip_reservation_update.assert_called_once_with(
            'fip_resv_id1', {'amount': 2})
        self.fip_pool.assert_called_once_with(
            'f548089e-fb3e-4013-a043-c5ed809c7a67')
        m.create_reserved_floatingip.assert_called_once_with(
            'subnet-id',
            '172.2.24.100',
            'fake-project-id',
            '441c1476-9f8f-4700-9f30-cd9b6fef3509')
        calls = [
            mock.call(
                {'floatingip_id': 'fip2',
                 'reservation_id': '441c1476-9f8f-4700-9f30-cd9b6fef3509',
                 })
        ]
        fip_allocation_create.assert_has_calls(calls)
        self.assertFalse(fip_allocation_destroy.called)

    def test_update_active_reservation_fip_creation_failure(self):
        fip_plugin = floatingip_plugin.FloatingIpPlugin()
        values = {
            'start_date': datetime.datetime(2013, 12, 19, 20, 0),
            'end_date': datetime.datetime(2013, 12, 19, 21, 0),
            'resource_type': plugin.RESOURCE_TYPE,
            'amount': 3,
        }
        lease_get = self.patch(self.db_api, 'lease_get')
        lease_get.return_value = {
            'id': '018c1b43-e69e-4aef-a543-09681539cf4c',
            'start_date': datetime.datetime(2013, 12, 19, 20, 0),
            'end_date': datetime.datetime(2013, 12, 19, 21, 0),
        }
        reservation_get = self.patch(self.db_api, 'reservation_get')
        reservation_get.return_value = {
            'id': '441c1476-9f8f-4700-9f30-cd9b6fef3509',
            'lease_id': '018c1b43-e69e-4aef-a543-09681539cf4c',
            'resource_id': 'fip-reservation-id-1',
            'resource_type': 'virtual:floatingip',
            'status': 'active',
        }
        fip_allocation_get_all_by_values = self.patch(
            self.db_api, 'fip_allocation_get_all_by_values'
        )
        fip_allocation_get_all_by_values.return_value = [{
            'floatingip_id': 'fip1'
        }]
        fip_reservation_get = self.patch(self.db_api, 'fip_reservation_get')
        fip_reservation_get.return_value = {
            'id': 'fip_resv_id1',
            'amount': 1,
            'reservation_id': '441c1476-9f8f-4700-9f30-cd9b6fef3509',
            'network_id': 'f548089e-fb3e-4013-a043-c5ed809c7a67',
            'required_floatingips': [],
        }
        matching_fips = self.patch(fip_plugin, '_matching_fips')
        matching_fips.return_value = ['fip2', 'fip3']
        fip_get = self.patch(self.db_api, 'floatingip_get')
        fip_get.side_effect = (
            {
                'network_id': 'f548089e-fb3e-4013-a043-c5ed809c7a67',
                'subnet_id': 'subnet-id',
                'floating_ip_address': '172.2.24.100'
            },
            {
                'network_id': 'f548089e-fb3e-4013-a043-c5ed809c7a67',
                'subnet_id': 'subnet-id',
                'floating_ip_address': '172.2.24.101'
            }
        )
        self.set_context(context.BlazarContext(project_id='fake-project-id'))
        m = mock.MagicMock()
        m.create_reserved_floatingip.side_effect = (None, Exception())
        self.fip_pool.return_value = m
        fip_allocation_create = self.patch(
            self.db_api, 'fip_allocation_create')
        fip_allocation_destroy = self.patch(
            self.db_api, 'fip_allocation_destroy')
        self.assertRaises(mgr_exceptions.NeutronClientError,
                          fip_plugin.update_reservation,
                          '441c1476-9f8f-4700-9f30-cd9b6fef3509', values)
        self.fip_pool.assert_called_once_with(
            'f548089e-fb3e-4013-a043-c5ed809c7a67')
        calls = [
            mock.call('subnet-id',
                      '172.2.24.100',
                      'fake-project-id',
                      '441c1476-9f8f-4700-9f30-cd9b6fef3509'),
            mock.call('subnet-id',
                      '172.2.24.101',
                      'fake-project-id',
                      '441c1476-9f8f-4700-9f30-cd9b6fef3509'),
        ]
        m.create_reserved_floatingip.assert_has_calls(calls)
        self.assertFalse(fip_allocation_create.called)
        self.assertFalse(fip_allocation_destroy.called)

    def test_update_reservation_increase_amount_fips_unavailable(self):
        fip_plugin = floatingip_plugin.FloatingIpPlugin()
        values = {
            'start_date': datetime.datetime(2013, 12, 19, 20, 0),
            'end_date': datetime.datetime(2013, 12, 19, 21, 0),
            'resource_type': plugin.RESOURCE_TYPE,
            'amount': 2,
        }
        lease_get = self.patch(self.db_api, 'lease_get')
        lease_get.return_value = {
            'id': '018c1b43-e69e-4aef-a543-09681539cf4c',
            'start_date': datetime.datetime(2013, 12, 19, 20, 0),
            'end_date': datetime.datetime(2013, 12, 19, 21, 0),
        }
        reservation_get = self.patch(self.db_api, 'reservation_get')
        reservation_get.return_value = {
            'id': '441c1476-9f8f-4700-9f30-cd9b6fef3509',
            'lease_id': '018c1b43-e69e-4aef-a543-09681539cf4c',
            'resource_id': 'fip-reservation-id-1',
            'resource_type': 'virtual:floatingip',
            'status': 'pending',
        }
        fip_allocation_get_all_by_values = self.patch(
            self.db_api, 'fip_allocation_get_all_by_values'
        )
        fip_allocation_get_all_by_values.return_value = [{
            'floatingip_id': 'fip1'
        }]
        fip_reservation_get = self.patch(self.db_api, 'fip_reservation_get')
        fip_reservation_get.return_value = {
            'id': 'fip_resv_id1',
            'amount': 1,
            'reservation_id': '441c1476-9f8f-4700-9f30-cd9b6fef3509',
            'network_id': 'f548089e-fb3e-4013-a043-c5ed809c7a67',
            'required_floatingips': [],
        }
        matching_fips = self.patch(fip_plugin, '_matching_fips')
        matching_fips.return_value = []
        self.assertRaises(mgr_exceptions.NotEnoughFloatingIPAvailable,
                          fip_plugin.update_reservation,
                          '441c1476-9f8f-4700-9f30-cd9b6fef3509', values)

    def test_update_reservation_decrease_amount(self):
        fip_plugin = floatingip_plugin.FloatingIpPlugin()
        values = {
            'start_date': datetime.datetime(2013, 12, 19, 20, 0),
            'end_date': datetime.datetime(2013, 12, 19, 21, 0),
            'resource_type': plugin.RESOURCE_TYPE,
            'amount': 1,
        }
        lease_get = self.patch(self.db_api, 'lease_get')
        lease_get.return_value = {
            'id': '018c1b43-e69e-4aef-a543-09681539cf4c',
            'start_date': datetime.datetime(2013, 12, 19, 20, 0),
            'end_date': datetime.datetime(2013, 12, 19, 21, 0),
        }
        reservation_get = self.patch(self.db_api, 'reservation_get')
        reservation_get.return_value = {
            'id': '441c1476-9f8f-4700-9f30-cd9b6fef3509',
            'lease_id': '018c1b43-e69e-4aef-a543-09681539cf4c',
            'resource_id': 'fip-reservation-id-1',
            'resource_type': 'virtual:floatingip',
            'status': 'pending',
        }
        fip_allocation_get_all_by_values = self.patch(
            self.db_api, 'fip_allocation_get_all_by_values'
        )
        fip_allocation_get_all_by_values.return_value = [
            {'id': 'fip_alloc_1', 'floatingip_id': 'fip1'},
            {'id': 'fip_alloc_2', 'floatingip_id': 'fip2'},
        ]
        fip_reservation_get = self.patch(self.db_api, 'fip_reservation_get')
        fip_reservation_get.return_value = {
            'id': 'fip_resv_id1',
            'amount': 2,
            'reservation_id': '441c1476-9f8f-4700-9f30-cd9b6fef3509',
            'network_id': 'f548089e-fb3e-4013-a043-c5ed809c7a67',
            'required_floatingips': [],
        }
        fip_allocation_destroy = self.patch(self.db_api,
                                            'fip_allocation_destroy')
        fip_reservation_update = self.patch(self.db_api,
                                            'fip_reservation_update')
        fip_plugin.update_reservation(
            '441c1476-9f8f-4700-9f30-cd9b6fef3509',
            values)
        fip_reservation_update.assert_called_once_with(
            'fip_resv_id1', {'amount': 1})
        calls = [
            mock.call('fip_alloc_1')
        ]
        fip_allocation_destroy.assert_has_calls(calls)

    def test_update_reservation_remove_required_fips(self):
        fip_plugin = floatingip_plugin.FloatingIpPlugin()
        values = {
            'start_date': datetime.datetime(2013, 12, 19, 20, 0),
            'end_date': datetime.datetime(2013, 12, 19, 21, 0),
            'resource_type': plugin.RESOURCE_TYPE,
            'required_floatingips': [],
        }
        lease_get = self.patch(self.db_api, 'lease_get')
        lease_get.return_value = {
            'id': '018c1b43-e69e-4aef-a543-09681539cf4c',
            'start_date': datetime.datetime(2013, 12, 19, 20, 0),
            'end_date': datetime.datetime(2013, 12, 19, 21, 0),
        }
        reservation_get = self.patch(self.db_api, 'reservation_get')
        reservation_get.return_value = {
            'id': '441c1476-9f8f-4700-9f30-cd9b6fef3509',
            'lease_id': '018c1b43-e69e-4aef-a543-09681539cf4c',
            'resource_id': 'fip-reservation-id-1',
            'resource_type': 'virtual:floatingip',
            'status': 'pending',
        }
        fip_allocation_get_all_by_values = self.patch(
            self.db_api, 'fip_allocation_get_all_by_values'
        )
        fip_allocation_get_all_by_values.return_value = [{
            'floatingip_id': 'fip1'
        }]
        fip_reservation_get = self.patch(self.db_api, 'fip_reservation_get')
        fip_reservation_get.return_value = {
            'id': 'fip_resv_id1',
            'amount': 1,
            'reservation_id': '441c1476-9f8f-4700-9f30-cd9b6fef3509',
            'network_id': 'f548089e-fb3e-4013-a043-c5ed809c7a67',
            'required_floatingips': ['172.24.4.100']
        }
        required_fip_destroy_by_fip_reservation_id = self.patch(
            self.db_api, 'required_fip_destroy_by_fip_reservation_id')
        fip_plugin.update_reservation(
            '441c1476-9f8f-4700-9f30-cd9b6fef3509',
            values)
        calls = [mock.call('fip_resv_id1')]
        required_fip_destroy_by_fip_reservation_id.assert_has_calls(calls)

    def test_update_reservation_change_required_fips(self):
        fip_plugin = floatingip_plugin.FloatingIpPlugin()
        values = {
            'start_date': datetime.datetime(2013, 12, 19, 20, 0),
            'end_date': datetime.datetime(2013, 12, 19, 21, 0),
            'resource_type': plugin.RESOURCE_TYPE,
            'required_floatingips': ['172.24.4.101'],
        }
        lease_get = self.patch(self.db_api, 'lease_get')
        lease_get.return_value = {
            'id': '018c1b43-e69e-4aef-a543-09681539cf4c',
            'start_date': datetime.datetime(2013, 12, 19, 20, 0),
            'end_date': datetime.datetime(2013, 12, 19, 21, 0),
        }
        reservation_get = self.patch(self.db_api, 'reservation_get')
        reservation_get.return_value = {
            'id': '441c1476-9f8f-4700-9f30-cd9b6fef3509',
            'lease_id': '018c1b43-e69e-4aef-a543-09681539cf4c',
            'resource_id': 'fip-reservation-id-1',
            'resource_type': 'virtual:floatingip',
            'status': 'pending',
        }
        fip_reservation_get = self.patch(self.db_api, 'fip_reservation_get')
        fip_reservation_get.return_value = {
            'id': 'fip_resv_id1',
            'amount': 1,
            'reservation_id': '441c1476-9f8f-4700-9f30-cd9b6fef3509',
            'network_id': 'f548089e-fb3e-4013-a043-c5ed809c7a67',
            'required_floatingips': ['172.24.4.100']
        }
        self.assertRaises(mgr_exceptions.CantUpdateFloatingIPReservation,
                          fip_plugin.update_reservation,
                          '441c1476-9f8f-4700-9f30-cd9b6fef3509', values)

    def test_update_reservation_change_network_id(self):
        fip_plugin = floatingip_plugin.FloatingIpPlugin()
        values = {
            'start_date': datetime.datetime(2013, 12, 19, 20, 0),
            'end_date': datetime.datetime(2013, 12, 19, 21, 0),
            'resource_type': plugin.RESOURCE_TYPE,
            'network_id': 'new-network-id',
        }
        lease_get = self.patch(self.db_api, 'lease_get')
        lease_get.return_value = {
            'id': '018c1b43-e69e-4aef-a543-09681539cf4c',
            'start_date': datetime.datetime(2013, 12, 19, 20, 0),
            'end_date': datetime.datetime(2013, 12, 19, 21, 0),
        }
        reservation_get = self.patch(self.db_api, 'reservation_get')
        reservation_get.return_value = {
            'id': '441c1476-9f8f-4700-9f30-cd9b6fef3509',
            'lease_id': '018c1b43-e69e-4aef-a543-09681539cf4c',
            'resource_id': 'fip-reservation-id-1',
            'resource_type': 'virtual:floatingip',
            'status': 'pending',
        }
        fip_reservation_get = self.patch(self.db_api, 'fip_reservation_get')
        fip_reservation_get.return_value = {
            'id': 'fip_resv_id1',
            'amount': 1,
            'reservation_id': '441c1476-9f8f-4700-9f30-cd9b6fef3509',
            'network_id': 'f548089e-fb3e-4013-a043-c5ed809c7a67',
        }
        self.assertRaises(mgr_exceptions.CantUpdateFloatingIPReservation,
                          fip_plugin.update_reservation,
                          '441c1476-9f8f-4700-9f30-cd9b6fef3509', values)

    def test_on_start(self):
        fip_reservation_get = self.patch(self.db_api, 'fip_reservation_get')
        fip_reservation_get.return_value = {
            'reservation_id': 'reservation-id1',
            'network_id': 'network-id1'
        }
        fip_allocation_get_all_by_values = self.patch(
            self.db_api, 'fip_allocation_get_all_by_values'
        )
        fip_allocation_get_all_by_values.return_value = [{
            'floatingip_id': 'fip-id',
        }]
        fip_get = self.patch(self.db_api, 'floatingip_get')
        fip_get.return_value = {
            'network_id': 'net-id',
            'subnet_id': 'subnet-id',
            'floating_ip_address': '172.2.24.100'
        }
        self.set_context(context.BlazarContext(project_id='fake-project-id'))
        m = mock.MagicMock()
        self.fip_pool.return_value = m

        fip_plugin = floatingip_plugin.FloatingIpPlugin()
        fip_plugin.on_start('resource-id1')

        self.fip_pool.assert_called_once_with('network-id1')
        m.create_reserved_floatingip.assert_called_once_with('subnet-id',
                                                             '172.2.24.100',
                                                             'fake-project-id',
                                                             'reservation-id1')

    def test_on_end(self):
        fip_reservation_get = self.patch(self.db_api, 'fip_reservation_get')
        fip_reservation_get.return_value = {
            'reservation_id': 'reservation-id1',
            'network_id': 'network-id1'
        }
        fip_allocation_get_all_by_values = self.patch(
            self.db_api, 'fip_allocation_get_all_by_values'
        )
        fip_allocation_get_all_by_values.return_value = [{
            'floatingip_id': 'fip-id',
        }]
        fip_get = self.patch(self.db_api, 'floatingip_get')
        fip_get.return_value = {
            'network_id': 'net-id',
            'subnet_id': 'subnet-id',
            'floating_ip_address': '172.2.24.100'
        }
        self.set_context(context.BlazarContext(project_id='fake-project-id'))
        m = mock.MagicMock()
        self.fip_pool.return_value = m

        fip_plugin = floatingip_plugin.FloatingIpPlugin()
        fip_plugin.on_end('resource-id1')

        self.fip_pool.assert_called_once_with('network-id1')
        m.delete_reserved_floatingip.assert_called_once_with('172.2.24.100')

    def test_matching_fips_not_allocated_fips(self):
        def fip_allocation_get_all_by_values(**kwargs):
            if kwargs['floatingip_id'] == 'fip1':
                return [{'id': 'allocation-id1'}]

        fip_plugin = floatingip_plugin.FloatingIpPlugin()
        fip_get = self.patch(self.db_api, 'reservable_fip_get_all_by_queries')
        fip_get.return_value = [
            {'id': 'fip1', 'floating_ip_address': '172.24.4.101'},
            {'id': 'fip2', 'floating_ip_address': '172.24.4.102'},
            {'id': 'fip3', 'floating_ip_address': '172.24.4.103'},
        ]
        fip_get = self.patch(self.db_api, 'fip_allocation_get_all_by_values')
        fip_get.side_effect = fip_allocation_get_all_by_values
        fip_get = self.patch(self.db_utils, 'get_free_periods')
        fip_get.return_value = [
            (datetime.datetime(2013, 12, 19, 20, 0),
             datetime.datetime(2013, 12, 19, 21, 0)),
        ]
        result = fip_plugin._matching_fips(
            'network-id', [], 2,
            datetime.datetime(2013, 12, 19, 20, 0),
            datetime.datetime(2013, 12, 19, 21, 0))
        self.assertEqual(['fip2', 'fip3'], result)

    def test_matching_fips_allocated_fips(self):
        def fip_allocation_get_all_by_values(**kwargs):
            return [{'id': kwargs['floatingip_id']}]

        fip_plugin = floatingip_plugin.FloatingIpPlugin()
        fip_get = self.patch(self.db_api, 'reservable_fip_get_all_by_queries')
        fip_get.return_value = [
            {'id': 'fip1', 'floating_ip_address': '172.24.4.101'},
            {'id': 'fip2', 'floating_ip_address': '172.24.4.102'},
            {'id': 'fip3', 'floating_ip_address': '172.24.4.103'},
        ]
        fip_get = self.patch(self.db_api, 'fip_allocation_get_all_by_values')
        fip_get.side_effect = fip_allocation_get_all_by_values
        fip_get = self.patch(self.db_utils, 'get_free_periods')
        fip_get.return_value = [
            (datetime.datetime(2013, 12, 19, 20, 0),
             datetime.datetime(2013, 12, 19, 21, 0)),
        ]
        result = fip_plugin._matching_fips(
            'network-id', [], 3,
            datetime.datetime(2013, 12, 19, 20, 0),
            datetime.datetime(2013, 12, 19, 21, 0))
        self.assertEqual(['fip1', 'fip2', 'fip3'], result)

    def test_matching_fips_allocated_fips_with_required(self):
        def fip_allocation_get_all_by_values(**kwargs):
            if kwargs['floatingip_id'] == 'fip1':
                return [{'id': 'allocation-id1'}]

        fip_plugin = floatingip_plugin.FloatingIpPlugin()
        fip_get = self.patch(self.db_api, 'reservable_fip_get_all_by_queries')
        fip_get.return_value = [
            {'id': 'fip1', 'floating_ip_address': '172.24.4.101'},
            {'id': 'fip2', 'floating_ip_address': '172.24.4.102'},
            {'id': 'fip3', 'floating_ip_address': '172.24.4.103'},
            {'id': 'fip4', 'floating_ip_address': '172.24.4.104'},
        ]
        fip_get = self.patch(self.db_api, 'fip_allocation_get_all_by_values')
        fip_get.side_effect = fip_allocation_get_all_by_values
        fip_get = self.patch(self.db_utils, 'get_free_periods')
        fip_get.return_value = [
            (datetime.datetime(2013, 12, 19, 20, 0),
             datetime.datetime(2013, 12, 19, 21, 0)),
        ]
        result = fip_plugin._matching_fips(
            'network-id', ['172.24.4.102'], 4,
            datetime.datetime(2013, 12, 19, 20, 0),
            datetime.datetime(2013, 12, 19, 21, 0))
        # The order must be 1. required fips, 2. non-allocated fips,
        # then 3. allocated fips
        self.assertEqual(['fip2', 'fip3', 'fip4', 'fip1'], result)

    def test_matching_fips_allocated_fips_with_cleaning_time(self):
        def fip_allocation_get_all_by_values(**kwargs):
            return [{'id': kwargs['floatingip_id']}]

        self.cfg.CONF.set_override('cleaning_time', '5')
        fip_get = self.patch(
            self.db_api,
            'reservable_fip_get_all_by_queries')
        fip_get.return_value = [
            {'id': 'fip1', 'floating_ip_address': '172.24.4.101'},
            {'id': 'fip2', 'floating_ip_address': '172.24.4.102'},
            {'id': 'fip3', 'floating_ip_address': '172.24.4.103'},
        ]
        fip_get = self.patch(
            self.db_api,
            'fip_allocation_get_all_by_values')
        fip_get.side_effect = fip_allocation_get_all_by_values
        fip_get = self.patch(
            self.db_utils,
            'get_free_periods')
        fip_get.return_value = [
            (datetime.datetime(2013, 12, 19, 20, 0)
             - datetime.timedelta(minutes=5),
             datetime.datetime(2013, 12, 19, 21, 0)
             + datetime.timedelta(minutes=5))
        ]
        fip_plugin = floatingip_plugin.FloatingIpPlugin()
        result = fip_plugin._matching_fips(
            'network-id', [], 3,
            datetime.datetime(2013, 12, 19, 20, 0),
            datetime.datetime(2013, 12, 19, 21, 0))
        self.assertEqual(['fip1', 'fip2', 'fip3'], result)
        start_mergin = (datetime.datetime(2013, 12, 19, 20, 0)
                        - datetime.timedelta(minutes=5))
        end_mergin = (datetime.datetime(2013, 12, 19, 21, 0)
                      + datetime.timedelta(minutes=5))
        calls = [mock.call(fip, start_mergin, end_mergin,
                           end_mergin - start_mergin,
                           resource_type='floatingip')
                 for fip in ['fip1', 'fip2', 'fip3']]
        fip_get.assert_has_calls(calls)

    def test_matching_fips_not_matching(self):
        fip_plugin = floatingip_plugin.FloatingIpPlugin()
        fip_get = self.patch(
            self.db_api,
            'reservable_fip_get_all_by_queries')
        fip_get.return_value = []
        self.assertRaises(mgr_exceptions.NotEnoughFloatingIPAvailable,
                          fip_plugin._matching_fips,
                          'network-id', [], 2,
                          datetime.datetime(2013, 12, 19, 20, 0),
                          datetime.datetime(2013, 12, 19, 21, 0))
