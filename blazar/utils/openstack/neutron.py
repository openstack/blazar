# Copyright (c) 2019 NTT.
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

from keystoneauth1.identity import v3
from keystoneauth1 import session
import netaddr
from neutronclient.common import exceptions as neutron_exceptions
from neutronclient.v2_0 import client as neutron_client

from oslo_config import cfg
from oslo_log import log as logging

from blazar import context
from blazar.utils.openstack import base
from blazar.utils.openstack import exceptions


neutron_opts = [
    cfg.StrOpt('endpoint_type',
               default='internal',
               choices=['public', 'admin', 'internal'],
               help='Type of the neutron endpoint to use. This endpoint will '
                    'be looked up in the keystone catalog and should be one '
                    'of public, internal or admin.'),
]

CONF = cfg.CONF
CONF.register_opts(neutron_opts, group='neutron')
LOG = logging.getLogger(__name__)


class BlazarNeutronClient(object):
    """Client class for Neutron service."""

    def __init__(self, **kwargs):
        ctx = kwargs.pop('ctx', None)
        username = kwargs.pop('username',
                              CONF.os_admin_username)
        password = kwargs.pop('password',
                              CONF.os_admin_password)
        project_name = kwargs.pop('project_name',
                                  CONF.os_admin_project_name)
        user_domain_name = kwargs.pop('user_domain_name',
                                      CONF.os_admin_user_domain_name)
        project_domain_name = kwargs.pop('project_domain_name',
                                         CONF.os_admin_project_domain_name)
        auth_url = kwargs.pop('auth_url', None)
        region_name = kwargs.pop('region_name', CONF.os_region_name)
        if ctx is None:
            try:
                ctx = context.current()
            except RuntimeError:
                pass
        if ctx is not None:
            kwargs.setdefault('global_request_id', ctx.global_request_id)

        if auth_url is None:
            auth_url = "%s://%s:%s" % (CONF.os_auth_protocol,
                                       base.get_os_auth_host(CONF),
                                       CONF.os_auth_port)
            if CONF.os_auth_prefix:
                auth_url += "/%s" % CONF.os_auth_prefix
            if CONF.os_auth_version:
                auth_url += "/%s" % CONF.os_auth_version

        auth = v3.Password(auth_url=auth_url,
                           username=username,
                           password=password,
                           project_name=project_name,
                           user_domain_name=user_domain_name,
                           project_domain_name=project_domain_name)
        sess_kwargs = dict(
            auth=auth
        )
        if CONF.cafile:
            sess_kwargs.update(verify=CONF.cafile)
        sess = session.Session(**sess_kwargs)
        kwargs.setdefault('session', sess)
        kwargs.setdefault('region_name', region_name)
        kwargs.setdefault('endpoint_type', CONF.neutron.endpoint_type + 'URL')
        self.neutron = neutron_client.Client(**kwargs)


class FloatingIPPool(BlazarNeutronClient):

    def __init__(self, network_id, **kwargs):
        super(FloatingIPPool, self).__init__(**kwargs)

        try:
            self.neutron.show_network(network_id)
        except neutron_exceptions.NotFound:
            LOG.info('Failed to find network %s.', network_id)
            raise exceptions.FloatingIPNetworkNotFound(network=network_id)

        self.network_id = network_id

    def fetch_subnet(self, floatingip):
        fip = netaddr.IPAddress(floatingip)
        network = self.neutron.show_network(self.network_id)['network']
        subnet_ids = network['subnets']

        for sub_id in subnet_ids:
            subnet = self.neutron.show_subnet(sub_id)['subnet']
            cidr = netaddr.IPNetwork(subnet['cidr'])

            # skip the subnet because it has not valid cidr for the floating ip
            if fip not in cidr:
                continue

            allocated_ip = netaddr.IPSet()

            allocated_ip.add(netaddr.IPAddress(subnet['gateway_ip']))
            for alloc in subnet['allocation_pools']:
                allocated_ip.add(netaddr.IPRange(alloc['start'], alloc['end']))

            if fip in allocated_ip:
                raise exceptions.NeutronUsesFloatingIP(floatingip=fip,
                                                       subnet=subnet['id'])
            else:
                self.subnet_id = subnet['id']
                return subnet

        raise exceptions.FloatingIPSubnetNotFound(fip=floatingip)

    def create_reserved_floatingip(self, subnet_id, address, project_id,
                                   reservation_id):
        body = {
            'floatingip': {
                'floating_network_id': self.network_id,
                'subnet_id': subnet_id,
                'floating_ip_address': address,
                'project_id': project_id
            }
        }
        fip = self.neutron.create_floatingip(body)['floatingip']
        body = {
            'tags': ['blazar', 'reservation:%s' % reservation_id]
        }
        self.neutron.replace_tag('floatingips', fip['id'], body)

    def delete_reserved_floatingip(self, address):
        query = {
            'floating_ip_address': address,
            'floating_network_id': self.network_id
        }
        fips = self.neutron.list_floatingips(**query)['floatingips']
        if not fips:
            # The floating ip address already deleted by the user.
            return None

        fip = next(iter(fips))
        if fip['port_id']:
            # Deassociate the floating ip from the attached port because
            # the delete floatingip API deletes both the floating ip and
            # associated port.
            body = {
                'floatingip': {
                    'port_id': None,
                }
            }
            self.neutron.update_floatingip(fip['id'], body)

        self.neutron.delete_floatingip(fip['id'])
