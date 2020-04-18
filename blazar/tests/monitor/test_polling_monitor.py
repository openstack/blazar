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

from blazar.monitor import base as base_monitor
from blazar.monitor import polling_monitor
from blazar.plugins import base
from blazar import tests


POLLING_INTERVAL = 10
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
        return POLLING_INTERVAL

    def poll(self):
        return {}

    def get_healing_interval(self):
        return HEALING_INTERVAL

    def heal(self):
        return {}


class PollingHandlerTestCase(tests.TestCase):
    def setUp(self):
        super(PollingHandlerTestCase, self).setUp()
        self.monitor_plugins = [DummyMonitorPlugin()]
        self.monitor = polling_monitor.PollingMonitor(self.monitor_plugins)

    def test_start_monitoring(self):
        add_timer = self.patch(threadgroup.ThreadGroup, 'add_timer')
        self.patch(base_monitor.BaseMonitor, 'start_monitoring')

        self.monitor.start_monitoring()
        add_timer.assert_called_once_with(
            POLLING_INTERVAL, self.monitor.call_monitor_plugin, None,
            self.monitor_plugins[0].poll)

    def test_stop_monitoring(self):
        dummy_timer = mock.Mock()
        timer_done = self.patch(threadgroup.ThreadGroup, 'timer_done')
        self.monitor.polling_timers.append(dummy_timer)
        self.patch(base_monitor.BaseMonitor, 'stop_monitoring')

        self.monitor.stop_monitoring()
        timer_done.assert_called_once_with(dummy_timer)
