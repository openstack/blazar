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

from oslo_log import log as logging

from blazar import context
from blazar.manager.leases import rpcapi as manager_rpcapi
from blazar import policy
from blazar.utils import trusts

LOG = logging.getLogger(__name__)


class API(object):

    def __init__(self):
        self.manager_rpcapi = manager_rpcapi.ManagerRPCAPI()

    # Leases operations

    @policy.authorize('leases', 'get')
    def get_leases(self, query):
        """List all existing leases."""
        ctx = context.current()
        if policy.enforce(ctx, 'admin', {}, do_raise=False):
            project_id = None
        else:
            project_id = ctx.project_id
        return self.manager_rpcapi.list_leases(project_id=project_id,
                                               query=query)

    @policy.authorize('leases', 'post')
    @trusts.use_trust_auth()
    def create_lease(self, data):
        """Create new lease.

        :param data: New lease characteristics.
        :type data: dict
        """
        # TODO(priteau): If possible, extend the context object used in the
        # manager to keep track of the trustor, instead of using the following
        # two lines
        ctx = context.current()
        data['user_id'] = ctx.user_id
        return self.manager_rpcapi.create_lease(data)

    @policy.authorize('leases', 'get')
    def get_lease(self, lease_id):
        """Get lease by its ID.

        :param lease_id: ID of the lease in Blazar DB.
        :type lease_id: str
        """
        return self.manager_rpcapi.get_lease(lease_id)

    @policy.authorize('leases', 'put')
    def update_lease(self, lease_id, data):
        """Update lease.

        :param lease_id: ID of the lease in Blazar DB.
        :type lease_id: str
        :param data: New lease characteristics.
        :type data: dict
        """
        return self.manager_rpcapi.update_lease(lease_id, data)

    @policy.authorize('leases', 'delete')
    def delete_lease(self, lease_id):
        """Delete specified lease.

        :param lease_id: ID of the lease in Blazar DB.
        :type lease_id: str
        """
        self.manager_rpcapi.delete_lease(lease_id)

    # Plugins operations

    @policy.authorize('plugins', 'get')
    def get_plugins(self):
        """List all possible plugins."""
        pass
