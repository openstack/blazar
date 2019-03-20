# Copyright (c) 2019 NTT
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

from blazar.manager.floatingips import rpcapi as manager_rpcapi
from blazar import policy
from blazar.utils import trusts


class API(object):
    def __init__(self):
        self.manager_rpcapi = manager_rpcapi.ManagerRPCAPI()

    @policy.authorize('floatingips', 'get')
    def get_floatingips(self):
        """List all existing floatingip."""
        return self.manager_rpcapi.list_floatingips()

    @policy.authorize('floatingips', 'post')
    @trusts.use_trust_auth()
    def create_floatingip(self, data):
        """Create new floatingip.

        :param data: New floatingip characteristics.
        :type data: dict
        """

        return self.manager_rpcapi.create_floatingip(data)

    @policy.authorize('floatingips', 'get')
    def get_floatingip(self, floatingip_id):
        """Get floatingip by its ID.

        :param floatingip_id: ID of the floatingip in Blazar DB.
        :type floatingip_id: str
        """
        return self.manager_rpcapi.get_floatingip(floatingip_id)

    @policy.authorize('floatingips', 'delete')
    def delete_floatingip(self, floatingip_id):
        """Delete specified floatingip.

        :param floatingip_id: ID of the floatingip in Blazar DB.
        :type floatingip_id: str
        """
        self.manager_rpcapi.delete_floatingip(floatingip_id)
