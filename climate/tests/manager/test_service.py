# Copyright (c) 2013 Mirantis Inc.
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
import eventlet
import mock
from oslo.config import cfg
from stevedore import enabled
import testtools

from climate import context
from climate.db import api as db_api
from climate import exceptions
from climate.manager import service
from climate.plugins import dummy_vm_plugin
from climate.plugins import physical_host_plugin
from climate import tests


class ServiceTestCase(tests.TestCase):
    def setUp(self):
        super(ServiceTestCase, self).setUp()

        self.cfg = cfg
        self.context = context
        self.service = service
        self.enabled = enabled
        self.exceptions = exceptions
        self.eventlet = eventlet
        self.datetime = datetime
        self.db_api = db_api
        self.dummy_plugin = dummy_vm_plugin

        self.fake_plugin = self.patch(self.dummy_plugin, 'DummyVMPlugin')

        self.physical_host_plugin = physical_host_plugin
        self.fake_phys_plugin = self.patch(self.physical_host_plugin,
                                           'PhysicalHostPlugin')

        self.manager = self.service.ManagerService('127.0.0.1')

        self.lease_id = '11-22-33'
        self.lease = {'id': self.lease_id,
                      'reservations': [{'id': '111',
                                        'resource_id': '111',
                                        'resource_type': 'virtual:instance',
                                        'status': 'FAKE PROGRESS'}],
                      'start_date': datetime.datetime(2013, 12, 20, 13, 00),
                      'end_date': datetime.datetime(2013, 12, 20, 15, 00)}
        self.good_date = datetime.datetime.strptime('2012-12-13 13:13',
                                                    '%Y-%m-%d %H:%M')
        self.extension = mock.MagicMock()

        self.patch(self.context, 'ClimateContext')
        self.lease_get = self.patch(self.db_api, 'lease_get')
        self.lease_get.return_value = self.lease
        self.lease_list = self.patch(self.db_api, 'lease_list')
        self.lease_create = self.patch(self.db_api, 'lease_create')
        self.lease_update = self.patch(self.db_api, 'lease_update')
        self.lease_destroy = self.patch(self.db_api, 'lease_destroy')
        self.reservation_update = self.patch(self.db_api, 'reservation_update')
        self.event_update = self.patch(self.db_api, 'event_update')
        self.manager.plugins = {'virtual:instance': self.fake_plugin}
        self.manager.resource_actions =\
            {'virtual:instance':
             {'on_start': self.fake_plugin.on_start,
              'on_end': self.fake_plugin.on_end}}
        self.ext_manager = self.patch(self.enabled, 'EnabledExtensionManager')

    def test_start(self):
        #NOTE(starodubcevna): it's useless to test start() now, but may be in
        #future it become useful
        pass

    @testtools.skip('WIP')
    def test_get_plugins_all_okay(self):
        config = self.patch(cfg, "CONF")
        config.manager.plugins = ['dummy.vm.plugin']
        self.extension.obj.resource_type = 'dummy.vm.plugin'
        self.ext_manager.extensions = ['dummy.vm.plugin']

        self.manager._get_plugins()

    def test_setup_actions(self):
        actions = {'virtual:instance':
                   {'on_start': self.fake_plugin.on_start,
                    'on_end': self.fake_plugin.on_end}}
        self.assertEqual(actions, self.manager._setup_actions())

    def test_event_all_okay(self):
        events = self.patch(self.db_api, 'event_get_all_sorted_by_filters')
        event_update = self.patch(self.db_api, 'event_update')
        events.return_value = [{'id': '111-222-333', 'time': self.good_date,
                                'event_type': 'end_lease',
                                'lease_id': self.lease_id}]

        self.manager._event()

        event_update.assert_called_once_with('111-222-333',
                                             {'status': 'IN_PROGRESS'})

    def test_event_wrong_event_status(self):
        events = self.patch(self.db_api, 'event_get_all_sorted_by_filters')
        self.patch(self.db_api, 'event_update')
        events.return_value = [{'id': '111-222-333', 'time': self.good_date,
                                'event_type': 'wrong_type',
                                'lease_id': self.lease_id}]

        self.assertRaises(self.exceptions.ClimateException,
                          self.manager._event)

    def test_event_wrong_eventlet_fail(self):
        events = self.patch(self.db_api, 'event_get_all_sorted_by_filters')
        event_update = self.patch(self.db_api, 'event_update')
        calls = [mock.call('111-222-333', {'status': 'IN_PROGRESS'}),
                 mock.call('111-222-333', {'status': 'ERROR'})]
        self.patch(eventlet, 'spawn_n').side_effect = Exception
        events.return_value = [{'id': '111-222-333', 'time': self.good_date,
                                'event_type': 'end_lease',
                                'lease_id': self.lease_id}]

        self.manager._event()

        event_update.assert_has_calls(calls)

    def test_get_lease(self):
        lease = self.manager.get_lease(self.lease_id)

        self.lease_get.assert_called_once_with('11-22-33')
        self.assertEqual(lease, self.lease)

    @testtools.skip('incorrect decorator')
    def test_list_leases(self):
        #NOTE(starodubcevna): This func works incorrect, and we need to skip
        #it. It'll be fix in coming soon patches
        self.manager.list_leases()

        self.lease_list.assert_called_once_with()

    def test_create_lease_now(self):
        lease_values = {
            'id': self.lease_id,
            'reservations': [{'id': '111',
                              'resource_id': '111',
                              'resource_type': 'virtual:instance',
                              'status': 'FAKE PROGRESS'}],
            'start_date': 'now',
            'end_date': '2026-12-13 13:13'}

        lease = self.manager.create_lease(lease_values)

        self.lease_create.assert_called_once_with(lease_values)
        self.assertEqual(lease, self.lease)

    def test_create_lease_some_time(self):
        lease_values = {
            'id': self.lease_id,
            'reservations': [{'id': '111',
                              'resource_id': '111',
                              'resource_type': 'virtual:instance',
                              'status': 'FAKE PROGRESS'}],
            'start_date': '2026-11-13 13:13',
            'end_date': '2026-12-13 13:13'}
        self.lease['start_date'] = '2026-11-13 13:13'

        lease = self.manager.create_lease(lease_values)

        self.lease_create.assert_called_once_with(lease_values)
        self.assertEqual(lease, self.lease)

    def test_create_lease_wrong_date(self):
        lease_values = {'start_date': '2025-13-35 13:13',
                        'end_date': '2025-12-31 13:13'}

        self.assertRaises(
            ValueError, self.manager.create_lease, lease_values)

    def test_update_lease_is_values(self):
        lease_values = {'end_date': '2025-12-12 13:13'}

        lease = self.manager.update_lease(self.lease_id, lease_values)

        self.lease_update.assert_called_once_with(self.lease_id, lease_values)
        self.assertEqual(lease, self.lease)

    def test_update_lease_is_not_values(self):
        lease_values = None

        lease = self.manager.update_lease(self.lease_id, lease_values)

        self.lease_update.assert_not_called()
        self.assertEqual(lease, self.lease)

    def test_delete_lease_before_starting_date(self):
        self.patch(self.manager, 'get_lease').\
            return_value = self.lease

        target = datetime.datetime(2013, 12, 20, 12, 00)
        with mock.patch.object(datetime,
                               'datetime',
                               mock.Mock(wraps=datetime.datetime)) as patched:
            patched.utcnow.return_value = target
            self.manager.delete_lease(self.lease_id)

        self.lease_destroy.assert_called_once_with(self.lease_id)

    def test_delete_lease_after_ending_date(self):
        self.patch(self.manager, 'get_lease').\
            return_value = self.lease

        target = datetime.datetime(2013, 12, 20, 16, 00)
        with mock.patch.object(datetime,
                               'datetime',
                               mock.Mock(wraps=datetime.datetime)) as patched:
            patched.utcnow.return_value = target
            self.manager.delete_lease(self.lease_id)

        self.lease_destroy.assert_called_once_with(self.lease_id)

    def test_delete_lease_after_starting_date(self):
        self.patch(self.manager, 'get_lease').\
            return_value = self.lease

        target = datetime.datetime(2013, 12, 20, 13, 30)
        with mock.patch.object(datetime,
                               'datetime',
                               mock.Mock(wraps=datetime.datetime)) as patched:
            patched.utcnow.return_value = target

            self.assertRaises(
                exceptions.NotAuthorized,
                self.manager.delete_lease,
                self.lease_id)

    def test_start_lease(self):
        basic_action = self.patch(self.manager, '_basic_action')

        self.manager.start_lease(self.lease_id, '1')

        basic_action.assert_called_once_with(self.lease_id, '1', 'on_start',
                                             'active')

    def test_end_lease(self):
        basic_action = self.patch(self.manager, '_basic_action')

        self.manager.end_lease(self.lease_id, '1')

        basic_action.assert_called_once_with(self.lease_id, '1', 'on_end',
                                             'deleted')

    def test_basic_action_no_res_status(self):
        self.patch(self.manager, 'get_lease').return_value = self.lease

        self.manager._basic_action(self.lease_id, '1', 'on_end')

        self.event_update.assert_called_once_with('1', {'status': 'DONE'})

    def test_basic_action_with_res_status(self):
        self.patch(self.manager, 'get_lease').return_value = self.lease

        self.manager._basic_action(self.lease_id, '1', 'on_end',
                                   reservation_status='IN_USE')

        self.reservation_update.assert_called_once_with(
            '111', {'status': 'IN_USE'})
        self.event_update.assert_called_once_with('1', {'status': 'DONE'})

    def test_getattr_with_correct_plugin_and_method(self):
        self.fake_list_computehosts = \
            self.patch(self.fake_phys_plugin, 'list_computehosts')
        self.fake_list_computehosts.return_value = 'foo'

        self.manager.plugins = {'physical:host': self.fake_phys_plugin}
        self.assertEqual('foo', getattr(self.manager,
                                        'physical:host:list_computehosts')())

    def test_getattr_with_incorrect_method_name(self):
        self.fake_list_computehosts = \
            self.patch(self.fake_phys_plugin, 'list_computehosts')
        self.fake_list_computehosts.return_value = 'foo'

        self.manager.plugins = {'physical:host': self.fake_phys_plugin}
        self.assertRaises(AttributeError, getattr, self.manager,
                          'simplefakecallwithValueError')

    def test_getattr_with_missing_plugin(self):
        self.fake_list_computehosts = \
            self.patch(self.fake_phys_plugin, 'list_computehosts')
        self.fake_list_computehosts.return_value = 'foo'

        self.manager.plugins = {'physical:host': self.fake_phys_plugin}
        self.assertRaises(AttributeError, getattr, self.manager,
                          'plugin:not_present:list_computehosts')

    def test_getattr_with_missing_method_in_plugin(self):
        self.fake_list_computehosts = \
            self.patch(self.fake_phys_plugin, 'list_computehosts')
        self.fake_list_computehosts.return_value = 'foo'

        self.manager.plugins = {'physical:host': None}
        self.assertRaises(AttributeError, getattr, self.manager,
                          'physical:host:method_not_present')
