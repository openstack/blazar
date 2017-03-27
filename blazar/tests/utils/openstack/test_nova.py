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
from oslo_config import cfg

from blazar import context
from blazar import tests
from blazar.utils.openstack import base
from blazar.utils.openstack import nova

CONF = cfg.CONF


class TestCNClient(tests.TestCase):
    def setUp(self):
        super(TestCNClient, self).setUp()

        self.nova = nova
        self.context = context
        self.n_client = nova_client
        self.base = base

        self.ctx = self.patch(self.context, 'current')
        self.client = self.patch(self.n_client, 'Client')
        self.auth = self.patch(token_endpoint, 'Token')
        self.session = self.patch(session, 'Session')
        self.url = 'http://fake.com/'
        self.patch(self.base, 'url_for').return_value = self.url

        self.version = '2'

    def test_client_from_kwargs(self):
        self.ctx.side_effect = RuntimeError
        endpoint = 'fake_endpoint'
        username = 'blazar_admin'
        password = 'blazar_password'
        user_domain = 'User_Domain'
        project_name = 'admin'
        project_domain = 'Project_Domain'
        auth_url = "%s://%s:%s/v3" % (CONF.os_auth_protocol,
                                      CONF.os_auth_host,
                                      CONF.os_auth_port)

        kwargs = {'version': self.version,
                  'endpoint_override': endpoint,
                  'username': username,
                  'password': password,
                  'user_domain_name': user_domain,
                  'project_name': project_name,
                  'project_domain_name': project_domain}

        self.nova.BlazarNovaClient(**kwargs)

        self.client.assert_called_once_with(version=self.version,
                                            username=username,
                                            password=password,
                                            user_domain_name=user_domain,
                                            project_name=project_name,
                                            project_domain_name=project_domain,
                                            auth_url=auth_url,
                                            endpoint_override=endpoint)

    def test_client_from_ctx(self):
        kwargs = {'version': self.version}

        self.nova.BlazarNovaClient(**kwargs)

        self.auth.assert_called_once_with(self.url,
                                          self.ctx().auth_token)
        self.session.assert_called_once_with(auth=self.auth.return_value)
        self.client.assert_called_once_with(version=self.version,
                                            endpoint_override=self.url,
                                            session=self.session.return_value)

    def test_getattr(self):
        # TODO(n.s.): Will be done as soon as pypi package will be updated
        pass
