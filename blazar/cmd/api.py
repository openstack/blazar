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

import eventlet
eventlet.monkey_patch(
    os=True, select=True, socket=True, thread=True, time=True)

import gettext
import sys

from eventlet import wsgi
from oslo_config import cfg
from oslo_log import log as logging

gettext.install('blazar')

from blazar.api import app as wsgi_app
from blazar.api.v2 import app as v2_app
from blazar.utils import service as service_utils


opts = [
    cfg.IntOpt('port',
               default=1234,
               min=0,
               max=65535,
               help='Port that will be used to listen on'),
]

LOG = logging.getLogger(__name__)
CONF = cfg.CONF
CONF.register_cli_opts(opts)

CONF.import_opt('host', 'blazar.config')
CONF.import_opt('enable_v1_api', 'blazar.config')


def main():
    """Entry point to start Blazar API wsgi server."""
    cfg.CONF(sys.argv[1:], project='blazar', prog='blazar-api')
    service_utils.prepare_service(sys.argv)
    if not CONF.enable_v1_api:
        app = v2_app.make_app()
    else:
        app = wsgi_app.VersionSelectorApplication()

    wsgi.server(eventlet.listen((CONF.host, CONF.port), backlog=500), app)


if __name__ == '__main__':
    main()
