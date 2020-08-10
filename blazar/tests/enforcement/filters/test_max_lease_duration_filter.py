# Copyright (c) 2021 StackHPC.
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
from unittest import mock

import ddt

from blazar import context
from blazar import enforcement
from blazar.enforcement import exceptions
from blazar.enforcement import filters
from blazar import tests

from oslo_config import cfg


def get_fake_host(host_id):
    return {
        'id': host_id,
        'hypervisor_hostname': 'hypvsr1',
        'service_name': 'compute1',
        'vcpus': 4,
        'cpu_info': 'foo',
        'hypervisor_type': 'xen',
        'hypervisor_version': 1,
        'memory_mb': 8192,
        'local_gb': 10,
    }


def get_fake_lease(**kwargs):
    fake_lease = {
        'id': '1',
        'name': 'lease_test',
        'start_date': datetime.datetime(2014, 1, 1, 1, 23),
        'end_date': datetime.datetime(2014, 1, 1, 2, 23),
        'user_id': '111',
        'project_id': '222',
        'trust_id': '35b17138b3644e6aa1318f3099c5be68',
        'reservations': [{'resource_id': '1234',
                          'resource_type': 'virtual:instance'}],
        'events': [],
        'before_end_date': datetime.datetime(2014, 1, 1, 1, 53),
        'action': None,
        'status': None,
        'status_reason': None}

    if kwargs:
        fake_lease.update(kwargs)

    return fake_lease


@ddt.ddt
class MaxLeaseDurationTestCase(tests.TestCase):
    def setUp(self):
        super(MaxLeaseDurationTestCase, self).setUp()

        self.cfg = cfg
        self.region = 'RegionOne'
        filters.all_filters = ['MaxLeaseDurationFilter']

        self.enforcement = enforcement.UsageEnforcement()

        cfg.CONF.set_override(
            'enabled_filters', filters.all_filters, group='enforcement')
        cfg.CONF.set_override('os_region_name', self.region)

        self.enforcement.load_filters()
        cfg.CONF.set_override('max_lease_duration', 3600, group='enforcement')
        self.fake_service_catalog = [
            dict(
                type='identity', endpoints=[
                    dict(
                        interface='public', region=self.region,
                        url='https://fakeauth.com')
                ]
            )
        ]

        self.ctx = context.BlazarContext(
            user_id='111', project_id='222',
            service_catalog=self.fake_service_catalog)
        self.set_context(self.ctx)

        self.fake_host_id = '1'
        self.fake_host = {
            'id': self.fake_host_id,
            'hypervisor_hostname': 'hypvsr1',
            'service_name': 'compute1',
            'vcpus': 4,
            'cpu_info': 'foo',
            'hypervisor_type': 'xen',
            'hypervisor_version': 1,
            'memory_mb': 8192,
            'local_gb': 10,
        }

        self.addCleanup(self.cfg.CONF.clear_override, 'enabled_filters',
                        group='enforcement')
        self.addCleanup(self.cfg.CONF.clear_override, 'max_lease_duration',
                        group='enforcement')
        self.addCleanup(self.cfg.CONF.clear_override,
                        'max_lease_duration_exempt_project_ids',
                        group='enforcement')
        self.addCleanup(self.cfg.CONF.clear_override, 'os_region_name')

    def tearDown(self):
        super(MaxLeaseDurationTestCase, self).tearDown()

    def test_check_create_allowed_with_max_lease_duration(self):
        allocation_candidates = {'virtual:instance': [get_fake_host('1')]}
        lease_values = get_fake_lease()
        reservations = list(lease_values['reservations'])

        del lease_values['reservations']
        ctx = context.current()

        self.enforcement.check_create(ctx, lease_values, reservations,
                                      allocation_candidates)

    def test_check_create_denied_beyond_max_lease_duration(self):
        allocation_candidates = {'virtual:instance': [get_fake_host('1')]}
        lease_values = get_fake_lease(
            end_date=datetime.datetime(2014, 1, 1, 2, 24))
        reservations = list(lease_values['reservations'])

        del lease_values['reservations']
        ctx = context.current()

        self.assertRaises(exceptions.MaxLeaseDurationException,
                          self.enforcement.check_create, ctx, lease_values,
                          reservations, allocation_candidates)

    def test_check_update_allowed(self):
        current_allocations = {'virtual:instance': [get_fake_host('1')]}
        lease = get_fake_lease(end_date=datetime.datetime(2014, 1, 1, 2, 22))
        reservations = list(lease['reservations'])

        new_lease_values = get_fake_lease(
            end_date=datetime.datetime(2014, 1, 1, 2, 23))
        new_reservations = list(new_lease_values['reservations'])
        allocation_candidates = {'virtual:instance': [get_fake_host('2')]}

        del new_lease_values['reservations']
        ctx = context.current()

        with mock.patch.object(datetime, 'datetime',
                               mock.Mock(wraps=datetime.datetime)) as patched:
            patched.utcnow.return_value = datetime.datetime(2014, 1, 1, 1, 1)
            self.enforcement.check_update(
                ctx, lease, new_lease_values, current_allocations,
                allocation_candidates, reservations, new_reservations)

    def test_check_update_denied(self):
        current_allocations = {'virtual:instance': [get_fake_host('1')]}
        lease = get_fake_lease(end_date=datetime.datetime(2014, 1, 1, 2, 22))
        reservations = list(lease['reservations'])

        new_lease_values = get_fake_lease(
            end_date=datetime.datetime(2014, 1, 1, 2, 24))
        new_reservations = list(new_lease_values['reservations'])
        allocation_candidates = {'virtual:instance': [get_fake_host('2')]}

        del new_lease_values['reservations']
        ctx = context.current()

        with mock.patch.object(datetime, 'datetime',
                               mock.Mock(wraps=datetime.datetime)) as patched:
            patched.utcnow.return_value = datetime.datetime(2014, 1, 1, 1, 1)
            self.assertRaises(exceptions.MaxLeaseDurationException,
                              self.enforcement.check_update, ctx, lease,
                              new_lease_values, current_allocations,
                              allocation_candidates, reservations,
                              new_reservations)

    def test_check_update_active_lease_allowed(self):
        current_allocations = {'virtual:instance': [get_fake_host('1')]}
        lease = get_fake_lease(end_date=datetime.datetime(2014, 1, 1, 1, 53))
        reservations = list(lease['reservations'])

        new_lease_values = get_fake_lease()
        new_reservations = list(new_lease_values['reservations'])
        allocation_candidates = {'virtual:instance': [get_fake_host('2')]}

        del new_lease_values['reservations']
        ctx = context.current()

        with mock.patch.object(datetime, 'datetime',
                               mock.Mock(wraps=datetime.datetime)) as patched:
            patched.utcnow.return_value = datetime.datetime(2014, 1, 1, 1, 50)
            self.enforcement.check_update(
                ctx, lease, new_lease_values, current_allocations,
                allocation_candidates, reservations, new_reservations)

    def test_check_create_exempt(self):
        cfg.CONF.set_override('max_lease_duration_exempt_project_ids', ['222'],
                              group='enforcement')
        allocation_candidates = {'virtual:instance': [get_fake_host('1')]}
        lease_values = get_fake_lease(
            end_date=datetime.datetime(2014, 1, 1, 2, 24))
        reservations = list(lease_values['reservations'])

        del lease_values['reservations']
        ctx = context.current()

        self.enforcement.check_create(ctx, lease_values, reservations,
                                      allocation_candidates)

    def test_check_update_exempt(self):
        cfg.CONF.set_override('max_lease_duration_exempt_project_ids', ['222'],
                              group='enforcement')
        current_allocations = {'virtual:instance': [get_fake_host('1')]}
        lease = get_fake_lease(end_date=datetime.datetime(2014, 1, 1, 2, 22))
        reservations = list(lease['reservations'])

        new_lease_values = get_fake_lease(
            end_date=datetime.datetime(2014, 1, 1, 2, 24))
        new_reservations = list(new_lease_values['reservations'])
        allocation_candidates = {'virtual:instance': [get_fake_host('2')]}

        del new_lease_values['reservations']
        ctx = context.current()

        with mock.patch.object(datetime, 'datetime',
                               mock.Mock(wraps=datetime.datetime)) as patched:
            patched.utcnow.return_value = datetime.datetime(2014, 1, 1, 1, 1)
            self.enforcement.check_update(
                ctx, lease, new_lease_values, current_allocations,
                allocation_candidates, reservations, new_reservations)

    def test_on_end(self):
        allocations = {'virtual:instance': [get_fake_host('1')]}
        lease = get_fake_lease()
        ctx = context.current()

        self.enforcement.on_end(ctx, lease, allocations)
