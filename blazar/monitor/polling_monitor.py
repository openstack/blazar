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
from oslo_service import threadgroup

from blazar.monitor import base

LOG = logging.getLogger(__name__)


class PollingMonitor(base.BaseMonitor):
    """A polling based monitor."""

    def __init__(self, monitor_plugins):
        """Initialize a polling monitor."""
        self.monitor_plugins = monitor_plugins
        self.tg = threadgroup.ThreadGroup()

    def start_monitoring(self):
        """Start polling."""
        LOG.debug('Starting a polling monitor...')
        try:
            for plugin in self.monitor_plugins:
                # Set poll() timer. The poll() is wrapped with the
                # update_statuses() to manage statuses of leases and
                # reservations.
                self.tg.add_timer(plugin.get_polling_interval(),
                                  self.update_statuses, 0, plugin.poll)
        except Exception as e:
            LOG.exception('Failed to start a polling monitor. (%s)',
                          e.message)

    def stop_monitoring(self):
        """Stop polling."""
        LOG.debug('Stopping a polling monitor...')
        try:
            self.tg.stop()
        except Exception as e:
            LOG.exception('Failed to stop a polling monitor. (%s)', e.message)
