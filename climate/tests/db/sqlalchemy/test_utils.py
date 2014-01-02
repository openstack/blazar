# -*- coding: utf-8 -*-
#
# Author: François Rossigneux <francois.rossigneux@inria.fr>
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import datetime

from climate.db.sqlalchemy import api as db_api
from climate.db.sqlalchemy import utils as db_utils
from climate.openstack.common import context
from climate.openstack.common import uuidutils
from climate import tests


def _get_fake_random_uuid():
    return unicode(uuidutils.generate_uuid())


def _get_fake_lease_uuid():
    """Returns a fake uuid."""
    return 'aaaaaaaa-1111-bbbb-2222-cccccccccccc'


def _get_fake_phys_reservation_values(lease_id=_get_fake_lease_uuid(),
                                      resource_id=None):
    return {'lease_id': lease_id,
            'resource_id': '1234' if not resource_id else resource_id,
            'resource_type': 'physical:host'}


def _get_datetime(value='2030-01-01 00:00'):
    return datetime.datetime.strptime(value, '%Y-%m-%d %H:%M')


def _get_fake_phys_lease_values(id=_get_fake_lease_uuid(),
                                name='fake_phys_lease',
                                start_date=_get_datetime('2030-01-01 00:00'),
                                end_date=_get_datetime('2030-01-02 00:00'),
                                resource_id=None):
    return {'id': id,
            'name': name,
            'start_date': start_date,
            'end_date': end_date,
            'trust': 'trust',
            'reservations': [_get_fake_phys_reservation_values(
                lease_id=id,
                resource_id=resource_id)],
            'events': []
            }


def _create_physical_lease(values=_get_fake_phys_lease_values(),
                           random=False):
    """Creating fake lease having a single physical resource."""
    if random is True:
        values = _get_fake_phys_lease_values(id=_get_fake_random_uuid(),
                                             name=_get_fake_random_uuid())
    lease = db_api.lease_create(values)
    for reservation in db_api.reservation_get_all_by_lease_id(lease['id']):
        allocation_values = {
            'id': _get_fake_random_uuid(),
            'compute_host_id': values['reservations'][0]['resource_id'],
            'reservation_id': reservation['id']
        }
        db_api.host_allocation_create(allocation_values)
    return lease


def _get_fake_phys_lease_values(id=_get_fake_lease_uuid(),
                                name='fake_phys_lease',
                                start_date=_get_datetime('2030-01-01 00:00'),
                                end_date=_get_datetime('2030-01-02 00:00'),
                                resource_id=None):
    return {'id': id,
            'name': name,
            'start_date': start_date,
            'end_date': end_date,
            'trust': 'trust',
            'reservations': [_get_fake_phys_reservation_values(
                lease_id=id,
                resource_id=resource_id)],
            'events': []
            }


class SQLAlchemyDBUtilsTestCase(tests.DBTestCase):
    """Test case for SQLAlchemy DB utils."""

    def setUp(self):
        super(SQLAlchemyDBUtilsTestCase, self).setUp()
        self.set_context(context.get_admin_context())

    def _setup_leases(self):
        """Setup some leases."""
        r1 = _get_fake_phys_lease_values(
            id='lease1',
            name='fake_phys_lease_r1',
            start_date=_get_datetime('2030-01-01 09:00'),
            end_date=_get_datetime('2030-01-01 10:30'),
            resource_id='r1')
        r2 = _get_fake_phys_lease_values(
            id='lease2',
            name='fake_phys_lease_r2',
            start_date=_get_datetime('2030-01-01 11:00'),
            end_date=_get_datetime('2030-01-01 12:45'),
            resource_id='r2')
        r3 = _get_fake_phys_lease_values(
            id='lease3',
            name='fake_phys_lease_r3',
            start_date=_get_datetime('2030-01-01 13:00'),
            end_date=_get_datetime('2030-01-01 14:00'),
            resource_id='r1')
        _create_physical_lease(values=r1)
        _create_physical_lease(values=r2)
        _create_physical_lease(values=r3)

    def test_get_free_periods(self):
        """Find the free periods."""
        self._setup_leases()
        start_date = datetime.datetime.strptime('2028-01-01 08:00',
                                                '%Y-%m-%d %H:%M')
        end_date = datetime.datetime.strptime('2099-01-01 00:00',
                                              '%Y-%m-%d %H:%M')
        duration = datetime.timedelta(hours=1)
        free_periods = db_utils.get_free_periods('r1',
                                                 start_date,
                                                 end_date,
                                                 duration)
        self.assertEqual(len(free_periods), 3)
        self.assertEqual(free_periods[0][0].strftime('%Y-%m-%d %H:%M'),
                         '2028-01-01 08:00')
        self.assertEqual(free_periods[0][1].strftime('%Y-%m-%d %H:%M'),
                         '2030-01-01 09:00')
        self.assertEqual(free_periods[1][0].strftime('%Y-%m-%d %H:%M'),
                         '2030-01-01 10:30')
        self.assertEqual(free_periods[1][1].strftime('%Y-%m-%d %H:%M'),
                         '2030-01-01 13:00')
        self.assertEqual(free_periods[2][0].strftime('%Y-%m-%d %H:%M'),
                         '2030-01-01 14:00')
        self.assertEqual(free_periods[2][1].strftime('%Y-%m-%d %H:%M'),
                         '2099-01-01 00:00')
        duration = datetime.timedelta(hours=3)
        free_periods = db_utils.get_free_periods('r1',
                                                 start_date,
                                                 end_date,
                                                 duration)
        self.assertEqual(len(free_periods), 2)
        self.assertEqual(free_periods[0][0].strftime('%Y-%m-%d %H:%M'),
                         '2028-01-01 08:00')
        self.assertEqual(free_periods[0][1].strftime('%Y-%m-%d %H:%M'),
                         '2030-01-01 09:00')
        self.assertEqual(free_periods[1][0].strftime('%Y-%m-%d %H:%M'),
                         '2030-01-01 14:00')
        self.assertEqual(free_periods[1][1].strftime('%Y-%m-%d %H:%M'),
                         '2099-01-01 00:00')

    def test_get_full_periods(self):
        """Find the full periods."""
        self._setup_leases()
        start_date = datetime.datetime.strptime('2028-01-01 08:00',
                                                '%Y-%m-%d %H:%M')
        end_date = datetime.datetime.strptime('2099-01-01 00:00',
                                              '%Y-%m-%d %H:%M')
        duration = datetime.timedelta(hours=1)
        full_periods = db_utils.get_full_periods('r1',
                                                 start_date,
                                                 end_date,
                                                 duration)
        self.assertEqual(len(full_periods), 2)
        self.assertEqual(full_periods[0][0].strftime('%Y-%m-%d %H:%M'),
                         '2030-01-01 09:00')
        self.assertEqual(full_periods[0][1].strftime('%Y-%m-%d %H:%M'),
                         '2030-01-01 10:30')
        self.assertEqual(full_periods[1][0].strftime('%Y-%m-%d %H:%M'),
                         '2030-01-01 13:00')
        self.assertEqual(full_periods[1][1].strftime('%Y-%m-%d %H:%M'),
                         '2030-01-01 14:00')
        duration = datetime.timedelta(hours=3)
        full_periods = db_utils.get_full_periods('r1',
                                                 start_date,
                                                 end_date,
                                                 duration)
        self.assertEqual(len(full_periods), 1)
        self.assertEqual(full_periods[0][0].strftime('%Y-%m-%d %H:%M'),
                         '2030-01-01 09:00')
        self.assertEqual(full_periods[0][1].strftime('%Y-%m-%d %H:%M'),
                         '2030-01-01 14:00')

    def test_availability_time(self):
        """Find the total availability time."""
        self._setup_leases()
        start_date = datetime.datetime.strptime('2030-01-01 09:15',
                                                '%Y-%m-%d %H:%M')
        end_date = datetime.datetime.strptime('2030-01-01 10:15',
                                              '%Y-%m-%d %H:%M')
        availability_time = db_utils.availability_time('r1',
                                                       start_date,
                                                       end_date)
        self.assertEqual(availability_time.seconds, 0 * 60)
        start_date = datetime.datetime.strptime('2030-01-01 09:15',
                                                '%Y-%m-%d %H:%M')
        end_date = datetime.datetime.strptime('2030-01-01 13:45',
                                              '%Y-%m-%d %H:%M')
        availability_time = db_utils.availability_time('r1',
                                                       start_date,
                                                       end_date)
        self.assertEqual(availability_time.seconds, 150 * 60)
        start_date = datetime.datetime.strptime('2030-01-01 08:00',
                                                '%Y-%m-%d %H:%M')
        end_date = datetime.datetime.strptime('2030-01-01 15:00',
                                              '%Y-%m-%d %H:%M')
        availability_time = db_utils.availability_time('r1',
                                                       start_date,
                                                       end_date)
        self.assertEqual(availability_time.seconds, 270 * 60)

    def test_reservation_time(self):
        """Find the total reserved time."""
        self._setup_leases()
        start_date = datetime.datetime.strptime('2030-01-01 09:15',
                                                '%Y-%m-%d %H:%M')
        end_date = datetime.datetime.strptime('2030-01-01 10:15',
                                              '%Y-%m-%d %H:%M')
        reservation_time = db_utils.reservation_time('r1',
                                                     start_date,
                                                     end_date)
        self.assertEqual(reservation_time.seconds, 60 * 60)
        start_date = datetime.datetime.strptime('2030-01-01 09:15',
                                                '%Y-%m-%d %H:%M')
        end_date = datetime.datetime.strptime('2030-01-01 13:45',
                                              '%Y-%m-%d %H:%M')
        reservation_time = db_utils.reservation_time('r1',
                                                     start_date,
                                                     end_date)
        self.assertEqual(reservation_time.seconds, 120 * 60)
        start_date = datetime.datetime.strptime('2030-01-01 08:00',
                                                '%Y-%m-%d %H:%M')
        end_date = datetime.datetime.strptime('2030-01-01 15:00',
                                              '%Y-%m-%d %H:%M')
        reservation_time = db_utils.reservation_time('r1',
                                                     start_date,
                                                     end_date)
        self.assertEqual(reservation_time.seconds, 150 * 60)

    def test_reservation_ratio(self):
        """Find the reservation ratio."""
        self._setup_leases()
        start_date = datetime.datetime.strptime('2030-01-01 09:15',
                                                '%Y-%m-%d %H:%M')
        end_date = datetime.datetime.strptime('2030-01-01 14:30',
                                              '%Y-%m-%d %H:%M')
        reservation_time = db_utils.reservation_time('r1',
                                                     start_date,
                                                     end_date)
        availability_time = db_utils.availability_time('r1',
                                                       start_date,
                                                       end_date)
        reservation_ratio = db_utils.reservation_ratio('r1',
                                                       start_date,
                                                       end_date)
        self.assertEqual(reservation_ratio,
                         float(reservation_time.seconds) /
                         (end_date - start_date).seconds)
        self.assertEqual(
            reservation_ratio,
            float((end_date - start_date - availability_time).seconds) /
            (end_date - start_date).seconds)

    def test_number_of_reservations(self):
        """Find the number of reservations."""
        self._setup_leases()
        start_date = datetime.datetime.strptime('2030-01-01 09:15',
                                                '%Y-%m-%d %H:%M')
        end_date = datetime.datetime.strptime('2030-01-01 14:30',
                                              '%Y-%m-%d %H:%M')
        self.assertEqual(
            db_utils.number_of_reservations('r1', start_date, end_date),
            2)

    def test_longest_lease(self):
        """Find the longest lease."""
        self._setup_leases()
        self.assertEqual(
            db_utils.longest_lease(
                'r1',
                start_date=_get_datetime('2030-01-01 08:00'),
                end_date=_get_datetime('2099-01-01 10:00')),
            'lease1')
        self.assertEqual(
            db_utils.longest_lease(
                'r1',
                start_date=_get_datetime('2030-01-01 10:00'),
                end_date=_get_datetime('2099-01-01 00:00')),
            'lease3')
        self.assertEqual(
            db_utils.longest_lease(
                'r1',
                start_date=_get_datetime('2030-01-01 08:00'),
                end_date=_get_datetime('2030-01-01 11:00')),
            'lease1')
        self.assertIsNone(
            db_utils.longest_lease(
                'r1',
                start_date=_get_datetime('2030-01-01 10:15'),
                end_date=_get_datetime('2030-01-01 13:00')),
            'lease1')

    def test_shortest_lease(self):
        """Find the shortest lease."""
        self._setup_leases()
        self.assertEqual(
            db_utils.shortest_lease(
                'r1',
                start_date=_get_datetime('2030-01-01 08:00'),
                end_date=_get_datetime('2099-01-01 10:00')),
            'lease3')
        self.assertEqual(
            db_utils.shortest_lease(
                'r1',
                start_date=_get_datetime('2030-01-01 10:00'),
                end_date=_get_datetime('2099-01-01 00:00')),
            'lease3')
        self.assertEqual(
            db_utils.shortest_lease(
                'r1',
                start_date=_get_datetime('2030-01-01 08:00'),
                end_date=_get_datetime('2030-01-01 11:00')),
            'lease1')
        self.assertIsNone(
            db_utils.shortest_lease(
                'r1',
                start_date=_get_datetime('2030-01-01 10:15'),
                end_date=_get_datetime('2030-01-01 13:00')),
            'lease1')

# TODO(frossigneux) longest_availability
# TODO(frossigneux) shortest_availability
