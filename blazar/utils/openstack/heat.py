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

from heatclient import client as heat_client
from keystoneauth1 import session
from keystoneauth1 import token_endpoint
from oslo_config import cfg
from oslo_log import log as logging

from blazar import context
from blazar.utils.openstack import base


heat_opts = [
    cfg.StrOpt(
        'heat_api_version',
        default='1',
        deprecated_group='DEFAULT',
        help='Heat API version'),
    cfg.StrOpt(
        'orchestration_service',
        default='orchestration',
        deprecated_group='DEFAULT',
        help='Heat name in keystone')
]

CONF = cfg.CONF
CONF.register_opts(heat_opts, group='heat')
CONF.import_opt('identity_service', 'blazar.utils.openstack.keystone')
LOG = logging.getLogger(__name__)


class BlazarHeatClient(object):

    def __init__(self, ctx=None):

        if ctx is None:
            ctx = context.current()

        endpoint_override = base.url_for(
            ctx.service_catalog,
            CONF.heat.orchestration_service,
            os_region_name=CONF.os_region_name)

        auth = token_endpoint.Token(endpoint_override, ctx.auth_token)
        sess = session.Session(auth=auth)

        self.heat = heat_client.Client(
            CONF.heat.heat_api_version, session=sess)

    def __getattr_(self, name):
        return getattr(self.heat, name)
