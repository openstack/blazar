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

from oslo_log import log as logging

from blazar.monitor import base

LOG = logging.getLogger(__name__)


class PollingMonitor(base.BaseMonitor):
    """A polling based monitor."""

    def __init__(self, monitor_plugins):
        """Initialize a polling monitor."""
        LOG.debug('Initializing a polling monitor...')
        super(PollingMonitor, self).__init__(monitor_plugins)
        self.polling_timers = []

    def start_monitoring(self):
        """Start polling."""
        LOG.debug('Starting a polling monitor...')

        try:
            for plugin in self.monitor_plugins:
                # Set polling timer. Wrap the monitor plugin method with the
                # call_monitor_plugin() to manage lease/reservation flags.
                self.polling_timers.append(
                    self.tg.add_timer(plugin.get_polling_interval(),
                                      self.call_monitor_plugin, None,
                                      plugin.poll))
            super(PollingMonitor, self).start_monitoring()
        except Exception as e:
            LOG.exception('Failed to start a polling monitor. (%s)',
                          str(e))

    def stop_monitoring(self):
        """Stop polling."""
        LOG.debug('Stopping a polling monitor...')
        try:
            for timer in self.polling_timers:
                self.tg.timer_done(timer)
            super(PollingMonitor, self).stop_monitoring()
        except Exception as e:
            LOG.exception('Failed to stop a polling monitor. (%s)', str(e))
