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

from blazar.monitor import notification_monitor
from blazar.monitor import polling_monitor


def load_monitors(plugins):
    """Load resource monitors.

    :param plugins: resource plugins.
    :return: a list of monitors.
    """
    monitors = []

    # Setup a notification monitor
    notification_plugins = set([])
    for plugin in plugins.values():
        if plugin.monitor:
            if plugin.monitor.is_notification_enabled():
                notification_plugins.add(plugin.monitor)
    if notification_plugins:
        monitors.append(
            notification_monitor.NotificationMonitor(notification_plugins))

    # Setup a polling monitor
    polling_plugins = set([])
    for plugin in plugins.values():
        if plugin.monitor:
            if plugin.monitor.is_polling_enabled():
                polling_plugins.add(plugin.monitor)
    if polling_plugins:
        monitors.append(polling_monitor.PollingMonitor(polling_plugins))

    return monitors
