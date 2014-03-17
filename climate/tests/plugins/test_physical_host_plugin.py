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

import datetime
import mock
import testtools
import uuid

from climate import context

from climate.db import api as db_api
from climate.db import exceptions as db_exceptions
from climate.db import utils as db_utils
from climate.manager import exceptions as manager_exceptions
from climate.manager import service
from climate.plugins import oshosts as plugin
from climate.plugins.oshosts import host_plugin
from climate.plugins.oshosts import nova_inventory
from climate.plugins.oshosts import reservation_pool as rp
from climate import tests
from novaclient import client as nova_client


class AggregateFake(object):

    def __init__(self, i, name, hosts):
        self.id = i
        self.name = name
        self.hosts = hosts


class PhysicalHostPlugingSetupOnlyTestCase(tests.TestCase):

    def setUp(self):
        super(PhysicalHostPlugingSetupOnlyTestCase, self).setUp()
        self.context = context
        self.patch(self.context, 'ClimateContext')
        self.host_plugin = host_plugin
        self.fake_phys_plugin = self.host_plugin.PhysicalHostPlugin()
        self.rp = rp
        self.nova_inventory = nova_inventory
        self.rp_create = self.patch(self.rp.ReservationPool, 'create')
        self.db_api = db_api
        self.db_host_extra_capability_get_all_per_host = (
            self.patch(self.db_api, 'host_extra_capability_get_all_per_host'))

    def test_setup(self):
        pool = self.patch(self.rp.ReservationPool, '__init__')
        pool.return_value = None
        inventory = self.patch(self.nova_inventory.NovaInventory, '__init__')
        inventory.return_value = None
        self.fake_phys_plugin.setup(None)
        pool.assert_called_once_with()
        inventory.assert_called_once_with()

    def test__get_extra_capabilities_with_values(self):
        self.db_host_extra_capability_get_all_per_host.return_value = [
            {'id': 1,
             'capability_name': 'foo',
             'capability_value': 'bar',
             'other': 'value',
             'computehost_id': 1
             },
            {'id': 2,
             'capability_name': 'buzz',
             'capability_value': 'word',
             'computehost_id': 1
             }]
        res = self.fake_phys_plugin._get_extra_capabilities(1)
        self.assertEqual({'foo': 'bar', 'buzz': 'word'}, res)

    def test__get_extra_capabilities_with_no_capabilities(self):
        self.db_host_extra_capability_get_all_per_host.return_value = []
        res = self.fake_phys_plugin._get_extra_capabilities(1)
        self.assertEqual({}, res)


class PhysicalHostPluginTestCase(tests.TestCase):

    def setUp(self):
        super(PhysicalHostPluginTestCase, self).setUp()

        self.context = context
        self.patch(self.context, 'ClimateContext')

        self.nova_client = nova_client
        self.nova = self.patch(self.nova_client, 'Client').return_value

        self.service = service
        self.manager = self.service.ManagerService()

        self.fake_host_id = '1'
        self.fake_host = {
            'id': self.fake_host_id,
            'hypervisor_hostname': 'foo',
            'vcpus': 4,
            'cpu_info': 'foo',
            'hypervisor_type': 'xen',
            'hypervisor_version': 1,
            'memory_mb': 8192,
            'local_gb': 10,
        }

        self.host_plugin = host_plugin
        self.fake_phys_plugin = self.host_plugin.PhysicalHostPlugin()
        self.db_api = db_api
        self.db_utils = db_utils

        self.db_host_get = self.patch(self.db_api, 'host_get')
        self.db_host_get.return_value = self.fake_host
        self.db_host_list = self.patch(self.db_api, 'host_list')
        self.db_host_create = self.patch(self.db_api, 'host_create')
        self.db_host_update = self.patch(self.db_api, 'host_update')
        self.db_host_destroy = self.patch(self.db_api, 'host_destroy')

        self.db_host_extra_capability_get_all_per_host = self.patch(
            self.db_api, 'host_extra_capability_get_all_per_host')

        self.db_host_extra_capability_get_all_per_name = self.patch(
            self.db_api, 'host_extra_capability_get_all_per_name')

        self.db_host_extra_capability_create = self.patch(
            self.db_api, 'host_extra_capability_create')

        self.db_host_extra_capability_update = self.patch(
            self.db_api, 'host_extra_capability_update')

        self.rp = rp
        self.nova_inventory = nova_inventory
        self.rp_create = self.patch(self.rp.ReservationPool, 'create')
        self.patch(self.rp.ReservationPool, 'get_aggregate_from_name_or_id')
        self.add_compute_host = self.patch(self.rp.ReservationPool,
                                           'add_computehost')
        self.remove_compute_host = self.patch(self.rp.ReservationPool,
                                              'remove_computehost')
        self.get_host_details = self.patch(self.nova_inventory.NovaInventory,
                                           'get_host_details')
        self.get_host_details.return_value = self.fake_host
        self.get_servers_per_host = self.patch(
            self.nova_inventory.NovaInventory, 'get_servers_per_host')
        self.get_servers_per_host.return_value = None
        self.get_extra_capabilities = self.patch(
            self.fake_phys_plugin, '_get_extra_capabilities')

        self.get_extra_capabilities.return_value = {
            'foo': 'bar',
            'buzz': 'word',
        }
        self.fake_phys_plugin.setup(None)

    def test_get_host(self):
        host = self.fake_phys_plugin.get_computehost(self.fake_host_id)
        self.db_host_get.assert_called_once_with('1')
        expected = self.fake_host.copy()
        expected.update({'foo': 'bar', 'buzz': 'word'})
        self.assertEqual(host, expected)

    def test_get_host_without_extracapabilities(self):
        self.get_extra_capabilities.return_value = {}
        host = self.fake_phys_plugin.get_computehost(self.fake_host_id)
        self.db_host_get.assert_called_once_with('1')
        self.assertEqual(host, self.fake_host)

    @testtools.skip('incorrect decorator')
    def test_list_hosts(self):
        self.fake_phys_plugin.list_computehosts()
        self.db_host_list.assert_called_once_with()
        del self.service_utils

    def test_create_host_without_extra_capabilities(self):
        self.get_extra_capabilities.return_value = {}
        host = self.fake_phys_plugin.create_computehost(self.fake_host)
        self.db_host_create.assert_called_once_with(self.fake_host)
        self.assertEqual(host, self.fake_host)

    def test_create_host_with_extra_capabilities(self):
        fake_host = self.fake_host.copy()
        fake_host.update({'foo': 'bar'})
        # NOTE(sbauza): 'id' will be pop'd, we need to keep track of it
        fake_request = fake_host.copy()
        fake_capa = {'computehost_id': '1',
                     'capability_name': 'foo',
                     'capability_value': 'bar',
                     }
        self.get_extra_capabilities.return_value = {'foo': 'bar'}
        self.db_host_create.return_value = self.fake_host
        host = self.fake_phys_plugin.create_computehost(fake_request)
        self.db_host_create.assert_called_once_with(self.fake_host)
        self.db_host_extra_capability_create.assert_called_once_with(fake_capa)
        self.assertEqual(host, fake_host)

    def test_create_host_with_invalid_values(self):
        self.assertRaises(manager_exceptions.InvalidHost,
                          self.fake_phys_plugin.create_computehost, {})

    def test_create_host_with_existing_vms(self):
        self.get_servers_per_host.return_value = ['server1', 'server2']
        self.assertRaises(manager_exceptions.HostHavingServers,
                          self.fake_phys_plugin.create_computehost,
                          self.fake_host)

    def test_create_host_issuing_rollback(self):
        def fake_db_host_create(*args, **kwargs):
            raise db_exceptions.ClimateDBException
        self.db_host_create.side_effect = fake_db_host_create
        host = self.fake_phys_plugin.create_computehost(self.fake_host)
        self.assertEqual(None, host)

    def test_create_host_having_issue_when_storing_extra_capability(self):
        def fake_db_host_extra_capability_create(*args, **kwargs):
            raise db_exceptions.ClimateDBException
        fake_host = self.fake_host.copy()
        fake_host.update({'foo': 'bar'})
        fake_request = fake_host.copy()
        self.get_extra_capabilities.return_value = {'foo': 'bar'}
        self.db_host_create.return_value = self.fake_host
        self.db_host_extra_capability_create.side_effect = \
            fake_db_host_extra_capability_create
        self.assertRaises(manager_exceptions.CantAddExtraCapability,
                          self.fake_phys_plugin.create_computehost,
                          fake_request)

    def test_update_host(self):
        host_values = {'foo': 'baz'}

        self.db_host_extra_capability_get_all_per_name.return_value = [
            {'id': '1',
             'capability_name': 'foo',
             'capability_value': 'bar'
             },
        ]
        self.fake_phys_plugin.update_computehost(self.fake_host_id,
                                                 host_values)
        self.db_host_extra_capability_update.assert_called_once_with(
            '1', {'capability_name': 'foo', 'capability_value': 'baz'})

    def test_update_host_having_issue_when_storing_extra_capability(self):
        def fake_db_host_extra_capability_update(*args, **kwargs):
            raise RuntimeError
        host_values = {'foo': 'baz'}
        self.db_host_extra_capability_get_all_per_name.return_value = [
            {'id': '1',
             'capability_name': 'foo',
             'capability_value': 'bar'
             },
        ]
        self.db_host_extra_capability_update.side_effect = \
            fake_db_host_extra_capability_update
        self.assertRaises(manager_exceptions.CantAddExtraCapability,
                          self.fake_phys_plugin.update_computehost,
                          self.fake_host_id, host_values)

    def test_delete_host(self):
        self.fake_phys_plugin.delete_computehost(self.fake_host_id)

        self.db_host_destroy.assert_called_once_with(self.fake_host_id)

    def test_delete_host_having_vms(self):
        self.get_servers_per_host.return_value = ['server1', 'server2']
        self.assertRaises(manager_exceptions.HostHavingServers,
                          self.fake_phys_plugin.delete_computehost,
                          self.fake_host_id)

    def test_delete_host_not_existing_in_db(self):
        self.db_host_get.return_value = None
        self.assertRaises(manager_exceptions.HostNotFound,
                          self.fake_phys_plugin.delete_computehost,
                          self.fake_host_id)

    def test_delete_host_issuing_rollback(self):
        def fake_db_host_destroy(*args, **kwargs):
            raise db_exceptions.ClimateDBException
        self.db_host_destroy.side_effect = fake_db_host_destroy
        self.assertRaises(manager_exceptions.CantRemoveHost,
                          self.fake_phys_plugin.delete_computehost,
                          self.fake_host_id)

    def test_create_reservation_no_hosts_available(self):
        values = {
            'lease_id': u'018c1b43-e69e-4aef-a543-09681539cf4c',
            'min': u'1',
            'max': u'1',
            'hypervisor_properties': '["=", "$memory_mb", "256"]',
            'resource_properties': '',
            'start_date': datetime.datetime(2013, 12, 19, 20, 00),
            'end_date': datetime.datetime(2013, 12, 19, 21, 00),
            'resource_type': plugin.RESOURCE_TYPE,
        }
        reservation_values = {
            'id': u'441c1476-9f8f-4700-9f30-cd9b6fef3509',
            'lease_id': u'018c1b43-e69e-4aef-a543-09681539cf4c',
            'resource_id': '1',
            'resource_type': plugin.RESOURCE_TYPE,
            'status': 'pending',
        }
        uuid4 = self.patch(uuid, 'uuid4')
        uuid4.return_value = uuid.UUID('441c1476-9f8f-4700-9f30-cd9b6fef3509')
        self.rp_create.return_value = mock.MagicMock(id='1')
        reservation_create = self.patch(self.db_api, 'reservation_create')
        reservation_create.return_value = {
            'id': u'f9894fcf-e2ed-41e9-8a4c-92fac332608e',
        }
        host_reservation_create = self.patch(self.db_api,
                                             'host_reservation_create')
        matching_hosts = self.patch(self.fake_phys_plugin, '_matching_hosts')
        matching_hosts.return_value = []
        self.assertRaises(RuntimeError,
                          self.fake_phys_plugin.create_reservation, values)
        reservation_create.assert_called_once_with(reservation_values)
        host_values = {
            'reservation_id': u'f9894fcf-e2ed-41e9-8a4c-92fac332608e',
            'resource_properties': '',
            'hypervisor_properties': '["=", "$memory_mb", "256"]',
            'count_range': '1-1',
            'status': 'pending'
        }
        host_reservation_create.assert_called_once_with(host_values)

    def test_create_reservation_hosts_available(self):
        values = {
            'lease_id': u'018c1b43-e69e-4aef-a543-09681539cf4c',
            'min': u'1',
            'max': u'1',
            'hypervisor_properties': '["=", "$memory_mb", "256"]',
            'resource_properties': '',
            'start_date': datetime.datetime(2013, 12, 19, 20, 00),
            'end_date': datetime.datetime(2013, 12, 19, 21, 00),
            'resource_type': plugin.RESOURCE_TYPE,
        }
        reservation_values = {
            'id': u'441c1476-9f8f-4700-9f30-cd9b6fef3509',
            'lease_id': u'018c1b43-e69e-4aef-a543-09681539cf4c',
            'resource_id': '1',
            'resource_type': plugin.RESOURCE_TYPE,
            'status': 'pending',
        }
        uuid4 = self.patch(uuid, 'uuid4')
        uuid4.return_value = uuid.UUID('441c1476-9f8f-4700-9f30-cd9b6fef3509')
        self.rp_create.return_value = mock.MagicMock(id='1')
        reservation_create = self.patch(self.db_api, 'reservation_create')
        reservation_create.return_value = {
            'id': u'f9894fcf-e2ed-41e9-8a4c-92fac332608e',
        }
        host_reservation_create = self.patch(self.db_api,
                                             'host_reservation_create')
        matching_hosts = self.patch(self.fake_phys_plugin, '_matching_hosts')
        matching_hosts.return_value = ['host1', 'host2']
        host_allocation_create = self.patch(
            self.db_api,
            'host_allocation_create')
        self.fake_phys_plugin.create_reservation(values)
        reservation_create.assert_called_once_with(reservation_values)
        host_values = {
            'reservation_id': u'f9894fcf-e2ed-41e9-8a4c-92fac332608e',
            'resource_properties': '',
            'hypervisor_properties': '["=", "$memory_mb", "256"]',
            'count_range': '1-1',
            'status': 'pending',
        }
        host_reservation_create.assert_called_once_with(host_values)
        calls = [
            mock.call(
                {'compute_host_id': 'host1',
                 'reservation_id': u'f9894fcf-e2ed-41e9-8a4c-92fac332608e',
                 }),
            mock.call(
                {'compute_host_id': 'host2',
                 'reservation_id': u'f9894fcf-e2ed-41e9-8a4c-92fac332608e',
                 }),
        ]
        host_allocation_create.assert_has_calls(calls)

    def test_update_reservation_shorten(self):
        values = {
            'start_date': datetime.datetime(2013, 12, 19, 20, 30),
            'end_date': datetime.datetime(2013, 12, 19, 21, 00)
        }
        reservation_get = self.patch(self.db_api, 'reservation_get')
        reservation_get.return_value = {
            'lease_id': u'10870923-6d56-45c9-b592-f788053f5baa',
            'resource_id': u'91253650-cc34-4c4f-bbe8-c943aa7d0c9b'
        }
        lease_get = self.patch(self.db_api, 'lease_get')
        lease_get.return_value = {
            'start_date': datetime.datetime(2013, 12, 19, 20, 00),
            'end_date': datetime.datetime(2013, 12, 19, 21, 00)
        }
        host_allocation_get_all = self.patch(
            self.db_api,
            'host_allocation_get_all_by_values')
        get_computehosts = self.patch(self.rp.ReservationPool,
                                      'get_computehosts')
        get_computehosts.return_value = ['host1']
        self.fake_phys_plugin.update_reservation(
            '706eb3bc-07ed-4383-be93-b32845ece672',
            values)
        host_allocation_get_all.assert_not_called()

    def test_update_reservation_extend(self):
        values = {
            'start_date': datetime.datetime(2013, 12, 19, 20, 00),
            'end_date': datetime.datetime(2013, 12, 19, 21, 30)
        }
        reservation_get = self.patch(self.db_api, 'reservation_get')
        reservation_get.return_value = {
            'lease_id': u'10870923-6d56-45c9-b592-f788053f5baa',
            'resource_id': u'91253650-cc34-4c4f-bbe8-c943aa7d0c9b'
        }
        lease_get = self.patch(self.db_api, 'lease_get')
        lease_get.return_value = {
            'start_date': datetime.datetime(2013, 12, 19, 20, 00),
            'end_date': datetime.datetime(2013, 12, 19, 21, 00)
        }
        host_reservation_get_by_reservation_id = self.patch(
            self.db_api,
            'host_reservation_get_by_reservation_id')
        host_allocation_get_all = self.patch(
            self.db_api,
            'host_allocation_get_all_by_values')
        host_allocation_get_all.return_value = [
            {
                'id': u'dd305477-4df8-4547-87f6-69069ee546a6',
                'compute_host_id': 'host1'
            }
        ]
        get_full_periods = self.patch(self.db_utils, 'get_full_periods')
        get_full_periods.return_value = [
            (datetime.datetime(2013, 12, 19, 20, 00),
             datetime.datetime(2013, 12, 19, 21, 00))
        ]
        get_computehosts = self.patch(self.rp.ReservationPool,
                                      'get_computehosts')
        get_computehosts.return_value = ['host1']
        self.fake_phys_plugin.update_reservation(
            '706eb3bc-07ed-4383-be93-b32845ece672',
            values)
        host_reservation_get_by_reservation_id.assert_not_called()

    def test_update_reservation_move_failure(self):
        values = {
            'start_date': datetime.datetime(2013, 12, 20, 20, 00),
            'end_date': datetime.datetime(2013, 12, 20, 21, 30)
        }
        reservation_get = self.patch(self.db_api, 'reservation_get')
        reservation_get.return_value = {
            'lease_id': u'10870923-6d56-45c9-b592-f788053f5baa',
            'resource_id': u'91253650-cc34-4c4f-bbe8-c943aa7d0c9b'
        }
        lease_get = self.patch(self.db_api, 'lease_get')
        lease_get.return_value = {
            'start_date': datetime.datetime(2013, 12, 19, 20, 00),
            'end_date': datetime.datetime(2013, 12, 19, 21, 00)
        }
        host_reservation_get_by_reservation_id = self.patch(
            self.db_api,
            'host_reservation_get_by_reservation_id')
        host_allocation_get_all = self.patch(
            self.db_api,
            'host_allocation_get_all_by_values')
        host_allocation_get_all.return_value = [
            {
                'id': u'dd305477-4df8-4547-87f6-69069ee546a6',
                'compute_host_id': 'host1'
            }
        ]
        get_full_periods = self.patch(self.db_utils, 'get_full_periods')
        get_full_periods.return_value = [
            (datetime.datetime(2013, 12, 20, 20, 30),
             datetime.datetime(2013, 12, 20, 21, 00))
        ]
        get_computehosts = self.patch(self.rp.ReservationPool,
                                      'get_computehosts')
        get_computehosts.return_value = ['host1']
        self.patch(self.fake_phys_plugin, '_get_hypervisor_from_name')
        get_hypervisors = self.patch(self.nova.hypervisors, 'get')
        get_hypervisors.return_value = mock.MagicMock(running_vms=1)
        self.assertRaises(
            RuntimeError, self.fake_phys_plugin.update_reservation,
            '706eb3bc-07ed-4383-be93-b32845ece672',
            values)
        host_reservation_get_by_reservation_id.assert_not_called()

    def test_update_reservation_move_overlap(self):
        values = {
            'start_date': datetime.datetime(2013, 12, 19, 20, 30),
            'end_date': datetime.datetime(2013, 12, 19, 21, 30)
        }
        reservation_get = self.patch(self.db_api, 'reservation_get')
        reservation_get.return_value = {
            'lease_id': u'10870923-6d56-45c9-b592-f788053f5baa',
            'resource_id': u'91253650-cc34-4c4f-bbe8-c943aa7d0c9b'
        }
        lease_get = self.patch(self.db_api, 'lease_get')
        lease_get.return_value = {
            'start_date': datetime.datetime(2013, 12, 19, 20, 00),
            'end_date': datetime.datetime(2013, 12, 19, 21, 00)
        }
        host_reservation_get_by_reservation_id = self.patch(
            self.db_api,
            'host_reservation_get_by_reservation_id')
        host_allocation_get_all = self.patch(
            self.db_api,
            'host_allocation_get_all_by_values')
        host_allocation_get_all.return_value = [
            {
                'id': u'dd305477-4df8-4547-87f6-69069ee546a6',
                'compute_host_id': 'host1'
            }
        ]
        get_full_periods = self.patch(self.db_utils, 'get_full_periods')
        get_full_periods.return_value = [
            (datetime.datetime(2013, 12, 19, 20, 30),
             datetime.datetime(2013, 12, 19, 21, 00))
        ]
        get_computehosts = self.patch(self.rp.ReservationPool,
                                      'get_computehosts')
        get_computehosts.return_value = []
        self.fake_phys_plugin.update_reservation(
            '706eb3bc-07ed-4383-be93-b32845ece672',
            values)
        host_reservation_get_by_reservation_id.assert_not_called()

    def test_update_reservation_move_realloc(self):
        values = {
            'start_date': datetime.datetime(2013, 12, 20, 20, 00),
            'end_date': datetime.datetime(2013, 12, 20, 21, 30)
        }
        reservation_get = self.patch(self.db_api, 'reservation_get')
        reservation_get.return_value = {
            'lease_id': u'10870923-6d56-45c9-b592-f788053f5baa',
            'resource_id': u'91253650-cc34-4c4f-bbe8-c943aa7d0c9b'
        }
        lease_get = self.patch(self.db_api, 'lease_get')
        lease_get.return_value = {
            'start_date': datetime.datetime(2013, 12, 19, 20, 00),
            'end_date': datetime.datetime(2013, 12, 19, 21, 00)
        }
        host_get = self.patch(self.db_api, 'host_get')
        host_get.return_value = {'hypervisor_hostname': 'host2'}
        host_reservation_get_by_reservation_id = self.patch(
            self.db_api,
            'host_reservation_get_by_reservation_id')
        host_allocation_get_all = self.patch(
            self.db_api,
            'host_allocation_get_all_by_values')
        host_allocation_get_all.return_value = [
            {
                'id': u'dd305477-4df8-4547-87f6-69069ee546a6',
                'compute_host_id': 'host1'
            }
        ]
        host_allocation_create = self.patch(
            self.db_api,
            'host_allocation_create')
        host_allocation_destroy = self.patch(
            self.db_api,
            'host_allocation_destroy')
        get_full_periods = self.patch(self.db_utils, 'get_full_periods')
        get_full_periods.return_value = [
            (datetime.datetime(2013, 12, 20, 20, 30),
             datetime.datetime(2013, 12, 20, 21, 00))
        ]
        get_computehosts = self.patch(self.rp.ReservationPool,
                                      'get_computehosts')
        get_computehosts.return_value = ['host1']
        self.patch(self.fake_phys_plugin, '_get_hypervisor_from_name')
        get_hypervisors = self.patch(self.nova.hypervisors, 'get')
        get_hypervisors.return_value = mock.MagicMock(running_vms=0)
        matching_hosts = self.patch(self.fake_phys_plugin, '_matching_hosts')
        matching_hosts.return_value = ['host2']
        self.fake_phys_plugin.update_reservation(
            '706eb3bc-07ed-4383-be93-b32845ece672',
            values)
        host_reservation_get_by_reservation_id.assert_called_with(
            '706eb3bc-07ed-4383-be93-b32845ece672')
        host_allocation_destroy.assert_called_with(
            'dd305477-4df8-4547-87f6-69069ee546a6')
        host_allocation_create.assert_called_with(
            {
                'compute_host_id': 'host2',
                'reservation_id': '706eb3bc-07ed-4383-be93-b32845ece672'
            }
        )
        self.remove_compute_host.assert_called_with(
            '91253650-cc34-4c4f-bbe8-c943aa7d0c9b',
            ['host1']
        )
        self.add_compute_host.assert_called_with(
            '91253650-cc34-4c4f-bbe8-c943aa7d0c9b',
            'host2'
        )

    def test_on_start(self):
        reservation_get_all_by_values = self.patch(
            self.db_api, 'reservation_get_all_by_values')

        reservation_get_all_by_values.return_value = [
            {
                'id': u'593e7028-c0d1-4d76-8642-2ffd890b324c',
                'resource_id': u'04de74e8-193a-49d2-9ab8-cba7b49e45e8',
            }
        ]
        host_allocation_get_all_by_values = self.patch(
            self.db_api, 'host_allocation_get_all_by_values')

        host_allocation_get_all_by_values.return_value = [
            {'compute_host_id': 'host1'},
        ]
        host_get = self.patch(self.db_api, 'host_get')
        host_get.return_value = {'hypervisor_hostname': 'host1_hostname'}
        add_computehost = self.patch(
            self.rp.ReservationPool, 'add_computehost')

        self.fake_phys_plugin.on_start(u'04de74e8-193a-49d2-9ab8-cba7b49e45e8')

        add_computehost.assert_called_with(
            u'04de74e8-193a-49d2-9ab8-cba7b49e45e8', 'host1_hostname')

    def test_on_end_with_instances(self):
        reservation_get_all_by_values = self.patch(
            self.db_api,
            'reservation_get_all_by_values')

        reservation_get_all_by_values.return_value = [
            {
                'id': u'593e7028-c0d1-4d76-8642-2ffd890b324c',
                'resource_id': u'04de74e8-193a-49d2-9ab8-cba7b49e45e8',
            }
        ]
        reservation_update = self.patch(self.db_api, 'reservation_update')
        host_reservation_get_by_reservation_id = self.patch(
            self.db_api,
            'host_reservation_get_by_reservation_id')
        host_reservation_get_by_reservation_id.return_value = {
            'id': u'35fc4e6a-ba57-4a36-be30-6012377a0387',
        }
        host_reservation_update = self.patch(
            self.db_api,
            'host_reservation_update')
        host_allocation_get_all_by_values = self.patch(
            self.db_api,
            'host_allocation_get_all_by_values')
        host_allocation_get_all_by_values.return_value = [
            {'id': u'bfa9aa0b-8042-43eb-a4e6-4555838bf64f',
             'compute_host_id': u'cdae2a65-236f-475a-977d-f6ad82f828b7',
             },
        ]
        host_allocation_destroy = self.patch(
            self.db_api,
            'host_allocation_destroy')
        delete = self.patch(self.rp.ReservationPool, 'delete')
        self.patch(self.fake_phys_plugin, '_get_hypervisor_from_name')
        get_hypervisors = self.patch(self.nova.hypervisors, 'get')
        get_hypervisors.return_value = mock.MagicMock(running_vms=1)
        self.fake_phys_plugin.on_end(u'04de74e8-193a-49d2-9ab8-cba7b49e45e8')
        reservation_update.assert_called_with(
            u'593e7028-c0d1-4d76-8642-2ffd890b324c', {'status': 'completed'})
        host_reservation_update.assert_called_with(
            u'35fc4e6a-ba57-4a36-be30-6012377a0387', {'status': 'completed'})
        host_allocation_destroy.assert_called_with(
            u'bfa9aa0b-8042-43eb-a4e6-4555838bf64f')
        assert not delete.called

    def test_on_end_without_instances(self):
        reservation_get_all_by_values = self.patch(
            self.db_api,
            'reservation_get_all_by_values')
        reservation_get_all_by_values.return_value = [
            {
                'id': u'593e7028-c0d1-4d76-8642-2ffd890b324c',
                'resource_id': u'04de74e8-193a-49d2-9ab8-cba7b49e45e8',
            },
        ]
        reservation_update = self.patch(self.db_api, 'reservation_update')
        host_reservation_get_by_reservation_id = self.patch(
            self.db_api,
            'host_reservation_get_by_reservation_id')
        host_reservation_get_by_reservation_id.return_value = {
            'id': u'35fc4e6a-ba57-4a36-be30-6012377a0387',
        }
        host_reservation_update = self.patch(
            self.db_api,
            'host_reservation_update')
        host_allocation_get_all_by_values = self.patch(
            self.db_api,
            'host_allocation_get_all_by_values')
        host_allocation_get_all_by_values.return_value = [
            {'id': u'bfa9aa0b-8042-43eb-a4e6-4555838bf64f',
             'compute_host_id': u'cdae2a65-236f-475a-977d-f6ad82f828b7',
             },
        ]
        host_allocation_destroy = self.patch(
            self.db_api,
            'host_allocation_destroy')
        delete = self.patch(self.rp.ReservationPool, 'delete')
        self.patch(self.fake_phys_plugin, '_get_hypervisor_from_name')
        get_hypervisors = self.patch(self.nova.hypervisors, 'get')
        get_hypervisors.return_value = mock.MagicMock(running_vms=0)
        self.fake_phys_plugin.on_end(u'04de74e8-193a-49d2-9ab8-cba7b49e45e8')
        reservation_update.assert_called_with(
            u'593e7028-c0d1-4d76-8642-2ffd890b324c', {'status': 'completed'})
        host_reservation_update.assert_called_with(
            u'35fc4e6a-ba57-4a36-be30-6012377a0387', {'status': 'completed'})
        host_allocation_destroy.assert_called_with(
            u'bfa9aa0b-8042-43eb-a4e6-4555838bf64f')
        delete.assert_called_with(u'04de74e8-193a-49d2-9ab8-cba7b49e45e8')

    def test_matching_hosts_not_allocated_hosts(self):
        def host_allocation_get_all_by_values(**kwargs):
            if kwargs['compute_host_id'] == 'host1':
                return True
        host_get = self.patch(
            self.db_api,
            'host_get_all_by_queries')
        host_get.return_value = [
            {'id': 'host1'},
            {'id': 'host2'},
            {'id': 'host3'},
        ]
        host_get = self.patch(
            self.db_api,
            'host_allocation_get_all_by_values')
        host_get.side_effect = host_allocation_get_all_by_values
        host_get = self.patch(
            self.db_utils,
            'get_free_periods')
        host_get.return_value = [
            (datetime.datetime(2013, 12, 19, 20, 00),
             datetime.datetime(2013, 12, 19, 21, 00)),
        ]
        result = self.fake_phys_plugin._matching_hosts(
            '[]', '[]', '1-3',
            datetime.datetime(2013, 12, 19, 20, 00),
            datetime.datetime(2013, 12, 19, 21, 00))
        self.assertEqual(['host2', 'host3'], result)

    def test_matching_hosts_allocated_hosts(self):
        def host_allocation_get_all_by_values(**kwargs):
            if kwargs['compute_host_id'] == 'host1':
                return True
        host_get = self.patch(
            self.db_api,
            'host_get_all_by_queries')
        host_get.return_value = [
            {'id': 'host1'},
            {'id': 'host2'},
            {'id': 'host3'},
        ]
        host_get = self.patch(
            self.db_api,
            'host_allocation_get_all_by_values')
        host_get.side_effect = host_allocation_get_all_by_values
        host_get = self.patch(
            self.db_utils,
            'get_free_periods')
        host_get.return_value = [
            (datetime.datetime(2013, 12, 19, 20, 00),
             datetime.datetime(2013, 12, 19, 21, 00)),
        ]
        result = self.fake_phys_plugin._matching_hosts(
            '[]', '[]', '3-3',
            datetime.datetime(2013, 12, 19, 20, 00),
            datetime.datetime(2013, 12, 19, 21, 00))
        self.assertEqual(['host1', 'host2', 'host3'], result)

    def test_matching_hosts_not_matching(self):
        host_get = self.patch(
            self.db_api,
            'host_get_all_by_queries')
        host_get.return_value = []
        result = self.fake_phys_plugin._matching_hosts(
            '["=", "$memory_mb", "2048"]', '[]', '1-1',
            datetime.datetime(2013, 12, 19, 20, 00),
            datetime.datetime(2013, 12, 19, 21, 00))
        self.assertEqual([], result)

    def test_convert_requirements_empty(self):
        request = '[]'
        result = self.fake_phys_plugin._convert_requirements(request)
        self.assertEqual([], result)

    def test_convert_requirements_small(self):
        request = '["=", "$memory", "4096"]'
        result = self.fake_phys_plugin._convert_requirements(request)
        self.assertEqual(['memory == 4096'], result)

    def test_convert_requirements_with_incorrect_syntax_1(self):
        self.assertRaises(
            RuntimeError, self.fake_phys_plugin._convert_requirements,
            '["a", "$memory", "4096"]')

    def test_convert_requirements_with_incorrect_syntax_2(self):
        self.assertRaises(
            RuntimeError, self.fake_phys_plugin._convert_requirements,
            '["=", "memory", "4096"]')

    def test_convert_requirements_with_incorrect_syntax_3(self):
        self.assertRaises(
            RuntimeError, self.fake_phys_plugin._convert_requirements,
            '["=", "$memory", 4096]')

    def test_convert_requirements_complex(self):
        request = '["and", [">", "$memory", "4096"], [">", "$disk", "40"]]'
        result = self.fake_phys_plugin._convert_requirements(request)
        self.assertEqual(['memory > 4096', 'disk > 40'], result)

    def test_convert_requirements_complex_with_incorrect_syntax_1(self):
        self.assertRaises(
            RuntimeError, self.fake_phys_plugin._convert_requirements,
            '["and", [">", "memory", "4096"], [">", "$disk", "40"]]')

    def test_convert_requirements_complex_with_incorrect_syntax_2(self):
        self.assertRaises(
            RuntimeError, self.fake_phys_plugin._convert_requirements,
            '["fail", [">", "$memory", "4096"], [">", "$disk", "40"]]')
