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

from collections import defaultdict

from oslo_config import cfg
from oslo_log import log as logging
import oslo_messaging

from blazar.monitor import base

LOG = logging.getLogger(__name__)


class NotificationMonitor(base.BaseMonitor):
    """A notification based monitor."""

    def __init__(self, monitor_plugins):
        """Initialize a notification monitor."""
        LOG.debug('Initializing a notification monitor...')
        super(NotificationMonitor, self).__init__(monitor_plugins)
        try:
            self.handlers = defaultdict(list)
            self.listener = oslo_messaging.get_notification_listener(
                oslo_messaging.get_notification_transport(cfg.CONF),
                self._get_targets(monitor_plugins),
                self._get_endpoints(monitor_plugins),
                executor='eventlet'
            )
            LOG.debug('Notification listener is successfully created.')
        except Exception as e:
            LOG.exception('Failed to create a notification listener. (%s)',
                          str(e))

    def start_monitoring(self):
        """Start subscribing notifications."""
        LOG.debug('Starting a notification monitor...')
        try:
            self.listener.start()
            super(NotificationMonitor, self).start_monitoring()
        except Exception as e:
            LOG.exception('Failed to start a notification monitor. (%s)',
                          str(e))

    def stop_monitoring(self):
        """Stop subscribing notifications."""
        LOG.debug('Stopping a notification monitor...')
        try:
            self.listener.stop()
            super(NotificationMonitor, self).stop_monitoring()
        except Exception as e:
            LOG.exception('Failed to stop a notification monitor. (%s)',
                          str(e))

    def _get_targets(self, monitor_plugins):
        """Get a list of targets to subscribe.

        :param monitor_plugins: a list of resource monitor plugins. These
                                plugins provide notification topics.
        :return: a list of targets to subscribe.
        """
        topics = []
        for plugin in monitor_plugins:
            topics += plugin.get_notification_topics()

        return [oslo_messaging.Target(topic=topic) for topic in set(topics)]

    def _get_endpoints(self, monitor_plugins):
        """Get a list of endpoints which handle notification messages.

        :param monitor_plugins: a list of resource monitor plugins. These
                                plugins provide event types to handle and a
                                handler which is called when notification
                                messages of those event types
                                are received.
        :return: a list of endpoints.
        """
        for plugin in monitor_plugins:
            for event_type in plugin.get_notification_event_types():
                self.handlers[event_type].append(
                    # Wrap the notification callback with the
                    # call_monitor_plugin() to manage lease/reservation flags.
                    lambda e_type, payload: self.call_monitor_plugin(
                        plugin.notification_callback, e_type, payload))

        return [NotificationEndpoint(self)]


class NotificationEndpoint(object):
    """End point of notifications.

    It handles the notification messages. If it receives a notification
    message, it calls notification handlers provided as a parameter for the
    __init__().
    """

    def __init__(self, monitor, filter_rules={}):
        self.monitor = monitor
        self.filter_rule = oslo_messaging.NotificationFilter(**filter_rules)

    def info(self, ctxt, publisher_id, event_type, payload, metadata):
        self.handle_notification('INFO', ctxt, publisher_id, event_type,
                                 payload, metadata)

    def warn(self, ctxt, publisher_id, event_type, payload, metadata):
        self.handle_notification('WARN', ctxt, publisher_id, event_type,
                                 payload, metadata)

    def error(self, ctxt, publisher_id, event_type, payload, metadata):
        self.handle_notification('ERROR', ctxt, publisher_id, event_type,
                                 payload, metadata)

    def handle_notification(self, priority, ctxt, publisher_id, event_type,
                            payload, metadata):
        LOG.debug('Received a notification: priority: %s, publisher id: %s, '
                  'event type: %s, payload: %s', priority, publisher_id,
                  event_type, payload)
        for handler in self.monitor.handlers[str(event_type)]:
            handler(event_type, payload)
