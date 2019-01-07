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

from blazar.manager.networks import rpcapi as manager_rpcapi
from blazar import policy
from blazar.utils import trusts


class API(object):
    def __init__(self):
        self.manager_rpcapi = manager_rpcapi.ManagerRPCAPI()

    @policy.authorize('networks', 'get')
    def get_networks(self):
        """List all existing networks."""
        return self.manager_rpcapi.list_networks()

    @policy.authorize('networks', 'create')
    @trusts.use_trust_auth()
    def create_network(self, data):
        """Create new network.

        :param data: New network characteristics.
        :type data: dict
        """

        return self.manager_rpcapi.create_network(data)

    @policy.authorize('networks', 'get')
    def get_network(self, network_id):
        """Get network by its ID.

        :param network_id: ID of the network in Blazar DB.
        :type network_id: str
        """
        return self.manager_rpcapi.get_network(network_id)

    @policy.authorize('networks', 'update')
    def update_network(self, network_id, data):
        """Update network. Only name changing may be proceeded.

        :param network_id: ID of the network in Blazar DB.
        :type network_id: str
        :param data: New network characteristics.
        :type data: dict
        """
        return self.manager_rpcapi.update_network(network_id, data)

    @policy.authorize('networks', 'delete')
    def delete_network(self, network_id):
        """Delete specified network.

        :param network_id: ID of the network in Blazar DB.
        :type network_id: str
        """
        self.manager_rpcapi.delete_network(network_id)
