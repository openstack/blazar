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

from climate import exceptions
from climate.manager import rpcapi as manager_rpcapi
from climate.openstack.common import log as logging


LOG = logging.getLogger(__name__)


class API(object):

    def __init__(self):
        self.manager_rpcapi = manager_rpcapi.ManagerRPCAPI()

    ## Leases operations

    def get_leases(self):
        """List all existing leases."""
        return self.manager_rpcapi.list_leases()

    def create_lease(self, data):
        """Create new lease.

        :param data: New lease characteristics.
        :type data: dict
        """
        # here API should go to Keystone API v3 and create trust
        trust = 'trust'
        data.update({'trust': trust})
        return self.manager_rpcapi.create_lease(data)

    def get_lease(self, lease_id):
        """Get lease by its ID.

        :param lease_id: ID of the lease in Climate DB.
        :type lease_id: str
        """
        return self.manager_rpcapi.get_lease(lease_id)

    def update_lease(self, lease_id, data):
        """Update lease. Only name changing and prolonging may be proceeded.

        :param lease_id: ID of the lease in Climate DB.
        :type lease_id: str
        :param data: New lease characteristics.
        :type data: dict
        """
        new_name = data.pop('name', None)
        end_date = data.pop('end_date', None)
        start_date = data.pop('start_date', None)

        if data:
            raise exceptions.ClimateException('Only name changing and '
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

    def delete_lease(self, lease_id):
        """Delete specified lease.

        :param lease_id: ID of the lease in Climate DB.
        :type lease_id: str
        """
        self.manager_rpcapi.delete_lease(lease_id)

    ## Plugins operations

    def get_plugins(self):
        """List all possible plugins."""
        pass
