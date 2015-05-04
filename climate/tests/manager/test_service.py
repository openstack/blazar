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
from oslo_config import cfg
from stevedore import enabled
import testtools

from climate import context
from climate.db import api as db_api
from climate.db import exceptions as db_ex
from climate import exceptions
from climate.manager import exceptions as manager_ex
from climate.manager import service
from climate.notification import api as notifier_api
from climate.plugins import base
from climate.plugins import dummy_vm_plugin
from climate.plugins.oshosts import host_plugin
from climate import tests
from climate.utils.openstack import base as base_utils
from climate.utils import trusts


class FakeExtension():
    def __init__(self, name, plugin):
        self.name = name
        self.plugin = plugin


class FakePlugin(base.BasePlugin):
    resource_type = 'fake:plugin'
    title = 'Fake Plugin'
    description = 'This plugin is fake.'

    def on_start(self, resource_id):
        return 'Resorce %s should be started this moment.' % resource_id

    def on_end(self, resource_id):
        return 'Resource %s should be deleted this moment.' % resource_id


class FakePluginRaisesException(base.BasePlugin):
    resource_type = 'fake:plugin:raise'
    title = 'Fake Plugin that raise Exception during initialization'
    description = 'This plugin is fake.'

    def __init__(self):
        raise Exception

    def on_start(self, resource_id):
        return 'Resorce %s should be started this moment.' % resource_id

    def on_end(self, resource_id):
        return 'Resource %s should be deleted this moment.' % resource_id


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
        self.trusts = trusts
        self.notifier_api = notifier_api
        self.base_utils = base_utils

        self.fake_plugin = self.patch(self.dummy_plugin, 'DummyVMPlugin')

        self.host_plugin = host_plugin
        self.fake_phys_plugin = self.patch(self.host_plugin,
                                           'PhysicalHostPlugin')

        self.ext_manager = self.patch(self.enabled, 'EnabledExtensionManager')
        self.fake_notifier = self.patch(self.notifier_api,
                                        'send_lease_notification')

        self.manager = self.service.ManagerService()

        self.lease_id = '11-22-33'
        self.user_id = '123'
        self.project_id = '555'
        self.lease = {'id': self.lease_id,
                      'user_id': self.user_id,
                      'project_id': self.project_id,
                      'reservations': [{'id': '111',
                                        'resource_id': '111',
                                        'resource_type': 'virtual:instance',
                                        'status': 'FAKE PROGRESS'}],
                      'start_date': datetime.datetime(2013, 12, 20, 13, 00),
                      'end_date': datetime.datetime(2013, 12, 20, 15, 00),
                      'trust_id': 'exxee111qwwwwe'}
        self.good_date = datetime.datetime.strptime('2012-12-13 13:13',
                                                    '%Y-%m-%d %H:%M')

        self.ctx = self.patch(self.context, 'ClimateContext')
        self.trust_ctx = self.patch(self.trusts, 'create_ctx_from_trust')
        self.trust_create = self.patch(self.trusts, 'create_trust')
        self.lease_get = self.patch(self.db_api, 'lease_get')
        self.lease_get.return_value = self.lease
        self.lease_list = self.patch(self.db_api, 'lease_list')
        self.lease_create = self.patch(self.db_api, 'lease_create')
        self.lease_update = self.patch(self.db_api, 'lease_update')
        self.lease_destroy = self.patch(self.db_api, 'lease_destroy')
        self.reservation_update = self.patch(self.db_api, 'reservation_update')
        self.event_update = self.patch(self.db_api, 'event_update')
        self.manager.plugins = {'virtual:instance': self.fake_plugin}
        self.manager.resource_actions = (
            {'virtual:instance':
             {'on_start': self.fake_plugin.on_start,
              'on_end': self.fake_plugin.on_end}})
        self.patch(
            self.base_utils, 'url_for').return_value = 'http://www.foo.fake'

        self.addCleanup(self.cfg.CONF.clear_override,
                        'notify_hours_before_lease_end',
                        group='manager')

    def tearDown(self):
        super(ServiceTestCase, self).tearDown()

    def test_start(self):
        # NOTE(starodubcevna): it's useless to test start() now, but may be in
        # future it become useful
        pass

    def test_multiple_plugins_same_resource_type(self):
        config = self.patch(cfg, "CONF")
        config.manager.plugins = ['fake.plugin.1', 'fake.plugin.2']
        self.ext_manager.return_value.extensions = [
            FakeExtension("fake.plugin.1", FakePlugin),
            FakeExtension("fake.plugin.2", FakePlugin)]

        self.assertRaises(manager_ex.PluginConfigurationError,
                          self.manager._get_plugins)

    def test_plugins_that_fail_to_init(self):
        config = self.patch(cfg, "CONF")
        config.manager.plugins = ['fake.plugin.1', 'fake.plugin.2']
        self.ext_manager.return_value.extensions = [
            FakeExtension("fake.plugin.1", FakePlugin),
            FakeExtension("fake.plugin.2", FakePluginRaisesException)]

        plugins = self.manager._get_plugins()
        self.assertIn("fake:plugin", plugins)
        self.assertNotIn("fake:plugin:raise", plugins)

    def test_get_bad_config_plugins(self):
        config = self.patch(cfg, "CONF")
        config.manager.plugins = ['foo.plugin']

        self.assertEqual({}, self.manager._get_plugins())

    def test_setup_actions(self):
        actions = {'virtual:instance':
                   {'on_start': self.fake_plugin.on_start,
                    'on_end': self.fake_plugin.on_end}}
        self.assertEqual(actions, self.manager._setup_actions())

    def test_no_events(self):
        events = self.patch(self.db_api, 'event_get_first_sorted_by_filters')
        event_update = self.patch(self.db_api, 'event_update')
        events.return_value = None

        self.manager._event()

        self.assertFalse(event_update.called)

    def test_event_all_okay(self):
        events = self.patch(self.db_api, 'event_get_first_sorted_by_filters')
        event_update = self.patch(self.db_api, 'event_update')
        events.return_value = {'id': '111-222-333', 'time': self.good_date,
                               'event_type': 'end_lease',
                               'lease_id': self.lease_id}

        self.manager._event()

        event_update.assert_called_once_with('111-222-333',
                                             {'status': 'IN_PROGRESS'})
        expected_context = self.trust_ctx.return_value
        self.fake_notifier.assert_called_once_with(
            expected_context.__enter__.return_value,
            notifier_api.format_lease_payload(self.lease),
            'lease.event.end_lease')

    def test_event_wrong_event_status(self):
        events = self.patch(self.db_api, 'event_get_first_sorted_by_filters')
        self.patch(self.db_api, 'event_update')
        events.return_value = {'id': '111-222-333', 'time': self.good_date,
                               'event_type': 'wrong_type',
                               'lease_id': self.lease_id}

        self.assertRaises(manager_ex.EventError,
                          self.manager._event)

    def test_event_wrong_eventlet_fail(self):
        events = self.patch(self.db_api, 'event_get_first_sorted_by_filters')
        event_update = self.patch(self.db_api, 'event_update')
        calls = [mock.call('111-222-333', {'status': 'IN_PROGRESS'}),
                 mock.call('111-222-333', {'status': 'ERROR'})]
        self.patch(eventlet, 'spawn_n').side_effect = Exception
        events.return_value = {'id': '111-222-333', 'time': self.good_date,
                               'event_type': 'end_lease',
                               'lease_id': self.lease_id}

        self.manager._event()

        event_update.assert_has_calls(calls)

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
        trust_id = 'exxee111qwwwwe'
        lease_values = {
            'id': self.lease_id,
            'reservations': [{'id': '111',
                              'resource_id': '111',
                              'resource_type': 'virtual:instance',
                              'status': 'FAKE PROGRESS'}],
            'start_date': 'now',
            'end_date': '2026-12-13 13:13',
            'trust_id': trust_id}

        lease = self.manager.create_lease(lease_values)

        self.trust_ctx.assert_called_once_with(trust_id)
        self.lease_create.assert_called_once_with(lease_values)
        self.assertEqual(lease, self.lease)
        expected_context = self.trust_ctx.return_value
        self.fake_notifier.assert_called_once_with(
            expected_context.__enter__.return_value,
            notifier_api.format_lease_payload(lease),
            'lease.create')

    def test_create_lease_some_time(self):
        trust_id = 'exxee111qwwwwe'
        lease_values = {
            'id': self.lease_id,
            'reservations': [{'id': '111',
                              'resource_id': '111',
                              'resource_type': 'virtual:instance',
                              'status': 'FAKE PROGRESS'}],
            'start_date': '2026-11-13 13:13',
            'end_date': '2026-12-13 13:13',
            'trust_id': trust_id}

        self.lease['start_date'] = '2026-11-13 13:13'

        lease = self.manager.create_lease(lease_values)

        self.trust_ctx.assert_called_once_with(trust_id)
        self.lease_create.assert_called_once_with(lease_values)
        self.assertEqual(lease, self.lease)

    def test_create_lease_validate_created_events(self):
        lease_values = {
            'id': self.lease_id,
            'reservations': [{'id': '111',
                              'resource_id': '111',
                              'resource_type': 'virtual:instance',
                              'status': 'FAKE PROGRESS'}],
            'start_date': '2026-11-13 13:13',
            'end_date': '2026-12-13 13:13',
            'trust_id': 'exxee111qwwwwe'}
        self.lease['start_date'] = '2026-11-13 13:13'

        lease = self.manager.create_lease(lease_values)

        self.lease_create.assert_called_once_with(lease_values)
        self.assertEqual(lease, self.lease)
        self.assertEqual(3, len(lease_values['events']))

        # start lease event
        event = lease_values['events'][0]
        self.assertEqual('start_lease', event['event_type'])
        self.assertEqual(lease_values['start_date'], event['time'])
        self.assertEqual('UNDONE', event['status'])

        # end lease event
        event = lease_values['events'][1]
        self.assertEqual('end_lease', event['event_type'])
        self.assertEqual(lease_values['end_date'], event['time'])
        self.assertEqual('UNDONE', event['status'])

        # end lease event
        event = lease_values['events'][2]
        self.assertEqual('before_end_lease', event['event_type'])
        delta = datetime.timedelta(
            hours=self.cfg.CONF.manager.notify_hours_before_lease_end)
        self.assertEqual(lease_values['end_date'] - delta, event['time'])
        self.assertEqual('UNDONE', event['status'])

    def test_create_lease_before_end_event_is_before_lease_start(self):
        lease_values = {
            'id': self.lease_id,
            'reservations': [{'id': '111',
                              'resource_id': '111',
                              'resource_type': 'virtual:instance',
                              'status': 'FAKE PROGRESS'}],
            'start_date': '2026-11-13 13:13',
            'end_date': '2026-11-14 13:13',
            'trust_id': 'exxee111qwwwwe'}
        self.lease['start_date'] = '2026-11-13 13:13'

        self.cfg.CONF.set_override('notify_hours_before_lease_end', 36,
                                   group='manager')

        lease = self.manager.create_lease(lease_values)

        self.lease_create.assert_called_once_with(lease_values)
        self.assertEqual(lease, self.lease)
        self.assertEqual(3, len(lease_values['events']))

        # start lease event
        event = lease_values['events'][0]
        self.assertEqual('start_lease', event['event_type'])
        self.assertEqual(lease_values['start_date'], event['time'])
        self.assertEqual('UNDONE', event['status'])

        # end lease event
        event = lease_values['events'][1]
        self.assertEqual('end_lease', event['event_type'])
        self.assertEqual(lease_values['end_date'], event['time'])
        self.assertEqual('UNDONE', event['status'])

        # end lease event
        event = lease_values['events'][2]
        self.assertEqual('before_end_lease', event['event_type'])
        self.assertEqual(lease_values['start_date'], event['time'])
        self.assertEqual('UNDONE', event['status'])

    def test_create_lease_before_end_event_before_start_without_lease_id(self):
        lease_values = {
            'reservations': [{'id': '111',
                              'resource_id': '111',
                              'resource_type': 'virtual:instance',
                              'status': 'FAKE PROGRESS'}],
            'start_date': '2026-11-13 13:13',
            'end_date': '2026-11-14 13:13',
            'trust_id': 'exxee111qwwwwe'}
        self.lease['start_date'] = '2026-11-13 13:13'

        self.cfg.CONF.set_override('notify_hours_before_lease_end', 36,
                                   group='manager')

        lease = self.manager.create_lease(lease_values)

        self.lease_create.assert_called_once_with(lease_values)
        self.assertEqual(lease, self.lease)
        self.assertEqual(3, len(lease_values['events']))

    def test_create_lease_before_end_param_is_before_lease_start(self):
        before_end_notification = '2026-11-11 13:13'
        start_date = '2026-11-13 13:13'
        lease_values = {
            'id': self.lease_id,
            'reservations': [{'id': '111',
                              'resource_id': '111',
                              'resource_type': 'virtual:instance',
                              'status': 'FAKE PROGRESS'}],
            'start_date': start_date,
            'end_date': '2026-11-14 13:13',
            'trust_id': 'exxee111qwwwwe',
            'before_end_notification': before_end_notification}
        self.lease['start_date'] = '2026-11-13 13:13'

        self.assertRaises(
            exceptions.NotAuthorized, self.manager.create_lease, lease_values)

    def test_create_lease_before_end_param_is_past_lease_ending(self):
        before_end_notification = '2026-11-15 13:13'
        lease_values = {
            'id': self.lease_id,
            'reservations': [{'id': '111',
                              'resource_id': '111',
                              'resource_type': 'virtual:instance',
                              'status': 'FAKE PROGRESS'}],
            'start_date': '2026-11-13 13:13',
            'end_date': '2026-11-14 13:13',
            'trust_id': 'exxee111qwwwwe',
            'before_end_notification': before_end_notification}
        self.lease['start_date'] = '2026-11-13 13:13'

        self.assertRaises(
            exceptions.NotAuthorized, self.manager.create_lease, lease_values)

    def test_create_lease_no_before_end_event(self):
        lease_values = {
            'id': self.lease_id,
            'reservations': [{'id': '111',
                              'resource_id': '111',
                              'resource_type': 'virtual:instance',
                              'status': 'FAKE PROGRESS'}],
            'start_date': '2026-11-13 13:13',
            'end_date': '2026-11-14 13:13',
            'trust_id': 'exxee111qwwwwe'}
        self.lease['start_date'] = '2026-11-13 13:13'

        self.cfg.CONF.set_override('notify_hours_before_lease_end', 0,
                                   group='manager')

        lease = self.manager.create_lease(lease_values)

        self.lease_create.assert_called_once_with(lease_values)
        self.assertEqual(lease, self.lease)
        self.assertEqual(2, len(lease_values['events']))

        # start lease event
        event = lease_values['events'][0]
        self.assertEqual('start_lease', event['event_type'])
        self.assertEqual(lease_values['start_date'], event['time'])
        self.assertEqual('UNDONE', event['status'])

        # end lease event
        event = lease_values['events'][1]
        self.assertEqual('end_lease', event['event_type'])
        self.assertEqual(lease_values['end_date'], event['time'])
        self.assertEqual('UNDONE', event['status'])

    def test_create_lease_with_before_end_notification_param(self):
        before_end_notification = '2026-11-14 10:13'
        lease_values = {
            'id': self.lease_id,
            'reservations': [{'id': '111',
                              'resource_id': '111',
                              'resource_type': 'virtual:instance',
                              'status': 'FAKE PROGRESS'}],
            'start_date': '2026-11-13 13:13',
            'end_date': '2026-11-14 13:13',
            'trust_id': 'exxee111qwwwwe',
            'before_end_notification': before_end_notification}
        self.lease['start_date'] = '2026-11-13 13:13'

        lease = self.manager.create_lease(lease_values)

        self.lease_create.assert_called_once_with(lease_values)
        self.assertEqual(lease, self.lease)
        self.assertEqual(3, len(lease_values['events']))

        # start lease event
        event = lease_values['events'][0]
        self.assertEqual('start_lease', event['event_type'])
        self.assertEqual(lease_values['start_date'], event['time'])
        self.assertEqual('UNDONE', event['status'])

        # end lease event
        event = lease_values['events'][1]
        self.assertEqual('end_lease', event['event_type'])
        self.assertEqual(lease_values['end_date'], event['time'])
        self.assertEqual('UNDONE', event['status'])

        # end lease event
        event = lease_values['events'][2]
        self.assertEqual('before_end_lease', event['event_type'])
        expected_before_end_time = datetime.datetime.strptime(
            before_end_notification, service.LEASE_DATE_FORMAT)
        self.assertEqual(expected_before_end_time, event['time'])
        self.assertEqual('UNDONE', event['status'])

    def test_create_lease_wrong_date(self):
        lease_values = {'start_date': '2025-13-35 13:13',
                        'end_date': '2025-12-31 13:13',
                        'trust_id': 'exxee111qwwwwe'}

        self.assertRaises(
            manager_ex.InvalidDate, self.manager.create_lease, lease_values)

    def test_create_lease_wrong_format_before_end_date(self):
        before_end_notification = '2026-14 10:13'
        lease_values = {'start_date': '2026-11-13 13:13',
                        'end_date': '2026-11-14 13:13',
                        'before_end_notification': before_end_notification,
                        'trust_id': 'exxee111qwwwwe'}

        self.assertRaises(
            manager_ex.InvalidDate, self.manager.create_lease, lease_values)

    def test_create_lease_start_date_in_past(self):
        lease_values = {
            'start_date':
            datetime.datetime.strftime(
                datetime.datetime.utcnow() - datetime.timedelta(days=1),
                service.LEASE_DATE_FORMAT),
            'end_date': '2025-12-31 13:13',
            'trust_id': 'exxee111qwwwwe'}

        self.assertRaises(
            exceptions.NotAuthorized, self.manager.create_lease, lease_values)

    def test_create_lease_unsupported_resource_type(self):
        lease_values = {
            'id': self.lease_id,
            'reservations': [{'id': '111',
                              'resource_id': '111',
                              'resource_type': 'unsupported:type',
                              'status': 'FAKE PROGRESS'}],
            'start_date': '2026-11-13 13:13',
            'end_date': '2026-12-13 13:13',
            'trust_id': 'exxee111qwwwwe'}

        self.assertRaises(manager_ex.UnsupportedResourceType,
                          self.manager.create_lease, lease_values)

    def test_create_lease_duplicated_name(self):
        lease_values = {
            'name': 'duplicated_name',
            'start_date': '2026-11-13 13:13',
            'end_date': '2026-12-13 13:13',
            'trust_id': 'exxee111qwwwwe'}

        self.patch(self.db_api,
                   'lease_create').side_effect = db_ex.ClimateDBDuplicateEntry
        self.assertRaises(manager_ex.LeaseNameAlreadyExists,
                          self.manager.create_lease, lease_values)

    def test_create_lease_without_trust_id(self):
        lease_values = {
            'name': 'name',
            'start_date': '2026-11-13 13:13',
            'end_date': '2026-12-13 13:13'}

        self.assertRaises(manager_ex.MissingTrustId,
                          self.manager.create_lease, lease_values)

    def test_update_lease_completed_lease_rename(self):
        lease_values = {'name': 'renamed'}
        target = datetime.datetime(2015, 1, 1)
        with mock.patch.object(datetime,
                               'datetime',
                               mock.Mock(wraps=datetime.datetime)) as patched:
            patched.utcnow.return_value = target
            lease = self.manager.update_lease(self.lease_id, lease_values)
        self.lease_update.assert_called_once_with(self.lease_id, lease_values)
        self.assertEqual(lease, self.lease)

    def test_update_lease_not_started_modify_dates(self):
        def fake_event_get(sort_key, sort_dir, filters):
            if filters['event_type'] == 'start_lease':
                return {'id': u'2eeb784a-2d84-4a89-a201-9d42d61eecb1'}
            elif filters['event_type'] == 'end_lease':
                return {'id': u'7085381b-45e0-4e5d-b24a-f965f5e6e5d7'}
            elif filters['event_type'] == 'before_end_lease':
                delta = datetime.timedelta(hours=1)
                return {'id': u'452bf850-e223-4035-9d13-eb0b0197228f',
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
                'id': u'593e7028-c0d1-4d76-8642-2ffd890b324c',
                'resource_type': 'virtual:instance',
                'start_date': datetime.datetime(2013, 12, 20, 20, 00),
                'end_date': datetime.datetime(2013, 12, 20, 21, 00)
            }
        ]
        event_get = self.patch(db_api, 'event_get_first_sorted_by_filters')
        event_get.side_effect = fake_event_get
        target = datetime.datetime(2013, 12, 15)
        with mock.patch.object(datetime,
                               'datetime',
                               mock.Mock(wraps=datetime.datetime)) as patched:
            patched.utcnow.return_value = target
            self.manager.update_lease(self.lease_id, lease_values)
        self.fake_plugin.update_reservation.assert_called_with(
            '593e7028-c0d1-4d76-8642-2ffd890b324c',
            {
                'id': '593e7028-c0d1-4d76-8642-2ffd890b324c',
                'resource_type': 'virtual:instance',
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

    def test_update_lease_started_modify_end_date_without_before_end(self):
        def fake_event_get(sort_key, sort_dir, filters):
            if filters['event_type'] == 'start_lease':
                return {'id': u'2eeb784a-2d84-4a89-a201-9d42d61eecb1'}
            elif filters['event_type'] == 'end_lease':
                return {'id': u'7085381b-45e0-4e5d-b24a-f965f5e6e5d7'}
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
                'id': u'593e7028-c0d1-4d76-8642-2ffd890b324c',
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
            self.manager.update_lease(self.lease_id, lease_values)
        self.fake_plugin.update_reservation.assert_called_with(
            '593e7028-c0d1-4d76-8642-2ffd890b324c',
            {
                'id': '593e7028-c0d1-4d76-8642-2ffd890b324c',
                'resource_type': 'virtual:instance',
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
                return {'id': u'2eeb784a-2d84-4a89-a201-9d42d61eecb1'}
            elif filters['event_type'] == 'end_lease':
                return {'id': u'7085381b-45e0-4e5d-b24a-f965f5e6e5d7'}
            elif filters['event_type'] == 'before_end_lease':
                delta = datetime.timedelta(hours=1)
                return {'id': u'452bf850-e223-4035-9d13-eb0b0197228f',
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
                'id': u'593e7028-c0d1-4d76-8642-2ffd890b324c',
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
            self.manager.update_lease(self.lease_id, lease_values)
        self.fake_plugin.update_reservation.assert_called_with(
            '593e7028-c0d1-4d76-8642-2ffd890b324c',
            {
                'id': '593e7028-c0d1-4d76-8642-2ffd890b324c',
                'resource_type': 'virtual:instance',
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
        before_end_notification = '2013-12-20 14:00'

        def fake_event_get(sort_key, sort_dir, filters):
            if filters['event_type'] == 'start_lease':
                return {'id': u'2eeb784a-2d84-4a89-a201-9d42d61eecb1'}
            elif filters['event_type'] == 'end_lease':
                return {'id': u'7085381b-45e0-4e5d-b24a-f965f5e6e5d7'}
            elif filters['event_type'] == 'before_end_lease':
                return {'id': u'452bf850-e223-4035-9d13-eb0b0197228f',
                        'time': before_end_notification,
                        'status': 'DONE'}

        lease_values = {
            'name': 'renamed',
            'end_date': '2013-12-20 16:00',
            'before_end_notification': before_end_notification
        }
        reservation_get_all = (
            self.patch(self.db_api, 'reservation_get_all_by_lease_id'))
        reservation_get_all.return_value = [
            {
                'id': u'593e7028-c0d1-4d76-8642-2ffd890b324c',
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
            self.manager.update_lease(self.lease_id, lease_values)
        self.fake_plugin.update_reservation.assert_called_with(
            '593e7028-c0d1-4d76-8642-2ffd890b324c',
            {
                'id': '593e7028-c0d1-4d76-8642-2ffd890b324c',
                'resource_type': 'virtual:instance',
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
                               before_end_notification,
                               service.LEASE_DATE_FORMAT),
                            'status': 'UNDONE'})
                 ]
        self.event_update.assert_has_calls(calls)
        self.lease_update.assert_called_once_with(self.lease_id, lease_values)

    def test_update_lease_started_before_end_lower_date_than_start(self):
        expected_start_date = datetime.datetime(2013, 12, 20, 13, 00)
        before_end_notification = datetime.datetime.strftime(
            (expected_start_date - datetime.timedelta(hours=1)),
            service.LEASE_DATE_FORMAT)

        def fake_event_get(sort_key, sort_dir, filters):
            if filters['event_type'] == 'start_lease':
                return {'id': u'2eeb784a-2d84-4a89-a201-9d42d61eecb1'}
            elif filters['event_type'] == 'end_lease':
                return {'id': u'7085381b-45e0-4e5d-b24a-f965f5e6e5d7'}
            elif filters['event_type'] == 'before_end_lease':
                return {'id': u'452bf850-e223-4035-9d13-eb0b0197228f',
                        'time': before_end_notification,
                        'status': 'DONE'}

        lease_values = {
            'name': 'renamed',
            'end_date': '2013-12-20 16:00',
            'before_end_notification': before_end_notification
        }
        reservation_get_all = (
            self.patch(self.db_api, 'reservation_get_all_by_lease_id'))
        reservation_get_all.return_value = [
            {
                'id': u'593e7028-c0d1-4d76-8642-2ffd890b324c',
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
                self.lease_id, lease_values)

    def test_update_lease_started_modify_before_end_with_invalid_date(self):
        # before_end_date is greater than current end_date
        before_end_notification = '2013-12-21 14:00'

        def fake_event_get(sort_key, sort_dir, filters):
            if filters['event_type'] == 'start_lease':
                return {'id': u'2eeb784a-2d84-4a89-a201-9d42d61eecb1'}
            elif filters['event_type'] == 'end_lease':
                return {'id': u'7085381b-45e0-4e5d-b24a-f965f5e6e5d7'}
            elif filters['event_type'] == 'before_end_lease':
                return {'id': u'452bf850-e223-4035-9d13-eb0b0197228f',
                        'time': before_end_notification,
                        'status': 'DONE'}

        lease_values = {
            'name': 'renamed',
            'end_date': '2013-12-20 16:00',
            'before_end_notification': before_end_notification
        }
        reservation_get_all = (
            self.patch(self.db_api, 'reservation_get_all_by_lease_id'))
        reservation_get_all.return_value = [
            {
                'id': u'593e7028-c0d1-4d76-8642-2ffd890b324c',
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
                self.lease_id, lease_values)

    def test_update_lease_started_modify_before_end_with_wrong_format(self):
        wrong_before_end_notification = '12-21 14:00'

        def fake_event_get(sort_key, sort_dir, filters):
            if filters['event_type'] == 'start_lease':
                return {'id': u'2eeb784a-2d84-4a89-a201-9d42d61eecb1'}
            elif filters['event_type'] == 'end_lease':
                return {'id': u'7085381b-45e0-4e5d-b24a-f965f5e6e5d7'}
            elif filters['event_type'] == 'before_end_lease':
                return {'id': u'452bf850-e223-4035-9d13-eb0b0197228f',
                        'time': wrong_before_end_notification,
                        'status': 'DONE'}

        lease_values = {
            'name': 'renamed',
            'end_date': '2013-12-20 16:00',
            'before_end_notification': wrong_before_end_notification
        }
        reservation_get_all = (
            self.patch(self.db_api, 'reservation_get_all_by_lease_id'))
        reservation_get_all.return_value = [
            {
                'id': u'593e7028-c0d1-4d76-8642-2ffd890b324c',
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
                self.lease_id, lease_values)

    def test_update_lease_is_not_values(self):
        lease_values = None
        lease = self.manager.update_lease(self.lease_id, lease_values)
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
                exceptions.NotAuthorized, self.manager.update_lease,
                self.lease_id, lease_values)

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
                exceptions.NotAuthorized, self.manager.update_lease,
                self.lease_id, lease_values)

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
                exceptions.NotAuthorized, self.manager.update_lease,
                self.lease_id, lease_values)

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
                exceptions.NotAuthorized, self.manager.update_lease,
                self.lease_id, lease_values)

    def test_update_lease_start_date_event_not_found(self):
        events = self.patch(self.db_api, 'event_get_first_sorted_by_filters')
        events.return_value = None
        lease_values = {
            'name': 'renamed',
            'start_date': '2013-12-15 20:00'
        }
        self.assertRaises(exceptions.ClimateException,
                          self.manager.update_lease,
                          self.lease_id,
                          lease_values)

    def test_update_lease_end_date_event_not_found(self):
        def fake_event_get(sort_key, sort_dir, filters):
            if filters['event_type'] == 'start_lease':
                return {'id': u'2eeb784a-2d84-4a89-a201-9d42d61eecb1'}
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
            self.assertRaises(exceptions.ClimateException,
                              self.manager.update_lease,
                              self.lease_id,
                              lease_values)
        event_update.assert_called_once_with(
            '2eeb784a-2d84-4a89-a201-9d42d61eecb1',
            {'time': datetime.datetime(2013, 12, 20, 13, 0)})

    def test_delete_lease_before_starting_date(self):
        fake_get_lease = self.patch(self.manager, 'get_lease')
        fake_get_lease.return_value = self.lease

        target = datetime.datetime(2013, 12, 20, 12, 00)
        with mock.patch.object(datetime,
                               'datetime',
                               mock.Mock(wraps=datetime.datetime)) as patched:
            patched.utcnow.return_value = target
            self.manager.delete_lease(self.lease_id)

        self.trust_ctx.assert_called_once_with(self.lease['trust_id'])
        self.lease_destroy.assert_called_once_with(self.lease_id)

    def test_delete_lease_after_ending_date(self):
        fake_get_lease = self.patch(self.manager, 'get_lease')
        fake_get_lease.return_value = self.lease

        target = datetime.datetime(2013, 12, 20, 16, 00)
        with mock.patch.object(datetime,
                               'datetime',
                               mock.Mock(wraps=datetime.datetime)) as patched:
            patched.utcnow.return_value = target
            self.manager.delete_lease(self.lease_id)

        expected_context = self.trust_ctx.return_value
        self.lease_destroy.assert_called_once_with(self.lease_id)
        self.fake_notifier.assert_called_once_with(
            expected_context.__enter__.return_value,
            self.notifier_api.format_lease_payload(self.lease),
            'lease.delete')

    def test_delete_lease_after_starting_date(self):
        fake_get_lease = self.patch(self.manager, 'get_lease')
        fake_get_lease.return_value = self.lease

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

        self.trust_ctx.assert_called_once_with(self.lease['trust_id'])
        basic_action.assert_called_once_with(self.lease_id, '1', 'on_start',
                                             'active')

    def test_end_lease(self):
        basic_action = self.patch(self.manager, '_basic_action')

        self.manager.end_lease(self.lease_id, '1')

        self.trust_ctx.assert_called_once_with(self.lease['trust_id'])
        basic_action.assert_called_once_with(self.lease_id, '1', 'on_end',
                                             'deleted')

    def test_before_end_lease(self):
        self.manager.before_end_lease(self.lease_id, '1')
        self.event_update.assert_called_once_with('1', {'status': 'DONE'})

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

    def test_basic_action_raise_exception(self):
        def raiseClimateException(resource_id):
            raise exceptions.ClimateException(resource_id)

        self.manager.resource_actions = (
            {'virtual:instance':
             {'on_start': self.fake_plugin.on_start,
              'on_end': raiseClimateException}})

        self.patch(self.manager, 'get_lease').return_value = self.lease

        self.manager._basic_action(self.lease_id, '1', 'on_end',
                                   reservation_status='done')

        self.reservation_update.assert_called_once_with(
            '111', {'status': 'error'})
        self.event_update.assert_called_once_with('1', {'status': 'ERROR'})

    def test_basic_action_raise_exception_no_reservation_status(self):
        def raiseClimateException(resource_id):
            raise exceptions.ClimateException(resource_id)

        self.manager.resource_actions = (
            {'virtual:instance':
             {'on_start': self.fake_plugin.on_start,
              'on_end': raiseClimateException}})

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
