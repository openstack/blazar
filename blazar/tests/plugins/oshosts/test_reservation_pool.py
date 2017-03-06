# Copyright (c) 2013 Openstack Fondation
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import uuid as uuidgen

from novaclient import client as nova_client
from novaclient import exceptions as nova_exceptions
from oslo_config import cfg

from blazar import context
from blazar.manager import exceptions as manager_exceptions
from blazar.plugins import oshosts as host_plugin
from blazar.plugins.oshosts import reservation_pool as rp
from blazar import tests
from blazar.utils.openstack import base
from blazar.utils.openstack import nova


class AggregateFake(object):

    def __init__(self, i, name, hosts):
        self.id = i
        self.name = name
        self.hosts = hosts


class ReservationPoolTestCase(tests.TestCase):

    def setUp(self):
        super(ReservationPoolTestCase, self).setUp()
        self.pool_name = 'pool-name-xxx'
        self.project_id = 'project-uuid'
        self.fake_aggregate = AggregateFake(i=123,
                                            name='fooname',
                                            hosts=['host1', 'host2'])
        conf = cfg.CONF[host_plugin.RESOURCE_TYPE]
        self.freepool_name = conf.aggregate_freepool_name
        self.project_id_key = conf.project_id_key
        self.blazar_owner = conf.blazar_owner
        self.blazar_az_prefix = conf.blazar_az_prefix

        self.fake_freepool = AggregateFake(i=456,
                                           name=self.freepool_name,
                                           hosts=['host3'])

        self.set_context(context.BlazarContext(project_id=self.project_id))

        self.nova_client = nova_client
        self.nova = self.patch(self.nova_client, 'Client').return_value

        self.patch(self.nova.aggregates, 'set_metadata')
        self.patch(self.nova.aggregates, 'remove_host')

        self.patch(base, 'url_for').return_value = 'http://foo.bar'
        self.pool = rp.ReservationPool()

        self.p_name = self.patch(self.pool, '_generate_aggregate_name')
        self.p_name.return_value = self.pool_name

    def _patch_get_aggregate_from_name_or_id(self):
        def get_fake_aggregate(*args):
            if self.freepool_name in args:
                return self.fake_freepool
            else:
                return self.fake_aggregate

        patched_pool = self.patch(self.pool, 'get_aggregate_from_name_or_id')
        patched_pool.side_effect = get_fake_aggregate

    def test_get_aggregate_from_name_or_id(self):
        def fake_aggregate_get(id):
            if id == self.fake_aggregate.id:
                return self.fake_aggregate
            else:
                raise nova_exceptions.NotFound(id)

        self.nova.aggregates.list.return_value = [self.fake_aggregate]
        self.nova.aggregates.get.side_effect = fake_aggregate_get

        self.assertRaises(manager_exceptions.AggregateNotFound,
                          self.pool.get_aggregate_from_name_or_id, 'none')
        self.assertRaises(manager_exceptions.AggregateNotFound,
                          self.pool.get_aggregate_from_name_or_id, '3000')
        self.assertEqual(self.pool.get_aggregate_from_name_or_id('fooname'),
                         self.fake_aggregate)
        self.assertEqual(
            self.pool.get_aggregate_from_name_or_id(self.fake_aggregate),
            self.fake_aggregate)

    def test_generate_aggregate_name(self):
        self.uuidgen = uuidgen
        self.patch(uuidgen, 'uuid4').return_value = 'foo'
        self.assertEqual('foo', rp.ReservationPool._generate_aggregate_name())

    def test_create(self):
        self.patch(self.nova.aggregates, 'create').return_value = (
            self.fake_aggregate)

        agg = self.pool.create()

        self.assertEqual(agg, self.fake_aggregate)

        az_name = self.blazar_az_prefix + self.pool_name
        check0 = self.nova.aggregates.create
        check0.assert_called_once_with(self.pool_name, az_name)

        meta = {self.blazar_owner: self.project_id}
        check1 = self.nova.aggregates.set_metadata
        check1.assert_called_once_with(self.fake_aggregate, meta)

    def test_create_no_az(self):
        self.patch(self.nova.aggregates, 'create').return_value = (
            self.fake_aggregate)

        self.pool.create(az=False)

        self.nova.aggregates.create.assert_called_once_with(self.pool_name,
                                                            None)

    def test_create_no_project_id(self):
        self.patch(self.nova.aggregates, 'create').return_value = (
            self.fake_aggregate)

        self.nova_wrapper = self.patch(nova.NovaClientWrapper, 'nova')

        def raiseRuntimeError():
            raise RuntimeError()

        self.context_mock.side_effect = raiseRuntimeError

        self.assertRaises(manager_exceptions.ProjectIdNotFound,
                          self.pool.create)

    def test_delete_with_host(self):
        self._patch_get_aggregate_from_name_or_id()
        agg = self.pool.get('foo')

        self.pool.delete(agg)
        self.nova.aggregates.delete.assert_called_once_with(agg.id)
        for host in agg.hosts:
            self.nova.aggregates.remove_host.assert_any_call(agg.id, host)
            self.nova.aggregates.add_host.assert_any_call(
                self.fake_freepool.id, host
            )

        # can't delete aggregate with hosts
        self.assertRaises(manager_exceptions.AggregateHaveHost,
                          self.pool.delete, 'bar',
                          force=False)

    def test_delete_with_no_host(self):
        self._patch_get_aggregate_from_name_or_id()
        agg = self.pool.get('foo')
        agg.hosts = []
        self.pool.delete('foo', force=False)
        self.nova.aggregates.delete.assert_called_once_with(agg.id)

    def test_delete_with_no_freepool(self):
        def get_fake_aggregate_but_no_freepool(*args):
            if self.freepool_name in args:
                raise manager_exceptions.AggregateNotFound
            else:
                return self.fake_aggregate
        fake_pool = self.patch(self.pool, 'get_aggregate_from_name_or_id')
        fake_pool.side_effect = get_fake_aggregate_but_no_freepool
        agg = self.pool.get('foo')
        agg.hosts = []
        self.assertRaises(manager_exceptions.NoFreePool,
                          self.pool.delete, 'bar',
                          force=False)

    def test_get_all(self):
        self.pool.get_all()
        self.nova.aggregates.list.assert_called_once_with()

    def test_get(self):
        self._patch_get_aggregate_from_name_or_id()
        agg = self.pool.get('foo')
        self.assertEqual(self.fake_aggregate, agg)

    def test_add_computehost(self):
        self._patch_get_aggregate_from_name_or_id()
        self.pool.add_computehost('pool', 'host3')

        check0 = self.nova.aggregates.add_host
        check0.assert_any_call(self.fake_aggregate.id, 'host3')
        check1 = self.nova.aggregates.remove_host
        check1.assert_any_call(self.fake_aggregate.id, 'host3')

    def test_add_computehost_with_host_id(self):
        # NOTE(sbauza): Freepool.hosts only contains names of hosts, not UUIDs
        self._patch_get_aggregate_from_name_or_id()
        self.assertRaises(manager_exceptions.HostNotInFreePool,
                          self.pool.add_computehost, 'pool', '3')

    def test_add_computehost_not_in_freepool(self):
        self._patch_get_aggregate_from_name_or_id()
        self.assertRaises(manager_exceptions.HostNotInFreePool,
                          self.pool.add_computehost,
                          'foopool',
                          'ghost-host')

    def test_add_computehost_with_no_freepool(self):
        def get_fake_aggregate_but_no_freepool(*args):
            if self.freepool_name in args:
                raise manager_exceptions.AggregateNotFound
            else:
                return self.fake_aggregate

        fake_pool = self.patch(self.pool, 'get_aggregate_from_name_or_id')
        fake_pool.side_effect = get_fake_aggregate_but_no_freepool

        self.assertRaises(manager_exceptions.NoFreePool,
                          self.pool.add_computehost,
                          'pool',
                          'host3')

    def test_add_computehost_with_incorrect_pool(self):
        def get_no_aggregate_but_freepool(*args):
            if self.freepool_name in args:
                return self.freepool_name
            else:
                raise manager_exceptions.AggregateNotFound
        fake_pool = self.patch(self.pool, 'get_aggregate_from_name_or_id')
        fake_pool.side_effect = get_no_aggregate_but_freepool
        self.assertRaises(manager_exceptions.AggregateNotFound,
                          self.pool.add_computehost,
                          'wrong_pool',
                          'host3')

    def test_add_computehost_to_freepool(self):
        self._patch_get_aggregate_from_name_or_id()
        self.pool.add_computehost(self.freepool_name, 'host2')
        check = self.nova.aggregates.add_host
        check.assert_called_once_with(self.fake_freepool.id, 'host2')

    def test_remove_computehost_from_freepool(self):
        self._patch_get_aggregate_from_name_or_id()
        self.pool.remove_computehost(self.freepool_name, 'host3')

        check = self.nova.aggregates.remove_host
        check.assert_called_once_with(self.fake_freepool.id, 'host3')

    def test_remove_computehost_not_existing_from_freepool(self):
        self._patch_get_aggregate_from_name_or_id()
        self.assertRaises(manager_exceptions.HostNotInFreePool,
                          self.pool.remove_computehost,
                          self.freepool_name,
                          'hostXX')

    def test_remove_all_computehosts(self):
        self._patch_get_aggregate_from_name_or_id()
        self.pool.remove_all_computehosts('pool')
        for host in self.fake_aggregate.hosts:
            check = self.nova.aggregates.remove_host
            check.assert_any_call(self.fake_aggregate.id, host)

    def test_remove_computehost_with_no_freepool(self):
        def get_fake_aggregate_but_no_freepool(*args):
            if self.freepool_name in args:
                raise manager_exceptions.AggregateNotFound
            else:
                return self.fake_aggregate

        fake_pool = self.patch(self.pool, 'get_aggregate_from_name_or_id')
        fake_pool.side_effect = get_fake_aggregate_but_no_freepool

        self.assertRaises(manager_exceptions.NoFreePool,
                          self.pool.remove_computehost,
                          'pool',
                          'host3')

    def test_remove_computehost_with_incorrect_pool(self):
        def get_no_aggregate_but_freepool(*args):
            if self.freepool_name in args:
                return self.freepool_name
            else:
                raise manager_exceptions.AggregateNotFound
        fake_pool = self.patch(self.pool, 'get_aggregate_from_name_or_id')
        fake_pool.side_effect = get_no_aggregate_but_freepool
        self.assertRaises(manager_exceptions.AggregateNotFound,
                          self.pool.remove_computehost,
                          'wrong_pool',
                          'host3')

    def test_remove_computehost_with_wrong_hosts(self):
        self._patch_get_aggregate_from_name_or_id()
        self.nova.aggregates.remove_host.side_effect = (
            nova_exceptions.NotFound(404))
        self.assertRaises(manager_exceptions.CantRemoveHost,
                          self.pool.remove_computehost,
                          'pool',
                          'host3')

    def test_remove_computehosts_with_duplicate_host(self):
        self._patch_get_aggregate_from_name_or_id()
        self.nova.aggregates.add_host.side_effect = (
            nova_exceptions.Conflict(409))
        self.assertRaises(manager_exceptions.CantAddHost,
                          self.pool.remove_computehost,
                          'pool',
                          'host3')

    def test_get_computehosts_with_correct_pool(self):
        self._patch_get_aggregate_from_name_or_id()
        hosts = self.pool.get_computehosts('foo')
        self.assertEqual(hosts, self.fake_aggregate.hosts)

    def test_get_computehosts_with_incorrect_pool(self):
        self.assertEqual([], self.pool.get_computehosts('wrong_pool'))

    def test_add_project(self):
        self._patch_get_aggregate_from_name_or_id()
        self.pool.add_project('pool', 'projectX')
        check = self.nova.aggregates.set_metadata
        check.assert_called_once_with(self.fake_aggregate.id,
                                      {'projectX': self.project_id_key})

    def test_remove_project(self):
        self._patch_get_aggregate_from_name_or_id()
        self.pool.remove_project('pool', 'projectY')
        check = self.nova.aggregates.set_metadata
        check.assert_called_once_with(self.fake_aggregate.id,
                                      {'projectY': None})
