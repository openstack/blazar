# -*- encoding: utf-8 -*-
#
# Copyright © 2013 Julien Danjou <julien@danjou.info>
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import os
from oslo.config import cfg

from novaclient import client
from climate import inventory


CLI_OPTIONS = [
    cfg.StrOpt('os-username',
               default=os.environ.get('OS_USERNAME', 'climate'),
               help='Username to use for OpenStack service access'),
    cfg.StrOpt('os-password',
               default=os.environ.get('OS_PASSWORD', 'admin'),
               help='Password to use for OpenStack service access'),
    cfg.StrOpt('os-tenant-id',
               default=os.environ.get('OS_TENANT_ID', ''),
               help='Tenant ID to use for OpenStack service access'),
    cfg.StrOpt('os-tenant-name',
               default=os.environ.get('OS_TENANT_NAME', 'admin'),
               help='Tenant name to use for OpenStack service access'),
    cfg.StrOpt('os-auth-url',
               default=os.environ.get('OS_AUTH_URL',
                                      'http://localhost:5000/v2.0'),
               help='Auth URL to use for openstack service access'),
]
cfg.CONF.register_cli_opts(CLI_OPTIONS)


class NovaInventory(inventory.Plugin):

    def __init__(self):
        self.novaclient = client.Client(
            "2",
            username=cfg.CONF.os_username,
            api_key=cfg.CONF.os_password,
            auth_url=cfg.CONF.os_auth_url,
            project_id=cfg.CONF.os_tenant_name or cfg.CONF.os_tenant_id)

    def list_hosts(self):
        return self.novaclient.hypervisors.list()

    def get_host_details(self, host):
        return self.novaclient.hypervisors.get(host)
