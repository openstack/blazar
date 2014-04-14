# Copyright 2014 Intel Corporation
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
import climateclient.client

from tempest import clients as manager
from tempest import config_resource_reservation as config
from tempest.openstack.common import log as logging

CONF = config.CONF
LOG = logging.getLogger(__name__)


class ResourceReservationManager(manager.OfficialClientManager):
    """Manager that provides access to the python climate client."""
    CLIMATECLIENT_VERSION = '1'

    def __init__(self, username, password, tenant_name):
        self.client_type = 'tempest'
        self.interface = None
        # super cares for credentials validation
        super(ResourceReservationManager, self).__init__(
            username=username, password=password, tenant_name=tenant_name)
        self.resource_reservation_client = \
            self._get_resource_reservation_client(username, password,
                                                  tenant_name)

    def _get_resource_reservation_client(self, username, password,
                                         tenant_name):
        self._validate_credentials(username, password, tenant_name)
        climate_url = self.identity_client.service_catalog.url_for(
            service_type='reservation')
        token = self.identity_client.auth_token
        return climateclient.client.Client(self.CLIMATECLIENT_VERSION,
                                           climate_url, token)
