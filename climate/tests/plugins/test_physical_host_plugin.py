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

import testtools

from climate import context
from climate.db import api as db_api
from climate.manager import service
from climate.plugins.oshosts import nova_inventory
from climate.plugins.oshosts import reservation_pool as rp
from climate.plugins import physical_host_plugin
from climate import tests


class PhysicalHostPlugingSetupOnlyTestCase(tests.TestCase):
    def setUp(self):
        super(PhysicalHostPlugingSetupOnlyTestCase, self).setUp()
        self.context = context
        self.patch(self.context, 'ClimateContext')
        self.physical_host_plugin = physical_host_plugin
        self.fake_phys_plugin = \
            self.physical_host_plugin.PhysicalHostPlugin()
        self.rp = rp
        self.nova_inventory = nova_inventory
        self.rp_create = self.patch(self.rp.ReservationPool, 'create')
        self.db_api = db_api
        self.db_host_extra_capability_get_all_per_host = \
            self.patch(self.db_api, 'host_extra_capability_get_all_per_host')

    def test_setup(self):
        def fake_setup():
            freepool = self.patch(self.fake_phys_plugin, '_freepool_exists')
            freepool.return_value = False

        pool = self.patch(self.rp.ReservationPool, '__init__')
        pool.side_effect = fake_setup
        inventory = self.patch(self.nova_inventory.NovaInventory, '__init__')
        inventory.return_value = None
        self.fake_phys_plugin.setup(None)
        pool.assert_called_once_with()
        inventory.assert_called_once_with()
        self.rp_create.assert_called_once_with(name='freepool', az=None)

    def test__freepool_exists_with_freepool_present(self):
        self.patch(self.rp.ReservationPool, 'get_aggregate_from_name_or_id')
        self.fake_phys_plugin.setup(None)
        self.assertEqual(self.fake_phys_plugin._freepool_exists(), True)

    def test__freepool_exists_with_freepool_missing(self):
        def fake_get_aggregate_from_name_or_id(*args, **kwargs):
            raise rp.AggregateNotFound
        mock = self.patch(self.rp.ReservationPool,
                          'get_aggregate_from_name_or_id')
        mock.side_effect = fake_get_aggregate_from_name_or_id
        self.fake_phys_plugin.setup(None)
        self.assertEqual(self.fake_phys_plugin._freepool_exists(), False)

    def test__get_extra_capabilities_with_values(self):
        self.db_host_extra_capability_get_all_per_host.return_value = \
            [{'id': 1,
              'capability_name': 'foo',
              'capability_value': 'bar',
              'other': 'value',
              'computehost_id': 1},
             {'id': 2,
              'capability_name': 'buzz',
              'capability_value': 'word',
              'computehost_id': 1}]
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

        self.service = service
        self.manager = self.service.ManagerService('127.0.0.1')

        self.fake_host_id = '1'
        self.fake_host = {'id': self.fake_host_id,
                          'hypervisor_hostname': 'foo',
                          'vcpus': 4,
                          'cpu_info': 'foo',
                          'hypervisor_type': 'xen',
                          'hypervisor_version': 1,
                          'memory_mb': 8192,
                          'local_gb': 10}

        self.physical_host_plugin = physical_host_plugin
        self.fake_phys_plugin = \
            self.physical_host_plugin.PhysicalHostPlugin()
        self.db_api = db_api

        self.db_host_get = self.patch(self.db_api, 'host_get')
        self.db_host_get.return_value = self.fake_host
        self.db_host_list = self.patch(self.db_api, 'host_list')
        self.db_host_create = self.patch(self.db_api, 'host_create')
        self.db_host_update = self.patch(self.db_api, 'host_update')
        self.db_host_destroy = self.patch(self.db_api, 'host_destroy')

        self.db_host_extra_capability_get_all_per_host = \
            self.patch(self.db_api, 'host_extra_capability_get_all_per_host')
        self.db_host_extra_capability_get_all_per_name = \
            self.patch(self.db_api, 'host_extra_capability_get_all_per_name')
        self.db_host_extra_capability_create = \
            self.patch(self.db_api, 'host_extra_capability_create')
        self.db_host_extra_capability_update = \
            self.patch(self.db_api, 'host_extra_capability_update')

        self.rp = rp
        self.nova_inventory = nova_inventory
        self.rp_create = self.patch(self.rp.ReservationPool, 'create')
        self.patch(self.rp.ReservationPool, 'get_aggregate_from_name_or_id')
        self.patch(self.rp.ReservationPool, 'add_computehost')
        self.patch(self.rp.ReservationPool, 'remove_computehost')
        self.get_host_details = self.patch(self.nova_inventory.NovaInventory,
                                           'get_host_details')
        self.get_host_details.return_value = self.fake_host
        self.get_servers_per_host = self.patch(
            self.nova_inventory.NovaInventory, 'get_servers_per_host')
        self.get_servers_per_host.return_value = None
        self.get_extra_capabilities = self.patch(self.fake_phys_plugin,
                                                 '_get_extra_capabilities')
        self.get_extra_capabilities.return_value = {'foo': 'bar',
                                                    'buzz': 'word'}
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
                     'capability_value': 'bar'}
        self.get_extra_capabilities.return_value = {'foo': 'bar'}
        self.db_host_create.return_value = self.fake_host
        host = self.fake_phys_plugin.create_computehost(fake_request)
        self.db_host_create.assert_called_once_with(self.fake_host)
        self.db_host_extra_capability_create.assert_called_once_with(fake_capa)
        self.assertEqual(host, fake_host)

    def test_create_host_with_invalid_values(self):
        self.assertRaises(nova_inventory.InvalidHost,
                          self.fake_phys_plugin.create_computehost, {})

    def test_create_host_with_existing_vms(self):
        self.get_servers_per_host.return_value = ['server1', 'server2']
        self.assertRaises(nova_inventory.HostHavingServers,
                          self.fake_phys_plugin.create_computehost,
                          self.fake_host)

    def test_create_host_issuing_rollback(self):
        def fake_db_host_create(*args, **kwargs):
            raise RuntimeError
        self.db_host_create.side_effect = fake_db_host_create
        host = self.fake_phys_plugin.create_computehost(self.fake_host)
        self.assertEqual(None, host)

    def test_create_host_having_issue_when_storing_extra_capability(self):
        def fake_db_host_extra_capability_create(*args, **kwargs):
            raise RuntimeError
        fake_host = self.fake_host.copy()
        fake_host.update({'foo': 'bar'})
        fake_request = fake_host.copy()
        self.get_extra_capabilities.return_value = {'foo': 'bar'}
        self.db_host_create.return_value = self.fake_host
        self.db_host_extra_capability_create.side_effect = \
            fake_db_host_extra_capability_create
        self.assertRaises(physical_host_plugin.CantAddExtraCapability,
                          self.fake_phys_plugin.create_computehost,
                          fake_request)

    def test_update_host(self):
        host_values = {'foo': 'baz'}

        self.db_host_extra_capability_get_all_per_name.return_value = \
            [{'id': '1',
             'capability_name': 'foo',
             'capability_value': 'bar'}]
        self.fake_phys_plugin.update_computehost(self.fake_host_id,
                                                 host_values)
        self.db_host_extra_capability_update.assert_called_once_with(
            '1', {'capability_name': 'foo', 'capability_value': 'baz'})

    def test_update_host_having_issue_when_storing_extra_capability(self):
        def fake_db_host_extra_capability_update(*args, **kwargs):
            raise RuntimeError
        host_values = {'foo': 'baz'}
        self.db_host_extra_capability_get_all_per_name.return_value = \
            [{'id': '1',
             'capability_name': 'foo',
             'capability_value': 'bar'}]
        self.db_host_extra_capability_update.side_effect = \
            fake_db_host_extra_capability_update
        self.assertRaises(physical_host_plugin.CantAddExtraCapability,
                          self.fake_phys_plugin.update_computehost,
                          self.fake_host_id, host_values)

    def test_delete_host(self):
        self.fake_phys_plugin.delete_computehost(self.fake_host_id)

        self.db_host_destroy.assert_called_once_with(self.fake_host_id)

    def test_delete_host_having_vms(self):
        self.get_servers_per_host.return_value = ['server1', 'server2']
        self.assertRaises(nova_inventory.HostHavingServers,
                          self.fake_phys_plugin.delete_computehost,
                          self.fake_host_id)

    def test_delete_host_not_existing_in_db(self):
        self.db_host_get.return_value = None
        self.assertRaises(rp.HostNotFound,
                          self.fake_phys_plugin.delete_computehost,
                          self.fake_host_id)

    def test_delete_host_issuing_rollback(self):
        def fake_db_host_destroy(*args, **kwargs):
            raise RuntimeError
        self.db_host_destroy.side_effect = fake_db_host_destroy
        self.assertRaises(rp.CantRemoveHost,
                          self.fake_phys_plugin.delete_computehost,
                          self.fake_host_id)
