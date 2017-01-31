# Copyright (c) 2013 Bull.
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

"""Test of Policy Engine For Climate."""

from oslo_config import cfg

from climate import context
from climate import exceptions
from climate import policy
from climate import tests

CONF = cfg.CONF


class ClimatePolicyTestCase(tests.TestCase):

    def setUp(self):
        super(ClimatePolicyTestCase, self).setUp()

        self.context = context.ClimateContext(user_id='fake',
                                              project_id='fake',
                                              roles=['member'])

    def test_standardpolicy(self):
        target_good = {'user_id': self.context.user_id,
                       'project_id': self.context.project_id}
        target_wrong = {'user_id': self.context.user_id,
                        'project_id': 'bad_project'}
        action = "climate:leases"
        self.assertEqual(True, policy.enforce(self.context, action,
                                              target_good))
        self.assertEqual(False, policy.enforce(self.context, action,
                                               target_wrong, False))

    def test_adminpolicy(self):
        target = {'user_id': self.context.user_id,
                  'project_id': self.context.project_id}
        action = "climate:oshosts"
        self.assertRaises(exceptions.PolicyNotAuthorized, policy.enforce,
                          self.context, action, target)

    def test_elevatedpolicy(self):
        target = {'user_id': self.context.user_id,
                  'project_id': self.context.project_id}
        action = "climate:oshosts"
        self.assertRaises(exceptions.PolicyNotAuthorized, policy.enforce,
                          self.context, action, target)
        elevated_context = self.context.elevated()
        self.assertEqual(True,
                         policy.enforce(elevated_context, action, target))

    def test_authorize(self):

        @policy.authorize('leases', ctx=self.context)
        def user_method(self):
            return True

        @policy.authorize('leases', 'get', ctx=self.context)
        def user_method_with_action(self):
            return True

        @policy.authorize('oshosts', ctx=self.context)
        def adminonly_method(self):
            return True

        self.assertEqual(True, user_method(self))
        self.assertEqual(True, user_method_with_action(self))
        try:
            adminonly_method(self)
            self.assertTrue(False)
        except exceptions.PolicyNotAuthorized:
            # We are expecting this exception
            self.assertTrue(True)
