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

from keystoneauth1 import session
from keystoneauth1 import token_endpoint
from novaclient import client as nova_client
from novaclient import exceptions as nova_exception
from novaclient.v2 import servers
from oslo_config import cfg

from blazar import context
from blazar.utils.openstack import base


nova_opts = [
    cfg.StrOpt('nova_client_version',
               default='2',
               help='Novaclient version'),
    cfg.StrOpt('compute_service',
               default='compute',
               help='Nova name in keystone'),
    cfg.StrOpt('image_prefix',
               default='reserved_',
               help='Prefix for VM images if you want to create snapshots')
]

CONF = cfg.CONF
CONF.register_opts(nova_opts)
CONF.import_opt('identity_service', 'blazar.utils.openstack.keystone')


class BlazarNovaClient(object):
    def __init__(self, **kwargs):
        """Description

        We suppose that in future we may want to use CNC in some places
        where context will be available, so we create 2 different ways of
        creating client from context(future) and kwargs(we use it now).

        :param version: service client version which we will use
        :type version: str

        :param auth_token: keystone auth token
        :type auth_token: str

        :param endpoint_override: endpoint url which we will use
        :type endpoint_override: str
        """

        ctx = kwargs.pop('ctx', None)
        auth_token = kwargs.pop('auth_token', None)
        endpoint_override = kwargs.pop('endpoint_override', None)
        version = kwargs.pop('version', cfg.CONF.nova_client_version)

        if ctx is None:
            try:
                ctx = context.current()
            except RuntimeError:
                pass
        if ctx is not None:
            auth_token = auth_token or ctx.auth_token
            endpoint_override = endpoint_override or \
                base.url_for(ctx.service_catalog,
                             CONF.compute_service)

        auth = token_endpoint.Token(endpoint_override,
                                    auth_token)
        sess = session.Session(auth=auth)

        kwargs.setdefault('endpoint_override', endpoint_override)
        kwargs.setdefault('session', sess)
        kwargs.setdefault('version', version)
        self.nova = nova_client.Client(**kwargs)

        self.nova.servers = ServerManager(self.nova)

        self.exceptions = nova_exception

    def __getattr__(self, name):
        return getattr(self.nova, name)


# TODO(dbelova): remove these lines after novaclient 2.16.0 will be released
class BlazarServer(servers.Server):
    def unshelve(self):
        """Unshelve -- Unshelve the server."""
        self.manager.unshelve(self)


class ServerManager(servers.ServerManager):
    resource_class = BlazarServer

    def unshelve(self, server):
        """Unshelve the server."""
        self._action('unshelve', server, None)

    def create_image(self, server_id, image_name=None, metadata=None):
        """Snapshot a server."""
        server_name = self.get(server_id).name
        if image_name is None:
            image_name = cfg.CONF.image_prefix + server_name
        return super(ServerManager, self).create_image(server_id,
                                                       image_name=image_name,
                                                       metadata=metadata)


class NovaClientWrapper(object):
    @property
    def nova(self):
        ctx = context.current()
        nova = BlazarNovaClient(ctx=ctx)
        return nova
