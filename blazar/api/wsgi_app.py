# Copyright (c) 2017 NTT Inc.
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

import os

from oslo_config import cfg
from oslo_log import log as logging

from blazar.api import app as wsgi_app
from blazar.api.v2 import app as v2_app
from blazar.utils import service as service_utils


CONF = cfg.CONF
CONF.import_opt('enable_v1_api', 'blazar.config')
logging.register_options(CONF)

CONFIG_FILES = ['blazar.conf']


def _get_config_files(env=None):
    if env is None:
        env = os.environ
    dirname = env.get('OS_BLAZAR_CONFIG_DIR', '/etc/blazar').strip()
    return [os.path.join(dirname, config_file)
            for config_file in CONFIG_FILES]


def init_app():
    config_files = _get_config_files()
    CONF([], project='blazar', prog='blazar-api',
         default_config_files=config_files)
    service_utils.prepare_service()
    if not CONF.enable_v1_api:
        app = v2_app.make_app()
    else:
        app = wsgi_app.VersionSelectorApplication()

    return app
