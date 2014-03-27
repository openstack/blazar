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

from tempest.cli import climateclient
from tempest import config_resource_reservation as config


CONF = config.CONF


class SimpleReadOnlyClimateClientTest(climateclient.ClientTestBase):
    """Basic, read-only tests for Climate CLI client.

    Basic smoke test for the Climate CLI commands which do not require
    creating or modifying leases.
    """

    @classmethod
    def setUpClass(cls):
        if (not CONF.service_available.climate):
            msg = ("Skipping all Climate cli tests because it is "
                   "not available")
            raise cls.skipException(msg)
        super(SimpleReadOnlyClimateClientTest, cls).setUpClass()

    def test_climate_lease_list(self):
        self.climate('lease-list')

    def test_climate_host_list(self):
        self.climate('host-list')

    def test_climate_version(self):
        self.climate('', flags='--version')
