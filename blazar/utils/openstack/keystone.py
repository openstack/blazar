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
    cfg.StrOpt('endpoint_type',
               default='internal',
               choices=['public', 'admin', 'internal'],
               help='Type of the keystone endpoint to use. This endpoint will '
                    'be looked up in the keystone catalog and should be one '
                    'of public, internal or admin.'),
    cfg.StrOpt('keystone_client_version',
               default='3',
               help='Keystoneclient version'),
]

CONF = cfg.CONF
CONF.register_cli_opts(opts)
CONF.register_opts(keystone_opts)


class BlazarKeystoneClient(object):
    def __init__(self, as_user=False, **kwargs):
        """Return Keystone client for defined in 'identity_service' conf."""
        if as_user:
            client_kwargs = base.client_user_kwargs(**kwargs)
        else:
            client_kwargs = base.client_kwargs(**kwargs)

        client_kwargs.setdefault('version', cfg.CONF.keystone_client_version)
        self.keystone = keystone_client.Client(**client_kwargs)
        self.exceptions = keystone_exception

    def __getattr__(self, name):
        func = getattr(self.keystone, name)
        return func
