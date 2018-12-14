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

from oslo_utils.fixture import uuidsentinel

from blazar import context
from blazar import tests


class TestBlazarContext(tests.TestCase):

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
            'project_id': 222,
            'project_name': None,
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
            'user_id': 111,
            'user_identity': u'111 222 - - -',
            'user_name': None}
        self.assertEqual(expected, ctx.to_dict())

    def test_elevated_empty(self):
        ctx = context.BlazarContext.elevated()
        self.assertTrue(ctx.is_admin)

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

    def test_blazar_context_elevated(self):
        user_context = context.BlazarContext(
            user_id=uuidsentinel.user_id,
            project_id=uuidsentinel.project_id, is_admin=False)
        self.assertFalse(user_context.is_admin)

        admin_context = user_context.elevated()
        self.assertFalse(user_context.is_admin)
        self.assertTrue(admin_context.is_admin)
        self.assertNotIn('admin', user_context.roles)
        self.assertIn('admin', admin_context.roles)
