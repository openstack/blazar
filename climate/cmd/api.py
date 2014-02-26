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

import gettext
import sys

import eventlet
from eventlet import wsgi
from oslo.config import cfg

gettext.install('climate', unicode=1)

from climate.api import app as api_app
from climate.openstack.common import log as logging
from climate.utils import service as service_utils


opts = [
    cfg.IntOpt('port', default=1234,
               help='Port that will be used to listen on'),
]


LOG = logging.getLogger(__name__)
CONF = cfg.CONF
CONF.register_cli_opts(opts)

cfg.CONF.import_opt('host', 'climate.config')


def main():
    """Entry point to start Climate API wsgi server."""
    cfg.CONF(sys.argv[1:], project='climate', prog='climate-api')
    service_utils.prepare_service(sys.argv)
    logging.setup("climate")
    app = api_app.make_app()

    wsgi.server(eventlet.listen((CONF.host, CONF.port), backlog=500), app)


if __name__ == '__main__':
    main()
