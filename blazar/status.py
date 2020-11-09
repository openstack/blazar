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

from functools import wraps

from oslo_log import log as logging
from oslo_utils.excutils import save_and_reraise_exception

from blazar.db import api as db_api
from blazar import exceptions

LOG = logging.getLogger(__name__)


class BaseStatus(object):
    """Base class of status."""

    # All statuses
    ALL = ()

    # Valid status transitions
    NEXT_STATUSES = {}

    @classmethod
    def is_valid_transition(cls, current_status, next_status, **kwargs):
        """Check validity of a status transition.

        :param current_status: Current status
        :param next_status: Next status
        :return: True if the transition is valid
        """

        if next_status not in cls.NEXT_STATUSES[current_status]:
            LOG.warning('Invalid transition from %s to %s.',
                        current_status, next_status)
            return False

        return True


class EventStatus(BaseStatus):
    """Event status class."""

    # Statuses of an event
    UNDONE = 'UNDONE'
    IN_PROGRESS = 'IN_PROGRESS'
    DONE = 'DONE'
    ERROR = 'ERROR'

    ALL = (UNDONE, IN_PROGRESS, DONE, ERROR)

    # Valid status transitions
    NEXT_STATUSES = {
        UNDONE: (IN_PROGRESS,),
        IN_PROGRESS: (DONE, ERROR),
        DONE: (),
        ERROR: ()
    }


class ReservationStatus(BaseStatus):
    """Reservation status class."""

    # Statuses of a reservation
    PENDING = 'pending'
    ACTIVE = 'active'
    DELETED = 'deleted'
    ERROR = 'error'

    ALL = (PENDING, ACTIVE, DELETED, ERROR)

    # Valid status transitions
    NEXT_STATUSES = {
        PENDING: (ACTIVE, DELETED, ERROR),
        ACTIVE: (DELETED, ERROR),
        DELETED: (),
        ERROR: (DELETED,)
    }


class LeaseStatus(BaseStatus):
    """Lease status class."""

    # Stable statuses of a lease
    PENDING = 'PENDING'
    ACTIVE = 'ACTIVE'
    TERMINATED = 'TERMINATED'
    ERROR = 'ERROR'

    STABLE = (PENDING, ACTIVE, TERMINATED, ERROR)

    # Transitional statuses of a lease
    CREATING = 'CREATING'
    STARTING = 'STARTING'
    UPDATING = 'UPDATING'
    TERMINATING = 'TERMINATING'
    DELETING = 'DELETING'

    TRANSITIONAL = (CREATING, STARTING, UPDATING, TERMINATING, DELETING)

    # All statuses
    ALL = STABLE + TRANSITIONAL

    # Valid status transitions
    NEXT_STATUSES = {
        PENDING: (STARTING, UPDATING, DELETING),
        ACTIVE: (TERMINATING, UPDATING, DELETING),
        TERMINATED: (UPDATING, DELETING),
        ERROR: (TERMINATING, UPDATING, DELETING),
        CREATING: (PENDING, DELETING),
        STARTING: (ACTIVE, ERROR, DELETING),
        UPDATING: STABLE + (DELETING,),
        TERMINATING: (TERMINATED, ERROR, DELETING),
        DELETING: (ERROR,)
    }

    @classmethod
    def is_valid_transition(cls, current, next, **kwargs):
        """Check validity of a status transition.

        :param current: Current status
        :param next: Next status
        :return: True if the transition is valid
        """

        if super(LeaseStatus, cls).is_valid_transition(current,
                                                       next, **kwargs):
            if cls.is_valid_combination(kwargs['lease_id'], next):
                return True
            else:
                LOG.warning('Invalid combination of statuses.')

        return False

    @classmethod
    def is_valid_combination(cls, lease_id, status):
        """Validator for the combination of statuses.

        Check if the combination of statuses of lease, reservations and events
        is valid

        :param lease_id: Lease ID
        :param status: Lease status
        :return: True if the combination is valid
        """

        # Validate reservation statuses
        reservations = db_api.reservation_get_all_by_lease_id(lease_id)
        if any([r['status'] not in COMBINATIONS[status]['reservation']
                for r in reservations]):
            return False

        # Validate event statuses
        for event_type in ('start_lease', 'end_lease'):
            event = db_api.event_get_first_sorted_by_filters(
                'lease_id', 'asc',
                {'lease_id': lease_id, 'event_type': event_type}
            )
            if event['status'] not in COMBINATIONS[status][event_type]:
                return False

        return True

    @classmethod
    def is_stable(cls, lease_id):
        """Check if the lease status is stable

        :param lease_id: Lease ID
        :return: True if the status is in (PENDING, ACTIVE, TERMINATED, ERROR)
        """
        lease = db_api.lease_get(lease_id)
        return (lease['status'] in cls.STABLE)

    @classmethod
    def lease_status(cls, transition, result_in, non_fatal_exceptions=[]):
        """Decorator for managing a lease status.

        This checks and updates a lease status before and after executing a
        decorated function.

        :param transition: A status which is set while executing the
                           decorated function.
        :param result_in: A tuple of statuses to which a lease transits after
                          executing the decorated function.
        :param non_fatal_exceptions: A list of exceptions that are non fatal.
                          If one is raised during execution, the lease status
                          will be restored.
        """
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Update a lease status
                lease_id = kwargs['lease_id']
                lease = db_api.lease_get(lease_id)
                original_status = lease['status']
                if cls.is_valid_transition(original_status,
                                           transition,
                                           lease_id=lease_id):
                    db_api.lease_update(lease_id,
                                        {'status': transition})
                    LOG.debug('Status of lease %s changed from %s to %s.',
                              lease_id, original_status, transition)
                else:
                    LOG.warning('Aborting %s. '
                                'Invalid lease status transition '
                                'from %s to %s.',
                                func.__name__, original_status,
                                transition)
                    raise exceptions.InvalidStatus

                # Executing the wrapped function
                try:
                    result = func(*args, **kwargs)
                except Exception as e:
                    with save_and_reraise_exception():
                        if type(e) in non_fatal_exceptions:
                            LOG.exception(
                                'Non-fatal exception during transition '
                                'of lease %s', lease_id)
                            db_api.lease_update(lease_id,
                                                {'status': original_status})
                        else:
                            LOG.exception(
                                'Lease %s went into ERROR status. %s',
                                lease_id, str(e))
                            db_api.lease_update(lease_id,
                                                {'status': cls.ERROR})

                # Update a lease status if it exists
                if db_api.lease_get(lease_id):
                    next_status = cls.derive_stable_status(lease_id)
                    if (next_status in result_in
                            and cls.is_valid_transition(transition,
                                                        next_status,
                                                        lease_id=lease_id)):
                        db_api.lease_update(lease_id,
                                            {'status': next_status})
                        LOG.debug('Status of lease %s changed from %s to %s.',
                                  lease_id, transition, next_status)
                    else:
                        LOG.error('Lease %s went into ERROR status.',
                                  lease_id)
                        db_api.lease_update(lease_id, {'status': cls.ERROR})
                        raise exceptions.InvalidStatus

                return result
            return wrapper
        return decorator

    @classmethod
    def derive_stable_status(cls, lease_id):
        """Derive stable lease status.

        This derives a lease status from statuses of reservations and events.

        :param lease_id: Lease ID
        :return: Derived lease status
        """

        # Possible lease statuses. Key is a tuple of (lease_start event
        # status, lease_end event status)
        possible_statuses = {
            (EventStatus.UNDONE, EventStatus.UNDONE): cls.PENDING,
            (EventStatus.DONE, EventStatus.UNDONE): cls.ACTIVE,
            (EventStatus.DONE, EventStatus.DONE): cls.TERMINATED
        }

        # Derive a lease status from event statuses
        event_statuses = {}
        for event_type in ('start_lease', 'end_lease'):
            event = db_api.event_get_first_sorted_by_filters(
                'lease_id', 'asc',
                {'lease_id': lease_id, 'event_type': event_type}
            )
            event_statuses[event_type] = event['status']
        try:
            status = possible_statuses[(event_statuses['start_lease'],
                                        event_statuses['end_lease'])]
        except KeyError:
            status = cls.ERROR

        # Check the combination of statuses.
        if cls.is_valid_combination(lease_id, status):
            return status
        else:
            return cls.ERROR


COMBINATIONS = {
    LeaseStatus.CREATING: {
        'reservation': (ReservationStatus.PENDING,),
        'start_lease': (EventStatus.UNDONE,),
        'end_lease': (EventStatus.UNDONE,)
    },
    LeaseStatus.PENDING: {
        'reservation': (ReservationStatus.PENDING,),
        'start_lease': (EventStatus.UNDONE,),
        'end_lease': (EventStatus.UNDONE,)
    },
    LeaseStatus.STARTING: {
        'reservation': (ReservationStatus.PENDING,
                        ReservationStatus.ACTIVE,
                        ReservationStatus.ERROR),
        'start_lease': (EventStatus.IN_PROGRESS,),
        'end_lease': (EventStatus.UNDONE,)
    },
    LeaseStatus.ACTIVE: {
        'reservation': (ReservationStatus.ACTIVE,),
        'start_lease': (EventStatus.DONE,),
        'end_lease': (EventStatus.UNDONE,)
    },
    LeaseStatus.TERMINATING: {
        'reservation': (ReservationStatus.ACTIVE,
                        ReservationStatus.DELETED,
                        ReservationStatus.ERROR),
        'start_lease': (EventStatus.DONE,
                        EventStatus.ERROR),
        'end_lease': (EventStatus.IN_PROGRESS,)
    },
    LeaseStatus.TERMINATED: {
        'reservation': (ReservationStatus.DELETED,),
        'start_lease': (EventStatus.DONE,),
        'end_lease': (EventStatus.DONE,)
    },
    LeaseStatus.DELETING: {
        'reservation': ReservationStatus.ALL,
        'start_lease': (EventStatus.UNDONE,
                        EventStatus.DONE,
                        EventStatus.ERROR),
        'end_lease': (EventStatus.UNDONE,
                      EventStatus.DONE,
                      EventStatus.ERROR)
    },
    LeaseStatus.UPDATING: {
        'reservation': ReservationStatus.ALL,
        'start_lease': (EventStatus.UNDONE,
                        EventStatus.DONE,
                        EventStatus.ERROR),
        'end_lease': (EventStatus.UNDONE,
                      EventStatus.DONE,
                      EventStatus.ERROR)
    },
    LeaseStatus.ERROR: {
        'reservation': ReservationStatus.ERROR,
        'start_lease': (EventStatus.DONE,
                        EventStatus.ERROR),
        'end_lease': (EventStatus.UNDONE,
                      EventStatus.ERROR)
    }
}

event = EventStatus
reservation = ReservationStatus
lease = LeaseStatus
