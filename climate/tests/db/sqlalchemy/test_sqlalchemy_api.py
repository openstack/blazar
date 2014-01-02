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

from climate import context
from climate.db.sqlalchemy import api as db_api
from climate.db.sqlalchemy import models
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


def _get_fake_virt_reservation_values(lease_id=_get_fake_lease_uuid(),
                                      resource_id=None):
    return {'lease_id': lease_id,
            'resource_id': '5678' if not resource_id else resource_id,
            'resource_type': 'virtual:instance'}


def _get_fake_event_values(lease_id=_get_fake_lease_uuid(),
                           event_type='fake_event_type'):
    return {'lease_id': lease_id,
            'event_type': event_type,
            'time': _get_datetime('2030-03-01 00:00')}


def _get_datetime(value='2030-01-01 00:00'):
    return datetime.datetime.strptime(value, '%Y-%m-%d %H:%M')


def _get_fake_virt_lease_values(id=_get_fake_lease_uuid(),
                                name='fake_virt_lease',
                                start_date=_get_datetime('2030-01-01 00:00'),
                                end_date=_get_datetime('2030-01-02 00:00'),
                                resource_id=None):
    return {'id': id,
            'name': name,
            'user_id': 'fake',
            'tenant_id': 'fake',
            'start_date': start_date,
            'end_date': end_date,
            'trust': 'trust',
            'reservations': [_get_fake_virt_reservation_values(
                lease_id=id,
                resource_id=resource_id)],
            'events': []
            }


def _get_fake_phys_lease_values(id=_get_fake_lease_uuid(),
                                name='fake_phys_lease',
                                start_date=_get_datetime('2030-01-01 00:00'),
                                end_date=_get_datetime('2030-01-02 00:00'),
                                resource_id=None):
    return {'id': id,
            'name': name,
            'user_id': 'fake',
            'tenant_id': 'fake',
            'start_date': start_date,
            'end_date': end_date,
            'trust': 'trust',
            'reservations': [_get_fake_phys_reservation_values(
                lease_id=id,
                resource_id=resource_id)],
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
    lease = db_api.lease_create(values)
    for reservation in db_api.reservation_get_all_by_lease_id(lease['id']):
        allocation_values = {
            'id': _get_fake_random_uuid(),
            'compute_host_id': values['reservations'][0]['resource_id'],
            'reservation_id': reservation['id']
        }
        db_api.host_allocation_create(allocation_values)
    return lease


def _get_fake_host_reservation_values(id=_get_fake_random_uuid(),
                                      reservation_id=_get_fake_random_uuid()):
    return {'id': id,
            'reservation_id': reservation_id,
            'resource_properties': "fake",
            'hypervisor_properties': "fake"}


def _get_fake_cpu_info():
    return str({'vendor': 'Intel',
                'model': 'Westmere',
                'arch': 'x86_64',
                'features': ['rdtscp', 'pdpe1gb', 'hypervisor', 'vmx', 'ss',
                         'vme'],
                'topology': {'cores': 1, 'threads': 1, 'sockets': 2}})


def _get_fake_host_values(id=_get_fake_random_uuid(), mem=8192, disk=10):
    return {'id': id,
            'vcpus': 1,
            'cpu_info': _get_fake_cpu_info(),
            'hypervisor_type': 'QEMU',
            'hypervisor_version': 1000,
            'memory_mb': mem,
            'local_gb': disk,
            'status': 'free'
            }


def _get_fake_host_extra_capabilities(id=_get_fake_random_uuid(),
                                      computehost_id=_get_fake_random_uuid()):
    return {'id': id,
            'computehost_id': computehost_id,
            'capability_name': 'vgpu',
            'capability_value': '2'}


class SQLAlchemyDBApiTestCase(tests.DBTestCase):
    """Test case for SQLAlchemy DB API."""

    def setUp(self):
        super(SQLAlchemyDBApiTestCase, self).setUp()

        self.set_context(context.ClimateContext(user_id='fake',
                                                tenant_id='fake'))

    def test_model_query(self):
        db_api.lease_create(_get_fake_virt_lease_values())
        query = db_api.model_query(models.Lease, project_only=None)
        self.assertEqual(1, len(query.all()))
        query = db_api.model_query(models.Lease, project_only=True)
        self.assertEqual(1, len(query.all()))
        self.set_context(context.ClimateContext(user_id='fake',
                                                tenant_id='wrong'))
        query = db_api.model_query(models.Lease, project_only=True)
        self.assertEqual(0, len(query.all()))

    def test_model_query_as_admin(self):
        db_api.lease_create(_get_fake_virt_lease_values())
        self.set_context(context.ClimateContext(user_id='fake',
                                                tenant_id='wrong',
                                                is_admin=True))
        query = db_api.model_query(models.Lease, project_only=True)
        self.assertEqual(1, len(query.all()))

    def test_create_virt_lease(self):
        """Create a virtual lease and verify that all tables have been
        populated.
        """

        result = db_api.lease_create(_get_fake_virt_lease_values())
        self.assertEqual(result['name'],
                         _get_fake_virt_lease_values()['name'])
        self.assertEqual(0, len(db_api.event_get_all()))
        self.assertEqual(1, len(db_api.reservation_get_all()))

    def test_create_phys_lease(self):
        """Create a physical lease and verify that all tables have been
        populated.
        """

        result = db_api.lease_create(_get_fake_phys_lease_values())
        self.assertEqual(result['name'],
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
        self.assertEqual(result['name'],
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
        self.assertEqual(['1', '2'], db_api.lease_list())

    def test_lease_update(self):
        """Update both start_time and name and check lease has been updated."""
        result = _create_physical_lease()
        result = db_api.lease_update(result['id'],
                                     values={'name': 'lease_renamed'})
        self.assertEqual('lease_renamed', result['name'])
        result = db_api.lease_update(
            result['id'],
            values={'start_date': _get_datetime('2014-02-01 00:00')})
        self.assertEqual(_get_datetime('2014-02-01 00:00'),
                         result['start_date'])

    # Reservations

    def test_create_reservation(self):
        """Create a reservation and verify that all tables have been
        populated.
        """

        result = db_api.reservation_create(_get_fake_phys_reservation_values())
        self.assertEqual(result['lease_id'],
                         _get_fake_phys_reservation_values()
                         ['lease_id'])

    def test_reservation_get_all_by_values(self):
        """Create two reservations and verify that we can find reservation per
        resource_id or resource_type.
        """
        db_api.reservation_create(_get_fake_phys_reservation_values())
        db_api.reservation_create(_get_fake_virt_reservation_values())
        self.assertEqual(2, len(db_api.reservation_get_all_by_values()))
        self.assertEqual(1, len(db_api.reservation_get_all_by_values(
            resource_id='5678')))
        self.assertEqual(1, len(db_api.reservation_get_all_by_values(
            resource_type='physical:host')))

    # Host reservations

    def test_create_host_reservation(self):
        """Create a host reservation and verify that all tables
        have been populated.
        """

        result = db_api.host_reservation_create(
            _get_fake_host_reservation_values(id='1'))
        self.assertEqual(result['id'],
                         _get_fake_host_reservation_values(id='1')
                         ['id'])
        # Making sure we still raise a DuplicateDBEntry
        self.assertRaises(RuntimeError, db_api.host_reservation_create,
                          _get_fake_host_reservation_values(id='1'))

    def test_delete_host_reservation(self):
        """Check all deletion cases for host reservation,
        including cascade deletion from reservations table.
        """

        self.assertRaises(RuntimeError,
                          db_api.host_reservation_destroy, 'fake_id')

        result = db_api.host_reservation_create(
            _get_fake_host_reservation_values())
        db_api.host_reservation_destroy(result['id'])
        self.assertIsNone(db_api.host_reservation_get(result['id']))
        reserv = db_api.reservation_create(_get_fake_phys_reservation_values())
        result = db_api.host_reservation_create(
            _get_fake_host_reservation_values(reservation_id=reserv['id']))
        db_api.reservation_destroy(reserv['id'])
        self.assertIsNone(db_api.host_reservation_get(result['id']))

    def test_host_reservation_get_all(self):
        """Check that we return 2 hosts."""

        db_api.host_reservation_create(_get_fake_host_reservation_values(id=1))
        db_api.host_reservation_create(_get_fake_host_reservation_values(id=2))
        hosts_reservations = db_api.host_reservation_get_all()
        self.assertEqual(['1', '2'], [x['id'] for x in hosts_reservations])

    def test_host_reservation_get_by_reservation_id(self):
        """Check that we return 2 hosts."""

        db_api.host_reservation_create(
            _get_fake_host_reservation_values(id=1, reservation_id=1))
        db_api.host_reservation_create(
            _get_fake_host_reservation_values(id=2, reservation_id=2))
        res = db_api.host_reservation_get_by_reservation_id(2)
        self.assertEqual('2', res['id'])

    def test_update_host_reservation(self):
        db_api.host_reservation_create(_get_fake_host_reservation_values(id=1))
        db_api.host_reservation_update(1, {'resource_properties': 'updated'})
        res = db_api.host_reservation_get(1)
        self.assertEqual('updated', res['resource_properties'])

    def test_create_host(self):
        """Create a host and verify that all tables
        have been populated.
        """
        result = db_api.host_create(_get_fake_host_values(id='1'))
        self.assertEqual(result['id'], _get_fake_host_values(id='1')['id'])
        # Making sure we still raise a DuplicateDBEntry
        self.assertRaises(RuntimeError, db_api.host_create,
                          _get_fake_host_values(id='1'))

    def test_search_for_hosts_by_ram(self):
        """Create two hosts and check that we can find a host per its RAM info.
        """
        db_api.host_create(_get_fake_host_values(id=1, mem=2048))
        db_api.host_create(_get_fake_host_values(id=2, mem=4096))
        self.assertEqual(2, len(
            db_api.host_get_all_by_queries(['memory_mb >= 2048'])))
        self.assertEqual(0, len(
            db_api.host_get_all_by_queries(['memory_mb lt 2048'])))

    def test_search_for_hosts_by_cpu_info(self):
        """Create one host and search within cpu_info."""

        db_api.host_create(_get_fake_host_values())
        self.assertEqual(1, len(
            db_api.host_get_all_by_queries(['cpu_info like %Westmere%'])))

    def test_search_for_hosts_by_extra_capability(self):
        """Create one host and test extra capability queries."""
        db_api.host_create(_get_fake_host_values(id=1))
        db_api.host_extra_capability_create(
            _get_fake_host_extra_capabilities(computehost_id=1))
        self.assertEqual(1, len(
            db_api.host_get_all_by_queries(['vgpu == 2'])))
        self.assertEqual(0, len(
            db_api.host_get_all_by_queries(['vgpu != 2'])))
        self.assertEqual(1, len(
            db_api.host_get_all_by_queries(['cpu_info like %Westmere%',
                                            'vgpu == 2'])))
        self.assertEqual(0, len(
            db_api.host_get_all_by_queries(['cpu_info like %wrongcpu%',
                                            'vgpu == 2'])))
        self.assertRaises(RuntimeError,
                          db_api.host_get_all_by_queries, ['apples < 2048'])

    def test_search_for_hosts_by_composed_queries(self):
        """Create one host and test composed queries."""

        db_api.host_create(_get_fake_host_values(mem=8192))
        self.assertEqual(1, len(
            db_api.host_get_all_by_queries(['memory_mb > 2048',
                                            'cpu_info like %Westmere%'])))
        self.assertEqual(0, len(
            db_api.host_get_all_by_queries(['memory_mb < 2048',
                                            'cpu_info like %Westmere%'])))
        self.assertRaises(RuntimeError,
                          db_api.host_get_all_by_queries, ['memory_mb <'])
        self.assertRaises(RuntimeError,
                          db_api.host_get_all_by_queries, ['apples < 2048'])
        self.assertRaises(RuntimeError,
                          db_api.host_get_all_by_queries,
                          ['memory_mb wrongop 2048'])
        self.assertEqual(1, len(
            db_api.host_get_all_by_queries(['memory_mb in 4096,8192'])))
        self.assertEqual(1, len(
            db_api.host_get_all_by_queries(['memory_mb != null'])))

    def test_list_hosts(self):
        db_api.host_create(_get_fake_host_values(id=1))
        db_api.host_create(_get_fake_host_values(id=2))
        self.assertEqual(2, len(db_api.host_list()))

    def test_get_hosts_per_filter(self):
        db_api.host_create(_get_fake_host_values(id=1))
        db_api.host_create(_get_fake_host_values(id=2))
        filters = {'status': 'free'}
        self.assertEqual(2, len(
            db_api.host_get_all_by_filters(filters)))

    def test_update_host(self):
        db_api.host_create(_get_fake_host_values(id=1))
        db_api.host_update(1, {'status': 'updated'})
        self.assertEqual('updated', db_api.host_get(1)['status'])

    def test_delete_host(self):
        db_api.host_create(_get_fake_host_values(id=1))
        db_api.host_destroy(1)
        self.assertEqual(None, db_api.host_get(1))
        self.assertRaises(RuntimeError, db_api.host_destroy, 2)

    def test_create_host_extra_capability(self):
        result = db_api.host_extra_capability_create(
            _get_fake_host_extra_capabilities(id=1))
        self.assertEqual(result['id'], _get_fake_host_values(id='1')['id'])
        # Making sure we still raise a DuplicateDBEntry
        self.assertRaises(RuntimeError, db_api.host_extra_capability_create,
                          _get_fake_host_extra_capabilities(id='1'))

    def test_get_host_extra_capability_per_id(self):
        db_api.host_extra_capability_create(
            _get_fake_host_extra_capabilities(id='1'))
        result = db_api.host_extra_capability_get('1')
        self.assertEqual('1', result['id'])

    def test_host_extra_capability_get_all_per_host(self):
        db_api.host_extra_capability_create(
            _get_fake_host_extra_capabilities(id='1', computehost_id='1'))
        db_api.host_extra_capability_create(
            _get_fake_host_extra_capabilities(id='2', computehost_id='1'))
        res = db_api.host_extra_capability_get_all_per_host('1')
        self.assertEqual(2, len(res))

    def test_update_host_extra_capability(self):
        db_api.host_extra_capability_create(
            _get_fake_host_extra_capabilities(id='1'))
        db_api.host_extra_capability_update('1', {'capability_value': '2'})
        res = db_api.host_extra_capability_get('1')
        self.assertEqual('2', res['capability_value'])

    def test_delete_host_extra_capability(self):
        db_api.host_extra_capability_create(
            _get_fake_host_extra_capabilities(id='1'))
        db_api.host_extra_capability_destroy('1')
        self.assertEqual(None, db_api.host_extra_capability_get('1'))
        self.assertRaises(RuntimeError,
                          db_api.host_extra_capability_destroy, '1')

    def test_host_extra_capability_get_all_per_name(self):
        db_api.host_extra_capability_create(
            _get_fake_host_extra_capabilities(id='1', computehost_id='1'))
        res = db_api.host_extra_capability_get_all_per_name('1', 'vgpu')
        self.assertEqual(1, len(res))
        self.assertEqual([],
                         db_api.host_extra_capability_get_all_per_name('1',
                                                                       'bad'))
