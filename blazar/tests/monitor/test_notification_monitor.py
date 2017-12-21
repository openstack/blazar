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
import oslo_messaging

from blazar.monitor import notification_monitor
from blazar.plugins import base
from blazar import tests


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
        return 0

    def heal(self):
        return {}


class NotificationMonitorTestCase(tests.TestCase):
    def setUp(self):
        super(NotificationMonitorTestCase, self).setUp()
        listener = self.patch(oslo_messaging, 'get_notification_listener')
        listener.return_value = None
        self.plugins = [DummyMonitorPlugin()]
        self.monitor = notification_monitor.NotificationMonitor(self.plugins)

    def test_get_targets(self):
        get_topics = self.patch(self.plugins[0], 'get_notification_topics')
        get_topics.return_value = ['topic1', 'topic2']

        targets = self.monitor._get_targets(self.plugins)
        self.assertEqual(2, len(targets))

    def test_get_endpoints(self):
        get_event_types = self.patch(self.plugins[0],
                                     'get_notification_event_types')
        get_event_types.return_value = ['event_type1', 'event_type2']

        endpoint = self.patch(notification_monitor.NotificationEndpoint,
                              '__init__')
        endpoint.return_value = None

        self.monitor._get_endpoints(self.plugins)
        endpoint.assert_called_once()


class NotificationEndpointTestCase(tests.TestCase):
    def setUp(self):
        super(NotificationEndpointTestCase, self).setUp()
        self.handler = self.patch(
            DummyMonitorPlugin, 'notification_callback'
        )
        plugin = DummyMonitorPlugin()
        monitor = notification_monitor.NotificationMonitor([plugin])
        monitor.handlers['event_type1'].append(plugin.notification_callback)
        self.endpoint = notification_monitor.NotificationEndpoint(monitor)

    def test_info(self):
        self.endpoint.info('dummy_ctxt', 'dummy_id', 'event_type1',
                           'hello', 'dummy_metadata')
        self.handler.assert_called_once_with('event_type1', 'hello')

    def test_warn(self):
        self.endpoint.warn('dummy_ctxt', 'dummy_id', 'event_type1',
                           'hello', 'dummy_metadata')
        self.handler.assert_called_once_with('event_type1', 'hello')

    def test_error(self):
        self.endpoint.error('dummy_ctxt', 'dummy_id', 'event_type1',
                            'hello', 'dummy_metadata')
        self.handler.assert_called_once_with('event_type1', 'hello')
