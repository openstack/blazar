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

from blazar.plugins import base


class DummyVMPlugin(base.BasePlugin):
    """Plugin for VM resource that does nothing."""
    resource_type = 'virtual:instance'
    title = 'Dummy VM Plugin'
    description = 'This plugin does nothing.'

    def get(self, resource_id):
        return None

    def reserve_resource(self, reservation_id, values):
        return None

    def list_allocations(self, query, detail=False):
        """List resource allocations."""
        pass

    def query_allocations(self, resource_id_list, lease_id=None,
                          reservation_id=None):
        return None

    def allocation_candidates(self, lease_values):
        return None

    def update_reservation(self, reservation_id, values):
        return None

    def on_start(self, resource_id):
        """Dummy VM plugin does nothing."""
        return 'VM %s should be waked up this moment.' % resource_id

    def on_end(self, resource_id):
        """Dummy VM plugin does nothing."""
        return 'VM %s should be deleted this moment.' % resource_id
