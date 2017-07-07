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

import datetime
import uuid

import mock

from blazar import context
from blazar.db import api as db_api
from blazar.db import utils as db_utils
from blazar import exceptions
from blazar.manager import exceptions as mgr_exceptions
from blazar.plugins.instances import instance_plugin
from blazar.plugins import oshosts
from blazar import tests
from blazar.utils.openstack import nova


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

    def generate_event(self, id, lease_id, event_type, time, status='UNDONE'):
        return {
            'id': id,
            'lease_id': lease_id,
            'event_type': event_type,
            'time': time,
            'status': status
            }

    def get_uuid(self):
        return unicode(str(uuid.uuid4()))

    def generate_basic_events(self, lease_id, start, before_end, end):
        return [
            self.generate_event(self.get_uuid(), lease_id, 'start_lease',
                                datetime.datetime.strptime(start,
                                                           '%Y-%m-%d %H:%M')),
            self.generate_event(self.get_uuid(), lease_id, 'before_end_lease',
                                datetime.datetime.strptime(before_end,
                                                           '%Y-%m-%d %H:%M')),
            self.generate_event(self.get_uuid(), lease_id, 'end_lease',
                                datetime.datetime.strptime(end,
                                                           '%Y-%m-%d %H:%M')),
            ]

    def test_reserve_resource(self):
        plugin = instance_plugin.VirtualInstancePlugin()
        mock_pickup_hosts = self.patch(plugin, 'pickup_hosts')
        mock_pickup_hosts.return_value = ['host1', 'host2']

        mock_inst_create = self.patch(db_api, 'instance_reservation_create')
        fake_instance_reservation = {'id': 'instance-reservation-id1'}
        mock_inst_create.return_value = fake_instance_reservation

        mock_alloc_create = self.patch(db_api, 'host_allocation_create')

        mock_create_resources = self.patch(plugin, '_create_resources')
        mock_flavor = mock.MagicMock(id=1)
        mock_group = mock.MagicMock(id=2)
        mock_pool = mock.MagicMock(id=3)
        mock_create_resources.return_value = (mock_flavor,
                                              mock_group, mock_pool)

        mock_inst_update = self.patch(db_api, 'instance_reservation_update')

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
        mock_create_resources.assert_called_once_with(
            fake_instance_reservation)
        mock_inst_update.assert_called_once_with('instance-reservation-id1',
                                                 {'flavor_id': 1,
                                                  'server_group_id': 2,
                                                  'aggregate_id': 3})

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

    def test_max_usage_with_serial_reservation(self):
        def fake_event_get(sort_key, sort_dir, filters):
            if filters['lease_id'] == 'lease-1':
                return self.generate_basic_events('lease-1',
                                                  '2030-01-01 08:00',
                                                  '2030-01-01 10:00',
                                                  '2030-01-01 11:00')
            elif filters['lease_id'] == 'lease-2':
                return self.generate_basic_events('lease-2',
                                                  '2030-01-01 12:00',
                                                  '2030-01-01 13:00',
                                                  '2030-01-01 14:00')

        plugin = instance_plugin.VirtualInstancePlugin()
        reservations = [
            {
                'lease_id': 'lease-1',
                'instance_reservations': {
                    'vcpus': 2, 'memory_mb': 3072, 'disk_gb': 20}},
            {
                'lease_id': 'lease-2',
                'instance_reservations': {
                    'vcpus': 3, 'memory_mb': 2048, 'disk_gb': 30}}
            ]

        mock_event_get = self.patch(db_api, 'event_get_all_sorted_by_filters')
        mock_event_get.side_effect = fake_event_get

        expected = (3, 3072, 30)
        ret = plugin.max_usages('fake-host', reservations)

        self.assertEqual(expected, ret)

    def test_max_usage_with_parallel_reservation(self):
        def fake_event_get(sort_key, sort_dir, filters):
            if filters['lease_id'] == 'lease-1':
                return self.generate_basic_events('lease-1',
                                                  '2030-01-01 08:00',
                                                  '2030-01-01 10:00',
                                                  '2030-01-01 11:00')
            elif filters['lease_id'] == 'lease-2':
                return self.generate_basic_events('lease-2',
                                                  '2030-01-01 10:00',
                                                  '2030-01-01 13:00',
                                                  '2030-01-01 14:00')

        plugin = instance_plugin.VirtualInstancePlugin()
        reservations = [
            {
                'lease_id': 'lease-1',
                'instance_reservations': {
                    'vcpus': 2, 'memory_mb': 3072, 'disk_gb': 20}},
            {
                'lease_id': 'lease-2',
                'instance_reservations': {
                    'vcpus': 3, 'memory_mb': 2048, 'disk_gb': 30}},
            ]

        mock_event_get = self.patch(db_api, 'event_get_all_sorted_by_filters')
        mock_event_get.side_effect = fake_event_get

        expected = (5, 5120, 50)
        ret = plugin.max_usages('fake-host', reservations)

        self.assertEqual(expected, ret)

    def test_max_usage_with_multi_reservation(self):
        def fake_event_get(sort_key, sort_dir, filters):
            if filters['lease_id'] == 'lease-1':
                return self.generate_basic_events('lease-1',
                                                  '2030-01-01 08:00',
                                                  '2030-01-01 10:00',
                                                  '2030-01-01 11:00')

        plugin = instance_plugin.VirtualInstancePlugin()
        reservations = [
            {
                'lease_id': 'lease-1',
                'instance_reservations': {
                    'vcpus': 2, 'memory_mb': 3072, 'disk_gb': 20}},
            {
                'lease_id': 'lease-1',
                'instance_reservations': {
                    'vcpus': 3, 'memory_mb': 2048, 'disk_gb': 30}},
            ]

        mock_event_get = self.patch(db_api, 'event_get_all_sorted_by_filters')
        mock_event_get.side_effect = fake_event_get

        expected = (5, 5120, 50)
        ret = plugin.max_usages('fake-host', reservations)

        self.assertEqual(expected, ret)

    def test_max_usage_with_decrease_reservation(self):
        def fake_event_get(sort_key, sort_dir, filters):
            if filters['lease_id'] == 'lease-1':
                return self.generate_basic_events('lease-1',
                                                  '2030-01-01 08:00',
                                                  '2030-01-01 10:00',
                                                  '2030-01-01 11:00')
            elif filters['lease_id'] == 'lease-2':
                return self.generate_basic_events('lease-2',
                                                  '2030-01-01 10:00',
                                                  '2030-01-01 13:00',
                                                  '2030-01-01 14:00')
            elif filters['lease_id'] == 'lease-3':
                return self.generate_basic_events('lease-3',
                                                  '2030-01-01 15:00',
                                                  '2030-01-01 16:00',
                                                  '2030-01-01 17:00')

        plugin = instance_plugin.VirtualInstancePlugin()
        reservations = [
            {
                'lease_id': 'lease-1',
                'instance_reservations': {
                    'vcpus': 2, 'memory_mb': 3072, 'disk_gb': 20}},
            {
                'lease_id': 'lease-2',
                'instance_reservations': {
                    'vcpus': 1, 'memory_mb': 1024, 'disk_gb': 10}},
            {
                'lease_id': 'lease-3',
                'instance_reservations': {
                    'vcpus': 4, 'memory_mb': 2048, 'disk_gb': 40
                    }},
            ]

        mock_event_get = self.patch(db_api, 'event_get_all_sorted_by_filters')
        mock_event_get.side_effect = fake_event_get

        expected = (4, 4096, 40)
        ret = plugin.max_usages('fake-host', reservations)

        self.assertEqual(expected, ret)

    def test_create_resources(self):
        instance_reservation = {
            'reservation_id': 'reservation-id1',
            'vcpus': 2,
            'memory_mb': 1024,
            'disk_gb': 20,
            'affinity': False
            }

        plugin = instance_plugin.VirtualInstancePlugin()

        fake_client = mock.MagicMock()
        mock_nova_client = self.patch(nova, 'NovaClientWrapper')
        mock_nova_client.return_value = fake_client
        fake_server_group = mock.MagicMock(id='server_group_id1')
        fake_client.nova.server_groups.create.return_value = \
            fake_server_group

        self.set_context(context.BlazarContext(project_id='fake-project',
                                               auth_token='fake-token'))
        fake_flavor = mock.MagicMock(method='set_keys',
                                     flavorid='reservation-id1')
        mock_nova = mock.MagicMock()
        type(plugin).nova = mock_nova
        mock_nova.nova.flavors.create.return_value = fake_flavor

        fake_pool = mock.MagicMock(id='pool-id1')
        fake_agg = mock.MagicMock()
        fake_pool.create.return_value = fake_agg
        mock_pool = self.patch(nova, 'ReservationPool')
        mock_pool.return_value = fake_pool

        expected = (fake_flavor, fake_server_group, fake_agg)

        ret = plugin._create_resources(instance_reservation)

        self.assertEqual(expected, ret)

        fake_client.nova.server_groups.create.assert_called_once_with(
            'reservation:reservation-id1', 'anti-affinity')
        mock_nova.nova.flavors.create.assert_called_once_with(
            flavorid='reservation-id1',
            name='reservation:reservation-id1',
            vcpus=2, ram=1024, disk=20, is_public=False)
        fake_flavor.set_keys.assert_called_once_with(
            {'aggregate_instance_extra_specs:reservation': 'reservation-id1',
             'affinity_id': 'server_group_id1'})
        fake_pool.create.assert_called_once_with(
            name='reservation-id1',
            metadata={'reservation': 'reservation-id1',
                      'filter_tenant_id': 'fake-project',
                      'affinity_id': 'server_group_id1'})

    def test_on_start(self):
        def fake_host_get(host_id):
            return {'service_name': 'host' + host_id[-1]}

        self.set_context(context.BlazarContext(project_id='fake-project'))
        plugin = instance_plugin.VirtualInstancePlugin()

        mock_inst_get = self.patch(db_api, 'instance_reservation_get')
        mock_inst_get.return_value = {'reservation_id': 'reservation-id1',
                                      'aggregate_id': 'aggregate-id1'}

        mock_nova = mock.MagicMock()
        type(plugin).nova = mock_nova

        fake_pool = mock.MagicMock()
        mock_pool = self.patch(nova, 'ReservationPool')
        mock_pool.return_value = fake_pool

        mock_alloc_get = self.patch(db_api,
                                    'host_allocation_get_all_by_values')
        mock_alloc_get.return_value = [
            {'compute_host_id': 'host-id1'}, {'compute_host_id': 'host-id2'},
            {'compute_host_id': 'host-id3'}]

        mock_host_get = self.patch(db_api, 'host_get')
        mock_host_get.side_effect = fake_host_get

        plugin.on_start('resource-id1')

        mock_nova.flavor_access.add_tenant_access.assert_called_once_with(
            'reservation-id1', 'fake-project')
        for i in range(3):
            fake_pool.add_computehost.assert_any_call('aggregate-id1',
                                                      'host' + str(i + 1),
                                                      stay_in=True)

    def test_on_end(self):
        self.set_context(context.BlazarContext(project_id='fake-project-id'))

        plugin = instance_plugin.VirtualInstancePlugin()

        fake_instance_reservation = {'reservation_id': 'reservation-id1'}
        mock_inst_get = self.patch(db_api, 'instance_reservation_get')
        mock_inst_get.return_value = fake_instance_reservation

        mock_alloc_get = self.patch(db_api,
                                    'host_allocation_get_all_by_values')
        mock_alloc_get.return_value = [{'id': 'host-alloc-id1'},
                                       {'id': 'host-alloc-id2'}]

        self.patch(db_api, 'host_allocation_destroy')

        fake_servers = [mock.MagicMock(method='delete') for i in range(5)]
        mock_nova = mock.MagicMock()
        type(plugin).nova = mock_nova
        mock_nova.servers.list.return_value = fake_servers

        mock_cleanup_resources = self.patch(plugin, 'cleanup_resources')

        plugin.on_end('resource-id1')

        mock_nova.flavor_access.remove_tenant_access.assert_called_once_with(
            'reservation-id1', 'fake-project-id')

        mock_nova.servers.list.assert_called_once_with(
            search_opts={'flavor': 'reservation-id1', 'all_tenants': 1},
            detailed=False)
        for fake in fake_servers:
            fake.delete.assert_called_once()
        mock_cleanup_resources.assert_called_once_with(
            fake_instance_reservation)
