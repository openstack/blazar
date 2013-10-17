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
from oslo.config import cfg

from climate import context
from climate.manager import exceptions as manager_exceptions
from climate.utils.openstack import base


nova_opts = [
    cfg.StrOpt('nova_client_version',
               default='2',
               help='Novaclient version'),
    cfg.StrOpt('compute_service',
               default='compute',
               help='Nova name in keystone'),
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

        if ctx is None:
            try:
                ctx = context.current()
            except RuntimeError:
                pass
        kwargs.setdefault('version', cfg.CONF.nova_client_version)
        if ctx is not None:
            kwargs.setdefault('username', ctx.user_name)
            kwargs.setdefault('api_key', None)
            kwargs.setdefault('auth_token', ctx.auth_token)
            kwargs.setdefault('project_id', ctx.tenant_id)
            if not kwargs.get('auth_url'):
                kwargs['auth_url'] = base.url_for(
                    ctx.service_catalog, CONF.identity_service)

        try:
            mgmt_url = kwargs.pop('mgmt_url', None) or base.url_for(
                ctx.service_catalog, CONF.compute_service)
        except AttributeError:
            raise manager_exceptions.NoManagementUrl()

        self.nova = nova_client.Client(**kwargs)

        self.nova.client.management_url = mgmt_url
        self.exceptions = nova_exception

    def _image_create(self, instance_id):
        instance = self.nova.servers.get(instance_id)
        instance_name = instance.name
        self.nova.servers.create_image(instance_id,
                                       "reserved_%s" % instance_name)

    def __getattr__(self, name):
        if name == 'create_image':
            func = self._image_create
        else:
            func = getattr(self.nova, name)

        return func
