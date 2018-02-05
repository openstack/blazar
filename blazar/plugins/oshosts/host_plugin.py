# -*- coding: utf-8 -*-
#
# Author: François Rossigneux <francois.rossigneux@inria.fr>
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import datetime

from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import strutils

from blazar.db import api as db_api
from blazar.db import exceptions as db_ex
from blazar.db import utils as db_utils
from blazar.manager import exceptions as manager_ex
from blazar.plugins import base
from blazar.plugins import oshosts as plugin
from blazar import status
from blazar.utils.openstack import nova
from blazar.utils import plugins as plugins_utils
from blazar.utils import trusts

plugin_opts = [
    cfg.StrOpt('on_end',
               default='on_end',
               deprecated_for_removal=True,
               deprecated_since='0.3.0',
               help='Actions which we will use in the end of the lease'),
    cfg.StrOpt('on_start',
               default='on_start',
               deprecated_for_removal=True,
               deprecated_since='0.3.0',
               help='Actions which we will use at the start of the lease'),
    cfg.StrOpt('blazar_az_prefix',
               default='blazar_',
               deprecated_name='climate_az_prefix',
               help='Prefix for Availability Zones created by Blazar'),
    cfg.StrOpt('before_end',
               default='',
               help='Actions which we will be taken before the end of '
                    'the lease'),
    cfg.BoolOpt('enable_notification_monitor',
                default=False,
                help='Enable notification-based resource monitoring. '
                     'If it is enabled, the blazar-manager monitors states of '
                     'compute hosts by subscribing to notifications of Nova.'),
    cfg.ListOpt('notification_topics',
                default=['notifications', 'versioned_notifications'],
                help='Notification topics to subscribe to.'),
    cfg.BoolOpt('enable_polling_monitor',
                default=False,
                help='Enable polling-based resource monitoring. '
                     'If it is enabled, the blazar-manager monitors states '
                     'of compute hosts by polling the Nova API.'),
    cfg.IntOpt('polling_interval',
               default=60,
               help='Interval (seconds) of polling for health checking.'),
]

CONF = cfg.CONF
CONF.register_opts(plugin_opts, group=plugin.RESOURCE_TYPE)
LOG = logging.getLogger(__name__)

before_end_options = ['', 'snapshot', 'default']


class PhysicalHostPlugin(base.BasePlugin, nova.NovaClientWrapper):
    """Plugin for physical host resource."""
    resource_type = plugin.RESOURCE_TYPE
    title = 'Physical Host Plugin'
    description = 'This plugin starts and shutdowns the hosts.'
    freepool_name = CONF.nova.aggregate_freepool_name
    pool = None

    def __init__(self):
        super(PhysicalHostPlugin, self).__init__(
            username=CONF.os_admin_username,
            password=CONF.os_admin_password,
            user_domain_name=CONF.os_admin_user_domain_name,
            project_name=CONF.os_admin_project_name,
            project_domain_name=CONF.os_admin_user_domain_name)
        self.monitor = PhysicalHostMonitorPlugin()
        self.monitor.register_healing_handler(self.heal_reservations)

    def reserve_resource(self, reservation_id, values):
        """Create reservation."""
        self._check_params(values)

        host_ids = self._matching_hosts(
            values['hypervisor_properties'],
            values['resource_properties'],
            values['count_range'],
            values['start_date'],
            values['end_date'],
        )
        if not host_ids:
            raise manager_ex.NotEnoughHostsAvailable()
        pool = nova.ReservationPool()
        pool_name = reservation_id
        az_name = "%s%s" % (CONF[self.resource_type].blazar_az_prefix,
                            pool_name)
        pool_instance = pool.create(name=pool_name, az=az_name)
        host_rsrv_values = {
            'reservation_id': reservation_id,
            'aggregate_id': pool_instance.id,
            'resource_properties': values['resource_properties'],
            'hypervisor_properties': values['hypervisor_properties'],
            'count_range': values['count_range'],
            'status': 'pending',
            'before_end': values['before_end']
        }
        host_reservation = db_api.host_reservation_create(host_rsrv_values)
        for host_id in host_ids:
            db_api.host_allocation_create({'compute_host_id': host_id,
                                          'reservation_id': reservation_id})
        return host_reservation['id']

    def update_reservation(self, reservation_id, values):
        """Update reservation."""
        reservation = db_api.reservation_get(reservation_id)
        lease = db_api.lease_get(reservation['lease_id'])

        if (not [x for x in values.keys() if x in ['min', 'max',
                                                   'hypervisor_properties',
                                                   'resource_properties']]
                and values['start_date'] >= lease['start_date']
                and values['end_date'] <= lease['end_date']):
            # Nothing to update
            return

        dates_before = {'start_date': lease['start_date'],
                        'end_date': lease['end_date']}
        dates_after = {'start_date': values['start_date'],
                       'end_date': values['end_date']}
        host_reservation = db_api.host_reservation_get(
            reservation['resource_id'])
        self._update_allocations(dates_before, dates_after, reservation_id,
                                 reservation['status'], host_reservation,
                                 values)

        updates = {}
        if 'min' in values or 'max' in values:
            count_range = str(values.get(
                'min', host_reservation['count_range'].split('-')[0])
            ) + '-' + str(values.get(
                'max', host_reservation['count_range'].split('-')[1])
            )
            updates['count_range'] = count_range
        if 'hypervisor_properties' in values:
            updates['hypervisor_properties'] = values.get(
                'hypervisor_properties')
        if 'resource_properties' in values:
            updates['resource_properties'] = values.get(
                'resource_properties')
        if updates:
            db_api.host_reservation_update(host_reservation['id'], updates)

    def on_start(self, resource_id):
        """Add the hosts in the pool."""
        host_reservation = db_api.host_reservation_get(resource_id)
        pool = nova.ReservationPool()
        for allocation in db_api.host_allocation_get_all_by_values(
                reservation_id=host_reservation['reservation_id']):
            host = db_api.host_get(allocation['compute_host_id'])
            pool.add_computehost(host_reservation['aggregate_id'],
                                 host['service_name'])

    def before_end(self, resource_id):
        """Take an action before the end of a lease."""
        host_reservation = db_api.host_reservation_get(resource_id)
        action = host_reservation['before_end']
        if action == 'default':
            action = CONF[plugin.RESOURCE_TYPE].before_end
        if action == 'snapshot':
            pool = nova.ReservationPool()
            client = nova.BlazarNovaClient()
            for host in pool.get_computehosts(
                    host_reservation['aggregate_id']):
                for server in client.servers.list(
                        search_opts={"host": host, "all_tenants": 1}):
                        client.servers.create_image(server=server)

    def on_end(self, resource_id):
        """Remove the hosts from the pool."""
        host_reservation = db_api.host_reservation_get(resource_id)
        db_api.host_reservation_update(host_reservation['id'],
                                       {'status': 'completed'})
        allocations = db_api.host_allocation_get_all_by_values(
            reservation_id=host_reservation['reservation_id'])
        for allocation in allocations:
            db_api.host_allocation_destroy(allocation['id'])
        pool = nova.ReservationPool()
        for host in pool.get_computehosts(host_reservation['aggregate_id']):
            for server in self.nova.servers.list(
                    search_opts={"host": host, "all_tenants": 1}):
                self.nova.servers.delete(server=server)
        try:
            pool.delete(host_reservation['aggregate_id'])
        except manager_ex.AggregateNotFound:
            pass

    def heal_reservations(self, failed_resources):
        """Heal reservations which suffer from resource failures.

        :param: failed_resources: a list of failed hosts.
        :return: a dictionary of {reservation id: flags to update}
                 e.g. {'de27786d-bd96-46bb-8363-19c13b2c6657':
                       {'missing_resources': True}}
        """
        reservation_flags = {}

        failed_allocs = []
        for host in failed_resources:
            failed_allocs += db_api.host_allocation_get_all_by_values(
                compute_host_id=host['id'])

        for alloc in failed_allocs:
            reservation = db_api.reservation_get(alloc['reservation_id'])
            if reservation['resource_type'] != plugin.RESOURCE_TYPE:
                continue
            lease = db_api.lease_get(reservation['lease_id'])
            host_reservation = None
            pool = None

            # Remove the failed host from the aggregate.
            if reservation['status'] == status.reservation.ACTIVE:
                host = db_api.host_get(alloc['compute_host_id'])
                host_reservation = db_api.host_reservation_get(
                    reservation['resource_id'])
                with trusts.create_ctx_from_trust(lease['trust_id']):
                    pool = nova.ReservationPool()
                    pool.remove_computehost(host_reservation['aggregate_id'],
                                            host['service_name'])

            # Allocate alternative resource.
            start_date = max(datetime.datetime.utcnow(), lease['start_date'])
            new_hostids = self._matching_hosts(
                reservation['hypervisor_properties'],
                reservation['resource_properties'],
                '1-1', start_date, lease['end_date']
            )
            if not new_hostids:
                if reservation['id'] not in reservation_flags:
                    reservation_flags[reservation['id']] = {}
                reservation_flags[reservation['id']].update(
                    {'missing_resources': True})
                db_api.host_allocation_destroy(alloc['id'])
                LOG.warn('Could not find alternative host for reservation %s '
                         '(lease: %s).', reservation['id'], lease['name'])
            else:
                new_hostid = new_hostids.pop()
                db_api.host_allocation_update(alloc['id'],
                                              {'compute_host_id': new_hostid})
                if reservation['status'] == status.reservation.ACTIVE:
                    # Add the alternative host into the aggregate.
                    new_host = db_api.host_get(new_hostid)
                    with trusts.create_ctx_from_trust(lease['trust_id']):
                        pool.add_computehost(host_reservation['aggregate_id'],
                                             new_host['service_name'])
                    if reservation['id'] not in reservation_flags:
                        reservation_flags[reservation['id']] = {}
                    reservation_flags[reservation['id']].update(
                        {'resources_changed': True})
                LOG.warn('Resource changed for reservation %s (lease: %s).',
                         reservation['id'], lease['name'])

        return reservation_flags

    def _get_extra_capabilities(self, host_id):
        extra_capabilities = {}
        raw_extra_capabilities = (
            db_api.host_extra_capability_get_all_per_host(host_id))
        for capability in raw_extra_capabilities:
            key = capability['capability_name']
            extra_capabilities[key] = capability['capability_value']
        return extra_capabilities

    def get_computehost(self, host_id):
        host = db_api.host_get(host_id)
        extra_capabilities = self._get_extra_capabilities(host_id)
        if host is not None and extra_capabilities:
            res = host.copy()
            res.update(extra_capabilities)
            return res
        else:
            return host

    def list_computehosts(self):
        raw_host_list = db_api.host_list()
        host_list = []
        for host in raw_host_list:
            host_list.append(self.get_computehost(host['id']))
        return host_list

    def create_computehost(self, host_values):
        # TODO(sbauza):
        #  - Exception handling for HostNotFound
        host_id = host_values.pop('id', None)
        host_name = host_values.pop('name', None)
        try:
            trust_id = host_values.pop('trust_id')
        except KeyError:
            raise manager_ex.MissingTrustId()

        host_ref = host_id or host_name
        if host_ref is None:
            raise manager_ex.InvalidHost(host=host_values)

        with trusts.create_ctx_from_trust(trust_id):
            inventory = nova.NovaInventory()
            servers = inventory.get_servers_per_host(host_ref)
            if servers:
                raise manager_ex.HostHavingServers(host=host_ref,
                                                   servers=servers)
            host_details = inventory.get_host_details(host_ref)
            # NOTE(sbauza): Only last duplicate name for same extra capability
            # will be stored
            to_store = set(host_values.keys()) - set(host_details.keys())
            extra_capabilities_keys = to_store
            extra_capabilities = dict(
                (key, host_values[key]) for key in extra_capabilities_keys
            )
            pool = nova.ReservationPool()
            pool.add_computehost(self.freepool_name,
                                 host_details['service_name'])

            host = None
            cantaddextracapability = []
            try:
                if trust_id:
                    host_details.update({'trust_id': trust_id})
                host = db_api.host_create(host_details)
            except db_ex.BlazarDBException:
                # We need to rollback
                # TODO(sbauza): Investigate use of Taskflow for atomic
                # transactions
                pool.remove_computehost(self.freepool_name,
                                        host_details['service_name'])
            if host:
                for key in extra_capabilities:
                    values = {'computehost_id': host['id'],
                              'capability_name': key,
                              'capability_value': extra_capabilities[key],
                              }
                    try:
                        db_api.host_extra_capability_create(values)
                    except db_ex.BlazarDBException:
                        cantaddextracapability.append(key)
            if cantaddextracapability:
                raise manager_ex.CantAddExtraCapability(
                    keys=cantaddextracapability,
                    host=host['id'])
            if host:
                return self.get_computehost(host['id'])
            else:
                return None

    def update_computehost(self, host_id, values):
        if values:
            cant_update_extra_capability = []
            for value in values:
                capabilities = db_api.host_extra_capability_get_all_per_name(
                    host_id,
                    value,
                )
                if capabilities:
                    for raw_capability in capabilities:
                        capability = {
                            'capability_name': value,
                            'capability_value': values[value],
                        }
                        try:
                            db_api.host_extra_capability_update(
                                raw_capability['id'], capability)
                        except (db_ex.BlazarDBException, RuntimeError):
                            cant_update_extra_capability.append(
                                raw_capability['capability_name'])
                else:
                    new_capability = {
                        'computehost_id': host_id,
                        'capability_name': value,
                        'capability_value': values[value],
                    }
                    try:
                        db_api.host_extra_capability_create(new_capability)
                    except (db_ex.BlazarDBException, RuntimeError):
                        cant_update_extra_capability.append(
                            new_capability['capability_name'])
            if cant_update_extra_capability:
                raise manager_ex.CantAddExtraCapability(
                    host=host_id,
                    keys=cant_update_extra_capability)
        return self.get_computehost(host_id)

    def delete_computehost(self, host_id):
        host = db_api.host_get(host_id)
        if not host:
            raise manager_ex.HostNotFound(host=host_id)

        with trusts.create_ctx_from_trust(host['trust_id']):
            if db_api.host_allocation_get_all_by_values(
                    compute_host_id=host_id):
                raise manager_ex.CantDeleteHost(
                    host=host_id,
                    msg='The host is reserved.'
                )

            inventory = nova.NovaInventory()
            servers = inventory.get_servers_per_host(
                host['hypervisor_hostname'])
            if servers:
                raise manager_ex.HostHavingServers(
                    host=host['hypervisor_hostname'], servers=servers)

            try:
                pool = nova.ReservationPool()
                pool.remove_computehost(self.freepool_name,
                                        host['service_name'])
                # NOTE(sbauza): Extracapabilities will be destroyed thanks to
                #  the DB FK.
                db_api.host_destroy(host_id)
            except db_ex.BlazarDBException as e:
                # Nothing so bad, but we need to alert admins
                # they have to rerun
                raise manager_ex.CantDeleteHost(host=host_id, msg=str(e))

    def _matching_hosts(self, hypervisor_properties, resource_properties,
                        count_range, start_date, end_date):
        """Return the matching hosts (preferably not allocated)

        """
        count_range = count_range.split('-')
        min_host = count_range[0]
        max_host = count_range[1]
        allocated_host_ids = []
        not_allocated_host_ids = []
        filter_array = []
        # TODO(frossigneux) support "or" operator
        if hypervisor_properties:
            filter_array = plugins_utils.convert_requirements(
                hypervisor_properties)
        if resource_properties:
            filter_array += plugins_utils.convert_requirements(
                resource_properties)
        for host in db_api.reservable_host_get_all_by_queries(filter_array):
            if not db_api.host_allocation_get_all_by_values(
                    compute_host_id=host['id']):
                not_allocated_host_ids.append(host['id'])
            elif db_utils.get_free_periods(
                host['id'],
                start_date,
                end_date,
                end_date - start_date,
            ) == [
                (start_date, end_date),
            ]:
                allocated_host_ids.append(host['id'])
        if len(not_allocated_host_ids) >= int(min_host):
            return not_allocated_host_ids[:int(max_host)]
        all_host_ids = allocated_host_ids + not_allocated_host_ids
        if len(all_host_ids) >= int(min_host):
            return all_host_ids[:int(max_host)]
        else:
            return []

    def _convert_int_param(self, param, name):
        """Checks that the parameter is present and can be converted to int."""
        if param is None:
            raise manager_ex.MissingParameter(param=name)
        if strutils.is_int_like(param):
            param = int(param)
        else:
            raise manager_ex.MalformedParameter(param=name)
        return param

    def _check_params(self, values):
        min_hosts = self._convert_int_param(values.get('min'), 'min')
        max_hosts = self._convert_int_param(values.get('max'), 'max')

        if 0 <= min_hosts and min_hosts <= max_hosts:
            values['count_range'] = str(min_hosts) + '-' + str(max_hosts)
        else:
            raise manager_ex.InvalidRange()

        if 'hypervisor_properties' not in values:
            raise manager_ex.MissingParameter(param='hypervisor_properties')
        if 'resource_properties' not in values:
            raise manager_ex.MissingParameter(param='resource_properties')

        if 'before_end' not in values:
            values['before_end'] = 'default'
        if values['before_end'] not in before_end_options:
            raise manager_ex.MalformedParameter(param='before_end')

    def _update_allocations(self, dates_before, dates_after, reservation_id,
                            reservation_status, host_reservation, values):
        min_hosts = self._convert_int_param(values.get(
            'min', host_reservation['count_range'].split('-')[0]), 'min')
        max_hosts = self._convert_int_param(values.get(
            'max', host_reservation['count_range'].split('-')[1]), 'max')
        if min_hosts < 0 or max_hosts < min_hosts:
            raise manager_ex.InvalidRange()
        hypervisor_properties = values.get(
            'hypervisor_properties',
            host_reservation['hypervisor_properties'])
        resource_properties = values.get(
            'resource_properties',
            host_reservation['resource_properties'])
        allocs = db_api.host_allocation_get_all_by_values(
            reservation_id=reservation_id)

        allocs_to_remove = self._allocations_to_remove(
            dates_before, dates_after, max_hosts, hypervisor_properties,
            resource_properties, allocs)

        if (allocs_to_remove and
                reservation_status == status.reservation.ACTIVE):
            raise manager_ex.NotEnoughHostsAvailable()

        kept_hosts = len(allocs) - len(allocs_to_remove)
        if kept_hosts < max_hosts:
            min_hosts = min_hosts - kept_hosts \
                if (min_hosts - kept_hosts) > 0 else 0
            max_hosts = max_hosts - kept_hosts
            host_ids = self._matching_hosts(
                hypervisor_properties, resource_properties,
                str(min_hosts) + '-' + str(max_hosts),
                dates_after['start_date'], dates_after['end_date'])
            if len(host_ids) >= min_hosts:
                for host_id in host_ids:
                    db_api.host_allocation_create(
                        {'compute_host_id': host_id,
                         'reservation_id': reservation_id})
            else:
                raise manager_ex.NotEnoughHostsAvailable()

        for allocation in allocs_to_remove:
            db_api.host_allocation_destroy(allocation['id'])

    def _allocations_to_remove(self, dates_before, dates_after, max_hosts,
                               hypervisor_properties, resource_properties,
                               allocs):
        allocs_to_remove = []
        requested_host_ids = [host['id'] for host in
                              self._filter_hosts_by_properties(
                                  hypervisor_properties, resource_properties)]

        for alloc in allocs:
            if alloc['compute_host_id'] not in requested_host_ids:
                allocs_to_remove.append(alloc)
                continue
            if (dates_before['start_date'] > dates_after['start_date'] or
                    dates_before['end_date'] < dates_after['end_date']):
                reserved_periods = db_utils.get_reserved_periods(
                    alloc['compute_host_id'],
                    dates_after['start_date'],
                    dates_after['end_date'],
                    datetime.timedelta(seconds=1))

                max_start = max(dates_before['start_date'],
                                dates_after['start_date'])
                min_end = min(dates_before['end_date'],
                              dates_after['end_date'])

                if not (len(reserved_periods) == 0 or
                        (len(reserved_periods) == 1 and
                         reserved_periods[0][0] == max_start and
                         reserved_periods[0][1] == min_end)):
                    allocs_to_remove.append(alloc)
                    continue

        kept_hosts = len(allocs) - len(allocs_to_remove)
        if kept_hosts > max_hosts:
            allocs_to_remove.extend(
                [allocation for allocation in allocs
                 if allocation not in allocs_to_remove
                 ][:(kept_hosts - max_hosts)]
            )

        return allocs_to_remove

    def _filter_hosts_by_properties(self, hypervisor_properties,
                                    resource_properties):
        filter = []
        if hypervisor_properties:
            filter += plugins_utils.convert_requirements(hypervisor_properties)
        if resource_properties:
            filter += plugins_utils.convert_requirements(resource_properties)
        if filter:
            return db_api.host_get_all_by_queries(filter)
        else:
            return db_api.host_list()


class PhysicalHostMonitorPlugin(base.BaseMonitorPlugin,
                                nova.NovaClientWrapper):
    """Monitor plugin for physical host resource."""

    # Singleton design pattern
    _instance = None

    def __new__(cls):
        if not cls._instance:
            cls._instance = super(PhysicalHostMonitorPlugin, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        super(PhysicalHostMonitorPlugin, self).__init__(
            username=CONF.os_admin_username,
            password=CONF.os_admin_password,
            user_domain_name=CONF.os_admin_user_domain_name,
            project_name=CONF.os_admin_project_name,
            project_domain_name=CONF.os_admin_user_domain_name)
        self.healing_handlers = []

    def register_healing_handler(self, handler):
        self.healing_handlers.append(handler)

    def is_notification_enabled(self):
        """Check if the notification monitor is enabled."""
        return CONF[plugin.RESOURCE_TYPE].enable_notification_monitor

    def get_notification_event_types(self):
        """Get event types of notification messages to handle."""
        return ['service.update']

    def get_notification_topics(self):
        """Get topics of notification to subscribe to."""
        return CONF[plugin.RESOURCE_TYPE].notification_topics

    def notification_callback(self, event_type, payload):
        """Handle a notification message.

        It is used as a callback of a notification-based resource monitor.

        :param event_type: an event type of a notification.
        :param payload: a payload of a notification.
        :return: a dictionary of {reservation id: flags to update}
                 e.g. {'de27786d-bd96-46bb-8363-19c13b2c6657':
                       {'missing_resources': True}}
        """
        LOG.trace('Handling a notification...')
        reservation_flags = {}

        data = payload.get('nova_object.data', None)
        if data:
            if data['disabled'] or data['forced_down']:
                failed_hosts = db_api.reservable_host_get_all_by_queries(
                    ['hypervisor_hostname == ' + data['host']])
                if failed_hosts:
                    LOG.warn('%s failed.',
                             failed_hosts[0]['hypervisor_hostname'])
                    reservation_flags = self._handle_failures(failed_hosts)

        return reservation_flags

    def is_polling_enabled(self):
        """Check if the polling monitor is enabled."""
        return CONF[plugin.RESOURCE_TYPE].enable_polling_monitor

    def get_polling_interval(self):
        """Get interval of polling."""
        return CONF[plugin.RESOURCE_TYPE].polling_interval

    def poll(self):
        """Detect and handle resource failures.

        :return: a dictionary of {reservation id: flags to update}
                 e.g. {'de27786d-bd96-46bb-8363-19c13b2c6657':
                 {'missing_resources': True}}
        """
        LOG.trace('Poll...')
        reservation_flags = {}

        failed_hosts = self._poll_resource_failures()
        if failed_hosts:
            for host in failed_hosts:
                LOG.warn('%s failed.', host['hypervisor_hostname'])
            reservation_flags = self._handle_failures(failed_hosts)

        return reservation_flags

    def _poll_resource_failures(self):
        """Check health of hosts by calling Nova Hypervisors API.

        :return: a list of failed hosts.
        """
        reservable_hosts = db_api.reservable_host_get_all_by_queries([])

        try:
            hvs = self.nova.hypervisors.list()
            failed_hv_ids = [str(hv.id) for hv in hvs
                             if hv.state == 'down' or hv.status == 'disabled']
            failed_hosts = [host for host in reservable_hosts
                            if host['id'] in failed_hv_ids]
        except Exception as e:
            LOG.exception('Skipping health check of host %s. %s',
                          host['hypervisor_hostname'], str(e))

        return failed_hosts

    def _handle_failures(self, failed_hosts):
        """Handle resource failures.

        :param: failed_hosts: a list of failed hosts.
        :return: a dictionary of {reservation id: flags to update}
                 e.g. {'de27786d-bd96-46bb-8363-19c13b2c6657':
                 {'missing_resources': True}}
        """

        # Update the computehosts table
        for host in failed_hosts:
            try:
                db_api.host_update(host['id'], {'reservable': False})
            except Exception as e:
                LOG.exception('Failed to update %s. %s',
                              host['hypervisor_hostname'], str(e))

        # Heal related reservations
        reservation_flags = {}
        for handler in self.healing_handlers:
            reservation_flags.update(handler(failed_hosts))

        return reservation_flags
