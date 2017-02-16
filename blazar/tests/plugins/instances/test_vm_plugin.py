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

import eventlet
from novaclient import exceptions as nova_exceptions
from oslo_log import log as logging
import testtools

from blazar import exceptions as blazar_exceptions
from blazar.plugins.instances import vm_plugin
from blazar import tests
from blazar.utils.openstack import nova


class VMPluginTestCase(tests.TestCase):
    def setUp(self):
        super(VMPluginTestCase, self).setUp()
        self.nova = nova
        self.exc = blazar_exceptions
        self.logging = logging
        self.sys = sys

        # To speed up the test run
        self.eventlet = eventlet
        self.eventlet_sleep = self.patch(self.eventlet, 'sleep')

        self.fake_id = '1'

        self.nova_wrapper = self.patch(self.nova.NovaClientWrapper, 'nova')
        self.plugin = vm_plugin.VMPlugin()

    def test_on_start_ok(self):
        self.plugin.on_start(self.fake_id)

        self.nova_wrapper.servers.unshelve.assert_called_once_with('1')

    @testtools.skip('Will be released later')
    def test_on_start_fail(self):
        def raise_exception(resource_id):
            raise blazar_exceptions.Conflict(409)

        self.nova_wrapper.servers.unshelve.side_effect = raise_exception
        self.plugin.on_start(self.fake_id)

    def test_on_end_create_image_ok(self):
        self.patch(self.plugin, '_split_actions').return_value = (
            ['create_image'])
        self.patch(self.plugin, '_check_active').return_value = True

        self.plugin.on_end(self.fake_id)

        self.nova_wrapper.servers.create_image.assert_called_once_with('1')

    def test_on_end_suspend_ok(self):
        self.patch(self.plugin, '_split_actions').return_value = ['suspend']

        self.plugin.on_end(self.fake_id)
        self.nova_wrapper.servers.suspend.assert_called_once_with('1')

    def test_on_end_delete_ok(self):
        self.patch(self.plugin, '_split_actions').return_value = ['delete']

        self.plugin.on_end(self.fake_id)
        self.nova_wrapper.servers.delete.assert_called_once_with('1')

    def test_on_end_create_image_instance_or_not_found(self):
        def raise_exception(resource_id):
            raise nova_exceptions.NotFound(404)

        self.nova_wrapper.servers.create_image.side_effect = raise_exception

        self.plugin.on_end(self.fake_id)
        self.nova_wrapper.servers.delete.assert_called_once_with('1')

    def test_on_end_create_image_ko_invalid_vm_state(self):
        def raise_exception(resource_id):
            raise nova_exceptions.Conflict(409)

        self.nova_wrapper.servers.create_image.side_effect = raise_exception

        self.plugin.on_end(self.fake_id)
        self.nova_wrapper.servers.delete.assert_called_once_with('1')

    @testtools.skip('Will be released later')
    def test_on_end_timeout(self):
        self.patch(self.plugin, '_split_actions').return_value = (
            ['create_image'])
        self.assertRaises(self.exc.Timeout,
                          self.plugin.on_end,
                          self.fake_id)

    @testtools.skip('Will be released later')
    def test_check_active(self):
        pass
