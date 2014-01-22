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

from climate import context
from climate import tests


class TestContext(context.BaseContext):
    _elements = set(["first", "second", "third"])


class TestContextCreate(tests.TestCase):

    def test_kwargs(self):
        ctx = TestContext(first=1, second=2)
        self.assertEqual(ctx.to_dict(), {"first": 1, "second": 2})

    def test_dict(self):
        ctx = TestContext({"first": 1, "second": 2})
        self.assertEqual(ctx.to_dict(), {"first": 1, "second": 2})

    def test_mix(self):
        ctx = TestContext({"first": 1}, second=2)
        self.assertEqual(ctx.to_dict(), {"first": 1, "second": 2})

    def test_fail(self):
        self.assertRaises(TypeError, TestContext, forth=4)


class TestBaseContext(tests.TestCase):

    def setUp(self):
        super(TestBaseContext, self).setUp()
        self.context = TestContext(first=1, second=2)

    def test_get_defined(self):
        super(TestBaseContext, self).tearDown()
        self.assertEqual(self.context.first, 1)

    def test_get_default(self):
        self.assertIsNone(self.context.third)

    def test_get_unexpected(self):
        self.assertRaises(AttributeError, getattr, self.context, 'forth')

    def test_current_fails(self):
        self.assertRaises(RuntimeError, TestContext.current)


class TestContextManager(tests.TestCase):

    def setUp(self):
        super(TestContextManager, self).setUp()
        self.context = TestContext(first=1, second=2)
        self.context.__enter__()

    def tearDown(self):
        super(TestContextManager, self).tearDown()
        self.context.__exit__(None, None, None)
        try:
            stack = TestContext._context_stack.stack
        except AttributeError:
            self.fail("Context stack have never been created")
        else:
            del TestContext._context_stack.stack
            self.assertEqual(stack, [],
                             "Context stack is not empty after test.")

    def test_enter(self):
        self.assertEqual(TestContext._context_stack.stack, [self.context])

    def test_double_enter(self):
        with self.context:
            self.assertEqual(TestContext._context_stack.stack,
                             [self.context, self.context])

    def test_current(self):
        self.assertIs(self.context, TestContext.current())


class TestClimateContext(tests.TestCase):

    def test_elevated_empty(self):
        ctx = context.ClimateContext.elevated()
        self.assertEqual(ctx.is_admin, True)

    def test_elevated(self):
        with context.ClimateContext(user_id="user", tenant_id="tenant"):
            ctx = context.ClimateContext.elevated()
            self.assertEqual(ctx.user_id, "user")
            self.assertEqual(ctx.tenant_id, "tenant")
            self.assertEqual(ctx.is_admin, True)

    def test_is_user_context(self):
        ctx = context.ClimateContext(user_id="user", tenant_id="tenant")
        self.assertEqual(True, context.is_user_context(ctx))
        ctx = ctx.elevated()
        self.assertEqual(False, context.is_user_context(ctx))

    def test_is_user_context_with_empty_context(self):
        ctx = context.ClimateContext()
        self.assertEqual(False, context.is_user_context(ctx))
        self.assertEqual(False, context.is_user_context(None))
