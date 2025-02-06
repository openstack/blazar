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

import collections
import datetime
import retrying

from novaclient import exceptions as nova_exceptions
from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import strutils
from oslo_utils.strutils import bool_from_string
from oslo_utils import timeutils

from blazar import context
from blazar.db import api as db_api
from blazar.db import utils as db_utils
from blazar.manager import exceptions as mgr_exceptions
from blazar.plugins import base
from blazar.plugins import instances as plugin
from blazar.plugins import oshosts
from blazar import status
from blazar.utils.openstack import exceptions as openstack_ex
from blazar.utils.openstack import nova
from blazar.utils.openstack import placement
from blazar.utils import plugins as plugins_utils

CONF = cfg.CONF
LOG = logging.getLogger(__name__)

RESERVATION_PREFIX = 'reservation'
FLAVOR_EXTRA_SPEC = "aggregate_instance_extra_specs:" + RESERVATION_PREFIX
INSTANCE_DELETION_TIMEOUT = 10 * 60 * 1000  # 10 minutes

NONE_VALUES = ('None', 'none', None)
QUERY_TYPE_ALLOCATION = 'allocation'


class VirtualInstancePlugin(base.BasePlugin, nova.NovaClientWrapper):
    """Plugin for virtual instance resources."""

    resource_type = plugin.RESOURCE_TYPE
    title = 'Virtual Instance Plugin'
    query_options = {
        QUERY_TYPE_ALLOCATION: ['lease_id', 'reservation_id']
    }

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
        self.placement_client = placement.BlazarPlacementClient()

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
                free.append({'host': host, 'reservations': []})
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

    def get_hosts_list(self, host_info, cpus, memory, disk):
        hosts_list = []
        host = host_info['host']
        reservations = host_info['reservations']
        max_cpus, max_memory, max_disk = self.max_usages(host,
                                                         reservations)
        used_cpus, used_memory, used_disk = (cpus, memory, disk)
        while (max_cpus + used_cpus <= host['vcpus'] and
               max_memory + used_memory <= host['memory_mb'] and
               max_disk + used_disk <= host['local_gb']):
            hosts_list.append(host)
            used_cpus += cpus
            used_memory += memory
            used_disk += disk
        return hosts_list

    def allocation_candidates(self, reservation):
        return self.pickup_hosts(None, reservation)['added']

    def list_allocations(self, query):
        hosts_id_list = [h['id'] for h in db_api.host_list()]
        options = self.get_query_options(query, QUERY_TYPE_ALLOCATION)

        hosts_allocations = self.query_allocations(hosts_id_list, **options)
        return [{"resource_id": host, "reservations": allocs}
                for host, allocs in hosts_allocations.items()]

    def query_allocations(self, hosts, lease_id=None, reservation_id=None):
        """Return dict of host and its allocations.

        The list element forms
        {
          'host-id': [
                       {
                         'lease_id': lease_id,
                         'id': reservation_id
                         'start_date': lease_start_date,
                         'end_date': lease_end_date,
                       },
                     ]
        }.
        """
        start = timeutils.utcnow()
        end = datetime.date.max

        # To reduce overhead, this method only executes one query
        # to get the allocation information
        reservations = db_utils.get_reservation_allocations_by_host_ids(
            hosts, start, end, lease_id, reservation_id)
        host_allocs = {h: [] for h in hosts}
        attributes_to_copy = ["id", "lease_id", "start_date", "end_date"]
        for reservation in reservations:
            for host_id in reservation['host_ids']:
                if host_id in host_allocs.keys():
                    host_allocs[host_id].append({
                        k: v for k, v in reservation.items()
                        if k in attributes_to_copy})
        return host_allocs

    def query_available_hosts(self, cpus=None, memory=None, disk=None,
                              resource_properties=None,
                              start_date=None, end_date=None,
                              excludes_res=None):
        """Returns a list of available hosts for a reservation.

        The list is in the order of reserved hosts to free hosts.

        1. filter hosts that have a spec enough to accommodate the flavor
        2. categorize hosts into hosts with and without allocation
           at the reservation time frame
        3. filter out hosts used by physical host reservation from
           allocate_host
        4. filter out hosts that can't accommodate the flavor at the
           time frame because of other reservations
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
        for host_info in (reserved_hosts + free_hosts):
            hosts_list = self.get_hosts_list(host_info, cpus, memory, disk)
            available_hosts.extend(hosts_list)

        return available_hosts

    def pickup_hosts(self, reservation_id, values):
        """Returns lists of host ids to add/remove.

        This function picks up available hosts, calculates the difference from
        old reservations and returns a dict of a list of host ids to add
        and remove keyed by "added" or "removed".

        Note that the lists allow duplicated host ids for `affinity=True`
        cases.

        :raises: NotEnoughHostsAvailable exception if there are not enough
                 hosts available for the request
        """
        req_amount = values['amount']
        affinity = bool_from_string(values['affinity'], default=None)

        query_params = {
            'cpus': values['vcpus'],
            'memory': values['memory_mb'],
            'disk': values['disk_gb'],
            'resource_properties': values['resource_properties'],
            'start_date': values['start_date'],
            'end_date': values['end_date']
            }

        old_allocs = db_api.host_allocation_get_all_by_values(
            reservation_id=reservation_id)
        if old_allocs:
            # This is a path for *update* reservation. Add the specific
            # query param not to consider resources reserved by existing
            # reservations to update
            query_params['excludes_res'] = [reservation_id]

        new_hosts = self.query_available_hosts(**query_params)

        old_host_id_list = [h['compute_host_id'] for h in old_allocs]
        candidate_id_list = [h['id'] for h in new_hosts]

        # Build `new_host_id_list`. Note that we'd like to pick up hosts in
        # the following order of priority:
        #  1. hosts reserved by the reservation to update
        #  2. hosts with reservations followed by hosts without reservations
        # Note that the `candidate_id_list` has already been ordered
        # satisfying the second requirement.
        if affinity:
            host_id_map = collections.Counter(candidate_id_list)
            available = {k for k, v in host_id_map.items() if v >= req_amount}
            if not available:
                raise mgr_exceptions.NotEnoughHostsAvailable()
            new_host_ids = set(old_host_id_list) & available
            if new_host_ids:
                # (priority 1) This is a path for update reservation. We pick
                # up a host from hosts reserved by the reservation to update.
                new_host_id = new_host_ids.pop()
            else:
                # (priority 2) This is a path both for update and for new
                # reservation. We pick up hosts with some other reservations
                # if possible and otherwise pick up hosts without any
                # reservation. We can do so by considering the order of the
                # `candidate_id_list`.
                for host_id in candidate_id_list:
                    if host_id in available:
                        new_host_id = host_id
                        break
            new_host_id_list = [new_host_id] * req_amount
        else:
            # Hosts that can accommodate but don't satisfy priority 1
            _, possible_host_list = plugins_utils.list_difference(
                old_host_id_list, candidate_id_list)
            # Hosts that satisfy priority 1
            new_host_id_list, _ = plugins_utils.list_difference(
                candidate_id_list, possible_host_list)
            if affinity is False:
                # Eliminate the duplication
                new_host_id_list = list(set(new_host_id_list))
            for host_id in possible_host_list:
                if (affinity is False) and (host_id in new_host_id_list):
                    # Eliminate the duplication
                    continue
                new_host_id_list.append(host_id)
            if len(new_host_id_list) < req_amount:
                raise mgr_exceptions.NotEnoughHostsAvailable()
            while len(new_host_id_list) > req_amount:
                new_host_id_list.pop()

        # Calculate the difference from the existing reserved host
        removed_host_ids, added_host_ids = plugins_utils.list_difference(
            old_host_id_list, new_host_id_list)

        return {'added': added_host_ids, 'removed': removed_host_ids}

    def _create_flavor(self, reservation_id, vcpus, memory, disk,
                       group_id=None):
        flavor_details = {
            'flavorid': reservation_id,
            'name': RESERVATION_PREFIX + ":" + reservation_id,
            'vcpus': vcpus,
            'ram': memory,
            'disk': disk,
            'is_public': False
            }
        reserved_flavor = self.nova.nova.flavors.create(**flavor_details)

        # Set extra specs to the flavor
        rsv_id_rc_format = reservation_id.upper().replace("-", "_")
        reservation_rc = "resources:CUSTOM_RESERVATION_" + rsv_id_rc_format
        extra_specs = {
            FLAVOR_EXTRA_SPEC: reservation_id,
            reservation_rc: "1"
            }
        if group_id is not None:
            extra_specs["affinity_id"] = group_id
        reserved_flavor.set_keys(extra_specs)

        return reserved_flavor

    def _create_resources(self, inst_reservation):
        reservation_id = inst_reservation['reservation_id']

        ctx = context.current()
        user_client = nova.NovaClientWrapper()

        flavor_args = {
            'reservation_id': reservation_id,
            'vcpus': inst_reservation['vcpus'],
            'memory': inst_reservation['memory_mb'],
            'disk': inst_reservation['disk_gb']
        }

        pool_metadata = {
            RESERVATION_PREFIX: reservation_id,
            'filter_tenant_id': ctx.project_id,
            }

        if inst_reservation['affinity'] is not None:
            reserved_group = user_client.nova.server_groups.create(
                RESERVATION_PREFIX + ':' + reservation_id,
                'affinity' if inst_reservation['affinity'] else 'anti-affinity'
                )
            flavor_args['group_id'] = reserved_group.id
            pool_metadata['affinity_id'] = reserved_group.id
        else:
            reserved_group = None

        reserved_flavor = self._create_flavor(**flavor_args)

        pool = nova.ReservationPool()
        agg = pool.create(name=reservation_id, metadata=pool_metadata)

        self.placement_client.create_reservation_class(reservation_id)

        return reserved_flavor, reserved_group, agg

    def cleanup_resources(self, instance_reservation):
        def check_and_delete_resource(client, id):
            try:
                client.delete(id)
            except nova_exceptions.NotFound:
                pass

        reservation_id = instance_reservation['reservation_id']

        server_group_id = instance_reservation['server_group_id']
        if server_group_id:
            check_and_delete_resource(self.nova.nova.server_groups,
                                      server_group_id)
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

            # Dict of number of instances to reserve on a host keyed by the
            # host id
            allocation_map = collections.defaultdict(lambda: 0)
            for allocation in db_api.host_allocation_get_all_by_values(
                    reservation_id=reservation['id']):
                host_id = allocation['compute_host_id']
                allocation_map[host_id] += 1

            for host_id, num in allocation_map.items():
                host = db_api.host_get(host_id)
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
                self.placement_client.update_reservation_inventory(
                    host['hypervisor_hostname'], reservation['id'], num)
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

    def _check_missing_reservation_params(self, values):
        marshall_attributes = set(['vcpus', 'memory_mb', 'disk_gb',
                                   'amount', 'affinity',
                                   'resource_properties'])
        missing_attr = marshall_attributes - set(values.keys())
        if missing_attr:
            raise mgr_exceptions.MissingParameter(param=','.join(missing_attr))

    def _validate_reservation_params(self, values):
        if 'amount' in values:
            try:
                values['amount'] = strutils.validate_integer(
                    values['amount'], "amount", 1, db_api.DB_MAX_INT)
            except ValueError as e:
                raise mgr_exceptions.MalformedParameter(str(e))

        if 'affinity' in values:
            if (values['affinity'] not in NONE_VALUES and
                    not strutils.is_valid_boolstr(values['affinity'])):
                raise mgr_exceptions.MalformedParameter(
                    param='affinity (must be a bool value or None)')

    def reserve_resource(self, reservation_id, values):
        self._check_missing_reservation_params(values)
        self._validate_reservation_params(values)

        hosts = self.pickup_hosts(reservation_id, values)

        instance_reservation_val = {
            'reservation_id': reservation_id,
            'vcpus': values['vcpus'],
            'memory_mb': values['memory_mb'],
            'disk_gb': values['disk_gb'],
            'amount': values['amount'],
            'affinity': bool_from_string(values['affinity'], default=None),
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

        server_group_id = group.id if group is not None else None
        db_api.instance_reservation_update(instance_reservation['id'],
                                           {'flavor_id': flavor.id,
                                            'server_group_id': server_group_id,
                                            'aggregate_id': pool.id})

        return instance_reservation['id']

    def update_host_allocations(self, added, removed, reservation_id):
        allocations = db_api.host_allocation_get_all_by_values(
            reservation_id=reservation_id)

        removed_allocs = []
        for host_id in removed:
            for allocation in allocations:
                if allocation['compute_host_id'] == host_id:
                    removed_allocs.append(allocation['id'])
                    break

        # TODO(tetsuro): It would be nice to have something like
        # db_api.host_allocation_replace() to process the following
        # deletion and addition in *one* DB transaction.
        for alloc_id in removed_allocs:
            db_api.host_allocation_destroy(alloc_id)

        for added_host in added:
            db_api.host_allocation_create({'compute_host_id': added_host,
                                           'reservation_id': reservation_id})

    def update_reservation(self, reservation_id, new_values):
        """Updates an instance reservation with requested parameters.

        This method allows users to update an instance reservation under the
        following conditions.
        - If an instance reservation has not started yet
             - vcpus, memory_mb disk_gb and amount can be updateable unless
               Blazar can accommodate the new request.
        - If an instance reservation has already started
             - only amount is increasable.
        """
        self._validate_reservation_params(new_values)

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

        if new_values.get('affinity', None):
            new_values['affinity'] = bool_from_string(new_values['affinity'],
                                                      default=None)

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

        db_api.instance_reservation_update(
            reservation['resource_id'],
            {key: new_values[key] for key in updatable})

        self.update_host_allocations(changed_hosts['added'],
                                     changed_hosts['removed'],
                                     reservation_id)
        self.update_resources(reservation_id)

    def on_start(self, resource_id):
        ctx = context.current()
        instance_reservation = db_api.instance_reservation_get(resource_id)
        reservation_id = instance_reservation['reservation_id']

        # TODO(johngarbutt): create flavor after updating placement?
        # else we will race with automation looking for the flavor here
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

        # Dict of number of instances to reserve on a host keyed by the
        # host id
        allocation_map = collections.defaultdict(lambda: 0)
        for allocation in db_api.host_allocation_get_all_by_values(
                reservation_id=reservation_id):
            host_id = allocation['compute_host_id']
            allocation_map[host_id] += 1

        for host_id, num in allocation_map.items():
            host = db_api.host_get(host_id)
            pool.add_computehost(instance_reservation['aggregate_id'],
                                 host['service_name'], stay_in=True)
            self.placement_client.update_reservation_inventory(
                host['hypervisor_hostname'], reservation_id, num)

    def on_end(self, resource_id):
        instance_reservation = db_api.instance_reservation_get(resource_id)
        reservation_id = instance_reservation['reservation_id']
        ctx = context.current()

        try:
            self.nova.flavor_access.remove_tenant_access(
                reservation_id, ctx.project_id)
        except nova_exceptions.NotFound:
            pass

        hostnames = []
        allocations = db_api.host_allocation_get_all_by_values(
            reservation_id=reservation_id)
        for allocation in allocations:
            host = db_api.host_get(allocation['compute_host_id'])
            db_api.host_allocation_destroy(allocation['id'])
            hostnames.append(host['hypervisor_hostname'])

        for server in self.nova.servers.list(search_opts={
                'flavor': reservation_id,
                'all_tenants': 1}, detailed=False):
            try:
                self.nova.servers.delete(server=server)
            except nova_exceptions.NotFound:
                LOG.info("Could not find server '%s', may have been deleted "
                         "concurrently.", server.id)
            except Exception as e:
                LOG.exception("Failed to delete server '%s': %s.", server.id,
                              str(e))

        # We need to check the deletion is complete before deleting the
        # reservation inventory. See the bug #1813252 for details.
        if not self._check_server_deletion(reservation_id):
            LOG.error('Timed out while deleting servers on reservation %s',
                      reservation_id)
            raise mgr_exceptions.ServerDeletionTimeout()

        self.cleanup_resources(instance_reservation)

        for host_name in hostnames:
            try:
                self.placement_client.delete_reservation_inventory(
                    host_name, reservation_id)
            except openstack_ex.ResourceProviderNotFound:
                pass
        self.placement_client.delete_reservation_class(reservation_id)

    @retrying.retry(stop_max_delay=INSTANCE_DELETION_TIMEOUT,
                    wait_fixed=5000,  # 5 seconds interval
                    retry_on_result=lambda x: x is False)
    def _check_server_deletion(self, reservation_id):
        servers = self.nova.servers.list(search_opts={
            'flavor': reservation_id, 'all_tenants': 1}, detailed=False)
        if servers:
            LOG.info('Waiting to delete servers: %s ', servers)
            return False
        return True

    def heal_reservations(self, failed_resources, interval_begin,
                          interval_end):
        """Heal reservations which suffer from resource failures.

        :param failed_resources: failed resources
        :param interval_begin: start date of the period to heal.
        :param interval_end: end date of the period to heal.
        :return: a dictionary of {reservation id: flags to update}
                 e.g. {'de27786d-bd96-46bb-8363-19c13b2c6657':
                       {'missing_resources': True}}
        """
        reservation_flags = collections.defaultdict(dict)

        host_ids = [h['id'] for h in failed_resources]
        reservations = db_utils.get_reservations_by_host_ids(
            host_ids, interval_begin, interval_end)

        for reservation in reservations:
            if reservation['resource_type'] != plugin.RESOURCE_TYPE:
                continue

            if self._heal_reservation(reservation, host_ids):
                if reservation['status'] == status.reservation.ACTIVE:
                    reservation_flags[reservation['id']].update(
                        {'resources_changed': True})
            else:
                reservation_flags[reservation['id']].update(
                    {'missing_resources': True})

        return reservation_flags

    def _heal_reservation(self, reservation, host_ids):
        """Allocate alternative host(s) for the given reservation.

        :param reservation: A reservation that has allocations to change
        :param host_ids: Failed host ids
        :return: True if all the allocations in the given reservation
                 are successfully allocated
        """
        lease = db_api.lease_get(reservation['lease_id'])

        ret = True
        allocations = [
            alloc for alloc in reservation['computehost_allocations']
            if alloc['compute_host_id'] in host_ids]

        if reservation['affinity']:
            old_host_id = allocations[0]['compute_host_id']
            new_host_id = self._select_host(reservation, lease)

            self._pre_reallocate(reservation, old_host_id)

            if new_host_id is None:
                for allocation in allocations:
                    db_api.host_allocation_destroy(allocation['id'])
                LOG.warning('Could not find alternative host for '
                            'reservation %s (lease: %s).',
                            reservation['id'], lease['name'])
                ret = False
            else:
                for allocation in allocations:
                    db_api.host_allocation_update(
                        allocation['id'], {'compute_host_id': new_host_id})
                self._post_reallocate(
                    reservation, lease, new_host_id, len(allocations))

        else:
            new_host_ids = []
            for allocation in allocations:
                old_host_id = allocation['compute_host_id']
                new_host_id = self._select_host(reservation, lease)

                self._pre_reallocate(reservation, old_host_id)

                if new_host_id is None:
                    db_api.host_allocation_destroy(allocation['id'])
                    LOG.warning('Could not find alternative host for '
                                'reservation %s (lease: %s).',
                                reservation['id'], lease['name'])
                    ret = False
                    continue

                db_api.host_allocation_update(
                    allocation['id'], {'compute_host_id': new_host_id})
                new_host_ids.append(new_host_id)

            for new_host, num in collections.Counter(new_host_ids).items():
                self._post_reallocate(reservation, lease, new_host, num)

        return ret

    def _select_host(self, reservation, lease):
        """Returns the alternative host id or None if not found."""
        values = {}
        values['start_date'] = max(timeutils.utcnow(), lease['start_date'])
        values['end_date'] = lease['end_date']
        specs = ['vcpus', 'memory_mb', 'disk_gb', 'affinity', 'amount',
                 'resource_properties']
        for key in specs:
            values[key] = reservation[key]
        try:
            changed_hosts = self.pickup_hosts(reservation['id'], values)
        except mgr_exceptions.NotEnoughHostsAvailable:
            return None
        # We should get at least one host to add because the old host can't
        # be in the candidates.
        return changed_hosts['added'][0]

    def _pre_reallocate(self, reservation, host_id):
        """Delete the reservation inventory/aggregates for the host."""
        pool = nova.ReservationPool()
        # Remove the failed host from the aggregate.
        if reservation['status'] == status.reservation.ACTIVE:
            host = db_api.host_get(host_id)
            pool.remove_computehost(reservation['aggregate_id'],
                                    host['service_name'])
            try:
                self.placement_client.delete_reservation_inventory(
                    host['hypervisor_hostname'], reservation['id'])
            except openstack_ex.ResourceProviderNotFound:
                pass

    def _post_reallocate(self, reservation, lease, host_id, num):
        """Add the reservation inventory/aggregates for the host."""
        pool = nova.ReservationPool()
        if reservation['status'] == status.reservation.ACTIVE:
            # Add the alternative host into the aggregate.
            new_host = db_api.host_get(host_id)
            pool.add_computehost(reservation['aggregate_id'],
                                 new_host['service_name'],
                                 stay_in=True)
            # Here we use "additional=True" not to break the existing
            # inventory(allocations) on the new host
            self.placement_client.update_reservation_inventory(
                new_host['hypervisor_hostname'], reservation['id'], num,
                additional=True)
        LOG.warning('Resource changed for reservation %s (lease: %s).',
                    reservation['id'], lease['name'])

    def _get_extra_capabilities(self, host_id):
        extra_capabilities = {}
        raw_extra_capabilities = (
            db_api.host_extra_capability_get_all_per_host(host_id))
        for capability, capability_name in raw_extra_capabilities:
            key = capability_name
            extra_capabilities[key] = capability.capability_value
        return extra_capabilities

    def get(self, host_id):
        host = db_api.host_get(host_id)
        extra_capabilities = self._get_extra_capabilities(host_id)
        if host is not None and extra_capabilities:
            res = host.copy()
            res.update(extra_capabilities)
            return res
        else:
            return host
