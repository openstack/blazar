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

import datetime
import eventlet
import six

from oslo.config import cfg
from stevedore import enabled

from climate import context
from climate.db import api as db_api
from climate import exceptions as common_ex
from climate import manager
from climate.manager import exceptions
from climate.openstack.common.gettextutils import _  # noqa
from climate.openstack.common import log as logging
from climate.openstack.common import service
from climate.utils import service as service_utils
from climate.utils import trusts

manager_opts = [
    cfg.ListOpt('plugins',
                default=['dummy.vm.plugin'],
                help='All plugins to use (one for every resource type to '
                     'support.)'),
]

CONF = cfg.CONF
CONF.register_opts(manager_opts, 'manager')
LOG = logging.getLogger(__name__)

LEASE_DATE_FORMAT = "%Y-%m-%d %H:%M"


class ManagerService(service_utils.RPCServer, service.Service):
    """Service class for the climate-manager service.

    Responsible for working with Climate DB, scheduling logic, running events,
    working with plugins, etc.
    """

    def __init__(self):
        target = manager.get_target()
        super(ManagerService, self).__init__(target)
        self.plugins = self._get_plugins()
        self.resource_actions = self._setup_actions()

    def start(self):
        super(ManagerService, self).start()
        self.tg.add_timer(10, self._event)

    def _get_plugins(self):
        """Return dict of resource-plugin class pairs."""
        config_plugins = CONF.manager.plugins
        plugins = {}

        extension_manager = enabled.EnabledExtensionManager(
            check_func=lambda ext: ext.name in config_plugins,
            namespace='climate.resource.plugins',
            invoke_on_load=True
        )

        for ext in extension_manager.extensions:
            if ext.obj.resource_type in plugins:
                msg = "You have provided several plugins for " \
                      "one resource type in configuration file. " \
                      "Please set one plugin per resource type."
                raise exceptions.PluginConfigurationError(error=msg)

            plugins[ext.obj.resource_type] = ext.obj

        if len(plugins) < len(config_plugins):
            msg = 'Not all requested plugins are loaded.'
            raise exceptions.PluginConfigurationError(error=msg)

        return plugins

    def _setup_actions(self):
        """Setup actions for each resource type supported.

        BasePlugin interface provides only on_start and on_end behaviour now.
        If there are some configs needed by plugin, they should be returned
        from get_plugin_opts method. These flags are registered in
        [resource_type] group of configuration file.
        """
        actions = {}

        for resource_type, plugin in six.iteritems(self.plugins):
            plugin = self.plugins[resource_type]
            CONF.register_opts(plugin.get_plugin_opts(), group=resource_type)

            actions[resource_type] = {}
            actions[resource_type]['on_start'] = plugin.on_start
            actions[resource_type]['on_end'] = plugin.on_end
            plugin.setup(None)
        return actions

    @service_utils.with_empty_context
    def _event(self):
        """Tries to commit event.

        If there is an event in Climate DB to be done, do it and change its
        status to 'DONE'.
        """
        LOG.debug(_('Trying to get event from DB.'))
        events = db_api.event_get_all_sorted_by_filters(
            sort_key='time',
            sort_dir='asc',
            filters={'status': 'UNDONE'}
        )

        if not events:
            return

        event = events[0]

        if event['time'] < datetime.datetime.utcnow():
            db_api.event_update(event['id'], {'status': 'IN_PROGRESS'})
            event_type = event['event_type']
            event_fn = getattr(self, event_type, None)
            if event_fn is None:
                raise exceptions.EventError(error='Event type %s is not '
                                                  'supported' % event_type)
            try:
                eventlet.spawn_n(service_utils.with_empty_context(event_fn),
                                 event['lease_id'], event['id'])
            except Exception:
                db_api.event_update(event['id'], {'status': 'ERROR'})
                LOG.exception(_('Error occurred while event handling.'))

    def _date_from_string(self, date_string, date_format=LEASE_DATE_FORMAT):
        try:
            date = datetime.datetime.strptime(date_string, date_format)
        except ValueError:
            raise exceptions.InvalidDate(date=date_string,
                                         date_format=date_format)

        return date

    def get_lease(self, lease_id):
        return db_api.lease_get(lease_id)

    def list_leases(self):
        return db_api.lease_list()

    def create_lease(self, lease_values):
        """Create a lease with reservations.

        Return either the model of created lease or None if any error.
        """
        # Remove and keep reservation values
        reservations = lease_values.pop("reservations", [])

        # Create the lease without the reservations
        start_date = lease_values['start_date']
        end_date = lease_values['end_date']

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
        end_date = self._date_from_string(end_date)

        if start_date < now:
            raise common_ex.NotAuthorized(
                'Start date must later than current date')

        ctx = context.current()
        lease_values['user_id'] = ctx.user_id
        lease_values['tenant_id'] = ctx.tenant_id
        lease_values['start_date'] = start_date
        lease_values['end_date'] = end_date

        if not lease_values.get('events'):
            lease_values['events'] = []

        lease_values['events'].append({'event_type': 'start_lease',
                                       'time': start_date,
                                       'status': 'UNDONE'})
        lease_values['events'].append({'event_type': 'end_lease',
                                       'time': end_date,
                                       'status': 'UNDONE'})

        #TODO(scroiset): catch DB Exception when they will become alive
        # see bug #1237293
        try:
            lease = db_api.lease_create(lease_values)
            lease_id = lease['id']
        except RuntimeError:
            LOG.exception('Cannot create a lease')
        else:
            try:
                for reservation in reservations:
                    reservation['lease_id'] = lease['id']
                    reservation['start_date'] = lease['start_date']
                    reservation['end_date'] = lease['end_date']
                    resource_type = reservation['resource_type']
                    self.plugins[resource_type].create_reservation(reservation)
            except RuntimeError:
                LOG.exception("Failed to create reservation for a lease. "
                              "Rollback the lease and associated reservations")
                db_api.lease_destroy(lease_id)
            else:
                return db_api.lease_get(lease['id'])

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
        end_date = self._date_from_string(end_date)

        values['start_date'] = start_date
        values['end_date'] = end_date

        if (lease['start_date'] < now and
                values['start_date'] != lease['start_date']):
            raise common_ex.NotAuthorized(
                'Cannot modify the start date of already started leases')

        if (lease['start_date'] > now and
                values['start_date'] < now):
            raise common_ex.NotAuthorized(
                'Start date must later than current date')

        if lease['end_date'] < now:
            raise common_ex.NotAuthorized(
                'Terminated leases can only be renamed')

        if (values['end_date'] < now or
           values['end_date'] < values['start_date']):
            raise common_ex.NotAuthorized(
                'End date must be later than current and start date')

        #TODO(frossigneux) rollback if an exception is raised
        for reservation in \
                db_api.reservation_get_all_by_lease_id(lease_id):
            reservation['start_date'] = values['start_date']
            reservation['end_date'] = values['end_date']
            resource_type = reservation['resource_type']
            self.plugins[resource_type].update_reservation(
                reservation['id'],
                reservation)

        events = db_api.event_get_all_sorted_by_filters(
            'lease_id',
            'asc',
            {
                'lease_id': lease_id,
                'event_type': 'start_lease'
            }
        )
        if len(events) != 1:
            raise common_ex.ClimateException(
                'Start lease event not found')
        event = events[0]
        db_api.event_update(event['id'], {'time': values['start_date']})

        events = db_api.event_get_all_sorted_by_filters(
            'lease_id',
            'asc',
            {
                'lease_id': lease_id,
                'event_type': 'end_lease'
            }
        )
        if len(events) != 1:
            raise common_ex.ClimateException(
                'End lease event not found')
        event = events[0]
        db_api.event_update(event['id'], {'time': values['end_date']})

        db_api.lease_update(lease_id, values)
        return db_api.lease_get(lease_id)

    def delete_lease(self, lease_id):
        lease = self.get_lease(lease_id)
        if (datetime.datetime.utcnow() < lease['start_date'] or
                datetime.datetime.utcnow() > lease['end_date']):
            with trusts.create_ctx_from_trust(lease['trust_id']):
                for reservation in lease['reservations']:
                    try:
                        self.plugins[reservation['resource_type']]\
                            .on_end(reservation['resource_id'])
                    except RuntimeError:
                        LOG.exception("Failed to delete a reservation")
                db_api.lease_destroy(lease_id)
        else:
            raise common_ex.NotAuthorized(
                'Already started lease cannot be deleted')

    def start_lease(self, lease_id, event_id):
        lease = self.get_lease(lease_id)
        with trusts.create_ctx_from_trust(lease['trust_id']):
            self._basic_action(lease_id, event_id, 'on_start', 'active')

    def end_lease(self, lease_id, event_id):
        lease = self.get_lease(lease_id)
        with trusts.create_ctx_from_trust(lease['trust_id']):
            self._basic_action(lease_id, event_id, 'on_end', 'deleted')

    def _basic_action(self, lease_id, event_id, action_time,
                      reservation_status=None):
        """Commits basic lease actions such as starting and ending."""
        lease = self.get_lease(lease_id)

        for reservation in lease['reservations']:
            resource_type = reservation['resource_type']
            try:
                self.resource_actions[resource_type][action_time](
                    reservation['resource_id']
                )
            except common_ex.ClimateException:
                LOG.exception("Failed to execute action %(action)s "
                              "for lease %(lease)d"
                              % {
                                  'action': action_time,
                                  'lease': lease_id,
                              })

            if reservation_status is not None:
                db_api.reservation_update(reservation['id'],
                                          {'status': reservation_status})

        db_api.event_update(event_id, {'status': 'DONE'})

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
        except AttributeError:
            LOG.error("Plugin %s doesn't include method %s",
                      self.plugins[resource_type], method)
        if fn is not None:
            return fn
        raise AttributeError(name)
