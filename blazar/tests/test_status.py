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

from unittest.mock import call

from blazar.db import api as db_api
from blazar import exceptions
from blazar import status
from blazar import tests


class EventStatusTestCase(tests.TestCase):
    def setUp(self):
        super(EventStatusTestCase, self).setUp()

    def test_is_valid_transition_true(self):
        result = status.EventStatus.is_valid_transition(
            status.EventStatus.UNDONE,
            status.EventStatus.IN_PROGRESS)

        self.assertTrue(result)

    def test_is_valid_transition_false(self):
        result = status.EventStatus.is_valid_transition(
            status.EventStatus.IN_PROGRESS,
            status.EventStatus.UNDONE)

        self.assertFalse(result)


class ReservationStatusTestCase(tests.TestCase):
    def setUp(self):
        super(ReservationStatusTestCase, self).setUp()

    def test_is_valid_transition_true(self):
        result = status.ReservationStatus.is_valid_transition(
            status.ReservationStatus.PENDING,
            status.ReservationStatus.ACTIVE)

        self.assertTrue(result)

    def test_is_valid_transition_false(self):
        result = status.ReservationStatus.is_valid_transition(
            status.ReservationStatus.ACTIVE,
            status.ReservationStatus.PENDING)

        self.assertFalse(result)


class LeaseStatusTestCase(tests.TestCase):
    def setUp(self):
        super(LeaseStatusTestCase, self).setUp()
        self.status = status
        self.db_api = db_api
        self.lease_id = 'lease-id'

    def test_is_valid_transition_true(self):
        self.patch(self.status.LeaseStatus, 'is_valid_combination'
                   ).return_value = True
        result = self.status.LeaseStatus.is_valid_transition(
            status.LeaseStatus.STARTING,
            status.LeaseStatus.ACTIVE,
            lease_id=self.lease_id)

        self.assertTrue(result)

    def test_is_valid_transition_false(self):
        self.patch(self.status.LeaseStatus, 'is_valid_combination'
                   ).return_value = True
        result = self.status.lease.is_valid_transition(
            status.LeaseStatus.ACTIVE,
            status.LeaseStatus.STARTING,
            lease_id=self.lease_id)

        self.assertFalse(result)

    def test_is_valid_combination_true(self):
        reservations = [
            {'status': status.ReservationStatus.PENDING}
        ]
        events = [
            {'event_type': 'start_lease',
             'status': status.EventStatus.UNDONE},
            {'event_type': 'end_lease',
             'status': status.EventStatus.UNDONE}
        ]

        def fake_event_get(sort_key, sort_dir, filters):
            if filters == {'lease_id': self.lease_id,
                           'event_type': events[0]['event_type']}:
                return events[0]
            elif filters == {'lease_id': self.lease_id,
                             'event_type': events[1]['event_type']}:
                return events[1]

        self.patch(self.db_api, 'reservation_get_all_by_lease_id'
                   ).return_value = reservations
        self.patch(self.db_api, 'event_get_first_sorted_by_filters'
                   ).side_effect = fake_event_get

        result = self.status.LeaseStatus.is_valid_combination(
            self.lease_id, status.LeaseStatus.PENDING)

        self.assertTrue(result)

    def test_is_valid_combination_invalid_reservation_status(self):
        reservations = [
            {'status': status.ReservationStatus.ACTIVE}
        ]
        self.patch(self.db_api, 'reservation_get_all_by_lease_id'
                   ).return_value = reservations

        result = self.status.LeaseStatus.is_valid_combination(
            self.lease_id, status.LeaseStatus.PENDING)

        self.assertFalse(result)

    def test_is_valid_combination_invalid_event_status(self):
        reservations = [
            {'status': status.ReservationStatus.PENDING}
        ]
        events = [
            {'event_type': 'start_lease',
             'status': status.EventStatus.DONE},
            {'event_type': 'end_lease',
             'status': status.EventStatus.UNDONE}
        ]

        def fake_event_get(sort_key, sort_dir, filters):
            if filters == {'lease_id': self.lease_id,
                           'event_type': events[0]['event_type']}:
                return events[0]
            elif filters == {'lease_id': self.lease_id,
                             'event_type': events[1]['event_type']}:
                return events[1]

        self.patch(self.db_api, 'reservation_get_all_by_lease_id'
                   ).return_value = reservations
        self.patch(self.db_api, 'event_get_first_sorted_by_filters'
                   ).side_effect = fake_event_get

        result = self.status.LeaseStatus.is_valid_combination(
            self.lease_id, status.LeaseStatus.PENDING)

        self.assertFalse(result)

    def test_is_stable(self):
        lease_id = self.lease_id
        lease_pending = {'id': lease_id,
                         'status': status.LeaseStatus.PENDING}
        lease_creating = {'id': lease_id,
                          'status': status.LeaseStatus.CREATING}

        self.patch(self.db_api, 'lease_get').return_value = lease_pending
        result = self.status.LeaseStatus.is_stable(lease_id)
        self.assertTrue(result)

        self.patch(self.db_api, 'lease_get').return_value = lease_creating
        result = self.status.LeaseStatus.is_stable(lease_id)
        self.assertFalse(result)

    def test_lease_status(self):
        lease = {
            'status': status.LeaseStatus.PENDING
        }
        lease_get = self.patch(self.db_api, 'lease_get')
        lease_get.return_value = lease
        lease_update = self.patch(self.db_api, 'lease_update')
        self.patch(self.status.LeaseStatus, 'is_valid_transition'
                   ).return_value = True
        self.patch(self.status.LeaseStatus, 'derive_stable_status'
                   ).return_value = status.LeaseStatus.ACTIVE

        @self.status.LeaseStatus.lease_status(
            transition=status.LeaseStatus.STARTING,
            result_in=(status.LeaseStatus.ACTIVE,))
        def dummy_start_lease(*args, **kwargs):
            pass

        dummy_start_lease(lease_id=self.lease_id)

        lease_get.assert_called_with(self.lease_id)
        lease_update.assert_has_calls(
            [call(self.lease_id, {'status': status.LeaseStatus.STARTING}),
             call(self.lease_id, {'status': status.LeaseStatus.ACTIVE})])

    def test_lease_status_invalid_transition(self):
        lease = {
            'status': status.LeaseStatus.ACTIVE
        }
        lease_get = self.patch(self.db_api, 'lease_get')
        lease_get.return_value = lease
        lease_update = self.patch(self.db_api, 'lease_update')
        self.patch(self.status.LeaseStatus, 'is_valid_transition'
                   ).return_value = False

        @self.status.LeaseStatus.lease_status(
            transition=status.LeaseStatus.STARTING,
            result_in=(status.LeaseStatus.ACTIVE,))
        def dummy_start_lease(*args, **kwargs):
            pass

        self.assertRaises(exceptions.InvalidStatus,
                          dummy_start_lease,
                          lease_id=self.lease_id)

        lease_get.assert_called_once_with(self.lease_id)
        lease_update.assert_not_called()

    def test_lease_status_func_raise_exception(self):
        lease = {
            'status': status.LeaseStatus.PENDING
        }
        lease_get = self.patch(self.db_api, 'lease_get')
        lease_get.return_value = lease
        lease_update = self.patch(self.db_api, 'lease_update')
        self.patch(self.status.LeaseStatus, 'is_valid_transition'
                   ).return_value = True

        @self.status.LeaseStatus.lease_status(
            transition=status.LeaseStatus.STARTING,
            result_in=(status.LeaseStatus.ACTIVE,))
        def dummy_start_lease(*args, **kwargs):
            raise exceptions.BlazarException

        self.assertRaises(exceptions.BlazarException,
                          dummy_start_lease,
                          lease_id=self.lease_id)

        lease_get.assert_called_once_with(self.lease_id)
        lease_update.assert_has_calls(
            [call(self.lease_id, {'status': status.LeaseStatus.STARTING}),
             call(self.lease_id, {'status': status.LeaseStatus.ERROR})])

    def test_lease_status_mismatch_result_in(self):
        lease = {
            'status': status.LeaseStatus.PENDING
        }
        lease_get = self.patch(self.db_api, 'lease_get')
        lease_get.return_value = lease
        lease_update = self.patch(self.db_api, 'lease_update')
        self.patch(self.status.LeaseStatus, 'is_valid_transition'
                   ).return_value = True
        self.patch(self.status.LeaseStatus, 'derive_stable_status'
                   ).return_value = status.LeaseStatus.ACTIVE

        @self.status.LeaseStatus.lease_status(
            transition=status.LeaseStatus.STARTING,
            result_in=(status.LeaseStatus.TERMINATED,))
        def dummy_start_lease(*args, **kwargs):
            pass

        self.assertRaises(exceptions.InvalidStatus,
                          dummy_start_lease,
                          lease_id=self.lease_id)

        lease_get.assert_called_with(self.lease_id)
        lease_update.assert_has_calls(
            [call(self.lease_id, {'status': status.LeaseStatus.STARTING}),
             call(self.lease_id, {'status': status.LeaseStatus.ERROR})])

    def test_lease_status_lease_deleted(self):
        lease = {
            'status': status.LeaseStatus.PENDING
        }
        lease_get = self.patch(self.db_api, 'lease_get')
        lease_get.side_effect = [lease, None]
        lease_update = self.patch(self.db_api, 'lease_update')
        self.patch(self.status.LeaseStatus, 'is_valid_transition'
                   ).return_value = True

        @self.status.LeaseStatus.lease_status(
            transition=status.LeaseStatus.STARTING,
            result_in=(status.LeaseStatus.ACTIVE,))
        def dummy_start_lease(*args, **kwargs):
            pass

        dummy_start_lease(lease_id=self.lease_id)

        lease_get.assert_called_with(self.lease_id)
        lease_update.assert_called_once_with(
            self.lease_id, {'status': status.LeaseStatus.STARTING})

    def test_derive_stable_status_pending(self):
        events = [
            {'event_type': 'start_lease',
             'status': status.EventStatus.UNDONE},
            {'event_type': 'end_lease',
             'status': status.EventStatus.UNDONE}
        ]

        def fake_event_get(sort_key, sort_dir, filters):
            if filters == {'lease_id': self.lease_id,
                           'event_type': events[0]['event_type']}:
                return events[0]
            elif filters == {'lease_id': self.lease_id,
                             'event_type': events[1]['event_type']}:
                return events[1]

        self.patch(self.db_api, 'event_get_first_sorted_by_filters'
                   ).side_effect = fake_event_get
        self.patch(self.status.LeaseStatus, 'is_valid_combination'
                   ).return_value = True

        result = self.status.LeaseStatus.derive_stable_status(self.lease_id)

        self.assertEqual(status.LeaseStatus.PENDING, result)

    def test_derive_stable_status_active(self):
        events = [
            {'event_type': 'start_lease',
             'status': status.EventStatus.DONE},
            {'event_type': 'end_lease',
             'status': status.EventStatus.UNDONE}
        ]

        def fake_event_get(sort_key, sort_dir, filters):
            if filters == {'lease_id': self.lease_id,
                           'event_type': events[0]['event_type']}:
                return events[0]
            elif filters == {'lease_id': self.lease_id,
                             'event_type': events[1]['event_type']}:
                return events[1]

        self.patch(self.db_api, 'event_get_first_sorted_by_filters'
                   ).side_effect = fake_event_get
        self.patch(self.status.LeaseStatus, 'is_valid_combination'
                   ).return_value = True

        result = self.status.LeaseStatus.derive_stable_status(self.lease_id)

        self.assertEqual(status.LeaseStatus.ACTIVE, result)

    def test_derive_stable_status_terminated(self):
        events = [
            {'event_type': 'start_lease',
             'status': status.EventStatus.DONE},
            {'event_type': 'end_lease',
             'status': status.EventStatus.DONE}
        ]

        def fake_event_get(sort_key, sort_dir, filters):
            if filters == {'lease_id': self.lease_id,
                           'event_type': events[0]['event_type']}:
                return events[0]
            elif filters == {'lease_id': self.lease_id,
                             'event_type': events[1]['event_type']}:
                return events[1]

        self.patch(self.db_api, 'event_get_first_sorted_by_filters'
                   ).side_effect = fake_event_get
        self.patch(self.status.LeaseStatus, 'is_valid_combination'
                   ).return_value = True

        result = self.status.LeaseStatus.derive_stable_status(self.lease_id)

        self.assertEqual(status.LeaseStatus.TERMINATED, result)

    def test_derive_stable_status_error(self):
        events = [
            {'event_type': 'start_lease',
             'status': status.EventStatus.DONE},
            {'event_type': 'end_lease',
             'status': status.EventStatus.ERROR}
        ]

        def fake_event_get(sort_key, sort_dir, filters):
            if filters == {'lease_id': self.lease_id,
                           'event_type': events[0]['event_type']}:
                return events[0]
            elif filters == {'lease_id': self.lease_id,
                             'event_type': events[1]['event_type']}:
                return events[1]

        self.patch(self.db_api, 'event_get_first_sorted_by_filters'
                   ).side_effect = fake_event_get
        self.patch(self.status.LeaseStatus, 'is_valid_combination'
                   ).return_value = True

        result = self.status.LeaseStatus.derive_stable_status(self.lease_id)

        self.assertEqual(status.LeaseStatus.ERROR, result)
