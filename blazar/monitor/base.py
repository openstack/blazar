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

from blazar.db import api as db_api

LOG = logging.getLogger(__name__)


class BaseMonitor(object):
    """Base class for monitoring classes."""

    def __init__(self, monitor_plugins):
        self.monitor_plugins = monitor_plugins
        self.tg = threadgroup.ThreadGroup()
        self.healing_timers = []

    def start_monitoring(self):
        """Start monitoring."""
        self.start_periodic_healing()

    def stop_monitoring(self):
        """Stop monitoring."""
        self.stop_periodic_healing()

    def start_periodic_healing(self):
        """Start periodic healing process."""
        for plugin in self.monitor_plugins:
            healing_interval_mins = plugin.get_healing_interval()
            if healing_interval_mins > 0:
                self.healing_timers.append(
                    self.tg.add_timer(healing_interval_mins * 60,
                                      self.call_monitor_plugin,
                                      None,
                                      plugin.heal))

    def stop_periodic_healing(self):
        """Stop periodic healing process."""
        for timer in self.healing_timers:
            self.tg.timer_done(timer)

    def call_monitor_plugin(self, callback, *args, **kwargs):
        """Call a callback and update lease/reservation flags."""
        # This method has to handle any exception internally. It shouldn't
        # raise an exception because the timer threads in the BaseMonitor class
        # terminates its execution once the thread has received any exception.
        try:
            # The callback() has to return a dictionary of
            # {reservation id: flags to update}.
            # e.g. {'dummyid': {'missing_resources': True}}
            reservation_flags = callback(*args, **kwargs)

            if reservation_flags:
                self._update_flags(reservation_flags)
        except Exception as e:
            LOG.exception('Caught an exception while executing a callback. '
                          '%s', str(e))

    def _update_flags(self, reservation_flags):
        """Update lease/reservation flags."""
        lease_ids = set([])

        for reservation_id, flags in reservation_flags.items():
            db_api.reservation_update(reservation_id, flags)
            LOG.debug('Reservation %s was updated: %s',
                      reservation_id, flags)
            reservation = db_api.reservation_get(reservation_id)
            lease_ids.add(reservation['lease_id'])

        for lease_id in lease_ids:
            LOG.debug('Lease %s was updated: {"degraded": True}', lease_id)
            db_api.lease_update(lease_id, {'degraded': True})
