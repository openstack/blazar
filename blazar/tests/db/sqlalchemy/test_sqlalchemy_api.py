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
import operator

from oslo_utils import uuidutils

from blazar.db import exceptions as db_exceptions
from blazar.db.sqlalchemy import api as db_api
from blazar.plugins import oshosts as host_plugin
from blazar import tests


def _get_fake_random_uuid():
    return uuidutils.generate_uuid()


def _get_fake_lease_uuid():
    """Returns a fake uuid."""
    return 'aaaaaaaa-1111-bbbb-2222-cccccccccccc'


def _get_fake_phys_reservation_values(id=None,
                                      lease_id=_get_fake_lease_uuid(),
                                      resource_id=None):
    if id is None:
        id = _get_fake_random_uuid()
    return {'id': id,
            'lease_id': lease_id,
            'resource_id': '1234' if not resource_id else resource_id,
            'resource_type': host_plugin.RESOURCE_TYPE,
            'hypervisor_properties': '[\"=\", \"$hypervisor_type\", \"QEMU\"]',
            'resource_properties': '',
            'min': 1, 'max': 1,
            'trust_id': 'exxee111qwwwwe'}


def _get_fake_event_values(id=None,
                           lease_id=_get_fake_lease_uuid(),
                           event_type='fake_event_type',
                           time=None,
                           status='fake_event_status'):
    if id is None:
        id = _get_fake_random_uuid()
    return {'id': id,
            'lease_id': lease_id,
            'event_type': event_type,
            'time': _get_datetime('2030-03-01 00:00') if not time else time,
            'status': status}


def _get_datetime(value='2030-01-01 00:00'):
    return datetime.datetime.strptime(value, '%Y-%m-%d %H:%M')


def _get_fake_phys_lease_values(id=None,
                                name='fake_phys_lease',
                                start_date=_get_datetime('2030-01-01 00:00'),
                                end_date=_get_datetime('2030-01-02 00:00'),
                                resource_id=None):
    if id is None:
        id = _get_fake_random_uuid()
    return {'id': id,
            'name': name,
            'user_id': 'fake',
            'project_id': 'fake',
            'start_date': start_date,
            'end_date': end_date,
            'trust': 'trust',
            'reservations': [_get_fake_phys_reservation_values(
                id=_get_fake_random_uuid(),
                lease_id=id,
                resource_id=resource_id)],
            'events': []
            }


def _get_fake_host_allocation_values(
        id=None,
        compute_host_id=_get_fake_random_uuid(),
        reservation_id=_get_fake_random_uuid()):
    values = {'compute_host_id': compute_host_id,
              'reservation_id': reservation_id}
    if id is not None:
        values.update({'id': id})

    return values


def _create_physical_lease(values=_get_fake_phys_lease_values(),
                           random=False):
    """Creating fake lease having a single physical resource."""
    if random is True:
        values = _get_fake_phys_lease_values(id=_get_fake_random_uuid(),
                                             name=_get_fake_random_uuid())
    lease = db_api.lease_create(values)
    phys_res = _get_fake_phys_reservation_values()
    for reservation in db_api.reservation_get_all_by_lease_id(lease['id']):
        allocation_values = {
            'id': _get_fake_random_uuid(),
            'compute_host_id': values['reservations'][0]['resource_id'],
            'reservation_id': reservation['id']
        }
        db_api.host_allocation_create(allocation_values)
        computehost_reservation = {
            'id': _get_fake_random_uuid(),
            'reservation_id': values['reservations'][0]['id'],
            'resource_properties': phys_res['resource_properties'],
            'hypervisor_properties': phys_res['hypervisor_properties'],
            'count_range': "{0} - {1}".format(phys_res['min'],
                                              phys_res['max'])
        }
        db_api.host_reservation_create(computehost_reservation)
    return lease


def _get_fake_host_reservation_values(id=None, reservation_id=None):
    if id is None:
        id = _get_fake_random_uuid()
    if reservation_id is None:
        reservation_id = _get_fake_random_uuid()
    return {'id': id,
            'reservation_id': reservation_id,
            'resource_properties': "fake",
            'hypervisor_properties': "fake",
            'min': 1, 'max': 1,
            'trust_id': 'exxee111qwwwwe'}


def _get_fake_instance_values(id=None, reservation_id=None):
    if id is None:
        id = _get_fake_random_uuid()
    if reservation_id is None:
        reservation_id = _get_fake_random_uuid()
    return {'id': id,
            'reservation_id': reservation_id,
            'vcpus': 1,
            'memory_mb': 2024,
            'disk_gb': 100,
            'amount': 2,
            'affinity': False,
            'flavor_id': 'fake_flavor_id',
            'aggregate_id': 29,
            'server_group_id': 'server_group_id'}


def _get_fake_cpu_info():
    return str({'vendor': 'Intel',
                'model': 'Westmere',
                'arch': 'x86_64',
                'features': ['rdtscp', 'pdpe1gb', 'hypervisor', 'vmx', 'ss',
                             'vme'],
                'topology': {'cores': 1, 'threads': 1, 'sockets': 2}})


def _get_fake_host_values(id=None, mem=8192, disk=10):
    if id is None:
        id = _get_fake_random_uuid()
    return {'id': id,
            'availability_zone': 'az1',
            'vcpus': 1,
            'cpu_info': _get_fake_cpu_info(),
            'hypervisor_type': 'QEMU',
            'hypervisor_version': 1000,
            'memory_mb': mem,
            'local_gb': disk,
            'status': 'free',
            'trust_id': 'exxee111qwwwwe',
            }


def _get_fake_host_extra_capabilities(id=None,
                                      computehost_id=None,
                                      name='vgpu',
                                      value='2'):
    if id is None:
        id = _get_fake_random_uuid()
    if computehost_id is None:
        computehost_id = _get_fake_random_uuid()
    return {'id': id,
            'computehost_id': computehost_id,
            'property_name': name,
            'capability_value': value}


def is_result_sorted_correctly(results, sort_key, sort_dir='asc'):
    sorted_list = sorted(results,
                         key=operator.itemgetter(sort_key),
                         reverse=False if sort_dir == 'asc' else True)
    return sorted_list == results


class SQLAlchemyDBApiTestCase(tests.DBTestCase):
    """Test case for SQLAlchemy DB API."""

    def setUp(self):
        super(SQLAlchemyDBApiTestCase, self).setUp()

    def test_create_phys_lease(self):
        """Check physical lease create

        Create a physical lease and verify that all tables have been
        populated.
        """

        result = db_api.lease_create(_get_fake_phys_lease_values())
        self.assertEqual(result['name'],
                         _get_fake_phys_lease_values()['name'])
        self.assertEqual(0, len(db_api.event_get_all()))
        self.assertEqual(1, len(db_api.reservation_get_all()))

    def test_create_duplicate_leases(self):
        """Create two leases with same ids, and checks it raises an error."""

        db_api.lease_create(_get_fake_phys_lease_values(id='42'))
        self.assertRaises(db_exceptions.BlazarDBDuplicateEntry,
                          db_api.lease_create,
                          _get_fake_phys_lease_values(id='42'))

    def test_create_leases_with_duplicated_reservation(self):
        """Check duplicated reservation create

        Create two leases with a duplicated reservation,
        and checks it raises an error.
        """
        lease_values = _get_fake_phys_lease_values()

        db_api.lease_create(lease_values)

        lease_values['id'] = _get_fake_random_uuid()
        lease_values['name'] = 'duplicated_reservation'

        self.assertRaises(db_exceptions.BlazarDBDuplicateEntry,
                          db_api.lease_create,
                          lease_values)

    def test_create_leases_with_duplicated_event(self):
        """Check duplicated event create

        Create two leases with a duplicated event,
        and checks it raises an error.
        """
        lease_values = _get_fake_phys_lease_values()
        lease_values['events'] = [_get_fake_event_values()]

        db_api.lease_create(lease_values)

        lease_values['id'] = _get_fake_random_uuid()
        lease_values['name'] = 'duplicated_event'
        lease_values['reservations'][0]['id'] = _get_fake_random_uuid()

        self.assertRaises(db_exceptions.BlazarDBDuplicateEntry,
                          db_api.lease_create,
                          lease_values)

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
        self.assertRaises(db_exceptions.BlazarDBNotFound,
                          db_api.lease_destroy, 'fake_id')

    def test_get_physical_lease(self):
        """Test if physical host reservation contains data of reservation."""
        lease = _get_fake_phys_lease_values()
        lease['events'].append(_get_fake_event_values(lease_id=lease['id']))
        result = _create_physical_lease(values=lease)
        result = db_api.lease_get(result['id'])
        res = result.to_dict()
        self.assertEqual(res['reservations'][0]['hypervisor_properties'],
                         lease['reservations'][0]['hypervisor_properties'])
        self.assertEqual(res['reservations'][0]['resource_properties'],
                         lease['reservations'][0]['resource_properties'])
        self.assertEqual(res['reservations'][0]['min'],
                         lease['reservations'][0]['min'])
        self.assertEqual(res['reservations'][0]['max'],
                         lease['reservations'][0]['max'])

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
        """Update both start_date and name and check lease has been updated."""
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
        """Create and verify reservation

        Create a reservation and verify that all tables have been
        populated.
        """

        result = db_api.reservation_create(_get_fake_phys_reservation_values())
        self.assertEqual(result['lease_id'],
                         _get_fake_phys_reservation_values()
                         ['lease_id'])

    def test_reservation_get_all_by_values(self):
        """Create 2 reservations and check find abilities

        Create two reservations and verify that we can find reservation per
        resource_id or resource_type.
        """
        db_api.reservation_create(
            _get_fake_phys_reservation_values(id='1', resource_id='1234'))
        db_api.reservation_create(
            _get_fake_phys_reservation_values(id='2', resource_id='5678'))
        self.assertEqual(2, len(db_api.reservation_get_all_by_values()))
        self.assertEqual(1, len(db_api.reservation_get_all_by_values(
            resource_id='5678')))
        self.assertEqual(2, len(db_api.reservation_get_all_by_values(
            resource_type=host_plugin.RESOURCE_TYPE)))

    def test_reservation_update(self):
        result = db_api.reservation_create(_get_fake_phys_reservation_values())
        self.assertNotEqual('fake', result.resource_type)

        result = db_api.reservation_update(result.id,
                                           {"resource_type": 'fake'})
        self.assertEqual('fake', result.resource_type)

    def test_reservation_destroy_for_reservation_not_found(self):
        self.assertFalse(db_api.reservation_get('1'))
        self.assertRaises(db_exceptions.BlazarDBNotFound,
                          db_api.reservation_destroy, '1')

    def test_create_duplicate_reservation(self):
        """Create duplicated reservation

        Create a reservation and verify that an exception is raised if a
        duplicated reservation is created.
        """
        uuid = _get_fake_random_uuid()
        db_api.reservation_create(_get_fake_phys_reservation_values(id=uuid))
        self.assertRaises(db_exceptions.BlazarDBDuplicateEntry,
                          db_api.reservation_create,
                          _get_fake_phys_reservation_values(id=uuid))

    # Host reservations

    def test_create_host_reservation(self):
        """Create host reservation

        Create a host reservation and verify that all tables
        have been populated.
        """

        result = db_api.host_reservation_create(
            _get_fake_host_reservation_values(id='1'))
        self.assertEqual(result['id'],
                         _get_fake_host_reservation_values(id='1')
                         ['id'])

    def test_create_duplicate_host_reservation(self):
        """Create duplicated host reservation

        Create a duplicated host reservation and verify that an exception is
        raised.
        """

        db_api.host_reservation_create(
            _get_fake_host_reservation_values(id='1'))
        self.assertRaises(db_exceptions.BlazarDBDuplicateEntry,
                          db_api.host_reservation_create,
                          _get_fake_host_reservation_values(id='1'))

    def test_delete_host_reservation(self):
        """Check deletion for host reservation

        Check all deletion cases for host reservation,
        including cascade deletion from reservations table.
        """

        self.assertRaises(db_exceptions.BlazarDBNotFound,
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
        """Create a host and verify that all tables have been populated."""
        result = db_api.host_create(_get_fake_host_values(id='1'))
        self.assertEqual(result['id'], _get_fake_host_values(id='1')['id'])

    def test_create_duplicated_host(self):
        """Create a duplicated host and verify that an exception is raised."""
        db_api.host_create(_get_fake_host_values(id='1'))
        # Making sure we still raise a DuplicateDBEntry
        self.assertRaises(db_exceptions.BlazarDBDuplicateEntry,
                          db_api.host_create,
                          _get_fake_host_values(id='1'))

    def test_search_for_hosts_by_ram(self):
        """Check RAM info search

        Create two hosts and check that we can find a host per its RAM
        info.
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
        # We create a first host, with extra capabilities
        db_api.host_create(_get_fake_host_values(id=1))
        db_api.resource_property_create(dict(
            id='a', resource_type='physical:host', private=False,
            property_name='vgpu'))
        db_api.resource_property_create(dict(
            id='b', resource_type='physical:host', private=False,
            property_name='nic_model'))
        db_api.host_extra_capability_create(
            _get_fake_host_extra_capabilities(computehost_id=1))
        db_api.host_extra_capability_create(_get_fake_host_extra_capabilities(
            computehost_id=1,
            name='nic_model',
            value='ACME Model A',
        ))
        # We create a second host, without any extra capabilities
        db_api.host_create(_get_fake_host_values(id=2))

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
        self.assertRaises(db_exceptions.BlazarDBNotFound,
                          db_api.host_get_all_by_queries, ['apples < 2048'])
        self.assertEqual(1, len(
            db_api.host_get_all_by_queries(['nic_model == ACME Model A'])
        ))

    def test_resource_properties_list(self):
        """Create one host and test extra capability queries."""
        # We create a first host, with extra capabilities
        db_api.host_create(_get_fake_host_values(id=1))
        db_api.resource_property_create(dict(
            id='a', resource_type='physical:host', private=False,
            property_name='vgpu'))
        db_api.host_extra_capability_create(
            _get_fake_host_extra_capabilities(computehost_id=1))

        result = db_api.resource_properties_list('physical:host')

        self.assertListEqual(result, [('vgpu', False, '2')])

    def test_search_for_hosts_by_composed_queries(self):
        """Create one host and test composed queries."""

        db_api.host_create(_get_fake_host_values(mem=8192))
        self.assertEqual(1, len(
            db_api.host_get_all_by_queries(['memory_mb > 2048',
                                            'cpu_info like %Westmere%'])))
        self.assertEqual(0, len(
            db_api.host_get_all_by_queries(['memory_mb < 2048',
                                            'cpu_info like %Westmere%'])))
        self.assertRaises(db_exceptions.BlazarDBInvalidFilter,
                          db_api.host_get_all_by_queries, ['memory_mb <'])
        self.assertRaises(db_exceptions.BlazarDBNotFound,
                          db_api.host_get_all_by_queries, ['apples < 2048'])
        self.assertRaises(db_exceptions.BlazarDBInvalidFilterOperator,
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
        self.assertIsNone(db_api.host_get(1))
        self.assertRaises(db_exceptions.BlazarDBNotFound,
                          db_api.host_destroy, 2)

    def test_create_host_extra_capability(self):
        db_api.resource_property_create(dict(
            id='id', resource_type='physical:host', private=False,
            property_name='vgpu'))
        result, _ = db_api.host_extra_capability_create(
            _get_fake_host_extra_capabilities(id=1, name='vgpu'))

        self.assertEqual(result.id, _get_fake_host_values(id='1')['id'])

    def test_create_duplicated_host_extra_capability(self):
        db_api.host_extra_capability_create(
            _get_fake_host_extra_capabilities(id=1))
        self.assertRaises(db_exceptions.BlazarDBDuplicateEntry,
                          db_api.host_extra_capability_create,
                          _get_fake_host_extra_capabilities(id='1'))

    def test_get_host_extra_capability_per_id(self):
        db_api.host_extra_capability_create(
            _get_fake_host_extra_capabilities(id='1'))
        result, _ = db_api.host_extra_capability_get('1')
        self.assertEqual('1', result.id)

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
        res, _ = db_api.host_extra_capability_get('1')
        self.assertEqual('2', res.capability_value)

    def test_delete_host_extra_capability(self):
        db_api.host_extra_capability_create(
            _get_fake_host_extra_capabilities(id='1'))
        db_api.host_extra_capability_destroy('1')
        self.assertIsNone(db_api.host_extra_capability_get('1'))
        self.assertRaises(db_exceptions.BlazarDBNotFound,
                          db_api.host_extra_capability_destroy, '1')

    def test_host_extra_capability_get_all_per_name(self):
        db_api.host_extra_capability_create(
            _get_fake_host_extra_capabilities(id='1', computehost_id='1'))
        res = db_api.host_extra_capability_get_all_per_name('1', 'vgpu')
        self.assertEqual(1, len(res))
        self.assertEqual([],
                         db_api.host_extra_capability_get_all_per_name('1',
                                                                       'bad'))

    # Instance reservation

    def check_instance_reservation_values(self, expected, reservation_id):
        inst_reservation = db_api.instance_reservation_get(reservation_id)
        for k, v in expected.items():
            self.assertEqual(v, inst_reservation[k])

    def test_instance_reservation_create(self):
        reservation_values = _get_fake_instance_values(id='1')
        ret = db_api.instance_reservation_create(reservation_values)

        self.assertEqual('1', ret['id'])
        self.check_instance_reservation_values(reservation_values, '1')

    def test_create_duplicated_instance_reservation(self):
        reservation_values = _get_fake_instance_values(id='1')
        db_api.instance_reservation_create(reservation_values)
        self.assertRaises(db_exceptions.BlazarDBDuplicateEntry,
                          db_api.instance_reservation_create,
                          reservation_values)

    def test_instance_reservation_get(self):
        reservation1_values = _get_fake_instance_values(id='1')
        db_api.instance_reservation_create(reservation1_values)
        reservation2_values = _get_fake_instance_values(id='2')
        db_api.instance_reservation_create(reservation2_values)

        self.check_instance_reservation_values(reservation1_values, '1')
        self.check_instance_reservation_values(reservation2_values, '2')

    def test_instance_reservation_update(self):
        reservation_values = _get_fake_instance_values(id='1')
        db_api.instance_reservation_create(reservation_values)

        self.check_instance_reservation_values(reservation_values, '1')

        updated_values = {
            'flavor_id': 'updated-flavor-id',
            'aggregate_id': 30,
            'server_group_id': 'updated-server-group-id'
            }
        db_api.instance_reservation_update('1', updated_values)
        reservation_values.update(updated_values)
        self.check_instance_reservation_values(reservation_values, '1')

    def test_update_non_existing_instance_reservation(self):
        self.assertRaises(db_exceptions.BlazarDBNotFound,
                          db_api.instance_reservation_destroy, 'non-exists')

    def test_instance_reservation_destroy(self):
        reservation_values = _get_fake_instance_values(id='1')
        db_api.instance_reservation_create(reservation_values)

        self.check_instance_reservation_values(reservation_values, '1')

        db_api.instance_reservation_destroy('1')
        self.assertIsNone(db_api.instance_reservation_get('1'))

    def test_destroy_non_existing_instance_reservation(self):
        self.assertRaises(db_exceptions.BlazarDBNotFound,
                          db_api.instance_reservation_destroy, 'non-exists')

    # Host allocations

    def test_host_allocation_get_all(self):
        self.assertFalse(db_api.host_allocation_get_all())

        db_api.host_allocation_create(_get_fake_host_allocation_values(id='1'))
        db_api.host_allocation_create(_get_fake_host_allocation_values(id='2'))

        self.assertEqual(2, len(db_api.host_allocation_get_all()))

    def test_host_allocation_create_for_duplicated_hosts(self):
        db_api.host_allocation_create(
            _get_fake_host_allocation_values(id='1')
        )

        self.assertRaises(db_exceptions.BlazarDBDuplicateEntry,
                          db_api.host_allocation_create,
                          _get_fake_host_allocation_values(id='1'))

    def test_host_allocation_update_for_host(self):
        host_allocation = db_api.host_allocation_create(
            _get_fake_host_allocation_values(
                compute_host_id="1",
                reservation_id="1"
            ))

        new_host_allocation = db_api.host_allocation_update(
            host_allocation.id,
            _get_fake_host_allocation_values(
                compute_host_id="2",
                reservation_id="2"
            ))

        self.assertEqual('2', new_host_allocation.compute_host_id)
        self.assertEqual('2', new_host_allocation.reservation_id)
        self.assertNotEqual(host_allocation.compute_host_id,
                            new_host_allocation.compute_host_id)

    def test_host_allocation_destroy_for_host(self):
        host_allocation = db_api.host_allocation_create(
            _get_fake_host_allocation_values()
        )
        db_api.host_allocation_destroy(host_allocation.id)

        self.assertIsNone(db_api.host_allocation_get(host_allocation.id))

    def test_host_allocation_destroy_for_host_not_found(self):
        host_allocation_id = _get_fake_random_uuid()

        self.assertIsNone(db_api.host_allocation_get(host_allocation_id))
        self.assertRaises(db_exceptions.BlazarDBNotFound,
                          db_api.host_allocation_destroy,
                          host_allocation_id)

    def test_host_allocation_get_all_by_values(self):
        db_api.host_allocation_create(_get_fake_host_allocation_values(
            compute_host_id="1", reservation_id="1"))
        db_api.host_allocation_create(_get_fake_host_allocation_values(
            compute_host_id="1", reservation_id="1234"))

        self.assertEqual(2, len(db_api.host_allocation_get_all_by_values()))
        self.assertEqual(1, len(db_api.host_allocation_get_all_by_values(
            reservation_id='1234')))

    # Event

    def test_event_create(self):
        fake_event_type = 'test_event'

        test_event = db_api.event_create(_get_fake_event_values(
            event_type=fake_event_type))
        self.assertTrue(test_event)
        self.assertEqual(fake_event_type, test_event.event_type)

    def test_create_duplicated_event(self):
        self.assertFalse(db_api.event_get('1'))

        fake_values = _get_fake_event_values(id='1')
        test_event = db_api.event_create(fake_values)

        self.assertTrue(test_event)
        self.assertRaises(db_exceptions.BlazarDBDuplicateEntry,
                          db_api.event_create, fake_values)

    def test_event_update(self):
        self.assertFalse(db_api.event_get('1'))

        test_event = db_api.event_create(_get_fake_event_values(id='1'))

        self.assertTrue(test_event)

        test_event = db_api.event_update(test_event.id, {'status': 'changed'})

        self.assertEqual('changed', test_event.status)

    def test_event_destroy(self):
        self.assertFalse(db_api.event_get('1'))

        db_api.event_create(_get_fake_event_values(
            id='1'))
        self.assertTrue(db_api.event_get('1'))
        db_api.event_destroy('1')
        self.assertFalse(db_api.event_get('1'))

    def test_destroy_for_event_not_found(self):
        self.assertFalse(db_api.event_get('1'))
        self.assertRaises(db_exceptions.BlazarDBNotFound,
                          db_api.event_destroy, '1')

    def test_event_get_first_sorted_by_event_type_filter(self):
        fake_event_type = 'test_event'

        db_api.event_create(_get_fake_event_values(
            id='1'
        ))
        db_api.event_create(_get_fake_event_values(
            id='2',
            event_type=fake_event_type
        ))
        db_api.event_create(_get_fake_event_values(
            id='3',
            event_type=fake_event_type
        ))

        filtered_events = db_api.event_get_first_sorted_by_filters(
            sort_key='time',
            sort_dir='asc',
            filters={'event_type': fake_event_type}
        )
        self.assertEqual(fake_event_type, filtered_events.event_type)
        self.assertEqual('2', filtered_events.id)

    def test_event_get_first_sorted_by_status_filter(self):
        fake_status = 'test_status'
        db_api.event_create(_get_fake_event_values(
            id='1'
        ))
        db_api.event_create(_get_fake_event_values(
            id='2',
            status=fake_status
        ))
        db_api.event_create(_get_fake_event_values(
            id='3',
            status=fake_status
        ))

        filtered_events = db_api.event_get_first_sorted_by_filters(
            sort_key='time',
            sort_dir='asc',
            filters={'status': fake_status}
        )
        self.assertEqual(fake_status, filtered_events.status)
        self.assertEqual('2', filtered_events.id)

    def test_event_get_first_sorted_by_lease_id_filter(self):
        fake_lease_id = '1234'
        db_api.event_create(_get_fake_event_values(
            id='1'
        ))
        db_api.event_create(_get_fake_event_values(
            id='2',
            lease_id=fake_lease_id
        ))
        db_api.event_create(_get_fake_event_values(
            id='3',
            lease_id=fake_lease_id
        ))

        filtered_events = db_api.event_get_first_sorted_by_filters(
            sort_key='time',
            sort_dir='asc',
            filters={'lease_id': fake_lease_id}
        )
        self.assertEqual(fake_lease_id, filtered_events.lease_id)
        self.assertEqual('2', filtered_events.id)

    def test_event_get_sorted_asc_by_event_type_filter(self):
        fake_event_type = 'test_event'
        sort_dir = 'asc'
        sort_key = 'time'

        db_api.event_create(_get_fake_event_values(
            id='1',
            event_type=fake_event_type,
            time=datetime.datetime.utcnow()
        ))
        db_api.event_create(_get_fake_event_values(
            id='2',
            event_type=fake_event_type,
            time=datetime.datetime.utcnow()
        ))

        filtered_events = db_api.event_get_all_sorted_by_filters(
            sort_key=sort_key,
            sort_dir=sort_dir,
            filters={'event_type': fake_event_type}
        )
        self.assertEqual(2, len(filtered_events))
        self.assertEqual(fake_event_type, filtered_events[0].event_type)

        # testing sort
        self.assertTrue(is_result_sorted_correctly(filtered_events,
                                                   sort_key=sort_key,
                                                   sort_dir=sort_dir))

    def test_event_get_sorted_asc_by_status_filter(self):
        fake_status = 'test_status'
        sort_dir = 'asc'
        sort_key = 'time'

        db_api.event_create(_get_fake_event_values(
            id='1',
            status=fake_status
        ))
        db_api.event_create(_get_fake_event_values(
            id='2'
        ))

        filtered_events = db_api.event_get_all_sorted_by_filters(
            sort_key=sort_key,
            sort_dir=sort_dir,
            filters={'status': fake_status}
        )
        self.assertEqual(1, len(filtered_events))
        self.assertEqual(fake_status, filtered_events[0].status)

        # testing sort
        self.assertTrue(is_result_sorted_correctly(filtered_events,
                                                   sort_key=sort_key,
                                                   sort_dir=sort_dir))

    def test_event_get_sorted_asc_by_lease_id_filter(self):
        fake_lease_id = '1234'
        sort_dir = 'asc'
        sort_key = 'time'

        db_api.event_create(_get_fake_event_values(
            id='1',
            lease_id=fake_lease_id

        ))
        db_api.event_create(_get_fake_event_values(
            id='2'
        ))

        filtered_events = db_api.event_get_all_sorted_by_filters(
            sort_key=sort_key,
            sort_dir=sort_dir,
            filters={'lease_id': fake_lease_id}
        )
        self.assertEqual(1, len(filtered_events))
        self.assertEqual(fake_lease_id, filtered_events[0].lease_id)

        # testing sort
        self.assertTrue(is_result_sorted_correctly(filtered_events,
                                                   sort_key=sort_key,
                                                   sort_dir=sort_dir))

    def test_event_get_sorted_asc_by_time_filter(self):
        def check_query(border, op, expected_ids):
            filtered_events = db_api.event_get_all_sorted_by_filters(
                sort_key=sort_key,
                sort_dir=sort_dir,
                filters={'time': {'border': _get_datetime(border),
                                  'op': op}})
            filtered_event_ids = [e.id for e in filtered_events]
            self.assertListEqual(expected_ids, filtered_event_ids)

        time1 = _get_datetime('2030-01-01 01:00')
        time2 = _get_datetime('2030-01-01 02:00')
        time3 = _get_datetime('2030-01-01 03:00')
        sort_key = 'time'
        sort_dir = 'asc'

        db_api.event_create(_get_fake_event_values(id='1', time=time1))
        db_api.event_create(_get_fake_event_values(id='2', time=time2))
        db_api.event_create(_get_fake_event_values(id='3', time=time3))

        check_query('2030-01-01 02:00', 'lt', ['1'])
        check_query('2030-01-01 02:00', 'le', ['1', '2'])
        check_query('2030-01-01 02:00', 'gt', ['3'])
        check_query('2030-01-01 02:00', 'ge', ['2', '3'])
        check_query('2030-01-01 02:00', 'eq', ['2'])

    def test_event_get_sorted_desc_by_event_type_filter(self):
        fake_event_type = 'test_event'
        sort_dir = 'desc'
        sort_key = 'time'

        db_api.event_create(_get_fake_event_values(
            id='1',
            event_type=fake_event_type
        ))
        db_api.event_create(_get_fake_event_values(
            id='2',
            event_type=fake_event_type
        ))

        filtered_events = db_api.event_get_all_sorted_by_filters(
            sort_key=sort_key,
            sort_dir=sort_dir,
            filters={'event_type': fake_event_type}
        )
        self.assertEqual(2, len(filtered_events))
        self.assertEqual(fake_event_type, filtered_events[0].event_type)

        # testing sort
        self.assertTrue(is_result_sorted_correctly(filtered_events,
                                                   sort_key=sort_key,
                                                   sort_dir=sort_dir))

    def test_event_get_sorted_desc_by_status_filter(self):
        fake_status = 'test_status'
        sort_dir = 'desc'
        sort_key = 'time'

        db_api.event_create(_get_fake_event_values(
            id='1',
            status=fake_status
        ))
        db_api.event_create(_get_fake_event_values(
            id='2'
        ))

        filtered_events = db_api.event_get_all_sorted_by_filters(
            sort_key=sort_key,
            sort_dir=sort_dir,
            filters={'status': fake_status}
        )
        self.assertEqual(1, len(filtered_events))
        self.assertEqual(fake_status, filtered_events[0].status)

        # testing sort
        self.assertTrue(is_result_sorted_correctly(filtered_events,
                                                   sort_key=sort_key,
                                                   sort_dir=sort_dir))

    def test_event_get_sorted_desc_by_lease_id_filter(self):
        fake_lease_id = '1234'
        sort_dir = 'desc'
        sort_key = 'time'

        db_api.event_create(_get_fake_event_values(
            id='1',
            lease_id=fake_lease_id

        ))
        db_api.event_create(_get_fake_event_values(
            id='2'
        ))

        filtered_events = db_api.event_get_all_sorted_by_filters(
            sort_key=sort_key,
            sort_dir=sort_dir,
            filters={'lease_id': fake_lease_id}
        )
        self.assertEqual(1, len(filtered_events))
        self.assertEqual(fake_lease_id, filtered_events[0].lease_id)

        # testing sort
        self.assertTrue(is_result_sorted_correctly(filtered_events,
                                                   sort_key=sort_key,
                                                   sort_dir=sort_dir))

    def test_event_get_sorted_desc_by_time_filter(self):
        def check_query(border, op, expected_ids):
            filtered_events = db_api.event_get_all_sorted_by_filters(
                sort_key=sort_key,
                sort_dir=sort_dir,
                filters={'time': {'border': _get_datetime(border),
                                  'op': op}})
            filtered_event_ids = [e.id for e in filtered_events]
            self.assertListEqual(expected_ids, filtered_event_ids)

        time1 = _get_datetime('2030-01-01 01:00')
        time2 = _get_datetime('2030-01-01 02:00')
        time3 = _get_datetime('2030-01-01 03:00')
        sort_key = 'time'
        sort_dir = 'desc'

        db_api.event_create(_get_fake_event_values(id='1', time=time1))
        db_api.event_create(_get_fake_event_values(id='2', time=time2))
        db_api.event_create(_get_fake_event_values(id='3', time=time3))

        check_query('2030-01-01 02:00', 'lt', ['1'])
        check_query('2030-01-01 02:00', 'le', ['2', '1'])
        check_query('2030-01-01 02:00', 'gt', ['3'])
        check_query('2030-01-01 02:00', 'ge', ['3', '2'])
        check_query('2030-01-01 02:00', 'eq', ['2'])
