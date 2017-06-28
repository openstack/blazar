# Copyright 2017 NTT Corporation. All Rights Reserved.
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

import datetime
import time

from oslo_log import log as logging
from tempest.common import waiters
from tempest import config
from tempest.lib import decorators
from tempest.lib import exceptions
from tempest.scenario import resource_reservation_scenario as rrs

CONF = config.CONF

LOG = logging.getLogger(__name__)


class TestHostReservationScenario(rrs.ResourceReservationScenarioTest):
    """A Scenario test class that checks host reservation."""

    MAX_RETRY = 20
    WAIT_TIME = 2

    def setUp(self):
        super(TestHostReservationScenario, self).setUp()
        self.aggr_client = self.os_admin.aggregates_client

    def tearDown(self):
        super(TestHostReservationScenario, self).tearDown()

    def fetch_one_compute_host(self):
        """Returns a first host listed in nova-compute services."""
        compute = next(iter(self.os_admin.services_client.
                            list_services(binary='nova-compute')['services']))
        return compute

    def get_lease_body(self, lease_name, host_name):
        current_time = datetime.datetime.utcnow()
        end_time = current_time + datetime.timedelta(hours=1)
        body = {
            "start_date": current_time.strftime('%Y-%m-%d %H:%M'),
            "end_date": end_time.strftime('%Y-%m-%d %H:%M'),
            "name": lease_name,
            "events": [],
            }
        body["reservations"] = [
            {
                "hypervisor_properties": ('["==", "$hypervisor_hostname", "'
                                          '%s"]' % host_name),
                "max": 1,
                "min": 1,
                "resource_type": 'physical:host',
                "resource_properties": ''
                }
            ]

        return body

    def fetch_aggregate_by_name(self, name):
        aggregates = self.aggr_client.list_aggregates()['aggregates']
        try:
            aggr = next(iter(filter(lambda aggr: aggr['name'] == name,
                                    aggregates)))
        except StopIteration:
            err_msg = "aggregate with name %s doesn't exist." % name
            raise exceptions.NotFound(err_msg)
        return aggr

    @decorators.attr(type='smoke')
    def test_host_reservation(self):

        def wait_until_aggregated(aggregate_name, host_name):
            for i in xrange(self.MAX_RETRY):
                try:
                    aggr = self.fetch_aggregate_by_name(aggregate_name)
                    self.assertTrue(host_name in aggr['hosts'])
                    return
                except Exception:
                    pass
                time.sleep(self.WAIT_TIME)
            err_msg = ("hostname %s doesn't exist in aggregate %s."
                       % (host_name, aggregate_name))
            raise exceptions.NotFound(err_msg)

        host = self.fetch_one_compute_host()
        self.reservation_client.create_host({'name': host['host']})

        # check the host is in freepool
        freepool = self.fetch_aggregate_by_name('freepool')
        self.assertTrue(host['host'] in freepool['hosts'])

        # create new lease and start reservation immediatly
        body = self.get_lease_body('scenario-1', host['host'])
        lease = self.reservation_client.create_lease(body)['lease']

        # check host added to the reservation
        reservation_id = next(iter(lease['reservations']))['id']
        wait_until_aggregated(reservation_id, host['host'])

        # create an instance with reservation id
        create_kwargs = {
            'scheduler_hints': {
                "reservation": reservation_id,
                },
            'image_id': CONF.compute.image_ref,
            'flavor': CONF.compute.flavor_ref,
            }
        server = self.create_server(clients=self.os_admin,
                                    **create_kwargs)
        # ensure server is located on the requested host
        self.assertEqual(host['host'], server['OS-EXT-SRV-ATTR:host'])

        # delete the lease, which should trigger termination of the instance
        self.reservation_client.delete_lease(lease['id'])
        waiters.wait_for_server_termination(self.os_admin.servers_client,
                                            server['id'])

        # create an instance without reservation id, which is expected to fail
        create_kwargs = {
            'image_id': CONF.compute.image_ref,
            'flavor': CONF.compute.flavor_ref,
            }
        server = self.create_server(clients=self.os_admin,
                                    wait_until=None,
                                    **create_kwargs)
        waiters.wait_for_server_status(self.os_admin.servers_client,
                                       server['id'], 'ERROR',
                                       raise_on_error=False)
