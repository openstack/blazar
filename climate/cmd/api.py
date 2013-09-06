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
import os
import sys

import eventlet
from eventlet import wsgi
from oslo.config import cfg


gettext.install('climate', unicode=1)

from climate.api import app as api_app
from climate import config
from climate.openstack.common import log as logging
from climate.utils import service as service_utils


opts = [
    cfg.IntOpt('port', default=1234,
               help='Port that will be used to listen on'),
]


LOG = logging.getLogger(__name__)
CONF = cfg.CONF
CONF.register_cli_opts(opts)


def main():
    """Entry point to start Climate API wsgi server."""
    possible_topdir = os.path.join(os.path.abspath(sys.argv[0]),
                                   os.pardir, os.pardir)
    possible_topdir = os.path.normpath(possible_topdir)

    dev_conf = os.path.join(possible_topdir, 'etc', 'climate', 'climate.conf')
    config_files = None

    if os.path.exists(dev_conf):
        config_files = [dev_conf]

    config.parse_configs(sys.argv[1:], config_files)
    service_utils.prepare_service(sys.argv)
    logging.setup("climate")
    app = api_app.make_app()

    wsgi.server(eventlet.listen((CONF.host, CONF.port), backlog=500), app)


if __name__ == '__main__':
    main()
