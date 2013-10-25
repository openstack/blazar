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

from climate.manager.oshosts import rpcapi as manager_rpcapi
from climate.openstack.common import log as logging


LOG = logging.getLogger(__name__)


class API(object):
    def __init__(self):
        self.manager_rpcapi = manager_rpcapi.ManagerRPCAPI()

    def get_computehosts(self):
        """List all existing computehosts."""
        return self.manager_rpcapi.list_computehosts()

    def create_computehost(self, data):
        """Create new computehost.

        :param data: New computehost characteristics.
        :type data: dict
        """

        return self.manager_rpcapi.create_computehost(data)

    def get_computehost(self, host_id):
        """Get computehost by its ID.

        :param host_id: ID of the computehost in Climate DB.
        :type host_id: str
        """
        return self.manager_rpcapi.get_computehost(host_id)

    def update_computehost(self, host_id, data):
        """Update computehost. Only name changing may be proceeded.

        :param host_id: ID of the computehost in Climate DB.
        :type host_id: str
        :param data: New computehost characteristics.
        :type data: dict
        """
        return self.manager_rpcapi.update_computehost(host_id, data)

    def delete_computehost(self, host_id):
        """Delete specified computehost.

        :param host_id: ID of the computehost in Climate DB.
        :type host_id: str
        """
        self.manager_rpcapi.delete_computehost(host_id)
