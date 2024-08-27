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

from oslo_config import cfg
import oslo_messaging as messaging

opts = [
    cfg.StrOpt('rpc_topic',
               default='blazar.manager',
               help='The topic Blazar uses for blazar-manager messages.'),
]

CONF = cfg.CONF
CONF.register_opts(opts, 'manager')
CONF.import_opt('host', 'blazar.config')
RPC_API_VERSION = '1.0'


def get_target():
    return messaging.Target(topic=CONF.manager.rpc_topic,
                            version=RPC_API_VERSION,
                            namespace='manager.api')


def get_service_target():
    return messaging.Target(topic=CONF.manager.rpc_topic,
                            version=RPC_API_VERSION,
                            server=CONF.host,
                            namespace='manager.api')
