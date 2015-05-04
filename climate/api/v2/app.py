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

from keystoneclient.middleware import auth_token
from oslo_config import cfg
import pecan

from climate.api.v2 import hooks
from climate.api.v2 import middleware
from climate.openstack.common.middleware import debug


auth_opts = [
    cfg.StrOpt('auth_strategy',
               default='keystone',
               help='The strategy to use for auth: noauth or keystone.'),
]

CONF = cfg.CONF
CONF.register_opts(auth_opts)

CONF.import_opt('log_exchange', 'climate.config')

OPT_GROUP_NAME = 'keystone_authtoken'


def setup_app(pecan_config=None, extra_hooks=None):

    app_hooks = [hooks.ConfigHook(),
                 hooks.DBHook(),
                 hooks.ContextHook(),
                 hooks.RPCHook(),
                 ]
    # TODO(sbauza): Add stevedore extensions for loading hooks
    if extra_hooks:
        app_hooks.extend(extra_hooks)

    app = pecan.make_app(
        pecan_config.app.root,
        debug=CONF.debug,
        hooks=app_hooks,
        wrap_app=middleware.ParsableErrorMiddleware,
        guess_content_type_from_ext=False
    )

    # WSGI middleware for debugging
    if CONF.log_exchange:
        app = debug.Debug.factory(pecan_config)(app)

    # WSGI middleware for Keystone auth
    # NOTE(sbauza): ACLs are always active unless for unittesting where
    #               enable_acl could be set to False
    if pecan_config.app.enable_acl:
        CONF.register_opts(auth_token.opts, group=OPT_GROUP_NAME)
        keystone_config = dict(CONF.get(OPT_GROUP_NAME))
        app = auth_token.AuthProtocol(app, conf=keystone_config)

    return app


def make_app():
    config = {
        'app': {
            'modules': ['climate.api.v2'],
            'root': 'climate.api.root.RootController',
            'enable_acl': True,
        }
    }
    # NOTE(sbauza): Fill Pecan config and call modules' path app.setup_app()
    app = pecan.load_app(config)
    return app
