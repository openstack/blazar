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

import itertools

import climate.api.v2.app
import climate.api.v2.controllers
import climate.cmd.api
import climate.config
import climate.db.base
import climate.db.migration.cli
import climate.manager
import climate.manager.service
import climate.notification.notifier
import climate.openstack.common.db.options
import climate.plugins.instances.vm_plugin
import climate.plugins.oshosts.host_plugin
import climate.plugins.oshosts.reservation_pool
import climate.utils.openstack.keystone
import climate.utils.openstack.nova


def list_opts():
    return [
        ('DEFAULT',
         itertools.chain(
             climate.api.v2.app.auth_opts,
             climate.cmd.api.api_opts,
             climate.cmd.api.opts,
             climate.config.cli_opts,
             climate.config.os_opts,
             climate.db.base.db_driver_opts,
             climate.db.migration.cli.command_opts,
             climate.utils.openstack.keystone.opts,
             climate.utils.openstack.keystone.keystone_opts,
             climate.utils.openstack.nova.nova_opts)),
        ('api', climate.api.v2.controllers.api_opts),
        ('manager', itertools.chain(climate.manager.opts,
                                    climate.manager.service.manager_opts)),
        ('notifications', climate.notification.notifier.notification_opts),
        ('database', climate.openstack.common.db.options.database_opts),
        (climate.plugins.instances.RESOURCE_TYPE,
         climate.plugins.instances.vm_plugin.plugin_opts),
        (climate.plugins.oshosts.RESOURCE_TYPE, itertools.chain(
            climate.plugins.oshosts.host_plugin.plugin_opts,
            climate.plugins.oshosts.reservation_pool.OPTS)),

    ]
