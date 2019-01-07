# -*- coding: utf-8 -*-
#
# Author: Pierre Riteau <pierre@stackhpc.com>
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
from random import shuffle

from ironicclient import client as ironic_client
from keystoneauth1 import identity
from keystoneauth1 import session
from neutronclient.common import exceptions as neutron_ex
from neutronclient.v2_0 import client as neutron_client
from oslo_config import cfg
from oslo_log import log as logging

from blazar.db import api as db_api
from blazar.db import exceptions as db_ex
from blazar.db import utils as db_utils
from blazar.manager import exceptions as manager_ex
from blazar.plugins import base
from blazar.plugins import networks as plugin
from blazar import status
from blazar.utils import plugins as plugins_utils

plugin_opts = [
    cfg.IntOpt('available_vfcs',
               default=63,
               help='Number of VFCs available for allocation to users'),
    cfg.IntOpt('available_vfc_resources',
               default=100,
               help='Amount of resources available for VFCs allocated to '
                    'users'),
    cfg.IntOpt('resources_per_vfc',
               default=2,
               help='Default amount of resources allocated for each VFC'),
]

CONF = cfg.CONF
CONF.register_opts(plugin_opts, group=plugin.RESOURCE_TYPE)
LOG = logging.getLogger(__name__)


before_end_options = ['', 'snapshot', 'default', 'email']


class NetworkPlugin(base.BasePlugin):
    """Plugin for network resource."""
    resource_type = plugin.RESOURCE_TYPE
    title = 'Network Plugin'
    description = 'This plugin creates and deletes networks.'

    def __init__(self):
        super(NetworkPlugin, self).__init__()
        self.usage_enforcer = None

    def set_usage_enforcer(self, usage_enforcer):
        self.usage_enforcer = usage_enforcer

    def filter_networks_by_reservation(self, networks, start_date, end_date):
        free = []
        non_free = []

        for network in networks:
            reservations = db_utils.get_reservations_by_network_id(
                network['id'], start_date, end_date)

            if reservations == []:
                free.append({'network': network, 'reservations': None})
            elif [r for r in reservations
                  if r['resource_type'] == self.resource_type]:
                non_free.append(
                    {'network': network, 'reservations': reservations})

        return free, non_free

    def query_available_resources(self, start_date, end_date):
        def resource_usage_by_event(event, resource_type):
            return event['reservation']['network_reservation'][resource_type]

        all_networks = db_api.network_get_all_by_queries([])
        free_networks, reserved_networks = self.filter_networks_by_reservation(
            all_networks,
            start_date - datetime.timedelta(minutes=CONF.cleaning_time),
            end_date + datetime.timedelta(minutes=CONF.cleaning_time))

        reservations = []
        for network_info in reserved_networks:
            reservations += network_info['reservations']

        events_list = []
        for r in reservations:
            fetched_events = db_api.event_get_all_sorted_by_filters(
                sort_key='time', sort_dir='asc',
                filters={'lease_id': r['lease_id']})
            events_list.extend([{'event': e, 'reservation': r}
                                for e in fetched_events])

        events_list.sort(key=lambda x: x['event']['time'])

        max_vfcs = max_vfc_resources = 0
        current_vfcs = current_vfc_resources = 0

        for event in events_list:
            if event['event']['event_type'] == 'start_lease':
                # TODO(priteau): This doesn't yet take into account networks
                # sharing a single VFC
                current_vfcs += 1
                current_vfc_resources += resource_usage_by_event(
                    event, 'vfc_resources')
                if max_vfcs < current_vfcs:
                    max_vfcs = current_vfcs
                if max_vfc_resources < current_vfc_resources:
                    max_vfc_resources = current_vfc_resources
            elif event['event']['event_type'] == 'end_lease':
                current_vfcs -= 1
                current_vfc_resources -= resource_usage_by_event(
                    event, 'vfc_resources')

        return (CONF[self.resource_type].available_vfcs - max_vfcs,
                CONF[self.resource_type].available_vfc_resources -
                max_vfc_resources)

    def check_vfc_resources(self, reservation_id, values):
        free_vfcs, free_vfc_resources = self.query_available_resources(
            values['start_date'],
            values['end_date'])

        if free_vfcs < 1:
            raise manager_ex.NotEnoughNetworksAvailable(
                "The reservation cannot be accommodated because no free VFC "
                "is available.")

        if free_vfc_resources < values['vfc_resources']:
            raise manager_ex.NotEnoughNetworksAvailable(
                "The reservation cannot be accommodated because not enough "
                "VFC resources are available.")

    def reserve_resource(self, reservation_id, values):
        """Create reservation."""
        self._check_params(values)

        lease = db_api.lease_get(values['lease_id'])
        network_ids = self._matching_networks(
            values['network_properties'],
            values['resource_properties'],
            values['start_date'],
            values['end_date'],
        )
        if not network_ids:
            raise manager_ex.NotEnoughNetworksAvailable()

        values['vfc_resources'] = CONF[self.resource_type].resources_per_vfc
        self.check_vfc_resources(reservation_id, values)

        # NOTE(priteau): Check if we have enough available SUs for this
        # reservation. This takes into account the su_factor of each allocated
        # network, if present.
        try:
            self.usage_enforcer.check_usage_against_allocation(
                lease, allocated_network_ids=network_ids)
        except manager_ex.RedisConnectionError:
            pass

        network_rsrv_values = {
            'reservation_id': reservation_id,
            'network_properties': values['network_properties'],
            'resource_properties': values['resource_properties'],
            'status': 'pending',
            'before_end': values['before_end'],
            'network_name': values['network_name'],
            'network_description': values.get('network_description'),
            'vfc_resources': values['vfc_resources'],
        }
        network_reservation = db_api.network_reservation_create(
            network_rsrv_values)
        for network_id in network_ids:
            db_api.network_allocation_create({
                'network_id': network_id, 'reservation_id': reservation_id})
        return network_reservation['id']

    def update_reservation(self, reservation_id, values):
        """Update reservation."""
        reservation = db_api.reservation_get(reservation_id)
        lease = db_api.lease_get(reservation['lease_id'])
        network_allocations = db_api.network_allocation_get_all_by_values(
            reservation_id=reservation_id)

        if (not [x for x in values.keys() if x in ['network_properties',
                                                   'resource_properties']]
                and values['start_date'] >= lease['start_date']
                and values['end_date'] <= lease['end_date']):
            # Nothing to update
            try:
                self.usage_enforcer.check_usage_against_allocation_post_update(
                    values, lease,
                    network_allocations,
                    network_allocations)
            except manager_ex.RedisConnectionError:
                pass

            return

        # Check if we have enough available SUs for update
        try:
            self.usage_enforcer.check_usage_against_allocation_pre_update(
                values, lease, network_allocations)
        except manager_ex.RedisConnectionError:
            pass

        dates_before = {'start_date': lease['start_date'],
                        'end_date': lease['end_date']}
        dates_after = {'start_date': values['start_date'],
                       'end_date': values['end_date']}
        network_reservation = db_api.network_reservation_get(
            reservation['resource_id'])
        self._update_allocations(dates_before, dates_after, reservation_id,
                                 reservation['status'], network_reservation,
                                 values, lease)

        updates = {}
        if 'network_properties' in values:
            updates['network_properties'] = values.get(
                'network_properties')
        if 'resource_properties' in values:
            updates['resource_properties'] = values.get(
                'resource_properties')
        if updates:
            db_api.network_reservation_update(
                network_reservation['id'], updates)

    def ironic(self):
        auth_url = "%s://%s:%s/%s" % (CONF.os_auth_protocol,
                                      CONF.os_auth_host,
                                      CONF.os_auth_port,
                                      CONF.os_auth_prefix)
        auth = identity.Password(
            auth_url=auth_url,
            username=CONF.os_admin_username,
            password=CONF.os_admin_password,
            project_name=CONF.os_admin_project_name,
            project_domain_name=CONF.os_admin_project_domain_name,
            user_domain_name=CONF.os_admin_user_domain_name)
        sess = session.Session(auth=auth)
        return ironic_client.get_client(1,
                                        session=sess,
                                        os_ironic_api_version='1.31',
                                        os_region_name=CONF.os_region_name)

    def neutron(self, trust_id=None):
        auth_url = "%s://%s:%s/%s" % (CONF.os_auth_protocol,
                                      CONF.os_auth_host,
                                      CONF.os_auth_port,
                                      CONF.os_auth_prefix)
        kwargs = {
            'auth_url': auth_url,
            'username': CONF.os_admin_username,
            'password': CONF.os_admin_password,
            'project_domain_name': CONF.os_admin_project_domain_name,
            'user_domain_name': CONF.os_admin_user_domain_name
        }
        if trust_id is not None:
            kwargs['trust_id'] = trust_id
        else:
            kwargs['project_name'] = CONF.os_admin_project_name
        auth = identity.Password(**kwargs)
        sess = session.Session(auth=auth)
        neutron = neutron_client.Client(
            session=sess, region_name=CONF.os_region_name)
        return neutron

    def on_start(self, resource_id):
        """Creates a Neutron network using the allocated segment."""
        network_reservation = db_api.network_reservation_get(resource_id)
        network_name = network_reservation['network_name']
        network_description = network_reservation['network_description']
        reservation_id = network_reservation['reservation_id']

        # We need the lease to get to the trust_id
        reservation = db_api.reservation_get(reservation_id)
        lease = db_api.lease_get(reservation['lease_id'])

        for allocation in db_api.network_allocation_get_all_by_values(
                reservation_id=reservation_id):
            network_segment = db_api.network_get(allocation['network_id'])
            network_type = network_segment['network_type']
            physical_network = network_segment['physical_network']
            segment_id = network_segment['segment_id']
            neutron = self.neutron(trust_id=lease['trust_id'])
            network_body = {
                "network": {
                    "name": network_name,
                    "provider:network_type": network_type,
                    "provider:segmentation_id": segment_id,
                }
            }

            if physical_network:
                network_body['network']['provider:physical_network'] = (
                    physical_network)

            if network_description:
                network_body['network']['description'] = network_description

            try:
                network = neutron.create_network(body=network_body)
                network_dict = network['network']
                network_id = network_dict['id']
                db_api.network_reservation_update(network_reservation['id'],
                                                  {'network_id': network_id})
            except Exception as e:
                LOG.error("create_network failed: %s", e)
                raise manager_ex.NetworkCreationFailed(name=network_name,
                                                       id=reservation_id,
                                                       msg=str(e))

    def delete_port(self, neutron, ironic, port):
        if port['binding:vnic_type'] == 'baremetal':
            node = port.get('binding:host_id')
            if node:
                ironic.node.vif_detach(node, port['id'])
            else:
                raise Exception("Expected to find attribute binding:host_id "
                                "on port %s" % port['id'])

        neutron.delete_port(port['id'])

    def delete_subnet(self, neutron, subnet_id):
        neutron.delete_subnet(subnet_id)

    def delete_router(self, neutron, router_id):
        neutron.remove_gateway_router(router_id)
        neutron.delete_router(router_id)

    def delete_neutron_network(self, network_id, reservation_id,
                               trust_id=None):
        if network_id is None:
            LOG.info("Not deleting network for reservation %s as no network "
                     "ID was recorded",
                     reservation_id)
            return

        neutron = self.neutron(trust_id=trust_id)

        try:
            neutron.show_network(network_id)
        except neutron_ex.NetworkNotFoundClient:
            LOG.info("Not deleting network %s as it could not be found",
                     network_id)
            return

        try:
            ports = neutron.list_ports(network_id=network_id)
            instance_ports = neutron.list_ports(
                device_owner='compute:nova', network_id=network_id)
            for instance_port in instance_ports['ports']:
                self.delete_port(neutron, self.ironic(), instance_port)

            router_ids = [port['device_id'] for port in ports['ports'] if
                          port['device_owner'] == 'network:router_interface']
            for router_id in router_ids:
                router_ports = neutron.list_ports(device_id=router_id)

                # Remove static routes
                neutron.update_router(
                    router_id, body={'router': {'routes': []}})

                # Remove subnets
                subnets = set()
                for router_port in router_ports['ports']:
                    if router_port['device_owner'] != 'network:router_gateway':
                        for fixed_ip in router_port['fixed_ips']:
                            subnets.update([fixed_ip['subnet_id']])
                for subnet_id in subnets:
                    body = {}
                    body['subnet_id'] = subnet_id
                    neutron.remove_interface_router(router_id, body=body)

                # Delete external gateway and router
                self.delete_router(neutron, router_id)

            subnets = neutron.list_subnets(network_id=network_id)
            for subnet in subnets['subnets']:
                self.delete_subnet(neutron, subnet['id'])

            neutron.delete_network(network_id)
        except Exception:
            LOG.exception("Failed to delete network %s", network_id)
            raise manager_ex.NetworkDeletionFailed(
                network_id=network_id, reservation_id=reservation_id)

    def on_end(self, resource_id):
        """Delete the Neutron network created when the lease started.

        We first need to delete associated Neutron resources.
        """

        network_reservation = db_api.network_reservation_get(resource_id)
        reservation_id = network_reservation['reservation_id']

        # We need the lease to get to the trust_id
        reservation = db_api.reservation_get(reservation_id)
        lease = db_api.lease_get(reservation['lease_id'])
        db_api.network_reservation_update(network_reservation['id'],
                                          {'status': 'completed'})
        allocations = db_api.network_allocation_get_all_by_values(
            reservation_id=network_reservation['reservation_id'])
        for allocation in allocations:
            db_api.network_allocation_destroy(allocation['id'])
        network_id = network_reservation['network_id']

        # The call to delete must be done without trust_id so the admin role is
        # used
        self.delete_neutron_network(network_id, reservation_id)

        reservation = db_api.reservation_get(
            network_reservation['reservation_id'])
        lease = db_api.lease_get(reservation['lease_id'])
        try:
            self.usage_enforcer.release_encumbered(
                lease, reservation, allocations)
        except manager_ex.RedisConnectionError:
            pass

    def _get_extra_capabilities(self, network_id):
        extra_capabilities = {}
        raw_extra_capabilities = (
            db_api.network_extra_capability_get_all_per_network(network_id))
        for capability in raw_extra_capabilities:
            key = capability['capability_name']
            extra_capabilities[key] = capability['capability_value']
        return extra_capabilities

    def get_network(self, network_id):
        network = db_api.network_get(network_id)
        extra_capabilities = self._get_extra_capabilities(network_id)
        if network is not None and extra_capabilities:
            res = network.copy()
            res.update(extra_capabilities)
            return res
        else:
            return network

    def list_networks(self):
        raw_network_list = db_api.network_list()
        network_list = []
        for network in raw_network_list:
            network_list.append(self.get_network(network['id']))
        return network_list

    def validate_network_param(self, values):
        marshall_attributes = set(['network_type', 'physical_network',
                                   'segment_id'])
        missing_attr = marshall_attributes - set(values.keys())
        if missing_attr:
            raise manager_ex.MissingParameter(param=','.join(missing_attr))

    def create_network(self, values):
        if 'trust_id' in values:
            del values['trust_id']

        # TODO(priteau): check that no network is using this segmentation_id
        self.validate_network_param(values)
        network_type = values.get('network_type')
        physical_network = values.get('physical_network')
        segment_id = values.get('segment_id')
        if network_type != 'vlan' and network_type != 'vxlan':
            raise manager_ex.MalformedParameter(param=network_type)

        # Check that VLAN segmentation ID is valid
        try:
            segment_id = int(segment_id)
        except ValueError:
            raise manager_ex.MalformedParameter(param=segment_id)
        if segment_id < 1 or segment_id > 4094:
            raise manager_ex.MalformedParameter(param=segment_id)

        network_values = {
            'network_type': network_type,
            'physical_network': physical_network,
            'segment_id': segment_id
        }
        network = db_api.network_create(network_values)

        to_store = set(values.keys()) - set(network.keys())
        extra_capabilities_keys = to_store
        extra_capabilities = dict(
            (key, values[key]) for key in extra_capabilities_keys
        )
        if any([len(key) > 64 for key in extra_capabilities_keys]):
            raise manager_ex.ExtraCapabilityTooLong()

        cantaddextracapability = []
        for key in extra_capabilities:
            values = {'network_id': network['id'],
                      'capability_name': key,
                      'capability_value': extra_capabilities[key],
                      }
            try:
                db_api.network_extra_capability_create(values)
            except db_ex.BlazarDBException:
                cantaddextracapability.append(key)
        if cantaddextracapability:
            raise manager_ex.CantAddExtraCapability(
                keys=cantaddextracapability,
                host=network['id'])
        return self.get_network(network['id'])

    def is_updatable_extra_capability(self, capability):
        reservations = db_utils.get_reservations_by_network_id(
            capability['network_id'], datetime.datetime.utcnow(),
            datetime.date.max)

        for r in reservations:
            plugin_reservation = db_utils.get_plugin_reservation(
                r['resource_type'], r['resource_id'])

            requirements_queries = plugins_utils.convert_requirements(
                plugin_reservation['resource_properties'])

            # TODO(masahito): If all the reservations using the
            # extra_capability can be re-allocated it's okay to update
            # the extra_capability.
            for requirement in requirements_queries:
                # A requirement is of the form "key op value" as string
                if requirement.split(" ")[0] == capability['capability_name']:
                    return False
        return True

    def update_network(self, network_id, values):
        # nothing to update
        if not values:
            return self.get_network(network_id)

        network = db_api.network_get(network_id)
        if not network:
            raise manager_ex.NetworkNotFound(network=network_id)

        updatable = ['network_type', 'physical_network', 'segment_id']

        network_type = values.get('network_type')
        if network_type == 'vlan':
            segment_id = values.get('segment_id')
            if segment_id is not None:
                try:
                    segment_id = int(segment_id)
                except ValueError:
                    raise manager_ex.MalformedParameter(param=segment_id)
                if segment_id < 1 or segment_id > 4094:
                    raise manager_ex.MalformedParameter(param=segment_id)

        new_values = {}
        for key in updatable:
            if key in values and values[key] is not None:
                new_values[key] = values[key]
        db_api.network_update(network_id, new_values)

        cant_update_extra_capability = []
        previous_capabilities = self._get_extra_capabilities(network_id)
        updated_keys = set(values.keys()) & set(previous_capabilities.keys())
        new_keys = set(values.keys()) - set(previous_capabilities.keys())

        for key in updated_keys:
            raw_capability = next(iter(
                db_api.network_extra_capability_get_all_per_name(
                    network_id, key)))
            capability = {
                'capability_name': key,
                'capability_value': values[key],
            }
            if self.is_updatable_extra_capability(raw_capability):
                try:
                    db_api.network_extra_capability_update(
                        raw_capability['id'], capability)
                except (db_ex.BlazarDBException, RuntimeError):
                    cant_update_extra_capability.append(
                        raw_capability['capability_name'])
            else:
                LOG.info("Capability %s can't be updated because "
                         "existing reservations require it.",
                         raw_capability['capability_name'])
                cant_update_extra_capability.append(
                    raw_capability['capability_name'])

        for key in new_keys:
            new_capability = {
                'network_id': network_id,
                'capability_name': key,
                'capability_value': values[key],
            }
            try:
                db_api.network_extra_capability_create(new_capability)
            except (db_ex.BlazarDBException, RuntimeError):
                cant_update_extra_capability.append(
                    new_capability['capability_name'])

        if cant_update_extra_capability:
            raise manager_ex.CantAddExtraCapability(
                network=network_id, keys=cant_update_extra_capability)

        LOG.info('Extra capabilities on network %s updated with %s',
                 network_id, values)

    def delete_network(self, network_id):
        network = db_api.network_get(network_id)
        if not network:
            raise manager_ex.NetworkNotFound(network=network_id)

        if db_api.network_allocation_get_all_by_values(
                network_id=network_id):
            raise manager_ex.CantDeleteNetwork(
                network=network_id,
                msg='The network is reserved.'
            )

        try:
            db_api.network_destroy(network_id)
        except db_ex.BlazarDBException as e:
            # Nothing so bad, but we need to alert admins
            # they have to rerun
            raise manager_ex.CantDeleteNetwork(network=network_id, msg=str(e))

    def _matching_networks(self, network_properties, resource_properties,
                           start_date, end_date):
        """Return the matching networks (preferably not allocated)"""
        allocated_network_ids = []
        not_allocated_network_ids = []
        filter_array = []
        start_date_with_margin = start_date - datetime.timedelta(
            minutes=CONF.cleaning_time)
        end_date_with_margin = end_date + datetime.timedelta(
            minutes=CONF.cleaning_time)

        # TODO(frossigneux) support "or" operator
        if network_properties:
            filter_array = plugins_utils.convert_requirements(
                network_properties)
        if resource_properties:
            filter_array += plugins_utils.convert_requirements(
                resource_properties)
        for network in db_api.network_get_all_by_queries(
                filter_array):
            if not db_api.network_allocation_get_all_by_values(
                    network_id=network['id']):
                not_allocated_network_ids.append(network['id'])
            elif db_utils.get_free_periods(
                network['id'],
                start_date_with_margin,
                end_date_with_margin,
                end_date_with_margin - start_date_with_margin,
                resource_type='network'
            ) == [
                (start_date_with_margin, end_date_with_margin),
            ]:
                allocated_network_ids.append(network['id'])
        if len(not_allocated_network_ids) >= 1:
            shuffle(not_allocated_network_ids)
            return not_allocated_network_ids[:1]
        all_network_ids = allocated_network_ids + not_allocated_network_ids
        if len(all_network_ids) >= 1:
            shuffle(all_network_ids)
            return all_network_ids[:1]
        else:
            return []

    def _check_params(self, values):
        required_values = ['network_name', 'network_properties',
                           'resource_properties']
        for value in required_values:
            if value not in values:
                raise manager_ex.MissingParameter(param=value)

        if 'network_description' in values:
            values['network_description'] = str(values['network_description'])

        if 'before_end' not in values:
            values['before_end'] = 'default'
        if values['before_end'] not in before_end_options:
            raise manager_ex.MalformedParameter(param='before_end')

    def _update_allocations(self, dates_before, dates_after, reservation_id,
                            reservation_status, network_reservation, values,
                            lease):
        network_properties = values.get(
            'network_properties',
            network_reservation['network_properties'])
        resource_properties = values.get(
            'resource_properties',
            network_reservation['resource_properties'])
        allocs = db_api.network_allocation_get_all_by_values(
            reservation_id=reservation_id)

        allocs_to_remove = self._allocations_to_remove(
            dates_before, dates_after, network_properties,
            resource_properties, allocs)

        if (allocs_to_remove and
                reservation_status == status.reservation.ACTIVE):
            raise manager_ex.NotEnoughNetworksAvailable()

        kept_networks = len(allocs) - len(allocs_to_remove)
        network_ids_to_add = []
        if kept_networks < 1:
            min_networks = 1 - kept_networks \
                if (1 - kept_networks) > 0 else 0
            max_networks = 1 - kept_networks
            network_ids_to_add = self._matching_networks(
                network_properties, resource_properties,
                str(min_networks) + '-' + str(max_networks),
                dates_after['start_date'], dates_after['end_date'])

            if len(network_ids_to_add) < min_networks:
                raise manager_ex.NotEnoughNetworksAvailable()

        allocs_to_keep = [a for a in allocs if a not in allocs_to_remove]
        allocs_to_add = [{'network_id': n} for n in network_ids_to_add]
        new_allocations = allocs_to_keep + allocs_to_add

        try:
            self.usage_enforcer.check_usage_against_allocation_post_update(
                values, lease,
                allocs,
                new_allocations)
        except manager_ex.RedisConnectionError:
            pass

        for network_id in network_ids_to_add:
            LOG.debug('Adding network {} to reservation {}'.format(
                network_id, reservation_id))
            db_api.network_allocation_create(
                {'network_id': network_id,
                 'reservation_id': reservation_id})

        for allocation in allocs_to_remove:
            LOG.debug('Removing network {} from reservation {}'.format(
                allocation['network_id'], reservation_id))
            db_api.network_allocation_destroy(allocation['id'])

    def _allocations_to_remove(self, dates_before, dates_after,
                               network_properties, resource_properties,
                               allocs):
        """Finds candidate network allocations to remove"""
        allocs_to_remove = []
        requested_network_ids = [network['id'] for network in
                                 self._filter_networks_by_properties(
                                 network_properties, resource_properties)]

        for alloc in allocs:
            if alloc['network_id'] not in requested_network_ids:
                allocs_to_remove.append(alloc)
                continue
            if (dates_before['start_date'] > dates_after['start_date'] or
                    dates_before['end_date'] < dates_after['end_date']):
                reserved_periods = db_utils.get_reserved_periods(
                    alloc['network_id'],
                    dates_after['start_date'],
                    dates_after['end_date'],
                    datetime.timedelta(seconds=1),
                    resource_type='network')

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

        kept_networks = len(allocs) - len(allocs_to_remove)
        if kept_networks > 1:
            allocs_to_remove.extend(
                [allocation for allocation in allocs
                 if allocation not in allocs_to_remove
                 ][:(kept_networks - 1)]
            )

        return allocs_to_remove

    def _filter_networks_by_properties(self, network_properties,
                                       resource_properties):
        filter = []
        if network_properties:
            filter += plugins_utils.convert_requirements(network_properties)
        if resource_properties:
            filter += plugins_utils.convert_requirements(resource_properties)
        if filter:
            return db_api.network_get_all_by_queries(filter)
        else:
            return db_api.network_list()
