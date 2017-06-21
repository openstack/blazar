# Copyright (c) 2017 NTT.
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

from blazar.db import api as db_api
from blazar.db import utils as db_utils
from blazar import exceptions
from blazar.manager import exceptions as mgr_exceptions
from blazar.plugins.instances import instance_plugin
from blazar.plugins import oshosts
from blazar import tests


class TestVirtualInstancePlugin(tests.TestCase):

    def setUp(self):
        super(TestVirtualInstancePlugin, self).setUp()

    def get_input_values(self, vcpus, memory, disk, amount, affinity,
                         start, end, lease_id):
        return {'vcpus': vcpus, 'memory_mb': memory, 'disk_gb': disk,
                'amount': amount, 'affinity': affinity, 'start_date': start,
                'end_date': end, 'lease_id': lease_id}

    def generate_host_info(self, id, vcpus, memory, disk):
        return {'id': id, 'vcpus': vcpus,
                'memory_mb': memory, 'local_gb': disk}

    def test_reserve_resource(self):
        plugin = instance_plugin.VirtualInstancePlugin()
        mock_pickup_hosts = self.patch(plugin, 'pickup_hosts')
        mock_pickup_hosts.return_value = ['host1', 'host2']

        mock_inst_create = self.patch(db_api, 'instance_reservation_create')
        mock_inst_create.return_value = {'id': 'instance-reservation-id1'}

        mock_alloc_create = self.patch(db_api, 'host_allocation_create')

        inputs = self.get_input_values(2, 4018, 10, 1, False,
                                       '2030-01-01 08:00', '2030-01-01 08:00',
                                       'lease-1')

        expected_ret = 'instance-reservation-id1'

        ret = plugin.reserve_resource('res_id1', inputs)

        self.assertEqual(expected_ret, ret)
        mock_pickup_hosts.assert_called_once_with(inputs['vcpus'],
                                                  inputs['memory_mb'],
                                                  inputs['disk_gb'],
                                                  inputs['amount'],
                                                  inputs['start_date'],
                                                  inputs['end_date'])

        mock_alloc_create.assert_any_call({'compute_host_id': 'host1',
                                           'reservation_id': 'res_id1'})
        mock_alloc_create.assert_any_call({'compute_host_id': 'host2',
                                           'reservation_id': 'res_id1'})

    def test_error_with_affinity(self):
        plugin = instance_plugin.VirtualInstancePlugin()
        inputs = self.get_input_values(2, 4018, 10, 1, True,
                                       '2030-01-01 08:00', '2030-01-01 08:00',
                                       'lease-1')
        self.assertRaises(exceptions.BlazarException, plugin.reserve_resource,
                          'reservation_id', inputs)

    def test_pickup_host_from_reserved_hosts(self):
        def fake_max_usages(host, reservations):
            if host['id'] == 'host-1':
                return 4, 4096, 2000
            else:
                return 0, 0, 0

        def fake_get_reservation_by_host(host_id, start, end):
            return [
                {'id': '1', 'resource_type': instance_plugin.RESOURCE_TYPE},
                {'id': '2', 'resource_type': instance_plugin.RESOURCE_TYPE}]

        plugin = instance_plugin.VirtualInstancePlugin()

        mock_host_get_query = self.patch(db_api, 'host_get_all_by_queries')
        hosts_list = [self.generate_host_info('host-1', 4, 4096, 1000),
                      self.generate_host_info('host-2', 4, 4096, 1000),
                      self.generate_host_info('host-3', 4, 4096, 1000)]
        mock_host_get_query.return_value = hosts_list

        mock_get_reservations = self.patch(db_utils,
                                           'get_reservations_by_host_id')

        mock_get_reservations.side_effect = fake_get_reservation_by_host
        plugin.max_usages = fake_max_usages
        expected = ['host-2', 'host-3']
        ret = plugin.pickup_hosts(1, 1024, 20, 2,
                                  '2030-01-01 08:00', '2030-01-01 12:00')

        self.assertEqual(expected, ret)
        expected_query = ['vcpus >= 1', 'memory_mb >= 1024', 'local_gb >= 20']
        mock_host_get_query.assert_called_once_with(expected_query)

    def test_pickup_host_from_free_hosts(self):
        def fake_get_reservation_by_host(host_id, start, end):
            return []

        plugin = instance_plugin.VirtualInstancePlugin()

        mock_host_get_query = self.patch(db_api, 'host_get_all_by_queries')
        hosts_list = [self.generate_host_info('host-1', 4, 4096, 1000),
                      self.generate_host_info('host-2', 4, 4096, 1000),
                      self.generate_host_info('host-3', 4, 4096, 1000)]
        mock_host_get_query.return_value = hosts_list

        mock_get_reservations = self.patch(db_utils,
                                           'get_reservations_by_host_id')

        mock_get_reservations.side_effect = fake_get_reservation_by_host

        expected = ['host-1', 'host-2']
        ret = plugin.pickup_hosts(1, 1024, 20, 2,
                                  '2030-01-01 08:00', '2030-01-01 12:00')

        self.assertEqual(expected, ret)
        expected_query = ['vcpus >= 1', 'memory_mb >= 1024', 'local_gb >= 20']
        mock_host_get_query.assert_called_once_with(expected_query)

    def test_pickup_host_from_free_and_reserved_host(self):
        def fake_get_reservation_by_host(host_id, start, end):
            if host_id in ['host-1', 'host-3']:
                return [
                    {'id': '1',
                     'resource_type': instance_plugin.RESOURCE_TYPE},
                    {'id': '2',
                     'resource_type': instance_plugin.RESOURCE_TYPE}
                    ]
            else:
                return []

        plugin = instance_plugin.VirtualInstancePlugin()

        mock_host_get_query = self.patch(db_api, 'host_get_all_by_queries')
        hosts_list = [self.generate_host_info('host-1', 4, 4096, 1000),
                      self.generate_host_info('host-2', 4, 4096, 1000),
                      self.generate_host_info('host-3', 4, 4096, 1000)]
        mock_host_get_query.return_value = hosts_list

        mock_get_reservations = self.patch(db_utils,
                                           'get_reservations_by_host_id')

        mock_get_reservations.side_effect = fake_get_reservation_by_host

        mock_max_usages = self.patch(plugin, 'max_usages')
        mock_max_usages.return_value = (0, 0, 0)

        expected = ['host-1', 'host-3']
        ret = plugin.pickup_hosts(1, 1024, 20, 2,
                                  '2030-01-01 08:00', '2030-01-01 12:00')

        self.assertEqual(expected, ret)
        expected_query = ['vcpus >= 1', 'memory_mb >= 1024', 'local_gb >= 20']
        mock_host_get_query.assert_called_once_with(expected_query)

    def test_pickup_host_from_less_hosts(self):
        def fake_get_reservation_by_host(host_id, start, end):
            if host_id in ['host-1', 'host-3']:
                return [
                    {'id': '1',
                     'resource_type': oshosts.RESOURCE_TYPE},
                    {'id': '2',
                     'resource_type': instance_plugin.RESOURCE_TYPE}
                    ]
            else:
                return [
                    {'id': '1',
                     'resource_type': instance_plugin.RESOURCE_TYPE},
                    {'id': '2',
                     'resource_type': instance_plugin.RESOURCE_TYPE}
                    ]

        plugin = instance_plugin.VirtualInstancePlugin()

        mock_host_get_query = self.patch(db_api, 'host_get_all_by_queries')
        hosts_list = [self.generate_host_info('host-1', 4, 4096, 1000),
                      self.generate_host_info('host-2', 4, 4096, 1000),
                      self.generate_host_info('host-3', 4, 4096, 1000)]
        mock_host_get_query.return_value = hosts_list

        mock_get_reservations = self.patch(db_utils,
                                           'get_reservations_by_host_id')

        mock_get_reservations.side_effect = fake_get_reservation_by_host
        mock_max_usages = self.patch(plugin, 'max_usages')
        mock_max_usages.return_value = (1, 1024, 100)

        self.assertRaises(mgr_exceptions.HostNotFound, plugin.pickup_hosts,
                          1, 1024, 20, 2,
                          '2030-01-01 08:00', '2030-01-01 12:00')
