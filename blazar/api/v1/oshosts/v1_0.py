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

from blazar.api.v1.oshosts import service
from blazar.api.v1 import utils as api_utils
from blazar.api.v1 import validation
from blazar import utils


rest = api_utils.Rest('host_v1_0', __name__)
_api = utils.LazyProxy(service.API)


# Computehosts operations

@rest.get('')
def computehosts_list():
    """List all existing computehosts."""
    return api_utils.render(hosts=_api.get_computehosts())


@rest.post('')
def computehosts_create(data):
    """Create new computehost."""
    return api_utils.render(host=_api.create_computehost(data))


@rest.get('/<host_id>')
@validation.check_exists(_api.get_computehost, host_id='host_id')
def computehosts_get(host_id):
    """Get computehost by its ID."""
    return api_utils.render(host=_api.get_computehost(host_id))


@rest.put('/<host_id>')
@validation.check_exists(_api.get_computehost, host_id='host_id')
def computehosts_update(host_id, data):
    """Update computehost. Only name changing may be proceeded."""
    if len(data) == 0:
        return api_utils.internal_error(status_code=400,
                                        descr="No data to update")
    else:
        return api_utils.render(host=_api.update_computehost(host_id, data))


@rest.delete('/<host_id>')
@validation.check_exists(_api.get_computehost, host_id='host_id')
def computehosts_delete(host_id):
    """Delete specified computehost."""
    _api.delete_computehost(host_id)
    return api_utils.render()
