# Copyright (c) 2013 Mirantis Inc.
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

from climate.utils import service

CONF = cfg.CONF
CONF.import_opt('rpc_topic', 'climate.manager.service', 'manager')


class ManagerRPCAPI(service.RpcProxy):
    """Client side for the Manager RPC API.

    Used from other services to communicate with climate-manager service.
    """
    BASE_RPC_API_VERSION = '1.0'

    def __init__(self):
        """Initiate RPC API client with needed topic and RPC version."""
        super(ManagerRPCAPI, self).__init__(
            topic=CONF.manager.rpc_topic,
            default_version=self.BASE_RPC_API_VERSION,
        )

    def get_lease(self, lease_id):
        """Get detailed info about some lease."""
        return self.call('get_lease', lease_id=lease_id)

    def list_leases(self):
        """List all leases."""
        return self.call('list_leases')

    def create_lease(self, lease_values):
        """Create lease with specified parameters."""
        return self.call('create_lease', lease_values=lease_values)

    def update_lease(self, lease_id, values):
        """Update lease with passes values dictionary."""
        return self.call('update_lease', lease_id=lease_id, values=values)

    def delete_lease(self, lease_id):
        """Delete specified lease."""
        return self.cast('delete_lease', lease_id=lease_id)
