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

import datetime

from climate.db.sqlalchemy import api as db_api
from climate.openstack.common import context
from climate.openstack.common import uuidutils
from climate import test


def _get_fake_random_uuid():
    return unicode(uuidutils.generate_uuid())


def _get_fake_lease_uuid():
    """Returns a fake uuid."""
    return 'aaaaaaaa-1111-bbbb-2222-cccccccccccc'


def _get_fake_phys_reservation_values(lease_id=_get_fake_lease_uuid()):
    return {'lease_id': lease_id,
            'resource_id': '1234',
            'resource_type': 'physical:host'}


def _get_fake_virt_reservation_values(lease_id=_get_fake_lease_uuid()):
    return {'lease_id': lease_id,
            'resource_id': '5678',
            'resource_type': 'virtual:instance'}


def _get_fake_event_values(lease_id=_get_fake_lease_uuid(),
                           event_type='fake_event_type'):
    return {'lease_id': lease_id,
            'event_type': event_type,
            'time': _get_datetime('2030-03-01 00:00')}


def _get_datetime(value):
    return datetime.datetime.strptime(value, "%Y-%m-%d %H:%M")


def _get_fake_virt_lease_values(id=_get_fake_lease_uuid(),
                                name='fake_virt_lease'):
    return {'id': id,
            'name': name,
            'start_date': _get_datetime('2030-01-01 00:00'),
            'end_date': _get_datetime('2030-01-02 00:00'),
            'trust': 'trust',
            'reservations': [_get_fake_virt_reservation_values(lease_id=id)],
            'events': []
            }


def _get_fake_phys_lease_values(id=_get_fake_lease_uuid(),
                                name='fake_phys_lease'):
    return {'id': id,
            'name': name,
            'start_date': _get_datetime('2030-01-01 00:00'),
            'end_date': _get_datetime('2030-01-02 00:00'),
            'trust': 'trust',
            'reservations': [_get_fake_phys_reservation_values(lease_id=id)],
            'events': []
            }


def _create_virtual_lease(values=_get_fake_virt_lease_values(),
                          random=False):
    """Creating fake lease having a single virtual resource."""
    return db_api.lease_create(values)


def _create_physical_lease(values=_get_fake_phys_lease_values(),
                           random=False):
    """Creating fake lease having a single physical resource."""
    if random is True:
        values = _get_fake_phys_lease_values(id=_get_fake_random_uuid(),
                                             name=_get_fake_random_uuid())
    return db_api.lease_create(values)


class SQLAlchemyDBApiTestCase(test.DBTestCase):
    """Test case for SQLAlchemy DB API."""

    def setUp(self):
        super(SQLAlchemyDBApiTestCase, self).setUp()
        self.set_context(context.get_admin_context())

    def test_create_virt_lease(self):
        """Create a virtual lease and verify that all tables have been
        populated.
        """

        result = db_api.lease_create(_get_fake_virt_lease_values())
        self.assertEquals(result['name'],
                          _get_fake_virt_lease_values()['name'])
        self.assertEqual(0, len(db_api.event_get_all()))
        self.assertEqual(1, len(db_api.reservation_get_all()))

    def test_create_phys_lease(self):
        """Create a physical lease and verify that all tables have been
        populated.
        """

        result = db_api.lease_create(_get_fake_phys_lease_values())
        self.assertEquals(result['name'],
                          _get_fake_phys_lease_values()['name'])
        self.assertEqual(0, len(db_api.event_get_all()))
        self.assertEqual(1, len(db_api.reservation_get_all()))

    def test_create_duplicate_leases(self):
        """Create two leases with same names, and checks it raises an error.
        """

        db_api.lease_create(_get_fake_phys_lease_values())
        self.assertRaises(RuntimeError, db_api.lease_create,
                          _get_fake_phys_lease_values())

    def test_create_lease_with_event(self):
        """Create a lease including a fake event and check all tables."""

        lease = _get_fake_phys_lease_values()
        lease['events'].append(_get_fake_event_values(lease_id=lease['id']))
        result = db_api.lease_create(lease)
        self.assertEquals(result['name'],
                          _get_fake_phys_lease_values()['name'])
        self.assertEqual(1, len(db_api.event_get_all()))

    def test_delete_wrong_lease(self):
        """Delete a lease that doesn't exist and check that raises an error."""
        self.assertRaises(RuntimeError, db_api.lease_destroy, 'fake_id')

    def test_delete_correct_lease(self):
        """Delete a lease and check that deletion has been cascaded to FKs."""
        lease = _get_fake_phys_lease_values()
        lease['events'].append(_get_fake_event_values(lease_id=lease['id']))
        result = _create_physical_lease(values=lease)
        db_api.lease_destroy(result['id'])
        self.assertIsNone(db_api.lease_get(result['id']))
        self.assertEqual(0, len(db_api.reservation_get_all()))
        self.assertEqual(0, len(db_api.event_get_all()))

    def test_lease_get_all(self):
        """Check the number of leases we get."""
        _create_physical_lease(random=True)
        self.assertEqual(1, len(db_api.lease_get_all()))
        _create_physical_lease(random=True)
        self.assertEqual(2, len(db_api.lease_get_all()))

    def test_lease_list(self):
        """Not implemented yet until lease_list returns list of IDs."""
        # TODO(sbauza): Enable this test when lease_list will return only IDs
        self.assertTrue(True)
        return
        _create_physical_lease(
            values=_get_fake_phys_lease_values(id='1', name='fake1'))
        _create_physical_lease(
            values=_get_fake_phys_lease_values(id='2', name='fake2'))
        self.assertEquals(['1', '2'], db_api.lease_list())

    def test_lease_update(self):
        """Update both start_time and name and check lease has been updated."""
        result = _create_physical_lease()
        result = db_api.lease_update(result['id'],
                                     values={'name': 'lease_renamed'})
        self.assertEquals('lease_renamed', result['name'])
        result = db_api.lease_update(
            result['id'],
            values={'start_date': _get_datetime('2014-02-01 00:00')})
        self.assertEquals(_get_datetime('2014-02-01 00:00'),
                          result['start_date'])
