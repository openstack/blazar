# vim: tabstop=4 shiftwidth=4 softtabstop=4
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
from oslo.config import cfg

from climate.api.v2 import app
from climate import policy
from climate.tests import api
from climate.tests.api import utils


class TestACL(api.APITest):

    def setUp(self):
        super(TestACL, self).setUp()

        self.environ = {'fake.cache': utils.FakeMemcache()}
        self.policy = policy
        self.path = '/v2/os-hosts'
        self.patch(
            self.hosts_rpcapi, 'list_computehosts').return_value = []

    def get_json(self, path, expect_errors=False, headers=None, q=[], **param):
        return super(TestACL, self).get_json(path,
                                             expect_errors=expect_errors,
                                             headers=headers,
                                             q=q,
                                             extra_environ=self.environ,
                                             path_prefix='',
                                             **param)

    def _make_app(self):
        cfg.CONF.set_override('cache', 'fake.cache', group=app.OPT_GROUP_NAME)
        return super(TestACL, self)._make_app(enable_acl=True)

    def test_non_authenticated(self):
        response = self.get_json(self.path, expect_errors=True)
        self.assertEqual(response.status_int, 401)

    def test_authenticated(self):
        response = self.get_json(self.path,
                                 headers={'X-Auth-Token': utils.ADMIN_TOKEN})

        self.assertEqual(response, [])

    def test_non_admin(self):
        response = self.get_json(self.path,
                                 headers={'X-Auth-Token': utils.MEMBER_TOKEN},
                                 expect_errors=True)

        self.assertEqual(response.status_int, 403)

    def test_non_admin_with_admin_header(self):
        response = self.get_json(self.path,
                                 headers={'X-Auth-Token': utils.MEMBER_TOKEN,
                                          'X-Roles': 'admin'},
                                 expect_errors=True)

        self.assertEqual(response.status_int, 403)
