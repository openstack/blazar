# Copyright (c) 2019 NTT.
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

from blazar.api.v1.floatingips import service
from blazar.api.v1 import utils as api_utils
from blazar.api.v1 import validation
from blazar import utils


def get_rest():
    """Return Rest app"""
    return rest


rest = api_utils.Rest('floatingip_v1_0', __name__,
                      url_prefix='/v1/floatingips')
_api = utils.LazyProxy(service.API)


# Floatingips operations

@rest.get('')
def floatingips_list(req):
    """List all existing floatingips."""
    return api_utils.render(floatingips=_api.get_floatingips())


@rest.post('')
def floatingips_create(req, data):
    """Create new floatingip."""
    return api_utils.render(floatingip=_api.create_floatingip(data))


@rest.get('/<floatingip_id>')
@validation.check_exists(_api.get_floatingip, floatingip_id='floatingip_id')
def floatingips_get(req, floatingip_id):
    """Get floatingip by its ID."""
    return api_utils.render(floatingip=_api.get_floatingip(floatingip_id))


@rest.delete('/<floatingip_id>')
@validation.check_exists(_api.get_floatingip, floatingip_id='floatingip_id')
def floatingips_delete(req, floatingip_id):
    """Delete specified floatingip."""
    _api.delete_floatingip(floatingip_id)
    return api_utils.render()
