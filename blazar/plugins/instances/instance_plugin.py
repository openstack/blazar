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

from novaclient import exceptions as nova_exceptions
from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils.strutils import bool_from_string

from blazar import context
from blazar.db import api as db_api
from blazar.db import utils as db_utils
from blazar import exceptions
from blazar.manager import exceptions as mgr_exceptions
from blazar.plugins import base
from blazar.plugins import oshosts
from blazar.utils.openstack import nova
from blazar.utils import plugins as plugins_utils

CONF = cfg.CONF
LOG = logging.getLogger(__name__)

RESOURCE_TYPE = u'virtual:instance'
RESERVATION_PREFIX = 'reservation'
FLAVOR_EXTRA_SPEC = "aggregate_instance_extra_specs:" + RESERVATION_PREFIX


class VirtualInstancePlugin(base.BasePlugin, nova.NovaClientWrapper):
    """Plugin for virtual instance resources."""

    resource_type = RESOURCE_TYPE
    title = 'Virtual Instance Plugin'

    def __init__(self):
        super(VirtualInstancePlugin, self).__init__(
            username=CONF.os_admin_username,
            password=CONF.os_admin_password,
            user_domain_name=CONF.os_admin_user_domain_name,
            project_name=CONF.os_admin_project_name,
            project_domain_name=CONF.os_admin_user_domain_name)

        self.freepool_name = CONF.nova.aggregate_freepool_name

    def filter_hosts_by_reservation(self, hosts, start_date, end_date):
        free = []
        non_free = []

        for host in hosts:
            reservations = db_utils.get_reservations_by_host_id(host['id'],
                                                                start_date,
                                                                end_date)
            if reservations == []:
                free.append({'host': host, 'reservations': None})
            elif not filter(lambda x: x['resource_type'] ==
                            oshosts.RESOURCE_TYPE, reservations):
                non_free.append({'host': host, 'reservations': reservations})

        return free, non_free

    def max_usages(self, host, reservations):
        def resource_usage_by_event(event, resource_type):
            return event['reservation']['instance_reservations'][resource_type]

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

    def pickup_hosts(self, cpus, memory, disk, amount, start_date, end_date):
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
        flavor_definitions = [
            'and',
            [">=", "$vcpus", str(cpus)],
            [">=", "$memory_mb", str(memory)],
            [">=", "$local_gb", str(disk)],
            ]

        filters = plugins_utils.convert_requirements(flavor_definitions)

        hosts = db_api.host_get_all_by_queries(filters)

        free_hosts, reserved_hosts = \
            self.filter_hosts_by_reservation(hosts, start_date, end_date)

        host_ids = []
        for host_info in reserved_hosts:
            host = host_info['host']
            reservations = host_info['reservations']
            max_cpus, max_memory, max_disk = self.max_usages(host,
                                                             reservations)

            if not (max_cpus + cpus > host['vcpus'] or
                    max_memory + memory > host['memory_mb'] or
                    max_disk + disk > host['local_gb']):
                host_ids.append(host['id'])

        if len(host_ids) >= int(amount):
            return host_ids[:int(amount)]
        elif len(host_ids) + len(free_hosts) >= int(amount):
            host_ids.extend([h['host']['id'] for h in free_hosts])
            return host_ids[:int(amount)]
        else:
            raise mgr_exceptions.HostNotFound("The reservation can't be "
                                              "accommodate because of less "
                                              "capacity.")

    def _create_resources(self, instance_reservation):
        reservation_id = instance_reservation['reservation_id']

        ctx = context.current()
        user_client = nova.NovaClientWrapper()

        reserved_group = user_client.nova.server_groups.create(
            RESERVATION_PREFIX + ':' + reservation_id,
            'affinity' if instance_reservation['affinity'] else 'anti-affinity'
            )

        flavor_details = {
            'flavorid': reservation_id,
            'name': RESERVATION_PREFIX + ":" + reservation_id,
            'vcpus': instance_reservation['vcpus'],
            'ram': instance_reservation['memory_mb'],
            'disk': instance_reservation['disk_gb'],
            'is_public': False
            }
        reserved_flavor = self.nova.nova.flavors.create(**flavor_details)
        extra_specs = {
            FLAVOR_EXTRA_SPEC: reservation_id,
            "affinity_id": reserved_group.id
            }
        reserved_flavor.set_keys(extra_specs)

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

    def validate_reservation_param(self, values):
        marshall_attributes = set(['vcpus', 'memory_mb', 'disk_gb',
                                   'amount', 'affinity'])
        missing_params = marshall_attributes - set(values.keys())
        if missing_params:
            mgr_exceptions.MissingParameter(param=','.join(missing_params))

    def reserve_resource(self, reservation_id, values):
        self.validate_reservation_param(values)

        # TODO(masahito) the instance reservation plugin only supports
        # anti-affinity rule in short-term goal.
        if bool_from_string(values['affinity']):
            raise exceptions.BlazarException('affinity = True is not '
                                             'supported.')

        host_ids = self.pickup_hosts(values['vcpus'], values['memory_mb'],
                                     values['disk_gb'], values['amount'],
                                     values['start_date'], values['end_date'])

        instance_reservation_val = {
            'reservation_id': reservation_id,
            'vcpus': values['vcpus'],
            'memory_mb': values['memory_mb'],
            'disk_gb': values['disk_gb'],
            'amount': values['amount'],
            'affinity': bool_from_string(values['affinity']),
            }
        instance_reservation = db_api.instance_reservation_create(
            instance_reservation_val)

        for host_id in host_ids:
            db_api.host_allocation_create({'compute_host_id': host_id,
                                          'reservation_id': reservation_id})

        try:
            flavor, group, pool = self._create_resources(instance_reservation)
        except nova_exceptions.ClientException:
            LOG.exception("Failed to create Nova resources "
                          "for reservation %s" % reservation_id)
            self.cleanup_resources(instance_reservation)
            raise mgr_exceptions.NovaClientError()

        db_api.instance_reservation_update(instance_reservation['id'],
                                           {'flavor_id': flavor.id,
                                            'server_group_id': group.id,
                                            'aggregate_id': pool.id})

        return instance_reservation['id']

    def update_reservation(self, reservation_id, values):
        raise NotImplementedError("resource type virtual:instance doesn't "
                                  "support updates of reservation.")

    def on_start(self, resource_id):
        pass

    def on_end(self, resource_id):
        pass
