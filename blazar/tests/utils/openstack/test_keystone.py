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

from blazar import context
from blazar import exceptions
from blazar import tests
from blazar.utils.openstack import base
from blazar.utils.openstack import keystone


class TestCKClient(tests.TestCase):

    def setUp(self):
        super(TestCKClient, self).setUp()

        self.keystone = keystone
        self.context = context
        self.k_client = keystone_client
        self.base = base

        self.ctx = self.patch(self.context, 'current')
        self.client = self.patch(self.k_client, 'Client')
        self.patch(self.base, 'url_for').return_value = 'http://fake.com/'

        self.version = '3'
        self.username = 'fake_user'
        self.user_domain_name = 'fake_user_domain'
        self.token = 'fake_token'
        self.password = 'fake_pass'
        self.project_name = 'fake_project'
        self.project_domain_name = 'fake_project_domain'
        self.auth_url = 'fake_url'
        self.trust_id = 'fake_trust'

    def test_client_from_kwargs(self):
        self.ctx.side_effect = RuntimeError
        self.keystone.BlazarKeystoneClient(
            version=self.version,
            username=self.username,
            password=self.password,
            project_name=self.project_name,
            trust_id=self.trust_id,
            auth_url=self.auth_url)
        self.client.assert_called_once_with(
            version=self.version,
            trust_id=self.trust_id,
            username=self.username,
            password=self.password,
            auth_url=self.auth_url)

    def test_client_from_kwargs_and_ctx(self):
        self.keystone.BlazarKeystoneClient(
            version=self.version,
            username=self.username,
            user_domain_name=self.user_domain_name,
            password=self.password,
            project_name=self.project_name,
            project_domain_name=self.project_domain_name,
            auth_url=self.auth_url)
        self.client.assert_called_once_with(
            version=self.version,
            username=self.username,
            user_domain_name=self.user_domain_name,
            project_name=self.project_name,
            project_domain_name=self.project_domain_name,
            endpoint='http://fake.com/',
            password=self.password,
            auth_url=self.auth_url,
            global_request_id=self.context.current().global_request_id)

    def test_client_from_ctx(self):
        self.keystone.BlazarKeystoneClient()
        self.client.assert_called_once_with(
            version='3',
            username=self.ctx().user_name,
            user_domain_name=self.ctx().user_domain_name,
            token=self.ctx().auth_token,
            project_name=self.ctx().project_name,
            project_domain_name=self.ctx().project_domain_name,
            auth_url='http://fake.com/',
            endpoint='http://fake.com/',
            global_request_id=self.context.current().global_request_id)

    def test_complement_auth_url_supported_api_version(self):
        bkc = self.keystone.BlazarKeystoneClient()
        expected_url = self.auth_url + '/v3'
        returned_url = bkc.complement_auth_url(auth_url=self.auth_url,
                                               version='v3')
        self.assertEqual(expected_url, returned_url)

    def test_complement_auth_url_unsupported_api_version(self):
        bkc = self.keystone.BlazarKeystoneClient()
        kwargs = {'auth_url': self.auth_url,
                  'version': 2.0}
        self.assertRaises(exceptions.UnsupportedAPIVersion,
                          bkc.complement_auth_url,
                          **kwargs)

    def test_complement_auth_url_valid_url(self):
        bkc = self.keystone.BlazarKeystoneClient()
        auth_url = self.auth_url + '/v3'
        returned_url = bkc.complement_auth_url(auth_url=auth_url,
                                               version='v3')
        self.assertEqual(auth_url, returned_url)

    def test_complement_auth_url_invalid_url(self):
        bkc = self.keystone.BlazarKeystoneClient()
        auth_url = self.auth_url + '/v2.0'
        kwargs = {'auth_url': auth_url,
                  'version': 'v3'}
        self.assertRaises(exceptions.UnsupportedAPIVersion,
                          bkc.complement_auth_url,
                          **kwargs)

    def test_getattr(self):
        # TODO(n.s.): Will be done as soon as pypi package will be updated
        pass
