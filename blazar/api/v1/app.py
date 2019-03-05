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

import flask
from keystonemiddleware import auth_token
from oslo_config import cfg
from oslo_log import log as logging
from oslo_middleware import debug
from stevedore import enabled
from werkzeug import exceptions as werkzeug_exceptions

from blazar.api.v1 import api_version_request
from blazar.api.v1 import request_id
from blazar.api.v1 import request_log
from blazar.api.v1 import utils as api_utils


LOG = logging.getLogger(__name__)

CONF = cfg.CONF

CONF.import_opt('log_exchange', 'blazar.config')


def make_json_error(ex):
    if isinstance(ex, werkzeug_exceptions.HTTPException):
        status_code = ex.code
        description = ex.description
    else:
        status_code = 500
        description = str(ex)
    return api_utils.render({'error': status_code,
                             'error_message': description},
                            status=status_code)


def version_list():
    return api_utils.render({
        "versions": [
            {"id": "v1.0",
             "status": "CURRENT",
             "links": [{"href": "{0}v1".format(flask.request.host_url),
                        "rel": "self"}],
             "min_version": api_version_request.MIN_API_VERSION,
             "max_version": api_version_request.MAX_API_VERSION,
             },
        ],
    }, status="300 Multiple Choices")


def make_app():
    """App builder (wsgi).

    Entry point for Blazar REST API server.
    """
    app = flask.Flask('blazar.api')

    app.route('/', methods=['GET'])(version_list)
    app.route('/versions', methods=['GET'])(version_list)

    LOG.debug("List of plugins: %s", cfg.CONF.manager.plugins)

    plugins = cfg.CONF.manager.plugins + ['leases']
    extension_manager = enabled.EnabledExtensionManager(
        check_func=lambda ext: ext.name in plugins,
        namespace='blazar.api.v1.extensions',
        invoke_on_load=False
        )

    for ext in extension_manager.extensions:
        bp = ext.plugin()
        app.register_blueprint(bp, url_prefix=bp.url_prefix)

    for code in werkzeug_exceptions.default_exceptions:
        app.register_error_handler(code, make_json_error)

    if cfg.CONF.debug and not cfg.CONF.log_exchange:
        LOG.debug('Logging of request/response exchange could be enabled '
                  'using flag --log_exchange')

    if cfg.CONF.log_exchange:
        app.wsgi_app = debug.Debug.factory(app.config)(app.wsgi_app)

    app.wsgi_app = request_id.BlazarReqIdMiddleware(app.wsgi_app)
    app.wsgi_app = request_log.RequestLog(app.wsgi_app)
    app.wsgi_app = auth_token.filter_factory(app.config)(app.wsgi_app)

    return app
