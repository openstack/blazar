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

from oslo.config import cfg

from climate import context
from climate.db import api as db_api
from climate.manager import exceptions as manager_exceptions
from climate.plugins import base
from climate.plugins.oshosts import nova_inventory
from climate.plugins.oshosts import reservation_pool as rp
from climate.utils import service as service_utils


class PhysicalHostPlugin(base.BasePlugin):
    """Plugin for physical host resource."""
    resource_type = 'physical:host'
    title = 'Physical Host Plugin'
    description = 'This plugin starts and shutdowns the hosts.'
    freepool_name = cfg.CONF[resource_type].aggregate_freepool_name
    pool = None
    inventory = None

    def on_start(self, resource_id):
        """Add the hosts in the pool."""
        pass

    def on_end(self, resource_id):
        """Remove the hosts from the pool."""
        pass

    def setup(self, conf):
        # Create freepool if not exists
        with context.ClimateContext() as ctx:
            ctx = ctx.elevated()
            if self.pool is None:
                self.pool = rp.ReservationPool()
            if self.inventory is None:
                self.inventory = nova_inventory.NovaInventory()
        if not self._freepool_exists():
            self.pool.create(name=self.freepool_name, az=None)

    def _freepool_exists(self):
        try:
            self.pool.get_aggregate_from_name_or_id(self.freepool_name)
            return True
        except manager_exceptions.AggregateNotFound:
            return False

    def _get_extra_capabilities(self, host_id):
        extra_capabilities = {}
        raw_extra_capabilities = \
            db_api.host_extra_capability_get_all_per_host(host_id)
        for capability in raw_extra_capabilities:
            extra_capabilities[capability['capability_name']] = \
                capability['capability_value']
        return extra_capabilities

    @service_utils.export_context
    def get_computehost(self, host_id):
        host = db_api.host_get(host_id)
        extra_capabilities = self._get_extra_capabilities(host_id)
        if host is not None and extra_capabilities:
            res = host.copy()
            res.update(extra_capabilities)
            return res
        else:
            return host

    @service_utils.export_context
    def list_computehosts(self):
        raw_host_list = db_api.host_list()
        host_list = []
        for host in raw_host_list:
            host_list.append(self.get_computehost(host['id']))
        return host_list

    @service_utils.export_context
    def create_computehost(self, host_values):
        # TODO(sbauza):
        #  - Exception handling for HostNotFound
        host_id = host_values.pop('id', None)
        host_name = host_values.pop('name', None)

        host_ref = host_id or host_name
        if host_ref is None:
            raise manager_exceptions.InvalidHost(host=host_values)
        servers = self.inventory.get_servers_per_host(host_ref)
        if servers:
            raise manager_exceptions.HostHavingServers(host=host_ref,
                                                       servers=servers)
        host_details = self.inventory.get_host_details(host_ref)
        # NOTE(sbauza): Only last duplicate name for same extra capability will
        #  be stored
        extra_capabilities_keys = \
            set(host_values.keys()) - set(host_details.keys())
        extra_capabilities = \
            dict((key, host_values[key]) for key in extra_capabilities_keys)
        self.pool.add_computehost(self.freepool_name, host_ref)

        host = None
        cantaddextracapability = []
        try:
            host = db_api.host_create(host_details)
        except RuntimeError:
            #We need to rollback
            # TODO(sbauza): Investigate use of Taskflow for atomic transactions
            self.pool.remove_computehost(self.freepool_name, host_ref)
        if host:
            for key in extra_capabilities:
                values = {'computehost_id': host['id'],
                          'capability_name': key,
                          'capability_value': extra_capabilities[key]}
                try:
                    db_api.host_extra_capability_create(values)
                except RuntimeError:
                    cantaddextracapability.append(key)
        if cantaddextracapability:
            raise manager_exceptions.CantAddExtraCapability(
                keys=cantaddextracapability, host=host['id'])
        if host:
            return self.get_computehost(host['id'])
        else:
            return None

    @service_utils.export_context
    def update_computehost(self, host_id, values):
        # NOTE (sbauza): Only update existing extra capabilites, don't create
        #  other ones
        if values:
            cantupdateextracapability = []
            for value in values:
                capabilities = \
                    db_api.host_extra_capability_get_all_per_name(host_id,
                                                                  value)
                for raw_capability in capabilities:
                    capability = {'capability_name': value,
                                  'capability_value': values[value]}
                    try:
                        db_api.host_extra_capability_update(
                            raw_capability['id'], capability)
                    except RuntimeError:
                        cantupdateextracapability.append(
                            raw_capability['capability_name'])
            if cantupdateextracapability:
                raise manager_exceptions.CantAddExtraCapability(
                    host=host_id, keys=cantupdateextracapability)
        return self.get_computehost(host_id)

    @service_utils.export_context
    def delete_computehost(self, host_id):
        # TODO(sbauza):
        #  - Check if no leases having this host scheduled
        servers = self.inventory.get_servers_per_host(host_id)
        if servers:
            raise manager_exceptions.HostHavingServers(host=host_id,
                                                       servers=servers)
        host = db_api.host_get(host_id)
        if not host:
            raise manager_exceptions.HostNotFound(host=host_id)
        try:
            self.pool.remove_computehost(self.freepool_name,
                                         host['hypervisor_hostname'])
            # NOTE(sbauza): Extracapabilities will be destroyed thanks to
            #  the DB FK.
            db_api.host_destroy(host_id)
        except RuntimeError:
            # Nothing so bad, but we need to advert the admin he has to rerun
            raise manager_exceptions.CantRemoveHost(host=host_id,
                                                    pool=self.freepool_name)
