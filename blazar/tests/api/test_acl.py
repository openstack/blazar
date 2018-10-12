# -*- encoding: utf-8 -*-
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
"""
Tests for ACL. Checks whether certain kinds of requests
are blocked or allowed to be processed.
"""
from blazar import policy
from blazar.tests import api


class TestACL(api.APITest):

    def setUp(self):
        super(TestACL, self).setUp()

        self.policy = policy
        self.path = '/os-hosts'
        self.patch(
            self.hosts_rpcapi, 'list_computehosts').return_value = []

    def _make_app(self):
        return super(TestACL, self)._make_app(enable_acl=True)

    def test_non_authenticated(self):
        response = self.get_json(self.path, expect_errors=True)
        self.assertEqual(401, response.status_int)

    def test_authenticated(self):
        response = self.get_json(self.path,
                                 headers={'X-Auth-Token': self.ADMIN_TOKEN})

        self.assertEqual([], response)

    def test_non_admin(self):
        response = self.get_json(self.path,
                                 headers={'X-Auth-Token': self.MEMBER_TOKEN},
                                 expect_errors=True)

        self.assertEqual(403, response.status_int)

    def test_non_admin_with_admin_header(self):
        response = self.get_json(self.path,
                                 headers={'X-Auth-Token': self.MEMBER_TOKEN,
                                          'X-Roles': 'admin'},
                                 expect_errors=True)

        self.assertEqual(403, response.status_int)
