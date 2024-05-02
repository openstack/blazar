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
import collections
import datetime
import json

from novaclient import exceptions as nova_exceptions
from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import strutils

from blazar import context
from blazar.db import api as db_api
from blazar.manager import exceptions as mgr_exceptions
from blazar.plugins import base
from blazar.plugins import flavor as plugin
from blazar.plugins.instances import instance_plugin
from blazar.plugins.oshosts import host_plugin
from blazar.utils.openstack import nova
from blazar.utils.openstack import placement

CONF = cfg.CONF
LOG = logging.getLogger(__name__)

QUERY_TYPE_ALLOCATION = 'allocation'


class FlavorPlugin(base.BasePlugin):
    """Plugin for Nova flavor-based server reservations."""

    resource_type = plugin.RESOURCE_TYPE
    title = 'Plugin for Nova flavor-based server reservations'
    description = 'Reserve compute resources modeled by Nova flavors.'

    query_options = {
        QUERY_TYPE_ALLOCATION: ['lease_id', 'reservation_id']
    }

    def __init__(self):
        super().__init__()
        self._placement_client = placement.BlazarPlacementClient()
        self._host_plugin = host_plugin.PhysicalHostPlugin()
        self._instance_plugin = instance_plugin.VirtualInstancePlugin()

    def get(self, host_id):
        return self._host_plugin.get(host_id)

    def list_allocations(self, query):
        return self._host_plugin.list_allocations(query)

    def query_allocations(self, hosts, lease_id=None, reservation_id=None):
        return self._host_plugin.query_allocations(
            hosts, lease_id, reservation_id)

    def allocation_candidates(self, reservation):
        """Return a list of candidate host_ids."""
        host_ids, _ = self._pick_hosts(reservation)
        return host_ids

    def _pick_hosts(self, reservation):
        self._validate_reservation_params(reservation)

        flavor_id = reservation['flavor_id']
        resource_request, resource_traits, source_flavor = \
            self._get_flavor_details(flavor_id)

        affinity = strutils.bool_from_string(
            reservation['affinity'], default=None)
        start_date = reservation['start_date']
        end_date = reservation['end_date']
        candidates = self._query_available_hosts(
            start_date, end_date, resource_request, resource_traits)

        # Fail if we have fewer candidates than amount requested
        req_amount = reservation['amount']
        if len(candidates) < req_amount:
            raise mgr_exceptions.NotEnoughHostsAvailable()

        if affinity is not None:
            raise mgr_exceptions.NotImplemented(
                error="Affinity not supported yet")

        # return just enough hosts to satisfy the request
        while len(candidates) > req_amount:
            candidates.pop()
        host_ids = [host['id'] for host in candidates]
        return host_ids, source_flavor

    def _validate_reservation_params(self, values):
        marshall_attributes = set([
            'amount', 'flavor_id', 'affinity', 'start_date', 'end_date',
        ])
        missing_attr = marshall_attributes - set(values.keys())
        if missing_attr:
            raise mgr_exceptions.MissingParameter(param=','.join(missing_attr))

        try:
            values['amount'] = strutils.validate_integer(
                values['amount'], "amount", 1, db_api.DB_MAX_INT)
        except ValueError as e:
            raise mgr_exceptions.MalformedParameter(str(e))

    def _query_available_hosts(self, start_date, end_date,
                               resource_request, resource_traits):
        # TODO(johngarbutt): offload more of this to the db
        # we should be able to exclude hosts that don't match the
        # resource requests, e.g. baremetal vs virtual
        # or missing traits
        if resource_traits:
            raise mgr_exceptions.NotImplemented(
                error="Resource traits not supported yet")
        hosts = db_api.reservable_host_get_all_by_queries([])

        # find reservations for each host in our time period
        free_hosts, reserved_hosts = \
            self._instance_plugin.filter_hosts_by_reservation(
                hosts,
                start_date - datetime.timedelta(minutes=CONF.cleaning_time),
                end_date + datetime.timedelta(minutes=CONF.cleaning_time),
                [])

        available_hosts = []
        for host_info in (reserved_hosts + free_hosts):
            # check how many instances can fit on this host
            hosts_list = self._get_hosts_list(host_info, resource_request)
            available_hosts.extend(hosts_list)
        return available_hosts

    def _get_hosts_list(self, host_info, resource_request):
        """For given host, work out how many instances can fit on it."""

        # For each host, look how many slots are available,
        # given the current list of reservations within the
        # target time window for this host

        # get high water mark of usage during all reservations
        max_usage = self._max_usages(host_info['reservations'])
        LOG.debug(f"Max usage {host_info['host']['hypervisor_hostname']} "
                  f"is {max_usage}")

        host = host_info['host']
        host_crs = db_api.host_resource_inventory_get_all_per_host(host['id'])
        host_inventory = {cr['resource_class']: cr for cr in host_crs}
        if not host_inventory:
            LOG.warning("host added before inventory set in DB!")
            return []
        LOG.debug(f"Inventory for {host_info['host']['hypervisor_hostname']} "
                  f"is {host_inventory}")

        # see how much room for slots we have
        hosts_list = []
        current_usage = max_usage.copy()

        def has_free_slot():
            for rc, requested in resource_request.items():
                if not requested:
                    # skip things like requests for 0 vcpus
                    continue

                host_details = host_inventory.get(rc)
                if not host_details:
                    # host doesn't have this sort of resource
                    LOG.debug(f"Resource {rc} not found for "
                              f"{host_info['host']['hypervisor_hostname']}")
                    return False
                usage = current_usage[rc]

                if requested > host_details["max_unit"]:
                    # requested more than the max allowed by this host
                    LOG.debug(f"Requested {requested} {rc} for "
                              f"{host_info['host']['hypervisor_hostname']} "
                              f"but maximum is {host_details['max_unit']}")
                    return False

                capacity = ((host_details["total"] - host_details["reserved"])
                            * host_details["allocation_ratio"])
                LOG.debug(f"Capacity is {capacity} for {rc} for "
                          f"{host_info['host']['hypervisor_hostname']}")
                if (usage + requested) > capacity:
                    LOG.debug("Current usage is %d, requested %d",
                              usage, requested)
                    return False

            # We have enough resources for all resource requests
            return True

        while (has_free_slot()):
            hosts_list.append(host)
            for rc, requested in resource_request.items():
                current_usage[rc] += requested

        LOG.debug(f"For host {host_info['host']['hypervisor_hostname']} "
                  f"we have {len(hosts_list)} slots.")
        return hosts_list

    def _get_cached_flavor(self, instance_reservation):
        source_flavor = instance_reservation["resource_properties"]
        if source_flavor and "OS-FLV-EXT-DATA:ephemeral" in source_flavor:
            return json.loads(source_flavor)

    def _max_usages(self, reservations):
        """For reservation list for a host, find resource high watermark."""
        def resource_usage_by_event(event):
            instance_reservation = event['reservation']['instance_reservation']
            request_count = instance_reservation["amount"]
            source_flavor = self._get_cached_flavor(instance_reservation)
            if source_flavor:
                flavor_resource_inventory, _ = \
                    self._estimate_flavor_resources(source_flavor)
                return {
                    rc: amount * request_count
                    for rc, amount in flavor_resource_inventory.items()
                    if amount > 0
                }
            raise mgr_exceptions.ReservationTypeConflict()

        # Get sorted list of events for all reservations
        # that exist in the target time window
        events_list = []
        for r in reservations:
            fetched_events = db_api.event_get_all_sorted_by_filters(
                sort_key='time', sort_dir='asc',
                filters={'lease_id': r['lease_id']})
            events_list.extend([{'event': e, 'reservation': r}
                                for e in fetched_events])
        events_list.sort(key=lambda x: x['event']['time'])

        current_usage = collections.defaultdict(int)
        max_usage = collections.defaultdict(int)
        for event in events_list:
            usage = resource_usage_by_event(event)

            if event['event']['event_type'] == 'start_lease':
                LOG.debug(f"found start{event} with {usage}")
                for rc, usage_amount in usage.items():
                    current_usage[rc] += usage_amount
                    # TODO(johngarbutt) what if the max usage is
                    # actually outside the target time window?
                    if max_usage[rc] < current_usage[rc]:
                        max_usage[rc] = current_usage[rc]

            elif event['event']['event_type'] == 'end_lease':
                for rc, usage_amount in usage.items():
                    current_usage[rc] -= usage_amount

            LOG.debug(f"after {event}\nusage is: {current_usage}\n"
                      f"max is: {max_usage}")
        return max_usage

    def _get_flavor_details(self, flavor_id):
        # access nova using the user token,
        # to ensure we can only see flavors they can see
        user_client = nova.NovaClientWrapper()
        flavor = user_client.nova.nova.flavors.get(flavor_id)
        source_flavor = flavor.to_dict()
        # TODO(johngarbutt): use newer api to get this above
        source_flavor["extra_specs"] = flavor.get_keys()
        if 'links' in source_flavor.keys():
            del source_flavor['links']

        # NOTE(johngarbutt): we are only partially reproducing all the
        # options that are available in a flavor.
        resource_request, resource_traits = \
            self._estimate_flavor_resources(source_flavor)

        return (resource_request, resource_traits, source_flavor)

    def _estimate_flavor_resources(self, source_flavor):
        resource_request = {}
        resource_traits = {}

        # add default resource requests
        resource_request["VCPU"] = int(source_flavor['vcpus'])
        resource_request["MEMORY_MB"] = int(source_flavor['ram'])
        # NOTE(priteau): This reserves resources for the root disk even if the
        # instance will boot from volume.
        resource_request["DISK_GB"] = (
            int(source_flavor['disk']) +
            int(source_flavor['OS-FLV-EXT-DATA:ephemeral']))

        # Check for PCPUs
        hw_cpu_policy = source_flavor['extra_specs'].get("hw:cpu_policy")
        if hw_cpu_policy == "dedicated":
            resource_request["PCPU"] = source_flavor['vcpus']
            resource_request["VCPU"] = 0

        # Check for traits and extra resources
        for key, value in source_flavor['extra_specs'].items():
            if key.startswith("trait:"):
                trait = key.split(":")[1]
                if value == "required":
                    resource_traits[trait] = "required"
                elif value == "forbidden":
                    resource_traits[trait] = "forbidden"
                else:
                    raise mgr_exceptions.MalformedParameter(
                        "Invalid value for trait %s" % trait)

            if key.startswith("resources:"):
                rc = key.split(":")[1]
                resource_request[rc] = int(value)

        # TODO(johngarbutt): look for other extra specs that we
        # don't support and error out the reservation if we find any

        return (resource_request, resource_traits)

    def reserve_resource(self, reservation_id, values):
        host_ids, source_flavor = self._pick_hosts(values)

        instance_reservation_val = {
            'reservation_id': reservation_id,
            # use flavor display values,
            # even though we probably reserve different resources
            'vcpus': source_flavor["vcpus"],
            'memory_mb': source_flavor["ram"],
            'disk_gb': source_flavor["disk"],
            'amount': values['amount'],
            'affinity': None,
            'resource_properties': json.dumps(source_flavor)
        }
        instance_reservation = db_api.instance_reservation_create(
            instance_reservation_val)

        for host_id in host_ids:
            db_api.host_allocation_create({'compute_host_id': host_id,
                                          'reservation_id': reservation_id})

        try:
            flavor_id, aggregate_id = \
                self._create_resources(instance_reservation)
        except nova_exceptions.ClientException:
            LOG.exception("Failed to create Nova resources "
                          "for reservation %s", reservation_id)
            self._cleanup_resources(instance_reservation)
            raise mgr_exceptions.NovaClientError()

        db_api.instance_reservation_update(instance_reservation['id'],
                                           {'flavor_id': flavor_id,
                                            'aggregate_id': aggregate_id})

        return instance_reservation['id']

    def _create_resources(self, instance_reservation):
        reservation_id = instance_reservation['reservation_id']
        # TODO(johngarbutt) we ignore affinity for now
        # user_client = nova.NovaClientWrapper()
        # reserved_group = user_client.nova.server_groups.create(
        #    instance_plugin.RESERVATION_PREFIX + ':' + reservation_id,
        #    'affinity' if inst_reservation['affinity'] else 'anti-affinity'
        #    )

        reserved_flavor = self._create_flavor(instance_reservation)

        ctx = context.current()
        pool = nova.ReservationPool()
        pool_metadata = {
            instance_plugin.RESERVATION_PREFIX: reservation_id,
            # this is added to work with Nova configuration options
            # [scheduler]limit_tenants_to_placement_aggregate=True and
            # [scheduler]placement_aggregate_required_for_tenants=True
            'filter_tenant_id': ctx.project_id,
        }
        agg = pool.create(name=reservation_id, metadata=pool_metadata)

        # TODO(johngarbutt) maybe add inventory here, but mark
        # then inventory as reserved to start with?
        self._placement_client.create_reservation_class(reservation_id)

        return reserved_flavor.id, agg.id

    def _create_flavor(self, instance_reservation):
        source_flavor = self._get_cached_flavor(instance_reservation)
        if not source_flavor:
            raise mgr_exceptions.ReservationTypeConflict()

        reservation_id = instance_reservation['reservation_id']
        flavor_details = {
            'flavorid': reservation_id,
            'name': instance_plugin.RESERVATION_PREFIX + ":" + reservation_id,
            'vcpus': source_flavor['vcpus'],
            'ram': source_flavor['ram'],
            'disk': source_flavor['disk'],
            'is_public': False
        }
        # create flavor using admin access
        reserved_flavor = self._instance_plugin.nova.nova.flavors.create(
            **flavor_details)

        # Set extra specs to the flavor
        rsv_id_rc_format = reservation_id.upper().replace("-", "_")
        reservation_rc = "resources:CUSTOM_RESERVATION_" + rsv_id_rc_format
        extra_specs = source_flavor["extra_specs"].copy()
        extra_specs[instance_plugin.FLAVOR_EXTRA_SPEC] = reservation_id
        extra_specs[reservation_rc] = "1"
        reserved_flavor.set_keys(extra_specs)

        return reserved_flavor

    def _cleanup_resources(self, instance_reservation):
        self._instance_plugin.cleanup_resources(instance_reservation)

    def update_reservation(self, reservation_id, values):
        raise mgr_exceptions.NotImplemented(
            error="Flavor-based reservation update not yet supported")

    def on_start(self, resource_id):
        self._instance_plugin.on_start(resource_id)

    def on_end(self, resource_id):
        self._instance_plugin.on_end(resource_id)
