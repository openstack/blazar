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

import eventlet
from oslo.config import cfg

from climate import exceptions as climate_exceptions
from climate.openstack.common import log as logging
from climate.plugins import base
from climate.utils.openstack import nova

LOG = logging.getLogger(__name__)


plugin_opts = [
    cfg.StrOpt('on_end',
               default='create_image, delete',
               help='Actions which we will use in the end of the lease')
]

CONF = cfg.CONF
CONF.register_opts(plugin_opts, 'virtual:instance')


class VMPlugin(base.BasePlugin):
    """Base plugin for VM reservation."""
    resource_type = 'virtual:instance'
    title = "Basic VM Plugin"
    description = ("This is basic plugin for VM management. "
                   "It can start, snapshot and suspend VMs")

    def on_start(self, resource_id):
        nova_client = nova.ClimateNovaClient()
        try:
            nova_client.servers.unshelve(resource_id)
        except nova_client.exceptions.Conflict:
            LOG.error("Instance have been unshelved")

    def on_end(self, resource_id):
        nova_client = nova.ClimateNovaClient()
        actions = self._split_actions(CONF['virtual:instance'].on_end)

        # actions will be processed in following order:
        # - create image from VM
        # - suspend VM
        # - delete VM
        # this order guarantees there will be no situations like
        # creating snapshot or suspending already deleted instance

        if 'create_image' in actions:
            with eventlet.timeout.Timeout(600, climate_exceptions.Timeout):
                try:
                    nova_client.servers.create_image(resource_id)
                    eventlet.sleep(5)
                    while not self._check_active(resource_id, nova_client):
                        eventlet.sleep(1)
                except nova_client.exceptions.NotFound:
                    LOG.error('Instance %s has been already deleted. '
                              'Cannot create image.' % resource_id)
                except climate_exceptions.Timeout:
                    LOG.error('Image create failed with timeout. Take a look '
                              'at nova.')

        if 'suspend' in actions:
            try:
                nova_client.servers.suspend(resource_id)
            except nova_client.exceptions.NotFound:
                LOG.error('Instance %s has been already deleted. '
                          'Cannot suspend instance.' % resource_id)

        if 'delete' in actions:
            try:
                nova_client.servers.delete(resource_id)
            except nova_client.exceptions.NotFound:
                LOG.error('Instance %s has been already deleted. '
                          'Cannot delete instance.' % resource_id)

    def _check_active(self, resource_id, curr_client):
        instance = curr_client.servers.get(resource_id)
        task_state = getattr(instance, 'OS-EXT-STS:task_state', None)
        if task_state is None:
            return True

        if task_state.upper() in ['IMAGE_SNAPSHOT', 'IMAGE_PENDING_UPLOAD',
                                  'IMAGE_UPLOADING']:
            return False
        else:
            LOG.error('Nova reported unexpected task status %s for '
                      'instance %s' % (task_state, resource_id))
            raise climate_exceptions.TaskFailed()

    def _split_actions(self, actions):
        try:
            return actions.replace(' ', '').split(',')
        except AttributeError:
            raise climate_exceptions.WrongFormat()
