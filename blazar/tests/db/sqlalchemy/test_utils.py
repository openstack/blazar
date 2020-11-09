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

from oslo_context import context
from oslo_utils import uuidutils
import six

from blazar.db.sqlalchemy import api as db_api
from blazar.db.sqlalchemy import utils as db_utils
from blazar.manager import exceptions as mgr_exceptions
from blazar import tests


def _get_fake_random_uuid():
    return six.text_type(uuidutils.generate_uuid())


def _get_fake_lease_uuid():
    """Returns a fake uuid."""
    return 'aaaaaaaa-1111-bbbb-2222-cccccccccccc'


def _get_fake_phys_reservation_values(lease_id=_get_fake_lease_uuid(),
                                      resource_id='1234'):
    return {'lease_id': lease_id,
            'resource_id': resource_id,
            'resource_type': 'physical:host'}


def _get_fake_inst_reservation_values(lease_id=_get_fake_lease_uuid(),
                                      resource_id='5678'):
    return {'lease_id': lease_id,
            'resource_id': resource_id,
            'resource_type': 'virtual:instance'}


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
            'compute_host_id': reservation['resource_id'],
            'reservation_id': reservation['id']
        }
        db_api.host_allocation_create(allocation_values)
    return lease


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

    def check_reservation(self, expect, host_ids, start, end):
        expect.sort(key=lambda x: x['lease_id'])
        if isinstance(host_ids, list):
            ret = db_utils.get_reservations_by_host_ids(host_ids, start, end)
        else:
            ret = db_utils.get_reservations_by_host_id(host_ids, start, end)

        for i, res in enumerate(sorted(ret, key=lambda x: x['lease_id'])):
            self.assertEqual(expect[i]['lease_id'], res['lease_id'])
            self.assertEqual(expect[i]['resource_id'], res['resource_id'])
            self.assertEqual(expect[i]['resource_type'], res['resource_type'])

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
        self.assertEqual(3, len(free_periods))
        self.assertEqual('2028-01-01 08:00',
                         free_periods[0][0].strftime('%Y-%m-%d %H:%M'))
        self.assertEqual('2030-01-01 09:00',
                         free_periods[0][1].strftime('%Y-%m-%d %H:%M'))
        self.assertEqual('2030-01-01 10:30',
                         free_periods[1][0].strftime('%Y-%m-%d %H:%M'))
        self.assertEqual('2030-01-01 13:00',
                         free_periods[1][1].strftime('%Y-%m-%d %H:%M'))
        self.assertEqual('2030-01-01 14:00',
                         free_periods[2][0].strftime('%Y-%m-%d %H:%M'))
        self.assertEqual('2099-01-01 00:00',
                         free_periods[2][1].strftime('%Y-%m-%d %H:%M'))
        duration = datetime.timedelta(hours=3)
        free_periods = db_utils.get_free_periods('r1',
                                                 start_date,
                                                 end_date,
                                                 duration)
        self.assertEqual(2, len(free_periods))
        self.assertEqual('2028-01-01 08:00',
                         free_periods[0][0].strftime('%Y-%m-%d %H:%M'))
        self.assertEqual('2030-01-01 09:00',
                         free_periods[0][1].strftime('%Y-%m-%d %H:%M'))
        self.assertEqual('2030-01-01 14:00',
                         free_periods[1][0].strftime('%Y-%m-%d %H:%M'))
        self.assertEqual('2099-01-01 00:00',
                         free_periods[1][1].strftime('%Y-%m-%d %H:%M'))

    def test_get_reserved_periods(self):
        """Find the reserved periods."""
        self._setup_leases()
        start_date = datetime.datetime.strptime('2028-01-01 08:00',
                                                '%Y-%m-%d %H:%M')
        end_date = datetime.datetime.strptime('2099-01-01 00:00',
                                              '%Y-%m-%d %H:%M')
        duration = datetime.timedelta(hours=1)
        reserved_periods = db_utils.get_reserved_periods('r1',
                                                         start_date,
                                                         end_date,
                                                         duration)
        self.assertEqual(2, len(reserved_periods))
        self.assertEqual('2030-01-01 09:00',
                         reserved_periods[0][0].strftime('%Y-%m-%d %H:%M'))
        self.assertEqual('2030-01-01 10:30',
                         reserved_periods[0][1].strftime('%Y-%m-%d %H:%M'))
        self.assertEqual('2030-01-01 13:00',
                         reserved_periods[1][0].strftime('%Y-%m-%d %H:%M'))
        self.assertEqual('2030-01-01 14:00',
                         reserved_periods[1][1].strftime('%Y-%m-%d %H:%M'))
        duration = datetime.timedelta(hours=3)
        reserved_periods = db_utils.get_reserved_periods('r1',
                                                         start_date,
                                                         end_date,
                                                         duration)
        self.assertEqual(1, len(reserved_periods))
        self.assertEqual('2030-01-01 09:00',
                         reserved_periods[0][0].strftime('%Y-%m-%d %H:%M'))
        self.assertEqual('2030-01-01 14:00',
                         reserved_periods[0][1].strftime('%Y-%m-%d %H:%M'))

    def test_get_reservations_by_host_id(self):
        self._setup_leases()

        self.check_reservation([], 'r1',
                               '2030-01-01 07:00', '2030-01-01 08:59')

        ret = db_api.reservation_get_all_by_lease_id('lease1')
        self.check_reservation(ret, 'r1',
                               '2030-01-01 08:00', '2030-01-01 10:00')

        ret = db_api.reservation_get_all_by_lease_id('lease1')
        ret.extend(db_api.reservation_get_all_by_lease_id('lease3'))
        self.check_reservation(ret, 'r1',
                               '2030-01-01 08:00', '2030-01-01 15:30')

        self.check_reservation([], 'r4',
                               '2030-01-01 07:00', '2030-01-01 15:00')

    def test_get_reservations_by_host_id_with_multi_reservation(self):
        self._setup_leases()

        fake_lease = _get_fake_phys_lease_values(
            id='lease-4',
            name='fake_phys_lease_r4',
            start_date=_get_datetime('2030-01-01 15:00'),
            end_date=_get_datetime('2030-01-01 16:00'),
            resource_id='r4-1')

        fake_lease['reservations'].append(
            _get_fake_phys_reservation_values(lease_id='lease-4',
                                              resource_id='r1'))
        _create_physical_lease(values=fake_lease)

        expected = db_api.reservation_get_all_by_values(
            **{'resource_id': 'r1'})
        self.assertEqual(3, len(expected))
        self.check_reservation(expected, 'r1',
                               '2030-01-01 08:00', '2030-01-01 17:00')

    def test_get_reservations_by_host_ids(self):
        self._setup_leases()

        self.check_reservation([], ['r1', 'r2'],
                               '2030-01-01 07:00', '2030-01-01 08:59')

        ret = db_api.reservation_get_all_by_lease_id('lease1')
        self.check_reservation(ret, ['r1', 'r2'],
                               '2030-01-01 08:00', '2030-01-01 10:00')

        ret = db_api.reservation_get_all_by_lease_id('lease1')
        ret.extend(db_api.reservation_get_all_by_lease_id('lease2'))
        ret.extend(db_api.reservation_get_all_by_lease_id('lease3'))
        self.check_reservation(ret, ['r1', 'r2'],
                               '2030-01-01 08:00', '2030-01-01 15:30')

        self.check_reservation([], ['r4'],
                               '2030-01-01 07:00', '2030-01-01 15:00')

    def _create_allocation_tuple(self, lease_id):
        reservation = db_api.reservation_get_all_by_lease_id(lease_id)[0]
        allocation = db_api.host_allocation_get_all_by_values(
            reservation_id=reservation['id'])[0]
        return (reservation['id'],
                reservation['lease_id'],
                allocation['compute_host_id'])

    def test_get_reservation_allocations_by_host_ids(self):
        self._setup_leases()

        # query all allocations of lease1, lease2 and lease3
        expected = [
            self._create_allocation_tuple('lease1'),
            self._create_allocation_tuple('lease2'),
            self._create_allocation_tuple('lease3'),
        ]
        ret = db_utils.get_reservation_allocations_by_host_ids(
            ['r1', 'r2'], '2030-01-01 08:00', '2030-01-01 15:00')

        self.assertListEqual(expected, ret)

        # query allocations of lease2 and lease3
        expected = [
            self._create_allocation_tuple('lease2'),
            self._create_allocation_tuple('lease3'),
        ]
        ret = db_utils.get_reservation_allocations_by_host_ids(
            ['r1', 'r2'], '2030-01-01 11:30', '2030-01-01 15:00')

        self.assertListEqual(expected, ret)

    def test_get_reservation_allocations_by_host_ids_with_lease_id(self):
        self._setup_leases()

        # query all allocations of lease1, lease2 and lease3
        expected = [
            self._create_allocation_tuple('lease1'),
        ]
        ret = db_utils.get_reservation_allocations_by_host_ids(
            ['r1', 'r2'], '2030-01-01 08:00', '2030-01-01 15:00', 'lease1')

        self.assertListEqual(expected, ret)

    def test_get_reservation_allocations_by_host_ids_with_reservation_id(self):
        self._setup_leases()
        reservation1 = db_api.reservation_get_all_by_lease_id('lease1')[0]

        # query allocations of lease1
        expected = [
            self._create_allocation_tuple('lease1'),
        ]
        ret = db_utils.get_reservation_allocations_by_host_ids(
            ['r1', 'r2'], '2030-01-01 08:00', '2030-01-01 15:00',
            reservation_id=reservation1['id'])

        self.assertListEqual(expected, ret)

    def test_get_plugin_reservation_with_host(self):
        patch_host_reservation_get = self.patch(db_api, 'host_reservation_get')
        patch_host_reservation_get.return_value = {
            'id': 'id',
            'reservation_id': 'reservation-id',
        }
        db_utils.get_plugin_reservation('physical:host', 'id-1')
        patch_host_reservation_get.assert_called_once_with('id-1')

    def test_get_plugin_reservation_with_instance(self):
        patch_inst_reservation_get = self.patch(db_api,
                                                'instance_reservation_get')
        patch_inst_reservation_get.return_value = {
            'id': 'id',
            'reservation_id': 'reservation-id',
        }
        db_utils.get_plugin_reservation('virtual:instance', 'id-1')
        patch_inst_reservation_get.assert_called_once_with('id-1')

    def test_get_plugin_reservation_with_invalid(self):
        self.assertRaises(mgr_exceptions.UnsupportedResourceType,
                          db_utils.get_plugin_reservation, 'invalid', 'id1')
