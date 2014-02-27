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

from oslo.config import cfg

from novaclient import exceptions as nova_exceptions

from climate import context
from climate.manager import exceptions as manager_exceptions
from climate.plugins import oshosts as plugin
from climate.utils.openstack import nova


class NovaInventory(nova.NovaClientWrapper):
    def __init__(self):
        super(NovaInventory, self).__init__()
        self.ctx = context.current()

        # Used by nova cli
        config = cfg.CONF[plugin.RESOURCE_TYPE]
        self.username = config.climate_username
        self.api_key = config.climate_password
        self.project_id = config.climate_tenant_name

    def get_host_details(self, host):
        """Get Nova capabilities of a single host

        :param host: UUID or name of nova-compute host
        :return: Dict of capabilities or raise HostNotFound
        """
        try:
            hypervisor = self.nova.hypervisors.get(host)
        except nova_exceptions.NotFound:
            try:
                hypervisors_list = self.nova.hypervisors.search(host)
            except nova_exceptions.NotFound:
                raise manager_exceptions.HostNotFound(host=host)
            if len(hypervisors_list) > 1:
                raise manager_exceptions.MultipleHostsFound(host)
            else:
                hypervisor_id = hypervisors_list[0].id
                # NOTE(sbauza): No need to catch the exception as we're sure
                #  that the hypervisor exists
                hypervisor = self.nova.hypervisors.get(hypervisor_id)
        try:
            return {'id': hypervisor.id,
                    'hypervisor_hostname': hypervisor.hypervisor_hostname,
                    'vcpus': hypervisor.vcpus,
                    'cpu_info': hypervisor.cpu_info,
                    'hypervisor_type': hypervisor.hypervisor_type,
                    'hypervisor_version': hypervisor.hypervisor_version,
                    'memory_mb': hypervisor.memory_mb,
                    'local_gb': hypervisor.local_gb}
        except AttributeError:
            raise manager_exceptions.InvalidHost(host=host)

    def get_servers_per_host(self, host):
        """List all servers of a nova-compute host

        :param host: Name (not UUID) of nova-compute host
        :return: Dict of servers or None
        """
        try:
            hypervisors_list = self.nova.hypervisors.search(host, servers=True)
        except nova_exceptions.NotFound:
            raise manager_exceptions.HostNotFound(host=host)
        if len(hypervisors_list) > 1:
            raise manager_exceptions.MultipleHostsFound(host)
        else:
            try:
                return hypervisors_list[0].servers
            except AttributeError:
                # NOTE(sbauza): nova.hypervisors.search(servers=True) returns
                #  a list of hosts without 'servers' attribute if no servers
                #  are running on that host
                return None
