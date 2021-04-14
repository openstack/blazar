# Copyright (c) 2020 University of Chicago.
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
import ddt

from blazar import context
from blazar import enforcement
from blazar.enforcement import filters
from blazar import exceptions
from blazar.manager import service
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
        'start_date': datetime.datetime.utcnow().strftime(
            service.LEASE_DATE_FORMAT),
        'end_date': (
            datetime.datetime.utcnow() + datetime.timedelta(days=1)).strftime(
                service.LEASE_DATE_FORMAT),
        'user_id': '111',
        'project_id': '222',
        'reservations': [{'resource_id': '1234',
                          'resource_type': 'virtual:instance'}],
        'events': [],
        'before_end_date': '2014-02-01 10:37',
        'action': None,
        'status': None,
        'status_reason': None,
        'trust_id': 'exxee111qwwwwe'}

    if kwargs:
        fake_lease.update(kwargs)

    return fake_lease


def get_lease_rsv_allocs():
    allocation_candidates = {'virtual:instance': [get_fake_host('1')]}
    lease_values = get_fake_lease()
    reservations = list(lease_values['reservations'])

    del lease_values['reservations']

    return lease_values, reservations, allocation_candidates


class FakeFilter(filters.base_filter.BaseFilter):

    enforcement_opts = [
        cfg.IntOpt('fake_opt', default=1, help='This is a fake config.'),
    ]

    def __init__(self, conf=None):
        super(FakeFilter, self).__init__(conf=conf)

    def check_create(self, context, lease_values):
        pass

    def check_update(self, context, current_lease_values, new_lease_values):
        pass

    def on_end(self, context, lease_values):
        pass


@ddt.ddt
class EnforcementTestCase(tests.TestCase):
    def setUp(self):
        super(EnforcementTestCase, self).setUp()

        self.cfg = cfg
        self.region = 'RegionOne'
        filters.FakeFilter = FakeFilter
        filters.all_filters = ['FakeFilter']

        self.enforcement = enforcement.UsageEnforcement()

        cfg.CONF.set_override(
            'enabled_filters', filters.all_filters, group='enforcement')
        cfg.CONF.set_override('os_region_name', self.region)

        self.enforcement.load_filters()
        self.fake_service_catalog = tests.FakeServiceCatalog([
            dict(
                type='identity', endpoints=[
                    dict(
                        interface='internal', region=self.region,
                        url='https://fakeauth.com')
                ]
            )
        ])

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
        self.addCleanup(self.cfg.CONF.clear_override, 'os_region_name')

    def tearDown(self):
        super(EnforcementTestCase, self).tearDown()

    def get_formatted_lease(self, lease_values, rsv, allocs):
        expected_lease = lease_values.copy()

        if rsv:
            expected_lease['reservations'] = rsv
        for res in expected_lease['reservations']:
            res['allocations'] = allocs[res['resource_type']]

        return expected_lease

    def test_load_filters(self):
        self.assertEqual(len(self.enforcement.enabled_filters), 1)

        fake_filter = self.enforcement.enabled_filters.pop()

        self.assertIsInstance(fake_filter, FakeFilter)
        self.assertEqual(fake_filter.conf.enforcement.fake_opt, 1)

    def test_format_context(self):

        formatted_context = self.enforcement.format_context(
            context.current(), get_fake_lease())

        expected = dict(user_id='111', project_id='222',
                        region_name=self.region,
                        auth_url='https://fakeauth.com')

        self.assertDictEqual(expected, formatted_context)

    def test_format_lease(self):
        lease_values, rsv, allocs = get_lease_rsv_allocs()

        formatted_lease = self.enforcement.format_lease(lease_values, rsv,
                                                        allocs)

        expected_lease = self.get_formatted_lease(lease_values, rsv, allocs)

        self.assertDictEqual(expected_lease, formatted_lease)

    def test_check_create(self):
        lease_values, rsv, allocs = get_lease_rsv_allocs()
        ctx = context.current()

        check_create = self.patch(self.enforcement.enabled_filters[0],
                                  'check_create')

        self.enforcement.check_create(ctx, lease_values, rsv, allocs)

        formatted_lease = self.enforcement.format_lease(lease_values, rsv,
                                                        allocs)
        formatted_context = self.enforcement.format_context(ctx, lease_values)

        check_create.assert_called_once_with(formatted_context,
                                             formatted_lease)

        expected_context = dict(user_id='111', project_id='222',
                                region_name=self.region,
                                auth_url='https://fakeauth.com')

        expected_lease = self.get_formatted_lease(lease_values, rsv, allocs)

        self.assertDictEqual(expected_context, formatted_context)
        self.assertDictEqual(expected_lease, formatted_lease)

    def test_check_create_with_exception(self):
        lease_values, rsv, allocs = get_lease_rsv_allocs()
        ctx = context.current()

        check_create = self.patch(self.enforcement.enabled_filters[0],
                                  'check_create')

        check_create.side_effect = exceptions.BlazarException

        self.assertRaises(exceptions.BlazarException,
                          self.enforcement.check_create,
                          context=ctx, lease_values=lease_values,
                          reservations=rsv, allocations=allocs)

    def test_check_update(self):
        lease, rsv, allocs = get_lease_rsv_allocs()

        new_lease_values = get_fake_lease(end_date='2014-02-07 13:37')
        new_reservations = list(new_lease_values['reservations'])
        allocation_candidates = {'virtual:instance': [get_fake_host('2')]}

        del new_lease_values['reservations']
        ctx = context.current()

        check_update = self.patch(self.enforcement.enabled_filters[0],
                                  'check_update')

        self.enforcement.check_update(
            ctx, lease, new_lease_values, allocs, allocation_candidates,
            rsv, new_reservations)

        formatted_context = self.enforcement.format_context(ctx, lease)
        formatted_lease = self.enforcement.format_lease(lease, rsv, allocs)
        new_formatted_lease = self.enforcement.format_lease(
            new_lease_values, new_reservations, allocation_candidates)

        expected_context = dict(user_id='111', project_id='222',
                                region_name=self.region,
                                auth_url='https://fakeauth.com')

        expected_lease = self.get_formatted_lease(lease, rsv, allocs)
        expected_new_lease = self.get_formatted_lease(
            new_lease_values, new_reservations, allocation_candidates)

        check_update.assert_called_once_with(
            formatted_context, formatted_lease, new_formatted_lease)

        self.assertDictEqual(expected_context, formatted_context)
        self.assertDictEqual(expected_lease, formatted_lease)
        self.assertDictEqual(expected_new_lease, new_formatted_lease)

    def test_check_update_with_exception(self):
        lease, rsv, allocs = get_lease_rsv_allocs()

        new_lease_values = get_fake_lease(end_date='2014-02-07 13:37')
        new_reservations = list(new_lease_values['reservations'])
        allocation_candidates = {'virtual:instance': [get_fake_host('2')]}

        del new_lease_values['reservations']
        ctx = context.current()

        check_update = self.patch(self.enforcement.enabled_filters[0],
                                  'check_update')
        check_update.side_effect = exceptions.BlazarException

        self.assertRaises(
            exceptions.BlazarException, self.enforcement.check_update,
            context=ctx, current_lease=lease, new_lease=new_lease_values,
            current_allocations=allocs, new_allocations=allocation_candidates,
            current_reservations=rsv, new_reservations=new_reservations)

    def test_on_end(self):
        allocations = {'virtual:instance': [get_fake_host('1')]}
        lease = get_fake_lease()
        ctx = context.current()

        on_end = self.patch(self.enforcement.enabled_filters[0], 'on_end')

        self.enforcement.on_end(ctx, lease, allocations)

        formatted_context = self.enforcement.format_context(ctx, lease)
        formatted_lease = self.enforcement.format_lease(
            lease, lease['reservations'], allocations)

        on_end.assert_called_once_with(formatted_context, formatted_lease)

        expected_context = dict(user_id='111', project_id='222',
                                region_name=self.region,
                                auth_url='https://fakeauth.com')

        expected_lease = self.get_formatted_lease(lease, None, allocations)

        self.assertDictEqual(expected_context, formatted_context)
        self.assertDictEqual(expected_lease, formatted_lease)
