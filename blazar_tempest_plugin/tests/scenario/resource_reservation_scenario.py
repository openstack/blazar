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


from oslo_log import log
from tempest import clients as tempestclients
from tempest import config
from tempest import exceptions
from tempest.lib.common.utils import test_utils

from blazar_tempest_plugin.services.reservation import (
    reservation_client as clients)
from blazar_tempest_plugin.tests.scenario import manager_freeze as manager

CONF = config.CONF

LOG = log.getLogger(__name__)


class ResourceReservationScenarioTest(manager.ScenarioTest):
    """Base class for resource reservation scenario tests."""

    credentials = ['primary', 'admin']

    @classmethod
    def setup_clients(cls):
        super(ResourceReservationScenarioTest, cls).setup_clients()
        if not (CONF.service_available.climate or
                CONF.service_available.blazar):
            raise cls.skipException("Resource reservation support is"
                                    "required")

        cred_provider = cls._get_credentials_provider()
        creds = cred_provider.get_credentials('admin')
        auth_prov = tempestclients.get_auth_provider(creds._credentials)
        cls.os_admin.resource_reservation_client = (
            clients.ResourceReservationV1Client(auth_prov,
                                                'reservation',
                                                CONF.identity.region))
        cls.reservation_client = (
            cls.os_admin.resource_reservation_client)

    def get_lease_by_name(self, lease_name):
        # the same as the blazarclient does it: ask for the entire list
        lease_list = self.reservation_client.list_lease()
        named_lease = []

        # and then search by lease_name
        named_lease = (
            filter(lambda lease: lease['name'] == lease_name, lease_list))

        if named_lease:
            return self.reservation_client.get_lease(
                named_lease[0]['id'])
        else:
            message = "Unable to find lease with name '%s'" % lease_name
            raise exceptions.NotFound(message)

    def delete_lease(self, lease_id):
        return self.reservation_client.delete_lease(lease_id)

    def wait_for_lease_end(self, lease_id):

        def check_lease_end():
            try:
                lease = self.reservation_client.get_lease(lease_id)['lease']
                if lease:
                    events = lease['events']
                    return len(filter(lambda evt:
                                      evt['event_type'] == 'end_lease' and
                                      evt['status'] == 'DONE',
                                      events)) > 0
                else:
                    LOG.info("Lease with id %s is empty", lease_id)
            except Exception as e:
                LOG.info("Unable to find lease with id %(lease_id)s. "
                         "Exception: %(message)s",
                         {'lease_id': lease_id, 'message': e.message})
            return True

        if not test_utils.call_until_true(
            check_lease_end,
            CONF.resource_reservation.lease_end_timeout,
                CONF.resource_reservation.lease_interval):
            message = "Timed out waiting for lease to change status to DONE"
            raise exceptions.TimeoutException(message)

    def remove_image_snapshot(self, image_name):
        try:
            image = filter(lambda i:
                           i['name'] == image_name,
                           self.image_client.list())
            self.image_client.delete(image)
        except Exception as e:
            LOG.info("Unable to delete %(image_name)s snapshot. "
                     "Exception: %(message)s",
                     {'image_name': image_name, 'message': e.message})

    def is_flavor_enough(self, flavor_id, image_id):
        image = self.compute_images_client.show_image(image_id)['image']
        flavor = self.flavors_client.show_flavor(flavor_id)['flavor']
        return image['minDisk'] <= flavor['disk']
