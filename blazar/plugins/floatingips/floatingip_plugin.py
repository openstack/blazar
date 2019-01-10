# Copyright (c) 2019 NTT.
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

from oslo_log import log as logging

from blazar.db import api as db_api
from blazar.db import exceptions as db_ex
from blazar import exceptions
from blazar.manager import exceptions as manager_ex
from blazar.plugins import base
from blazar.plugins import floatingips as plugin
from blazar.utils.openstack import neutron


LOG = logging.getLogger(__name__)


class FloatingIpPlugin(base.BasePlugin):
    """Plugin for floating IP resource."""

    resource_type = plugin.RESOURCE_TYPE
    title = 'Floating IP Plugin'
    description = 'This plugin creates and assigns floating IPs.'

    def reserve_resource(self, reservation_id, values):
        raise NotImplementedError

    def on_start(self, resource_id):
        raise NotImplementedError

    def on_end(self, resource_id):
        raise NotImplementedError

    def validate_floatingip_params(self, values):
        marshall_attributes = set(['floating_network_id',
                                   'floating_ip_address'])
        missing_attr = marshall_attributes - set(values.keys())
        if missing_attr:
            raise manager_ex.MissingParameter(param=','.join(missing_attr))

    def create_floatingip(self, values):

        self.validate_floatingip_params(values)

        network_id = values.pop('floating_network_id')
        floatingip_address = values.pop('floating_ip_address')

        pool = neutron.FloatingIPPool(network_id)
        # validate the floating ip address is out of allocation_pools and
        # within its subnet cidr.
        try:
            subnet = pool.fetch_subnet(floatingip_address)
        except exceptions.BlazarException:
            LOG.info("Floating IP %s in network %s can't be used "
                     "for Blazar's resource.", floatingip_address, network_id)
            raise

        floatingip_values = {
            'floating_network_id': network_id,
            'subnet_id': subnet['id'],
            'floating_ip_address': floatingip_address
        }

        floatingip = db_api.floatingip_create(floatingip_values)

        return floatingip

    def get_floatingip(self, fip_id):
        fip = db_api.floatingip_get(fip_id)
        if fip is None:
            raise manager_ex.FloatingIPNotFound(floatingip=fip_id)
        return fip

    def list_floatingip(self):
        fips = db_api.floatingip_list()
        return fips

    def delete_floatingip(self, fip_id):
        fip = db_api.floatingip_get(fip_id)
        if fip is None:
            raise manager_ex.FloatingIPNotFound(floatingip=fip_id)

        # TODO(masahito): Check no allocation exists for the floating ip here
        # once this plugin supports reserve_resource method.

        try:
            db_api.floatingip_destroy(fip_id)
        except db_ex.BlazarDBException as e:
            raise manager_ex.CantDeleteFloatingIP(floatingip=fip_id,
                                                  msg=str(e))
