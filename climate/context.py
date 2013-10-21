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

from eventlet import corolocal

from climate.openstack.common import log as logging


LOG = logging.getLogger(__name__)


class Context(object):
    """Context class for the Climate operations."""
    _contexts = {}

    def __init__(self, user_id=None, tenant_id=None, auth_token=None,
                 service_catalog=None, user_name=None, tenant_name=None,
                 roles=None, **kwargs):
        if kwargs:
            LOG.warn('Arguments dropped when creating context: %s', kwargs)

        self.user_id = user_id
        self.user_name = user_name
        self.tenant_id = tenant_id
        self.tenant_name = tenant_name
        self.auth_token = auth_token
        self.service_catalog = service_catalog
        self.roles = roles
        self._db_session = None

    def __enter__(self):
        stack = self._contexts.setdefault(corolocal.get_ident(), [])
        stack.append(self)

    def __exit__(self, exc_type, exc_val, exc_tb):
        stack = self._contexts[corolocal.get_ident()]
        stack.pop()
        if not stack:
            del self._contexts[corolocal.get_ident()]

    @classmethod
    def current(cls):
        try:
            return cls._contexts[corolocal.get_ident()][-1]
        except (KeyError, IndexError):
            raise RuntimeError("Context isn't available here")

    @classmethod
    def clear(cls):
        try:
            del cls._contexts[corolocal.get_ident()]
        except KeyError:
            pass

    def clone(self):
        return Context(self.user_id,
                       self.tenant_id,
                       self.auth_token,
                       self.service_catalog,
                       self.user_name,
                       self.tenant_name,
                       self.roles)

    def to_dict(self):
        return {
            'user_id': self.user_id,
            'user_name': self.user_name,
            'tenant_id': self.tenant_id,
            'tenant_name': self.tenant_name,
            'auth_token': self.auth_token,
            'service_catalog': self.service_catalog,
            'roles': self.roles,
        }
