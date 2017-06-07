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
               deprecated_group='DEFAULT',
               help='Novaclient version'),
    cfg.StrOpt('compute_service',
               default='compute',
               deprecated_group='DEFAULT',
               help='Nova name in keystone'),
    cfg.StrOpt('image_prefix',
               default='reserved_',
               deprecated_group='DEFAULT',
               help='Prefix for VM images if you want to create snapshots')
]

CONF = cfg.CONF
CONF.register_opts(nova_opts, group='nova')
CONF.import_opt('identity_service', 'blazar.utils.openstack.keystone')


class BlazarNovaClient(object):
    def __init__(self, **kwargs):
        """Description

        BlazarNovaClient can be used in two ways: from context or kwargs.

        :param version: service client version which we will use
        :type version: str

        :param ctx: request context
        :type ctx: context object

        :param auth_token: keystone auth token
        :type auth_token: str

        :param endpoint_override: endpoint url which we will use
        :type endpoint_override: str

        :param username: username to use with nova client
        :type username: str

        :param password: password to use with nova client
        :type password: str

        :param user_domain_name: domain name of the user
        :type user_domain_name: str

        :param project_name: project name to use with nova client
        :type project_name: str

        :param project_domain_name: domain name of the project
        :type project_domain_name: str

        :param auth_url: keystone url to authenticate against
        :type auth_url: str
        """

        ctx = kwargs.pop('ctx', None)
        auth_token = kwargs.pop('auth_token', None)
        endpoint_override = kwargs.pop('endpoint_override', None)
        version = kwargs.pop('version', CONF.nova.nova_client_version)
        username = kwargs.pop('username', None)
        password = kwargs.pop('password', None)
        user_domain_name = kwargs.pop('user_domain_name', None)
        project_name = kwargs.pop('project_name', None)
        project_domain_name = kwargs.pop('project_domain_name', None)
        auth_url = kwargs.pop('auth_url', None)

        if ctx is None:
            try:
                ctx = context.current()
            except RuntimeError:
                pass
        if ctx is not None:
            auth_token = auth_token or ctx.auth_token
            endpoint_override = endpoint_override or \
                base.url_for(ctx.service_catalog,
                             CONF.nova.compute_service)
            auth_url = base.url_for(ctx.service_catalog, CONF.identity_service)

        if auth_url is None:
            auth_url = "%s://%s:%s/v3" % (CONF.os_auth_protocol,
                                          CONF.os_auth_host,
                                          CONF.os_auth_port)

        if username:
            kwargs.setdefault('username', username)
            kwargs.setdefault('password', password)
            kwargs.setdefault('project_name', project_name)
            kwargs.setdefault('auth_url', auth_url)

            if "v2.0" not in auth_url:
                kwargs.setdefault('project_domain_name', project_domain_name)
                kwargs.setdefault('user_domain_name', user_domain_name)
        else:
            auth = token_endpoint.Token(endpoint_override,
                                        auth_token)
            sess = session.Session(auth=auth)
            kwargs.setdefault('session', sess)

        kwargs.setdefault('endpoint_override', endpoint_override)
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
            image_name = CONF.nova.image_prefix + server_name
        return super(ServerManager, self).create_image(server_id,
                                                       image_name=image_name,
                                                       metadata=metadata)


class NovaClientWrapper(object):
    def __init__(self, username=None, password=None, user_domain_name=None,
                 project_name=None, project_domain_name=None):
        self.username = username
        self.password = password
        self.user_domain_name = user_domain_name
        self.project_name = project_name
        self.project_domain_name = project_domain_name

    @property
    def nova(self):
        ctx = context.current()
        nova = BlazarNovaClient(ctx=ctx,
                                username=self.username,
                                password=self.password,
                                user_domain_name=self.user_domain_name,
                                project_name=self.project_name,
                                project_domain_name=self.project_domain_name)
        return nova
