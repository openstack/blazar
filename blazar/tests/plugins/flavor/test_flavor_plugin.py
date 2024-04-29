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
from unittest import mock

from novaclient.v2 import flavors

from blazar.db.sqlalchemy import api as db_api
from blazar.db import utils as db_utils
from blazar.manager import exceptions as mgr_exceptions
from blazar.plugins.flavor import flavor_plugin
from blazar.plugins.oshosts import host_plugin
from blazar import tests
from blazar.tests.db.sqlalchemy import test_sqlalchemy_api as fake


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

    @mock.patch.object(flavor_plugin.FlavorPlugin, '_get_flavor_details')
    def test_allocation_candidates(self, mock_get_flavor):
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
            'amount': 1,
            'affinity': None,
            'start_date': datetime.datetime(2030, 1, 1, 8, 00),
            'end_date': datetime.datetime(2030, 1, 1, 12, 00)
        }
        mock_get_flavor.return_value = ({"PCPU": 2}, {})

        result = plugin.allocation_candidates(reservation)

        # 4 because 2 requested x 4 + 2 reserved = 10 total
        self.assertEqual(4, len(result))
        mock_get_flavor.assert_called_once_with(
            "34eb7166-0e9b-432c-96fd-dff37f22e36e")

    @mock.patch.object(flavor_plugin.FlavorPlugin, '_get_flavor_details')
    def test_allocation_candidates_fails_no_space(self, mock_get_flavor):
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
            'amount': 1,
            'affinity': None,
            'start_date': datetime.datetime(2030, 1, 1, 8, 00),
            'end_date': datetime.datetime(2030, 1, 1, 12, 00)
        }
        mock_get_flavor.return_value = ({"PCPU": 9}, {})

        self.assertRaises(mgr_exceptions.NotEnoughHostsAvailable,
                          plugin.allocation_candidates,
                          reservation)

    @mock.patch.object(flavors.FlavorManager, 'get')
    def test__get_flavor_details(self, mock_get):
        plugin = flavor_plugin.FlavorPlugin()
        mock_flavor = mock.Mock()
        mock_get.return_value = mock_flavor
        mock_flavor.to_dict.return_value = {
            "disk": 10,  # GiB
            "OS-FLV-EXT-DATA:ephemeral": 0,  # GiB
            "id": "34eb7166-0e9b-432c-96fd-dff37f22e36e",
            "name": "test1",
            "ram": 1024,  # MB
            "swap": 0,
            "vcpus": 1,
        }
        mock_flavor.get_keys.return_value = {
            'hw:cpu_policy': 'dedicated',
            'trait:HW_CPU_X86_AVX': 'required',
            'resources:VGPU': '1',
        }

        resource_request, resource_traits = plugin._get_flavor_details(
            "34eb7166-0e9b-432c-96fd-dff37f22e36e")

        self.assertDictEqual({
            'DISK_GB': 10, 'MEMORY_MB': 1024, 'PCPU': 1, 'VCPU': 0, 'VGPU': 1
        }, resource_request)
        self.assertDictEqual({'HW_CPU_X86_AVX': 'required'}, resource_traits)

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
