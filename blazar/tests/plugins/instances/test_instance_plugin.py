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
import six

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
        return six.text_type(str(uuid.uuid4()))

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
        mock_pickup_hosts.return_value = {'added': ['host1', 'host2'],
                                          'removed': []}

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
        pickup_hosts_value = {}
        for key in ['vcpus', 'memory_mb', 'disk_gb', 'amount', 'affinity',
                    'lease_id', 'start_date', 'end_date']:
            pickup_hosts_value[key] = inputs[key]
        mock_pickup_hosts.assert_called_once_with('res_id1',
                                                  pickup_hosts_value)

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
        self.assertRaises(exceptions.BlazarException,
                          plugin.update_reservation, 'reservation_id', inputs)

    def test_filter_hosts_by_reservation_with_exclude(self):
        def fake_get_reservation_by_host(host_id, start, end):
            if host_id == 'host-1':
                return [
                    {'id': '1',
                     'resource_type': instance_plugin.RESOURCE_TYPE}]
            else:
                return []

        hosts_list = [self.generate_host_info('host-1', 4, 4096, 1000),
                      self.generate_host_info('host-2', 4, 4096, 1000),
                      self.generate_host_info('host-3', 4, 4096, 1000)]
        mock_get_reservations = self.patch(db_utils,
                                           'get_reservations_by_host_id')

        mock_get_reservations.side_effect = fake_get_reservation_by_host
        free = [{'host': hosts_list[0], 'reservations': None},
                {'host': hosts_list[1], 'reservations': None},
                {'host': hosts_list[2], 'reservations': None}]
        non_free = []

        plugin = instance_plugin.VirtualInstancePlugin()
        ret = plugin.filter_hosts_by_reservation(hosts_list,
                                                 '2030-01-01 08:00',
                                                 '2030-01-01 12:00', ['1'])
        self.assertEqual(free, ret[0])
        self.assertEqual(non_free, ret[1])

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

        mock_host_allocation_get = self.patch(
            db_api, 'host_allocation_get_all_by_values')
        mock_host_allocation_get.return_value = []

        mock_host_get_query = self.patch(db_api,
                                         'reservable_host_get_all_by_queries')
        hosts_list = [self.generate_host_info('host-1', 4, 4096, 1000),
                      self.generate_host_info('host-2', 4, 4096, 1000),
                      self.generate_host_info('host-3', 4, 4096, 1000)]
        mock_host_get_query.return_value = hosts_list

        mock_get_reservations = self.patch(db_utils,
                                           'get_reservations_by_host_id')

        mock_get_reservations.side_effect = fake_get_reservation_by_host
        plugin.max_usages = fake_max_usages

        mock_reservation_get = self.patch(db_api, 'reservation_get')
        mock_reservation_get.return_value = {
            'status': 'pending'
            }

        values = {
            'vcpus': 1,
            'memory_mb': 1024,
            'disk_gb': 20,
            'amount': 2,
            'start_date': '2030-01-01 08:00',
            'end_date': '2030-01-01 12:00'
            }
        expected = {'added': set(['host-2', 'host-3']), 'removed': set()}
        ret = plugin.pickup_hosts('reservation-id1', values)

        self.assertEqual(expected, ret)
        expected_query = ['vcpus >= 1', 'memory_mb >= 1024', 'local_gb >= 20']
        mock_host_get_query.assert_called_once_with(expected_query)

    def test_pickup_host_from_free_hosts(self):
        def fake_get_reservation_by_host(host_id, start, end):
            return []

        plugin = instance_plugin.VirtualInstancePlugin()

        mock_host_allocation_get = self.patch(
            db_api, 'host_allocation_get_all_by_values')
        mock_host_allocation_get.return_value = []

        mock_host_get_query = self.patch(db_api,
                                         'reservable_host_get_all_by_queries')
        hosts_list = [self.generate_host_info('host-1', 4, 4096, 1000),
                      self.generate_host_info('host-2', 4, 4096, 1000),
                      self.generate_host_info('host-3', 4, 4096, 1000)]
        mock_host_get_query.return_value = hosts_list

        mock_get_reservations = self.patch(db_utils,
                                           'get_reservations_by_host_id')
        mock_get_reservations.side_effect = fake_get_reservation_by_host

        mock_reservation_get = self.patch(db_api, 'reservation_get')
        mock_reservation_get.return_value = {
            'status': 'pending'
            }

        values = {
            'vcpus': 1,
            'memory_mb': 1024,
            'disk_gb': 20,
            'amount': 2,
            'start_date': '2030-01-01 08:00',
            'end_date': '2030-01-01 12:00'
            }
        expected = {'added': set(['host-1', 'host-2']), 'removed': set()}
        ret = plugin.pickup_hosts('reservation-id1', values)

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

        mock_host_allocation_get = self.patch(
            db_api, 'host_allocation_get_all_by_values')
        mock_host_allocation_get.return_value = []

        mock_host_get_query = self.patch(db_api,
                                         'reservable_host_get_all_by_queries')
        hosts_list = [self.generate_host_info('host-1', 4, 4096, 1000),
                      self.generate_host_info('host-2', 4, 4096, 1000),
                      self.generate_host_info('host-3', 4, 4096, 1000)]
        mock_host_get_query.return_value = hosts_list

        mock_get_reservations = self.patch(db_utils,
                                           'get_reservations_by_host_id')

        mock_get_reservations.side_effect = fake_get_reservation_by_host

        mock_max_usages = self.patch(plugin, 'max_usages')
        mock_max_usages.return_value = (0, 0, 0)

        mock_reservation_get = self.patch(db_api, 'reservation_get')
        mock_reservation_get.return_value = {
            'status': 'pending'
            }

        params = {
            'vcpus': 1,
            'memory_mb': 1024,
            'disk_gb': 20,
            'amount': 2,
            'start_date': '2030-01-01 08:00',
            'end_date': '2030-01-01 12:00'
            }

        expected = {'added': set(['host-1', 'host-3']), 'removed': set()}
        ret = plugin.pickup_hosts('reservation-id1', params)

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

        mock_host_get_query = self.patch(db_api,
                                         'reservable_host_get_all_by_queries')
        hosts_list = [self.generate_host_info('host-1', 4, 4096, 1000),
                      self.generate_host_info('host-2', 4, 4096, 1000),
                      self.generate_host_info('host-3', 4, 4096, 1000)]
        mock_host_get_query.return_value = hosts_list

        mock_get_reservations = self.patch(db_utils,
                                           'get_reservations_by_host_id')

        mock_get_reservations.side_effect = fake_get_reservation_by_host
        mock_host_allocation_get = self.patch(
            db_api, 'host_allocation_get_all_by_values')
        mock_host_allocation_get.return_value = []

        mock_max_usages = self.patch(plugin, 'max_usages')
        mock_max_usages.return_value = (1, 1024, 100)

        values = {
            'vcpus': 1,
            'memory_mb': 1024,
            'disk_gb': 20,
            'amount': 2,
            'start_date': '2030-01-01 08:00',
            'end_date': '2030-01-01 12:00'
            }

        hosts = plugin.pickup_hosts('reservation-id1', values)
        self.assertTrue((len(hosts['added']) - len(hosts['removed']))
                        < values['amount'])

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

    def test_pickup_hosts_for_update(self):
        reservation = {'id': 'reservation-id1', 'status': 'pending'}
        plugin = instance_plugin.VirtualInstancePlugin()

        mock_alloc_get = self.patch(db_api,
                                    'host_allocation_get_all_by_values')
        mock_alloc_get.return_value = [
            {'compute_host_id': 'host-id1'}, {'compute_host_id': 'host-id2'},
            {'compute_host_id': 'host-id3'}]
        mock_query_available = self.patch(plugin, 'query_available_hosts')
        mock_query_available.return_value = [
            self.generate_host_info('host-id2', 2, 2024, 1000),
            self.generate_host_info('host-id3', 2, 2024, 1000),
            self.generate_host_info('host-id4', 2, 2024, 1000)]

        mock_reservation_get = self.patch(db_api, 'reservation_get')
        mock_reservation_get.return_value = reservation

        # case: new amount is less than old amount
        values = self.get_input_values(1, 1024, 10, 1, False,
                                       '2020-07-01 10:00', '2020-07-01 11:00',
                                       'lease-1')
        expect = {'added': set(),
                  'removed': set(['host-id1', 'host-id2', 'host-id3'])}
        ret = plugin.pickup_hosts(reservation['id'], values)
        self.assertEqual(expect['added'], ret['added'])
        self.assertTrue(len(ret['removed']) == 2)
        self.assertTrue(all([h in expect['removed'] for h in ret['removed']]))

        # case: new amount is same but change allocations
        values = self.get_input_values(1, 1024, 10, 3, False,
                                       '2020-07-01 10:00', '2020-07-01 11:00',
                                       'lease-1')
        expect = {'added': set(['host-id4']), 'removed': set(['host-id1'])}
        ret = plugin.pickup_hosts(reservation['id'], values)
        self.assertEqual(expect['added'], ret['added'])
        self.assertEqual(expect['removed'], ret['removed'])

        # case: new amount is greater than old amount
        mock_query_available.return_value = [
            self.generate_host_info('host-id1', 2, 2024, 1000),
            self.generate_host_info('host-id2', 2, 2024, 1000),
            self.generate_host_info('host-id3', 2, 2024, 1000),
            self.generate_host_info('host-id4', 2, 2024, 1000)]

        values = self.get_input_values(1, 1024, 10, 4, False,
                                       '2020-07-01 10:00', '2020-07-01 11:00',
                                       'lease-1')
        expect = {'added': set(['host-id4']), 'removed': set()}
        ret = plugin.pickup_hosts(reservation['id'], values)
        self.assertEqual(expect['added'], ret['added'])
        self.assertEqual(expect['removed'], ret['removed'])

    def test_update_resources(self):
        reservation = {
            'id': 'reservation-id1',
            'status': 'pending',
            'vcpus': 2, 'memory_mb': 1024,
            'disk_gb': 10, 'server_group_id': 'group-1'}
        mock_reservation_get = self.patch(db_api, 'reservation_get')
        mock_reservation_get.return_value = reservation
        fake_client = mock.MagicMock()
        mock_nova_client = self.patch(nova, 'NovaClientWrapper')
        mock_nova_client.return_value = fake_client
        self.set_context(context.BlazarContext(project_id='fake-project',
                                               auth_token='fake-token'))
        plugin = instance_plugin.VirtualInstancePlugin()
        fake_flavor = mock.MagicMock(method='set_keys',
                                     flavorid='reservation-id1')
        mock_nova = mock.MagicMock()
        type(plugin).nova = mock_nova
        mock_nova.nova.flavors.create.return_value = fake_flavor

        plugin.update_resources('reservation-id1')

        mock_reservation_get.assert_called_once_with('reservation-id1')
        mock_nova.nova.flavors.delete.assert_called_once_with(
            'reservation-id1')
        mock_nova.nova.flavors.create.assert_called_once_with(
            flavorid='reservation-id1',
            name='reservation:reservation-id1',
            vcpus=2, ram=1024, disk=10, is_public=False)
        fake_flavor.set_keys.assert_called_once_with(
            {'aggregate_instance_extra_specs:reservation': 'reservation-id1',
             'affinity_id': 'group-1'})

    def test_update_resources_in_active(self):
        def fake_host_get(host_id):
            return {'service_name': 'host' + host_id[-1]}

        reservation = {
            'id': 'reservation-id1',
            'status': 'active',
            'vcpus': 2, 'memory_mb': 1024,
            'disk_gb': 10, 'aggregate_id': 'aggregate-1'}

        mock_reservation_get = self.patch(db_api, 'reservation_get')
        mock_reservation_get.return_value = reservation
        self.set_context(context.BlazarContext(project_id='fake-project'))
        plugin = instance_plugin.VirtualInstancePlugin()

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

        plugin.update_resources('reservation-id1')

        mock_reservation_get.assert_called_once_with('reservation-id1')
        for i in range(3):
            fake_pool.add_computehost.assert_any_call('aggregate-1',
                                                      'host' + str(i + 1),
                                                      stay_in=True)

    def test_update_reservation(self):
        plugin = instance_plugin.VirtualInstancePlugin()

        old_reservation = {
            'id': 'reservation-id1',
            'status': 'pending',
            'lease_id': 'lease-id1',
            'resource_id': 'instance-reservation-id1',
            'vcpus': 2, 'memory_mb': 1024, 'disk_gb': 100,
            'amount': 2, 'affinity': False}
        mock_reservation_get = self.patch(db_api, 'reservation_get')
        mock_reservation_get.return_value = old_reservation

        mock_lease_get = self.patch(db_api, 'lease_get')
        mock_lease_get.return_value = {'start_date': '2020-07-07 18:00',
                                       'end_date': '2020-07-07 19:00'}

        mock_pickup_hosts = self.patch(plugin, 'pickup_hosts')
        mock_pickup_hosts.return_value = {
            'added': set(['host-id1']), 'removed': set(['host-id2'])}

        mock_inst_update = self.patch(db_api, 'instance_reservation_update')
        mock_inst_update.return_value = {
            'vcpus': 4, 'memory_mb': 1024, 'disk_gb': 200,
            'amount': 2, 'affinity': False}

        mock_update_alloc = self.patch(plugin, 'update_host_allocations')

        mock_update_resource = self.patch(plugin, 'update_resources')

        new_values = {'vcpus': 4, 'disk_gb': 200}
        plugin.update_reservation('reservation-id1', new_values)

        mock_pickup_hosts.assert_called_once_with(
            'reservation-id1',
            {'vcpus': 4, 'memory_mb': 1024, 'disk_gb': 200,
             'amount': 2, 'affinity': False})
        mock_inst_update.assert_called_once_with(
            'instance-reservation-id1',
            {'vcpus': 4, 'memory_mb': 1024, 'disk_gb': 200,
             'amount': 2, 'affinity': False})
        mock_update_alloc.assert_called_once_with(set(['host-id1']),
                                                  set(['host-id2']),
                                                  'reservation-id1')
        mock_update_resource.assert_called_once_with('reservation-id1')

    def test_update_flavor_in_active(self):
        plugin = instance_plugin.VirtualInstancePlugin()

        old_reservation = {
            'id': 'reservation-id1',
            'status': 'active',
            'lease_id': 'lease-id1',
            'resource_id': 'instance-reservation-id1',
            'vcpus': 2, 'memory_mb': 1024, 'disk_gb': 100,
            'amount': 2, 'affinity': False}
        mock_reservation_get = self.patch(db_api, 'reservation_get')
        mock_reservation_get.return_value = old_reservation

        mock_lease_get = self.patch(db_api, 'lease_get')
        mock_lease_get.return_value = {'start_date': '2020-07-07 18:00',
                                       'end_date': '2020-07-07 19:00'}

        new_values = {'vcpus': 4, 'disk_gb': 200}
        self.assertRaises(mgr_exceptions.InvalidStateUpdate,
                          plugin.update_reservation,
                          'reservation-id1', new_values)

    def test_update_host_allocations(self):
        mock_alloc_get = self.patch(db_api,
                                    'host_allocation_get_all_by_values')
        mock_alloc_get.return_value = [
            {'id': 'id10', 'compute_host_id': 'host-id10'},
            {'id': 'id11', 'compute_host_id': 'host-id11'},
            {'id': 'id12', 'compute_host_id': 'host-id12'}]

        mock_alloc_destroy = self.patch(db_api, 'host_allocation_destroy')
        mock_alloc_create = self.patch(db_api, 'host_allocation_create')

        plugin = instance_plugin.VirtualInstancePlugin()

        added_host = ['host-id1', 'host-id2']
        removed_host = ['host-id10', 'host-id11']

        removed_calls = [mock.call('id10'), mock.call('id11')]
        added_calls = [
            mock.call({'compute_host_id': 'host-id1',
                       'reservation_id': 'reservation-id1'}),
            mock.call({'compute_host_id': 'host-id2',
                       'reservation_id': 'reservation-id1'})]

        plugin.update_host_allocations(added_host, removed_host,
                                       'reservation-id1')

        mock_alloc_destroy.assert_has_calls(removed_calls)
        mock_alloc_create.assert_has_calls(added_calls)

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

    def test_heal_reservations_before_start_and_resources_changed(self):
        plugin = instance_plugin.VirtualInstancePlugin()
        failed_hosts = [{'id': 1}]
        new_host_ids = [2]
        alloc_get = self.patch(db_api,
                               'host_allocation_get_all_by_values')
        alloc_get.return_value = [{'id': 'alloc-1',
                                   'compute_host_id': '1',
                                   'reservation_id': 'rsrv-1'}]
        alloc_destroy = self.patch(db_api, 'host_allocation_destroy')
        reservation_get = self.patch(db_api, 'reservation_get')
        reservation_get.return_value = {
            'id': 'rsrv-1',
            'resource_type': instance_plugin.RESOURCE_TYPE,
            'lease_id': 'lease-1',
            'status': 'pending',
            'vcpus': 2,
            'memory_mb': 1024,
            'disk_gb': 256,
            'aggregate_id': 'agg-1',
            'affinity': False,
            'amount': 3}
        host_get = self.patch(db_api, 'host_get')
        host_get.return_value = {'service_name': 'compute'}
        mock_pool = self.patch(nova, 'ReservationPool')
        mock_pool.return_value = mock.MagicMock()
        lease_get = self.patch(db_api, 'lease_get')
        lease_get.return_value = {
            'name': 'lease-name',
            'start_date': datetime.datetime(2020, 1, 1, 12, 00),
            'end_date': datetime.datetime(2020, 1, 2, 12, 00)}
        pickup_hosts = self.patch(plugin, 'pickup_hosts')
        pickup_hosts.return_value = {'added': new_host_ids, 'removed': []}
        alloc_update = self.patch(db_api, 'host_allocation_update')

        with mock.patch.object(datetime, 'datetime',
                               mock.Mock(wraps=datetime.datetime)) as patched:
            patched.utcnow.return_value = datetime.datetime(2020, 1, 1,
                                                            11, 00)
            result = plugin.heal_reservations(failed_hosts)
        alloc_destroy.assert_not_called()
        pickup_hosts.assert_called_once()
        alloc_update.assert_called_once_with('alloc-1',
                                             {'compute_host_id': 2})
        self.assertEqual({}, result)

    def test_heal_reservations_before_start_and_missing_resources(self):
        plugin = instance_plugin.VirtualInstancePlugin()
        failed_hosts = [{'id': 1}]
        new_host_ids = []
        alloc_get = self.patch(db_api,
                               'host_allocation_get_all_by_values')
        alloc_get.return_value = [{'id': 'alloc-1',
                                   'compute_host_id': '1',
                                   'reservation_id': 'rsrv-1'}]
        alloc_destroy = self.patch(db_api, 'host_allocation_destroy')
        reservation_get = self.patch(db_api, 'reservation_get')
        reservation_get.return_value = {
            'id': 'rsrv-1',
            'resource_type': instance_plugin.RESOURCE_TYPE,
            'lease_id': 'lease-1',
            'status': 'pending',
            'vcpus': 2,
            'memory_mb': 1024,
            'disk_gb': 256,
            'aggregate_id': 'agg-1',
            'affinity': False,
            'amount': 3}
        host_get = self.patch(db_api, 'host_get')
        host_get.return_value = {'service_name': 'compute'}
        mock_pool = self.patch(nova, 'ReservationPool')
        mock_pool.return_value = mock.MagicMock()
        lease_get = self.patch(db_api, 'lease_get')
        lease_get.return_value = {
            'name': 'lease-name',
            'start_date': datetime.datetime(2020, 1, 1, 12, 00),
            'end_date': datetime.datetime(2020, 1, 2, 12, 00)}
        pickup_hosts = self.patch(plugin, 'pickup_hosts')
        pickup_hosts.return_value = {'added': new_host_ids, 'removed': []}
        alloc_update = self.patch(db_api, 'host_allocation_update')

        with mock.patch.object(datetime, 'datetime',
                               mock.Mock(wraps=datetime.datetime)) as patched:
            patched.utcnow.return_value = datetime.datetime(2020, 1, 1,
                                                            11, 00)
            result = plugin.heal_reservations(failed_hosts)
        alloc_destroy.assert_called_once_with('alloc-1')
        pickup_hosts.assert_called_once()
        alloc_update.assert_not_called()
        self.assertEqual({'rsrv-1': {'missing_resources': True}}, result)

    def test_heal_active_reservations_and_resources_changed(self):
        plugin = instance_plugin.VirtualInstancePlugin()
        failed_hosts = [{'id': 1}]
        new_host_ids = [2]
        alloc_get = self.patch(db_api,
                               'host_allocation_get_all_by_values')
        alloc_get.return_value = [{'id': 'alloc-1',
                                   'compute_host_id': '1',
                                   'reservation_id': 'rsrv-1'}]
        alloc_destroy = self.patch(db_api, 'host_allocation_destroy')
        reservation_get = self.patch(db_api, 'reservation_get')
        reservation_get.return_value = {
            'id': 'rsrv-1',
            'resource_type': instance_plugin.RESOURCE_TYPE,
            'lease_id': 'lease-1',
            'status': 'active',
            'vcpus': 2,
            'memory_mb': 1024,
            'disk_gb': 256,
            'aggregate_id': 'agg-1',
            'affinity': False,
            'amount': 3}
        host_get = self.patch(db_api, 'host_get')
        host_get.return_value = {'service_name': 'compute'}
        fake_pool = mock.MagicMock()
        mock_pool = self.patch(nova, 'ReservationPool')
        mock_pool.return_value = fake_pool
        lease_get = self.patch(db_api, 'lease_get')
        lease_get.return_value = {
            'name': 'lease-name',
            'start_date': datetime.datetime(2020, 1, 1, 12, 00),
            'end_date': datetime.datetime(2020, 1, 2, 12, 00)}
        pickup_hosts = self.patch(plugin, 'pickup_hosts')
        pickup_hosts.return_value = {'added': new_host_ids, 'removed': []}
        alloc_update = self.patch(db_api, 'host_allocation_update')

        with mock.patch.object(datetime, 'datetime',
                               mock.Mock(wraps=datetime.datetime)) as patched:
            patched.utcnow.return_value = datetime.datetime(2020, 1, 1,
                                                            13, 00)
            result = plugin.heal_reservations(failed_hosts)
        alloc_destroy.assert_not_called()
        pickup_hosts.assert_called_once()
        alloc_update.assert_called_once_with('alloc-1',
                                             {'compute_host_id': 2})
        fake_pool.add_computehost.assert_called_once_with('agg-1',
                                                          'compute',
                                                          stay_in=True)
        self.assertEqual({'rsrv-1': {'resources_changed': True}}, result)

    def test_heal_active_reservations_and_missing_resources(self):
        plugin = instance_plugin.VirtualInstancePlugin()
        failed_hosts = [{'id': 1}]
        new_host_ids = []
        alloc_get = self.patch(db_api,
                               'host_allocation_get_all_by_values')
        alloc_get.return_value = [{'id': 'alloc-1',
                                   'compute_host_id': '1',
                                   'reservation_id': 'rsrv-1'}]
        alloc_destroy = self.patch(db_api, 'host_allocation_destroy')
        reservation_get = self.patch(db_api, 'reservation_get')
        reservation_get.return_value = {
            'id': 'rsrv-1',
            'resource_type': instance_plugin.RESOURCE_TYPE,
            'lease_id': 'lease-1',
            'status': 'active',
            'vcpus': 2,
            'memory_mb': 1024,
            'disk_gb': 256,
            'aggregate_id': 'agg-1',
            'affinity': False,
            'amount': 3}
        host_get = self.patch(db_api, 'host_get')
        host_get.return_value = {'service_name': 'compute'}
        fake_pool = mock.MagicMock()
        mock_pool = self.patch(nova, 'ReservationPool')
        mock_pool.return_value = fake_pool
        lease_get = self.patch(db_api, 'lease_get')
        lease_get.return_value = {
            'name': 'lease-name',
            'start_date': datetime.datetime(2020, 1, 1, 12, 00),
            'end_date': datetime.datetime(2020, 1, 2, 12, 00)}
        pickup_hosts = self.patch(plugin, 'pickup_hosts')
        pickup_hosts.return_value = {'added': new_host_ids, 'removed': []}
        alloc_update = self.patch(db_api, 'host_allocation_update')

        with mock.patch.object(datetime, 'datetime',
                               mock.Mock(wraps=datetime.datetime)) as patched:
            patched.utcnow.return_value = datetime.datetime(2020, 1, 1,
                                                            13, 00)
            result = plugin.heal_reservations(failed_hosts)
        alloc_destroy.assert_called_once_with('alloc-1')
        pickup_hosts.assert_called_once()
        alloc_update.assert_not_called()
        self.assertEqual({'rsrv-1': {'missing_resources': True}}, result)
