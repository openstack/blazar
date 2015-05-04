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

from keystoneclient import client as keystone_client
from keystoneclient import exceptions as keystone_exception
from oslo_config import cfg

from climate import context
from climate.manager import exceptions as manager_exceptions
from climate.utils.openstack import base


opts = [
    cfg.StrOpt('identity_service',
               default='identityv3',
               help='Identity service to use.')
]

keystone_opts = [
    cfg.StrOpt('keystone_client_version',
               default='3',
               help='Keystoneclient version'),
]

CONF = cfg.CONF
CONF.register_cli_opts(opts)
CONF.register_opts(keystone_opts)


class ClimateKeystoneClient(object):
    def __init__(self, **kwargs):
        """Description

        Return Keystone client for defined in 'identity_service' conf.
        NOTE: We will use tenant_name until we start using keystone V3
        client for all our needs.

        :param version: service client version which we will use
        :type version: str

        :param username: username
        :type username: str

        :param password: password
        :type password: str

        :param tenant_name: tenant_name
        :type tenant_name: str

        :param auth_url: auth_url
        :type auth_url: str

        :param ctx: climate context object
        :type ctx: dict

        :param auth_url: keystone auth url
        :type auth_url: string

        :param endpoint: keystone management (endpoint) url
        :type endpoint: string

        :param trust_id: keystone trust ID
        :type trust_id: string

        :param token: user token to use for authentication
        :type token: string
        """

        ctx = kwargs.pop('ctx', None)
        if ctx is None:
            try:
                ctx = context.current()
            except RuntimeError:
                pass

        kwargs.setdefault('version', cfg.CONF.keystone_client_version)
        if ctx is not None:
            kwargs.setdefault('username', ctx.user_name)
            kwargs.setdefault('tenant_name', ctx.project_name)
            if not kwargs.get('auth_url'):
                kwargs['auth_url'] = base.url_for(
                    ctx.service_catalog, CONF.identity_service)
            if not kwargs.get('trust_id'):
                try:
                    kwargs.setdefault('endpoint', base.url_for(
                        ctx.service_catalog, CONF.identity_service,
                        endpoint_interface='admin'))
                except AttributeError:
                    raise manager_exceptions.NoManagementUrl()
            if not kwargs.get('password'):
                kwargs.setdefault('token', ctx.auth_token)

        # NOTE(dbelova): we need this checking to support current
        # keystoneclient: token can only be scoped now to either
        # a trust or project, not both.
        if kwargs.get('trust_id') and kwargs.get('tenant_name'):
            kwargs.pop('tenant_name')

        try:
            # NOTE(n.s.): we shall remove this try: except: clause when
            # https://review.openstack.org/#/c/66494/ will be merged
            self.keystone = keystone_client.Client(**kwargs)
            self.keystone.session.auth = self.keystone
            self.keystone.authenticate(auth_url=kwargs.get('auth_url', None))
        except AttributeError:
            raise manager_exceptions.WrongClientVersion()

        self.exceptions = keystone_exception

    def __getattr__(self, name):
        func = getattr(self.keystone, name)
        return func
