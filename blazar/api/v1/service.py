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
from blazar import exceptions
from blazar.manager import rpcapi as manager_rpcapi
from blazar import policy
from blazar.utils import trusts

LOG = logging.getLogger(__name__)


class API(object):

    def __init__(self):
        self.manager_rpcapi = manager_rpcapi.ManagerRPCAPI()

    # Leases operations

    @policy.authorize('leases', 'get')
    def get_leases(self):
        """List all existing leases."""
        ctx = context.current()
        if policy.enforce(ctx, 'admin', {}, do_raise=False):
            project_id = None
        else:
            project_id = ctx.project_id
        return self.manager_rpcapi.list_leases(project_id=project_id)

    @policy.authorize('leases', 'create')
    @trusts.use_trust_auth()
    def create_lease(self, data):
        """Create new lease.

        :param data: New lease characteristics.
        :type data: dict
        """
        return self.manager_rpcapi.create_lease(data)

    @policy.authorize('leases', 'get')
    def get_lease(self, lease_id):
        """Get lease by its ID.

        :param lease_id: ID of the lease in Blazar DB.
        :type lease_id: str
        """
        return self.manager_rpcapi.get_lease(lease_id)

    @policy.authorize('leases', 'update')
    def update_lease(self, lease_id, data):
        """Update lease. Only name changing and prolonging may be proceeded.

        :param lease_id: ID of the lease in Blazar DB.
        :type lease_id: str
        :param data: New lease characteristics.
        :type data: dict
        """
        new_name = data.pop('name', None)
        end_date = data.pop('end_date', None)
        start_date = data.pop('start_date', None)

        if data:
            raise exceptions.BlazarException('Only name changing and '
                                             'dates changing may be '
                                             'proceeded.')
        data = {}
        if new_name:
            data['name'] = new_name
        if end_date:
            data['end_date'] = end_date
        if start_date:
            data['start_date'] = start_date
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
