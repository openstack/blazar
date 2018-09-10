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

import collections
import datetime
from unittest import mock

import ddt
from novaclient import client as nova_client
from novaclient import exceptions as nova_exceptions
from oslo_config import cfg
from oslo_config import fixture as conf_fixture
import random
import testtools

from blazar import context
from blazar.db import api as db_api
from blazar.db import exceptions as db_exceptions
from blazar.db import utils as db_utils
from blazar.manager import exceptions as manager_exceptions
from blazar.manager import service
from blazar.plugins import oshosts as plugin
from blazar.plugins.oshosts import host_plugin
from blazar import tests
from blazar.utils.openstack import base
from blazar.utils.openstack import nova
from blazar.utils.openstack import placement
from blazar.utils import trusts

CONF = cfg.CONF


class AggregateFake(object):

    def __init__(self, i, name, hosts):
        self.id = i
        self.name = name
        self.hosts = hosts


class PhysicalHostPluginSetupOnlyTestCase(tests.TestCase):

    def setUp(self):
        super(PhysicalHostPluginSetupOnlyTestCase, self).setUp()

        self.cfg = self.useFixture(conf_fixture.Config(CONF))
        self.cfg.config(os_admin_username='fake-user')
        self.cfg.config(os_admin_password='fake-passwd')
        self.cfg.config(os_admin_user_domain_name='fake-user-domain')
        self.cfg.config(os_admin_project_name='fake-pj-name')
        self.cfg.config(os_admin_project_domain_name='fake-pj-domain')

        self.context = context
        self.patch(self.context, 'BlazarContext')
        self.patch(base, 'url_for').return_value = 'http://foo.bar'
        self.host_plugin = host_plugin
        self.fake_phys_plugin = self.host_plugin.PhysicalHostPlugin()
        self.nova = nova
        self.rp_create = self.patch(self.nova.ReservationPool, 'create')
        self.db_api = db_api
        self.db_host_extra_capability_get_all_per_host = (
            self.patch(self.db_api, 'host_extra_capability_get_all_per_host'))

    def test_configuration(self):
        self.assertEqual("fake-user", self.fake_phys_plugin.username)
        self.assertEqual("fake-passwd", self.fake_phys_plugin.password)
        self.assertEqual("fake-user-domain",
                         self.fake_phys_plugin.user_domain_name)
        self.assertEqual("fake-pj-name", self.fake_phys_plugin.project_name)
        self.assertEqual("fake-pj-domain",
                         self.fake_phys_plugin.project_domain_name)

    def test__get_extra_capabilities_with_values(self):
        ComputeHostExtraCapability = collections.namedtuple(
            'ComputeHostExtraCapability',
            ['id', 'property_id', 'capability_value', 'computehost_id'])
        self.db_host_extra_capability_get_all_per_host.return_value = [
            (ComputeHostExtraCapability(1, 'foo', 'bar', 1), 'foo'),
            (ComputeHostExtraCapability(2, 'buzz', 'word', 1), 'buzz')]

        res = self.fake_phys_plugin._get_extra_capabilities(1)
        self.assertEqual({'foo': 'bar', 'buzz': 'word'}, res)

    def test__get_extra_capabilities_with_no_capabilities(self):
        self.db_host_extra_capability_get_all_per_host.return_value = []
        res = self.fake_phys_plugin._get_extra_capabilities(1)
        self.assertEqual({}, res)


@ddt.ddt
class PhysicalHostPluginTestCase(tests.TestCase):

    def setUp(self):
        super(PhysicalHostPluginTestCase, self).setUp()
        self.cfg = cfg
        self.context = context
        self.patch(self.context, 'BlazarContext')

        self.nova_client = nova_client
        self.nova_client = self.patch(self.nova_client, 'Client').return_value

        self.service = service
        self.manager = self.service.ManagerService()

        self.fake_host_id = '1'
        self.fake_host = {
            'id': self.fake_host_id,
            'hypervisor_hostname': 'hypvsr1',
            'service_name': 'compute1',
            'vcpus': 4,
            'cpu_info': 'foo',
            'hypervisor_type': 'xen',
            'hypervisor_version': 1,
            'memory_mb': 8192,
            'local_gb': 10,
            'trust_id': 'exxee111qwwwwe',
        }

        self.patch(base, 'url_for').return_value = 'http://foo.bar'
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

        self.nova = nova
        self.rp_create = self.patch(self.nova.ReservationPool, 'create')
        self.patch(self.nova.ReservationPool, 'get_aggregate_from_name_or_id')
        self.add_compute_host = self.patch(self.nova.ReservationPool,
                                           'add_computehost')
        self.remove_compute_host = self.patch(self.nova.ReservationPool,
                                              'remove_computehost')
        self.get_host_details = self.patch(self.nova.NovaInventory,
                                           'get_host_details')
        self.get_host_details.return_value = self.fake_host
        self.get_servers_per_host = self.patch(
            self.nova.NovaInventory, 'get_servers_per_host')
        self.get_servers_per_host.return_value = None
        self.get_extra_capabilities = self.patch(
            self.fake_phys_plugin, '_get_extra_capabilities')
        self.get_extra_capabilities.return_value = {
            'foo': 'bar',
            'buzz': 'word',
        }

        self.placement = placement
        self.prov_create = self.patch(self.placement.BlazarPlacementClient,
                                      'create_reservation_provider')
        self.prov_create.return_value = {
            "generation": 0,
            "name": "blazar_foo",
            "uuid": "7d2590ae-fb85-4080-9306-058b4c915e3f",
            "parent_provider_uuid": "542df8ed-9be2-49b9-b4db-6d3183ff8ec8",
            "root_provider_uuid": "542df8ed-9be2-49b9-b4db-6d3183ff8ec8"
        }
        self.prov_delete = self.patch(self.placement.BlazarPlacementClient,
                                      'delete_reservation_provider')

        self.fake_phys_plugin.setup(None)

        self.trusts = trusts
        self.trust_ctx = self.patch(self.trusts, 'create_ctx_from_trust')
        self.trust_create = self.patch(self.trusts, 'create_trust')

        self.ServerManager = nova.ServerManager

    def test_get_host(self):
        host = self.fake_phys_plugin.get_computehost(self.fake_host_id)
        self.db_host_get.assert_called_once_with('1')
        expected = self.fake_host.copy()
        expected.update({'foo': 'bar', 'buzz': 'word'})
        self.assertEqual(expected, host)

    def test_get_host_without_extracapabilities(self):
        self.get_extra_capabilities.return_value = {}
        host = self.fake_phys_plugin.get_computehost(self.fake_host_id)
        self.db_host_get.assert_called_once_with('1')
        self.assertEqual(self.fake_host, host)

    @testtools.skip('incorrect decorator')
    def test_list_hosts(self):
        self.fake_phys_plugin.list_computehosts({})
        self.db_host_list.assert_called_once_with()
        del self.service_utils

    def test_create_host_without_extra_capabilities(self):
        self.get_extra_capabilities.return_value = {}
        host = self.fake_phys_plugin.create_computehost(self.fake_host)
        self.db_host_create.assert_called_once_with(self.fake_host)
        self.prov_create.assert_called_once_with('hypvsr1')
        self.assertEqual(self.fake_host, host)

    def test_create_host_with_extra_capabilities(self):
        fake_host = self.fake_host.copy()
        fake_host.update({'foo': 'bar'})
        # NOTE(sbauza): 'id' will be pop'd, we need to keep track of it
        fake_request = fake_host.copy()
        fake_capa = {'computehost_id': '1',
                     'property_name': 'foo',
                     'capability_value': 'bar',
                     }
        self.get_extra_capabilities.return_value = {'foo': 'bar'}
        self.db_host_create.return_value = self.fake_host
        host = self.fake_phys_plugin.create_computehost(fake_request)
        self.db_host_create.assert_called_once_with(self.fake_host)
        self.prov_create.assert_called_once_with('hypvsr1')
        self.db_host_extra_capability_create.assert_called_once_with(fake_capa)
        self.assertEqual(fake_host, host)

    def test_create_host_with_capabilities_too_long(self):
        fake_host = self.fake_host.copy()
        fake_host.update({'foo': 'bar'})
        # NOTE(sbauza): 'id' will be pop'd, we need to keep track of it
        fake_request = fake_host.copy()
        long_key = ""
        for i in range(65):
            long_key += "0"
        fake_request[long_key] = "foo"
        self.assertRaises(manager_exceptions.ExtraCapabilityTooLong,
                          self.fake_phys_plugin.create_computehost,
                          fake_request)

    def test_create_host_without_trust_id(self):
        self.assertRaises(manager_exceptions.MissingTrustId,
                          self.fake_phys_plugin.create_computehost, {})

    def test_create_host_without_host_id(self):
        self.assertRaises(manager_exceptions.InvalidHost,
                          self.fake_phys_plugin.create_computehost,
                          {'trust_id': 'exxee111qwwwwe'})

    def test_create_host_with_existing_vms(self):
        self.get_servers_per_host.return_value = ['server1', 'server2']
        self.assertRaises(manager_exceptions.HostHavingServers,
                          self.fake_phys_plugin.create_computehost,
                          self.fake_host)

    def test_create_host_issuing_rollback(self):
        def fake_db_host_create(*args, **kwargs):
            raise db_exceptions.BlazarDBException
        self.db_host_create.side_effect = fake_db_host_create
        self.assertRaises(db_exceptions.BlazarDBException,
                          self.fake_phys_plugin.create_computehost,
                          self.fake_host)
        self.prov_create.assert_called_once_with('hypvsr1')
        self.prov_delete.assert_called_once_with('hypvsr1')

    def test_create_host_having_issue_when_storing_extra_capability(self):
        def fake_db_host_extra_capability_create(*args, **kwargs):
            raise db_exceptions.BlazarDBException
        fake_host = self.fake_host.copy()
        fake_host.update({'foo': 'bar'})
        fake_request = fake_host.copy()
        self.get_extra_capabilities.return_value = {'foo': 'bar'}
        self.db_host_create.return_value = self.fake_host
        fake = self.db_host_extra_capability_create
        fake.side_effect = fake_db_host_extra_capability_create
        self.assertRaises(manager_exceptions.CantAddExtraCapability,
                          self.fake_phys_plugin.create_computehost,
                          fake_request)

    def test_update_host(self):
        host_values = {'foo': 'baz'}

        self.db_host_extra_capability_get_all_per_name.return_value = [
            ({'id': 'extra_id1',
              'computehost_id': self.fake_host_id,
              'capability_value': 'bar'},
             'foo'),
        ]

        self.get_reservations_by_host = self.patch(
            self.db_utils, 'get_reservations_by_host_id')
        self.get_reservations_by_host.return_value = []

        self.fake_phys_plugin.update_computehost(self.fake_host_id,
                                                 host_values)
        self.db_host_extra_capability_update.assert_called_once_with(
            'extra_id1', {'capability_value': 'baz'})

    def test_update_host_having_issue_when_storing_extra_capability(self):
        def fake_db_host_extra_capability_update(*args, **kwargs):
            raise RuntimeError
        host_values = {'foo': 'baz'}
        self.get_reservations_by_host = self.patch(
            self.db_utils, 'get_reservations_by_host_id')
        self.get_reservations_by_host.return_value = []
        self.db_host_extra_capability_get_all_per_name.return_value = [
            ({'id': 'extra_id1',
              'computehost_id': self.fake_host_id,
              'capability_value': 'bar'},
             'foo'),
        ]
        fake = self.db_host_extra_capability_update
        fake.side_effect = fake_db_host_extra_capability_update
        self.assertRaises(manager_exceptions.CantAddExtraCapability,
                          self.fake_phys_plugin.update_computehost,
                          self.fake_host_id, host_values)

    def test_update_host_with_new_extra_capability(self):
        host_values = {'qux': 'word'}

        self.db_host_extra_capability_get_all_per_host.return_value = []
        self.fake_phys_plugin.update_computehost(self.fake_host_id,
                                                 host_values)
        self.db_host_extra_capability_create.assert_called_once_with({
            'computehost_id': '1',
            'property_name': 'qux',
            'capability_value': 'word'
        })

    def test_update_host_with_used_capability(self):
        host_values = {'foo': 'buzz'}

        self.db_host_extra_capability_get_all_per_name.return_value = [
            ({'id': 'extra_id1',
              'computehost_id': self.fake_host_id,
              'capability_value': 'bar'},
             'foo'),
        ]
        fake_phys_reservation = {
            'resource_type': plugin.RESOURCE_TYPE,
            'resource_id': 'resource-1',
        }

        fake_get_reservations = self.patch(self.db_utils,
                                           'get_reservations_by_host_id')
        fake_get_reservations.return_value = [fake_phys_reservation]

        fake_get_plugin_reservation = self.patch(self.db_utils,
                                                 'get_plugin_reservation')
        fake_get_plugin_reservation.return_value = {
            'resource_properties': '["==", "$foo", "bar"]'
        }
        self.assertRaises(manager_exceptions.CantAddExtraCapability,
                          self.fake_phys_plugin.update_computehost,
                          self.fake_host_id, host_values)
        fake_get_plugin_reservation.assert_called_once_with(
            plugin.RESOURCE_TYPE, 'resource-1')

    def test_delete_host(self):
        host_allocation_get_all = self.patch(
            self.db_api,
            'host_allocation_get_all_by_values')
        host_allocation_get_all.return_value = []
        self.fake_phys_plugin.delete_computehost(self.fake_host_id)

        self.db_host_destroy.assert_called_once_with(self.fake_host_id)
        self.prov_delete.assert_called_once_with('hypvsr1')
        self.get_servers_per_host.assert_called_once_with(
            self.fake_host["hypervisor_hostname"])

    def test_delete_host_reserved(self):
        host_allocation_get_all = self.patch(
            self.db_api,
            'host_allocation_get_all_by_values')
        host_allocation_get_all.return_value = [
            {
                'id': 'dd305477-4df8-4547-87f6-69069ee546a6',
                'compute_host_id': self.fake_host_id
            }
        ]

        self.assertRaises(manager_exceptions.CantDeleteHost,
                          self.fake_phys_plugin.delete_computehost,
                          self.fake_host_id)

    def test_delete_host_having_vms(self):
        host_allocation_get_all = self.patch(
            self.db_api,
            'host_allocation_get_all_by_values')
        host_allocation_get_all.return_value = []
        self.get_servers_per_host.return_value = ['server1', 'server2']
        self.assertRaises(manager_exceptions.HostHavingServers,
                          self.fake_phys_plugin.delete_computehost,
                          self.fake_host_id)
        self.get_servers_per_host.assert_called_once_with(
            self.fake_host["hypervisor_hostname"])

    def test_delete_host_not_existing_in_db(self):
        self.db_host_get.return_value = None
        self.assertRaises(manager_exceptions.HostNotFound,
                          self.fake_phys_plugin.delete_computehost,
                          self.fake_host_id)

    def test_delete_host_issuing_rollback(self):
        def fake_db_host_destroy(*args, **kwargs):
            raise db_exceptions.BlazarDBException
        host_allocation_get_all = self.patch(
            self.db_api,
            'host_allocation_get_all_by_values')
        host_allocation_get_all.return_value = []
        self.db_host_destroy.side_effect = fake_db_host_destroy
        self.assertRaises(manager_exceptions.CantDeleteHost,
                          self.fake_phys_plugin.delete_computehost,
                          self.fake_host_id)

    def test_list_allocations(self):
        self.db_get_reserv_allocs = self.patch(
            self.db_utils, 'get_reservation_allocations_by_host_ids')

        self.db_host_list.return_value = [
            {'id': '3001'},
            {'id': '3002'},
            {'id': '3003'},
            {'id': '3004'},
        ]

        # Expecting a list of (Reservation, Allocation)
        self.db_get_reserv_allocs.return_value = [
            {
                'id': '1001',
                'lease_id': '2001',
                'start_date': datetime.datetime(2021, 8, 20, 20, 18),
                'end_date': datetime.datetime(2021, 8, 30, 20, 0),
                'host_ids': ['3002']
            },
            {
                'id': '1002',
                'lease_id': '2002',
                'start_date': datetime.datetime(2021, 8, 20, 16, 34),
                'end_date': datetime.datetime(2021, 8, 21, 16, 34),
                'host_ids': ['3003', '3004']
            },
            {
                'id': '1003',
                'lease_id': '2003',
                'start_date': datetime.datetime(2021, 8, 19, 20, 18),
                'end_date': datetime.datetime(2021, 8, 27, 20, 18),
                'host_ids': ['3001']
            },
            {
                'id': '1004',
                'lease_id': '2004',
                'start_date': datetime.datetime(2021, 8, 25, 20, 18),
                'end_date': datetime.datetime(2021, 8, 30, 20, 0),
                'host_ids': ['3003']
            }
        ]

        expected = [
            {
                'resource_id': '3001',
                'reservations': [
                    {
                        'id': '1003',
                        'lease_id': '2003',
                        'start_date': datetime.datetime(2021, 8, 19, 20, 18),
                        'end_date': datetime.datetime(2021, 8, 27, 20, 18)
                    }
                ]
            },
            {
                'resource_id': '3002',
                'reservations': [
                    {
                        'id': '1001',
                        'lease_id': '2001',
                        'start_date': datetime.datetime(2021, 8, 20, 20, 18),
                        'end_date': datetime.datetime(2021, 8, 30, 20, 0)
                    },
                ]
            },
            {
                'resource_id': '3003',
                'reservations': [
                    {
                        'id': '1002',
                        'lease_id': '2002',
                        'start_date': datetime.datetime(2021, 8, 20, 16, 34),
                        'end_date': datetime.datetime(2021, 8, 21, 16, 34)
                    },
                    {
                        'id': '1004',
                        'lease_id': '2004',
                        'start_date': datetime.datetime(2021, 8, 25, 20, 18),
                        'end_date': datetime.datetime(2021, 8, 30, 20, 0)
                    }
                ]
            },
            {
                'resource_id': '3004',
                'reservations': [
                    {
                        'id': '1002',
                        'lease_id': '2002',
                        'start_date': datetime.datetime(2021, 8, 20, 16, 34),
                        'end_date': datetime.datetime(2021, 8, 21, 16, 34)
                    }
                ]
            }
        ]
        ret = self.fake_phys_plugin.list_allocations({})

        # Sort returned value to use assertListEqual
        for r in ret:
            r['reservations'].sort(key=lambda x: x['id'])
        ret.sort(key=lambda x: x['resource_id'])

        self.assertListEqual(expected, ret)

    def test_list_allocations_with_lease_id(self):
        self.db_get_reserv_allocs = self.patch(
            self.db_utils, 'get_reservation_allocations_by_host_ids')

        self.db_host_list.return_value = [
            {'id': '3001'},
            {'id': '3002'},
            {'id': '3003'},
            {'id': '3004'},
        ]
        # Expecting a list of (Reservation, Allocation)
        self.db_get_reserv_allocs.return_value = [
            {
                'id': '1001',
                'lease_id': '2001',
                'start_date': datetime.datetime(2021, 8, 20, 20, 18),
                'end_date': datetime.datetime(2021, 8, 30, 20, 0),
                'host_ids': ['3002']
            },
        ]

        expected = [
            {
                'resource_id': '3001',
                'reservations': []
            },
            {
                'resource_id': '3002',
                'reservations': [
                    {
                        'id': '1001',
                        'lease_id': '2001',
                        'start_date': datetime.datetime(2021, 8, 20, 20, 18),
                        'end_date': datetime.datetime(2021, 8, 30, 20, 0)
                    }
                ]
            },
            {
                'resource_id': '3003',
                'reservations': []
            },
            {
                'resource_id': '3004',
                'reservations': []
            },
        ]
        ret = self.fake_phys_plugin.list_allocations({'lease_id': '2001'})
        # Sort returned value to use assertListEqual
        for r in ret:
            r['reservations'].sort(key=lambda x: x['id'])
        ret.sort(key=lambda x: x['resource_id'])

        self.assertListEqual(expected, ret)

    def test_list_allocations_with_reservation_id(self):
        self.db_get_reserv_allocs = self.patch(
            self.db_utils, 'get_reservation_allocations_by_host_ids')

        self.db_host_list.return_value = [
            {'id': "3001"},
            {'id': "3002"},
            {'id': "3003"},
            {'id': "3004"},
        ]
        # Expecting a list of (Reservation, Allocation)
        self.db_get_reserv_allocs.return_value = [
            {
                'id': '1002',
                'lease_id': '2002',
                'start_date': datetime.datetime(2021, 8, 20, 16, 34),
                'end_date': datetime.datetime(2021, 8, 21, 16, 34),
                'host_ids': ['3003', '3004']
            },
        ]

        expected = [
            {
                'resource_id': '3001',
                'reservations': []
            },
            {
                'resource_id': '3002',
                'reservations': []
            },
            {
                'resource_id': '3003',
                'reservations': [
                    {
                        'id': '1002',
                        'lease_id': '2002',
                        'start_date': datetime.datetime(2021, 8, 20, 16, 34),
                        'end_date': datetime.datetime(2021, 8, 21, 16, 34)
                    },
                ]
            },
            {
                'resource_id': '3004',
                'reservations': [
                    {
                        'id': '1002',
                        'lease_id': '2002',
                        'start_date': datetime.datetime(2021, 8, 20, 16, 34),
                        'end_date': datetime.datetime(2021, 8, 21, 16, 34)
                    }
                ]
            },
        ]

        ret = self.fake_phys_plugin.list_allocations(
            {'reservation_id': '1002'})

        # Sort returned value to use assertListEqual
        for r in ret:
            r['reservations'].sort(key=lambda x: x['id'])
        ret.sort(key=lambda x: x['resource_id'])

        self.assertListEqual(expected, ret)

    def test_get_allocations(self):
        self.db_get_reserv_allocs = self.patch(
            self.db_utils, 'get_reservation_allocations_by_host_ids')

        # Expecting a list of (Reservation, Allocation)
        self.db_get_reserv_allocs.return_value = [
            {
                'id': '1001',
                'lease_id': '2001',
                'start_date': datetime.datetime(2021, 8, 20, 20, 18),
                'end_date': datetime.datetime(2021, 8, 30, 20, 0),
                'host_ids': ['3002']
            },
            {
                'id': '1002',
                'lease_id': '2002',
                'start_date': datetime.datetime(2021, 8, 20, 16, 34),
                'end_date': datetime.datetime(2021, 8, 21, 16, 34),
                'host_ids': ['3003', '3004']
            },
            {
                'id': '1003',
                'lease_id': '2003',
                'start_date': datetime.datetime(2021, 8, 19, 20, 18),
                'end_date': datetime.datetime(2021, 8, 27, 20, 18),
                'host_ids': ['3001']
            },
            {
                'id': '1004',
                'lease_id': '2004',
                'start_date': datetime.datetime(2021, 8, 25, 20, 18),
                'end_date': datetime.datetime(2021, 8, 30, 20, 0),
                'host_ids': ['3003']
            }
        ]

        expected = {
            'resource_id': '3003',
            'reservations': [
                {
                    'id': '1002',
                    'lease_id': '2002',
                    'start_date': datetime.datetime(2021, 8, 20, 16, 34),
                    'end_date': datetime.datetime(2021, 8, 21, 16, 34)
                },
                {
                    'id': '1004',
                    'lease_id': '2004',
                    'start_date': datetime.datetime(2021, 8, 25, 20, 18),
                    'end_date': datetime.datetime(2021, 8, 30, 20, 0)
                }
            ]
        }
        ret = self.fake_phys_plugin.get_allocations('3003', {})

        # sort returned value to use assertListEqual
        ret['reservations'].sort(key=lambda x: x['id'])

        self.assertDictEqual(expected, ret)

    def test_get_allocations_with_lease_id(self):
        self.db_get_reserv_allocs = self.patch(
            self.db_utils, 'get_reservation_allocations_by_host_ids')

        # Expecting a list of (Reservation, Allocation)
        self.db_get_reserv_allocs.return_value = [
            {
                'id': '1001',
                'lease_id': '2001',
                'start_date': datetime.datetime(2021, 8, 20, 20, 18),
                'end_date': datetime.datetime(2021, 8, 30, 20, 0),
                'host_ids': ['3002']
            },
        ]

        expected = {
            'resource_id': '3002',
            'reservations': [
                {
                    'id': '1001',
                    'lease_id': '2001',
                    'start_date': datetime.datetime(2021, 8, 20, 20, 18),
                    'end_date': datetime.datetime(2021, 8, 30, 20, 0)
                }
            ]
        }

        ret = self.fake_phys_plugin.get_allocations('3002',
                                                    {'lease_id': '2001'})

        # sort returned value to use assertListEqual
        ret['reservations'].sort(key=lambda x: x['id'])

        self.assertDictEqual(expected, ret)

    def test_get_allocations_with_reservation_id(self):
        self.db_get_reserv_allocs = self.patch(
            self.db_utils, 'get_reservation_allocations_by_host_ids')

        # Expecting a list of (Reservation, Allocation)
        self.db_get_reserv_allocs.return_value = [
            {
                'id': '1001',
                'lease_id': '2001',
                'start_date': datetime.datetime(2021, 8, 20, 20, 18),
                'end_date': datetime.datetime(2021, 8, 30, 20, 0),
                'host_ids': ['3002']
            },
        ]

        expected = {
            'resource_id': '3002',
            'reservations': [
                {
                    'id': '1001',
                    'lease_id': '2001',
                    'start_date': datetime.datetime(2021, 8, 20, 20, 18),
                    'end_date': datetime.datetime(2021, 8, 30, 20, 0)
                }
            ]
        }
        ret = self.fake_phys_plugin.get_allocations(
            '3002', {'reservation_id': '1001'})

        # sort returned value to use assertListEqual
        ret['reservations'].sort(key=lambda x: x['id'])

        self.assertDictEqual(expected, ret)

    def test_get_allocations_with_invalid_host(self):
        self.db_get_reserv_allocs = self.patch(
            self.db_utils, 'get_reservation_allocations_by_host_ids')

        # Expecting a list of (Reservation, Allocation)
        self.db_get_reserv_allocs.return_value = [
            {
                'id': '1001',
                'lease_id': '2001',
                'start_date': datetime.datetime(2021, 8, 20, 20, 18),
                'end_date': datetime.datetime(2021, 8, 30, 20, 0),
                'host_ids': ['3002']
            },
            {
                'id': '1002',
                'lease_id': '2002',
                'start_date': datetime.datetime(2021, 8, 20, 16, 34),
                'end_date': datetime.datetime(2021, 8, 21, 16, 34),
                'host_ids': ['3003', '3004']
            },
            {
                'id': '1003',
                'lease_id': '2003',
                'start_date': datetime.datetime(2021, 8, 19, 20, 18),
                'end_date': datetime.datetime(2021, 8, 27, 20, 18),
                'host_ids': ['3001']
            },
            {
                'id': '1004',
                'lease_id': '2004',
                'start_date': datetime.datetime(2021, 8, 25, 20, 18),
                'end_date': datetime.datetime(2021, 8, 30, 20, 0),
                'host_ids': ['3003']
            }
        ]
        expected = {'resource_id': 'no-reserved-host', 'reservations': []}
        ret = self.fake_phys_plugin.get_allocations('no-reserved-host', {})

        self.assertDictEqual(expected, ret)

    def test_create_reservation_no_hosts_available(self):
        now = datetime.datetime.utcnow()
        values = {
            'lease_id': '018c1b43-e69e-4aef-a543-09681539cf4c',
            'min': 1,
            'max': 1,
            'hypervisor_properties': '["=", "$memory_mb", "256"]',
            'resource_properties': '',
            'start_date': now,
            'end_date': now + datetime.timedelta(hours=1),
            'resource_type': plugin.RESOURCE_TYPE,
        }
        host_reservation_create = self.patch(self.db_api,
                                             'host_reservation_create')
        matching_hosts = self.patch(self.fake_phys_plugin, '_matching_hosts')
        matching_hosts.return_value = []
        self.assertRaises(manager_exceptions.NotEnoughHostsAvailable,
                          self.fake_phys_plugin.reserve_resource,
                          'f9894fcf-e2ed-41e9-8a4c-92fac332608e',
                          values)
        self.rp_create.assert_not_called()
        host_reservation_create.assert_not_called()

    def test_create_reservation_hosts_available(self):
        values = {
            'lease_id': '018c1b43-e69e-4aef-a543-09681539cf4c',
            'min': 1,
            'max': 1,
            'hypervisor_properties': '["=", "$memory_mb", "256"]',
            'resource_properties': '',
            'start_date': datetime.datetime(2013, 12, 19, 20, 00),
            'end_date': datetime.datetime(2013, 12, 19, 21, 00),
            'resource_type': plugin.RESOURCE_TYPE,
        }
        self.rp_create.return_value = mock.MagicMock(id=1)
        host_reservation_create = self.patch(self.db_api,
                                             'host_reservation_create')
        matching_hosts = self.patch(self.fake_phys_plugin, '_matching_hosts')
        matching_hosts.return_value = ['host1', 'host2']
        host_allocation_create = self.patch(
            self.db_api,
            'host_allocation_create')
        self.fake_phys_plugin.reserve_resource(
            '441c1476-9f8f-4700-9f30-cd9b6fef3509',
            values)
        host_values = {
            'reservation_id': '441c1476-9f8f-4700-9f30-cd9b6fef3509',
            'aggregate_id': 1,
            'resource_properties': '',
            'hypervisor_properties': '["=", "$memory_mb", "256"]',
            'count_range': '1-1',
            'status': 'pending',
            'before_end': 'default'
        }
        host_reservation_create.assert_called_once_with(host_values)
        calls = [
            mock.call(
                {'compute_host_id': 'host1',
                 'reservation_id': '441c1476-9f8f-4700-9f30-cd9b6fef3509',
                 }),
            mock.call(
                {'compute_host_id': 'host2',
                 'reservation_id': '441c1476-9f8f-4700-9f30-cd9b6fef3509',
                 }),
        ]
        host_allocation_create.assert_has_calls(calls)

    @ddt.data("min", "max", "hypervisor_properties", "resource_properties")
    def test_create_reservation_with_missing_param(self, missing_param):
        values = {
            'lease_id': '018c1b43-e69e-4aef-a543-09681539cf4c',
            'min': 1,
            'max': 2,
            'before_end': 'default',
            'hypervisor_properties': '["=", "$memory_mb", "256"]',
            'resource_properties': '',
            'start_date': datetime.datetime(2017, 3, 1, 20, 00),
            'end_date': datetime.datetime(2017, 3, 2, 20, 00),
            'resource_type': plugin.RESOURCE_TYPE}
        del values[missing_param]
        self.assertRaises(
            manager_exceptions.MissingParameter,
            self.fake_phys_plugin.reserve_resource,
            '441c1476-9f8f-4700-9f30-cd9b6fef3509',
            values)

    @ddt.data({"params": {'max': 0}},
              {"params": {'max': -1}},
              {"params": {'max': 'one'}},
              {"params": {'min': 0}},
              {"params": {'min': -1}},
              {"params": {'min': 'one'}},
              {"params": {'before_end': 'invalid'}})
    @ddt.unpack
    def test_create_reservation_with_invalid_param(self, params):
        values = {
            'lease_id': '018c1b43-e69e-4aef-a543-09681539cf4c',
            'min': 1,
            'max': 2,
            'before_end': 'default',
            'hypervisor_properties': '["=", "$memory_mb", "256"]',
            'resource_properties': '',
            'start_date': datetime.datetime(2017, 3, 1, 20, 00),
            'end_date': datetime.datetime(2017, 3, 2, 20, 00),
            'resource_type': plugin.RESOURCE_TYPE}
        for key, value in params.items():
            values[key] = value
        self.assertRaises(
            manager_exceptions.MalformedParameter,
            self.fake_phys_plugin.reserve_resource,
            '441c1476-9f8f-4700-9f30-cd9b6fef3509',
            values)

    @ddt.data({"params": {'max': 0}},
              {"params": {'max': -1}},
              {"params": {'max': 'one'}},
              {"params": {'min': 0}},
              {"params": {'min': -1}},
              {"params": {'min': 'one'}})
    @ddt.unpack
    def test_update_reservation_with_invalid_param(self, params):
        values = {
            'lease_id': '018c1b43-e69e-4aef-a543-09681539cf4c',
            'min': 1,
            'max': 2,
            'before_end': 'default',
            'hypervisor_properties': '["=", "$memory_mb", "256"]',
            'resource_properties': '',
            'start_date': datetime.datetime(2017, 3, 1, 20, 00),
            'end_date': datetime.datetime(2017, 3, 2, 20, 00),
            'resource_type': plugin.RESOURCE_TYPE}
        self.patch(self.db_api, 'reservation_get')
        self.patch(self.db_api, 'lease_get')
        host_reservation_get = self.patch(self.db_api,
                                          'host_reservation_get')
        host_reservation_get.return_value = {
            'count_range': '1-1',
            'hypervisor_properties': '["=", "$memory_mb", "256"]',
            'resource_properties': ''
        }
        for key, value in params.items():
            values[key] = value
        self.assertRaises(
            manager_exceptions.MalformedParameter,
            self.fake_phys_plugin.update_reservation,
            '441c1476-9f8f-4700-9f30-cd9b6fef3509',
            values)

    def test_create_update_reservation_with_invalid_range(self):
        values = {
            'lease_id': '018c1b43-e69e-4aef-a543-09681539cf4c',
            'min': 2,
            'max': 1,
            'hypervisor_properties': '["=", "$memory_mb", "256"]',
            'resource_properties': '',
            'start_date': datetime.datetime(2017, 3, 1, 20, 00),
            'end_date': datetime.datetime(2017, 3, 2, 20, 00),
            'resource_type': plugin.RESOURCE_TYPE,
        }
        self.patch(self.db_api, 'reservation_get')
        self.patch(self.db_api, 'lease_get')
        host_reservation_get = self.patch(self.db_api,
                                          'host_reservation_get')
        host_reservation_get.return_value = {
            'count_range': '1-1',
            'hypervisor_properties': '["=", "$memory_mb", "256"]',
            'resource_properties': ''
        }
        self.assertRaises(
            manager_exceptions.InvalidRange,
            self.fake_phys_plugin.reserve_resource,
            '441c1476-9f8f-4700-9f30-cd9b6fef3509',
            values)
        self.assertRaises(
            manager_exceptions.InvalidRange,
            self.fake_phys_plugin.update_reservation,
            '441c1476-9f8f-4700-9f30-cd9b6fef3509',
            values)

    def test_update_reservation_shorten(self):
        values = {
            'start_date': datetime.datetime(2013, 12, 19, 20, 30),
            'end_date': datetime.datetime(2013, 12, 19, 21, 00)
        }
        reservation_get = self.patch(self.db_api, 'reservation_get')
        reservation_get.return_value = {
            'lease_id': '10870923-6d56-45c9-b592-f788053f5baa',
        }
        lease_get = self.patch(self.db_api, 'lease_get')
        lease_get.return_value = {
            'start_date': datetime.datetime(2013, 12, 19, 20, 00),
            'end_date': datetime.datetime(2013, 12, 19, 21, 00)
        }
        host_reservation_get = self.patch(self.db_api, 'host_reservation_get')

        self.fake_phys_plugin.update_reservation(
            '706eb3bc-07ed-4383-be93-b32845ece672',
            values)
        host_reservation_get.assert_not_called()

    def test_update_reservation_extend(self):
        values = {
            'start_date': datetime.datetime(2013, 12, 19, 20, 00),
            'end_date': datetime.datetime(2013, 12, 19, 21, 30)
        }
        reservation_get = self.patch(self.db_api, 'reservation_get')
        reservation_get.return_value = {
            'lease_id': '10870923-6d56-45c9-b592-f788053f5baa',
            'resource_id': '91253650-cc34-4c4f-bbe8-c943aa7d0c9b',
            'status': 'pending'
        }
        lease_get = self.patch(self.db_api, 'lease_get')
        lease_get.return_value = {
            'start_date': datetime.datetime(2013, 12, 19, 20, 00),
            'end_date': datetime.datetime(2013, 12, 19, 21, 00)
        }
        host_reservation_get = self.patch(self.db_api, 'host_reservation_get')
        host_reservation_get.return_value = {
            'count_range': '1-1',
            'hypervisor_properties': '["=", "$memory_mb", "256"]',
            'resource_properties': ''
        }
        host_allocation_get_all = self.patch(
            self.db_api,
            'host_allocation_get_all_by_values')
        host_allocation_get_all.return_value = [
            {
                'id': 'dd305477-4df8-4547-87f6-69069ee546a6',
                'compute_host_id': 'host1'
            }
        ]
        host_get_all_by_queries = self.patch(self.db_api,
                                             'host_get_all_by_queries')
        host_get_all_by_queries.return_value = [{'id': 'host1'}]
        get_reserved_periods = self.patch(self.db_utils,
                                          'get_reserved_periods')
        get_reserved_periods.return_value = [
            (datetime.datetime(2013, 12, 19, 20, 00),
             datetime.datetime(2013, 12, 19, 21, 00))
        ]
        host_allocation_create = self.patch(
            self.db_api,
            'host_allocation_create')
        host_allocation_destroy = self.patch(
            self.db_api,
            'host_allocation_destroy')

        self.fake_phys_plugin.update_reservation(
            '706eb3bc-07ed-4383-be93-b32845ece672',
            values)
        host_allocation_create.assert_not_called()
        host_allocation_destroy.assert_not_called()

    def test_update_reservation_move_failure(self):
        values = {
            'start_date': datetime.datetime(2013, 12, 20, 20, 00),
            'end_date': datetime.datetime(2013, 12, 20, 21, 30)
        }
        reservation_get = self.patch(self.db_api, 'reservation_get')
        reservation_get.return_value = {
            'lease_id': '10870923-6d56-45c9-b592-f788053f5baa',
            'resource_id': '91253650-cc34-4c4f-bbe8-c943aa7d0c9b',
            'status': 'active'
        }
        lease_get = self.patch(self.db_api, 'lease_get')
        lease_get.return_value = {
            'start_date': datetime.datetime(2013, 12, 19, 20, 00),
            'end_date': datetime.datetime(2013, 12, 19, 21, 00)
        }
        host_reservation_get = self.patch(
            self.db_api,
            'host_reservation_get')
        host_reservation_get.return_value = {
            'count_range': '1-1',
            'hypervisor_properties': '["=", "$memory_mb", "256"]',
            'resource_properties': ''
        }
        host_allocation_get_all = self.patch(
            self.db_api,
            'host_allocation_get_all_by_values')
        host_allocation_get_all.return_value = [
            {
                'id': 'dd305477-4df8-4547-87f6-69069ee546a6',
                'compute_host_id': 'host1'
            }
        ]
        host_get_all_by_queries = self.patch(self.db_api,
                                             'host_get_all_by_queries')
        host_get_all_by_queries.return_value = [{'id': 'host1'}]
        get_reserved_periods = self.patch(self.db_utils,
                                          'get_reserved_periods')
        get_reserved_periods.return_value = [
            (datetime.datetime(2013, 12, 20, 20, 30),
             datetime.datetime(2013, 12, 20, 21, 00))
        ]
        get_computehosts = self.patch(self.nova.ReservationPool,
                                      'get_computehosts')
        get_computehosts.return_value = ['host1']
        matching_hosts = self.patch(self.fake_phys_plugin, '_matching_hosts')
        matching_hosts.return_value = []
        self.assertRaises(
            manager_exceptions.NotEnoughHostsAvailable,
            self.fake_phys_plugin.update_reservation,
            '706eb3bc-07ed-4383-be93-b32845ece672',
            values)
        reservation_get.assert_called()

    def test_update_reservation_move_overlap(self):
        values = {
            'start_date': datetime.datetime(2013, 12, 19, 20, 30),
            'end_date': datetime.datetime(2013, 12, 19, 21, 30)
        }
        reservation_get = self.patch(self.db_api, 'reservation_get')
        reservation_get.return_value = {
            'lease_id': '10870923-6d56-45c9-b592-f788053f5baa',
            'resource_id': '91253650-cc34-4c4f-bbe8-c943aa7d0c9b',
            'status': 'pending'
        }
        lease_get = self.patch(self.db_api, 'lease_get')
        lease_get.return_value = {
            'start_date': datetime.datetime(2013, 12, 19, 20, 00),
            'end_date': datetime.datetime(2013, 12, 19, 21, 00)
        }
        host_reservation_get = self.patch(
            self.db_api,
            'host_reservation_get')
        host_reservation_get.return_value = {
            'count_range': '1-1',
            'hypervisor_properties': '["=", "$memory_mb", "256"]',
            'resource_properties': ''
        }
        host_allocation_get_all = self.patch(
            self.db_api,
            'host_allocation_get_all_by_values')
        host_allocation_get_all.return_value = [
            {
                'id': 'dd305477-4df8-4547-87f6-69069ee546a6',
                'compute_host_id': 'host1'
            }
        ]
        host_get_all_by_queries = self.patch(self.db_api,
                                             'host_get_all_by_queries')
        host_get_all_by_queries.return_value = [{'id': 'host1'}]
        get_reserved_periods = self.patch(self.db_utils,
                                          'get_reserved_periods')
        get_reserved_periods.return_value = [
            (datetime.datetime(2013, 12, 19, 20, 30),
             datetime.datetime(2013, 12, 19, 21, 00))
        ]
        host_allocation_create = self.patch(
            self.db_api,
            'host_allocation_create')
        host_allocation_destroy = self.patch(
            self.db_api,
            'host_allocation_destroy')

        self.fake_phys_plugin.update_reservation(
            '706eb3bc-07ed-4383-be93-b32845ece672',
            values)
        host_allocation_create.assert_not_called()
        host_allocation_destroy.assert_not_called()

    def test_update_reservation_move_realloc(self):
        values = {
            'start_date': datetime.datetime(2013, 12, 20, 20, 00),
            'end_date': datetime.datetime(2013, 12, 20, 21, 30)
        }
        reservation_get = self.patch(self.db_api, 'reservation_get')
        reservation_get.return_value = {
            'lease_id': '10870923-6d56-45c9-b592-f788053f5baa',
            'resource_id': '91253650-cc34-4c4f-bbe8-c943aa7d0c9b',
            'status': 'pending'
        }
        lease_get = self.patch(self.db_api, 'lease_get')
        lease_get.return_value = {
            'start_date': datetime.datetime(2013, 12, 19, 20, 00),
            'end_date': datetime.datetime(2013, 12, 19, 21, 00)
        }
        host_reservation_get = self.patch(
            self.db_api,
            'host_reservation_get')
        host_reservation_get.return_value = {
            'aggregate_id': 1,
            'count_range': '1-1',
            'hypervisor_properties': '["=", "$memory_mb", "256"]',
            'resource_properties': ''
        }
        host_allocation_get_all = self.patch(
            self.db_api,
            'host_allocation_get_all_by_values')
        host_allocation_get_all.return_value = [
            {
                'id': 'dd305477-4df8-4547-87f6-69069ee546a6',
                'compute_host_id': 'host1'
            }
        ]
        host_get_all_by_queries = self.patch(self.db_api,
                                             'host_get_all_by_queries')
        host_get_all_by_queries.return_value = [{'id': 'host1'},
                                                {'id': 'host2'}]
        host_allocation_create = self.patch(
            self.db_api,
            'host_allocation_create')
        host_allocation_destroy = self.patch(
            self.db_api,
            'host_allocation_destroy')
        get_reserved_periods = self.patch(self.db_utils,
                                          'get_reserved_periods')
        get_reserved_periods.return_value = [
            (datetime.datetime(2013, 12, 20, 20, 30),
             datetime.datetime(2013, 12, 20, 21, 00))
        ]
        matching_hosts = self.patch(self.fake_phys_plugin, '_matching_hosts')
        matching_hosts.return_value = ['host2']
        self.fake_phys_plugin.update_reservation(
            '706eb3bc-07ed-4383-be93-b32845ece672',
            values)
        host_reservation_get.assert_called_with(
            '91253650-cc34-4c4f-bbe8-c943aa7d0c9b')
        host_allocation_destroy.assert_called_with(
            'dd305477-4df8-4547-87f6-69069ee546a6')
        host_allocation_create.assert_called_with(
            {
                'compute_host_id': 'host2',
                'reservation_id': '706eb3bc-07ed-4383-be93-b32845ece672'
            }
        )

    def test_update_reservation_min_increase_success(self):
        values = {
            'start_date': datetime.datetime(2017, 7, 12, 20, 00),
            'end_date': datetime.datetime(2017, 7, 12, 21, 00),
            'min': 3
        }
        reservation_get = self.patch(self.db_api, 'reservation_get')
        reservation_get.return_value = {
            'lease_id': '10870923-6d56-45c9-b592-f788053f5baa',
            'resource_id': '91253650-cc34-4c4f-bbe8-c943aa7d0c9b',
            'status': 'pending'
        }
        lease_get = self.patch(self.db_api, 'lease_get')
        lease_get.return_value = {
            'start_date': datetime.datetime(2017, 7, 12, 20, 00),
            'end_date': datetime.datetime(2017, 7, 12, 21, 00)
        }
        host_reservation_get = self.patch(self.db_api, 'host_reservation_get')
        host_reservation_get.return_value = {
            'id': '91253650-cc34-4c4f-bbe8-c943aa7d0c9b',
            'count_range': '2-3',
            'hypervisor_properties': '["=", "$memory_mb", "16384"]',
            'resource_properties': ''
        }
        host_allocation_get_all = self.patch(
            self.db_api, 'host_allocation_get_all_by_values')
        host_allocation_get_all.return_value = [
            {
                'id': 'dd305477-4df8-4547-87f6-69069ee546a6',
                'compute_host_id': 'host1'
            },
            {
                'id': 'dd305477-4df8-4547-87f6-69069ee546a7',
                'compute_host_id': 'host2'
            }
        ]
        host_get_all_by_queries = self.patch(self.db_api,
                                             'host_get_all_by_queries')
        host_get_all_by_queries.return_value = [
            {'id': 'host1'},
            {'id': 'host2'},
            {'id': 'host3'}
        ]
        host_allocation_destroy = self.patch(self.db_api,
                                             'host_allocation_destroy')
        host_allocation_create = self.patch(self.db_api,
                                            'host_allocation_create')
        matching_hosts = self.patch(self.fake_phys_plugin, '_matching_hosts')
        matching_hosts.return_value = ['host3']
        host_reservation_update = self.patch(self.db_api,
                                             'host_reservation_update')

        self.fake_phys_plugin.update_reservation(
            '706eb3bc-07ed-4383-be93-b32845ece672',
            values)
        host_reservation_get.assert_called_with(
            '91253650-cc34-4c4f-bbe8-c943aa7d0c9b')
        matching_hosts.assert_called_with(
            '["=", "$memory_mb", "16384"]',
            '',
            '1-1',
            datetime.datetime(2017, 7, 12, 20, 00),
            datetime.datetime(2017, 7, 12, 21, 00)
        )
        host_allocation_destroy.assert_not_called()
        host_allocation_create.assert_called_with(
            {
                'compute_host_id': 'host3',
                'reservation_id': '706eb3bc-07ed-4383-be93-b32845ece672'
            }
        )
        host_reservation_update.assert_called_with(
            '91253650-cc34-4c4f-bbe8-c943aa7d0c9b',
            {'count_range': '3-3'}
        )

    def test_update_reservation_min_increase_fail(self):
        values = {
            'start_date': datetime.datetime(2017, 7, 12, 20, 00),
            'end_date': datetime.datetime(2017, 7, 12, 21, 00),
            'min': 3
        }
        reservation_get = self.patch(self.db_api, 'reservation_get')
        reservation_get.return_value = {
            'lease_id': '10870923-6d56-45c9-b592-f788053f5baa',
            'resource_id': '91253650-cc34-4c4f-bbe8-c943aa7d0c9b',
            'status': 'pending'
        }
        lease_get = self.patch(self.db_api, 'lease_get')
        lease_get.return_value = {
            'start_date': datetime.datetime(2017, 7, 12, 20, 00),
            'end_date': datetime.datetime(2017, 7, 12, 21, 00)
        }
        host_reservation_get = self.patch(self.db_api, 'host_reservation_get')
        host_reservation_get.return_value = {
            'id': '91253650-cc34-4c4f-bbe8-c943aa7d0c9b',
            'count_range': '2-3',
            'hypervisor_properties': '["=", "$memory_mb", "16384"]',
            'resource_properties': ''
        }
        host_allocation_get_all = self.patch(
            self.db_api, 'host_allocation_get_all_by_values')
        host_allocation_get_all.return_value = [
            {
                'id': 'dd305477-4df8-4547-87f6-69069ee546a6',
                'compute_host_id': 'host1'
            },
            {
                'id': 'dd305477-4df8-4547-87f6-69069ee546a7',
                'compute_host_id': 'host2'
            }
        ]
        host_get_all_by_queries = self.patch(self.db_api,
                                             'host_get_all_by_queries')
        host_get_all_by_queries.return_value = [
            {'id': 'host1'},
            {'id': 'host2'}
        ]
        matching_hosts = self.patch(self.fake_phys_plugin, '_matching_hosts')
        matching_hosts.return_value = []

        self.assertRaises(
            manager_exceptions.NotEnoughHostsAvailable,
            self.fake_phys_plugin.update_reservation,
            '706eb3bc-07ed-4383-be93-b32845ece672',
            values)
        matching_hosts.assert_called_with(
            '["=", "$memory_mb", "16384"]',
            '',
            '1-1',
            datetime.datetime(2017, 7, 12, 20, 00),
            datetime.datetime(2017, 7, 12, 21, 00)
        )

    def test_update_reservation_min_decrease(self):
        values = {
            'start_date': datetime.datetime(2017, 7, 12, 20, 00),
            'end_date': datetime.datetime(2017, 7, 12, 21, 00),
            'min': 1
        }
        reservation_get = self.patch(self.db_api, 'reservation_get')
        reservation_get.return_value = {
            'lease_id': '10870923-6d56-45c9-b592-f788053f5baa',
            'resource_id': '91253650-cc34-4c4f-bbe8-c943aa7d0c9b',
            'status': 'pending'
        }
        lease_get = self.patch(self.db_api, 'lease_get')
        lease_get.return_value = {
            'start_date': datetime.datetime(2017, 7, 12, 20, 00),
            'end_date': datetime.datetime(2017, 7, 12, 21, 00)
        }
        host_reservation_get = self.patch(self.db_api, 'host_reservation_get')
        host_reservation_get.return_value = {
            'id': '91253650-cc34-4c4f-bbe8-c943aa7d0c9b',
            'count_range': '2-2',
            'hypervisor_properties': '["=", "$memory_mb", "16384"]',
            'resource_properties': ''
        }
        host_allocation_get_all = self.patch(
            self.db_api, 'host_allocation_get_all_by_values')
        host_allocation_get_all.return_value = [
            {
                'id': 'dd305477-4df8-4547-87f6-69069ee546a6',
                'compute_host_id': 'host1'
            },
            {
                'id': 'dd305477-4df8-4547-87f6-69069ee546a7',
                'compute_host_id': 'host2'
            }
        ]
        host_get_all_by_queries = self.patch(self.db_api,
                                             'host_get_all_by_queries')
        host_get_all_by_queries.return_value = [
            {'id': 'host1'},
            {'id': 'host2'}
        ]
        matching_hosts = self.patch(self.fake_phys_plugin, '_matching_hosts')
        host_allocation_destroy = self.patch(self.db_api,
                                             'host_allocation_destroy')
        host_allocation_create = self.patch(self.db_api,
                                            'host_allocation_create')
        host_reservation_update = self.patch(self.db_api,
                                             'host_reservation_update')

        self.fake_phys_plugin.update_reservation(
            '706eb3bc-07ed-4383-be93-b32845ece672',
            values)
        matching_hosts.assert_not_called()
        host_allocation_destroy.assert_not_called()
        host_allocation_create.assert_not_called()
        host_reservation_update.assert_called_with(
            '91253650-cc34-4c4f-bbe8-c943aa7d0c9b',
            {'count_range': '1-2'}
        )

    def test_update_reservation_max_increase_alloc(self):
        values = {
            'start_date': datetime.datetime(2017, 7, 12, 20, 00),
            'end_date': datetime.datetime(2017, 7, 12, 21, 00),
            'max': 3
        }
        reservation_get = self.patch(self.db_api, 'reservation_get')
        reservation_get.return_value = {
            'lease_id': '10870923-6d56-45c9-b592-f788053f5baa',
            'resource_id': '91253650-cc34-4c4f-bbe8-c943aa7d0c9b',
            'status': 'pending'
        }
        lease_get = self.patch(self.db_api, 'lease_get')
        lease_get.return_value = {
            'start_date': datetime.datetime(2017, 7, 12, 20, 00),
            'end_date': datetime.datetime(2017, 7, 12, 21, 00)
        }
        host_reservation_get = self.patch(self.db_api, 'host_reservation_get')
        host_reservation_get.return_value = {
            'id': '91253650-cc34-4c4f-bbe8-c943aa7d0c9b',
            'count_range': '1-2',
            'hypervisor_properties': '["=", "$memory_mb", "16384"]',
            'resource_properties': ''
        }
        host_allocation_get_all = self.patch(
            self.db_api, 'host_allocation_get_all_by_values')
        host_allocation_get_all.return_value = [
            {
                'id': 'dd305477-4df8-4547-87f6-69069ee546a6',
                'compute_host_id': 'host1'
            },
            {
                'id': 'dd305477-4df8-4547-87f6-69069ee546a7',
                'compute_host_id': 'host2'
            }
        ]
        host_get_all_by_queries = self.patch(self.db_api,
                                             'host_get_all_by_queries')
        host_get_all_by_queries.return_value = [
            {'id': 'host1'},
            {'id': 'host2'},
            {'id': 'host3'}
        ]
        host_allocation_destroy = self.patch(self.db_api,
                                             'host_allocation_destroy')
        host_allocation_create = self.patch(self.db_api,
                                            'host_allocation_create')
        matching_hosts = self.patch(self.fake_phys_plugin, '_matching_hosts')
        matching_hosts.return_value = ['host3']
        host_reservation_update = self.patch(self.db_api,
                                             'host_reservation_update')

        self.fake_phys_plugin.update_reservation(
            '706eb3bc-07ed-4383-be93-b32845ece672',
            values)
        host_reservation_get.assert_called_with(
            '91253650-cc34-4c4f-bbe8-c943aa7d0c9b')
        matching_hosts.assert_called_with(
            '["=", "$memory_mb", "16384"]',
            '',
            '0-1',
            datetime.datetime(2017, 7, 12, 20, 00),
            datetime.datetime(2017, 7, 12, 21, 00)
        )
        host_allocation_destroy.assert_not_called()
        host_allocation_create.assert_called_with(
            {
                'compute_host_id': 'host3',
                'reservation_id': '706eb3bc-07ed-4383-be93-b32845ece672'
            }
        )
        host_reservation_update.assert_called_with(
            '91253650-cc34-4c4f-bbe8-c943aa7d0c9b',
            {'count_range': '1-3'}
        )

    def test_update_active_reservation_max_increase_alloc(self):
        values = {
            'start_date': datetime.datetime(2017, 7, 12, 20, 00),
            'end_date': datetime.datetime(2017, 7, 12, 21, 00),
            'max': 3
        }
        reservation_get = self.patch(self.db_api, 'reservation_get')
        reservation_get.return_value = {
            'lease_id': '10870923-6d56-45c9-b592-f788053f5baa',
            'resource_id': '91253650-cc34-4c4f-bbe8-c943aa7d0c9b',
            'status': 'active'
        }
        lease_get = self.patch(self.db_api, 'lease_get')
        lease_get.return_value = {
            'start_date': datetime.datetime(2017, 7, 12, 20, 00),
            'end_date': datetime.datetime(2017, 7, 12, 21, 00)
        }
        host_reservation_get = self.patch(self.db_api, 'host_reservation_get')
        host_reservation_get.return_value = {
            'id': '91253650-cc34-4c4f-bbe8-c943aa7d0c9b',
            'count_range': '1-2',
            'hypervisor_properties': '["=", "$memory_mb", "16384"]',
            'resource_properties': '',
            'reservation_id': '706eb3bc-07ed-4383-be93-b32845ece672',
            'aggregate_id': 1,
        }
        host_allocation_get_all = self.patch(
            self.db_api, 'host_allocation_get_all_by_values')
        host_allocation_get_all.return_value = [
            {
                'id': 'dd305477-4df8-4547-87f6-69069ee546a6',
                'compute_host_id': 'host1'
            },
            {
                'id': 'dd305477-4df8-4547-87f6-69069ee546a7',
                'compute_host_id': 'host2'
            }
        ]
        host_get_all_by_queries = self.patch(self.db_api,
                                             'host_get_all_by_queries')
        host_get_all_by_queries.return_value = [
            {'id': 'host1'},
            {'id': 'host2'},
            {'id': 'host3'}
        ]
        host_allocation_destroy = self.patch(self.db_api,
                                             'host_allocation_destroy')
        host_allocation_create = self.patch(self.db_api,
                                            'host_allocation_create')
        matching_hosts = self.patch(self.fake_phys_plugin, '_matching_hosts')
        matching_hosts.return_value = ['host3']
        host_get = self.patch(self.db_api, 'host_get')
        host_get.return_value = {'service_name': 'host3_hostname'}
        add_computehost = self.patch(
            self.nova.ReservationPool, 'add_computehost')
        host_reservation_update = self.patch(self.db_api,
                                             'host_reservation_update')

        self.fake_phys_plugin.update_reservation(
            '706eb3bc-07ed-4383-be93-b32845ece672',
            values)
        host_reservation_get.assert_called_with(
            '91253650-cc34-4c4f-bbe8-c943aa7d0c9b')
        matching_hosts.assert_called_with(
            '["=", "$memory_mb", "16384"]',
            '',
            '0-1',
            datetime.datetime(2017, 7, 12, 20, 00),
            datetime.datetime(2017, 7, 12, 21, 00)
        )
        host_allocation_destroy.assert_not_called()
        host_allocation_create.assert_called_with(
            {
                'compute_host_id': 'host3',
                'reservation_id': '706eb3bc-07ed-4383-be93-b32845ece672'
            }
        )
        add_computehost.assert_called_with(1, ['host3_hostname'])
        host_reservation_update.assert_called_with(
            '91253650-cc34-4c4f-bbe8-c943aa7d0c9b',
            {'count_range': '1-3'}
        )

    def test_update_reservation_max_increase_noalloc(self):
        values = {
            'start_date': datetime.datetime(2017, 7, 12, 20, 00),
            'end_date': datetime.datetime(2017, 7, 12, 21, 00),
            'max': 3
        }
        reservation_get = self.patch(self.db_api, 'reservation_get')
        reservation_get.return_value = {
            'lease_id': '10870923-6d56-45c9-b592-f788053f5baa',
            'resource_id': '91253650-cc34-4c4f-bbe8-c943aa7d0c9b',
            'status': 'pending'
        }
        lease_get = self.patch(self.db_api, 'lease_get')
        lease_get.return_value = {
            'start_date': datetime.datetime(2017, 7, 12, 20, 00),
            'end_date': datetime.datetime(2017, 7, 12, 21, 00)
        }
        host_reservation_get = self.patch(self.db_api, 'host_reservation_get')
        host_reservation_get.return_value = {
            'id': '91253650-cc34-4c4f-bbe8-c943aa7d0c9b',
            'count_range': '1-2',
            'hypervisor_properties': '["=", "$memory_mb", "16384"]',
            'resource_properties': ''
        }
        host_allocation_get_all = self.patch(
            self.db_api, 'host_allocation_get_all_by_values')
        host_allocation_get_all.return_value = [
            {
                'id': 'dd305477-4df8-4547-87f6-69069ee546a6',
                'compute_host_id': 'host1'
            },
            {
                'id': 'dd305477-4df8-4547-87f6-69069ee546a7',
                'compute_host_id': 'host2'
            }
        ]
        host_get_all_by_queries = self.patch(self.db_api,
                                             'host_get_all_by_queries')
        host_get_all_by_queries.return_value = [
            {'id': 'host1'},
            {'id': 'host2'}
        ]
        matching_hosts = self.patch(self.fake_phys_plugin, '_matching_hosts')
        matching_hosts.return_value = []
        host_reservation_update = self.patch(self.db_api,
                                             'host_reservation_update')

        self.fake_phys_plugin.update_reservation(
            '706eb3bc-07ed-4383-be93-b32845ece672',
            values)
        host_reservation_get.assert_called_with(
            '91253650-cc34-4c4f-bbe8-c943aa7d0c9b')
        matching_hosts.assert_called_with(
            '["=", "$memory_mb", "16384"]',
            '',
            '0-1',
            datetime.datetime(2017, 7, 12, 20, 00),
            datetime.datetime(2017, 7, 12, 21, 00)
        )
        host_reservation_update.assert_called_with(
            '91253650-cc34-4c4f-bbe8-c943aa7d0c9b',
            {'count_range': '1-3'}
        )

    def test_update_reservation_max_decrease(self):
        values = {
            'start_date': datetime.datetime(2017, 7, 12, 20, 00),
            'end_date': datetime.datetime(2017, 7, 12, 21, 00),
            'max': 1
        }
        reservation_get = self.patch(self.db_api, 'reservation_get')
        reservation_get.return_value = {
            'lease_id': '10870923-6d56-45c9-b592-f788053f5baa',
            'resource_id': '91253650-cc34-4c4f-bbe8-c943aa7d0c9b',
            'status': 'pending'
        }
        lease_get = self.patch(self.db_api, 'lease_get')
        lease_get.return_value = {
            'start_date': datetime.datetime(2017, 7, 12, 20, 00),
            'end_date': datetime.datetime(2017, 7, 12, 21, 00)
        }
        host_reservation_get = self.patch(self.db_api, 'host_reservation_get')
        host_reservation_get.return_value = {
            'id': '91253650-cc34-4c4f-bbe8-c943aa7d0c9b',
            'count_range': '1-2',
            'hypervisor_properties': '["=", "$memory_mb", "16384"]',
            'resource_properties': ''
        }
        host_allocation_get_all = self.patch(
            self.db_api, 'host_allocation_get_all_by_values')
        host_allocation_get_all.return_value = [
            {
                'id': 'dd305477-4df8-4547-87f6-69069ee546a6',
                'compute_host_id': 'host1'
            },
            {
                'id': 'dd305477-4df8-4547-87f6-69069ee546a7',
                'compute_host_id': 'host2'
            }
        ]
        host_get_all_by_queries = self.patch(self.db_api,
                                             'host_get_all_by_queries')
        host_get_all_by_queries.return_value = [
            {'id': 'host1'},
            {'id': 'host2'}
        ]
        host_allocation_destroy = self.patch(self.db_api,
                                             'host_allocation_destroy')
        host_reservation_update = self.patch(self.db_api,
                                             'host_reservation_update')

        self.fake_phys_plugin.update_reservation(
            '706eb3bc-07ed-4383-be93-b32845ece672',
            values)
        host_reservation_get.assert_called_with(
            '91253650-cc34-4c4f-bbe8-c943aa7d0c9b')
        host_allocation_destroy.assert_called_with(
            'dd305477-4df8-4547-87f6-69069ee546a6')
        host_reservation_update.assert_called_with(
            '91253650-cc34-4c4f-bbe8-c943aa7d0c9b',
            {'count_range': '1-1'}
        )

    def test_update_reservation_realloc_with_properties_change(self):
        values = {
            'start_date': datetime.datetime(2017, 7, 12, 20, 00),
            'end_date': datetime.datetime(2017, 7, 12, 21, 00),
            'hypervisor_properties': '["=", "$memory_mb", "32768"]',
        }
        reservation_get = self.patch(self.db_api, 'reservation_get')
        reservation_get.return_value = {
            'lease_id': '10870923-6d56-45c9-b592-f788053f5baa',
            'resource_id': '91253650-cc34-4c4f-bbe8-c943aa7d0c9b',
            'status': 'pending'
        }
        lease_get = self.patch(self.db_api, 'lease_get')
        lease_get.return_value = {
            'start_date': datetime.datetime(2017, 7, 12, 20, 00),
            'end_date': datetime.datetime(2017, 7, 12, 21, 00)
        }
        host_reservation_get = self.patch(self.db_api, 'host_reservation_get')
        host_reservation_get.return_value = {
            'id': '91253650-cc34-4c4f-bbe8-c943aa7d0c9b',
            'count_range': '1-1',
            'hypervisor_properties': '["=", "$memory_mb", "16384"]',
            'resource_properties': ''
        }
        host_allocation_get_all = self.patch(
            self.db_api, 'host_allocation_get_all_by_values')
        host_allocation_get_all.return_value = [
            {
                'id': 'dd305477-4df8-4547-87f6-69069ee546a6',
                'compute_host_id': 'host1'
            }
        ]
        host_get_all_by_queries = self.patch(self.db_api,
                                             'host_get_all_by_queries')
        host_get_all_by_queries.return_value = [{'id': 'host2'}]
        matching_hosts = self.patch(self.fake_phys_plugin, '_matching_hosts')
        matching_hosts.return_value = ['host2']
        host_allocation_create = self.patch(self.db_api,
                                            'host_allocation_create')
        host_allocation_destroy = self.patch(self.db_api,
                                             'host_allocation_destroy')
        host_reservation_update = self.patch(self.db_api,
                                             'host_reservation_update')

        self.fake_phys_plugin.update_reservation(
            '706eb3bc-07ed-4383-be93-b32845ece672',
            values)
        host_reservation_get.assert_called_with(
            '91253650-cc34-4c4f-bbe8-c943aa7d0c9b')
        matching_hosts.assert_called_with(
            '["=", "$memory_mb", "32768"]',
            '',
            '1-1',
            datetime.datetime(2017, 7, 12, 20, 00),
            datetime.datetime(2017, 7, 12, 21, 00)
        )
        host_allocation_create.assert_called_with(
            {
                'compute_host_id': 'host2',
                'reservation_id': '706eb3bc-07ed-4383-be93-b32845ece672'
            }
        )
        host_allocation_destroy.assert_called_with(
            'dd305477-4df8-4547-87f6-69069ee546a6'
        )
        host_reservation_update.assert_called_with(
            '91253650-cc34-4c4f-bbe8-c943aa7d0c9b',
            {'hypervisor_properties': '["=", "$memory_mb", "32768"]'}
        )

    def test_update_reservation_no_requested_hosts_available(self):
        values = {
            'start_date': datetime.datetime(2017, 7, 12, 20, 00),
            'end_date': datetime.datetime(2017, 7, 12, 21, 00),
            'resource_properties': '[">=", "$vcpus", "32768"]'
        }
        reservation_get = self.patch(self.db_api, 'reservation_get')
        reservation_get.return_value = {
            'lease_id': '10870923-6d56-45c9-b592-f788053f5baa',
            'resource_id': '91253650-cc34-4c4f-bbe8-c943aa7d0c9b',
            'status': 'pending'
        }
        lease_get = self.patch(self.db_api, 'lease_get')
        lease_get.return_value = {
            'start_date': datetime.datetime(2013, 12, 19, 20, 00),
            'end_date': datetime.datetime(2013, 12, 19, 21, 00)
        }
        host_reservation_get = self.patch(self.db_api, 'host_reservation_get')
        host_reservation_get.return_value = {
            'id': '91253650-cc34-4c4f-bbe8-c943aa7d0c9b',
            'count_range': '1-1',
            'hypervisor_properties': '["=", "$memory_mb", "16384"]',
            'resource_properties': ''
        }
        host_allocation_get_all = self.patch(
            self.db_api, 'host_allocation_get_all_by_values')
        host_allocation_get_all.return_value = [
            {
                'id': 'dd305477-4df8-4547-87f6-69069ee546a6',
                'compute_host_id': 'host1'
            }
        ]
        host_get_all_by_queries = self.patch(self.db_api,
                                             'host_get_all_by_queries')
        host_get_all_by_queries.return_value = []
        matching_hosts = self.patch(self.fake_phys_plugin, '_matching_hosts')
        matching_hosts.return_value = []

        self.assertRaises(
            manager_exceptions.NotEnoughHostsAvailable,
            self.fake_phys_plugin.update_reservation,
            '441c1476-9f8f-4700-9f30-cd9b6fef3509',
            values)

    def test_on_start(self):
        host_reservation_get = self.patch(self.db_api, 'host_reservation_get')
        host_reservation_get.return_value = {
            'reservation_id': '593e7028-c0d1-4d76-8642-2ffd890b324c',
            'aggregate_id': 1,
        }
        host_allocation_get_all_by_values = self.patch(
            self.db_api, 'host_allocation_get_all_by_values')
        host_allocation_get_all_by_values.return_value = [
            {'compute_host_id': 'host1'},
        ]
        host_get = self.patch(self.db_api, 'host_get')
        host_get.return_value = {'service_name': 'host1_hostname'}
        add_computehost = self.patch(
            self.nova.ReservationPool, 'add_computehost')

        self.fake_phys_plugin.on_start('04de74e8-193a-49d2-9ab8-cba7b49e45e8')

        add_computehost.assert_called_with(1, ['host1_hostname'])

    def test_before_end_with_no_action(self):
        host_reservation_get = self.patch(self.db_api, 'host_reservation_get')
        host_reservation_get.return_value = {'before_end': ''}
        reservationpool = self.patch(self.nova, 'ReservationPool')
        self.fake_phys_plugin.before_end(
            '04de74e8-193a-49d2-9ab8-cba7b49e45e8')
        reservationpool.assert_not_called()

    def test_before_end_with_snapshot(self):
        host_reservation_get = self.patch(self.db_api, 'host_reservation_get')
        host_reservation_get.return_value = {
            'aggregate_id': 1,
            'before_end': 'snapshot'
        }
        get_computehosts = self.patch(self.nova.ReservationPool,
                                      'get_computehosts')
        get_computehosts.return_value = ['host']
        list_servers = self.patch(self.ServerManager, 'list')
        list_servers.return_value = ['server1', 'server2']
        create_image = self.patch(self.ServerManager, 'create_image')
        self.fake_phys_plugin.before_end(
            '04de74e8-193a-49d2-9ab8-cba7b49e45e8')
        create_image.assert_any_call(server='server1')
        create_image.assert_any_call(server='server2')

    def test_on_end_with_instances(self):
        host_reservation_get = self.patch(self.db_api, 'host_reservation_get')
        host_reservation_get.return_value = {
            'id': '04de74e8-193a-49d2-9ab8-cba7b49e45e8',
            'reservation_id': '593e7028-c0d1-4d76-8642-2ffd890b324c',
            'aggregate_id': 1
        }
        host_reservation_update = self.patch(
            self.db_api,
            'host_reservation_update')
        host_allocation_get_all_by_values = self.patch(
            self.db_api,
            'host_allocation_get_all_by_values')
        host_allocation_get_all_by_values.return_value = [
            {'id': 'bfa9aa0b-8042-43eb-a4e6-4555838bf64f',
             'compute_host_id': 'cdae2a65-236f-475a-977d-f6ad82f828b7',
             },
        ]
        host_allocation_destroy = self.patch(
            self.db_api,
            'host_allocation_destroy')
        get_computehosts = self.patch(self.nova.ReservationPool,
                                      'get_computehosts')
        get_computehosts.return_value = ['host']
        list_servers = self.patch(self.ServerManager, 'list')
        list_servers.return_value = ['server1', 'server2']
        delete_server = self.patch(self.ServerManager, 'delete')
        # Mock delete_server so the first call fails to find the instance.
        # This can happen when the user is deleting instances concurrently.
        delete_server.side_effect = mock.Mock(
            side_effect=[nova_exceptions.NotFound(
                404, 'Instance server1 could not be found.'), None])
        delete_pool = self.patch(self.nova.ReservationPool, 'delete')
        self.fake_phys_plugin.on_end('04de74e8-193a-49d2-9ab8-cba7b49e45e8')
        host_reservation_update.assert_called_with(
            '04de74e8-193a-49d2-9ab8-cba7b49e45e8', {'status': 'completed'})
        host_allocation_destroy.assert_called_with(
            'bfa9aa0b-8042-43eb-a4e6-4555838bf64f')
        list_servers.assert_called_with(search_opts={'host': 'host',
                                                     'all_tenants': 1})
        delete_server.assert_any_call(server='server1')
        delete_server.assert_any_call(server='server2')
        delete_pool.assert_called_with(1)

    def test_on_end_without_instances(self):
        host_reservation_get = self.patch(self.db_api, 'host_reservation_get')
        host_reservation_get.return_value = {
            'id': '04de74e8-193a-49d2-9ab8-cba7b49e45e8',
            'reservation_id': '593e7028-c0d1-4d76-8642-2ffd890b324c',
            'aggregate_id': 1
        }
        host_reservation_update = self.patch(
            self.db_api,
            'host_reservation_update')
        host_allocation_get_all_by_values = self.patch(
            self.db_api,
            'host_allocation_get_all_by_values')
        host_allocation_get_all_by_values.return_value = [
            {'id': 'bfa9aa0b-8042-43eb-a4e6-4555838bf64f',
             'compute_host_id': 'cdae2a65-236f-475a-977d-f6ad82f828b7',
             },
        ]
        host_allocation_destroy = self.patch(
            self.db_api,
            'host_allocation_destroy')
        get_computehosts = self.patch(self.nova.ReservationPool,
                                      'get_computehosts')
        get_computehosts.return_value = ['host']
        list_servers = self.patch(self.ServerManager, 'list')
        list_servers.return_value = []
        delete_server = self.patch(self.ServerManager, 'delete')
        delete_pool = self.patch(self.nova.ReservationPool, 'delete')
        self.fake_phys_plugin.on_end('04de74e8-193a-49d2-9ab8-cba7b49e45e8')
        host_reservation_update.assert_called_with(
            '04de74e8-193a-49d2-9ab8-cba7b49e45e8', {'status': 'completed'})
        host_allocation_destroy.assert_called_with(
            'bfa9aa0b-8042-43eb-a4e6-4555838bf64f')
        delete_server.assert_not_called()
        delete_pool.assert_called_with(1)

    def test_heal_reservations_before_start_and_resources_changed(self):
        failed_host = {'id': '1'}
        dummy_reservation = {
            'id': 'rsrv-1',
            'resource_type': plugin.RESOURCE_TYPE,
            'lease_id': 'lease-1',
            'status': 'pending',
            'hypervisor_properties': [],
            'resource_properties': [],
            'resource_id': 'resource-1',
            'computehost_allocations': [{
                'id': 'alloc-1', 'compute_host_id': failed_host['id'],
                'reservation_id': 'rsrv-1'
            }]
        }
        get_reservations = self.patch(self.db_utils,
                                      'get_reservations_by_host_ids')
        get_reservations.return_value = [dummy_reservation]
        reallocate = self.patch(self.fake_phys_plugin, '_reallocate')
        reallocate.return_value = True

        result = self.fake_phys_plugin.heal_reservations(
            [failed_host],
            datetime.datetime(2020, 1, 1, 12, 00),
            datetime.datetime(2020, 1, 1, 13, 00))
        reallocate.assert_called_once_with(
            dummy_reservation['computehost_allocations'][0])
        self.assertEqual({}, result)

    def test_heal_reservations_before_start_and_missing_resources(self):
        failed_host = {'id': '1'}
        dummy_reservation = {
            'id': 'rsrv-1',
            'resource_type': plugin.RESOURCE_TYPE,
            'lease_id': 'lease-1',
            'status': 'pending',
            'hypervisor_properties': [],
            'resource_properties': [],
            'resource_id': 'resource-1',
            'computehost_allocations': [{
                'id': 'alloc-1', 'compute_host_id': failed_host['id'],
                'reservation_id': 'rsrv-1'
            }]
        }
        get_reservations = self.patch(self.db_utils,
                                      'get_reservations_by_host_ids')
        get_reservations.return_value = [dummy_reservation]
        reallocate = self.patch(self.fake_phys_plugin, '_reallocate')
        reallocate.return_value = False

        result = self.fake_phys_plugin.heal_reservations(
            [failed_host],
            datetime.datetime(2020, 1, 1, 12, 00),
            datetime.datetime(2020, 1, 1, 13, 00))
        reallocate.assert_called_once_with(
            dummy_reservation['computehost_allocations'][0])
        self.assertEqual(
            {dummy_reservation['id']: {'missing_resources': True}},
            result)

    def test_heal_active_reservations_and_resources_changed(self):
        failed_host = {'id': '1'}
        dummy_reservation = {
            'id': 'rsrv-1',
            'resource_type': plugin.RESOURCE_TYPE,
            'lease_id': 'lease-1',
            'status': 'active',
            'hypervisor_properties': [],
            'resource_properties': [],
            'resource_id': 'resource-1',
            'computehost_allocations': [{
                'id': 'alloc-1', 'compute_host_id': failed_host['id'],
                'reservation_id': 'rsrv-1'
            }]
        }
        get_reservations = self.patch(self.db_utils,
                                      'get_reservations_by_host_ids')
        get_reservations.return_value = [dummy_reservation]
        reallocate = self.patch(self.fake_phys_plugin, '_reallocate')
        reallocate.return_value = True

        result = self.fake_phys_plugin.heal_reservations(
            [failed_host],
            datetime.datetime(2020, 1, 1, 12, 00),
            datetime.datetime(2020, 1, 1, 13, 00))
        reallocate.assert_called_once_with(
            dummy_reservation['computehost_allocations'][0])
        self.assertEqual(
            {dummy_reservation['id']: {'resources_changed': True}},
            result)

    def test_heal_active_reservations_and_missing_resources(self):
        failed_host = {'id': '1'}
        dummy_reservation = {
            'id': 'rsrv-1',
            'resource_type': plugin.RESOURCE_TYPE,
            'lease_id': 'lease-1',
            'status': 'active',
            'hypervisor_properties': [],
            'resource_properties': [],
            'resource_id': 'resource-1',
            'computehost_allocations': [{
                'id': 'alloc-1', 'compute_host_id': failed_host['id'],
                'reservation_id': 'rsrv-1'
            }]
        }
        get_reservations = self.patch(self.db_utils,
                                      'get_reservations_by_host_ids')
        get_reservations.return_value = [dummy_reservation]
        reallocate = self.patch(self.fake_phys_plugin, '_reallocate')
        reallocate.return_value = False

        result = self.fake_phys_plugin.heal_reservations(
            [failed_host],
            datetime.datetime(2020, 1, 1, 12, 00),
            datetime.datetime(2020, 1, 1, 13, 00))
        reallocate.assert_called_once_with(
            dummy_reservation['computehost_allocations'][0])
        self.assertEqual(
            {dummy_reservation['id']: {'missing_resources': True}},
            result)

    def test_reallocate_before_start(self):
        failed_host = {'id': '1'}
        new_host = {'id': '2'}
        dummy_allocation = {
            'id': 'alloc-1',
            'compute_host_id': failed_host['id'],
            'reservation_id': 'rsrv-1'
        }
        dummy_reservation = {
            'id': 'rsrv-1',
            'resource_type': plugin.RESOURCE_TYPE,
            'lease_id': 'lease-1',
            'status': 'pending',
            'hypervisor_properties': [],
            'resource_properties': [],
            'resource_id': 'resource-1'
        }
        dummy_host_reservation = {
            'aggregate_id': 1
        }
        dummy_lease = {
            'name': 'lease-name',
            'start_date': datetime.datetime(2020, 1, 1, 12, 00),
            'end_date': datetime.datetime(2020, 1, 2, 12, 00),
            'trust_id': 'trust-1'
        }
        reservation_get = self.patch(self.db_api, 'reservation_get')
        reservation_get.return_value = dummy_reservation
        host_reservation_get = self.patch(self.db_api, 'host_reservation_get')
        host_reservation_get.return_value = dummy_host_reservation
        lease_get = self.patch(self.db_api, 'lease_get')
        lease_get.return_value = dummy_lease
        matching_hosts = self.patch(host_plugin.PhysicalHostPlugin,
                                    '_matching_hosts')
        matching_hosts.return_value = [new_host['id']]
        alloc_update = self.patch(self.db_api, 'host_allocation_update')

        with mock.patch.object(datetime, 'datetime',
                               mock.Mock(wraps=datetime.datetime)) as patched:
            patched.utcnow.return_value = datetime.datetime(
                2020, 1, 1, 11, 00)
            result = self.fake_phys_plugin._reallocate(dummy_allocation)

        matching_hosts.assert_called_once_with(
            dummy_reservation['hypervisor_properties'],
            dummy_reservation['resource_properties'],
            '1-1', dummy_lease['start_date'], dummy_lease['end_date'])
        alloc_update.assert_called_once_with(
            dummy_allocation['id'],
            {'compute_host_id': new_host['id']})
        self.assertEqual(True, result)

    def test_reallocate_active(self):
        failed_host = {'id': '1',
                       'service_name': 'compute-1'}
        new_host = {'id': '2',
                    'service_name': 'compute-2'}
        dummy_allocation = {
            'id': 'alloc-1',
            'compute_host_id': failed_host['id'],
            'reservation_id': 'rsrv-1'
        }
        dummy_reservation = {
            'id': 'rsrv-1',
            'resource_type': plugin.RESOURCE_TYPE,
            'lease_id': 'lease-1',
            'status': 'active',
            'hypervisor_properties': [],
            'resource_properties': [],
            'resource_id': 'resource-1'
        }
        dummy_host_reservation = {
            'aggregate_id': 1
        }
        dummy_lease = {
            'name': 'lease-name',
            'start_date': datetime.datetime(2020, 1, 1, 12, 00),
            'end_date': datetime.datetime(2020, 1, 2, 12, 00),
            'trust_id': 'trust-1'
        }
        reservation_get = self.patch(self.db_api, 'reservation_get')
        reservation_get.return_value = dummy_reservation
        lease_get = self.patch(self.db_api, 'lease_get')
        lease_get.return_value = dummy_lease
        host_reservation_get = self.patch(self.db_api, 'host_reservation_get')
        host_reservation_get.return_value = dummy_host_reservation
        host_get = self.patch(self.db_api, 'host_get')
        host_get.side_effect = [failed_host, new_host]
        matching_hosts = self.patch(host_plugin.PhysicalHostPlugin,
                                    '_matching_hosts')
        matching_hosts.return_value = [new_host['id']]
        alloc_update = self.patch(self.db_api, 'host_allocation_update')

        with mock.patch.object(datetime, 'datetime',
                               mock.Mock(wraps=datetime.datetime)) as patched:
            patched.utcnow.return_value = datetime.datetime(
                2020, 1, 1, 13, 00)
            result = self.fake_phys_plugin._reallocate(dummy_allocation)

        self.remove_compute_host.assert_called_once_with(
            dummy_host_reservation['aggregate_id'],
            failed_host['service_name'])
        matching_hosts.assert_called_once_with(
            dummy_reservation['hypervisor_properties'],
            dummy_reservation['resource_properties'],
            '1-1', datetime.datetime(2020, 1, 1, 13, 00),
            dummy_lease['end_date'])
        alloc_update.assert_called_once_with(
            dummy_allocation['id'],
            {'compute_host_id': new_host['id']})
        self.add_compute_host(
            dummy_host_reservation['aggregate_id'],
            new_host['service_name'])
        self.assertEqual(True, result)

    def test_reallocate_missing_resources(self):
        failed_host = {'id': '1'}
        dummy_allocation = {
            'id': 'alloc-1',
            'compute_host_id': failed_host['id'],
            'reservation_id': 'rsrv-1'
        }
        dummy_reservation = {
            'id': 'rsrv-1',
            'resource_type': plugin.RESOURCE_TYPE,
            'lease_id': 'lease-1',
            'status': 'pending',
            'hypervisor_properties': [],
            'resource_properties': [],
            'resource_id': 'resource-1'
        }
        dummy_host_reservation = {
            'aggregate_id': 1
        }
        dummy_lease = {
            'name': 'lease-name',
            'start_date': datetime.datetime(2020, 1, 1, 12, 00),
            'end_date': datetime.datetime(2020, 1, 2, 12, 00),
            'trust_id': 'trust-1'
        }
        reservation_get = self.patch(self.db_api, 'reservation_get')
        reservation_get.return_value = dummy_reservation
        host_reservation_get = self.patch(self.db_api, 'host_reservation_get')
        host_reservation_get.return_value = dummy_host_reservation
        lease_get = self.patch(self.db_api, 'lease_get')
        lease_get.return_value = dummy_lease
        matching_hosts = self.patch(host_plugin.PhysicalHostPlugin,
                                    '_matching_hosts')
        matching_hosts.return_value = []
        alloc_destroy = self.patch(self.db_api, 'host_allocation_destroy')

        with mock.patch.object(datetime, 'datetime',
                               mock.Mock(wraps=datetime.datetime)) as patched:
            patched.utcnow.return_value = datetime.datetime(
                2020, 1, 1, 11, 00)
            result = self.fake_phys_plugin._reallocate(dummy_allocation)

        matching_hosts.assert_called_once_with(
            dummy_reservation['hypervisor_properties'],
            dummy_reservation['resource_properties'],
            '1-1', dummy_lease['start_date'], dummy_lease['end_date'])
        alloc_destroy.assert_called_once_with(dummy_allocation['id'])
        self.assertEqual(False, result)

    def test_matching_hosts_not_allocated_hosts(self):
        def host_allocation_get_all_by_values(**kwargs):
            if kwargs['compute_host_id'] == 'host1':
                return True
        host_get = self.patch(
            self.db_api,
            'reservable_host_get_all_by_queries')
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
            'reservable_host_get_all_by_queries')
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

    def test_matching_hosts_allocated_hosts_with_cleaning_time(self):
        def host_allocation_get_all_by_values(**kwargs):
            if kwargs['compute_host_id'] == 'host1':
                return True
        self.cfg.CONF.set_override('cleaning_time', '5')
        host_get = self.patch(
            self.db_api,
            'reservable_host_get_all_by_queries')
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
            (datetime.datetime(2013, 12, 19, 20, 00)
             - datetime.timedelta(minutes=5),
             datetime.datetime(2013, 12, 19, 21, 00)
             + datetime.timedelta(minutes=5))
        ]
        result = self.fake_phys_plugin._matching_hosts(
            '[]', '[]', '3-3',
            datetime.datetime(2013, 12, 19, 20, 00),
            datetime.datetime(2013, 12, 19, 21, 00))
        self.addCleanup(CONF.clear_override, 'cleaning_time')
        self.assertEqual(['host1', 'host2', 'host3'], result)

    @mock.patch.object(random.Random, "shuffle")
    def test_random_matching_hosts_not_allocated_hosts(self, mock_shuffle):
        def host_allocation_get_all_by_values(**kwargs):
            if kwargs['compute_host_id'] == 'host1':
                return True
        self.cfg.CONF.set_override('randomize_host_selection', True,
                                   group=plugin.RESOURCE_TYPE)
        host_get = self.patch(
            self.db_api,
            'reservable_host_get_all_by_queries')
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
        self.fake_phys_plugin._matching_hosts(
            '[]', '[]', '1-3',
            datetime.datetime(2013, 12, 19, 20, 00),
            datetime.datetime(2013, 12, 19, 21, 00))
        self.addCleanup(CONF.clear_override, 'randomize_host_selection',
                        group=plugin.RESOURCE_TYPE)
        mock_shuffle.assert_called_once_with(['host2', 'host3'])

    @mock.patch.object(random.Random, "shuffle")
    def test_random_matching_hosts_allocated_hosts(self, mock_shuffle):
        def host_allocation_get_all_by_values(**kwargs):
            if kwargs['compute_host_id'] == 'host1':
                return True
        self.cfg.CONF.set_override('randomize_host_selection', True,
                                   group=plugin.RESOURCE_TYPE)
        host_get = self.patch(
            self.db_api,
            'reservable_host_get_all_by_queries')
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
        self.fake_phys_plugin._matching_hosts(
            '[]', '[]', '3-3',
            datetime.datetime(2013, 12, 19, 20, 00),
            datetime.datetime(2013, 12, 19, 21, 00))
        self.addCleanup(CONF.clear_override, 'randomize_host_selection',
                        group=plugin.RESOURCE_TYPE)
        mock_shuffle.assert_called_once_with(['host1', 'host2', 'host3'])

    @mock.patch.object(random.Random, "shuffle")
    def test_random_matching_hosts_allocated_cleaning_time(self, mock_shuffle):
        def host_allocation_get_all_by_values(**kwargs):
            if kwargs['compute_host_id'] == 'host1':
                return True
        self.cfg.CONF.set_override('randomize_host_selection', True,
                                   group=plugin.RESOURCE_TYPE)
        self.cfg.CONF.set_override('cleaning_time', '5')
        host_get = self.patch(
            self.db_api,
            'reservable_host_get_all_by_queries')
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
            (datetime.datetime(2013, 12, 19, 20, 00)
             - datetime.timedelta(minutes=5),
             datetime.datetime(2013, 12, 19, 21, 00)
             + datetime.timedelta(minutes=5))
        ]
        self.fake_phys_plugin._matching_hosts(
            '[]', '[]', '3-3',
            datetime.datetime(2013, 12, 19, 20, 00),
            datetime.datetime(2013, 12, 19, 21, 00))
        self.addCleanup(CONF.clear_override, 'randomize_host_selection',
                        group=plugin.RESOURCE_TYPE)
        self.addCleanup(CONF.clear_override, 'cleaning_time')
        mock_shuffle.assert_called_once_with(['host1', 'host2', 'host3'])

    def test_matching_hosts_not_matching(self):
        host_get = self.patch(
            self.db_api,
            'reservable_host_get_all_by_queries')
        host_get.return_value = []
        result = self.fake_phys_plugin._matching_hosts(
            '["=", "$memory_mb", "2048"]', '[]', '1-1',
            datetime.datetime(2013, 12, 19, 20, 00),
            datetime.datetime(2013, 12, 19, 21, 00))
        self.assertEqual([], result)

    def test_check_params_with_valid_before_end(self):
        values = {
            'min': 1,
            'max': 2,
            'resource_properties': '',
            'hypervisor_properties': '',
            'before_end': 'snapshot'
        }
        self.fake_phys_plugin._check_params(values)
        self.assertEqual(values['before_end'], 'snapshot')

    def test_check_params_with_invalid_before_end(self):
        values = {
            'min': 1,
            'max': 2,
            'resource_properties': '',
            'hypervisor_properties': '',
            'before_end': 'invalid'
        }
        self.assertRaises(manager_exceptions.MalformedParameter,
                          self.fake_phys_plugin._check_params,
                          values)

    def test_check_params_without_before_end(self):
        self.cfg.CONF.set_override('before_end', '',
                                   group='physical:host')
        values = {
            'min': 1,
            'max': 2,
            'resource_properties': '',
            'hypervisor_properties': ''
        }
        self.fake_phys_plugin._check_params(values)
        self.assertEqual(values['before_end'], 'default')

    def test_list_resource_properties(self):
        self.db_list_resource_properties = self.patch(
            self.db_api, 'resource_properties_list')

        # Expecting a list of (Reservation, Allocation)
        self.db_list_resource_properties.return_value = [
            ('prop1', False, 'aaa'),
            ('prop1', False, 'bbb'),
            ('prop2', False, 'aaa'),
            ('prop2', False, 'aaa'),
            ('prop3', True, 'aaa')
        ]

        expected = [
            {'property': 'prop1'},
            {'property': 'prop2'}
        ]

        ret = self.fake_phys_plugin.list_resource_properties(
            query={'detail': False})

        # Sort returned value to use assertListEqual
        ret.sort(key=lambda x: x['property'])

        self.assertListEqual(expected, ret)
        self.db_list_resource_properties.assert_called_once_with(
            'physical:host')

    def test_list_resource_properties_with_detail(self):
        self.db_list_resource_properties = self.patch(
            self.db_api, 'resource_properties_list')

        # Expecting a list of (Reservation, Allocation)
        self.db_list_resource_properties.return_value = [
            ('prop1', False, 'aaa'),
            ('prop1', False, 'bbb'),
            ('prop2', False, 'ccc'),
            ('prop3', True, 'aaa')
        ]

        expected = [
            {'property': 'prop1', 'private': False, 'values': ['aaa', 'bbb']},
            {'property': 'prop2', 'private': False, 'values': ['ccc']}
        ]

        ret = self.fake_phys_plugin.list_resource_properties(
            query={'detail': True})

        # Sort returned value to use assertListEqual
        ret.sort(key=lambda x: x['property'])

        self.assertListEqual(expected, ret)
        self.db_list_resource_properties.assert_called_once_with(
            'physical:host')

    def test_update_resource_property(self):
        resource_property_values = {
            'resource_type': 'physical:host',
            'private': False}

        db_resource_property_update = self.patch(
            self.db_api, 'resource_property_update')

        self.fake_phys_plugin.update_resource_property(
            'foo', resource_property_values)
        db_resource_property_update.assert_called_once_with(
            'physical:host', 'foo', resource_property_values)


class PhysicalHostMonitorPluginTestCase(tests.TestCase):

    def setUp(self):
        super(PhysicalHostMonitorPluginTestCase, self).setUp()
        self.patch(nova_client, 'Client')
        self.host_monitor_plugin = host_plugin.PhysicalHostMonitorPlugin()

    def test_configuration(self):
        # reset the singleton at first
        host_plugin.PhysicalHostMonitorPlugin._instance = None
        self.cfg = self.useFixture(conf_fixture.Config(CONF))
        self.cfg.config(os_admin_username='fake-user')
        self.cfg.config(os_admin_password='fake-passwd')
        self.cfg.config(os_admin_user_domain_name='fake-user-domain')
        self.cfg.config(os_admin_project_name='fake-pj-name')
        self.cfg.config(os_admin_project_domain_name='fake-pj-domain')
        self.host_monitor_plugin = host_plugin.PhysicalHostMonitorPlugin()
        self.assertEqual('fake-user', self.host_monitor_plugin.username)
        self.assertEqual("fake-passwd", self.host_monitor_plugin.password)
        self.assertEqual("fake-user-domain",
                         self.host_monitor_plugin.user_domain_name)
        self.assertEqual("fake-pj-name", self.host_monitor_plugin.project_name)
        self.assertEqual("fake-pj-domain",
                         self.host_monitor_plugin.project_domain_name)

    def test_notification_callback_disabled_true(self):
        failed_host = {'hypervisor_hostname': 'hypvsr1'}
        event_type = 'service.update'
        payload = {
            'nova_object.namespace': 'nova',
            'nova_object.name': 'ServiceStatusPayload',
            'nova_object.version': '1.1',
            'nova_object.data': {
                'host': failed_host['hypervisor_hostname'],
                'disabled': True,
                'last_seen_up': '2012-10-29T13:42:05Z',
                'binary': 'nova-compute',
                'topic': 'compute',
                'disabled_reason': None,
                'report_count': 1,
                'forced_down': False,
                'version': 22,
                'availability_zone': None,
                'uuid': 'fa69c544-906b-4a6a-a9c6-c1f7a8078c73'
            }
        }
        host_get_all = self.patch(db_api,
                                  'reservable_host_get_all_by_queries')
        host_get_all.return_value = [failed_host]
        handle_failures = self.patch(self.host_monitor_plugin,
                                     '_handle_failures')
        handle_failures.return_value = {'rsrv-1': {'missing_resources': True}}

        result = self.host_monitor_plugin.notification_callback(event_type,
                                                                payload)
        host_get_all.assert_called_once_with(
            ['hypervisor_hostname == ' + payload['nova_object.data']['host']])
        self.assertEqual({'rsrv-1': {'missing_resources': True}}, result)

    def test_notification_callback_no_failure(self):
        event_type = 'service.update'
        payload = {
            'nova_object.namespace': 'nova',
            'nova_object.name': 'ServiceStatusPayload',
            'nova_object.version': '1.1',
            'nova_object.data': {
                'host': 'compute-1',
                'disabled': False,
                'last_seen_up': '2012-10-29T13:42:05Z',
                'binary': 'nova-compute',
                'topic': 'compute',
                'disabled_reason': None,
                'report_count': 1,
                'forced_down': False,
                'version': 22,
                'availability_zone': None,
                'uuid': 'fa69c544-906b-4a6a-a9c6-c1f7a8078c73'
            }
        }
        host_get_all = self.patch(db_api, 'host_get_all_by_queries')
        host_get_all.return_value = []
        handle_failures = self.patch(self.host_monitor_plugin,
                                     '_handle_failures')

        result = self.host_monitor_plugin.notification_callback(event_type,
                                                                payload)
        host_get_all.assert_called_once_with(
            ['reservable == 0',
             'hypervisor_hostname == ' + payload['nova_object.data']['host']])
        handle_failures.assert_not_called()
        self.assertEqual({}, result)

    def test_notification_callback_recover(self):
        recovered_host = {'hypervisor_hostname': 'hypvsr1', 'id': 1}
        event_type = 'service.update'
        payload = {
            'nova_object.namespace': 'nova',
            'nova_object.name': 'ServiceStatusPayload',
            'nova_object.version': '1.1',
            'nova_object.data': {
                'host': 'compute-1',
                'disabled': False,
                'last_seen_up': '2012-10-29T13:42:05Z',
                'binary': 'nova-compute',
                'topic': 'compute',
                'disabled_reason': None,
                'report_count': 1,
                'forced_down': False,
                'version': 22,
                'availability_zone': None,
                'uuid': 'fa69c544-906b-4a6a-a9c6-c1f7a8078c73'
            }
        }
        host_get_all = self.patch(db_api, 'host_get_all_by_queries')
        host_get_all.return_value = [recovered_host]
        handle_failures = self.patch(self.host_monitor_plugin,
                                     '_handle_failures')
        host_update = self.patch(db_api, 'host_update')

        result = self.host_monitor_plugin.notification_callback(event_type,
                                                                payload)
        host_get_all.assert_called_once_with(
            ['reservable == 0',
             'hypervisor_hostname == ' + payload['nova_object.data']['host']])
        host_update.assert_called_once_with(recovered_host['id'],
                                            {'reservable': True})
        handle_failures.assert_not_called()
        self.assertEqual({}, result)

    def test_poll_resource_failures_state_down(self):
        hosts = [
            {'id': '1',
             'hypervisor_hostname': 'hypvsr1',
             'reservable': True},
            {'id': '2',
             'hypervisor_hostname': 'hypvsr2',
             'reservable': True},
        ]

        host_get_all = self.patch(db_api,
                                  'host_get_all_by_filters')
        host_get_all.return_value = hosts
        hypervisors_list = self.patch(
            self.host_monitor_plugin.nova.hypervisors, 'list')
        hypervisors_list.return_value = [
            mock.MagicMock(id=1, state='down', status='enabled'),
            mock.MagicMock(id=2, state='down', status='enabled')]

        result = self.host_monitor_plugin._poll_resource_failures()
        self.assertEqual((hosts, []), result)

    def test_poll_resource_failures_status_disabled(self):
        hosts = [
            {'id': '1',
             'hypervisor_hostname': 'hypvsr1',
             'reservable': True},
            {'id': '2',
             'hypervisor_hostname': 'hypvsr2',
             'reservable': True},
        ]

        host_get_all = self.patch(db_api,
                                  'host_get_all_by_filters')
        host_get_all.return_value = hosts
        hypervisors_list = self.patch(
            self.host_monitor_plugin.nova.hypervisors, 'list')
        hypervisors_list.return_value = [
            mock.MagicMock(id=1, state='up', status='disabled'),
            mock.MagicMock(id=2, state='up', status='disabled')]

        result = self.host_monitor_plugin._poll_resource_failures()
        self.assertEqual((hosts, []), result)

    def test_poll_resource_failures_nothing(self):
        hosts = [
            {'id': '1',
             'hypervisor_hostname': 'hypvsr1',
             'reservable': True},
            {'id': '2',
             'hypervisor_hostname': 'hypvsr2',
             'reservable': True},
        ]

        host_get_all = self.patch(db_api,
                                  'host_get_all_by_filters')
        host_get_all.return_value = hosts
        hypervisors_list = self.patch(
            self.host_monitor_plugin.nova.hypervisors, 'list')
        hypervisors_list.return_value = [
            mock.MagicMock(id=1, state='up', status='enabled'),
            mock.MagicMock(id=2, state='up', status='enabled')]

        result = self.host_monitor_plugin._poll_resource_failures()
        self.assertEqual(([], []), result)

    def test_poll_resource_failures_recover(self):
        hosts = [
            {'id': '1',
             'hypervisor_hostname': 'hypvsr1',
             'reservable': False},
            {'id': '2',
             'hypervisor_hostname': 'hypvsr2',
             'reservable': False},
        ]

        host_get_all = self.patch(db_api,
                                  'host_get_all_by_filters')
        host_get_all.return_value = hosts
        hypervisors_list = self.patch(
            self.host_monitor_plugin.nova.hypervisors, 'list')
        hypervisors_list.return_value = [
            mock.MagicMock(id=1, state='up', status='enabled'),
            mock.MagicMock(id=2, state='up', status='enabled')]

        result = self.host_monitor_plugin._poll_resource_failures()
        self.assertEqual(([], hosts), result)

    def test_handle_failures(self):
        failed_hosts = [
            {'id': '1',
             'hypervisor_hostname': 'hypvsr1'}
        ]
        host_update = self.patch(db_api, 'host_update')
        heal = self.patch(self.host_monitor_plugin, 'heal')

        self.host_monitor_plugin._handle_failures(failed_hosts)
        host_update.assert_called_once_with(failed_hosts[0]['id'],
                                            {'reservable': False})
        heal.assert_called_once()

    def test_heal(self):
        failed_hosts = [
            {'id': '1',
             'hypervisor_hostname': 'hypvsr1'}
        ]
        reservation_flags = {
            'rsrv-1': {'missing_resources': True}
        }
        hosts_get = self.patch(db_api, 'unreservable_host_get_all_by_queries')
        hosts_get.return_value = failed_hosts
        get_healing_interval = self.patch(self.host_monitor_plugin,
                                          'get_healing_interval')
        get_healing_interval.return_value = 60
        healing_handler = mock.Mock()
        healing_handler.return_value = reservation_flags
        self.host_monitor_plugin.healing_handlers = [healing_handler]
        start_date = datetime.datetime(2020, 1, 1, 12, 00)

        with mock.patch.object(datetime, 'datetime',
                               mock.Mock(wraps=datetime.datetime)) as patched:
            patched.utcnow.return_value = start_date
            result = self.host_monitor_plugin.heal()

        healing_handler.assert_called_once_with(
            failed_hosts, start_date,
            start_date + datetime.timedelta(minutes=60)
        )
        self.assertEqual(reservation_flags, result)
