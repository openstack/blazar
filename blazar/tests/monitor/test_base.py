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

from unittest import mock

from oslo_service import threadgroup

from blazar.db import api as db_api
from blazar import exceptions
from blazar.monitor import base as base_monitor
from blazar.plugins import base
from blazar import tests


HEALING_INTERVAL = 10


class DummyMonitorPlugin(base.BaseMonitorPlugin):
    def is_notification_enabled(self):
        return True

    def get_notification_event_types(self):
        return []

    def get_notification_topics(self):
        return []

    def notification_callback(self, event_type, message):
        return {}

    def is_polling_enabled(self):
        return False

    def get_polling_interval(self):
        return 0

    def poll(self):
        return {}

    def get_healing_interval(self):
        return HEALING_INTERVAL

    def heal(self):
        return {}


class BaseMonitorTestCase(tests.TestCase):
    def setUp(self):
        super(BaseMonitorTestCase, self).setUp()
        self.monitor_plugins = [DummyMonitorPlugin()]
        self.monitor = base_monitor.BaseMonitor(self.monitor_plugins)

    def test_start_periodic_healing(self):
        add_timer = self.patch(threadgroup.ThreadGroup, 'add_timer')

        self.monitor.start_periodic_healing()
        add_timer.assert_called_once_with(
            HEALING_INTERVAL * 60, self.monitor.call_monitor_plugin, None,
            self.monitor_plugins[0].heal)

    def test_stop_periodic_healing(self):
        dummy_timer = mock.Mock()
        timer_done = self.patch(threadgroup.ThreadGroup, 'timer_done')
        self.monitor.healing_timers.append(dummy_timer)

        self.monitor.stop_monitoring()
        timer_done.assert_called_once_with(dummy_timer)

    def test_call_monitor_plugin(self):
        callback = self.patch(DummyMonitorPlugin,
                              'notification_callback')
        callback.return_value = {
            'dummy_id1': {'missing_resources': True}
        }
        update_flags = self.patch(self.monitor, '_update_flags')

        self.monitor.call_monitor_plugin(callback, 'event_type1', 'hello')
        callback.assert_called_once_with('event_type1', 'hello')
        update_flags.assert_called_once_with(
            {'dummy_id1': {'missing_resources': True}})

    def test_error_in_callback(self):
        callback = self.patch(DummyMonitorPlugin, 'poll')
        callback.side_effect = exceptions.BlazarException('error')

        # Testing that no exception is raised even if the callback raises one
        self.monitor.call_monitor_plugin(callback)

    def test_call_update_flags(self):
        reservation_update = self.patch(db_api, 'reservation_update')
        reservation_get = self.patch(db_api, 'reservation_get')
        reservation_get.return_value = {
            'lease_id': 'dummy_id2'
        }
        lease_update = self.patch(db_api, 'lease_update')

        self.monitor._update_flags({'dummy_id1': {'missing_resources': True}})
        reservation_update.assert_called_once_with(
            'dummy_id1', {'missing_resources': True})
        reservation_get.assert_called_once_with('dummy_id1')
        lease_update.assert_called_once_with('dummy_id2',
                                             {'degraded': True})

    def test_error_in_update_flags(self):
        callback = self.patch(DummyMonitorPlugin, 'poll')
        callback.return_value = {
            'dummy_id1': {'missing_resources': True}
        }

        update_flags = self.patch(self.monitor, '_update_flags')
        update_flags.side_effect = exceptions.BlazarException('error')

        # Testing that no exception is raised even if the callback raises one
        self.monitor.call_monitor_plugin(callback)
