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

from oslo_config import cfg

from blazar import manager
from blazar.utils import service

CONF = cfg.CONF
CONF.import_opt('rpc_topic', 'blazar.manager.service', 'manager')


class ManagerRPCAPI(service.RPCClient):
    """Client side for the Manager RPC API.

    Used from other services to communicate with blazar-manager service.
    """
    BASE_RPC_API_VERSION = '1.0'

    def __init__(self):
        """Initiate RPC API client with needed topic and RPC version."""
        super(ManagerRPCAPI, self).__init__(manager.get_target())

    def get_network(self, network_id):
        """Get detailed info about some network."""
        return self.call('network:get_network', network_id=network_id)

    def list_networks(self):
        """List all networks."""
        return self.call('network:list_networks')

    def create_network(self, values):
        """Create network with specified parameters."""
        return self.call('network:create_network',
                         values=values)

    def update_network(self, network_id, values):
        """Update network with passes values dictionary."""
        return self.call('network:update_network', network_id=network_id,
                         values=values)

    def delete_network(self, network_id):
        """Delete specified network."""
        return self.call('network:delete_network',
                         network_id=network_id)
