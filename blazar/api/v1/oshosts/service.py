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

from blazar import context
from blazar.manager.oshosts import rpcapi as manager_rpcapi
from blazar import policy
from blazar.utils import trusts


class API(object):
    def __init__(self):
        self.manager_rpcapi = manager_rpcapi.ManagerRPCAPI()

    @policy.authorize('oshosts', 'get')
    def get_computehosts(self, query):
        """List all existing computehosts."""
        return self.manager_rpcapi.list_computehosts(query=query)

    @policy.authorize('oshosts', 'post')
    @trusts.use_trust_auth()
    def create_computehost(self, data):
        """Create new computehost.

        :param data: New computehost characteristics.
        :type data: dict
        """

        return self.manager_rpcapi.create_computehost(data)

    @policy.authorize('oshosts', 'get')
    def get_computehost(self, host_id):
        """Get computehost by its ID.

        :param host_id: ID of the computehost in Blazar DB.
        :type host_id: str
        """
        return self.manager_rpcapi.get_computehost(host_id)

    @policy.authorize('oshosts', 'put')
    def update_computehost(self, host_id, data):
        """Update computehost. Only name changing may be proceeded.

        :param host_id: ID of the computehost in Blazar DB.
        :type host_id: str
        :param data: New computehost characteristics.
        :type data: dict
        """
        return self.manager_rpcapi.update_computehost(host_id, data)

    @policy.authorize('oshosts', 'delete')
    def delete_computehost(self, host_id):
        """Delete specified computehost.

        :param host_id: ID of the computehost in Blazar DB.
        :type host_id: str
        """
        self.manager_rpcapi.delete_computehost(host_id)

    @policy.authorize('oshosts', 'get_allocations')
    def list_allocations(self, query):
        """List all allocations on all computehosts.

        :param query: parameters to query allocations
        :type query: dict
        """
        ctx = context.current()
        detail = False

        if policy.enforce(ctx, 'admin', {}, do_raise=False):
            detail = True

        return self.manager_rpcapi.list_allocations(query, detail=detail)

    @policy.authorize('oshosts', 'get_allocations')
    def get_allocations(self, host_id, query):
        """List all allocations on a specified computehost.

        :param host_id: ID of the computehost in Blazar DB.
        :type host_id: str
        :param query: parameters to query allocations
        :type query: dict
        """
        return self.manager_rpcapi.get_allocations(host_id, query)

    @policy.authorize('oshosts', 'reallocate')
    def reallocate(self, host_id, data):
        """Exchange host from allocations."""
        return self.manager_rpcapi.reallocate(host_id, data)
