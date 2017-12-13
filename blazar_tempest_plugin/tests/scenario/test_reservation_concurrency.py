# Copyright 2017 University of Chicago. All Rights Reserved.
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

from multiprocessing.pool import ThreadPool

from blazar_tempest_plugin.tests.scenario import (
    resource_reservation_scenario as rrs)


class TestReservationConcurrencyScenario(rrs.ResourceReservationScenarioTest):
    """A Scenario test class checking Blazar handles concurrent requests."""

    MAX_CONCURRENCY = 10

    def setUp(self):
        super(TestReservationConcurrencyScenario, self).setUp()

    def tearDown(self):
        super(TestReservationConcurrencyScenario, self).tearDown()

    def test_concurrent_list_lease(self):
        # run lease-list requests in parallel to check service concurrency
        results = []
        pool = ThreadPool(self.MAX_CONCURRENCY)
        for i in range(0, self.MAX_CONCURRENCY):
            results.append(
                pool.apply_async(self.reservation_client.list_lease, ()))

        pool.close()
        pool.join()
        results = [r.get() for r in results]
        for r in results:
            self.assertEqual('200', r.response['status'])
