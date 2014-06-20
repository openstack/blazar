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

from climate import context
from climate import tests
from climate.utils.openstack import base
from climate.utils.openstack import nova


class TestCNClient(tests.TestCase):
    def setUp(self):
        super(TestCNClient, self).setUp()

        self.nova = nova
        self.context = context
        self.n_client = nova_client
        self.base = base

        self.ctx = self.patch(self.context, 'current')
        self.client = self.patch(self.n_client, 'Client')
        self.patch(self.base, 'url_for').return_value = 'http://fake.com/'

        self.version = '2'
        self.username = 'fake_user'
        self.api_key = self.ctx().auth_token
        self.project_id = self.ctx().project_id
        self.auth_url = 'fake_auth'
        self.mgmt_url = 'fake_mgmt'

    def test_client_from_kwargs(self):
        self.ctx.side_effect = RuntimeError

        kwargs = {'version': self.version,
                  'username': self.username,
                  'api_key': self.api_key,
                  'project_id': self.project_id,
                  'auth_url': self.auth_url,
                  'mgmt_url': self.mgmt_url}

        self.nova.ClimateNovaClient(**kwargs)

        self.client.assert_called_once_with(version=self.version,
                                            username=self.username,
                                            api_key=self.api_key,
                                            project_id=self.project_id,
                                            auth_url=self.auth_url)

    def test_client_from_ctx(self):

        kwargs = {'version': self.version}

        self.nova.ClimateNovaClient(**kwargs)

        self.client.assert_called_once_with(version=self.version,
                                            username=self.ctx().user_name,
                                            api_key=None,
                                            project_id=self.ctx().project_id,
                                            auth_url='http://fake.com/')

    def test_getattr(self):
        # TODO(n.s.): Will be done as soon as pypi package will be updated
        pass
