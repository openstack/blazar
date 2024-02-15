# Copyright (c) 2013 Mirantis Inc.
#
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
import datetime
from operator import itemgetter

import eventlet
from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils.excutils import save_and_reraise_exception
from stevedore import enabled

from blazar import context
from blazar.db import api as db_api
from blazar.db import exceptions as db_ex
from blazar import enforcement
from blazar import exceptions as common_ex
from blazar import manager
from blazar.manager import exceptions
from blazar import monitor
from blazar.notification import api as notification_api
from blazar import status
from blazar.utils import service as service_utils
from blazar.utils import trusts

manager_opts = [
    cfg.ListOpt('plugins',
                default=['dummy.vm.plugin'],
                help='All plugins to use (one for every resource type to '
                     'support.)'),
    cfg.IntOpt('minutes_before_end_lease',
               default=60,
               min=0,
               help='Minutes prior to the end of a lease in which actions '
                    'like notification and snapshot are taken. If this is '
                    'set to 0, then these actions are not taken.'),
    cfg.IntOpt('event_max_retries',
               default=1,
               min=0,
               max=50,
               help='Number of times to retry an event action.')
]

CONF = cfg.CONF
CONF.register_opts(manager_opts, 'manager')
LOG = logging.getLogger(__name__)

LEASE_DATE_FORMAT = "%Y-%m-%d %H:%M"

EVENT_INTERVAL = 10


class ManagerService(service_utils.RPCServer):
    """Service class for the blazar-manager service.

    Responsible for working with Blazar DB, scheduling logic, running events,
    working with plugins, etc.
    """

    def __init__(self):
        target = manager.get_target()
        super(ManagerService, self).__init__(target)
        self.plugins = self._get_plugins()
        self.resource_actions = self._setup_actions()
        self.monitors = monitor.load_monitors(self.plugins)
        self.enforcement = enforcement.UsageEnforcement()

    def start(self):
        super(ManagerService, self).start()
        # NOTE(jakecoll): stop_on_exception=False was added because database
        # exceptions would prevent threads from being scheduled again.
        # TODO(jakecoll): Find a way to test this.
        self.tg.add_timer_args(EVENT_INTERVAL, self._process_events,
                               stop_on_exception=False)
        for m in self.monitors:
            m.start_monitoring()

    def _get_plugins(self):
        """Return dict of resource-plugin class pairs."""
        config_plugins = CONF.manager.plugins
        plugins = {}

        extension_manager = enabled.EnabledExtensionManager(
            check_func=lambda ext: ext.name in config_plugins,
            namespace='blazar.resource.plugins',
            invoke_on_load=False
        )

        invalid_plugins = (set(config_plugins) -
                           set([ext.name for ext
                                in extension_manager.extensions]))
        if invalid_plugins:
            raise common_ex.BlazarException('Invalid plugin names are '
                                            'specified: %s' % invalid_plugins)

        for ext in extension_manager.extensions:
            try:
                plugin_obj = ext.plugin()
            except Exception as e:
                LOG.warning("Could not load {0} plugin "
                            "for resource type {1} '{2}'".format(
                                ext.name, ext.plugin.resource_type, e))
            else:
                if plugin_obj.resource_type in plugins:
                    msg = ("You have provided several plugins for "
                           "one resource type in configuration file. "
                           "Please set one plugin per resource type.")
                    raise exceptions.PluginConfigurationError(error=msg)

                plugins[plugin_obj.resource_type] = plugin_obj
        return plugins

    def _setup_actions(self):
        """Setup actions for each resource type supported.

        BasePlugin interface provides only on_start and on_end behaviour now.
        If there are some configs needed by plugin, they should be returned
        from get_plugin_opts method. These flags are registered in
        [resource_type] group of configuration file.
        """
        actions = {}

        for resource_type, plugin in self.plugins.items():
            plugin = self.plugins[resource_type]
            CONF.register_opts(plugin.get_plugin_opts(), group=resource_type)

            actions[resource_type] = {}
            actions[resource_type]['on_start'] = plugin.on_start
            actions[resource_type]['on_end'] = plugin.on_end
            actions[resource_type]['before_end'] = plugin.before_end
            plugin.setup(None)
        return actions

    @service_utils.with_empty_context
    def _process_events_concurrently(self, events):
        if not events:
            return

        LOG.info("Trying to execute events: %s", events)
        event_threads = {}
        for event in events:
            if not status.LeaseStatus.is_stable(event['lease_id']):
                LOG.info("Skip event %s because the status of the lease %s "
                         "is still transitional", event, event['lease_id'])
                continue
            db_api.event_update(event['id'],
                                {'status': status.event.IN_PROGRESS})
            try:
                event_thread = eventlet.spawn(
                    service_utils.with_empty_context(self._exec_event),
                    event)
                event_threads[event['id']] = event_thread
            except Exception:
                db_api.event_update(event['id'],
                                    {'status': status.event.ERROR})
                LOG.exception('Error occurred while spawning event %s.',
                              event['id'])

        for event_id, event_thread in event_threads.items():
            try:
                event_thread.wait()
            except Exception:
                db_api.event_update(event['id'],
                                    {'status': status.event.ERROR})
                LOG.exception('Error occurred while handling event %s.',
                              event_id)

    def _select_for_execution(self, events):
        """Orders the events such that they can be safely executed concurrently.

        Events are selected to be executed concurrently if they are of the same
        type, while keeping strict time ordering and the following priority of
        event types: before_end_lease, end_lease, and start_lease (except for
        before_end_lease events where there is a start_lease event for the same
        lease at the same time).

        We ensure that:

        - the before_end_lease event of a lease is executed after the
          start_lease event and before the end_lease event of the same lease,
        - for two reservations using the same hosts back to back, the end_lease
          event is executed before the start_lease event.
        """
        if not events:
            return []

        events_by_lease = defaultdict(list)
        events_by_type = defaultdict(list)

        for e in sorted(events, key=itemgetter('time')):
            events_by_lease[e['lease_id']].append(e)
            events_by_type[e['event_type']].append(e)

        # If there is a start_lease event for the same lease, we run it first.
        deferred_before_end_events = []
        deferred_end_events = []
        for start_event in events_by_type['start_lease']:
            for e in events_by_lease[start_event['lease_id']]:
                if e['event_type'] == 'before_end_lease':
                    events_by_type['before_end_lease'].remove(e)
                    deferred_before_end_events.append(e)
                elif e['event_type'] == 'end_lease':
                    events_by_type['end_lease'].remove(e)
                    deferred_end_events.append(e)

        return [
            events_by_type['before_end_lease'],
            events_by_type['end_lease'],
            events_by_type['start_lease'],
            deferred_before_end_events,
            deferred_end_events
        ]

    def _process_events(self):
        """Tries to execute events.

        If there is any event in Blazar DB to be executed, do it and change its
        status to 'DONE'. Events are executed concurrently if possible.
        """
        LOG.debug('Trying to get events from DB.')
        events = db_api.event_get_all_sorted_by_filters(
            sort_key='time',
            sort_dir='asc',
            filters={'status': status.event.UNDONE,
                     'time': {'op': 'le',
                              'border': datetime.datetime.utcnow()}}
        )

        for batch in self._select_for_execution(events):
            self._process_events_concurrently(batch)

    def _exec_event(self, event):
        """Execute an event function"""
        event_fn = getattr(self, event['event_type'], None)
        if event_fn is None:
            raise exceptions.EventError(
                error='Event type %s is not supported'
                      % event['event_type'])
        try:
            event_fn(lease_id=event['lease_id'], event_id=event['id'])
        except common_ex.InvalidStatus:
            now = datetime.datetime.utcnow()
            if now < event['time'] + datetime.timedelta(
                    seconds=CONF.manager.event_max_retries * 10):
                # Set the event status UNDONE for retrying the event
                db_api.event_update(event['id'],
                                    {'status': status.event.UNDONE})
            else:
                db_api.event_update(event['id'],
                                    {'status': status.event.ERROR})
                LOG.exception('Error occurred while handling %s event for '
                              'lease %s.', event['event_type'],
                              event['lease_id'])
        except Exception:
            db_api.event_update(event['id'],
                                {'status': status.event.ERROR})
            LOG.exception('Error occurred while handling %s event for '
                          'lease %s.', event['event_type'], event['lease_id'])
        else:
            lease = db_api.lease_get(event['lease_id'])
            with trusts.create_ctx_from_trust(lease['trust_id']) as ctx:
                self._send_notification(
                    lease, ctx, events=['event.%s' % event['event_type']])

    def _date_from_string(self, date_string, date_format=LEASE_DATE_FORMAT):
        try:
            date = datetime.datetime.strptime(date_string, date_format)
        except ValueError:
            raise exceptions.InvalidDate(date=date_string,
                                         date_format=date_format)
        return date

    def _parse_lease_dates(self, start_date, end_date):
        now = datetime.datetime.utcnow()
        now = datetime.datetime(now.year,
                                now.month,
                                now.day,
                                now.hour,
                                now.minute)
        if start_date == 'now':
            start_date = now
        else:
            start_date = self._date_from_string(start_date)

        if end_date == 'now':
            end_date = now
        else:
            end_date = self._date_from_string(end_date)

        return start_date, end_date, now

    def _check_for_invalid_date_inputs(self, lease, values, now):
        if (lease['start_date'] < now and
                values['start_date'] != lease['start_date']):
            raise common_ex.InvalidInput(
                'Cannot modify the start date of already started leases')

        if (lease['start_date'] > now and
                values['start_date'] < now):
            raise common_ex.InvalidInput(
                'Start date must be later than current date')

        if lease['end_date'] < now:
            raise common_ex.InvalidInput(
                'Terminated leases can only be renamed')

        if (values['end_date'] < now or
           values['end_date'] < values['start_date']):
            raise common_ex.InvalidInput(
                'End date must be later than current and start date')

    def validate_params(self, values, required_params):
        if isinstance(required_params, list):
            required_params = set(required_params)
        missing_attr = required_params - set(values.keys())
        if missing_attr:
            raise exceptions.MissingParameter(param=', '.join(missing_attr))

    def get_lease(self, lease_id):
        return db_api.lease_get(lease_id)

    def list_leases(self, project_id=None, query=None):
        return db_api.lease_list(project_id)

    def create_lease(self, lease_values):
        """Create a lease with reservations.

        Return either the model of created lease or None if any error.
        """
        lease_values['status'] = status.lease.CREATING

        try:
            trust_id = lease_values.pop('trust_id')
        except KeyError:
            raise exceptions.MissingTrustId()

        self.validate_params(lease_values, ['name', 'start_date', 'end_date'])

        # Remove and keep event and reservation values
        events = lease_values.pop("events", [])
        reservations = lease_values.pop("reservations", [])
        for res in reservations:
            self.validate_params(res, ['resource_type'])

        # Create the lease without the reservations
        start_date, end_date, now = self._parse_lease_dates(
            lease_values['start_date'], lease_values['end_date'])

        if start_date < now:
            raise common_ex.InvalidInput(
                'Start date must be later than current date')

        if end_date <= start_date:
            raise common_ex.InvalidInput(
                'End date must be later than start date.')

        with trusts.create_ctx_from_trust(trust_id) as ctx:
            # NOTE(priteau): We should not get user_id from ctx, because we are
            # in the context of the trustee (blazar user).
            # lease_values['user_id'] is set in blazar/api/v1/service.py
            lease_values['project_id'] = ctx.project_id
            lease_values['start_date'] = start_date
            lease_values['end_date'] = end_date

            allocations = self._allocation_candidates(
                lease_values, reservations)
            try:
                self.enforcement.check_create(
                    context.current(), lease_values, reservations, allocations)
            except common_ex.NotAuthorized as e:
                LOG.error("Enforcement checks failed. %s", str(e))
                raise common_ex.NotAuthorized(e)

            events.append({'event_type': 'start_lease',
                           'time': start_date,
                           'status': status.event.UNDONE})
            events.append({'event_type': 'end_lease',
                           'time': end_date,
                           'status': status.event.UNDONE})

            before_end_date = lease_values.get('before_end_date', None)
            if before_end_date:
                # incoming param. Validation check
                try:
                    before_end_date = self._date_from_string(
                        before_end_date)
                    self._check_date_within_lease_limits(before_end_date,
                                                         lease_values)
                except common_ex.BlazarException as e:
                    LOG.error("Invalid before_end_date param. %s", str(e))
                    raise e
            elif CONF.manager.minutes_before_end_lease > 0:
                delta = datetime.timedelta(
                    minutes=CONF.manager.minutes_before_end_lease)
                before_end_date = lease_values['end_date'] - delta

            if before_end_date:
                event = {'event_type': 'before_end_lease',
                         'status': status.event.UNDONE}
                events.append(event)
                self._update_before_end_event_date(event, before_end_date,
                                                   lease_values)

            try:
                if trust_id:
                    lease_values.update({'trust_id': trust_id})
                lease = db_api.lease_create(lease_values)
                lease_id = lease['id']
            except db_ex.BlazarDBDuplicateEntry:
                LOG.exception('Cannot create a lease - duplicated lease name')
                raise exceptions.LeaseNameAlreadyExists(
                    name=lease_values['name'])
            except db_ex.BlazarDBException:
                with save_and_reraise_exception():
                    LOG.exception('Cannot create a lease')
            else:
                try:
                    for reservation in reservations:
                        reservation['lease_id'] = lease['id']
                        reservation['start_date'] = lease['start_date']
                        reservation['end_date'] = lease['end_date']
                        self._create_reservation(reservation)
                except Exception:
                    with save_and_reraise_exception():
                        LOG.exception("Failed to create reservation for a "
                                      "lease. Rollback the lease and "
                                      "associated reservations")
                        db_api.lease_destroy(lease_id)

                try:
                    for event in events:
                        event['lease_id'] = lease['id']
                        db_api.event_create(event)
                except (exceptions.UnsupportedResourceType,
                        common_ex.BlazarException):
                    with save_and_reraise_exception():
                        LOG.exception("Failed to create event for a lease. "
                                      "Rollback the lease and associated "
                                      "reservations")
                        db_api.lease_destroy(lease_id)

                else:
                    db_api.lease_update(
                        lease_id,
                        {'status': status.lease.PENDING})
                    lease = db_api.lease_get(lease_id)
                    self._send_notification(lease, ctx, events=['create'])
                    return lease

    def _add_resource_type(self, reservations, existing_reservations):
        rsvns_by_id = {}

        for r in existing_reservations:
            rsvns_by_id[r['id']] = r
        for r in reservations:
            if 'resource_type' not in r:
                r['resource_type'] = rsvns_by_id[r['id']]['resource_type']

        return reservations

    @status.lease.lease_status(
        transition=status.lease.UPDATING,
        result_in=status.lease.STABLE,
        non_fatal_exceptions=[
            common_ex.InvalidInput,
            exceptions.InvalidRange,
            exceptions.MissingParameter,
            exceptions.MalformedRequirements,
            exceptions.MalformedParameter,
            exceptions.NotEnoughHostsAvailable,
            exceptions.InvalidDate,
            exceptions.CantUpdateParameter,
            exceptions.InvalidPeriod,
            enforcement.exceptions.MaxLeaseDurationException,
            enforcement.exceptions.ExternalServiceFilterException,
        ]
    )
    def update_lease(self, lease_id, values):
        if not values:
            return db_api.lease_get(lease_id)

        if len(values) == 1 and 'name' in values:
            db_api.lease_update(lease_id, values)
            return db_api.lease_get(lease_id)

        lease = db_api.lease_get(lease_id)
        start_date = values.get(
            'start_date',
            datetime.datetime.strftime(lease['start_date'], LEASE_DATE_FORMAT))
        end_date = values.get(
            'end_date',
            datetime.datetime.strftime(lease['end_date'], LEASE_DATE_FORMAT))
        before_end_date = values.get('before_end_date', None)

        start_date, end_date, now = self._parse_lease_dates(start_date,
                                                            end_date)

        values['start_date'] = start_date
        values['end_date'] = end_date

        self._check_for_invalid_date_inputs(lease, values, now)

        with trusts.create_ctx_from_trust(lease['trust_id']):
            if before_end_date:
                try:
                    before_end_date = self._date_from_string(before_end_date)
                    self._check_date_within_lease_limits(before_end_date,
                                                         values)
                except common_ex.BlazarException as e:
                    LOG.error("Invalid before_end_date param. %s", str(e))
                    raise e

            reservations = values.get('reservations', [])
            existing_reservations = (
                db_api.reservation_get_all_by_lease_id(lease_id))

            try:
                invalid_ids = set([r['id'] for r in reservations]).difference(
                    [r['id'] for r in existing_reservations])
            except KeyError:
                raise exceptions.MissingParameter(param='reservation ID')

            if invalid_ids:
                raise common_ex.InvalidInput(
                    'Please enter valid reservation IDs. Invalid reservation '
                    'IDs are: %s' % ','.join([str(id) for id in invalid_ids]))

            # Populate resource_type if missing from data passed by client
            reservations = self._add_resource_type(reservations,
                                                   existing_reservations)

            try:
                [
                    self.plugins[r['resource_type']] for r
                    in (reservations + existing_reservations)]
            except KeyError:
                raise exceptions.CantUpdateParameter(param='resource_type')

            existing_allocs = self._existing_allocations(existing_reservations)

            if reservations:
                new_reservations = reservations
                new_allocs = self._allocation_candidates(values,
                                                         existing_reservations)
            else:
                # User is not updating reservation parameters, e.g., is only
                # adjusting lease start/end dates.
                new_reservations = existing_reservations
                new_allocs = existing_allocs

            try:
                self.enforcement.check_update(context.current(), lease, values,
                                              existing_allocs, new_allocs,
                                              existing_reservations,
                                              new_reservations)
            except common_ex.NotAuthorized as e:
                LOG.error("Enforcement checks failed. %s", str(e))
                raise e

            # TODO(frossigneux) rollback if an exception is raised
            for reservation in existing_reservations:
                v = {}
                v['start_date'] = values['start_date']
                v['end_date'] = values['end_date']
                try:
                    v.update([r for r in reservations
                              if r['id'] == reservation['id']].pop())
                except IndexError:
                    pass
                resource_type = v.get('resource_type',
                                      reservation['resource_type'])

                if resource_type != reservation['resource_type']:
                    raise exceptions.CantUpdateParameter(
                        param='resource_type')
                self.plugins[resource_type].update_reservation(
                    reservation['id'], v)

        event = db_api.event_get_first_sorted_by_filters(
            'lease_id',
            'asc',
            {
                'lease_id': lease_id,
                'event_type': 'start_lease'
            }
        )
        if not event:
            raise common_ex.BlazarException(
                'Start lease event not found')
        db_api.event_update(event['id'], {'time': values['start_date']})

        event = db_api.event_get_first_sorted_by_filters(
            'lease_id',
            'asc',
            {
                'lease_id': lease_id,
                'event_type': 'end_lease'
            }
        )
        if not event:
            raise common_ex.BlazarException(
                'End lease event not found')
        db_api.event_update(event['id'], {'time': values['end_date']})

        notifications = ['update']
        self._update_before_end_event(lease, values, notifications,
                                      before_end_date)

        try:
            del values['reservations']
        except KeyError:
            pass
        db_api.lease_update(lease_id, values)

        lease = db_api.lease_get(lease_id)
        with trusts.create_ctx_from_trust(lease['trust_id']) as ctx:
            self._send_notification(lease, ctx, events=notifications)

        return lease

    @status.lease.lease_status(transition=status.lease.DELETING,
                               result_in=(status.lease.ERROR,))
    def delete_lease(self, lease_id):
        lease = self.get_lease(lease_id)

        start_event = db_api.event_get_first_sorted_by_filters(
            'lease_id',
            'asc',
            {
                'lease_id': lease_id,
                'event_type': 'start_lease',
            }
        )
        if not start_event:
            raise common_ex.BlazarException(
                'start_lease event for lease %s not found' % lease_id)

        end_event = db_api.event_get_first_sorted_by_filters(
            'lease_id',
            'asc',
            {
                'lease_id': lease_id,
                'event_type': 'end_lease',
            }
        )
        if not end_event:
            raise common_ex.BlazarException(
                'end_lease event for lease %s not found' % lease_id)

        lease_already_started = start_event['status'] != status.event.UNDONE
        lease_not_started = not lease_already_started
        lease_already_ended = end_event['status'] != status.event.UNDONE
        lease_not_ended = not lease_already_ended

        end_lease = lease_already_started and lease_not_ended

        if end_lease:
            db_api.event_update(end_event['id'],
                                {'status': status.event.IN_PROGRESS})

        with trusts.create_ctx_from_trust(lease['trust_id']) as ctx:
            reservations = lease['reservations']

            if lease_not_started or lease_not_ended:
                # Only run the on_end enforcement if we're explicitly
                # ending the lease for the first time OR if we're terminating
                # it before the lease ever started. It's important to run
                # on_end in the second case to inform enforcement that the
                # lease is no longer in play.
                allocations = self._existing_allocations(reservations)
                try:
                    self.enforcement.on_end(ctx, lease, allocations)
                except Exception as e:
                    LOG.error(e)

            for reservation in reservations:
                if reservation['status'] != status.reservation.DELETED:
                    plugin = self.plugins[reservation['resource_type']]
                    try:
                        plugin.on_end(reservation['resource_id'])
                    except (db_ex.BlazarDBException, RuntimeError):
                        with save_and_reraise_exception():
                            LOG.exception("Failed to delete a reservation "
                                          "for a lease.")
            db_api.lease_destroy(lease_id)
            self._send_notification(lease, ctx, events=['delete'])

    @status.lease.lease_status(
        transition=status.lease.STARTING,
        result_in=(status.lease.ACTIVE, status.lease.ERROR))
    def start_lease(self, lease_id, event_id):
        lease = self.get_lease(lease_id)
        with trusts.create_ctx_from_trust(lease['trust_id']):
            self._basic_action(lease_id, event_id, 'on_start',
                               status.reservation.ACTIVE)

    @status.lease.lease_status(
        transition=status.lease.TERMINATING,
        result_in=(status.lease.TERMINATED, status.lease.ERROR))
    def end_lease(self, lease_id, event_id):
        lease = self.get_lease(lease_id)

        with trusts.create_ctx_from_trust(lease['trust_id']) as ctx:
            allocations = self._existing_allocations(lease['reservations'])
            try:
                self.enforcement.on_end(ctx, lease, allocations)
            except Exception as e:
                LOG.error(e)

            self._basic_action(lease_id, event_id, 'on_end',
                               status.reservation.DELETED)

    def before_end_lease(self, lease_id, event_id):
        lease = self.get_lease(lease_id)
        with trusts.create_ctx_from_trust(lease['trust_id']):
            self._basic_action(lease_id, event_id, 'before_end')

    def _basic_action(self, lease_id, event_id, action_time,
                      reservation_status=None):
        """Commits basic lease actions such as starting and ending."""
        lease = self.get_lease(lease_id)

        event_status = status.event.DONE
        for reservation in lease['reservations']:
            resource_type = reservation['resource_type']
            try:
                if reservation_status is not None:
                    if not status.reservation.is_valid_transition(
                            reservation['status'], reservation_status):
                        raise common_ex.InvalidStatus
                self.resource_actions[resource_type][action_time](
                    reservation['resource_id']
                )
            except common_ex.BlazarException:
                LOG.exception("Failed to execute action %(action)s "
                              "for lease %(lease)s",
                              {'action': action_time,
                               'lease': lease_id})
                event_status = status.event.ERROR
                db_api.reservation_update(
                    reservation['id'],
                    {'status': status.reservation.ERROR})
            else:
                if reservation_status is not None:
                    db_api.reservation_update(reservation['id'],
                                              {'status': reservation_status})

        db_api.event_update(event_id, {'status': event_status})

        return event_status

    def _create_reservation(self, values):
        resource_type = values['resource_type']
        if resource_type not in self.plugins:
            raise exceptions.UnsupportedResourceType(
                resource_type=resource_type)
        reservation_values = {
            'lease_id': values['lease_id'],
            'resource_type': resource_type,
            'status': status.reservation.PENDING
        }
        reservation = db_api.reservation_create(reservation_values)
        resource_id = self.plugins[resource_type].reserve_resource(
            reservation['id'],
            values
        )
        db_api.reservation_update(reservation['id'],
                                  {'resource_id': resource_id})

    def _allocation_candidates(self, lease, reservations):
        """Returns dict by resource type of reservation candidates."""
        allocations = {}

        for reservation in reservations:
            res = reservation.copy()
            resource_type = reservation['resource_type']
            res['start_date'] = lease['start_date']
            res['end_date'] = lease['end_date']

            if resource_type not in self.plugins:
                raise exceptions.UnsupportedResourceType(
                    resource_type=resource_type)

            plugin = self.plugins.get(resource_type)

            if not plugin:
                raise common_ex.BlazarException(
                    'Invalid plugin names are specified: %s' % resource_type)

            candidate_ids = plugin.allocation_candidates(res)

            allocations[resource_type] = [
                plugin.get(cid) for cid in candidate_ids]

        return allocations

    def _existing_allocations(self, reservations):
        allocations = {}

        for reservation in reservations:
            resource_type = reservation['resource_type']

            if resource_type not in self.plugins:
                raise exceptions.UnsupportedResourceType(
                    resource_type=resource_type)

            plugin = self.plugins.get(resource_type)

            if not plugin:
                raise common_ex.BlazarException(
                    'Invalid plugin names are specified: %s' % resource_type)

            resource_ids = [
                x['resource_id'] for x in plugin.list_allocations(
                    dict(reservation_id=reservation['id']))
                if x['reservations']]

            allocations[resource_type] = [
                plugin.get(rid) for rid in resource_ids]

        return allocations

    def _send_notification(self, lease, ctx, events=[]):
        payload = notification_api.format_lease_payload(lease)

        for event in events:
            notification_api.send_lease_notification(ctx, payload,
                                                     'lease.%s' % event)

    def _check_date_within_lease_limits(self, date, lease):
        if not lease['start_date'] < date < lease['end_date']:
            raise common_ex.NotAuthorized(
                'Datetime is out of lease limits')

    def _update_before_end_event_date(self, event, before_end_date, lease):
        event['time'] = before_end_date
        if event['time'] < lease['start_date']:
            LOG.warning("Start_date greater than before_end_date. "
                        "Setting before_end_date to %(start_date)s for "
                        "lease %(id_name)s",
                        {'start_date': lease['start_date'],
                         'id_name': lease.get('id', lease.get('name'))})
            event['time'] = lease['start_date']

    def _update_before_end_event(self, old_lease, new_lease,
                                 notifications, before_end_date=None):
        event = db_api.event_get_first_sorted_by_filters(
            'lease_id',
            'asc',
            {
                'lease_id': old_lease['id'],
                'event_type': 'before_end_lease'
            }
        )
        if event:
            # NOTE(casanch1) do nothing if the event does not exist.
            # This is for backward compatibility
            update_values = {}
            if not before_end_date:
                # before_end_date needs to be calculated based on
                # previous delta
                prev_before_end_delta = old_lease['end_date'] - event['time']
                before_end_date = new_lease['end_date'] - prev_before_end_delta

            self._update_before_end_event_date(update_values, before_end_date,
                                               new_lease)
            if event['status'] == status.event.DONE:
                update_values['status'] = status.event.UNDONE
                notifications.append('event.before_end_lease.stop')

            db_api.event_update(event['id'], update_values)

    def __getattr__(self, name):
        """RPC Dispatcher for plugins methods."""

        fn = None
        try:
            resource_type, method = name.rsplit(':', 1)
        except ValueError:
            # NOTE(sbauza) : the dispatcher needs to know which plugin to use,
            #  raising error if consequently not
            raise AttributeError(name)
        try:
            try:
                fn = getattr(self.plugins[resource_type], method)
            except KeyError:
                LOG.error("Plugin with resource type %s not found",
                          resource_type)
                raise exceptions.UnsupportedResourceType(
                    resource_type=resource_type)
        except AttributeError:
            LOG.error("Plugin %s doesn't include method %s",
                      self.plugins[resource_type], method)
        if fn is not None:
            return fn
        raise AttributeError(name)
