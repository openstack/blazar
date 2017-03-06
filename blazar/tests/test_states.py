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

"""Test of States."""

from blazar.db import api as db_api
from blazar.db import exceptions as db_exc
from blazar.manager import exceptions as mgr_exc
from blazar import states
from blazar import tests
from blazar.tests import fake_lease


class LeaseStateTestCase(tests.TestCase):

    def setUp(self):
        super(LeaseStateTestCase, self).setUp()

        self.db_api = db_api
        self.lease_update = self.patch(self.db_api, 'lease_update')
        self.lease_update.side_effect = fake_lease.fake_lease_update

        self.lease_get = self.patch(self.db_api, 'lease_get')
        self.lease_get.return_value = fake_lease.fake_lease()

    def test_state_init(self):
        self.leaseState = states.LeaseState(id=1)
        self.lease_get.assert_called_once_with(1)
        expected = {'action': None,
                    'status': None,
                    'status_reason': None}
        self.assertEqual(expected, self.leaseState.current())

    def test_state_init_with_args(self):
        self.leaseState = states.LeaseState(
            id=1,
            action=states.lease.CREATE,
            status=states.lease.IN_PROGRESS)
        self.assertEqual(0, self.lease_get.call_count)
        expected = {'action': 'CREATE',
                    'status': 'IN_PROGRESS',
                    'status_reason': None}
        self.assertEqual(expected, self.leaseState.current())

    def test_state_init_with_no_existing_lease(self):
        self.lease_get.return_value = None
        self.leaseState = states.LeaseState(id=1)
        expected = {'action': None,
                    'status': None,
                    'status_reason': None}
        self.assertEqual(expected, self.leaseState.current())

    def test_state_attributes(self):
        self.leaseState = states.LeaseState(
            id=1,
            action=states.lease.CREATE,
            status=states.lease.IN_PROGRESS)
        self.assertEqual(self.leaseState.action, states.lease.CREATE)
        self.assertEqual(self.leaseState.status, states.lease.IN_PROGRESS)
        self.assertEqual(self.leaseState.status_reason, None)

    def test_update_state_with_autosave(self):
        self.leaseState = states.LeaseState(id=1, autosave=False)
        self.leaseState.autosave = True
        self.leaseState.update(action=states.lease.CREATE,
                               status=states.lease.IN_PROGRESS,
                               status_reason="Creating Lease...")
        expected = {'action': 'CREATE',
                    'status': 'IN_PROGRESS',
                    'status_reason': "Creating Lease..."}
        self.lease_update.assert_called_once_with(1, expected)
        self.assertEqual(expected, self.leaseState.current())

    def test_update_state_with_noautosave(self):
        self.leaseState = states.LeaseState(id=1, autosave=False)
        self.leaseState.update(action=states.lease.CREATE,
                               status=states.lease.IN_PROGRESS,
                               status_reason="Creating Lease...")
        expected = {'action': 'CREATE',
                    'status': 'IN_PROGRESS',
                    'status_reason': "Creating Lease..."}
        self.assertEqual(0, self.lease_update.call_count)
        self.assertEqual(expected, self.leaseState.current())

    def test_update_state_with_incorrect_action_status(self):
        self.leaseState = states.LeaseState(id=1)
        self.assertRaises(mgr_exc.InvalidStateUpdate, self.leaseState.update,
                          action='foo', status=states.lease.IN_PROGRESS)
        self.assertRaises(mgr_exc.InvalidStateUpdate, self.leaseState.update,
                          action=states.lease.CREATE, status='bar')

    def test_save_state(self):
        self.leaseState = states.LeaseState(id=1, autosave=False)
        self.leaseState.update(action=states.lease.CREATE,
                               status=states.lease.IN_PROGRESS,
                               status_reason="Creating Lease...")
        self.assertEqual(0, self.lease_update.call_count)
        self.leaseState.save()
        values = {'action': 'CREATE',
                  'status': 'IN_PROGRESS',
                  'status_reason': "Creating Lease..."}
        self.lease_update.assert_called_once_with(1, values)

    def test_save_state_with_nonexisting_lease(self):
        def fake_lease_update_raise(id, values):
            raise db_exc.BlazarDBException

        self.lease_update.side_effect = fake_lease_update_raise
        self.leaseState = states.LeaseState(id=1, autosave=False)
        self.leaseState.update(action=states.lease.CREATE,
                               status=states.lease.IN_PROGRESS,
                               status_reason="Creating Lease...")
        self.assertRaises(mgr_exc.InvalidState, self.leaseState.save)
