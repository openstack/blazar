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

from tempest.cli import blazarclient
from tempest import config_resource_reservation as config


CONF = config.CONF


class SimpleReadOnlyBlazarClientTest(blazarclient.ClientTestBase):
    """Basic, read-only tests for Blazar CLI client.

    Basic smoke test for the Blazar CLI commands which do not require
    creating or modifying leases.
    """

    @classmethod
    def setUpClass(cls):
        if (not CONF.service_available.blazar):
            msg = ("Skipping all Blazar cli tests because it is "
                   "not available")
            raise cls.skipException(msg)
        super(SimpleReadOnlyBlazarClientTest, cls).setUpClass()

    def test_blazar_lease_list(self):
        self.blazar('lease-list')

    def test_blazar_host_list(self):
        self.blazar('host-list')

    def test_blazar_version(self):
        self.blazar('', flags='--version')
