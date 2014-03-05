# Copyright (c) 2014 Bull.
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

"""Version 2 of the API.
"""

import pecan

from climate.api.v2.controllers import host
from climate.api.v2.controllers import lease
from climate.openstack.common.gettextutils import _  # noqa
from climate.openstack.common import log as logging

LOG = logging.getLogger(__name__)


class V2Controller(pecan.rest.RestController):
    """Version 2 API controller root."""

    _routes = {'os-hosts': 'oshosts',
               'oshosts': 'None'}

    leases = lease.LeasesController()
    oshosts = host.HostsController()

    @pecan.expose()
    def _route(self, args):
        """Overrides the default routing behavior.

        It allows to map controller URL with correct controller instance.
        By default, it maps with the same name.
        """

        try:
            args[0] = self._routes.get(args[0], args[0])
        except IndexError:
            LOG.error(_("No args found on V2 controller"))
        return super(V2Controller, self)._route(args)
