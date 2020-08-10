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

import blazar.api.v2.app
import blazar.api.v2.controllers
import blazar.cmd.api
import blazar.config
import blazar.db.base
import blazar.db.migration.cli
import blazar.manager
import blazar.manager.service
import blazar.notification.notifier
import blazar.plugins.oshosts.host_plugin
import blazar.utils.openstack.keystone
import blazar.utils.openstack.nova


def list_opts():
    return [
        ('DEFAULT',
         itertools.chain(
             blazar.api.v2.app.auth_opts,
             blazar.cmd.api.opts,
             blazar.config.api_opts,
             blazar.config.cli_opts,
             blazar.config.lease_opts,
             blazar.config.os_opts,
             blazar.db.base.db_driver_opts,
             blazar.db.migration.cli.command_opts,
             blazar.utils.openstack.keystone.opts,
             blazar.utils.openstack.keystone.keystone_opts)),
        ('api', blazar.api.v2.controllers.api_opts),
        ('manager', itertools.chain(blazar.manager.opts,
                                    blazar.manager.service.manager_opts)),
        ('enforcement', itertools.chain(
            blazar.enforcement.filters.max_lease_duration_filter.MaxLeaseDurationFilter.enforcement_opts, # noqa
            blazar.enforcement.enforcement.enforcement_opts)),
        ('notifications', blazar.notification.notifier.notification_opts),
        ('nova', blazar.utils.openstack.nova.nova_opts),
        (blazar.plugins.oshosts.RESOURCE_TYPE,
         blazar.plugins.oshosts.host_plugin.plugin_opts),
    ]
