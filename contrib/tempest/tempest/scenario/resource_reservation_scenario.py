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

from tempest import config_resource_reservation as config
from tempest import exceptions
from tempest.openstack.common import log
from tempest import resource_reservation_client_manager as clients
from tempest.scenario import manager as clientTest
import tempest.test

CONF = config.CONF

LOG = log.getLogger(__name__)


class ResourceReservationScenarioTest(clientTest.OfficialClientTest):
    """Base class for resource reservation scenario tests."""

    @classmethod
    def setUpClass(cls):
        super(ResourceReservationScenarioTest, cls).setUpClass()
        if not CONF.service_available.climate:
            raise cls.skipException("Resource reservation support is required")

        username, password, tenant_name = cls.credentials()
        cls.manager = clients.ResourceReservationManager(
            username, password, tenant_name)
        cls.resource_reservation_client = (
            cls.manager.resource_reservation_client)

    def get_lease_by_name(self, lease_name):
        # the same as the climateclient does it: ask for the entire list
        lease_list = self.resource_reservation_client.lease.list()
        named_lease = []

        # and then search by lease_name
        named_lease = (
            filter(lambda lease: lease['name'] == lease_name, lease_list))

        if named_lease:
            return self.resource_reservation_client.lease.get(
                named_lease[0]['id'])
        else:
            message = "Unable to find lease with name '%s'" % lease_name
            raise exceptions.NotFound(message)

    def wait_for_lease_end(self, lease_id):

        def check_lease_end():
            try:
                lease = self.resource_reservation_client.lease.get(lease_id)
                if lease:
                    events = lease['events']
                    return len(filter(lambda evt:
                                      evt['event_type'] == 'end_lease' and
                                      evt['status'] == 'DONE',
                                      events)) > 0
                else:
                    LOG.info("Lease with id %s is empty" % lease_id)
            except Exception as e:
                LOG.info("Unable to find lease with id %s. Exception: %s"
                         % (lease_id, e.message))
            return True

        if not tempest.test.call_until_true(
            check_lease_end,
            CONF.resource_reservation.lease_end_timeout,
                CONF.resource_reservation.lease_interval):
            message = "Timed out waiting for lease to change status to DONE"
            raise exceptions.TimeoutException(message)

    def remove_image_snapshot(self, image_name):
        try:
            image = filter(lambda i:
                           i.name == image_name,
                           self.compute_client.images.list())
            self.compute_client.images.delete(image)
        except Exception as e:
            LOG.info("Unable to delete %s snapshot. Exception: %s"
                     % (image_name, e.message))
