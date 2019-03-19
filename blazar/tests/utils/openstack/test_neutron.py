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

import mock
import neutronclient
from neutronclient.common import exceptions as neutron_exceptions
from oslo_config import cfg
from oslo_config import fixture

from blazar import tests
from blazar.utils.openstack import exceptions
from blazar.utils.openstack import neutron

CONF = cfg.CONF


class TestBlazarNeutronClient(tests.TestCase):
    def setUp(self):
        super(TestBlazarNeutronClient, self).setUp()
        self.cfg = self.useFixture(fixture.Config(CONF))

    def test_client_from_kwargs(self):
        kwargs = {
            'auth_url': 'http://foo:8080/identity/v3'
        }
        client = neutron.BlazarNeutronClient(**kwargs)
        self.assertEqual("http://foo:8080/identity/v3",
                         client.neutron.httpclient.session.auth.auth_url)


class TestFloatingIPPool(tests.TestCase):
    def setUp(self):
        super(TestFloatingIPPool, self).setUp()

    @mock.patch.object(neutronclient.v2_0.client.Client, 'show_network')
    def test_init_floatingippool(self, mock_net):
        mock_net.return_value = {'network': {'id': 'net-id'}}
        client = neutron.FloatingIPPool('net-id')
        self.assertEqual('net-id', client.network_id)
        mock_net.assert_called_once_with('net-id')

    @mock.patch.object(neutronclient.v2_0.client.Client, 'show_network')
    def test_init_with_invalid_network_id(self, mock_net):
        mock_net.side_effect = neutron_exceptions.NotFound()

        self.assertRaises(exceptions.FloatingIPNetworkNotFound,
                          neutron.FloatingIPPool, 'invalid-net-id')
