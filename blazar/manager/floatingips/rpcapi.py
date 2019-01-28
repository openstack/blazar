# Copyright (c) 2019 NTT.
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

    def get_floatingip(self, floatingip_id):
        """Get detailed info about a floatingip."""
        return self.call('virtual:floatingip:get_floatingip',
                         fip_id=floatingip_id)

    def list_floatingips(self):
        """List all floatingips."""
        return self.call('virtual:floatingip:list_floatingip')

    def create_floatingip(self, floatingip_values):
        """Create floatingip with specified parameters."""
        return self.call('virtual:floatingip:create_floatingip',
                         values=floatingip_values)

    def delete_floatingip(self, floatingip_id):
        """Delete specified floatingip."""
        return self.call('virtual:floatingip:delete_floatingip',
                         fip_id=floatingip_id)
