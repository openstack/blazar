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

from oslo_config import cfg
from oslo_log import log as logging
import pecan
from pecan import rest
from stevedore import enabled

from blazar import exceptions
from blazar.i18n import _

LOG = logging.getLogger(__name__)

api_opts = [
    cfg.ListOpt('api_v2_controllers',
                default=['oshosts', 'leases'],
                help='API extensions to use'),
]

CONF = cfg.CONF
CONF.register_opts(api_opts, 'api')


class V2Controller(rest.RestController):
    """Version 2 API controller root."""

    versions = [{"id": "v2.0", "status": "DEPRECATED"}]
    _routes = {}

    def _log_missing_plugins(self, names):
        for name in names:
            if name not in self.extension_manager.names():
                LOG.error("API Plugin %s was not loaded", name)

    def __init__(self):
        extensions = []

        self.extension_manager = enabled.EnabledExtensionManager(
            check_func=lambda ext: ext.name in CONF.api.api_v2_controllers,
            namespace='blazar.api.v2.controllers.extensions',
            invoke_on_load=True
        )
        self._log_missing_plugins(CONF.api.api_v2_controllers)

        for ext in self.extension_manager.extensions:
            try:
                setattr(self, ext.obj.name, ext.obj)
            except TypeError:
                raise exceptions.BlazarException(
                    _("API name must be specified for "
                        "extension {0}").format(ext.name))
            self._routes.update(ext.obj.extra_routes)
            extensions.append(ext.obj.name)

        LOG.debug("Loaded extensions: %s", extensions)

    @pecan.expose()
    def _route(self, args):
        """Overrides the default routing behavior.

        It allows to map controller URL with correct controller instance.
        By default, it maps with the same name.
        """

        try:
            route = self._routes.get(args[0], args[0])
            if route is None:
                # NOTE(sbauza): Route must map to a non-existing controller
                args[0] = 'http404-nonexistingcontroller'
            else:
                args[0] = route
        except IndexError:
            LOG.error("No args found on V2 controller")
        return super(V2Controller, self)._route(args)
