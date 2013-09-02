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

from climate.openstack.common import log as logging


LOG = logging.getLogger(__name__)


## Leases operations

def get_leases():
    """List all existing leases."""
    pass


def create_lease(data):
    """Create new lease.

    :param data: New lease characteristics.
    :type data: dict
    """
    pass


def get_lease(lease_id):
    """Get lease by its ID.

    :param lease_id: ID of the lease in Climate DB.
    :type lease_id: str
    """
    pass


def update_lease(lease_id, data):
    """Update lease. Only name changing and prolonging may be proceeded.

    :param lease_id: ID of the lease in Climate DB.
    :type lease_id: str
    :param data: New lease characteristics.
    :type data: dict
    """
    pass


def delete_lease(lease_id):
    """Delete specified lease.

    :param lease_id: ID of the lease in Climate DB.
    :type lease_id: str
    """
    pass


## Plugins operations

def get_plugins():
    """List all possible plugins."""
    pass
