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

import abc

from oslo_log import log as logging
import six

from blazar.db import api as db_api

LOG = logging.getLogger(__name__)


@six.add_metaclass(abc.ABCMeta)
class BaseMonitor(object):
    """Base class for monitoring classes."""

    @abc.abstractmethod
    def start_monitoring(self):
        """Start monitoring."""
        pass

    @abc.abstractmethod
    def stop_monitoring(self):
        """Stop monitoring."""
        pass

    def update_statuses(self, callback, *args, **kwargs):
        """Update leases and reservations table after executing a callback."""
        try:
            # The callback() has to return a dictionary of
            # {reservation id: flags to update}.
            # e.g. {'dummyid': {'missing_resources': True}}
            reservation_flags = callback(*args, **kwargs)
        except Exception as e:
            LOG.exception('Caught an exception while executing a callback. '
                          '%s', e.message)

            # TODO(hiro-kobayashi): update statuses of related leases and
            # reservations. Depends on the state-machine blueprint.

        # Update flags of related leases and reservations.
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
