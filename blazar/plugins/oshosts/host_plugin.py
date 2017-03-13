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
import json
import uuid

from oslo_config import cfg
import six

from blazar.db import api as db_api
from blazar.db import exceptions as db_ex
from blazar.db import utils as db_utils
from blazar.manager import exceptions as manager_ex
from blazar.plugins import base
from blazar.plugins import oshosts as plugin
from blazar.plugins.oshosts import nova_inventory
from blazar.plugins.oshosts import reservation_pool as rp
from blazar.utils.openstack import nova
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
               help='Actions which we will use at the start of the lease')
]

CONF = cfg.CONF
CONF.register_opts(plugin_opts, group=plugin.RESOURCE_TYPE)


class PhysicalHostPlugin(base.BasePlugin, nova.NovaClientWrapper):
    """Plugin for physical host resource."""
    resource_type = plugin.RESOURCE_TYPE
    title = 'Physical Host Plugin'
    description = 'This plugin starts and shutdowns the hosts.'
    freepool_name = CONF[resource_type].aggregate_freepool_name
    pool = None

    def __init__(self):
        super(PhysicalHostPlugin, self).__init__()

    def create_reservation(self, values):
        """Create reservation."""
        pool = rp.ReservationPool()
        pool_name = str(uuid.uuid4())
        pool_instance = pool.create(name=pool_name)
        reservation_values = {
            'id': pool_name,
            'lease_id': values['lease_id'],
            'resource_id': pool_instance.id,
            'resource_type': values['resource_type'],
            'status': 'pending',
        }
        min_hosts = values.get('min')
        max_hosts = values.get('max')
        if 0 <= min_hosts and min_hosts <= max_hosts:
            count_range = str(min_hosts) + '-' + str(max_hosts)
        else:
            raise manager_ex.InvalidRange()
        reservation = db_api.reservation_create(reservation_values)
        host_values = {
            'reservation_id': reservation['id'],
            'resource_properties': values['resource_properties'],
            'hypervisor_properties': values['hypervisor_properties'],
            'count_range': count_range,
            'status': 'pending',
        }
        db_api.host_reservation_create(host_values)
        host_ids = self._matching_hosts(
            values['hypervisor_properties'],
            values['resource_properties'],
            count_range,
            values['start_date'],
            values['end_date'],
        )
        if not host_ids:
            raise manager_ex.NotEnoughHostsAvailable()
        for host_id in host_ids:
            db_api.host_allocation_create({'compute_host_id': host_id,
                                          'reservation_id': reservation['id']})

    def update_reservation(self, reservation_id, values):
        """Update reservation."""
        reservation = db_api.reservation_get(reservation_id)
        lease = db_api.lease_get(reservation['lease_id'])
        pool = rp.ReservationPool()
        hosts_in_pool = pool.get_computehosts(
            reservation['resource_id'])
        if (values['start_date'] < lease['start_date'] or
                values['end_date'] > lease['end_date']):
            allocations = []
            for allocation in db_api.host_allocation_get_all_by_values(
                    reservation_id=reservation_id):
                full_periods = db_utils.get_full_periods(
                    allocation['compute_host_id'],
                    values['start_date'],
                    values['end_date'],
                    datetime.timedelta(seconds=1))
                if lease['start_date'] < values['start_date']:
                    max_start = values['start_date']
                else:
                    max_start = lease['start_date']
                if lease['end_date'] < values['end_date']:
                    min_end = lease['end_date']
                else:
                    min_end = values['end_date']
                if not (len(full_periods) == 0 or
                        (len(full_periods) == 1 and
                         full_periods[0][0] == max_start and
                         full_periods[0][1] == min_end)):
                    allocations.append(allocation)
                    if (hosts_in_pool and
                            self.nova.hypervisors.get(
                                self._get_hypervisor_from_name_or_id(
                                    allocation['compute_host_id'])
                            ).__dict__['running_vms'] > 0):
                        raise manager_ex.NotEnoughHostsAvailable()
            if allocations:
                host_reservation = (
                    db_api.host_reservation_get_by_reservation_id(
                        reservation_id))
                host_ids = self._matching_hosts(
                    host_reservation['hypervisor_properties'],
                    host_reservation['resource_properties'],
                    str(len(allocations)) + '-' + str(len(allocations)),
                    values['start_date'],
                    values['end_date'])
                if not host_ids:
                    raise manager_ex.NotEnoughHostsAvailable()
                if hosts_in_pool:
                    old_hosts = [allocation['compute_host_id']
                                 for allocation in allocations]
                    pool.remove_computehost(reservation['resource_id'],
                                            old_hosts)
                for allocation in allocations:
                    db_api.host_allocation_destroy(allocation['id'])
                for host_id in host_ids:
                    db_api.host_allocation_create(
                        {'compute_host_id': host_id,
                         'reservation_id': reservation_id})
                    if hosts_in_pool:
                        host = db_api.host_get(host_id)
                        pool.add_computehost(reservation['resource_id'],
                                             host['service_name'])

    def on_start(self, resource_id):
        """Add the hosts in the pool."""
        reservations = db_api.reservation_get_all_by_values(
            resource_id=resource_id)
        for reservation in reservations:
            pool = rp.ReservationPool()
            for allocation in db_api.host_allocation_get_all_by_values(
                    reservation_id=reservation['id']):
                host = db_api.host_get(allocation['compute_host_id'])
                pool.add_computehost(reservation['resource_id'],
                                     host['service_name'])

    def on_end(self, resource_id):
        """Remove the hosts from the pool."""
        reservations = db_api.reservation_get_all_by_values(
            resource_id=resource_id)
        for reservation in reservations:
            db_api.reservation_update(reservation['id'],
                                      {'status': 'completed'})
            host_reservation = db_api.host_reservation_get_by_reservation_id(
                reservation['id'])
            db_api.host_reservation_update(host_reservation['id'],
                                           {'status': 'completed'})
            allocations = db_api.host_allocation_get_all_by_values(
                reservation_id=reservation['id'])
            for allocation in allocations:
                db_api.host_allocation_destroy(allocation['id'])
            pool = rp.ReservationPool()
            for host in pool.get_computehosts(reservation['resource_id']):
                for server in self.nova.servers.list(
                        search_opts={"host": host}):
                    self.nova.servers.delete(server=server)
            try:
                pool.delete(reservation['resource_id'])
            except manager_ex.AggregateNotFound:
                pass

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
            inventory = nova_inventory.NovaInventory()
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
            pool = rp.ReservationPool()
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
        # NOTE (sbauza): Only update existing extra capabilites, don't create
        #  other ones
        if values:
            cant_update_extra_capability = []
            for value in values:
                capabilities = db_api.host_extra_capability_get_all_per_name(
                    host_id,
                    value,
                )
                for raw_capability in capabilities:
                    capability = {
                        'capability_name': value,
                        'capability_value': values[value],
                    }
                    try:
                        db_api.host_extra_capability_update(
                            raw_capability['id'], capability)
                    except RuntimeError:
                        cant_update_extra_capability.append(
                            raw_capability['capability_name'])
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
            # TODO(sbauza):
            #  - Check if no leases having this host scheduled
            inventory = nova_inventory.NovaInventory()
            servers = inventory.get_servers_per_host(
                host['hypervisor_hostname'])
            if servers:
                raise manager_ex.HostHavingServers(
                    host=host['hypervisor_hostname'], servers=servers)

            try:
                pool = rp.ReservationPool()
                pool.remove_computehost(self.freepool_name,
                                        host['service_name'])
                # NOTE(sbauza): Extracapabilities will be destroyed thanks to
                #  the DB FK.
                db_api.host_destroy(host_id)
            except db_ex.BlazarDBException:
                # Nothing so bad, but we need to advert the admin
                # he has to rerun
                raise manager_ex.CantRemoveHost(host=host_id,
                                                pool=self.freepool_name)

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
            filter_array = self._convert_requirements(
                hypervisor_properties)
        if resource_properties:
            filter_array += self._convert_requirements(
                resource_properties)
        for host in db_api.host_get_all_by_queries(filter_array):
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

    def _convert_requirements(self, requirements):
        """Convert the requirements to an array of strings

        Convert the requirements to an array of strings.
        ["key op value", "key op value", ...]
        """
        # TODO(frossigneux) Support the "or" operator
        # Convert text to json
        if isinstance(requirements, six.string_types):
            try:
                requirements = json.loads(requirements)
            except ValueError:
                raise manager_ex.MalformedRequirements(rqrms=requirements)

        # Requirement list looks like ['<', '$ram', '1024']
        if self._requirements_with_three_elements(requirements):
            result = []
            if requirements[0] == '=':
                requirements[0] = '=='
            string = (requirements[1][1:] + " " + requirements[0] + " " +
                      requirements[2])
            result.append(string)
            return result
        # Remove the 'and' element at the head of the requirement list
        elif self._requirements_with_and_keyword(requirements):
            return [self._convert_requirements(x)[0]
                    for x in requirements[1:]]
        # Empty requirement list0
        elif isinstance(requirements, list) and not requirements:
            return requirements
        else:
            raise manager_ex.MalformedRequirements(rqrms=requirements)

    def _requirements_with_three_elements(self, requirements):
        """Return true if requirement list looks like ['<', '$ram', '1024']."""
        return (isinstance(requirements, list) and
                len(requirements) == 3 and
                isinstance(requirements[0], six.string_types) and
                isinstance(requirements[1], six.string_types) and
                isinstance(requirements[2], six.string_types) and
                requirements[0] in ['==', '=', '!=', '>=', '<=', '>', '<'] and
                len(requirements[1]) > 1 and requirements[1][0] == '$' and
                len(requirements[2]) > 0)

    def _requirements_with_and_keyword(self, requirements):
        return (len(requirements) > 1 and
                isinstance(requirements[0], six.string_types) and
                requirements[0] == 'and' and
                all(self._convert_requirements(x) for x in requirements[1:]))

    def _get_hypervisor_from_name_or_id(self, hypervisor_name_or_id):
        """Return an hypervisor by name or an id."""
        hypervisor = None
        all_hypervisors = self.nova.hypervisors.list()
        for hyp in all_hypervisors:
            if (hypervisor_name_or_id == hyp.hypervisor_hostname or
               hypervisor_name_or_id == str(hyp.id)):
                hypervisor = hyp
        if hypervisor:
            return hypervisor
        else:
            raise manager_ex.HypervisorNotFound(pool=hypervisor_name_or_id)
