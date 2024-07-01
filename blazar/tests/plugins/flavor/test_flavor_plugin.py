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
import json
from unittest import mock

from novaclient.v2 import flavors

from blazar import context
from blazar.db.sqlalchemy import api as db_api
from blazar.db import utils as db_utils
from blazar.manager import exceptions as mgr_exceptions
from blazar.plugins.flavor import flavor_plugin
from blazar.plugins.oshosts import host_plugin
from blazar import tests
from blazar.tests.db.sqlalchemy import test_sqlalchemy_api as fake
from blazar.utils.openstack import nova
from blazar.utils.openstack import placement


class TestFlavorPlugin(tests.DBTestCase):
    def _create_fake_host(self):
        host_values = fake._get_fake_host_values(id=123)
        host_values["reservable"] = 1
        db_api.host_create(host_values)

    def test_get(self):
        plugin = flavor_plugin.FlavorPlugin()
        resource_id = '123'
        self._create_fake_host()

        result = plugin.get(resource_id)

        self.assertEqual(resource_id, result['id'])

    def test_list_allocations(self):
        plugin = flavor_plugin.FlavorPlugin()

        result = plugin.list_allocations({'lease_id': '2001'})

        self.assertEqual(0, len(result))

    @mock.patch.object(host_plugin.PhysicalHostPlugin, 'query_allocations')
    def test_query_allocations(self, mock_query):
        plugin = flavor_plugin.FlavorPlugin()
        mock_query.return_value = "fake"

        result = plugin.query_allocations(['123'], lease_id='2001')

        self.assertEqual("fake", result)
        mock_query.assert_called_once_with(['123'], '2001', None)

    @mock.patch.object(flavor_plugin.FlavorPlugin,
                       '_estimate_flavor_resources')
    @mock.patch.object(flavor_plugin.FlavorPlugin, '_get_flavor_details')
    def test_allocation_candidates(self, mock_get_flavor, mock_resources):
        self._create_fake_host()
        fake_inventory_values = {
            'computehost_id': 123,
            'resource_class': 'PCPU',
            'total': 10,
            'reserved': 2,
            'min_unit': 1,
            'max_unit': 10,
            'step_size': 1,
            'allocation_ratio': 1.0
        }
        db_api.host_resource_inventory_create(fake_inventory_values)
        plugin = flavor_plugin.FlavorPlugin()
        reservation = {
            'flavor_id': "34eb7166-0e9b-432c-96fd-dff37f22e36e",
            'amount': 4,
            'affinity': None,
            'start_date': datetime.datetime(2030, 1, 1, 8, 00),
            'end_date': datetime.datetime(2030, 1, 1, 12, 00)
        }
        mock_resources.return_value = ({"PCPU": 2}, {})
        mock_flavor = {"flavor_id": "fake"}
        mock_get_flavor.return_value = mock_flavor

        result = plugin.allocation_candidates(reservation)

        self.assertEqual(4, len(result))
        mock_get_flavor.assert_called_once_with(reservation)
        mock_resources.assert_called_once_with(mock_flavor)

    @mock.patch.object(flavor_plugin.FlavorPlugin,
                       '_estimate_flavor_resources')
    @mock.patch.object(flavor_plugin.FlavorPlugin, '_get_flavor_details')
    def test_allocation_candidates_fails_no_space(self, mock_get_flavor,
                                                  mock_resources):
        self._create_fake_host()
        fake_inventory_values = {
            'computehost_id': 123,
            'resource_class': 'PCPU',
            'total': 10,
            'reserved': 2,
            'min_unit': 1,
            'max_unit': 10,
            'step_size': 1,
            'allocation_ratio': 1.0
        }
        db_api.host_resource_inventory_create(fake_inventory_values)
        plugin = flavor_plugin.FlavorPlugin()
        reservation = {
            'flavor_id': "34eb7166-0e9b-432c-96fd-dff37f22e36e",
            'amount': 5,
            'affinity': None,
            'start_date': datetime.datetime(2030, 1, 1, 8, 00),
            'end_date': datetime.datetime(2030, 1, 1, 12, 00)
        }
        mock_get_flavor.return_value = {"flavor_id": "fake"}
        mock_resources.return_value = ({"PCPU": 2}, {})

        self.assertRaises(mgr_exceptions.NotEnoughHostsAvailable,
                          plugin.allocation_candidates,
                          reservation)

    @mock.patch.object(flavor_plugin.FlavorPlugin,
                       '_estimate_flavor_resources')
    @mock.patch.object(flavor_plugin.FlavorPlugin, '_create_resources')
    @mock.patch.object(flavor_plugin.FlavorPlugin, '_get_flavor_details')
    def test_allocation_candidates_avoids_reservations(self, mock_get_flavor,
                                                       mock_create,
                                                       mock_resources):
        self._create_fake_host()
        fake_inventory_values = {
            'computehost_id': 123,
            'resource_class': 'PCPU',
            'total': 10,
            'reserved': 2,
            'min_unit': 1,
            'max_unit': 10,
            'step_size': 1,
            'allocation_ratio': 1.0,
        }
        db_api.host_resource_inventory_create(fake_inventory_values)
        plugin = flavor_plugin.FlavorPlugin()
        new_reservation = {
            'flavor_id': "34eb7166-0e9b-432c-96fd-dff37f22e36e",
            'amount': 3,
            'affinity': None,
            'start_date': datetime.datetime(2030, 1, 1, 8, 00),
            'end_date': datetime.datetime(2030, 1, 1, 12, 00),
        }
        fake_flavor = {
            "disk": 0,  # GiB
            "OS-FLV-EXT-DATA:ephemeral": 0,  # GiB
            "id": "34eb7166-0e9b-432c-96fd-dff37f22e36e",
            "name": "test1",
            "ram": 0,  # MB
            "swap": 0,
            "vcpus": 2,
            "extra_specs": {'hw:cpu_policy': 'dedicated'},
        }
        mock_get_flavor.return_value = fake_flavor
        mock_resources.return_value = ({"PCPU": 2}, {})
        old_reservation = new_reservation.copy()
        old_reservation['amount'] = 2
        fake_phys_reservation = new_reservation.copy()
        fake_phys_reservation['id'] = 345
        fake_start_event = {
            'id': 123,
            'lease_id': 1234,
            'event_type': "start_lease",
            'time': datetime.datetime(2030, 1, 1, 8, 00),
            'status': "fake",
        }
        fake_lease = {
            'id': 1234,
            'name': "fakelease",
            'user_id': 'fake',
            'project_id': 'fake',
            'start_date': datetime.datetime(2030, 1, 1, 8, 00),
            'end_date': datetime.datetime(2030, 1, 1, 12, 00),
            'trust': 'trust',
            'reservations': [fake_phys_reservation],
            'events': [fake_start_event]
        }
        db_api.lease_create(fake_lease)
        mock_create.return_value = ("flavor_id", "aggregate_id")
        # create a reservation to avoid
        plugin.reserve_resource("345", old_reservation)

        # Host as 10 PCPUs, 2 are reserved, leaving 8 PCPUs available
        # Old reservation is for 2 flavors needing 2 each, so 4 left
        # So there should be space for 2 lots of 2 PCPUs
        new_reservation['amount'] = 2
        result = plugin.allocation_candidates(new_reservation)
        self.assertEqual(2, len(result))

        # there should not be space for 3 lots of 2 PCPUs
        new_reservation['amount'] = 3
        self.assertRaises(mgr_exceptions.NotEnoughHostsAvailable,
                          plugin.allocation_candidates,
                          new_reservation)

    @mock.patch.object(flavors.FlavorManager, 'get')
    def test__get_flavor_details(self, mock_get):
        plugin = flavor_plugin.FlavorPlugin()
        mock_flavor = mock.Mock()
        mock_get.return_value = mock_flavor
        fake_flavor = {
            "disk": 10,  # GiB
            "OS-FLV-EXT-DATA:ephemeral": 0,  # GiB
            "id": "34eb7166-0e9b-432c-96fd-dff37f22e36e",
            "name": "test1",
            "ram": 1024,  # MB
            "swap": 0,
            "vcpus": 1,
        }
        mock_flavor.to_dict.return_value = fake_flavor
        fake_extra_specs = {
            'hw:cpu_policy': 'dedicated',
            'trait:HW_CPU_X86_AVX': 'required',
            'resources:VGPU': '1',
        }
        mock_flavor.get_keys.return_value = fake_extra_specs
        fake_instance_reservation = {
            "flavor_id": "34eb7166-0e9b-432c-96fd-dff37f22e36e"
        }

        source_flavor = plugin._get_flavor_details(fake_instance_reservation)

        expected = fake_flavor.copy()
        expected["extra_specs"] = fake_extra_specs
        self.assertDictEqual(expected, source_flavor)

    @mock.patch.object(flavor_plugin.FlavorPlugin, '_create_resources')
    @mock.patch.object(flavor_plugin.FlavorPlugin, '_pick_hosts')
    def test_reserve_resource(self, mock_pick, mock_create):
        plugin = flavor_plugin.FlavorPlugin()
        reservation = {
            'flavor_id': "34eb7166-0e9b-432c-96fd-dff37f22e36e",
            'amount': 5,
            'affinity': None,
            'start_date': datetime.datetime(2030, 1, 1, 8, 00),
            'end_date': datetime.datetime(2030, 1, 1, 12, 00)
        }
        fake_flavor = {
            "disk": 10,  # GiB
            "OS-FLV-EXT-DATA:ephemeral": 0,  # GiB
            "id": "34eb7166-0e9b-432c-96fd-dff37f22e36e",
            "name": "test1",
            "ram": 1024,  # MB
            "swap": 0,
            "vcpus": 1,
        }
        mock_pick.return_value = (['123', '124'], fake_flavor)
        mock_create.return_value = ("flavor_id", "aggregate_id")

        id = plugin.reserve_resource("345", reservation)

        allocations = db_api.host_allocation_get_all_by_values(
            reservation_id="345")
        self.assertEqual(2, len(allocations))
        reservation = db_api.instance_reservation_get(id)
        self.assertEqual("345", reservation["reservation_id"])
        self.assertEqual("flavor_id", reservation["flavor_id"])
        self.assertEqual("aggregate_id", reservation["aggregate_id"])

    @mock.patch.object(nova.ReservationPool, 'create')
    @mock.patch.object(context.BlazarContext, 'current')
    @mock.patch.object(placement.BlazarPlacementClient,
                       'create_reservation_class')
    @mock.patch.object(flavor_plugin.FlavorPlugin, '_create_flavor')
    def test_create_resources(self, mock_create_flavor,
                              mock_reservation_create,
                              mock_current, mock_pool_create):
        plugin = flavor_plugin.FlavorPlugin()
        fake_flavor = {
            "disk": 10,  # GiB
            "OS-FLV-EXT-DATA:ephemeral": 100,  # GiB
            "id": "34eb7166-0e9b-432c-96fd-dff37f22e36e",
            "name": "test1",
            "ram": 1024,  # MB
            "swap": 0,
            "vcpus": 2,
            "extra_specs": {'hw:cpu_policy': 'dedicated'}
        }
        fake_reservation = {
            'reservation_id': "12345",
            'vcpus': fake_flavor["vcpus"],
            'memory_mb': fake_flavor["ram"],
            'disk_gb': fake_flavor["disk"],
            'amount': 2,
            'affinity': None,
            'resource_properties': json.dumps(fake_flavor)
        }
        mock_context = mock.Mock()
        mock_context.project_id = "fake-project-id"
        mock_current.return_value = mock_context
        mock_aggregate = mock.Mock()
        mock_aggregate.id = "aggregate_id"
        mock_pool_create.return_value = mock_aggregate
        mock_flavor = mock.Mock()
        mock_flavor.id = "flavor_id"
        mock_create_flavor.return_value = mock_flavor

        fid, aid = plugin._create_resources(fake_reservation)

        self.assertEqual(fid, "flavor_id")
        self.assertEqual(aid, "aggregate_id")
        mock_create_flavor.assert_called_once_with(fake_reservation)
        mock_reservation_create.assert_called_once_with("12345")
        mock_current.assert_called_once_with()
        mock_pool_create.assert_called_once_with(
            name="12345",
            metadata={'reservation': '12345',
                      'filter_tenant_id': 'fake-project-id'}
        ),

    @mock.patch.object(flavors.FlavorManager, 'create')
    def test_create_flavor(self, mock_create):
        plugin = flavor_plugin.FlavorPlugin()
        fake_flavor = {
            "disk": 10,  # GiB
            "OS-FLV-EXT-DATA:ephemeral": 100,  # GiB
            "id": "34eb7166-0e9b-432c-96fd-dff37f22e36e",
            "name": "test1",
            "ram": 1024,  # MB
            "swap": 0,
            "vcpus": 2,
            "extra_specs": {'hw:cpu_policy': 'dedicated'}
        }
        fake_reservation = {
            'reservation_id': "12345",
            'vcpus': fake_flavor["vcpus"],
            'memory_mb': fake_flavor["ram"],
            'disk_gb': fake_flavor["disk"],
            'amount': 2,
            'affinity': None,
            'resource_properties': json.dumps(fake_flavor)
        }
        mock_flavor = mock.Mock()
        mock_create.return_value = mock_flavor

        plugin._create_flavor(fake_reservation)

        mock_flavor.set_keys.assert_called_once_with({
            'hw:cpu_policy': 'dedicated',
            'aggregate_instance_extra_specs:reservation': '12345',
            'resources:CUSTOM_RESERVATION_12345': '1',
        })
        mock_create.assert_called_once_with(
            flavorid='12345', name='reservation:12345', vcpus=2, ram=1024,
            disk=10, is_public=False)

    def test__query_available_hosts(self):
        get_reservations = self.patch(db_utils,
                                      'get_reservations_by_host_id')
        get_reservations.return_value = []
        plugin = flavor_plugin.FlavorPlugin()

        # Check that we can fit 4 VCPU resource requests
        self._create_fake_host()
        fake_inventory_values = {
            'computehost_id': 123,
            'resource_class': 'VCPU',
            'total': 4,
            'reserved': 0,
            'min_unit': 1,
            'max_unit': 4,
            'step_size': 1,
            'allocation_ratio': 1.0
        }
        db_api.host_resource_inventory_create(fake_inventory_values)

        query_params = {
            'start_date': datetime.datetime(2020, 7, 7, 18, 0),
            'end_date': datetime.datetime(2020, 7, 7, 19, 0),
            'resource_request': {
                'VCPU': 1,
            },
            'resource_traits': {}
        }
        ret = plugin._query_available_hosts(**query_params)
        self.assertEqual(4, len(ret))

        # Only 2 * 1024 MB requests fit when we add a MEMORY_MB inventory
        fake_inventory_values = {
            'computehost_id': 123,
            'resource_class': 'MEMORY_MB',
            'total': 2048,
            'reserved': 0,
            'min_unit': 1,
            'max_unit': 2048,
            'step_size': 1,
            'allocation_ratio': 1.0
        }
        db_api.host_resource_inventory_create(fake_inventory_values)

        query_params = {
            'start_date': datetime.datetime(2020, 7, 7, 18, 0),
            'end_date': datetime.datetime(2020, 7, 7, 19, 0),
            'resource_request': {
                'VCPU': 1,
                'MEMORY_MB': 1024
            },
            'resource_traits': {}
        }
        ret = plugin._query_available_hosts(**query_params)
        self.assertEqual(2, len(ret))

    @mock.patch.object(flavor_plugin.FlavorPlugin, 'get_enforcement_resources')
    @mock.patch.object(flavors.FlavorManager, 'create')
    def test_get_enforcement_resources(self, mock_create_flavor,
                                       mock_get_resources):
        plugin = flavor_plugin.FlavorPlugin()
        fake_flavor = {
            "disk": 10,  # GiB
            "OS-FLV-EXT-DATA:ephemeral": 100,  # GiB
            "id": "34eb7166-0e9b-432c-96fd-dff37f22e36e",
            "name": "test1",
            "ram": 1024,  # MB
            "swap": 0,
            "vcpus": 2,
            "extra_specs": {}
        }
        fake_reservation = {
            'reservation_id': "12345",
            'vcpus': fake_flavor["vcpus"],
            'memory_mb': fake_flavor["ram"],
            'disk_gb': fake_flavor["disk"],
            'amount': 2,
            'affinity': None,
            'resource_properties': json.dumps(fake_flavor)
        }
        expected_resources = {
            'DISK_GB': 220,
            'MEMORY_MB': 2048,
            'VCPU': 4
        }
        mock_get_resources.return_value = expected_resources
        mock_flavor = mock.Mock()
        mock_create_flavor.return_value = mock_flavor
        rsv = plugin.get_enforcement_resources(fake_reservation)
        self.assertEqual(rsv, expected_resources)
