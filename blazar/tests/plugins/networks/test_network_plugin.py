# Copyright (c) 2018 StackHPC
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

from ironicclient import client as ironic_client
from keystoneauth1 import identity
from keystoneauth1 import session
import mock
from neutronclient.v2_0 import client as neutron_client
from oslo_config import cfg
import six

from blazar import context
from blazar.db import api as db_api
from blazar.db import exceptions as db_exceptions
from blazar.db import utils as db_utils
from blazar.manager import exceptions as manager_exceptions
from blazar.manager import service
from blazar.plugins import networks as plugin
from blazar.plugins.networks import network_plugin
from blazar import tests
from blazar.utils.openstack import base
from blazar.utils.openstack import nova
from blazar.utils import trusts

CONF = cfg.CONF


class NetworkPluginTestCase(tests.TestCase):

    def setUp(self):
        super(NetworkPluginTestCase, self).setUp()
        self.cfg = cfg
        self.context = context
        self.patch(self.context, 'BlazarContext')

        self.ironic_client = ironic_client
        self.ironic_client = self.patch(
            self.ironic_client, 'get_client').return_value
        self.neutron_client = neutron_client
        self.neutron_client = self.patch(
            self.neutron_client, 'Client').return_value
        self.identity = identity
        self.session = session

        self.service = service
        self.manager = self.service.ManagerService()

        self.fake_network_id = 'e3ed59f3-27e6-48df-b8bd-2a397aeb57dc'
        self.fake_network_values = {
            'network_type': 'vlan',
            'physical_network': 'physnet1',
            'segment_id': 1234
        }
        self.fake_network = self.fake_network_values.copy()
        self.fake_network['id'] = self.fake_network_id

        self.patch(base, 'url_for').return_value = 'http://foo.bar'
        self.network_plugin = network_plugin
        self.fake_network_plugin = self.network_plugin.NetworkPlugin()
        self.db_api = db_api
        self.db_utils = db_utils

        self.usage_enforcer = self.patch(self.fake_network_plugin,
                                         'usage_enforcer')
        self.check_usage_against_allocation = self.patch(
            self.usage_enforcer, 'check_usage_against_allocation')
        self.check_usage_against_allocation_pre_update = self.patch(
            self.usage_enforcer, 'check_usage_against_allocation_pre_update')
        self.release_encumbered = self.patch(
            self.usage_enforcer, 'release_encumbered')

        self.db_network_get = self.patch(self.db_api, 'network_get')
        self.db_network_get.return_value = self.fake_network
        self.db_network_list = self.patch(self.db_api, 'network_list')
        self.db_network_create = self.patch(self.db_api, 'network_create')
        self.db_network_update = self.patch(self.db_api, 'network_update')
        self.db_network_destroy = self.patch(self.db_api, 'network_destroy')

        self.db_network_extra_capability_get_all_per_network = self.patch(
            self.db_api, 'network_extra_capability_get_all_per_network')

        self.db_network_extra_capability_get_all_per_name = self.patch(
            self.db_api, 'network_extra_capability_get_all_per_name')

        self.db_network_extra_capability_create = self.patch(
            self.db_api, 'network_extra_capability_create')

        self.db_network_extra_capability_update = self.patch(
            self.db_api, 'network_extra_capability_update')

        self.get_extra_capabilities = self.patch(
            self.fake_network_plugin, '_get_extra_capabilities')

        self.get_extra_capabilities.return_value = {
            'foo': 'bar',
            'buzz': 'word',
        }
        self.fake_network_plugin.setup(None)

        self.trusts = trusts
        self.trust_ctx = self.patch(self.trusts, 'create_ctx_from_trust')
        self.trust_create = self.patch(self.trusts, 'create_trust')

        self.ServerManager = nova.ServerManager

    def test_get_network(self):
        network = self.fake_network_plugin.get_network(self.fake_network_id)
        self.db_network_get.assert_called_once_with(self.fake_network_id)
        expected = self.fake_network.copy()
        expected.update({'foo': 'bar', 'buzz': 'word'})
        self.assertEqual(expected, network)

    def test_get_network_without_extracapabilities(self):
        self.get_extra_capabilities.return_value = {}
        network = self.fake_network_plugin.get_network(self.fake_network_id)
        self.db_network_get.assert_called_once_with(self.fake_network_id)
        self.assertEqual(self.fake_network, network)

    def test_list_networks(self):
        self.fake_network_plugin.list_networks()
        self.db_network_list.assert_called_once_with()

    def test_create_network_without_extra_capabilities(self):
        network_values = {
            'network_type': 'vlan',
            'physical_network': 'physnet1',
            'segment_id': 1234
        }
        expected_network_values = network_values.copy()
        self.get_extra_capabilities.return_value = {}
        network = self.fake_network_plugin.create_network(network_values)
        self.db_network_create.assert_called_once_with(expected_network_values)
        self.assertEqual(network, self.fake_network)

    def test_create_network_with_extra_capabilities(self):
        fake_network = self.fake_network.copy()
        fake_network.update({'foo': 'bar'})
        # NOTE(sbauza): 'id' will be pop'd, we need to keep track of it
        fake_request = fake_network.copy()
        fake_capa = {'network_id': self.fake_network_id,
                     'capability_name': 'foo',
                     'capability_value': 'bar',
                     }
        self.get_extra_capabilities.return_value = {'foo': 'bar'}
        self.db_network_create.return_value = self.fake_network
        network = self.fake_network_plugin.create_network(fake_request)
        self.db_network_create.assert_called_once_with(
            self.fake_network_values)
        self.db_network_extra_capability_create.assert_called_once_with(
            fake_capa)
        self.assertEqual(network, fake_network)

    def test_create_network_with_capabilities_too_long(self):
        fake_network = self.fake_network_values.copy()
        fake_network.update({'foo': 'bar'})
        # NOTE(sbauza): 'id' will be pop'd, we need to keep track of it
        fake_request = fake_network.copy()
        long_key = ""
        for i in range(65):
            long_key += "0"
        fake_request[long_key] = "foo"
        self.db_network_create.return_value = self.fake_network
        self.assertRaises(manager_exceptions.ExtraCapabilityTooLong,
                          self.fake_network_plugin.create_network,
                          fake_request)

    def test_create_network_without_required_params(self):
        self.assertRaises(manager_exceptions.MissingParameter,
                          self.fake_network_plugin.create_network,
                          {'network_type': 'vlan',
                           'physical_network': 'physnet1'})

    def test_create_network_with_invalid_segment_id(self):
        self.assertRaises(manager_exceptions.MalformedParameter,
                          self.fake_network_plugin.create_network,
                          {'network_type': 'vlan',
                           'physical_network': 'physnet1',
                           'segment_id': 0})
        self.assertRaises(manager_exceptions.MalformedParameter,
                          self.fake_network_plugin.create_network,
                          {'network_type': 'vlan',
                           'physical_network': 'physnet1',
                           'segment_id': 4095})

    def test_create_network_issuing_rollback(self):
        def fake_db_network_create(*args, **kwargs):
            raise db_exceptions.BlazarDBException
        self.db_network_create.side_effect = fake_db_network_create
        self.assertRaises(db_exceptions.BlazarDBException,
                          self.fake_network_plugin.create_network,
                          self.fake_network)

    def test_create_duplicate_network(self):
        def fake_db_network_create(*args, **kwargs):
            raise db_exceptions.BlazarDBDuplicateEntry
        self.db_network_create.side_effect = fake_db_network_create
        self.assertRaises(db_exceptions.BlazarDBDuplicateEntry,
                          self.fake_network_plugin.create_network,
                          self.fake_network)

    def test_create_network_having_issue_when_storing_extra_capability(self):
        def fake_db_network_extra_capability_create(*args, **kwargs):
            raise db_exceptions.BlazarDBException
        fake_network = self.fake_network_values.copy()
        fake_network.update({'foo': 'bar'})
        fake_request = fake_network.copy()
        self.get_extra_capabilities.return_value = {'foo': 'bar'}
        self.db_network_create.return_value = self.fake_network
        fake = self.db_network_extra_capability_create
        fake.side_effect = fake_db_network_extra_capability_create
        self.assertRaises(manager_exceptions.CantAddExtraCapability,
                          self.fake_network_plugin.create_network,
                          fake_request)

    def test_update_network(self):
        network_values = {'segment_id': 2345}
        self.fake_network_plugin.update_network(self.fake_network_id,
                                                network_values)
        self.db_network_update.assert_called_once_with(
            self.fake_network_id, network_values)

    def test_update_network_extra_capabilities(self):
        network_values = {'foo': 'baz'}

        self.db_network_extra_capability_get_all_per_name.return_value = [
            {'id': 'extra_id1',
             'network_id': self.fake_network_id,
             'capability_name': 'foo',
             'capability_value': 'bar'
             },
        ]

        self.get_reservations_by_network = self.patch(
            self.db_utils, 'get_reservations_by_network_id')
        self.get_reservations_by_network.return_value = []

        self.fake_network_plugin.update_network(self.fake_network_id,
                                                network_values)
        self.db_network_extra_capability_update.assert_called_once_with(
            'extra_id1', {'capability_name': 'foo', 'capability_value': 'baz'})

    def test_update_network_having_issue_when_storing_extra_capability(self):
        def fake_db_network_extra_capability_update(*args, **kwargs):
            raise RuntimeError
        network_values = {'foo': 'baz'}
        self.get_reservations_by_network = self.patch(
            self.db_utils, 'get_reservations_by_network_id')
        self.get_reservations_by_network.return_value = []
        self.db_network_extra_capability_get_all_per_name.return_value = [
            {'id': 'extra_id1',
             'network_id': self.fake_network_id,
             'capability_name': 'foo',
             'capability_value': 'bar'
             },
        ]
        fake = self.db_network_extra_capability_update
        fake.side_effect = fake_db_network_extra_capability_update
        self.assertRaises(manager_exceptions.CantAddExtraCapability,
                          self.fake_network_plugin.update_network,
                          self.fake_network_id, network_values)

    def test_update_network_with_new_extra_capability(self):
        network_values = {'qux': 'word'}

        self.db_network_extra_capability_get_all_per_network.return_value = []
        self.fake_network_plugin.update_network(self.fake_network_id,
                                                network_values)
        self.db_network_extra_capability_create.assert_called_once_with({
            'network_id': self.fake_network_id,
            'capability_name': 'qux',
            'capability_value': 'word'
        })

    def test_update_network_with_used_capability(self):
        network_values = {'foo': 'buzz'}

        self.db_network_extra_capability_get_all_per_name.return_value = [
            {'id': 'extra_id1',
             'network_id': self.fake_network_id,
             'capability_name': 'foo',
             'capability_value': 'bar'
             },
        ]
        fake_network_reservation = {
            'resource_type': plugin.RESOURCE_TYPE,
            'resource_id': 'resource-1',
        }

        fake_get_reservations = self.patch(self.db_utils,
                                           'get_reservations_by_network_id')
        fake_get_reservations.return_value = [fake_network_reservation]

        fake_get_plugin_reservation = self.patch(self.db_utils,
                                                 'get_plugin_reservation')
        fake_get_plugin_reservation.return_value = {
            'resource_properties': '["==", "$foo", "bar"]'
        }
        self.assertRaises(manager_exceptions.CantAddExtraCapability,
                          self.fake_network_plugin.update_network,
                          self.fake_network_id, network_values)
        fake_get_plugin_reservation.assert_called_once_with(
            plugin.RESOURCE_TYPE, 'resource-1')

    def test_delete_network(self):
        network_allocation_get_all = self.patch(
            self.db_api,
            'network_allocation_get_all_by_values')
        network_allocation_get_all.return_value = []
        self.fake_network_plugin.delete_network(self.fake_network_id)

        self.db_network_destroy.assert_called_once_with(self.fake_network_id)

    def test_delete_reserved_network(self):
        network_allocation_get_all = self.patch(
            self.db_api,
            'network_allocation_get_all_by_values')
        network_allocation_get_all.return_value = [
            {
                'id': u'dd305477-4df8-4547-87f6-69069ee546a6',
                'network_id': self.fake_network_id
            }
        ]

        self.assertRaises(manager_exceptions.CantDeleteNetwork,
                          self.fake_network_plugin.delete_network,
                          self.fake_network_id)

    def test_delete_network_not_existing_in_db(self):
        self.db_network_get.return_value = None
        self.assertRaises(manager_exceptions.NetworkNotFound,
                          self.fake_network_plugin.delete_network,
                          self.fake_network_id)

    def test_delete_network_issuing_rollback(self):
        def fake_db_network_destroy(*args, **kwargs):
            raise db_exceptions.BlazarDBException
        network_allocation_get_all = self.patch(
            self.db_api,
            'network_allocation_get_all_by_values')
        network_allocation_get_all.return_value = []
        self.db_network_destroy.side_effect = fake_db_network_destroy
        self.assertRaises(manager_exceptions.CantDeleteNetwork,
                          self.fake_network_plugin.delete_network,
                          self.fake_network_id)

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

    def test_query_available_resources_with_parallel_reservation(self):
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

        available_vfcs = 10
        available_vfc_resources = 50
        self.cfg.CONF.set_override('available_vfcs', available_vfcs,
                                   plugin.RESOURCE_TYPE)
        self.cfg.CONF.set_override('available_vfc_resources',
                                   available_vfc_resources,
                                   plugin.RESOURCE_TYPE)
        reservations = [
            {
                'lease_id': 'lease-1',
                'resource_type': plugin.RESOURCE_TYPE,
                'network_reservation': {'vfc_resources': 2}
            },
            {
                'lease_id': 'lease-2',
                'resource_type': plugin.RESOURCE_TYPE,
                'network_reservation': {'vfc_resources': 5}
            },
        ]

        network_get_all_by_queries = self.patch(
            db_api, 'network_get_all_by_queries')
        network_get_all_by_queries.return_value = [
            {'id': 'network-1'},
            {'id': 'network-2'}
        ]
        fake_get_reservations = self.patch(self.db_utils,
                                           'get_reservations_by_network_id')
        fake_get_reservations.side_effect = [
            [reservations[0]],
            [reservations[1]]
        ]
        mock_event_get = self.patch(db_api, 'event_get_all_sorted_by_filters')
        mock_event_get.side_effect = fake_event_get

        expected = (available_vfcs - 2, available_vfc_resources - 7)
        ret = self.fake_network_plugin.query_available_resources(
            datetime.datetime(2030, 1, 1, 7, 0),
            datetime.datetime(2030, 1, 1, 15, 0))

        self.assertEqual(expected, ret)

    def test_create_reservation_no_network_available(self):
        now = datetime.datetime.utcnow()
        lease = {
            'id': u'018c1b43-e69e-4aef-a543-09681539cf4c',
            'user_id': '123',
            'project_id': '456',
        }
        values = {
            'lease_id': u'018c1b43-e69e-4aef-a543-09681539cf4c',
            'start_date': now,
            'end_date': now + datetime.timedelta(hours=1),
            'resource_type': plugin.RESOURCE_TYPE,
            'network_name': 'foo-net',
            'network_properties': '',
            'resource_properties': '',
        }
        lease_get = self.patch(self.db_api, 'lease_get')
        lease_get.return_value = lease
        network_reservation_create = self.patch(self.db_api,
                                                'network_reservation_create')
        matching_networks = self.patch(self.fake_network_plugin,
                                       '_matching_networks')
        matching_networks.return_value = []
        self.assertRaises(manager_exceptions.NotEnoughNetworksAvailable,
                          self.fake_network_plugin.reserve_resource,
                          u'f9894fcf-e2ed-41e9-8a4c-92fac332608e',
                          values)
        network_reservation_create.assert_not_called()

    def test_create_reservation_no_vfc_available(self):
        now = datetime.datetime.utcnow()
        lease = {
            'id': u'018c1b43-e69e-4aef-a543-09681539cf4c',
            'user_id': '123',
            'project_id': '456',
        }
        values = {
            'lease_id': u'018c1b43-e69e-4aef-a543-09681539cf4c',
            'start_date': now,
            'end_date': now + datetime.timedelta(hours=1),
            'resource_type': plugin.RESOURCE_TYPE,
            'network_name': 'foo-net',
            'network_properties': '',
            'resource_properties': '',
        }
        lease_get = self.patch(self.db_api, 'lease_get')
        lease_get.return_value = lease
        network_reservation_create = self.patch(self.db_api,
                                                'network_reservation_create')
        matching_networks = self.patch(self.fake_network_plugin,
                                       '_matching_networks')
        matching_networks.return_value = ['network1', 'network2']
        query_available_resources = self.patch(self.fake_network_plugin,
                                               'query_available_resources')
        query_available_resources.return_value = (0, 2)
        self.assertRaises(manager_exceptions.NotEnoughNetworksAvailable,
                          self.fake_network_plugin.reserve_resource,
                          u'f9894fcf-e2ed-41e9-8a4c-92fac332608e',
                          values)
        network_reservation_create.assert_not_called()

    def test_create_reservation_not_enough_vfc_resources_available(self):
        now = datetime.datetime.utcnow()
        lease = {
            'id': u'018c1b43-e69e-4aef-a543-09681539cf4c',
            'user_id': '123',
            'project_id': '456',
        }
        values = {
            'lease_id': u'018c1b43-e69e-4aef-a543-09681539cf4c',
            'start_date': now,
            'end_date': now + datetime.timedelta(hours=1),
            'resource_type': plugin.RESOURCE_TYPE,
            'network_name': 'foo-net',
            'network_properties': '',
            'resource_properties': '',
        }
        lease_get = self.patch(self.db_api, 'lease_get')
        lease_get.return_value = lease
        network_reservation_create = self.patch(self.db_api,
                                                'network_reservation_create')
        matching_networks = self.patch(self.fake_network_plugin,
                                       '_matching_networks')
        matching_networks.return_value = ['network1', 'network2']
        query_available_resources = self.patch(self.fake_network_plugin,
                                               'query_available_resources')
        query_available_resources.return_value = (1, 1)
        self.assertRaises(manager_exceptions.NotEnoughNetworksAvailable,
                          self.fake_network_plugin.reserve_resource,
                          u'f9894fcf-e2ed-41e9-8a4c-92fac332608e',
                          values)
        network_reservation_create.assert_not_called()

    def test_create_reservation_networks_available(self):
        lease = {
            'id': u'018c1b43-e69e-4aef-a543-09681539cf4c',
            'user_id': '123',
            'project_id': '456',
        }
        values = {
            'lease_id': u'018c1b43-e69e-4aef-a543-09681539cf4c',
            'network_properties': '',
            'resource_properties': '',
            'start_date': datetime.datetime(2013, 12, 19, 20, 00),
            'end_date': datetime.datetime(2013, 12, 19, 21, 00),
            'resource_type': plugin.RESOURCE_TYPE,
            'network_name': 'foo-net',
            'network_description': ''
        }
        lease_get = self.patch(self.db_api, 'lease_get')
        lease_get.return_value = lease
        network_reservation_create = self.patch(self.db_api,
                                                'network_reservation_create')
        matching_networks = self.patch(self.fake_network_plugin,
                                       '_matching_networks')
        matching_networks.return_value = ['network1', 'network2']
        query_available_resources = self.patch(self.fake_network_plugin,
                                               'query_available_resources')
        query_available_resources.return_value = (1, 2)
        network_allocation_create = self.patch(
            self.db_api,
            'network_allocation_create')
        self.fake_network_plugin.reserve_resource(
            u'441c1476-9f8f-4700-9f30-cd9b6fef3509',
            values)
        network_values = {
            'reservation_id': u'441c1476-9f8f-4700-9f30-cd9b6fef3509',
            'network_properties': '',
            'resource_properties': '',
            'status': 'pending',
            'before_end': 'default',
            'network_name': 'foo-net',
            'network_description': '',
            'vfc_resources': CONF[plugin.RESOURCE_TYPE].resources_per_vfc
        }
        network_reservation_create.assert_called_once_with(network_values)
        # self.check_usage_against_allocation.assert_called_once_with(
        #     lease, allocated_network_ids=['network1', 'network2'])
        calls = [
            mock.call(
                {'network_id': 'network1',
                 'reservation_id': u'441c1476-9f8f-4700-9f30-cd9b6fef3509',
                 }),
            mock.call(
                {'network_id': 'network2',
                 'reservation_id': u'441c1476-9f8f-4700-9f30-cd9b6fef3509',
                 }),
        ]
        network_allocation_create.assert_has_calls(calls)

    def test_create_reservation_with_missing_param_properties(self):
        values = {
            'lease_id': u'018c1b43-e69e-4aef-a543-09681539cf4c',
            'start_date': datetime.datetime(2017, 3, 1, 20, 00),
            'end_date': datetime.datetime(2017, 3, 2, 20, 00),
            'resource_type': plugin.RESOURCE_TYPE,
        }
        self.assertRaises(
            manager_exceptions.MissingParameter,
            self.fake_network_plugin.reserve_resource,
            u'441c1476-9f8f-4700-9f30-cd9b6fef3509',
            values)

    def test_create_reservation_with_invalid_param_before_end(self):
        values = {
            'lease_id': u'018c1b43-e69e-4aef-a543-09681539cf4c',
            'before_end': 'invalid',
            'start_date': datetime.datetime(2017, 3, 1, 20, 00),
            'end_date': datetime.datetime(2017, 3, 2, 20, 00),
            'resource_type': plugin.RESOURCE_TYPE,
            'network_name': 'foo-net',
            'network_properties': '',
            'resource_properties': '',
        }
        self.assertRaises(
            manager_exceptions.MalformedParameter,
            self.fake_network_plugin.reserve_resource,
            u'441c1476-9f8f-4700-9f30-cd9b6fef3509',
            values)

    def test_update_reservation_shorten(self):
        values = {
            'start_date': datetime.datetime(2013, 12, 19, 20, 30),
            'end_date': datetime.datetime(2013, 12, 19, 21, 00)
        }
        reservation_get = self.patch(self.db_api, 'reservation_get')
        reservation_get.return_value = {
            'lease_id': u'10870923-6d56-45c9-b592-f788053f5baa',
        }
        lease_get = self.patch(self.db_api, 'lease_get')
        lease_get.return_value = {
            'start_date': datetime.datetime(2013, 12, 19, 20, 00),
            'end_date': datetime.datetime(2013, 12, 19, 21, 00)
        }
        network_reservation_get = self.patch(
            self.db_api, 'network_reservation_get')
        self.patch(self.db_api, 'network_allocation_get_all_by_values')

        self.fake_network_plugin.update_reservation(
            '706eb3bc-07ed-4383-be93-b32845ece672',
            values)
        network_reservation_get.assert_not_called()

    def test_update_reservation_extend(self):
        values = {
            'start_date': datetime.datetime(2013, 12, 19, 20, 00),
            'end_date': datetime.datetime(2013, 12, 19, 21, 30)
        }
        reservation_get = self.patch(self.db_api, 'reservation_get')
        reservation_get.return_value = {
            'lease_id': u'10870923-6d56-45c9-b592-f788053f5baa',
            'resource_id': u'91253650-cc34-4c4f-bbe8-c943aa7d0c9b',
            'status': 'pending'
        }
        lease_get = self.patch(self.db_api, 'lease_get')
        lease_get.return_value = {
            'start_date': datetime.datetime(2013, 12, 19, 20, 00),
            'end_date': datetime.datetime(2013, 12, 19, 21, 00)
        }
        network_reservation_get = self.patch(
            self.db_api, 'network_reservation_get')
        network_reservation_get.return_value = {
            'network_properties': '["=", "$network_type", "vlan"]',
            'resource_properties': ''
        }
        network_allocation_get_all = self.patch(
            self.db_api,
            'network_allocation_get_all_by_values')
        network_allocation_get_all.return_value = [
            {
                'id': u'dd305477-4df8-4547-87f6-69069ee546a6',
                'network_id': 'network1'
            }
        ]
        network_get_all_by_queries = self.patch(
            self.db_api, 'network_get_all_by_queries')
        network_get_all_by_queries.return_value = [{'id': 'network1'}]
        get_reserved_periods = self.patch(self.db_utils,
                                          'get_reserved_periods')
        get_reserved_periods.return_value = [
            (datetime.datetime(2013, 12, 19, 20, 00),
             datetime.datetime(2013, 12, 19, 21, 00))
        ]
        network_allocation_create = self.patch(
            self.db_api,
            'network_allocation_create')
        network_allocation_destroy = self.patch(
            self.db_api,
            'network_allocation_destroy')

        self.fake_network_plugin.update_reservation(
            '706eb3bc-07ed-4383-be93-b32845ece672',
            values)
        network_allocation_create.assert_not_called()
        network_allocation_destroy.assert_not_called()

    def test_update_reservation_move_failure(self):
        values = {
            'start_date': datetime.datetime(2013, 12, 20, 20, 00),
            'end_date': datetime.datetime(2013, 12, 20, 21, 30)
        }
        reservation_get = self.patch(self.db_api, 'reservation_get')
        reservation_get.return_value = {
            'lease_id': u'10870923-6d56-45c9-b592-f788053f5baa',
            'resource_id': u'91253650-cc34-4c4f-bbe8-c943aa7d0c9b',
            'status': 'active'
        }
        lease_get = self.patch(self.db_api, 'lease_get')
        lease_get.return_value = {
            'start_date': datetime.datetime(2013, 12, 19, 20, 00),
            'end_date': datetime.datetime(2013, 12, 19, 21, 00)
        }
        network_reservation_get = self.patch(
            self.db_api,
            'network_reservation_get')
        network_reservation_get.return_value = {
            'network_properties': '["=", "$network_type", "vlan"]',
            'resource_properties': ''
        }
        network_allocation_get_all = self.patch(
            self.db_api,
            'network_allocation_get_all_by_values')
        network_allocation_get_all.return_value = [
            {
                'id': u'dd305477-4df8-4547-87f6-69069ee546a6',
                'network_id': 'network1'
            }
        ]
        network_get_all_by_queries = self.patch(self.db_api,
                                                'network_get_all_by_queries')
        network_get_all_by_queries.return_value = [{'id': 'network1'}]
        get_reserved_periods = self.patch(self.db_utils,
                                          'get_reserved_periods')
        get_reserved_periods.return_value = [
            (datetime.datetime(2013, 12, 20, 20, 30),
             datetime.datetime(2013, 12, 20, 21, 00))
        ]
        matching_networks = self.patch(
            self.fake_network_plugin, '_matching_networks')
        matching_networks.return_value = []
        self.assertRaises(
            manager_exceptions.NotEnoughNetworksAvailable,
            self.fake_network_plugin.update_reservation,
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
            'lease_id': u'10870923-6d56-45c9-b592-f788053f5baa',
            'resource_id': u'91253650-cc34-4c4f-bbe8-c943aa7d0c9b',
            'status': 'pending'
        }
        lease_get = self.patch(self.db_api, 'lease_get')
        lease_get.return_value = {
            'start_date': datetime.datetime(2013, 12, 19, 20, 00),
            'end_date': datetime.datetime(2013, 12, 19, 21, 00)
        }
        network_reservation_get = self.patch(
            self.db_api,
            'network_reservation_get')
        network_reservation_get.return_value = {
            'network_properties': '["=", "$network_type", "vlan"]',
            'resource_properties': ''
        }
        network_allocation_get_all = self.patch(
            self.db_api,
            'network_allocation_get_all_by_values')
        network_allocation_get_all.return_value = [
            {
                'id': u'dd305477-4df8-4547-87f6-69069ee546a6',
                'network_id': 'network1'
            }
        ]
        network_get_all_by_queries = self.patch(self.db_api,
                                                'network_get_all_by_queries')
        network_get_all_by_queries.return_value = [{'id': 'network1'}]
        get_reserved_periods = self.patch(self.db_utils,
                                          'get_reserved_periods')
        get_reserved_periods.return_value = [
            (datetime.datetime(2013, 12, 19, 20, 30),
             datetime.datetime(2013, 12, 19, 21, 00))
        ]
        network_allocation_create = self.patch(
            self.db_api,
            'network_allocation_create')
        network_allocation_destroy = self.patch(
            self.db_api,
            'network_allocation_destroy')

        self.fake_network_plugin.update_reservation(
            '706eb3bc-07ed-4383-be93-b32845ece672',
            values)
        network_allocation_create.assert_not_called()
        network_allocation_destroy.assert_not_called()

    def test_update_reservation_move_realloc(self):
        values = {
            'start_date': datetime.datetime(2013, 12, 20, 20, 00),
            'end_date': datetime.datetime(2013, 12, 20, 21, 30)
        }
        reservation_get = self.patch(self.db_api, 'reservation_get')
        reservation_get.return_value = {
            'lease_id': u'10870923-6d56-45c9-b592-f788053f5baa',
            'resource_id': u'91253650-cc34-4c4f-bbe8-c943aa7d0c9b',
            'status': 'pending'
        }
        lease_get = self.patch(self.db_api, 'lease_get')
        lease_get.return_value = {
            'start_date': datetime.datetime(2013, 12, 19, 20, 00),
            'end_date': datetime.datetime(2013, 12, 19, 21, 00)
        }
        network_reservation_get = self.patch(
            self.db_api,
            'network_reservation_get')
        network_reservation_get.return_value = {
            'network_properties': '["=", "$network_type", "vlan"]',
            'resource_properties': ''
        }
        network_allocation_get_all = self.patch(
            self.db_api,
            'network_allocation_get_all_by_values')
        network_allocation_get_all.return_value = [
            {
                'id': u'dd305477-4df8-4547-87f6-69069ee546a6',
                'network_id': 'network1'
            }
        ]
        network_get_all_by_queries = self.patch(self.db_api,
                                                'network_get_all_by_queries')
        network_get_all_by_queries.return_value = [{'id': 'network1'},
                                                   {'id': 'network2'}]
        network_allocation_create = self.patch(
            self.db_api,
            'network_allocation_create')
        network_allocation_destroy = self.patch(
            self.db_api,
            'network_allocation_destroy')
        get_reserved_periods = self.patch(self.db_utils,
                                          'get_reserved_periods')
        get_reserved_periods.return_value = [
            (datetime.datetime(2013, 12, 20, 20, 30),
             datetime.datetime(2013, 12, 20, 21, 00))
        ]
        matching_networks = self.patch(
            self.fake_network_plugin, '_matching_networks')
        matching_networks.return_value = ['network2']
        self.fake_network_plugin.update_reservation(
            '706eb3bc-07ed-4383-be93-b32845ece672',
            values)
        network_reservation_get.assert_called_with(
            u'91253650-cc34-4c4f-bbe8-c943aa7d0c9b')
        network_allocation_destroy.assert_called_with(
            'dd305477-4df8-4547-87f6-69069ee546a6')
        network_allocation_create.assert_called_with(
            {
                'network_id': 'network2',
                'reservation_id': '706eb3bc-07ed-4383-be93-b32845ece672'
            }
        )

    def test_update_reservation_realloc_with_properties_change(self):
        values = {
            'start_date': datetime.datetime(2017, 7, 12, 20, 00),
            'end_date': datetime.datetime(2017, 7, 12, 21, 00),
            'network_properties': '["=", "$network_type", "vlan"]',
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
        network_reservation_get = self.patch(
            self.db_api, 'network_reservation_get')
        network_reservation_get.return_value = {
            'id': '91253650-cc34-4c4f-bbe8-c943aa7d0c9b',
            'network_properties': '["=", "$network_type", "vlan"]',
            'resource_properties': ''
        }
        network_allocation_get_all = self.patch(
            self.db_api, 'network_allocation_get_all_by_values')
        network_allocation_get_all.return_value = [
            {
                'id': 'dd305477-4df8-4547-87f6-69069ee546a6',
                'network_id': 'network1'
            }
        ]
        network_get_all_by_queries = self.patch(self.db_api,
                                                'network_get_all_by_queries')
        network_get_all_by_queries.return_value = [{'id': 'network2'}]
        matching_networks = self.patch(
            self.fake_network_plugin, '_matching_networks')
        matching_networks.return_value = ['network2']
        network_allocation_create = self.patch(self.db_api,
                                               'network_allocation_create')
        network_allocation_destroy = self.patch(self.db_api,
                                                'network_allocation_destroy')
        network_reservation_update = self.patch(self.db_api,
                                                'network_reservation_update')

        self.fake_network_plugin.update_reservation(
            '706eb3bc-07ed-4383-be93-b32845ece672',
            values)
        network_reservation_get.assert_called_with(
            '91253650-cc34-4c4f-bbe8-c943aa7d0c9b')
        matching_networks.assert_called_with(
            '["=", "$network_type", "vlan"]',
            '',
            datetime.datetime(2017, 7, 12, 20, 00),
            datetime.datetime(2017, 7, 12, 21, 00)
        )
        network_allocation_create.assert_called_with(
            {
                'network_id': 'network2',
                'reservation_id': '706eb3bc-07ed-4383-be93-b32845ece672'
            }
        )
        network_allocation_destroy.assert_called_with(
            'dd305477-4df8-4547-87f6-69069ee546a6'
        )
        network_reservation_update.assert_called_with(
            '91253650-cc34-4c4f-bbe8-c943aa7d0c9b',
            {'network_properties': '["=", "$network_type", "vlan"]'}
        )

    def test_update_reservation_no_requested_networks_available(self):
        values = {
            'start_date': datetime.datetime(2017, 7, 12, 20, 00),
            'end_date': datetime.datetime(2017, 7, 12, 21, 00),
            'resource_properties': '["=", "$segment_id", "2345"]'
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
        network_reservation_get = self.patch(
            self.db_api, 'network_reservation_get')
        network_reservation_get.return_value = {
            'id': '91253650-cc34-4c4f-bbe8-c943aa7d0c9b',
            'network_properties': '["=", "$network_type", "vlan"]',
            'resource_properties': ''
        }
        network_allocation_get_all = self.patch(
            self.db_api, 'network_allocation_get_all_by_values')
        network_allocation_get_all.return_value = [
            {
                'id': 'dd305477-4df8-4547-87f6-69069ee546a6',
                'network_id': 'network1'
            }
        ]
        network_get_all_by_queries = self.patch(self.db_api,
                                                'network_get_all_by_queries')
        network_get_all_by_queries.return_value = []
        matching_networks = self.patch(
            self.fake_network_plugin, '_matching_networks')
        matching_networks.return_value = []

        self.assertRaises(
            manager_exceptions.NotEnoughNetworksAvailable,
            self.fake_network_plugin.update_reservation,
            '441c1476-9f8f-4700-9f30-cd9b6fef3509',
            values)

    def test_on_start(self):
        lease_get = self.patch(self.db_api, 'lease_get')
        lease_get.return_value = {
            'id': u'018c1b43-e69e-4aef-a543-09681539cf4c',
            'project_id': '456'
        }
        reservation_get = self.patch(
            self.db_api, 'reservation_get')
        reservation_get.return_value = {
            'id': u'593e7028-c0d1-4d76-8642-2ffd890b324c',
            'lease_id': u'018c1b43-e69e-4aef-a543-09681539cf4c',
        }
        network_reservation_get = self.patch(
            self.db_api, 'network_reservation_get')
        network_reservation_get.return_value = {
            'id': '04de74e8-193a-49d2-9ab8-cba7b49e45e8',
            'network_id': None,
            'network_name': 'foo-net',
            'network_description': None,
            'reservation_id': u'593e7028-c0d1-4d76-8642-2ffd890b324c'
        }
        network_allocation_get_all_by_values = self.patch(
            self.db_api, 'network_allocation_get_all_by_values')
        network_allocation_get_all_by_values.return_value = [
            {'network_id': 'network1'},
        ]
        network_get = self.patch(self.db_api, 'network_get')
        network_get.return_value = {
            'network_id': 'network1',
            'network_type': 'vlan',
            'physical_network': 'physnet1',
            'segment_id': 1234
        }
        create_network = self.patch(self.neutron_client, 'create_network')
        create_network.return_value = {
            'network': {
                'id': '69cab064-0e60-4efb-a503-b42dde0fb3f2',
                'name': 'foo-net'
            }
        }
        network_reservation_update = self.patch(
            self.db_api,
            'network_reservation_update')

        self.fake_network_plugin.on_start(
            u'04de74e8-193a-49d2-9ab8-cba7b49e45e8')
        create_network.assert_called_with(
            body={
                'network': {
                    'provider:segmentation_id': 1234,
                    'name': 'foo-net',
                    'project_id': '456',
                    'provider:physical_network': 'physnet1',
                    'provider:network_type': 'vlan'}})
        network_reservation_update.assert_called_with(
            '04de74e8-193a-49d2-9ab8-cba7b49e45e8',
            {'network_id': '69cab064-0e60-4efb-a503-b42dde0fb3f2'})

    def test_on_start_failure(self):
        lease_get = self.patch(self.db_api, 'lease_get')
        lease_get.return_value = {
            'id': u'018c1b43-e69e-4aef-a543-09681539cf4c',
            'project_id': '456'
        }
        reservation_get = self.patch(
            self.db_api, 'reservation_get')
        reservation_get.return_value = {
            'id': u'593e7028-c0d1-4d76-8642-2ffd890b324c',
            'lease_id': u'018c1b43-e69e-4aef-a543-09681539cf4c',
        }
        network_reservation_get = self.patch(
            self.db_api, 'network_reservation_get')
        network_reservation_get.return_value = {
            'id': '04de74e8-193a-49d2-9ab8-cba7b49e45e8',
            'network_id': None,
            'network_name': 'foo-net',
            'network_description': None,
            'reservation_id': u'593e7028-c0d1-4d76-8642-2ffd890b324c'
        }
        network_allocation_get_all_by_values = self.patch(
            self.db_api, 'network_allocation_get_all_by_values')
        network_allocation_get_all_by_values.return_value = [
            {'network_id': 'network1'},
        ]
        network_get = self.patch(self.db_api, 'network_get')
        network_get.return_value = {
            'network_id': 'network1',
            'network_type': 'vlan',
            'physical_network': 'physnet1',
            'segment_id': 1234
        }

        def fake_create_network(*args, **kwargs):
            raise manager_exceptions.NetworkCreationFailed
        create_network = self.patch(self.neutron_client, 'create_network')
        create_network.side_effect = fake_create_network

        self.assertRaises(manager_exceptions.NetworkCreationFailed,
                          self.fake_network_plugin.on_start,
                          '04de74e8-193a-49d2-9ab8-cba7b49e45e8')

    def test_on_end(self):
        network_reservation_get = self.patch(
            self.db_api, 'network_reservation_get')
        network_reservation_get.return_value = {
            'id': '04de74e8-193a-49d2-9ab8-cba7b49e45e8',
            'network_id': '69cab064-0e60-4efb-a503-b42dde0fb3f2',
            'network_name': 'foo-net',
            'reservation_id': u'593e7028-c0d1-4d76-8642-2ffd890b324c'
        }
        reservation_get = self.patch(self.db_api, 'reservation_get')
        reservation_get.return_value = {
            'id': u'593e7028-c0d1-4d76-8642-2ffd890b324c',
            'lease_id': '10870923-6d56-45c9-b592-f788053f5baa',
            'status': 'active'
        }
        lease_get = self.patch(self.db_api, 'lease_get')
        lease_get.return_value = {
            'id': u'018c1b43-e69e-4aef-a543-09681539cf4c',
            'trust_id': 'exxee111qwwwwe'
        }
        network_reservation_update = self.patch(
            self.db_api,
            'network_reservation_update')
        network_allocation_get_all_by_values = self.patch(
            self.db_api,
            'network_allocation_get_all_by_values')
        network_allocation_get_all_by_values.return_value = [
            {'id': u'bfa9aa0b-8042-43eb-a4e6-4555838bf64f',
             'network_id': u'cdae2a65-236f-475a-977d-f6ad82f828b7',
             },
        ]
        network_allocation_destroy = self.patch(
            self.db_api,
            'network_allocation_destroy')
        delete_network = self.patch(self.neutron_client, 'delete_network')
        delete_network.return_value = None

        self.fake_network_plugin.on_end(
            u'04de74e8-193a-49d2-9ab8-cba7b49e45e8')
        network_reservation_update.assert_called_with(
            u'04de74e8-193a-49d2-9ab8-cba7b49e45e8', {'status': 'completed'})
        network_allocation_destroy.assert_called_with(
            u'bfa9aa0b-8042-43eb-a4e6-4555838bf64f')
        delete_network.assert_called_with(
            '69cab064-0e60-4efb-a503-b42dde0fb3f2')

    def test_on_end_failure(self):
        network_reservation_get = self.patch(
            self.db_api, 'network_reservation_get')
        network_reservation_get.return_value = {
            'id': '04de74e8-193a-49d2-9ab8-cba7b49e45e8',
            'network_id': '69cab064-0e60-4efb-a503-b42dde0fb3f2',
            'network_name': 'foo-net',
            'reservation_id': u'593e7028-c0d1-4d76-8642-2ffd890b324c'
        }
        reservation_get = self.patch(self.db_api, 'reservation_get')
        reservation_get.return_value = {
            'id': u'593e7028-c0d1-4d76-8642-2ffd890b324c',
            'lease_id': '10870923-6d56-45c9-b592-f788053f5baa',
            'status': 'active'
        }
        lease_get = self.patch(self.db_api, 'lease_get')
        lease_get.return_value = {
            'id': u'018c1b43-e69e-4aef-a543-09681539cf4c',
            'trust_id': 'exxee111qwwwwe'
        }
        network_reservation_update = self.patch(
            self.db_api,
            'network_reservation_update')
        network_allocation_get_all_by_values = self.patch(
            self.db_api,
            'network_allocation_get_all_by_values')
        network_allocation_get_all_by_values.return_value = [
            {'id': u'bfa9aa0b-8042-43eb-a4e6-4555838bf64f',
             'network_id': u'cdae2a65-236f-475a-977d-f6ad82f828b7',
             },
        ]
        network_allocation_destroy = self.patch(
            self.db_api,
            'network_allocation_destroy')

        def fake_delete_network(*args, **kwargs):
            raise manager_exceptions.NetworkDeletionFailed
        delete_network = self.patch(self.neutron_client, 'delete_network')
        delete_network.side_effect = fake_delete_network

        self.assertRaises(manager_exceptions.NetworkDeletionFailed,
                          self.fake_network_plugin.on_end,
                          '04de74e8-193a-49d2-9ab8-cba7b49e45e8')
        network_reservation_update.assert_called_with(
            u'04de74e8-193a-49d2-9ab8-cba7b49e45e8', {'status': 'completed'})
        network_allocation_destroy.assert_called_with(
            u'bfa9aa0b-8042-43eb-a4e6-4555838bf64f')
        delete_network.assert_called_with(
            '69cab064-0e60-4efb-a503-b42dde0fb3f2')
