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

    def get_computehost(self, host_id):
        """Get detailed info about some computehost."""
        return self.call('physical:host:get_computehost', host_id=host_id)

    def list_computehosts(self, query=None):
        """List all computehosts."""
        return self.call('physical:host:list_computehosts', query=query)

    def create_computehost(self, host_values):
        """Create computehost with specified parameters."""
        return self.call('physical:host:create_computehost',
                         host_values=host_values)

    def update_computehost(self, host_id, values):
        """Update computehost with passes values dictionary."""
        return self.call('physical:host:update_computehost', host_id=host_id,
                         values=values)

    def delete_computehost(self, host_id):
        """Delete specified computehost."""
        return self.call('physical:host:delete_computehost',
                         host_id=host_id)

    def list_allocations(self, query, detail=False):
        """List all allocations on all computehosts."""
        return self.call('physical:host:list_allocations', query=query,
                         detail=detail)

    def get_allocations(self, host_id, query):
        """List all allocations on a specified computehost."""
        return self.call('physical:host:get_allocations',
                         host_id=host_id, query=query)

    def reallocate(self, host_id, data):
        """Exchange host from current allocations."""
        return self.call('physical:host:reallocate_computehost',
                         host_id=host_id, data=data)
