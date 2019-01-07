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

from blazar.api.v1.networks import service
from blazar.api.v1 import utils as api_utils
from blazar.api.v1 import validation
from blazar import utils


rest = api_utils.Rest('network_v1_0', __name__)
_api = utils.LazyProxy(service.API)


# networks operations

@rest.get('')
def networks_list():
    """List all existing networks."""
    return api_utils.render(networks=_api.get_networks())


@rest.post('')
def networks_create(data):
    """Create new network."""
    return api_utils.render(network=_api.create_network(data))


@rest.get('/<network_id>')
@validation.check_exists(_api.get_network, network_id='network_id')
def networks_get(network_id):
    """Get network by its ID."""
    return api_utils.render(network=_api.get_network(network_id))


@rest.put('/<network_id>')
@validation.check_exists(_api.get_network, network_id='network_id')
def networks_update(network_id, data):
    """Update network. Only name changing may be proceeded."""
    if len(data) == 0:
        return api_utils.internal_error(status_code=400,
                                        descr="No data to update")
    else:
        return api_utils.render(network=_api.update_network(network_id, data))


@rest.delete('/<network_id>')
@validation.check_exists(_api.get_network, network_id='network_id')
def networks_delete(network_id):
    """Delete specified network."""
    _api.delete_network(network_id)
    return api_utils.render()
