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

from blazar import manager
from blazar.utils import service


class ManagerRPCAPI(service.RPCClient):
    """Client side for the Manager RPC API.

    Used from other services to communicate with blazar-manager service.
    """
    def __init__(self):
        """Initiate RPC API client with needed topic and RPC version."""
        super(ManagerRPCAPI, self).__init__(manager.get_target())

    def get_lease(self, lease_id):
        """Get detailed info about some lease."""
        return self.call('get_lease', lease_id=lease_id)

    def list_leases(self, project_id=None, query=None):
        """List all leases."""
        return self.call('list_leases', project_id=project_id, query=query)

    def create_lease(self, lease_values):
        """Create lease with specified parameters."""
        return self.call('create_lease', lease_values=lease_values)

    def update_lease(self, lease_id, values):
        """Update lease with passes values dictionary."""
        return self.call('update_lease', lease_id=lease_id, values=values)

    def delete_lease(self, lease_id):
        """Delete specified lease."""
        return self.call('delete_lease', lease_id=lease_id)
