# Copyright (c) 2019 NTT.
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

from keystoneauth1.identity import v3
from keystoneauth1 import session
from neutronclient.v2_0 import client as neutron_client

from oslo_config import cfg
from oslo_log import log as logging

CONF = cfg.CONF
LOG = logging.getLogger(__name__)


class BlazarNeutronClient(object):
    """Client class for Neutron service."""

    def __init__(self, **kwargs):
        username = kwargs.pop('username',
                              CONF.os_admin_username)
        password = kwargs.pop('password',
                              CONF.os_admin_password)
        project_name = kwargs.pop('project_name',
                                  CONF.os_admin_project_name)
        user_domain_name = kwargs.pop('user_domain_name',
                                      CONF.os_admin_user_domain_name)
        project_domain_name = kwargs.pop('project_domain_name',
                                         CONF.os_admin_project_domain_name)
        auth_url = kwargs.pop('auth_url', None)

        if auth_url is None:
            auth_url = "%s://%s:%s/%s/%s" % (CONF.os_auth_protocol,
                                             CONF.os_auth_host,
                                             CONF.os_auth_port,
                                             CONF.os_auth_prefix,
                                             CONF.os_auth_version)

        auth = v3.Password(auth_url=auth_url,
                           username=username,
                           password=password,
                           project_name=project_name,
                           user_domain_name=user_domain_name,
                           project_domain_name=project_domain_name)
        sess = session.Session(auth=auth)
        self.neutron = neutron_client.Client(session=sess)
