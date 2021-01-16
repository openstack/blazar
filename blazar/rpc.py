#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
from oslo_config import cfg
import oslo_messaging as messaging


CONF = cfg.CONF
TRANSPORT = None


def init():
    global TRANSPORT
    if TRANSPORT is None:
        TRANSPORT = create_transport(get_transport_url())


def get_transport_url(url_str=None):
    return messaging.TransportURL.parse(CONF, url_str)


def get_client(target):
    if TRANSPORT is None:
        raise AssertionError("'TRANSPORT' must not be None")
    return messaging.RPCClient(
        TRANSPORT,
        target,
    )


def get_server(target, endpoints):
    if TRANSPORT is None:
        raise AssertionError("'TRANSPORT' must not be None")
    return messaging.get_rpc_server(
        TRANSPORT,
        target,
        endpoints,
        executor='eventlet',
    )


def create_transport(url):
    return messaging.get_rpc_transport(CONF, url=url)
