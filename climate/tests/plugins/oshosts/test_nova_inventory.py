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

from novaclient import client
from novaclient import exceptions as nova_exceptions

from climate import context
from climate.manager import exceptions as manager_exceptions
from climate.plugins.oshosts import nova_inventory
from climate import tests
from climate.utils.openstack import base


class FakeNovaHypervisors(object):

    class FakeHost(object):
        id = 1
        hypervisor_hostname = 'fake_name'
        vcpus = 1
        cpu_info = 'fake_cpu'
        hypervisor_type = 'fake_type'
        hypervisor_version = 1000000
        memory_mb = 8192
        local_gb = 10

        servers = ['server1', 'server2']

    @classmethod
    def get(cls, host):
        try:
            host = int(host)
        except ValueError:
            raise nova_exceptions.NotFound(404)
        if host == cls.FakeHost.id:
            return cls.FakeHost
        else:
            raise nova_exceptions.NotFound(404)

    @classmethod
    def search(cls, host, servers=False):
        if host == 'multiple':
            return [cls.FakeHost, cls.FakeHost]
        if host == cls.FakeHost.hypervisor_hostname:
            return [cls.FakeHost]
        else:
            raise nova_exceptions.NotFound(404)

    @classmethod
    def expected(cls):
        return {'id': cls.FakeHost.id,
                'hypervisor_hostname': cls.FakeHost.hypervisor_hostname,
                'vcpus': cls.FakeHost.vcpus,
                'cpu_info': cls.FakeHost.cpu_info,
                'hypervisor_type': cls.FakeHost.hypervisor_type,
                'hypervisor_version': cls.FakeHost.hypervisor_version,
                'memory_mb': cls.FakeHost.memory_mb,
                'local_gb': cls.FakeHost.local_gb}


class NovaInventoryTestCase(tests.TestCase):
    def setUp(self):
        super(NovaInventoryTestCase, self).setUp()
        self.context = context
        self.patch(self.context, 'ClimateContext')
        self.nova_inventory = nova_inventory
        self.client = client
        self.client = self.patch(self.client, 'Client').return_value
        self.patch(base, 'url_for').return_value = 'http://foo.bar'
        self.inventory = self.nova_inventory.NovaInventory()

        self.hypervisors_get = self.patch(self.inventory.nova.hypervisors,
                                          'get')
        self.hypervisors_get.side_effect = FakeNovaHypervisors.get
        self.hypervisors_search = self.patch(self.inventory.nova.hypervisors,
                                             'search')
        self.hypervisors_search.side_effect = FakeNovaHypervisors.search

    def test_get_host_details_with_host_id(self):
        host = self.inventory.get_host_details('1')
        expected = FakeNovaHypervisors.expected()
        self.assertEqual(expected, host)

    def test_get_host_details_with_host_name(self):
        host = self.inventory.get_host_details('fake_name')
        expected = FakeNovaHypervisors.expected()
        self.assertEqual(expected, host)

    def test_get_host_details_with_host_name_having_multiple_results(self):
        self.assertRaises(manager_exceptions.MultipleHostsFound,
                          self.inventory.get_host_details, 'multiple')

    def test_get_host_details_with_host_id_not_found(self):
        self.assertRaises(manager_exceptions.HostNotFound,
                          self.inventory.get_host_details, '2')

    def test_get_host_details_with_host_name_not_found(self):
        self.assertRaises(manager_exceptions.HostNotFound,
                          self.inventory.get_host_details, 'wrong_name')

    def test_get_host_details_with_invalid_host(self):
        invalid_host = FakeNovaHypervisors.FakeHost
        del invalid_host.vcpus
        self.hypervisors_get.return_value = invalid_host
        self.assertRaises(manager_exceptions.InvalidHost,
                          self.inventory.get_host_details, '1')

    def test_get_servers_per_host(self):
        servers = self.inventory.get_servers_per_host('fake_name')
        self.assertEqual(FakeNovaHypervisors.FakeHost.servers, servers)

    def test_get_servers_per_host_with_host_id(self):
        self.assertRaises(manager_exceptions.HostNotFound,
                          self.inventory.get_servers_per_host, '1')

    def test_get_servers_per_host_with_host_not_found(self):
        self.assertRaises(manager_exceptions.HostNotFound,
                          self.inventory.get_servers_per_host, 'wrong_name')

    def test_get_servers_per_host_having_multiple_results(self):
        self.assertRaises(manager_exceptions.MultipleHostsFound,
                          self.inventory.get_servers_per_host, 'multiple')

    def test_get_servers_per_host_with_host_having_no_servers(self):
        host_with_zero_servers = FakeNovaHypervisors.FakeHost
        # NOTE(sbauza): We need to simulate a host having zero servers
        del host_with_zero_servers.servers
        servers = self.inventory.get_servers_per_host('fake_name')
        self.assertEqual(None, servers)
