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

"""Test of Policy Engine For Blazar."""

from oslo_config import cfg

from blazar import context
from blazar import exceptions
from blazar import policy
from blazar import tests

CONF = cfg.CONF


class BlazarPolicyTestCase(tests.TestCase):

    def setUp(self):
        super(BlazarPolicyTestCase, self).setUp()

        self.context = context.BlazarContext(user_id='fake',
                                             project_id='fake',
                                             roles=['member'])

    def test_standardpolicy(self):
        target_good = {'user_id': self.context.user_id,
                       'project_id': self.context.project_id}
        target_wrong = {'user_id': self.context.user_id,
                        'project_id': 'bad_project'}
        action = "blazar:leases:get"
        self.assertTrue(policy.enforce(self.context, action,
                                       target_good))
        self.assertFalse(policy.enforce(self.context, action,
                                        target_wrong, False))

    def test_adminpolicy(self):
        target = {'user_id': self.context.user_id,
                  'project_id': self.context.project_id}
        action = "blazar:oshosts:get"
        self.assertRaises(exceptions.PolicyNotAuthorized, policy.enforce,
                          self.context, action, target)

    def test_authorize(self):

        @policy.authorize('leases', 'get', ctx=self.context)
        def user_method_with_action(self):
            return True

        @policy.authorize('oshosts', 'get', ctx=self.context)
        def adminonly_method_with_action(self):
            return True

        self.assertTrue(user_method_with_action(self))
        self.assertRaises(exceptions.PolicyNotAuthorized,
                          adminonly_method_with_action, self)
