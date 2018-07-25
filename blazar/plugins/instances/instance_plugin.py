# Copyright (c) 2017 NTT.
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

from novaclient import exceptions as nova_exceptions
from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils.strutils import bool_from_string

from blazar import context
from blazar.db import api as db_api
from blazar.db import utils as db_utils
from blazar.manager import exceptions as mgr_exceptions
from blazar.plugins import base
from blazar.plugins import instances as plugin
from blazar.plugins import oshosts
from blazar import status
from blazar.utils.openstack import nova
from blazar.utils import plugins as plugins_utils

CONF = cfg.CONF
LOG = logging.getLogger(__name__)

RESERVATION_PREFIX = 'reservation'
FLAVOR_EXTRA_SPEC = "aggregate_instance_extra_specs:" + RESERVATION_PREFIX


class VirtualInstancePlugin(base.BasePlugin, nova.NovaClientWrapper):
    """Plugin for virtual instance resources."""

    resource_type = plugin.RESOURCE_TYPE
    title = 'Virtual Instance Plugin'

    def __init__(self):
        super(VirtualInstancePlugin, self).__init__(
            username=CONF.os_admin_username,
            password=CONF.os_admin_password,
            user_domain_name=CONF.os_admin_user_domain_name,
            project_name=CONF.os_admin_project_name,
            project_domain_name=CONF.os_admin_project_domain_name)

        self.freepool_name = CONF.nova.aggregate_freepool_name
        self.monitor = oshosts.host_plugin.PhysicalHostMonitorPlugin()
        self.monitor.register_healing_handler(self.heal_reservations)

    def filter_hosts_by_reservation(self, hosts, start_date, end_date,
                                    excludes):
        free = []
        non_free = []

        for host in hosts:
            reservations = db_utils.get_reservations_by_host_id(host['id'],
                                                                start_date,
                                                                end_date)

            if excludes:
                reservations = [r for r in reservations
                                if r['id'] not in excludes]

            if reservations == []:
                free.append({'host': host, 'reservations': None})
            elif not [r for r in reservations
                      if r['resource_type'] == oshosts.RESOURCE_TYPE]:
                non_free.append({'host': host, 'reservations': reservations})

        return free, non_free

    def max_usages(self, host, reservations):
        def resource_usage_by_event(event, resource_type):
            return event['reservation']['instance_reservation'][resource_type]

        events_list = []
        for r in reservations:
            fetched_events = db_api.event_get_all_sorted_by_filters(
                sort_key='time', sort_dir='asc',
                filters={'lease_id': r['lease_id']})
            events_list.extend([{'event': e, 'reservation': r}
                                for e in fetched_events])

        events_list.sort(key=lambda x: x['event']['time'])

        max_vcpus = max_memory = max_disk = 0
        current_vcpus = current_memory = current_disk = 0

        for event in events_list:
            if event['event']['event_type'] == 'start_lease':
                current_vcpus += resource_usage_by_event(event, 'vcpus')
                current_memory += resource_usage_by_event(event, 'memory_mb')
                current_disk += resource_usage_by_event(event, 'disk_gb')
                if max_vcpus < current_vcpus:
                    max_vcpus = current_vcpus
                if max_memory < current_memory:
                    max_memory = current_memory
                if max_disk < current_disk:
                    max_disk = current_disk
            elif event['event']['event_type'] == 'end_lease':
                current_vcpus -= resource_usage_by_event(event, 'vcpus')
                current_memory -= resource_usage_by_event(event, 'memory_mb')
                current_disk -= resource_usage_by_event(event, 'disk_gb')

        return max_vcpus, max_memory, max_disk

    def query_available_hosts(self, cpus=None, memory=None, disk=None,
                              resource_properties=None,
                              start_date=None, end_date=None,
                              excludes_res=None):
        """Query hosts that are available for a reservation.

        Its return value is in the order of reserved hosts to free hosts now.
        """
        flavor_definitions = [
            'and',
            [">=", "$vcpus", str(cpus)],
            [">=", "$memory_mb", str(memory)],
            [">=", "$local_gb", str(disk)],
            ]

        filters = plugins_utils.convert_requirements(flavor_definitions)

        if resource_properties:
            filters += plugins_utils.convert_requirements(resource_properties)

        hosts = db_api.reservable_host_get_all_by_queries(filters)
        free_hosts, reserved_hosts = self.filter_hosts_by_reservation(
            hosts,
            start_date - datetime.timedelta(minutes=CONF.cleaning_time),
            end_date + datetime.timedelta(minutes=CONF.cleaning_time),
            excludes_res)

        available_hosts = []
        for host_info in reserved_hosts:
            host = host_info['host']
            reservations = host_info['reservations']
            max_cpus, max_memory, max_disk = self.max_usages(host,
                                                             reservations)

            if not (max_cpus + cpus > host['vcpus'] or
                    max_memory + memory > host['memory_mb'] or
                    max_disk + disk > host['local_gb']):
                available_hosts.append(host)

        available_hosts.extend([h['host'] for h in free_hosts])
        return available_hosts

    def pickup_hosts(self, reservation_id, values):
        """Checks whether Blazar can accommodate the request.

        This method filters and pick up hosts for this reservation
        with following steps.

        1. filter hosts that have a spec enough to accommodate the flavor
        2. categorize hosts allocated_hosts and not_allocated_hosts
           at the reservation time frame
        3. filter out hosts used by physical host reservation from
           allocate_host
        4. filter out hosts that can't accommodate the flavor at the
           time frame because of others reservations
        """
        query_params = {
            'cpus': values['vcpus'],
            'memory': values['memory_mb'],
            'disk': values['disk_gb'],
            'resource_properties': values['resource_properties'],
            'start_date': values['start_date'],
            'end_date': values['end_date']
            }

        # add the specific query param for reservation update
        old_allocs = db_api.host_allocation_get_all_by_values(
            reservation_id=reservation_id)
        if old_allocs:
            query_params['excludes_res'] = [reservation_id]

        new_hosts = self.query_available_hosts(**query_params)

        old_host_ids = {h['compute_host_id'] for h in old_allocs}
        candidate_ids = {h['id'] for h in new_hosts}

        kept_host_ids = old_host_ids & candidate_ids
        removed_host_ids = old_host_ids - candidate_ids
        extra_host_ids = candidate_ids - old_host_ids
        added_host_ids = set([])

        if len(kept_host_ids) > values['amount']:
            extra = len(kept_host_ids) - values['amount']
            for i in range(extra):
                removed_host_ids.add(kept_host_ids.pop())
        elif len(kept_host_ids) < values['amount']:
            less = values['amount'] - len(kept_host_ids)
            ordered_extra_host_ids = [h['id'] for h in new_hosts
                                      if h['id'] in extra_host_ids]
            for i in range(min(less, len(extra_host_ids))):
                added_host_ids.add(ordered_extra_host_ids[i])

        return {'added': added_host_ids, 'removed': removed_host_ids}

    def _create_flavor(self, reservation_id, vcpus, memory, disk, group_id):
        flavor_details = {
            'flavorid': reservation_id,
            'name': RESERVATION_PREFIX + ":" + reservation_id,
            'vcpus': vcpus,
            'ram': memory,
            'disk': disk,
            'is_public': False
            }
        reserved_flavor = self.nova.nova.flavors.create(**flavor_details)
        extra_specs = {
            FLAVOR_EXTRA_SPEC: reservation_id,
            "affinity_id": group_id
            }
        reserved_flavor.set_keys(extra_specs)
        return reserved_flavor

    def _create_resources(self, inst_reservation):
        reservation_id = inst_reservation['reservation_id']

        ctx = context.current()
        user_client = nova.NovaClientWrapper()

        reserved_group = user_client.nova.server_groups.create(
            RESERVATION_PREFIX + ':' + reservation_id,
            'affinity' if inst_reservation['affinity'] else 'anti-affinity'
            )

        reserved_flavor = self._create_flavor(reservation_id,
                                              inst_reservation['vcpus'],
                                              inst_reservation['memory_mb'],
                                              inst_reservation['disk_gb'],
                                              reserved_group.id)

        pool = nova.ReservationPool()
        pool_metadata = {
            RESERVATION_PREFIX: reservation_id,
            'filter_tenant_id': ctx.project_id,
            'affinity_id': reserved_group.id
            }
        agg = pool.create(name=reservation_id, metadata=pool_metadata)

        return reserved_flavor, reserved_group, agg

    def cleanup_resources(self, instance_reservation):
        def check_and_delete_resource(client, id):
            try:
                client.delete(id)
            except nova_exceptions.NotFound:
                pass

        reservation_id = instance_reservation['reservation_id']

        check_and_delete_resource(self.nova.nova.server_groups,
                                  instance_reservation['server_group_id'])
        check_and_delete_resource(self.nova.nova.flavors, reservation_id)
        check_and_delete_resource(nova.ReservationPool(), reservation_id)

    def update_resources(self, reservation_id):
        """Updates reserved resources in Nova.

        This method updates reserved resources in Compute service. If the
        reservation is in active status, it adds new allocated hosts into
        a reserved aggregate. If the reservation is not started yet, it
        updates a reserved flavor.
        """
        reservation = db_api.reservation_get(reservation_id)

        if reservation['status'] == 'active':
            pool = nova.ReservationPool()
            for allocation in db_api.host_allocation_get_all_by_values(
                    reservation_id=reservation['id']):
                host = db_api.host_get(allocation['compute_host_id'])
                try:
                    pool.add_computehost(
                        reservation['aggregate_id'],
                        host['service_name'], stay_in=True)
                except mgr_exceptions.AggregateAlreadyHasHost:
                    pass
                except nova_exceptions.ClientException:
                    err_msg = ('Fail to add host %s to aggregate %s.'
                               % (host, reservation['aggregate_id']))
                    raise mgr_exceptions.NovaClientError(err_msg)
        else:
            try:
                self.nova.nova.flavors.delete(reservation['id'])
                self._create_flavor(reservation['id'],
                                    reservation['vcpus'],
                                    reservation['memory_mb'],
                                    reservation['disk_gb'],
                                    reservation['server_group_id'])
            except nova_exceptions.ClientException:
                LOG.exception("Failed to update Nova resources "
                              "for reservation %s", reservation['id'])
                raise mgr_exceptions.NovaClientError()

    def validate_reservation_param(self, values):
        marshall_attributes = set(['vcpus', 'memory_mb', 'disk_gb',
                                   'amount', 'affinity',
                                   'resource_properties'])
        missing_attr = marshall_attributes - set(values.keys())
        if missing_attr:
            raise mgr_exceptions.MissingParameter(param=','.join(missing_attr))

    def reserve_resource(self, reservation_id, values):
        self.validate_reservation_param(values)

        # TODO(masahito) the instance reservation plugin only supports
        # anti-affinity rule in short-term goal.
        if bool_from_string(values['affinity']):
            raise mgr_exceptions.MalformedParameter(
                param='affinity (only affinity = False is supported)')

        hosts = self.pickup_hosts(reservation_id, values)

        if len(hosts['added']) < values['amount']:
            raise mgr_exceptions.HostNotFound("The reservation can't be "
                                              "accommodate because of less "
                                              "capacity.")

        instance_reservation_val = {
            'reservation_id': reservation_id,
            'vcpus': values['vcpus'],
            'memory_mb': values['memory_mb'],
            'disk_gb': values['disk_gb'],
            'amount': values['amount'],
            'affinity': bool_from_string(values['affinity']),
            'resource_properties': values['resource_properties']
            }
        instance_reservation = db_api.instance_reservation_create(
            instance_reservation_val)

        for host_id in hosts['added']:
            db_api.host_allocation_create({'compute_host_id': host_id,
                                          'reservation_id': reservation_id})

        try:
            flavor, group, pool = self._create_resources(instance_reservation)
        except nova_exceptions.ClientException:
            LOG.exception("Failed to create Nova resources "
                          "for reservation %s", reservation_id)
            self.cleanup_resources(instance_reservation)
            raise mgr_exceptions.NovaClientError()

        db_api.instance_reservation_update(instance_reservation['id'],
                                           {'flavor_id': flavor.id,
                                            'server_group_id': group.id,
                                            'aggregate_id': pool.id})

        return instance_reservation['id']

    def update_host_allocations(self, added, removed, reservation_id):
        allocations = db_api.host_allocation_get_all_by_values(
            reservation_id=reservation_id)

        removed_allocs = [a for a in allocations
                          if a['compute_host_id'] in removed]
        for alloc in removed_allocs:
            db_api.host_allocation_destroy(alloc['id'])

        for added_host in added:
            db_api.host_allocation_create({'compute_host_id': added_host,
                                           'reservation_id': reservation_id})

    def update_reservation(self, reservation_id, new_values):
        """Updates an instance reservation with requested parameters.

        This method allows users to update an instance reservation under the
        following conditions.
        - If an instance reservation has not started yet
             - vcpus, memory_mb disk_gb and amount can be updateable unless
               Blazar can accomodate the new request.
        - If an instance reservation has already started
             - only amount is increasable.
        """
        # TODO(masahito) the instance reservation plugin only supports
        # anti-affinity rule in short-term goal.
        if bool_from_string(new_values.get('affinity', None)):
            raise mgr_exceptions.MalformedParameter(
                param='affinity (only affinity = False is supported)')

        reservation = db_api.reservation_get(reservation_id)
        lease = db_api.lease_get(reservation['lease_id'])

        updatable = ['vcpus', 'memory_mb', 'disk_gb', 'affinity', 'amount',
                     'resource_properties']
        if (not any([k in updatable for k in new_values.keys()])
                and new_values['start_date'] >= lease['start_date']
                and new_values['end_date'] <= lease['end_date']):
            # no update because of just shortening the reservation time
            return

        if (reservation['status'] == 'active' and
                any([k in updatable[:-1] for k in new_values.keys()])):
            msg = "An active reservation only accepts to update amount."
            raise mgr_exceptions.InvalidStateUpdate(msg)

        if reservation['status'] == 'error':
            msg = "An error reservation doesn't accept an updating request."
            raise mgr_exceptions.InvalidStateUpdate(msg)

        for key in updatable:
            if key not in new_values:
                new_values[key] = reservation[key]

        changed_hosts = self.pickup_hosts(reservation_id, new_values)

        if (reservation['status'] == 'active'
                and len(changed_hosts['removed']) > 0):
            err_msg = ("Instance reservation doesn't allow to reduce/replace "
                       "reserved instance slots when the reservation is in "
                       "active status.")
            raise mgr_exceptions.CantUpdateParameter(err_msg)

        if (new_values['amount'] - reservation['amount'] !=
           (len(changed_hosts['added']) - len(changed_hosts['removed']))):
            raise mgr_exceptions.NotEnoughHostsAvailable()

        db_api.instance_reservation_update(
            reservation['resource_id'],
            {key: new_values[key] for key in updatable})

        self.update_host_allocations(changed_hosts['added'],
                                     changed_hosts['removed'],
                                     reservation_id)

        try:
            self.update_resources(reservation_id)
        except mgr_exceptions.NovaClientError:
            raise

    def on_start(self, resource_id):
        ctx = context.current()
        instance_reservation = db_api.instance_reservation_get(resource_id)
        reservation_id = instance_reservation['reservation_id']

        try:
            self.nova.flavor_access.add_tenant_access(reservation_id,
                                                      ctx.project_id)
        except nova_exceptions.ClientException:
            LOG.info('Failed to associate flavor %(reservation_id)s '
                     'to project %(project_id)s',
                     {'reservation_id': reservation_id,
                      'project_id': ctx.project_id})
            raise mgr_exceptions.EventError()

        pool = nova.ReservationPool()
        for allocation in db_api.host_allocation_get_all_by_values(
                reservation_id=reservation_id):
            host = db_api.host_get(allocation['compute_host_id'])
            pool.add_computehost(instance_reservation['aggregate_id'],
                                 host['service_name'], stay_in=True)

    def on_end(self, resource_id):
        instance_reservation = db_api.instance_reservation_get(resource_id)
        ctx = context.current()

        try:
            self.nova.flavor_access.remove_tenant_access(
                instance_reservation['reservation_id'], ctx.project_id)
        except nova_exceptions.NotFound:
            pass

        allocations = db_api.host_allocation_get_all_by_values(
            reservation_id=instance_reservation['reservation_id'])
        for allocation in allocations:
            db_api.host_allocation_destroy(allocation['id'])

        for server in self.nova.servers.list(search_opts={
                'flavor': instance_reservation['reservation_id'],
                'all_tenants': 1}, detailed=False):
            server.delete()

        self.cleanup_resources(instance_reservation)

    def heal_reservations(self, failed_resources, interval_begin,
                          interval_end):
        """Heal reservations which suffer from resource failures.

        :param: failed_resources: failed resources
        :param: interval_begin: start date of the period to heal.
        :param: interval_end: end date of the period to heal.
        :return: a dictionary of {reservation id: flags to update}
                 e.g. {'de27786d-bd96-46bb-8363-19c13b2c6657':
                       {'missing_resources': True}}
        """
        reservation_flags = {}

        host_ids = [h['id'] for h in failed_resources]
        reservations = db_utils.get_reservations_by_host_ids(host_ids,
                                                             interval_begin,
                                                             interval_end)

        for reservation in reservations:
            if reservation['resource_type'] != plugin.RESOURCE_TYPE:
                continue

            for allocation in [alloc for alloc
                               in reservation['computehost_allocations']
                               if alloc['compute_host_id'] in host_ids]:
                if self._reallocate(allocation):
                    if reservation['status'] == status.reservation.ACTIVE:
                        if reservation['id'] not in reservation_flags:
                            reservation_flags[reservation['id']] = {}
                        reservation_flags[reservation['id']].update(
                            {'resources_changed': True})
                else:
                    if reservation['id'] not in reservation_flags:
                        reservation_flags[reservation['id']] = {}
                    reservation_flags[reservation['id']].update(
                        {'missing_resources': True})

        return reservation_flags

    def _reallocate(self, allocation):
        """Allocate an alternative host.

        :param: allocation: allocation to change.
        :return: True if an alternative host was successfully allocated.
        """
        reservation = db_api.reservation_get(allocation['reservation_id'])
        pool = nova.ReservationPool()

        # Remove the failed host from the aggregate.
        if reservation['status'] == status.reservation.ACTIVE:
            host = db_api.host_get(allocation['compute_host_id'])
            pool.remove_computehost(reservation['aggregate_id'],
                                    host['service_name'])

        # Allocate an alternative host.
        values = {}
        lease = db_api.lease_get(reservation['lease_id'])
        values['start_date'] = max(datetime.datetime.utcnow(),
                                   lease['start_date'])
        values['end_date'] = lease['end_date']
        specs = ['vcpus', 'memory_mb', 'disk_gb', 'affinity', 'amount',
                 'resource_properties']
        for key in specs:
            values[key] = reservation[key]
        changed_hosts = self.pickup_hosts(reservation['id'], values)
        if len(changed_hosts['added']) == 0:
            db_api.host_allocation_destroy(allocation['id'])
            LOG.warn('Could not find alternative host for reservation %s '
                     '(lease: %s).', reservation['id'], lease['name'])
            return False
        else:
            new_host_id = changed_hosts['added'].pop()
            db_api.host_allocation_update(
                allocation['id'], {'compute_host_id': new_host_id})
            if reservation['status'] == status.reservation.ACTIVE:
                # Add the alternative host into the aggregate.
                new_host = db_api.host_get(new_host_id)
                pool.add_computehost(reservation['aggregate_id'],
                                     new_host['service_name'],
                                     stay_in=True)
            LOG.warn('Resource changed for reservation %s (lease: %s).',
                     reservation['id'], lease['name'])

            return True
