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

import copy
import datetime
from unittest import mock

import ddt
import eventlet
import importlib
from oslo_config import cfg
import oslo_messaging as messaging
from stevedore import enabled
import testtools

from blazar import context
from blazar.db import api as db_api
from blazar.db import exceptions as db_ex
from blazar import enforcement
from blazar.enforcement import exceptions as enforcement_ex
from blazar import exceptions
from blazar.manager import exceptions as manager_ex
from blazar.manager import service
from blazar.notification import api as notifier_api
from blazar.plugins import base
from blazar.plugins import dummy_vm_plugin
from blazar.plugins.oshosts import host_plugin
from blazar import status
from blazar import tests
from blazar.utils.openstack import base as base_utils
from blazar.utils import trusts


class FakeExtension():
    def __init__(self, name, plugin):
        self.name = name
        self.plugin = plugin


class FakePlugin(base.BasePlugin):
    resource_type = 'fake:plugin'
    title = 'Fake Plugin'
    description = 'This plugin is fake.'

    def get(self, resource_id):
        return None

    def reserve_resource(self, reservation_id, values):
        return None

    def query_allocations(self, resource_id_list, lease_id=None,
                          reservation_id=None):
        return None

    def allocation_candidates(self, lease_values):
        return None

    def list_allocations(self, query, defail=False):
        return None

    def update_reservation(self, reservation_id, values):
        return None

    def on_start(self, resource_id):
        return 'Resource %s should be started this moment.' % resource_id

    def on_end(self, resource_id):
        return 'Resource %s should be deleted this moment.' % resource_id


class FakePluginRaisesException(base.BasePlugin):
    resource_type = 'fake:plugin:raise'
    title = 'Fake Plugin that raise Exception during initialization'
    description = 'This plugin is fake.'

    def __init__(self):
        raise Exception

    def reserve_resource(self, reservation_id, values):
        return None

    def update_reservation(self, reservation_id, values):
        return None

    def on_start(self, resource_id):
        return 'Resource %s should be started this moment.' % resource_id

    def on_end(self, resource_id):
        return 'Resource %s should be deleted this moment.' % resource_id


class FakeLeaseStatus(object):
    @classmethod
    def lease_status(cls, transition, result_in, non_fatal_exceptions=[]):
        def decorator(func):
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            return wrapper
        return decorator


@ddt.ddt
class ServiceTestCase(tests.DBTestCase):
    def setUp(self):
        super(ServiceTestCase, self).setUp()

        self.cfg = cfg
        self.context = context
        self.enabled = enabled
        self.exceptions = exceptions
        self.eventlet = eventlet
        self.datetime = datetime
        self.db_api = db_api
        self.dummy_plugin = dummy_vm_plugin
        self.trusts = trusts
        self.notifier_api = notifier_api
        self.base_utils = base_utils
        self.status = status

        self.fake_plugin = self.patch(self.dummy_plugin, 'DummyVMPlugin')

        self.host_plugin = host_plugin
        self.fake_phys_plugin = self.patch(self.host_plugin,
                                           'PhysicalHostPlugin')

        self.ext_manager = self.patch(self.enabled, 'EnabledExtensionManager')
        self.ext_manager.return_value.extensions = [
            FakeExtension('dummy.vm.plugin', FakePlugin),
            ]
        self.fake_notifier = self.patch(self.notifier_api,
                                        'send_lease_notification')

        cfg.CONF.set_override('plugins', ['dummy.vm.plugin'], group='manager')
        cfg.CONF.set_override(
            'enabled_filters', ['MaxLeaseDurationFilter'],
            group='enforcement')

        with mock.patch('blazar.status.lease.lease_status',
                        FakeLeaseStatus.lease_status):
            importlib.reload(service)
        self.service = service
        self.manager = self.service.ManagerService()
        self.enforcement = self.patch(self.manager, 'enforcement')

        self.lease_id = '11-22-33'
        self.user_id = '123'
        self.project_id = '555'
        self.lease = {'id': self.lease_id,
                      'user_id': self.user_id,
                      'project_id': self.project_id,
                      'events': [
                          {'event_type': 'start_lease',
                           'time': datetime.datetime(2013, 12, 20, 13, 00),
                           'status': 'UNDONE'},
                          {'event_type': 'end_lease',
                           'time': datetime.datetime(2013, 12, 20, 15, 00),
                           'status': 'UNDONE'},
                          {'event_type': 'before_end_lease',
                           'time': datetime.datetime(2013, 12, 20, 13, 00),
                           'status': 'UNDONE'}
                      ],
                      'reservations': [{'id': '111',
                                        'resource_id': '111',
                                        'resource_type': 'virtual:instance',
                                        'status': 'FAKE PROGRESS'}],
                      'status': status.LeaseStatus.PENDING,
                      'start_date': datetime.datetime(2013, 12, 20, 13, 00),
                      'end_date': datetime.datetime(2013, 12, 20, 15, 00),
                      'trust_id': 'exxee111qwwwwe'}
        self.lease_values = {
            'id': self.lease_id,
            'user_id': self.user_id,
            'project_id': self.project_id,
            'name': 'lease-name',
            'reservations': [{'id': '111',
                              'resource_id': '111',
                              'resource_type': 'virtual:instance',
                              'status': 'FAKE PROGRESS'}],
            'start_date': '2026-11-13 13:13',
            'end_date': '2026-12-13 13:13',
            'trust_id': 'exxee111qwwwwe'}

        self.good_date = datetime.datetime.strptime('2012-12-13 13:13',
                                                    '%Y-%m-%d %H:%M')

        self.ctx = self.patch(self.context, 'BlazarContext')
        self.ctx_current = self.patch(context, 'current')
        self.trust_ctx = self.patch(self.trusts, 'create_ctx_from_trust')
        self.trust_create = self.patch(self.trusts, 'create_trust')
        self.patch(enforcement.UsageEnforcement, 'format_context')
        self.lease_get = self.patch(self.db_api, 'lease_get')
        self.lease_get.return_value = self.lease
        self.lease_list = self.patch(self.db_api, 'lease_list')
        self.lease_create = self.patch(self.db_api, 'lease_create')
        self.lease_update = self.patch(self.db_api, 'lease_update')
        self.lease_destroy = self.patch(self.db_api, 'lease_destroy')
        self.reservation_create = self.patch(self.db_api, 'reservation_create')
        self.reservation_update = self.patch(self.db_api, 'reservation_update')
        self.event_create = self.patch(self.db_api, 'event_create')
        self.event_update = self.patch(self.db_api, 'event_update')
        self.manager.plugins = {'virtual:instance': self.fake_plugin}
        self.manager.resource_actions = (
            {'virtual:instance':
             {'on_start': self.fake_plugin.on_start,
              'on_end': self.fake_plugin.on_end}})
        self.patch(
            self.base_utils, 'url_for').return_value = 'http://www.foo.fake'

        self.addCleanup(self.cfg.CONF.clear_override,
                        'minutes_before_end_lease',
                        group='manager')

    def tearDown(self):
        super(ServiceTestCase, self).tearDown()

    def test_start(self):
        # NOTE(starodubcevna): it's useless to test start() now, but may be in
        # future it become useful
        pass

    def test_multiple_plugins_same_resource_type(self):
        config = self.patch(cfg.CONF, "manager")
        config.plugins = ['fake.plugin.1', 'fake.plugin.2']
        self.ext_manager.return_value.extensions = [
            FakeExtension("fake.plugin.1", FakePlugin),
            FakeExtension("fake.plugin.2", FakePlugin)]

        self.assertRaises(manager_ex.PluginConfigurationError,
                          self.manager._get_plugins)

    def test_plugins_that_fail_to_init(self):
        config = self.patch(cfg.CONF, "manager")
        config.plugins = ['fake.plugin.1', 'fake.plugin.2']
        self.ext_manager.return_value.extensions = [
            FakeExtension("fake.plugin.1", FakePlugin),
            FakeExtension("fake.plugin.2", FakePluginRaisesException)]

        plugins = self.manager._get_plugins()
        self.assertIn("fake:plugin", plugins)
        self.assertNotIn("fake:plugin:raise", plugins)

    def test_get_bad_config_plugins(self):
        config = self.patch(cfg.CONF, "manager")
        config.plugins = ['foo.plugin']

        self.assertRaises(exceptions.BlazarException,
                          self.manager._get_plugins)

    def test_setup_actions(self):
        actions = {'virtual:instance':
                   {'on_start': self.fake_plugin.on_start,
                    'on_end': self.fake_plugin.on_end,
                    'before_end': self.fake_plugin.before_end}}
        self.assertEqual(actions, self.manager._setup_actions())

    def test_no_events(self):
        events = self.patch(self.db_api, 'event_get_all_sorted_by_filters')
        event_update = self.patch(self.db_api, 'event_update')
        events.return_value = None

        self.manager._process_events()

        self.assertFalse(event_update.called)

    def test_event_success(self):
        events = self.patch(self.db_api, 'event_get_all_sorted_by_filters')
        event_update = self.patch(self.db_api, 'event_update')
        events.return_value = [{'id': '111-222-333', 'time': self.good_date,
                                'lease_id': 'aaa-bbb-ccc',
                                'event_type': 'start_lease'},
                               {'id': '444-555-666', 'time': self.good_date,
                                'lease_id': 'bbb-ccc-ddd',
                                'event_type': 'start_lease'}]
        self.patch(eventlet, 'spawn')

        self.manager._process_events()

        event_update.assert_has_calls([
            mock.call('111-222-333', {'status': status.event.IN_PROGRESS}),
            mock.call('444-555-666', {'status': status.event.IN_PROGRESS})])

    def test_concurrent_events(self):
        events = self.patch(self.db_api, 'event_get_all_sorted_by_filters')
        self.patch(self.db_api, 'event_update')
        events.return_value = [{'id': '111-222-333', 'time': self.good_date,
                                'lease_id': 'aaa-bbb-ccc',
                                'event_type': 'start_lease'},
                               {'id': '222-333-444', 'time': self.good_date,
                                'lease_id': 'bbb-ccc-ddd',
                                'event_type': 'end_lease'},
                               {'id': '333-444-555', 'time': self.good_date,
                                'lease_id': 'bbb-ccc-ddd',
                                'event_type': 'before_end_lease'},
                               {'id': '444-555-666', 'time': self.good_date,
                                # Same lease as start_lease event above
                                'lease_id': 'aaa-bbb-ccc',
                                'event_type': 'before_end_lease'},
                               {'id': '444-555-666', 'time': self.good_date,
                                # Same lease as start_lease event above
                                'lease_id': 'aaa-bbb-ccc',
                                'event_type': 'end_lease'},
                               {'id': '555-666-777', 'time': self.good_date,
                                'lease_id': 'ccc-ddd-eee',
                                'event_type': 'end_lease'},
                               {'id': '666-777-888',
                                'time': self.good_date + datetime.timedelta(
                                    minutes=1),
                                'lease_id': 'ddd-eee-fff',
                                'event_type': 'end_lease'}]
        events_values = copy.copy(events.return_value)
        _process_events_concurrently = self.patch(
            self.manager, '_process_events_concurrently')

        self.manager._process_events()
        _process_events_concurrently.assert_has_calls([
            # First execute the before_end_lease event which doesn't have a
            # corresponding start_lease
            mock.call([events_values[2]]),
            # Then end_lease events
            mock.call([events_values[1], events_values[5], events_values[6]]),
            # Then the start_lease event
            mock.call([events_values[0]]),
            # Then the before_end_lease which is for the same lease as the
            # previous start_lease event
            mock.call([events_values[3]]),
            # Then the end_lease which is for the same lease as the previous
            # start_lease event
            mock.call([events_values[4]])])

    def test_process_events_concurrently(self):
        events = [{'id': '111-222-333', 'time': self.good_date,
                   'lease_id': 'aaa-bbb-ccc',
                   'event_type': 'start_lease'},
                  {'id': '222-333-444', 'time': self.good_date,
                   'lease_id': 'bbb-ccc-ddd',
                   'event_type': 'start_lease'},
                  {'id': '333-444-555', 'time': self.good_date,
                   'lease_id': 'ccc-ddd-eee',
                   'event_type': 'start_lease'}]
        spawn = self.patch(eventlet, 'spawn')

        self.manager._process_events_concurrently(events)
        spawn.assert_has_calls([
            mock.call(mock.ANY, events[0]),
            mock.call(mock.ANY, events[1]),
            mock.call(mock.ANY, events[2])])

    def test_event_spawn_fail(self):
        events = self.patch(self.db_api, 'event_get_all_sorted_by_filters')
        event_update = self.patch(self.db_api, 'event_update')
        self.patch(eventlet, 'spawn').side_effect = Exception
        events.return_value = [{'id': '111-222-333', 'time': self.good_date,
                                'lease_id': 'aaa-bbb-ccc',
                                'event_type': 'start_lease'}]

        self.manager._process_events()

        event_update.assert_has_calls([
            mock.call('111-222-333', {'status': status.event.IN_PROGRESS}),
            mock.call('111-222-333', {'status': status.event.ERROR})])

    def test_event_pass(self):
        events = self.patch(self.db_api, 'event_get_all_sorted_by_filters')
        events.return_value = [{'id': '111-222-333',
                                'lease_id': self.lease_id,
                                'event_type': 'start_lease',
                                'time': self.good_date}]

        self.lease_get = self.patch(self.db_api, 'lease_get')
        lease = self.lease.copy()
        lease.update({'status': status.LeaseStatus.CREATING})
        self.lease_get.return_value = lease

        event_update = self.patch(self.db_api, 'event_update')

        self.manager._process_events()

        event_update.assert_not_called()

    def test_exec_event_success(self):
        event = {'id': '111-222-333',
                 'event_type': 'start_lease',
                 'lease_id': self.lease_id}
        start_lease = self.patch(self.manager, 'start_lease')

        self.manager._exec_event(event)

        start_lease.assert_called_once_with(lease_id=event['lease_id'],
                                            event_id=event['id'])
        self.lease_get.assert_called_once_with(event['lease_id'])
        expected_context = self.trust_ctx.return_value
        self.fake_notifier.assert_called_once_with(
            expected_context.__enter__.return_value,
            notifier_api.format_lease_payload(self.lease),
            'lease.event.start_lease')

    def test_exec_event_invalid_event_type(self):
        event = {'id': '111-222-333',
                 'event_type': 'invalid',
                 'lease_id': self.lease_id}

        self.assertRaises(manager_ex.EventError,
                          self.manager._exec_event,
                          event)

    def test_exec_event_retry(self):
        event = {'id': '111-222-333',
                 'event_type': 'start_lease',
                 'lease_id': self.lease_id,
                 'time': self.good_date}
        start_lease = self.patch(self.manager, 'start_lease')
        start_lease.side_effect = exceptions.InvalidStatus
        event_update = self.patch(self.db_api, 'event_update')

        with mock.patch.object(datetime, 'datetime',
                               mock.Mock(wraps=datetime.datetime)) as patched:
            patched.utcnow.return_value = (self.good_date
                                           + datetime.timedelta(seconds=1))
            self.manager._exec_event(event)

        start_lease.assert_called_once_with(lease_id=event['lease_id'],
                                            event_id=event['id'])
        event_update.assert_called_once_with(
            event['id'], {'status': status.event.UNDONE})
        self.lease_get.assert_not_called()

    def test_exec_event_no_more_retry(self):
        event = {'id': '111-222-333',
                 'event_type': 'start_lease',
                 'lease_id': self.lease_id,
                 'time': self.good_date}
        start_lease = self.patch(self.manager, 'start_lease')
        start_lease.side_effect = exceptions.InvalidStatus
        event_update = self.patch(self.db_api, 'event_update')

        with mock.patch.object(datetime, 'datetime',
                               mock.Mock(wraps=datetime.datetime)) as patched:
            patched.utcnow.return_value = (self.good_date
                                           + datetime.timedelta(days=1))
            self.manager._exec_event(event)

        start_lease.assert_called_once_with(lease_id=event['lease_id'],
                                            event_id=event['id'])
        event_update.assert_called_once_with(
            event['id'], {'status': status.event.ERROR})
        self.lease_get.assert_not_called()

    def test_exec_event_handle_exception(self):
        event = {'id': '111-222-333',
                 'event_type': 'start_lease',
                 'lease_id': self.lease_id,
                 'time': self.good_date}
        start_lease = self.patch(self.manager, 'start_lease')
        start_lease.side_effect = Exception
        event_update = self.patch(self.db_api, 'event_update')

        self.manager._exec_event(event)

        start_lease.assert_called_once_with(lease_id=event['lease_id'],
                                            event_id=event['id'])
        event_update.assert_called_once_with(
            event['id'], {'status': status.event.ERROR})
        self.lease_get.assert_not_called()

    def test_get_lease(self):
        lease = self.manager.get_lease(self.lease_id)

        self.lease_get.assert_called_once_with('11-22-33')
        self.assertEqual(lease, self.lease)

    @testtools.skip('incorrect decorator')
    def test_list_leases(self):
        # NOTE(starodubcevna): This func works incorrect, and we need to skip
        # it. It'll be fix in coming soon patches
        self.manager.list_leases()

        self.lease_list.assert_called_once_with()

    def test_create_lease_now(self):
        lease_values = self.lease_values
        resources = {
            "CUSTOM_FAKE": 3, "VCPU": 1
        }
        self.fake_plugin.get_enforcement_resources.return_value = resources

        lease = self.manager.create_lease(lease_values)

        self.enforcement.check_create.assert_called_once_with(
            self.context.current(), lease_values, mock.ANY, mock.ANY,
            resources
        )
        self.trust_ctx.assert_called_once_with(lease_values['trust_id'])
        self.lease_create.assert_called_once_with(lease_values)
        self.assertEqual(lease, self.lease)
        expected_context = self.trust_ctx.return_value

        self.fake_notifier.assert_called_once_with(
            expected_context.__enter__.return_value,
            notifier_api.format_lease_payload(lease),
            'lease.create')

    def test_create_lease_some_time(self):
        lease_values = self.lease_values.copy()
        self.lease['start_date'] = '2026-11-13 13:13'

        lease = self.manager.create_lease(lease_values)

        self.trust_ctx.assert_called_once_with(lease_values['trust_id'])
        self.lease_create.assert_called_once_with(lease_values)
        self.assertEqual(lease, self.lease)

    def test_create_lease_validate_created_events(self):
        lease_values = self.lease_values.copy()
        self.lease['start_date'] = '2026-11-13 13:13:00'
        self.lease['end_date'] = '2026-12-13 13:13:00'
        self.lease['events'][0]['time'] = '2026-11-13 13:13:00'
        self.lease['events'][1]['time'] = '2026-12-13 13:13:00'
        self.lease['events'][2]['time'] = '2026-12-13 12:13:00'

        lease = self.manager.create_lease(lease_values)

        self.lease_create.assert_called_once_with(lease_values)
        self.assertEqual(lease, self.lease)
        self.assertEqual(3, len(lease['events']))

        # start lease event
        event = lease['events'][0]
        self.assertEqual('start_lease', event['event_type'])
        self.assertEqual(lease['start_date'], event['time'])
        self.assertEqual('UNDONE', event['status'])

        # end lease event
        event = lease['events'][1]
        self.assertEqual('end_lease', event['event_type'])
        self.assertEqual(lease['end_date'], event['time'])
        self.assertEqual('UNDONE', event['status'])

        # before end lease event
        event = lease['events'][2]
        self.assertEqual('before_end_lease', event['event_type'])
        delta = datetime.timedelta(
            minutes=self.cfg.CONF.manager.minutes_before_end_lease)
        self.assertEqual(str(lease_values['end_date'] - delta),
                         event['time'])
        self.assertEqual('UNDONE', event['status'])

    def test_create_lease_before_end_event_is_before_lease_start(self):
        lease_values = self.lease_values.copy()
        self.lease['start_date'] = '2026-11-13 13:13:00'
        self.lease['end_date'] = '2026-12-13 13:13:00'
        self.lease['events'][0]['time'] = '2026-11-13 13:13:00'
        self.lease['events'][1]['time'] = '2026-12-13 13:13:00'
        self.lease['events'][2]['time'] = '2026-11-13 13:13:00'

        self.cfg.CONF.set_override('minutes_before_end_lease', 120,
                                   group='manager')

        lease = self.manager.create_lease(lease_values)

        self.lease_create.assert_called_once_with(lease_values)
        self.assertEqual(lease, self.lease)
        self.assertEqual(3, len(lease['events']))

        # start lease event
        event = lease['events'][0]
        self.assertEqual('start_lease', event['event_type'])
        self.assertEqual(lease['start_date'], event['time'])
        self.assertEqual('UNDONE', event['status'])

        # end lease event
        event = lease['events'][1]
        self.assertEqual('end_lease', event['event_type'])
        self.assertEqual(lease['end_date'], event['time'])
        self.assertEqual('UNDONE', event['status'])

        # before end lease event
        event = lease['events'][2]
        self.assertEqual('before_end_lease', event['event_type'])
        self.assertEqual(lease['start_date'], event['time'])
        self.assertEqual('UNDONE', event['status'])

    def test_create_lease_before_end_event_before_start_without_lease_id(self):
        lease_values = self.lease_values.copy()

        self.lease['start_date'] = '2026-11-13 13:13'

        self.cfg.CONF.set_override('minutes_before_end_lease', 120,
                                   group='manager')

        lease = self.manager.create_lease(lease_values)

        self.lease_create.assert_called_once_with(lease_values)
        self.assertEqual(lease, self.lease)
        self.assertEqual(3, len(lease['events']))

    def test_create_lease_before_end_param_is_before_lease_start(self):
        lease_values = self.lease_values.copy()
        lease_values['before_end_date'] = '2026-11-11 13:13'
        lease_values['start_date'] = '2026-11-13 13:13'

        self.lease['start_date'] = '2026-11-13 13:13'

        self.assertRaises(
            exceptions.NotAuthorized, self.manager.create_lease, lease_values)

    def test_create_lease_before_end_param_is_past_lease_ending(self):
        lease_values = self.lease_values.copy()
        lease_values['start_date'] = '2026-11-13 13:13'
        lease_values['end_date'] = '2026-11-14 13:13'
        lease_values['before_end_date'] = '2026-11-15 13:13'
        self.lease['start_date'] = '2026-11-13 13:13'

        self.assertRaises(
            exceptions.NotAuthorized, self.manager.create_lease, lease_values)

    def test_create_lease_no_before_end_event(self):
        lease_values = self.lease_values.copy()
        self.lease['start_date'] = '2026-11-13 13:13:00'
        self.lease['end_date'] = '2026-11-14 13:13:00'
        self.lease['events'][0]['time'] = '2026-11-13 13:13:00'
        self.lease['events'][1]['time'] = '2026-11-14 13:13:00'
        self.lease['events'].pop()

        self.cfg.CONF.set_override('minutes_before_end_lease', 0,
                                   group='manager')

        lease = self.manager.create_lease(lease_values)

        self.lease_create.assert_called_once_with(lease_values)
        self.assertEqual(lease, self.lease)
        self.assertEqual(2, len(lease['events']))

        # start lease event
        event = lease['events'][0]
        self.assertEqual('start_lease', event['event_type'])
        self.assertEqual(lease['start_date'], event['time'])
        self.assertEqual('UNDONE', event['status'])

        # end lease event
        event = lease['events'][1]
        self.assertEqual('end_lease', event['event_type'])
        self.assertEqual(lease['end_date'], event['time'])
        self.assertEqual('UNDONE', event['status'])

    def test_create_lease_with_before_end_date_param(self):
        lease_values = self.lease_values.copy()
        lease_values['before_end_date'] = '2026-11-14 10:13'

        self.lease['start_date'] = '2026-11-13 13:13:00'
        self.lease['end_date'] = '2026-11-14 13:13:00'
        self.lease['events'][0]['time'] = '2026-11-13 13:13:00'
        self.lease['events'][1]['time'] = '2026-11-14 13:13:00'
        self.lease['events'][2]['time'] = '2026-11-14 10:13:00'

        lease = self.manager.create_lease(lease_values)

        self.lease_create.assert_called_once_with(lease_values)
        self.assertEqual(lease, self.lease)
        self.assertEqual(3, len(lease['events']))

        # start lease event
        event = lease['events'][0]
        self.assertEqual('start_lease', event['event_type'])
        self.assertEqual(lease['start_date'], event['time'])
        self.assertEqual('UNDONE', event['status'])

        # end lease event
        event = lease['events'][1]
        self.assertEqual('end_lease', event['event_type'])
        self.assertEqual(lease['end_date'], event['time'])
        self.assertEqual('UNDONE', event['status'])

        # before end lease event
        event = lease['events'][2]
        self.assertEqual('before_end_lease', event['event_type'])
        expected_before_end_time = datetime.datetime.strptime(
            lease_values['before_end_date'], service.LEASE_DATE_FORMAT)
        self.assertEqual(str(expected_before_end_time), event['time'])
        self.assertEqual('UNDONE', event['status'])

    def test_create_lease_wrong_date(self):
        lease_values = self.lease_values.copy()
        lease_values['start_date'] = '2025-13-35 13:13'
        lease_values['end_date'] = '2025-12-31 13:13'

        self.assertRaises(
            manager_ex.InvalidDate, self.manager.create_lease, lease_values)

    def test_create_lease_wrong_format_before_end_date(self):
        lease_values = self.lease_values.copy()
        lease_values['before_end_date'] = '2026-14 10:13'

        self.assertRaises(
            manager_ex.InvalidDate, self.manager.create_lease, lease_values)

    def test_create_lease_start_date_in_past(self):
        lease_values = self.lease_values.copy()
        lease_values['start_date'] = datetime.datetime.strftime(
            datetime.datetime.utcnow() - datetime.timedelta(days=1),
            service.LEASE_DATE_FORMAT)

        self.assertRaises(
            exceptions.InvalidInput, self.manager.create_lease, lease_values)

    def test_create_lease_end_before_start(self):
        lease_values = self.lease_values.copy()
        lease_values['start_date'] = '2026-11-13 13:13'
        lease_values['end_date'] = '2026-11-13 12:13'

        self.assertRaises(
            exceptions.InvalidInput, self.manager.create_lease, lease_values)

    def test_create_lease_unsupported_resource_type(self):
        lease_values = self.lease_values.copy()
        lease_values['reservations'] = [{'id': '111',
                                         'resource_id': '111',
                                         'resource_type': 'unsupported:type',
                                         'status': 'FAKE PROGRESS'}]

        self.assertRaises(manager_ex.UnsupportedResourceType,
                          self.manager.create_lease, lease_values)

    def test_create_lease_duplicated_name(self):
        lease_values = self.lease_values.copy()
        lease_values['name'] = 'duplicated_name'

        self.patch(self.db_api,
                   'lease_create').side_effect = db_ex.BlazarDBDuplicateEntry
        self.assertRaises(manager_ex.LeaseNameAlreadyExists,
                          self.manager.create_lease, lease_values)

    def test_create_lease_without_trust_id(self):
        lease_values = self.lease_values.copy()
        del lease_values['trust_id']

        self.assertRaises(manager_ex.MissingTrustId,
                          self.manager.create_lease, lease_values)

    def test_create_lease_without_required_params(self):
        name_missing_values = {
            'start_date': '2026-11-13 13:13',
            'end_date': '2026-12-13 13:13',
            'trust_id': 'trust1'}
        start_missing_values = {
            'name': 'name',
            'end_date': '2026-12-13 13:13',
            'trust_id': 'trust1'}
        end_missing_values = {
            'name': 'name',
            'start_date': '2026-11-13 13:13',
            'trust_id': 'trust1'}
        resource_type_missing_value = {
            'name': 'name',
            'start_date': '2026-11-13 13:13',
            'end_date': '2026-12-13 13:13',
            'reservations': [{'min': 1, 'max': 3}],
            'trust_id': 'trust1'
            }

        for value in [name_missing_values, start_missing_values,
                      end_missing_values, resource_type_missing_value]:
            self.assertRaises(manager_ex.MissingParameter,
                              self.manager.create_lease, value)

    def test_create_lease_with_filter_exception(self):
        lease_values = self.lease_values.copy()

        self.enforcement.check_create.side_effect = (
            enforcement_ex.MaxLeaseDurationException(lease_duration=200,
                                                     max_duration=100))

        self.assertRaises(exceptions.NotAuthorized,
                          self.manager.create_lease,
                          lease_values=lease_values)
        self.lease_create.assert_not_called()

    def test_update_lease_completed_lease_rename(self):
        lease_values = {'name': 'renamed'}
        target = datetime.datetime(2015, 1, 1)
        with mock.patch.object(datetime,
                               'datetime',
                               mock.Mock(wraps=datetime.datetime)) as patched:
            patched.utcnow.return_value = target
            lease = self.manager.update_lease(lease_id=self.lease_id,
                                              values=lease_values)
        self.lease_update.assert_called_once_with(self.lease_id, lease_values)
        self.assertEqual(lease, self.lease)

    def test_update_lease_not_started_modify_dates(self):
        def fake_event_get(sort_key, sort_dir, filters):
            if filters['event_type'] == 'start_lease':
                return {'id': '2eeb784a-2d84-4a89-a201-9d42d61eecb1'}
            elif filters['event_type'] == 'end_lease':
                return {'id': '7085381b-45e0-4e5d-b24a-f965f5e6e5d7'}
            elif filters['event_type'] == 'before_end_lease':
                delta = datetime.timedelta(hours=1)
                return {'id': '452bf850-e223-4035-9d13-eb0b0197228f',
                        'time': self.lease['end_date'] - delta,
                        'status': 'UNDONE'}

        lease_values = {
            'name': 'renamed',
            'start_date': '2015-12-01 20:00',
            'end_date': '2015-12-01 22:00'
        }
        reservation_get_all = (
            self.patch(self.db_api, 'reservation_get_all_by_lease_id'))
        reservation_get_all.return_value = [
            {
                'id': '593e7028-c0d1-4d76-8642-2ffd890b324c',
                'resource_type': 'virtual:instance',
            }
        ]
        event_get = self.patch(db_api, 'event_get_first_sorted_by_filters')
        event_get.side_effect = fake_event_get
        target = datetime.datetime(2013, 12, 15)
        with mock.patch.object(datetime,
                               'datetime',
                               mock.Mock(wraps=datetime.datetime)) as patched:
            patched.utcnow.return_value = target
            self.manager.update_lease(lease_id=self.lease_id,
                                      values=lease_values)
        self.fake_plugin.update_reservation.assert_called_with(
            '593e7028-c0d1-4d76-8642-2ffd890b324c',
            {
                'start_date': datetime.datetime(2015, 12, 1, 20, 00),
                'end_date': datetime.datetime(2015, 12, 1, 22, 00)
            }
        )
        calls = [mock.call('2eeb784a-2d84-4a89-a201-9d42d61eecb1',
                           {'time': datetime.datetime(2015, 12, 1, 20, 00)}),
                 mock.call('7085381b-45e0-4e5d-b24a-f965f5e6e5d7',
                           {'time': datetime.datetime(2015, 12, 1, 22, 00)}),
                 mock.call('452bf850-e223-4035-9d13-eb0b0197228f',
                           {'time': datetime.datetime(2015, 12, 1, 21, 00)})
                 ]
        self.event_update.assert_has_calls(calls)
        self.lease_update.assert_called_once_with(self.lease_id, lease_values)

    def test_update_modify_reservations(self):
        def fake_event_get(sort_key, sort_dir, filters):
            if filters['event_type'] == 'start_lease':
                return {'id': '2eeb784a-2d84-4a89-a201-9d42d61eecb1'}
            elif filters['event_type'] == 'end_lease':
                return {'id': '7085381b-45e0-4e5d-b24a-f965f5e6e5d7'}
            elif filters['event_type'] == 'before_end_lease':
                delta = datetime.timedelta(hours=1)
                return {'id': '452bf850-e223-4035-9d13-eb0b0197228f',
                        'time': self.lease['end_date'] - delta,
                        'status': 'UNDONE'}

        lease_values = {
            'reservations': [
                {
                    'id': '593e7028-c0d1-4d76-8642-2ffd890b324c',
                    'min': 3,
                    'max': 3,
                    'resource_type': 'virtual:instance'
                }
            ]
        }
        reservation_get_all = (
            self.patch(self.db_api, 'reservation_get_all_by_lease_id'))
        reservation_get_all.return_value = [
            {
                'id': '593e7028-c0d1-4d76-8642-2ffd890b324c',
                'resource_type': 'virtual:instance',
            }
        ]
        event_get = self.patch(db_api, 'event_get_first_sorted_by_filters')
        event_get.side_effect = fake_event_get
        target = datetime.datetime(2013, 12, 15)
        with mock.patch.object(datetime,
                               'datetime',
                               mock.Mock(wraps=datetime.datetime)) as patched:
            patched.utcnow.return_value = target
            self.manager.update_lease(lease_id=self.lease_id,
                                      values=lease_values)
        self.fake_plugin.update_reservation.assert_called_with(
            '593e7028-c0d1-4d76-8642-2ffd890b324c',
            {
                'start_date': datetime.datetime(2013, 12, 20, 13, 00),
                'end_date': datetime.datetime(2013, 12, 20, 15, 00),
                'id': '593e7028-c0d1-4d76-8642-2ffd890b324c',
                'min': 3,
                'max': 3,
                'resource_type': 'virtual:instance'
            }
        )
        calls = [mock.call('2eeb784a-2d84-4a89-a201-9d42d61eecb1',
                           {'time': datetime.datetime(2013, 12, 20, 13, 00)}),
                 mock.call('7085381b-45e0-4e5d-b24a-f965f5e6e5d7',
                           {'time': datetime.datetime(2013, 12, 20, 15, 00)}),
                 mock.call('452bf850-e223-4035-9d13-eb0b0197228f',
                           {'time': datetime.datetime(2013, 12, 20, 14, 00)})
                 ]
        self.event_update.assert_has_calls(calls)
        self.lease_update.assert_called_once_with(self.lease_id, lease_values)

    def test_update_modify_reservations_with_invalid_param(self):
        lease_values = {
            'reservations': [
                {
                    'id': '593e7028-c0d1-4d76-8642-2ffd890b324c',
                    'resource_type': 'invalid',
                    'min': 3,
                    'max': 3
                }
            ]
        }
        reservation_get_all = (
            self.patch(self.db_api, 'reservation_get_all_by_lease_id'))
        reservation_get_all.return_value = [
            {
                'id': '593e7028-c0d1-4d76-8642-2ffd890b324c',
                'resource_type': 'virtual:instance',
            }
        ]
        target = datetime.datetime(2013, 12, 15)
        with mock.patch.object(datetime,
                               'datetime',
                               mock.Mock(wraps=datetime.datetime)) as patched:
            patched.utcnow.return_value = target
            self.assertRaises(
                manager_ex.CantUpdateParameter, self.manager.update_lease,
                lease_id=self.lease_id, values=lease_values)

    def test_update_modify_reservations_without_reservation_id(self):
        lease_values = {
            'reservations': [
                {
                    'max': 3
                }
            ]
        }
        reservation_get_all = (
            self.patch(self.db_api, 'reservation_get_all_by_lease_id'))
        reservation_get_all.return_value = [
            {
                'id': '593e7028-c0d1-4d76-8642-2ffd890b324c',
                'resource_type': 'virtual:instance',
            }
        ]
        target = datetime.datetime(2013, 12, 15)
        with mock.patch.object(datetime,
                               'datetime',
                               mock.Mock(wraps=datetime.datetime)) as patched:
            patched.utcnow.return_value = target
            self.assertRaises(
                manager_ex.MissingParameter, self.manager.update_lease,
                lease_id=self.lease_id, values=lease_values)

    @ddt.data('', None, '1234', '7085381b-45e0-4e5d-b24a-f965f5e6e5d7')
    def test_update_reservations_with_invalid_reservation_id(self,
                                                             reservation_id):
        lease_values = {
            'reservations': [
                {
                    'disk_gb': 30,
                    'id': reservation_id,
                }
            ]
        }
        reservation_get_all = (
            self.patch(self.db_api, 'reservation_get_all_by_lease_id'))
        reservation_get_all.return_value = [
            {
                'id': '593e7028-c0d1-4d76-8642-2ffd890b324c',
                'resource_type': 'virtual:instance',
            },
            {
                'id': '2eeb784a-2d84-4a89-a201-9d42d61eecb1',
                'resource_type': 'virtual:instance',
            }
        ]
        target = datetime.datetime(2013, 12, 15)
        with mock.patch.object(datetime,
                               'datetime',
                               mock.Mock(wraps=datetime.datetime)) as patched:
            patched.utcnow.return_value = target
        self.assertRaises(
            exceptions.InvalidInput, self.manager.update_lease,
            lease_id=self.lease_id, values=lease_values)

    def test_update_lease_started_modify_end_date_without_before_end(self):
        def fake_event_get(sort_key, sort_dir, filters):
            if filters['event_type'] == 'start_lease':
                return {'id': '2eeb784a-2d84-4a89-a201-9d42d61eecb1'}
            elif filters['event_type'] == 'end_lease':
                return {'id': '7085381b-45e0-4e5d-b24a-f965f5e6e5d7'}
            else:
                return None

        lease_values = {
            'name': 'renamed',
            'end_date': '2013-12-20 16:00'
        }
        reservation_get_all = (
            self.patch(self.db_api, 'reservation_get_all_by_lease_id'))
        reservation_get_all.return_value = [
            {
                'id': '593e7028-c0d1-4d76-8642-2ffd890b324c',
                'resource_type': 'virtual:instance',
                'start_date': datetime.datetime(2013, 12, 20, 13, 00),
                'end_date': datetime.datetime(2013, 12, 20, 15, 00)
            }
        ]
        event_get = self.patch(db_api, 'event_get_first_sorted_by_filters')
        event_get.side_effect = fake_event_get
        target = datetime.datetime(2013, 12, 20, 14, 00)
        with mock.patch.object(datetime,
                               'datetime',
                               mock.Mock(wraps=datetime.datetime)) as patched:
            patched.utcnow.return_value = target
            self.manager.update_lease(lease_id=self.lease_id,
                                      values=lease_values)
        self.fake_plugin.update_reservation.assert_called_with(
            '593e7028-c0d1-4d76-8642-2ffd890b324c',
            {
                'start_date': datetime.datetime(2013, 12, 20, 13, 00),
                'end_date': datetime.datetime(2013, 12, 20, 16, 00)
            }
        )
        calls = [mock.call('2eeb784a-2d84-4a89-a201-9d42d61eecb1',
                           {'time': datetime.datetime(2013, 12, 20, 13, 00)}),
                 mock.call('7085381b-45e0-4e5d-b24a-f965f5e6e5d7',
                           {'time': datetime.datetime(2013, 12, 20, 16, 00)})
                 ]
        self.event_update.assert_has_calls(calls)
        self.lease_update.assert_called_once_with(self.lease_id, lease_values)

    def test_update_lease_started_modify_end_date_and_before_end(self):
        def fake_event_get(sort_key, sort_dir, filters):
            if filters['event_type'] == 'start_lease':
                return {'id': '2eeb784a-2d84-4a89-a201-9d42d61eecb1'}
            elif filters['event_type'] == 'end_lease':
                return {'id': '7085381b-45e0-4e5d-b24a-f965f5e6e5d7'}
            elif filters['event_type'] == 'before_end_lease':
                delta = datetime.timedelta(hours=1)
                return {'id': '452bf850-e223-4035-9d13-eb0b0197228f',
                        'time': self.lease['end_date'] - delta,
                        'status': 'DONE'}

        lease_values = {
            'name': 'renamed',
            'end_date': '2013-12-20 16:00'
        }
        reservation_get_all = (
            self.patch(self.db_api, 'reservation_get_all_by_lease_id'))
        reservation_get_all.return_value = [
            {
                'id': '593e7028-c0d1-4d76-8642-2ffd890b324c',
                'resource_type': 'virtual:instance',
                'start_date': datetime.datetime(2013, 12, 20, 13, 00),
                'end_date': datetime.datetime(2013, 12, 20, 15, 00)
            }
        ]
        event_get = self.patch(db_api, 'event_get_first_sorted_by_filters')
        event_get.side_effect = fake_event_get
        target = datetime.datetime(2013, 12, 20, 14, 00)
        with mock.patch.object(datetime,
                               'datetime',
                               mock.Mock(wraps=datetime.datetime)) as patched:
            patched.utcnow.return_value = target
            self.manager.update_lease(lease_id=self.lease_id,
                                      values=lease_values)
        self.fake_plugin.update_reservation.assert_called_with(
            '593e7028-c0d1-4d76-8642-2ffd890b324c',
            {
                'start_date': datetime.datetime(2013, 12, 20, 13, 00),
                'end_date': datetime.datetime(2013, 12, 20, 16, 00)
            }
        )
        expected_context = self.trust_ctx.return_value
        calls = [mock.call(expected_context.__enter__.return_value,
                           notifier_api.format_lease_payload(self.lease),
                           'lease.update'),
                 mock.call(expected_context.__enter__.return_value,
                           notifier_api.format_lease_payload(self.lease),
                           'lease.event.before_end_lease.stop'),
                 ]
        self.fake_notifier.assert_has_calls(calls)

        calls = [mock.call('2eeb784a-2d84-4a89-a201-9d42d61eecb1',
                           {'time': datetime.datetime(2013, 12, 20, 13, 00)}),
                 mock.call('7085381b-45e0-4e5d-b24a-f965f5e6e5d7',
                           {'time': datetime.datetime(2013, 12, 20, 16, 00)}),
                 mock.call('452bf850-e223-4035-9d13-eb0b0197228f',
                           {'time': datetime.datetime(2013, 12, 20, 15, 00),
                            'status': 'UNDONE'})
                 ]
        self.event_update.assert_has_calls(calls)
        self.lease_update.assert_called_once_with(self.lease_id, lease_values)

    def test_update_lease_started_modify_before_end_with_param(self):
        before_end_date = '2013-12-20 14:00'

        def fake_event_get(sort_key, sort_dir, filters):
            if filters['event_type'] == 'start_lease':
                return {'id': '2eeb784a-2d84-4a89-a201-9d42d61eecb1'}
            elif filters['event_type'] == 'end_lease':
                return {'id': '7085381b-45e0-4e5d-b24a-f965f5e6e5d7'}
            elif filters['event_type'] == 'before_end_lease':
                return {'id': '452bf850-e223-4035-9d13-eb0b0197228f',
                        'time': before_end_date,
                        'status': 'DONE'}

        lease_values = {
            'name': 'renamed',
            'end_date': '2013-12-20 16:00',
            'before_end_date': before_end_date
        }
        reservation_get_all = (
            self.patch(self.db_api, 'reservation_get_all_by_lease_id'))
        reservation_get_all.return_value = [
            {
                'id': '593e7028-c0d1-4d76-8642-2ffd890b324c',
                'resource_type': 'virtual:instance',
                'start_date': datetime.datetime(2013, 12, 20, 13, 00),
                'end_date': datetime.datetime(2013, 12, 20, 15, 00)
            }
        ]
        event_get = self.patch(db_api, 'event_get_first_sorted_by_filters')
        event_get.side_effect = fake_event_get
        target = datetime.datetime(2013, 12, 20, 14, 00)
        with mock.patch.object(datetime,
                               'datetime',
                               mock.Mock(wraps=datetime.datetime)) as patched:
            patched.utcnow.return_value = target
            self.manager.update_lease(lease_id=self.lease_id,
                                      values=lease_values)
        self.fake_plugin.update_reservation.assert_called_with(
            '593e7028-c0d1-4d76-8642-2ffd890b324c',
            {
                'start_date': datetime.datetime(2013, 12, 20, 13, 00),
                'end_date': datetime.datetime(2013, 12, 20, 16, 00)
            }
        )
        expected_context = self.trust_ctx.return_value
        calls = [mock.call(expected_context.__enter__.return_value,
                           notifier_api.format_lease_payload(self.lease),
                           'lease.update'),
                 mock.call(expected_context.__enter__.return_value,
                           notifier_api.format_lease_payload(self.lease),
                           'lease.event.before_end_lease.stop'),
                 ]
        self.fake_notifier.assert_has_calls(calls)

        calls = [mock.call('2eeb784a-2d84-4a89-a201-9d42d61eecb1',
                           {'time': datetime.datetime(2013, 12, 20, 13, 00)}),
                 mock.call('7085381b-45e0-4e5d-b24a-f965f5e6e5d7',
                           {'time': datetime.datetime(2013, 12, 20, 16, 00)}),
                 mock.call('452bf850-e223-4035-9d13-eb0b0197228f',
                           {'time': datetime.datetime.strptime(
                               before_end_date,
                               service.LEASE_DATE_FORMAT),
                            'status': 'UNDONE'})
                 ]
        self.event_update.assert_has_calls(calls)
        self.lease_update.assert_called_once_with(self.lease_id, lease_values)

    def test_update_lease_started_before_end_lower_date_than_start(self):
        expected_start_date = datetime.datetime(2013, 12, 20, 13, 00)
        before_end_date = datetime.datetime.strftime(
            (expected_start_date - datetime.timedelta(hours=1)),
            service.LEASE_DATE_FORMAT)

        def fake_event_get(sort_key, sort_dir, filters):
            if filters['event_type'] == 'start_lease':
                return {'id': '2eeb784a-2d84-4a89-a201-9d42d61eecb1'}
            elif filters['event_type'] == 'end_lease':
                return {'id': '7085381b-45e0-4e5d-b24a-f965f5e6e5d7'}
            elif filters['event_type'] == 'before_end_lease':
                return {'id': '452bf850-e223-4035-9d13-eb0b0197228f',
                        'time': before_end_date,
                        'status': 'DONE'}

        lease_values = {
            'name': 'renamed',
            'end_date': '2013-12-20 16:00',
            'before_end_date': before_end_date
        }
        reservation_get_all = (
            self.patch(self.db_api, 'reservation_get_all_by_lease_id'))
        reservation_get_all.return_value = [
            {
                'id': '593e7028-c0d1-4d76-8642-2ffd890b324c',
                'resource_type': 'virtual:instance',
                'start_date': expected_start_date,
                'end_date': datetime.datetime(2013, 12, 20, 15, 00)
            }
        ]
        event_get = self.patch(db_api, 'event_get_first_sorted_by_filters')
        event_get.side_effect = fake_event_get
        target = datetime.datetime(2013, 12, 20, 14, 00)
        with mock.patch.object(datetime,
                               'datetime',
                               mock.Mock(wraps=datetime.datetime)) as patched:
            patched.utcnow.return_value = target
            self.assertRaises(
                exceptions.NotAuthorized, self.manager.update_lease,
                lease_id=self.lease_id, values=lease_values)

    def test_update_lease_started_modify_before_end_with_invalid_date(self):
        # before_end_date is greater than current end_date
        before_end_date = '2013-12-21 14:00'

        def fake_event_get(sort_key, sort_dir, filters):
            if filters['event_type'] == 'start_lease':
                return {'id': '2eeb784a-2d84-4a89-a201-9d42d61eecb1'}
            elif filters['event_type'] == 'end_lease':
                return {'id': '7085381b-45e0-4e5d-b24a-f965f5e6e5d7'}
            elif filters['event_type'] == 'before_end_lease':
                return {'id': '452bf850-e223-4035-9d13-eb0b0197228f',
                        'time': before_end_date,
                        'status': 'DONE'}

        lease_values = {
            'name': 'renamed',
            'end_date': '2013-12-20 16:00',
            'before_end_date': before_end_date
        }
        reservation_get_all = (
            self.patch(self.db_api, 'reservation_get_all_by_lease_id'))
        reservation_get_all.return_value = [
            {
                'id': '593e7028-c0d1-4d76-8642-2ffd890b324c',
                'resource_type': 'virtual:instance',
                'start_date': datetime.datetime(2013, 12, 20, 13, 00),
                'end_date': datetime.datetime(2013, 12, 20, 15, 00)
            }
        ]
        event_get = self.patch(db_api, 'event_get_first_sorted_by_filters')
        event_get.side_effect = fake_event_get
        target = datetime.datetime(2013, 12, 20, 14, 00)
        with mock.patch.object(datetime,
                               'datetime',
                               mock.Mock(wraps=datetime.datetime)) as patched:
            patched.utcnow.return_value = target
            self.assertRaises(
                exceptions.NotAuthorized, self.manager.update_lease,
                lease_id=self.lease_id, values=lease_values)

    def test_update_lease_started_modify_before_end_with_wrong_format(self):
        wrong_before_end_date = '12-21 14:00'

        def fake_event_get(sort_key, sort_dir, filters):
            if filters['event_type'] == 'start_lease':
                return {'id': '2eeb784a-2d84-4a89-a201-9d42d61eecb1'}
            elif filters['event_type'] == 'end_lease':
                return {'id': '7085381b-45e0-4e5d-b24a-f965f5e6e5d7'}
            elif filters['event_type'] == 'before_end_lease':
                return {'id': '452bf850-e223-4035-9d13-eb0b0197228f',
                        'time': wrong_before_end_date,
                        'status': 'DONE'}

        lease_values = {
            'name': 'renamed',
            'end_date': '2013-12-20 16:00',
            'before_end_date': wrong_before_end_date
        }
        reservation_get_all = (
            self.patch(self.db_api, 'reservation_get_all_by_lease_id'))
        reservation_get_all.return_value = [
            {
                'id': '593e7028-c0d1-4d76-8642-2ffd890b324c',
                'resource_type': 'virtual:instance',
                'start_date': datetime.datetime(2013, 12, 20, 13, 00),
                'end_date': datetime.datetime(2013, 12, 20, 15, 00)
            }
        ]
        event_get = self.patch(db_api, 'event_get_first_sorted_by_filters')
        event_get.side_effect = fake_event_get
        target = datetime.datetime(2013, 12, 20, 14, 00)
        with mock.patch.object(datetime,
                               'datetime',
                               mock.Mock(wraps=datetime.datetime)) as patched:
            patched.utcnow.return_value = target
            self.assertRaises(
                manager_ex.InvalidDate, self.manager.update_lease,
                lease_id=self.lease_id, values=lease_values)

    def test_update_lease_is_not_values(self):
        lease_values = {}
        lease = self.manager.update_lease(lease_id=self.lease_id,
                                          values=lease_values)
        self.lease_get.assert_called_once_with(self.lease_id)
        self.assertEqual(lease, self.lease)

    def test_update_lease_started_modify_start_date(self):
        lease_values = {
            'name': 'renamed',
            'start_date': '2013-12-20 16:00'
        }
        target = datetime.datetime(2013, 12, 20, 14, 00)
        with mock.patch.object(datetime,
                               'datetime',
                               mock.Mock(wraps=datetime.datetime)) as patched:
            patched.utcnow.return_value = target
            self.assertRaises(
                exceptions.InvalidInput, self.manager.update_lease,
                lease_id=self.lease_id, values=lease_values)

    def test_update_lease_not_started_start_date_before_current_time(self):
        lease_values = {
            'name': 'renamed',
            'start_date': '2013-12-14 13:00'
        }
        target = datetime.datetime(2013, 12, 15)
        with mock.patch.object(datetime,
                               'datetime',
                               mock.Mock(wraps=datetime.datetime)) as patched:
            patched.utcnow.return_value = target
            self.assertRaises(
                exceptions.InvalidInput, self.manager.update_lease,
                lease_id=self.lease_id, values=lease_values)

    def test_update_lease_end_date_before_current_time(self):
        lease_values = {
            'name': 'renamed',
            'end_date': '2013-12-14 13:00'
        }
        target = datetime.datetime(2013, 12, 15)
        with mock.patch.object(datetime,
                               'datetime',
                               mock.Mock(wraps=datetime.datetime)) as patched:
            patched.utcnow.return_value = target
            self.assertRaises(
                exceptions.InvalidInput, self.manager.update_lease,
                lease_id=self.lease_id, values=lease_values)

    def test_update_lease_completed_modify_dates(self):
        lease_values = {
            'name': 'renamed',
            'end_date': '2013-12-15 20:00'
        }
        target = datetime.datetime(2015, 12, 15)
        with mock.patch.object(datetime,
                               'datetime',
                               mock.Mock(wraps=datetime.datetime)) as patched:
            patched.utcnow.return_value = target
            self.assertRaises(
                exceptions.InvalidInput, self.manager.update_lease,
                lease_id=self.lease_id, values=lease_values)

    def test_update_lease_start_date_event_not_found(self):
        events = self.patch(self.db_api, 'event_get_first_sorted_by_filters')
        events.return_value = None
        lease_values = {
            'name': 'renamed',
            'start_date': '2013-12-15 20:00'
        }
        self.assertRaises(exceptions.BlazarException,
                          self.manager.update_lease,
                          lease_id=self.lease_id, values=lease_values)

    def test_update_lease_end_date_event_not_found(self):
        def fake_event_get(sort_key, sort_dir, filters):
            if filters['event_type'] == 'start_lease':
                return {'id': '2eeb784a-2d84-4a89-a201-9d42d61eecb1'}
            else:
                return None

        events = self.patch(self.db_api, 'event_get_first_sorted_by_filters')
        events.side_effect = fake_event_get
        event_update = self.patch(self.db_api, 'event_update')
        reservation_get_all = (
            self.patch(self.db_api, 'reservation_get_all_by_lease_id'))
        reservation_get_all.return_value = []

        lease_values = {
            'name': 'renamed',
            'end_date': '2013-12-25 20:00'
        }
        target = datetime.datetime(2013, 12, 10)
        with mock.patch.object(datetime,
                               'datetime',
                               mock.Mock(wraps=datetime.datetime)) as patched:
            patched.utcnow.return_value = target
            self.assertRaises(exceptions.BlazarException,
                              self.manager.update_lease,
                              lease_id=self.lease_id, values=lease_values)
        event_update.assert_called_once_with(
            '2eeb784a-2d84-4a89-a201-9d42d61eecb1',
            {'time': datetime.datetime(2013, 12, 20, 13, 0)})

    def test_update_lease_with_filter_exception(self):
        self.enforcement.check_update.side_effect = (
            enforcement_ex.MaxLeaseDurationException(lease_duration=200,
                                                     max_duration=100))

        def fake_event_get(sort_key, sort_dir, filters):
            if filters['event_type'] == 'start_lease':
                return {'id': '2eeb784a-2d84-4a89-a201-9d42d61eecb1'}
            elif filters['event_type'] == 'end_lease':
                return {'id': '7085381b-45e0-4e5d-b24a-f965f5e6e5d7'}
            elif filters['event_type'] == 'before_end_lease':
                delta = datetime.timedelta(hours=1)
                return {'id': '452bf850-e223-4035-9d13-eb0b0197228f',
                        'time': self.lease['end_date'] - delta,
                        'status': 'UNDONE'}

        lease_values = {
            'reservations': [
                {
                    'id': '593e7028-c0d1-4d76-8642-2ffd890b324c',
                    'min': 3,
                    'max': 3,
                    'resource_type': 'virtual:instance'
                }
            ]
        }
        reservation_get_all = (
            self.patch(self.db_api, 'reservation_get_all_by_lease_id'))
        reservation_get_all.return_value = [
            {
                'id': '593e7028-c0d1-4d76-8642-2ffd890b324c',
                'resource_type': 'virtual:instance',
            }
        ]
        event_get = self.patch(db_api, 'event_get_first_sorted_by_filters')
        event_get.side_effect = fake_event_get
        target = datetime.datetime(2013, 12, 15)
        with mock.patch.object(datetime,
                               'datetime',
                               mock.Mock(wraps=datetime.datetime)) as patched:
            patched.utcnow.return_value = target

            self.assertRaises(exceptions.NotAuthorized,
                              self.manager.update_lease,
                              lease_id=self.lease_id, values=lease_values)

        self.lease_update.assert_not_called()

    def test_delete_lease_before_start(self):
        def fake_event_get(sort_key, sort_dir, filters):
            if filters['event_type'] == 'start_lease':
                return {'id': 'fake', 'status': 'UNDONE'}
            elif filters['event_type'] == 'end_lease':
                return {'id': 'fake', 'status': 'UNDONE'}
            else:
                return None

        fake_get_lease = self.patch(self.manager, 'get_lease')
        fake_get_lease.return_value = self.lease
        event_get = self.patch(db_api, 'event_get_first_sorted_by_filters')
        event_get.side_effect = fake_event_get
        enforcement_on_end = self.patch(self.enforcement, 'on_end')

        self.manager.delete_lease(self.lease_id)

        self.trust_ctx.assert_called_once_with(self.lease['trust_id'])
        self.lease_destroy.assert_called_once_with(self.lease_id)
        self.fake_plugin.on_end.assert_called_with('111')
        enforcement_on_end.assert_called_once()

    def test_delete_lease_after_ending(self):
        def fake_event_get(sort_key, sort_dir, filters):
            if filters['event_type'] == 'start_lease':
                return {'id': 'fake', 'status': 'DONE'}
            elif filters['event_type'] == 'end_lease':
                return {'id': 'fake', 'status': 'DONE'}
            else:
                return None

        self.lease['reservations'][0]['status'] = 'deleted'
        fake_get_lease = self.patch(self.manager, 'get_lease')
        fake_get_lease.return_value = self.lease
        event_get = self.patch(db_api, 'event_get_first_sorted_by_filters')
        event_get.side_effect = fake_event_get
        enforcement_on_end = self.patch(self.enforcement, 'on_end')

        self.manager.delete_lease(self.lease_id)

        expected_context = self.trust_ctx.return_value
        self.lease_destroy.assert_called_once_with(self.lease_id)
        self.fake_notifier.assert_called_once_with(
            expected_context.__enter__.return_value,
            self.notifier_api.format_lease_payload(self.lease),
            'lease.delete')
        self.fake_plugin.on_end.assert_not_called()
        enforcement_on_end.assert_not_called()

    def test_delete_lease_after_start(self):
        def fake_event_get(sort_key, sort_dir, filters):
            if filters['event_type'] == 'start_lease':
                return {'id': 'fake', 'status': 'DONE'}
            elif filters['event_type'] == 'end_lease':
                return {'id': 'fake', 'status': 'UNDONE'}
            else:
                return None

        event_get = self.patch(db_api, 'event_get_first_sorted_by_filters')
        event_get.side_effect = fake_event_get
        fake_get_lease = self.patch(self.manager, 'get_lease')
        fake_get_lease.return_value = self.lease
        enforcement_on_end = self.patch(self.enforcement, 'on_end')

        self.manager.delete_lease(self.lease_id)

        self.event_update.assert_called_once_with('fake',
                                                  {'status': 'IN_PROGRESS'})
        self.fake_plugin.on_end.assert_called_with('111')
        self.lease_destroy.assert_called_once_with(self.lease_id)
        enforcement_on_end.assert_called_once()

    def test_delete_lease_after_start_with_error_status(self):
        def fake_event_get(sort_key, sort_dir, filters):
            if filters['event_type'] == 'start_lease':
                return {'id': 'fake', 'status': 'ERROR'}
            elif filters['event_type'] == 'end_lease':
                return {'id': 'fake', 'status': 'UNDONE'}
            else:
                return None

        event_get = self.patch(db_api, 'event_get_first_sorted_by_filters')
        event_get.side_effect = fake_event_get
        fake_get_lease = self.patch(self.manager, 'get_lease')
        fake_get_lease.return_value = self.lease
        enforcement_on_end = self.patch(self.enforcement, 'on_end')

        self.manager.delete_lease(self.lease_id)

        self.event_update.assert_called_once_with('fake',
                                                  {'status': 'IN_PROGRESS'})

        self.fake_plugin.on_end.assert_called_with('111')
        self.lease_destroy.assert_called_once_with(self.lease_id)
        enforcement_on_end.assert_called_once()

    def test_delete_lease_with_filter_exception(self):
        self.enforcement.on_end.side_effect = (
            exceptions.BlazarException)

        def fake_event_get(sort_key, sort_dir, filters):
            if filters['event_type'] == 'start_lease':
                return {'id': 'fake', 'status': 'DONE'}
            elif filters['event_type'] == 'end_lease':
                return {'id': 'fake', 'status': 'UNDONE'}
            else:
                return None

        event_get = self.patch(db_api, 'event_get_first_sorted_by_filters')
        event_get.side_effect = fake_event_get
        fake_get_lease = self.patch(self.manager, 'get_lease')
        fake_get_lease.return_value = self.lease
        enforcement_on_end = self.patch(self.enforcement, 'on_end')

        self.manager.delete_lease(self.lease_id)

        self.event_update.assert_called_once_with('fake',
                                                  {'status': 'IN_PROGRESS'})
        self.fake_plugin.on_end.assert_called_with('111')
        self.lease_destroy.assert_called_once_with(self.lease_id)
        enforcement_on_end.assert_called_once()

    def test_start_lease(self):
        basic_action = self.patch(self.manager, '_basic_action')

        self.manager.start_lease(self.lease_id, '1')

        self.trust_ctx.assert_called_once_with(self.lease['trust_id'])
        basic_action.assert_called_once_with(self.lease_id, '1', 'on_start',
                                             'active')

    def test_end_lease(self):
        basic_action = self.patch(self.manager, '_basic_action')
        enforcement_on_end = self.patch(self.enforcement, 'on_end')

        self.manager.end_lease(self.lease_id, '1')

        self.trust_ctx.assert_called_once_with(self.lease['trust_id'])
        basic_action.assert_called_once_with(self.lease_id, '1', 'on_end',
                                             'deleted')
        enforcement_on_end.assert_called_once()

    def test_before_end_lease(self):
        basic_action = self.patch(self.manager, '_basic_action')
        self.manager.before_end_lease(self.lease_id, '1')
        basic_action.assert_called_once_with(self.lease_id, '1', 'before_end')

    def test_basic_action_no_res_status(self):
        self.patch(self.manager, 'get_lease').return_value = self.lease

        self.manager._basic_action(self.lease_id, '1', 'on_end')

        self.event_update.assert_called_once_with('1', {'status': 'DONE'})

    def test_basic_action_with_res_status(self):
        self.patch(self.manager, 'get_lease').return_value = self.lease
        self.patch(self.status.reservation,
                   'is_valid_transition').return_value = True

        self.manager._basic_action(self.lease_id, '1', 'on_end',
                                   reservation_status='IN_USE')

        self.reservation_update.assert_called_once_with(
            '111', {'status': 'IN_USE'})
        self.event_update.assert_called_once_with('1', {'status': 'DONE'})

    def test_basic_action_raise_exception(self):
        def raiseBlazarException(resource_id):
            raise exceptions.BlazarException(resource_id)

        self.manager.resource_actions = (
            {'virtual:instance':
             {'on_start': self.fake_plugin.on_start,
              'on_end': raiseBlazarException}})
        self.patch(self.status.reservation,
                   'is_valid_transition').return_value = True

        self.patch(self.manager, 'get_lease').return_value = self.lease

        self.manager._basic_action(self.lease_id, '1', 'on_end',
                                   reservation_status='done')

        self.reservation_update.assert_called_once_with(
            '111', {'status': 'error'})
        self.event_update.assert_called_once_with('1', {'status': 'ERROR'})

    def test_basic_action_raise_exception_no_reservation_status(self):
        def raiseBlazarException(resource_id):
            raise exceptions.BlazarException(resource_id)

        self.manager.resource_actions = (
            {'virtual:instance':
             {'on_start': self.fake_plugin.on_start,
              'on_end': raiseBlazarException}})

        self.patch(self.manager, 'get_lease').return_value = self.lease

        self.manager._basic_action(self.lease_id, '1', 'on_end')

        self.reservation_update.assert_called_once_with(
            '111', {'status': 'error'})
        self.event_update.assert_called_once_with('1', {'status': 'ERROR'})

    def test_getattr_with_correct_plugin_and_method(self):
        self.fake_list_computehosts = (
            self.patch(self.fake_phys_plugin, 'list_computehosts'))
        self.fake_list_computehosts.return_value = 'foo'

        self.manager.plugins = {'physical:host': self.fake_phys_plugin}
        self.assertEqual('foo', getattr(self.manager,
                                        'physical:host:list_computehosts')())

    def test_getattr_with_incorrect_method_name(self):
        self.fake_list_computehosts = (
            self.patch(self.fake_phys_plugin, 'list_computehosts'))
        self.fake_list_computehosts.return_value = 'foo'

        self.manager.plugins = {'physical:host': self.fake_phys_plugin}
        self.assertRaises(AttributeError, getattr, self.manager,
                          'simplefakecallwithValueError')

    def test_getattr_with_missing_plugin(self):
        self.fake_list_computehosts = (
            self.patch(self.fake_phys_plugin, 'list_computehosts'))
        self.fake_list_computehosts.return_value = 'foo'

        self.manager.plugins = {'physical:host': self.fake_phys_plugin}
        self.assertRaises(manager_ex.UnsupportedResourceType, getattr,
                          self.manager, 'plugin:not_present:list_computehosts')

    def test_getattr_with_missing_method_in_plugin(self):
        self.fake_list_computehosts = (
            self.patch(self.fake_phys_plugin, 'list_computehosts'))
        self.fake_list_computehosts.return_value = 'foo'

        self.manager.plugins = {'physical:host': None}
        self.assertRaises(AttributeError, getattr, self.manager,
                          'physical:host:method_not_present')

    @mock.patch.object(messaging, 'get_rpc_server')
    def test_rpc_server(self, mock_get_rpc_server):
        server = service.ManagerService()
        server.start()
        for m in server.monitors:
            m.start_monitoring.assert_called_once()
        server.stop()
        server._server.stop.assert_called_once()
        server.wait()
        server._server.wait.assert_called_once()
        self.assertEqual(1, mock_get_rpc_server.call_count)

    def test_update_non_fatal_max_lease_duration_exception(self):
        importlib.reload(service)
        # import service again without mocking the lease_status
        # decorator
        manager = service.ManagerService()
        enforcement_mngr = self.patch(manager, 'enforcement')
        enforcement_mngr.check_update.side_effect = (
            enforcement_ex.MaxLeaseDurationException(lease_duration=200,
                                                     max_duration=100))
        manager.plugins = {'virtual:instance': self.fake_plugin}
        manager.resource_actions = (
            {'virtual:instance':
             {'on_start': self.fake_plugin.on_start,
              'on_end': self.fake_plugin.on_end}})
        events = self.patch(self.db_api, 'event_get_first_sorted_by_filters')
        events.return_value = self.lease['events'][0]
        lease_values = {
            'name': 'renamed',
            'prolong_for': '8d'
        }
        target = datetime.datetime(2013, 12, 14)
        with mock.patch.object(datetime,
                               'datetime',
                               mock.Mock(wraps=datetime.datetime)) as patched:
            patched.utcnow.return_value = target
            self.assertRaises(
                enforcement_ex.MaxLeaseDurationException,
                manager.update_lease,
                lease_id=self.lease_id,
                values=lease_values
            )
            self.lease_update.assert_called_with(
                '11-22-33', {'status': 'PENDING'}
            )

    def test_update_non_fatal_external_service_filter_exception(self):
        importlib.reload(service)
        manager = service.ManagerService()
        enforcement_mngr = self.patch(manager, 'enforcement')
        enforcement_mngr.check_update.side_effect = (
            enforcement.exceptions.ExternalServiceFilterException(
                message="filter exception")
            )
        manager.plugins = {'virtual:instance': self.fake_plugin}
        manager.resource_actions = (
            {'virtual:instance':
             {'on_start': self.fake_plugin.on_start,
              'on_end': self.fake_plugin.on_end}})
        events = self.patch(self.db_api, 'event_get_first_sorted_by_filters')
        events.return_value = self.lease['events'][0]
        lease_values = {
            'name': 'renamed',
            'prolong_for': '8d'
        }
        target = datetime.datetime(2013, 12, 14)
        with mock.patch.object(datetime,
                               'datetime',
                               mock.Mock(wraps=datetime.datetime)) as patched:
            patched.utcnow.return_value = target
            self.assertRaises(
                enforcement.exceptions.ExternalServiceFilterException,
                manager.update_lease,
                lease_id=self.lease_id,
                values=lease_values
            )
            self.lease_update.assert_called_with(
                '11-22-33', {'status': 'PENDING'}
            )

    def test_update_fatal_extra_capability_too_long_exception(self):
        # lease status ERROR when a fatal exception occurs
        importlib.reload(service)
        manager = service.ManagerService()
        enforcement_mngr = self.patch(manager, 'enforcement')
        enforcement_mngr.check_update.side_effect = (
            manager_ex.ExtraCapabilityTooLong()
        )
        manager.plugins = {'virtual:instance': self.fake_plugin}
        manager.resource_actions = (
            {'virtual:instance':
             {'on_start': self.fake_plugin.on_start,
              'on_end': self.fake_plugin.on_end}})
        events = self.patch(self.db_api, 'event_get_first_sorted_by_filters')
        events.return_value = self.lease['events'][0]
        lease_values = {
            'name': 'renamed',
            'prolong_for': '8d'
        }
        target = datetime.datetime(2013, 12, 14)
        with mock.patch.object(datetime,
                               'datetime',
                               mock.Mock(wraps=datetime.datetime)) as patched:
            patched.utcnow.return_value = target
            self.assertRaises(
                manager_ex.ExtraCapabilityTooLong,
                manager.update_lease,
                lease_id=self.lease_id,
                values=lease_values
            )
            self.lease_update.assert_called_with(
                '11-22-33', {'status': 'ERROR'}
            )
