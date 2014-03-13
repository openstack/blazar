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

from novaclient import client as nova_client
from novaclient import exceptions as nova_exception
from novaclient.v1_1 import servers
from oslo.config import cfg

from climate import context
from climate.utils.openstack import base


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
CONF.import_opt('identity_service', 'climate.utils.openstack.keystone')


class ClimateNovaClient(object):
    def __init__(self, **kwargs):
        """We suppose that in future we may want to use CNC in some places
        where context will be available, so we create 2 different ways of
        creating client from context(future) and kwargs(we use it now).

        :param version: service client version which we will use
        :type version: str

        :param username: username
        :type username: str

        :param api_key: password
        :type api_key: str

        :param auth_token: keystone auth token
        :type auth_token: str

        :param project_id: project_id
        :type api_key: str

        :param auth_url: auth_url
        :type auth_url: str

        :param mgmt_url: management url
        :type mgmt_url: str
        """

        ctx = kwargs.pop('ctx', None)
        auth_token = kwargs.pop('auth_token', None)
        mgmt_url = kwargs.pop('mgmt_url', None)

        if ctx is None:
            try:
                ctx = context.current()
            except RuntimeError:
                pass
        kwargs.setdefault('version', cfg.CONF.nova_client_version)
        if ctx is not None:
            kwargs.setdefault('username', ctx.user_name)
            kwargs.setdefault('api_key', None)
            kwargs.setdefault('project_id', ctx.project_id)
            kwargs.setdefault('auth_url', base.url_for(
                ctx.service_catalog, CONF.identity_service))

            auth_token = auth_token or ctx.auth_token
            mgmt_url = mgmt_url or base.url_for(ctx.service_catalog,
                                                CONF.compute_service)
        if not kwargs.get('auth_url', None):
            #NOTE(scroiset): novaclient v2.17.0 support only Identity API v2.0
            auth_url = "%s://%s:%s/v2.0" % (CONF.os_auth_protocol,
                                            CONF.os_auth_host,
                                            CONF.os_auth_port)
            kwargs['auth_url'] = auth_url

        self.nova = nova_client.Client(**kwargs)
        self.nova.client.auth_token = auth_token
        self.nova.client.management_url = mgmt_url

        self.nova.servers = ServerManager(self.nova)

        self.exceptions = nova_exception

    def __getattr__(self, name):
        return getattr(self.nova, name)


#todo(dbelova): remove these lines after novaclient 2.16.0 will be released
class ClimateServer(servers.Server):
    def unshelve(self):
        """Unshelve -- Unshelve the server."""
        self.manager.unshelve(self)


class ServerManager(servers.ServerManager):
    resource_class = ClimateServer

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
        nova = ClimateNovaClient(username=ctx.user_name,
                                 api_key=None,
                                 project_id=ctx.project_id,
                                 ctx=ctx)
        return nova
