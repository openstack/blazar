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

import threading


class BaseContext(object):

    _elements = set()
    _context_stack = threading.local()

    def __init__(self, __mapping=None, **kwargs):
        if __mapping is None:
            self.__values = dict(**kwargs)
        else:
            if isinstance(__mapping, BaseContext):
                __mapping = __mapping.__values
            self.__values = dict(__mapping)
            self.__values.update(**kwargs)
        not_supported_keys = set(self.__values) - self._elements
        for k in not_supported_keys:
            del self.__values[k]

    def __getattr__(self, name):
        try:
            return self.__values[name]
        except KeyError:
            if name in self._elements:
                return None
            else:
                raise AttributeError(name)

    def __setattr__(self, name, value):
        # NOTE(yorik-sar): only the very first assignment for __values is
        # allowed. All context arguments should be set at the time the context
        # object is being created.
        if not self.__dict__:
            super(BaseContext, self).__setattr__(name, value)
        else:
            raise Exception(self.__dict__, name, value)

    def __enter__(self):
        try:
            stack = self._context_stack.stack
        except AttributeError:
            stack = []
            self._context_stack.stack = stack
        stack.append(self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        res = self._context_stack.stack.pop()
        assert res is self, "self should be the top element of the stack"

    @classmethod
    def current(cls):
        try:
            return cls._context_stack.stack[-1]
        except (AttributeError, IndexError):
            raise RuntimeError("Context isn't available here")

    # NOTE(yorik-sar): as long as oslo.rpc requires this
    def to_dict(self):
        return self.__values


class BlazarContext(BaseContext):

    _elements = set([
        "user_id",
        "project_id",
        "auth_token",
        "service_catalog",
        "user_name",
        "project_name",
        "roles",
        "is_admin",
    ])

    @classmethod
    def elevated(cls):
        try:
            ctx = cls.current()
        except RuntimeError:
            ctx = None
        return cls(ctx, is_admin=True)


def current():
    return BlazarContext.current()


def elevated():
    return BlazarContext.elevated()
