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
import json
import sys

import eventlet
from eventlet import wsgi
from oslo_config import cfg
from oslo_log import log as logging

gettext.install('climate', unicode=1)

from climate.api.v1 import app as v1_app
from climate.api.v2 import app as v2_app
from climate.utils import service as service_utils


opts = [
    cfg.IntOpt('port', default=1234,
               help='Port that will be used to listen on'),
]

api_opts = [
    cfg.BoolOpt('enable_v1_api',
                default=True,
                help='Deploy the v1 API.'),
]


LOG = logging.getLogger(__name__)
CONF = cfg.CONF
CONF.register_cli_opts(opts)
CONF.register_opts(api_opts)

CONF.import_opt('host', 'climate.config')


class VersionSelectorApplication(object):
    """Maps WSGI versioned apps and defines default WSGI app."""

    def __init__(self):
        self._status = ''
        self._response_headers = []
        self.v1 = v1_app.make_app()
        self.v2 = v2_app.make_app()

    def _append_versions_from_app(self, versions, app, environ):
        tmp_versions = app(environ, self.internal_start_response)
        if self._status.startswith("300"):
            tmp_versions = json.loads("".join(tmp_versions))
            versions['versions'].extend(tmp_versions['versions'])

    def internal_start_response(self, status, response_headers, exc_info=None):
        self._status = status
        self._response_headers = response_headers

    def __call__(self, environ, start_response):
        self._status = ''
        self._response_headers = []

        if environ['PATH_INFO'] == '/' or environ['PATH_INFO'] == '/versions':
            versions = {'versions': []}
            self._append_versions_from_app(versions, self.v1, environ)
            self._append_versions_from_app(versions, self.v2, environ)
            if len(versions['versions']):
                start_response("300 Multiple Choices",
                               [("Content-Type", "application/json")])
                return [json.dumps(versions)]
            else:
                start_response("204 No Content", [])
                return []
        else:
            if environ['PATH_INFO'].startswith('/v1'):
                return self.v1(environ, start_response)
            return self.v2(environ, start_response)


def main():
    """Entry point to start Climate API wsgi server."""
    cfg.CONF(sys.argv[1:], project='climate', prog='climate-api')
    service_utils.prepare_service(sys.argv)
    if not CONF.enable_v1_api:
        app = v2_app.make_app()
    else:
        app = VersionSelectorApplication()

    wsgi.server(eventlet.listen((CONF.host, CONF.port), backlog=500), app)


if __name__ == '__main__':
    main()
