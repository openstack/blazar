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
import flask
from keystoneclient.middleware import auth_token
from oslo_config import cfg
from werkzeug import exceptions as werkzeug_exceptions

from climate.api.v1.oshosts import v1_0 as host_api_v1_0
from climate.api.v1 import utils as api_utils
from climate.api.v1 import v1_0 as api_v1_0
from climate.openstack.common import log
from climate.openstack.common.middleware import debug


LOG = log.getLogger(__name__)

CONF = cfg.CONF

CONF.import_opt('os_auth_host', 'climate.config')
CONF.import_opt('os_auth_port', 'climate.config')
CONF.import_opt('os_auth_protocol', 'climate.config')
CONF.import_opt('os_admin_username', 'climate.config')
CONF.import_opt('os_admin_password', 'climate.config')
CONF.import_opt('os_admin_project_name', 'climate.config')
CONF.import_opt('os_auth_version', 'climate.config')
CONF.import_opt('log_exchange', 'climate.config')


eventlet.monkey_patch(
    os=True, select=True, socket=True, thread=True, time=True)


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
                        "rel": "self"}]
             },
        ],
    }, status="300 Multiple Choices")


def make_app():
    """App builder (wsgi).

    Entry point for Climate REST API server.
    """
    app = flask.Flask('climate.api')

    app.route('/', methods=['GET'])(version_list)
    app.route('/versions', methods=['GET'])(version_list)
    app.register_blueprint(api_v1_0.rest, url_prefix='/v1')

    LOG.debug("List of plugins: %s", cfg.CONF.manager.plugins)
    # TODO(sbauza) : Change this whole crap by removing hardcoded values and
    #   maybe using stevedore for achieving this
    if (cfg.CONF.manager.plugins
            and 'physical.host.plugin' in cfg.CONF.manager.plugins):
        app.register_blueprint(host_api_v1_0.rest, url_prefix='/v1/os-hosts')

    for code in werkzeug_exceptions.default_exceptions.iterkeys():
        app.error_handler_spec[None][code] = make_json_error

    if cfg.CONF.debug and not cfg.CONF.log_exchange:
        LOG.debug('Logging of request/response exchange could be enabled '
                  'using flag --log_exchange')

    if cfg.CONF.log_exchange:
        app.wsgi_app = debug.Debug.factory(app.config)(app.wsgi_app)

    app.wsgi_app = auth_token.filter_factory(
        app.config,
        auth_host=cfg.CONF.os_auth_host,
        auth_port=cfg.CONF.os_auth_port,
        auth_protocol=cfg.CONF.os_auth_protocol,
        admin_user=cfg.CONF.os_admin_username,
        admin_password=cfg.CONF.os_admin_password,
        admin_tenant_name=cfg.CONF.os_admin_project_name,
        auth_version=cfg.CONF.os_auth_version,
    )(app.wsgi_app)

    return app
