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

from oslo_config import cfg
from oslo_config import fixture as conf_fixture
from oslo_utils.fixture import uuidsentinel

from blazar import context
from blazar import tests

CONF = cfg.CONF


class TestBlazarContext(tests.TestCase):

    def setUp(self):
        super(TestBlazarContext, self).setUp()

        self.cfg = self.useFixture(conf_fixture.Config(CONF))
        self.cfg.config(os_admin_username='fake-admin')
        self.cfg.config(os_admin_user_domain_name='fake-admin-domain')
        self.cfg.config(os_admin_project_name='fake-admin-project')
        self.cfg.config(os_admin_project_domain_name='fake-admin-domain')

    def test_to_dict(self):
        ctx = context.BlazarContext(
            user_id=111, project_id=222,
            request_id='req-679033b7-1755-4929-bf85-eb3bfaef7e0b')
        expected = {
            'auth_token': None,
            'domain': None,
            'global_request_id': None,
            'is_admin': False,
            'is_admin_project': True,
            'project': 222,
            'project_domain': None,
            'read_only': False,
            'request_id': 'req-679033b7-1755-4929-bf85-eb3bfaef7e0b',
            'resource_uuid': None,
            'roles': [],
            'service_catalog': [],
            'show_deleted': False,
            'system_scope': None,
            'tenant': 222,
            'user': 111,
            'user_domain': None,
            'user_identity': '111 222 - - -'}
        self.assertEqual(expected, ctx.to_dict())

    def test_service_catalog_default(self):
        ctxt = context.BlazarContext(user_id=uuidsentinel.user_id,
                                     project_id=uuidsentinel.project_id)
        self.assertEqual([], ctxt.service_catalog)

        ctxt = context.BlazarContext(user_id=uuidsentinel.user_id,
                                     project_id=uuidsentinel.project_id,
                                     service_catalog=[])
        self.assertEqual([], ctxt.service_catalog)

        ctxt = context.BlazarContext(user_id=uuidsentinel.user_id,
                                     project_id=uuidsentinel.project_id,
                                     service_catalog=None)
        self.assertEqual([], ctxt.service_catalog)

    def test_admin(self):
        ctx = context.admin()
        self.assertEqual(ctx.user_name, 'fake-admin')
        self.assertEqual(ctx.user_domain_name, 'fake-admin-domain')
        self.assertEqual(ctx.project_name, 'fake-admin-project')
        self.assertEqual(ctx.project_domain_name, 'fake-admin-domain')
        self.assertEqual(ctx.is_admin, True)

    def test_admin_nested(self):
        """Test that admin properties take priority over current context."""
        request_id = 'req-679033b7-1755-4929-bf85-eb3bfaef7e0b'
        service_catalog = ['foo']
        ctx = context.BlazarContext(
            user_name='fake-user', user_domain_name='fake-user-domain',
            project_name='fake-project',
            project_domain_name='fake-user-domain',
            service_catalog=service_catalog, request_id=request_id)
        with ctx:
            admin_ctx = context.admin()
            self.assertEqual(admin_ctx.user_name, 'fake-admin')
            self.assertEqual(admin_ctx.user_domain_name, 'fake-admin-domain')
            self.assertEqual(admin_ctx.project_name, 'fake-admin-project')
            self.assertEqual(admin_ctx.project_domain_name,
                             'fake-admin-domain')
            self.assertEqual(admin_ctx.is_admin, True)
            self.assertEqual(admin_ctx.request_id, request_id)
            self.assertEqual(admin_ctx.service_catalog, service_catalog)
