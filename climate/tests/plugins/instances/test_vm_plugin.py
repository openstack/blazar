# Copyright (c) 2013 Mirantis Inc.
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

import sys
import testtools

from climate import exceptions as climate_exceptions
from climate.openstack.common import log as logging
from climate.plugins.instances import vm_plugin
from climate import tests
from climate.utils.openstack import nova


class VMPluginTestCase(tests.TestCase):
    def setUp(self):
        super(VMPluginTestCase, self).setUp()
        self.plugin = vm_plugin.VMPlugin()
        self.nova = nova
        self.exc = climate_exceptions
        self.logging = logging
        self.sys = sys

        self.client = self.patch(self.nova, 'ClimateNovaClient')
        self.fake_id = '1'

    def test_on_start_ok(self):
        self.plugin.on_start(self.fake_id)

        self.client.return_value.servers.unshelve.assert_called_once_with('1')

    @testtools.skip('Will be released later')
    def test_on_start_fail(self):
        self.client.side_effect = \
            self.nova.ClimateNovaClient.exceptions.Conflict

        self.plugin.on_start(self.fake_id)

    def test_on_end_create_image_ok(self):
        self.patch(self.plugin, '_split_actions').return_value =\
            ['create_image']
        self.patch(self.plugin, '_check_active').return_value =\
            True

        self.plugin.on_end(self.fake_id)

        self.client.return_value.servers.create_image.assert_called_once_with(
            '1')

    def test_on_end_suspend_ok(self):
        self.patch(self.plugin, '_split_actions').return_value =\
            ['suspend']

        self.plugin.on_end(self.fake_id)
        self.client.return_value.servers.suspend.assert_called_once_with('1')

    def test_on_end_delete_ok(self):
        self.patch(self.plugin, '_split_actions').return_value =\
            ['delete']

        self.plugin.on_end(self.fake_id)
        self.client.return_value.servers.delete.assert_called_once_with('1')

    def test_on_end_instance_deleted(self):
        self.client.side_effect = \
            self.nova.ClimateNovaClient.exceptions.NotFound

        self.assertRaises(self.exc.TaskFailed,
                          self.plugin.on_end,
                          self.fake_id)

    @testtools.skip('Will be released later')
    def test_on_end_timeout(self):
        self.patch(self.plugin, '_split_actions').return_value =\
            ['create_image']
        self.assertRaises(self.exc.Timeout,
                          self.plugin.on_end,
                          self.fake_id)

    @testtools.skip('Will be released later')
    def test_check_active(self):
        pass
