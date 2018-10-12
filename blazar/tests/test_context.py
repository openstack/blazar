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

from blazar import context
from blazar import tests


class TestContext(context.BaseContext):
    _elements = set(["first", "second", "third"])


class TestContextCreate(tests.TestCase):

    def test_kwargs(self):
        ctx = TestContext(first=1, second=2)
        self.assertEqual({"first": 1, "second": 2}, ctx.to_dict())

    def test_dict(self):
        ctx = TestContext({"first": 1, "second": 2})
        self.assertEqual({"first": 1, "second": 2}, ctx.to_dict())

    def test_mix(self):
        ctx = TestContext({"first": 1}, second=2)
        self.assertEqual({"first": 1, "second": 2}, ctx.to_dict())

    def test_fail(self):
        ctx = TestContext({'first': 1, "forth": 4}, fifth=5)
        self.assertEqual(ctx.to_dict(), {"first": 1})


class TestBaseContext(tests.TestCase):

    def setUp(self):
        super(TestBaseContext, self).setUp()
        self.context = TestContext(first=1, second=2)

    def tearDown(self):
        super(TestBaseContext, self).tearDown()
        self.assertEqual(1, self.context.first)

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


class TestBlazarContext(tests.TestCase):

    def test_elevated_empty(self):
        ctx = context.BlazarContext.elevated()
        self.assertTrue(ctx.is_admin)

    def test_elevated(self):
        with context.BlazarContext(user_id="user", project_id="project"):
            ctx = context.BlazarContext.elevated()
            self.assertEqual(ctx.user_id, "user")
            self.assertEqual(ctx.project_id, "project")
            self.assertTrue(ctx.is_admin)
