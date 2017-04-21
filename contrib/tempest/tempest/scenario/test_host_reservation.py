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
        self.aggr_client = self.admin_manager.aggregates_client

    def tearDown(self):
        super(TestHostReservationScenario, self).tearDown()

    def fetch_one_compute_host(self):
        """Returns a first host listed in nova-compute services."""
        compute = next(iter(self.admin_manager.services_client.
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
        server = self.create_server(clients=self.admin_manager,
                                    **create_kwargs)
        # ensure server is located on the requested host
        self.assertEqual(host['host'], server['OS-EXT-SRV-ATTR:host'])

        # create an instance without reservation id, which is expected to fail
        create_kwargs = {
            'image_id': CONF.compute.image_ref,
            'flavor': CONF.compute.flavor_ref,
            }
        server = self.create_server(clients=self.admin_manager,
                                    wait_until=None,
                                    **create_kwargs)

        # TODO(masahito) the try-except statement is a quick fix for nova's bug
        # https://bugs.launchpad.net/nova/+bug/1693438. After fixing the bug
        # remove the try-except. extra_timeout argument is added for ensuring
        # the server remains in BUILD status longer than instance boots time.
        try:
            waiters.wait_for_server_status(self.admin_manager.servers_client,
                                           server['id'], 'ERROR',
                                           raise_on_error=False,
                                           extra_timeout=100)
        except exceptions.TimeoutException:
            # check the server's status remains in BUILD status
            waiters.wait_for_server_status(self.admin_manager.servers_client,
                                           server['id'], 'BUILD')
