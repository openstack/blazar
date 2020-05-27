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

import re

from keystoneclient import client as keystone_client
from keystoneclient import exceptions as keystone_exception
from oslo_config import cfg

from blazar import context
from blazar import exceptions
from blazar.manager import exceptions as manager_exceptions
from blazar.utils.openstack import base


opts = [
    cfg.StrOpt('identity_service',
               default='identity',
               help='Identity service to use.'),
    cfg.StrOpt('os_region_name',
               default=None,
               help="""
Region name of this node. This is used when picking the URL in the service
catalog.

Possible values:

* Any string representing region name
""")
]

keystone_opts = [
    cfg.StrOpt('keystone_client_version',
               default='3',
               help='Keystoneclient version'),
]

CONF = cfg.CONF
CONF.register_cli_opts(opts)
CONF.register_opts(keystone_opts)


class BlazarKeystoneClient(object):
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

        :param ctx: blazar context object
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
            kwargs.setdefault('user_domain_name', ctx.user_domain_name)
            kwargs.setdefault('project_name', ctx.project_name)
            kwargs.setdefault('project_domain_name', ctx.project_domain_name)
            kwargs.setdefault('global_request_id', ctx.global_request_id)
            if not kwargs.get('auth_url'):
                kwargs['auth_url'] = base.url_for(
                    ctx.service_catalog, CONF.identity_service,
                    os_region_name=CONF.os_region_name)
            if not kwargs.get('trust_id'):
                try:
                    kwargs.setdefault('endpoint', base.url_for(
                        ctx.service_catalog, CONF.identity_service,
                        endpoint_interface='admin',
                        os_region_name=CONF.os_region_name))
                except AttributeError:
                    raise manager_exceptions.NoManagementUrl()
            if not kwargs.get('password'):
                kwargs.setdefault('token', ctx.auth_token)

        # NOTE(dbelova): we need this checking to support current
        # keystoneclient: token can only be scoped now to either
        # a trust or project, not both.
        if kwargs.get('trust_id') and kwargs.get('project_name'):
            kwargs.pop('project_name')

        try:
            # NOTE(n.s.): we shall remove this try: except: clause when
            # https://review.openstack.org/#/c/66494/ will be merged
            self.keystone = keystone_client.Client(**kwargs)
            self.keystone.session.auth = self.keystone
            auth_url = self.complement_auth_url(kwargs.get('auth_url', None),
                                                kwargs.get('version', None))
            self.keystone.authenticate(auth_url=auth_url)
        except AttributeError:
            raise manager_exceptions.WrongClientVersion()

        self.exceptions = keystone_exception

    def complement_auth_url(self, auth_url, version):
        """Return auth_url with api version.

        This method checks whether auth_url contains api version info.
        If api version info is not contained in auth_url, this method
        complements version info to auth_url. This method only support
        complementing auth_url to v3 api url since we use keystone v3
        api to treat trusts.
        """

        # Create api version from major number of keystoneclient version.
        # keystoneclient version can take forms of "3", "v3" or "3.0" and
        # so this method convert them to form of "v3" for keystone api
        # version.
        api_version = version
        if isinstance(api_version, str):
            api_version = api_version.lstrip('v')

        api_version = int(float(api_version))

        if api_version != 3:
            raise exceptions.UnsupportedAPIVersion(version=api_version)

        if re.search(r'/v2.0/{,1}$', auth_url) is not None:
            raise exceptions.UnsupportedAPIVersion(version='v2.0')
        elif re.search(r'/v3/{,1}$', auth_url) is None:
            complemented_url = auth_url.rstrip('/') + '/v' + str(api_version)
        else:
            return auth_url

        return complemented_url

    def __getattr__(self, name):
        func = getattr(self.keystone, name)
        return func
