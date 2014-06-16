# Copyright (c) 2014 Red Hat.
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

"""Actions and states for Climate objects."""

import abc

import six

from climate.db import api as db_api
from climate.db import exceptions as db_exc
from climate.manager import exceptions as mgr_exc
from climate.openstack.common import log as logging

LOG = logging.getLogger(__name__)


@six.add_metaclass(abc.ABCMeta)
class ObjectState(object):

    ACTIONS = (CREATE, DELETE, UPDATE
               ) = ('CREATE', 'DELETE', 'UPDATE')

    STATUSES = (IN_PROGRESS, FAILED, COMPLETE
                ) = ('IN_PROGRESS', 'FAILED', 'COMPLETE')

    id = None
    action = None
    status = None
    status_reason = None

    def __init__(self, id, autosave=True,
                 action=None, status=None, status_reason=None):
        self.id = id
        self.autosave = autosave
        if action is not None and status is not None:
            self.update(action, status, status_reason)

    def current(self):
        return {'action': self.action,
                'status': self.status,
                'status_reason': self.status_reason}

    def update(self, action, status, status_reason=None):
        if action not in self.ACTIONS or status not in self.STATUSES:
            raise mgr_exc.InvalidStateUpdate(id=self.id, action=action,
                                             status=status)
        self.action = action
        self.status = status
        self.status_reason = status_reason

        if self.autosave is True:
            self.save()

    @abc.abstractmethod
    def save():
        pass


class LeaseState(ObjectState):

    ACTIONS = (CREATE, DELETE, UPDATE, START, STOP
               ) = ('CREATE', 'DELETE', 'UPDATE', 'START', 'STOP')

    def __init__(self, id, autosave=True,
                 action=None, status=None, status_reason=None):

        if action is None or status is None:
            # NOTE(sbauza): The lease can be not yet in DB, so lease_get can
            #               return None
            lease = db_api.lease_get(id) or {}
            action = lease.get('action', action)
            status = lease.get('status', status)
            status_reason = lease.get('status_reason', status_reason)
        super(LeaseState, self).__init__(id, autosave,
                                         action, status, status_reason)

    def save(self):
        try:
            db_api.lease_update(self.id, self.current())
        except db_exc.ClimateDBException:
            # Lease can be not yet in DB, we must first write it
            raise mgr_exc.InvalidState(id=self.id, state=self.current())
        return self.current()

# NOTE(sbauza): For convenient purpose
lease = LeaseState
